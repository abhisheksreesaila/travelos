"""Around you (F-073): food, coffee, groceries, a pharmacy, gas or a restroom near where the family is standing, from OpenStreetMap.

    search(cat, lat, lon, mode, now, ...) -> {"items": [...], "ai": bool}   the model: places near a point, ranked
    open_now(spec, now) -> True | False | None                            OpenStreetMap's opening_hours, for the common forms
    vegetarian(session), set_vegetarian(session, on)                       the family's food preference (family_prefs)

Where the places come from: the Overpass API (https://overpass-api.de/api/interpreter, then the public mirrors in MIRRORS when it refuses or is slow, F-095), one GET per (category, rounded point, radius), at most one
request every two seconds for the whole process, GitAway's User-Agent, a short timeout, and ten minutes of silence after a 429 or 403 (the same etiquette
and the same `geo.Gate` as the geocoder). Answers are kept in this process for 30 minutes under (category, point rounded to ~110 m, radius), so a second
person standing at the same spot costs nothing. Tests never reach Overpass: they replace `geo.fetch` (the one function that does a GET).

Privacy. The point a person is at is used for the request that carries it and is never stored: not in the family database, not in the log, not in the
cache key beyond the rounding above. Overpass gets that rounded point and the category. The AI (job "around-you", optional) gets the category, the food
preference and up to 15 places (name, distance, open now, a few tags); never coordinates, never a family member's name. If it is off, busy or answers
badly, places are ranked by distance with closed ones last. See docs/ai-usage.md and /privacy.
"""

import json
import math
import re
import threading
import time
from datetime import datetime
from urllib.parse import quote

from gitaway import ai, familydb, geo, session as ses

MIRRORS = ("https://overpass-api.de/api/interpreter?data={q}",            # F-095: the main server often refuses or is slow from a cloud host,
           "https://overpass.kumi.systems/api/interpreter?data={q}",       # so the public mirrors are asked in turn
           "https://overpass.private.coffee/api/interpreter?data={q}")
OVERPASS = MIRRORS[0]
WALK_M, DRIVE_M = 1500, 8000
RADIUS = {"walk": WALK_M, "drive": DRIVE_M}
TIMEOUT = 9          # seconds one mirror may take (the query itself asks the server for 8)
BUDGET = 20          # seconds all the mirrors together may take for one search
GAP = 2.0            # seconds between two calls to Overpass, whole process
TTL = 30 * 60        # seconds a result is kept
CACHE_MAX = 200
CANDIDATES = 15      # places the model sees
SHOW = 5             # places a person sees
WALK_M_PER_MIN, DRIVE_M_PER_MIN = 80, 600   # about 3 mph on foot, 22 mph in town
ROUND = 3            # decimals of a degree kept for the query and the cache (about 110 m)

_clock = time.monotonic
GATES = tuple(geo.Gate(GAP) for _ in MIRRORS)   # each mirror is paced, and left alone after it refuses us, on its own
GATE = GATES[0]
_cache: dict = {}
_lock = threading.Lock()

FOOD = r"^(restaurant|fast_food|cafe)$"
# key -> label, icon, filters (Overpass tag filters, each one OR-ed), a default name for a place with none, the kind of plan "Add to plan" makes
CATEGORIES = {
    "veg": dict(label="Vegetarian food", icon="leaf", noname="Vegetarian place", kind="food",
                strict=[f'["amenity"~"{FOOD}"]["diet:vegetarian"~"^(yes|only)$"]', f'["amenity"~"{FOOD}"]["cuisine"~"vegetarian|vegan"]', f'["amenity"~"{FOOD}"]["diet:vegan"~"^(yes|only)$"]'],
                loose=[f'["amenity"~"{FOOD}"]["diet:vegetarian"~"^(yes|only|limited)$"]', f'["amenity"~"{FOOD}"]["cuisine"~"vegetarian|vegan"]', f'["amenity"~"{FOOD}"]["diet:vegan"~"^(yes|only|limited)$"]']),
    "coffee": dict(label="Coffee", icon="coffee", noname="Coffee place", kind="food", filters=['["amenity"="cafe"]']),
    "groc": dict(label="Groceries", icon="cart", noname="Grocery store", kind="fun", filters=['["shop"~"^(supermarket|convenience|greengrocer)$"]']),
    "big": dict(label="Costco / Walmart", icon="store", noname="Store", kind="fun", filters=['["brand"~"Costco|Walmart",i]', '["name"~"Costco|Walmart",i]']),
    "rx": dict(label="Pharmacy", icon="pill", noname="Pharmacy", kind="fun", filters=['["amenity"="pharmacy"]']),
    "gas": dict(label="Gas", icon="fuel", noname="Gas station", kind="fun", filters=['["amenity"="fuel"]']),
    "wc": dict(label="Restrooms", icon="door", noname="Public restroom", kind="fun", filters=['["amenity"="toilets"]']),
}
DEFAULT_CAT = "veg"
MODES = ("walk", "drive")

NO_PLACES = "Couldn’t look up places just now. Try again in a moment."
NOTHING = "Nothing found within {where}. Try the drive range, or another chip."


class AroundError(Exception):
    """A failed search; the text is fit to show a person."""


# ---- the family's food preference ------------------------------------------------------------------------------------------

def vegetarian(session) -> bool:
    """Is the family's "Vegetarian" setting on? False when signed out or there is no family."""
    with familydb.using(session) as db:
        if db is None:
            return False
        r = familydb.row(db, "SELECT value FROM family_prefs WHERE key = 'vegetarian'")
        return bool(r and r["value"] == "1")


def set_vegetarian(session, on: bool) -> bool:
    with ses.family(session) as fam:
        if fam is None:
            return False
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "INSERT OR REPLACE INTO family_prefs (key, value) VALUES ('vegetarian', :v)", v="1" if on else "0")
    return on


# ---- the query ---------------------------------------------------------------------------------------------------------------

def _r(x) -> float:
    return round(float(x), ROUND)


def build_query(cat, lat, lon, radius, vegetarian_pref=True) -> str:
    """The Overpass QL for `cat` within `radius` metres of the (rounded) point. Pure."""
    c = CATEGORIES[cat]
    filters = c.get("filters") or (c["strict"] if vegetarian_pref else c["loose"])
    around = f"(around:{int(radius)},{_r(lat)},{_r(lon)})"
    body = "".join(f"  nwr{f}{around};\n" for f in filters)
    return f"[out:json][timeout:8];\n(\n{body});\nout center tags 80;"


def url_for(query) -> str:
    return OVERPASS.format(q=quote(query, safe=""))


def parse(answer, cat) -> list:
    """Places out of an Overpass answer: [{name, lat, lon, phone, hours, website, tags}], nameless ones given the category's plain name, repeats dropped. Pure."""
    out, seen = [], set()
    for el in (answer or {}).get("elements") or []:
        if not isinstance(el, dict):
            continue
        tags = el.get("tags") or {}
        pos = (el.get("lat"), el.get("lon")) if "lat" in el else ((el.get("center") or {}).get("lat"), (el.get("center") or {}).get("lon"))
        try:
            lat, lon = float(pos[0]), float(pos[1])
        except (TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        name = " ".join(str(tags.get("name") or tags.get("brand") or tags.get("operator") or "").split())[:60] or CATEGORIES[cat]["noname"]
        key = (name.casefold(), round(lat, 4), round(lon, 4))
        if key in seen:
            continue
        seen.add(key)
        phone = " ".join(str(tags.get("phone") or tags.get("contact:phone") or "").split())[:30]
        web = str(tags.get("website") or tags.get("contact:website") or "").strip()
        keep = {k: str(tags[k])[:40] for k in ("cuisine", "diet:vegetarian", "diet:vegan", "brand", "amenity", "shop", "fee", "wheelchair") if tags.get(k)}
        out.append(dict(name=name, lat=lat, lon=lon, phone=phone, hours=str(tags.get("opening_hours") or "")[:200], website=web if web.startswith(("http://", "https://")) else "", tags=keep))
    return out


# ---- the service -----------------------------------------------------------------------------------------------------------

def _key(cat, lat, lon, radius, pref):
    return (cat, _r(lat), _r(lon), int(radius), bool(pref))


def _get(key):
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > _clock():
            return hit[1]
        _cache.pop(key, None)
        return None


def _put(key, places):
    with _lock:
        if len(_cache) >= CACHE_MAX:
            for k in sorted(_cache, key=lambda k: _cache[k][0])[: CACHE_MAX // 4]:
                _cache.pop(k, None)
        _cache[key] = (_clock() + TTL, places)


def clear_cache():
    with _lock:
        _cache.clear()


def places_near(cat, lat, lon, radius, pref=True) -> list:
    """The places for `cat` around the point, from this process's cache or from Overpass. Raises AroundError. A failure is never cached."""
    key = _key(cat, lat, lon, radius, pref)
    got = _get(key)
    if got is not None:
        return got
    query = quote(build_query(cat, lat, lon, radius, pref), safe="")
    budget = geo._clock() + BUDGET   # the gates count in the geocoder's clock
    answer, last = None, None
    for mirror, gate in zip(MIRRORS, GATES):     # F-095: the first mirror that answers wins; one that refuses or is slow hands over to the next
        deadline = min(budget, geo._clock() + TIMEOUT)
        if not gate.wait(deadline):
            continue
        try:
            got = geo._call(mirror.format(q=query), gate, deadline)
        except Exception as e:  # noqa: BLE001 - whatever the service did, the next mirror is asked
            last = e
            continue
        if isinstance(got, dict) and "elements" in got:
            answer = got
            break
    if answer is None:
        raise AroundError(NO_PLACES) from last
    places = parse(answer, cat)
    _put(key, places)
    return places


# ---- distance --------------------------------------------------------------------------------------------------------------

def metres(a_lat, a_lon, b_lat, b_lon) -> float:
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(min(1.0, math.sqrt(h)))


def miles_label(m) -> str:
    mi = m / 1609.344
    return "under 0.1 mi" if mi < 0.1 else f"{mi:.1f} mi"


def minutes_label(m, mode) -> str:
    n = max(1, round(m / (DRIVE_M_PER_MIN if mode == "drive" else WALK_M_PER_MIN)))
    return f"about {n} min {'drive' if mode == 'drive' else 'walk'}"


# ---- opening hours ---------------------------------------------------------------------------------------------------------

_DAYS = ["mo", "tu", "we", "th", "fr", "sa", "su"]
_TIMES = re.compile(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$")


def _day_set(text):
    """Weekday numbers (Mon 0) named by "Mo-Fr", "Sa,Su", "Mo-We,Fr"; None if it is not a plain list of days."""
    days = set()
    for part in text.lower().replace(" ", "").split(","):
        if "-" in part:
            a, _, b = part.partition("-")
            if a not in _DAYS or b not in _DAYS:
                return None
            i, j = _DAYS.index(a), _DAYS.index(b)
            days.update(range(i, j + 1) if i <= j else [*range(i, 7), *range(0, j + 1)])
        elif part in _DAYS:
            days.add(_DAYS.index(part))
        else:
            return None
    return days


def _ranges(text):
    """[(start, end)] minutes for "08:00-12:00,13:00-17:00"; end may be below start (past midnight) or 1440. [] for off/closed. None if not understood."""
    t = text.strip().lower()
    if t in ("off", "closed"):
        return []
    out = []
    for part in t.split(","):
        m = _TIMES.match(part.strip())
        if not m:
            return None
        s, e = int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4])
        if s > 1440 or e > 1440 or int(m[2]) > 59 or int(m[4]) > 59:
            return None
        out.append((s, e))
    return out


def _parse_rules(spec):
    """[(weekdays or None, ranges)] in order, or None when the text has something this small reader does not know. Public-holiday rules are skipped."""
    rules = []
    for raw in spec.split(";"):
        r = raw.strip()
        if not r:
            continue
        low = r.lower()
        if low.startswith("ph") or (" ph" in low and low.endswith("off")):
            continue                        # public holidays: not known here, so the ordinary hours stand
        if low in ("24/7",):
            rules.append((None, [(0, 1440)]))
            continue
        m = re.match(r"^([A-Za-z][A-Za-z,\- ]*?)\s+(\d.*|off|closed)$", r, re.I) or re.match(r"^()(\d.*|off|closed)$", r, re.I)
        if not m:
            return None
        days = _day_set(m[1]) if m[1] else None
        if m[1] and days is None:
            return None
        ranges = _ranges(m[2])
        if ranges is None:
            return None
        rules.append((days, ranges))
    return rules or None


def _intervals(rules, weekday):
    got = []
    for days, ranges in rules:
        if days is None or weekday in days:
            got = ranges
    return got


def open_now(spec, now) -> bool | None:
    """Is a place with OpenStreetMap opening_hours `spec` open at `now` (a datetime in the place's time zone)? None when there are no hours or they use something
    this reader does not know (months, "sunrise", week numbers). Reads "24/7", day lists and ranges, "off", several ranges, hours past midnight; later rules win."""
    spec = (spec or "").strip()
    if not spec:
        return None
    if spec.lower() == "24/7":
        return True
    rules = _parse_rules(spec)
    if rules is None:
        return None
    minute = now.hour * 60 + now.minute
    today, yesterday = now.weekday(), (now.weekday() - 1) % 7
    for s, e in _intervals(rules, today):
        if s <= minute < e or (e <= s and minute >= s):
            return True
    for s, e in _intervals(rules, yesterday):
        if e <= s and e > 0 and minute < e:     # yesterday's late night runs on into today
            return True
    return False


def open_label(state) -> str:
    return "Open now" if state is True else ("Closed now" if state is False else "Hours unknown")


# ---- ranking ---------------------------------------------------------------------------------------------------------------

def by_distance(items) -> list:
    """Closest first, with the ones known to be closed after the rest."""
    return sorted(items, key=lambda p: (p["open"] is False, p["m"]))


SYSTEM = ("You help a family pick a place near them. You get one category, whether the family eats vegetarian, and a numbered list of nearby places with distance in metres, "
          "whether each is open now, and a few tags. Choose the best 5 (fewer if fewer fit) and give each a one-line reason of at most 14 words that uses only what the list says. "
          "Prefer open places, nearer ones, and for food a place that serves what the family eats. Use only ids from the list. Never invent a fact.")
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["picks"],
          "properties": {"picks": {"type": "array", "maxItems": SHOW, "items": {"type": "object", "additionalProperties": False, "required": ["id", "why"],
                                                                              "properties": {"id": {"type": "integer"}, "why": {"type": "string"}}}}}}


def ask_ai(cat, pref, cands, family="") -> list:
    """[(index into cands, why)] chosen by the model, every id checked against the list: unknown and repeated ids are dropped. Raises ai.AIError."""
    shown = [dict(id=i, name=c["name"], metres=int(round(c["m"], -1)), open_now=c["open"], tags=c["tags"]) for i, c in enumerate(cands)]
    user = json.dumps(dict(category=CATEGORIES[cat]["label"], family_eats_vegetarian=bool(pref), places=shown), separators=(",", ":"), ensure_ascii=False)
    answer = ai.call_json("around-you", family, SYSTEM, user, SCHEMA, name="around_you")
    picks, seen = [], set()
    for p in answer.get("picks") or []:
        i = p.get("id") if isinstance(p, dict) else None
        if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(cands) or i in seen:
            continue
        seen.add(i)
        why = " ".join(str(p.get("why") or "").split())[:140]
        picks.append((i, why))
    return picks[:SHOW]


def search(cat, lat, lon, mode, now, *, pref=False, family="", use_ai=True) -> dict:
    """The places for `cat` near (lat, lon) as cards: [{name, m, dist, walk, open, open_label, phone, website, why, lat, lon}], at most SHOW, best first.
    `now` is a datetime in the trip's zone (for "open now"). Raises AroundError. {"items", "ai": True when the model chose and explained, "radius"}."""
    if cat not in CATEGORIES:
        raise AroundError("Pick one of the buttons.")
    mode = mode if mode in RADIUS else "walk"
    radius = RADIUS[mode]
    found = places_near(cat, lat, lon, radius, pref if cat == "veg" else True)
    cands = []
    for p in found:
        m = metres(lat, lon, p["lat"], p["lon"])
        if m > radius * 1.05:
            continue
        cands.append(dict(p, m=m, open=open_now(p["hours"], now)))
    cands = by_distance(cands)[:CANDIDATES]
    if not cands:
        return dict(items=[], ai=False, radius=radius)
    chosen, used = [], False
    if ai.configured("around-you"):
        try:
            picks = ask_ai(cat, pref, cands, family)
        except ai.AIError:
            picks = []
        if picks:
            used = True
            taken = {i for i, _ in picks}
            chosen = [dict(cands[i], why=why) for i, why in picks]
            chosen += [dict(c, why="") for i, c in enumerate(cands) if i not in taken][: SHOW - len(chosen)]
    if not used:
        chosen = [dict(c, why="") for c in cands[:SHOW]]
    for c in chosen:
        c.update(dist=miles_label(c["m"]), walk=minutes_label(c["m"], mode), open_label=open_label(c["open"]))
    return dict(items=chosen, ai=used, radius=radius)


def now_in(zone) -> datetime:
    """Now in the trip's time zone (gitaway.catalog's clock, which tests pin)."""
    from zoneinfo import ZoneInfo
    from gitaway import catalog
    try:
        return catalog.now_utc().astimezone(ZoneInfo(zone))
    except Exception:  # noqa: BLE001 - an unknown zone name: the machine's own clock
        return datetime.now()


def next_half_hour(now) -> int:
    """The next :00 or :30 after `now`, as minutes into the day (capped at 23:30)."""
    m = now.hour * 60 + now.minute
    return min(-(-(m + 1) // 30) * 30, 23 * 60 + 30)

