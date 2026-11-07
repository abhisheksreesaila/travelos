"""The trip cockpit's model (F-201, Direction 3 "Ticket line"): what the page draws, read once and handed over as plain data. The page is
gitaway/pages/cockpit.py; the design is docs/design/cockpit/3-ticket.html and README.md.

    view(session, day="", ua="")   the trip as a line of days (each with its weather and its times), the open day's ticket (on today: Up next with the next
                                   leg turn by turn), the wallet's passes and the paper map's data (the pack's state and each day's stops and drive line)
    turns(line, roads)             the steps of a drive ("Turn left on Lake Tahoe Boulevard (US 50)", 3.8 mi), worked out from its line (gitaway.geo's cached
                                   route) and the geo pack's named roads: the router gives no steps (F-204 may), so the line is matched to the roads it runs along
    mask(ref)                      "••821": a reference number is never drawn whole here
    partner_of(...)                F-198's hook: "Booked on <partner>" and its Change or cancel page for one booking (today the trip's own "booked on", no page)

Pure functions take data; `view` is the one that reads the family (gitaway.tripcal, gitaway.geo's cache only, gitaway.geopack's stored pack).
"""

import json
import math
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from gitaway import catalog, dayweather, familydb, geo, geopack, session as ses, tripcal as cal, tripday as td, tripgeo, tripimport

KIND_OF_ICON = {"plane": "flight", "bed": "stay", "car": "car"}        # a booking's kind from its icon
ICON_OF_KIND = {"flight": "plane", "stay": "bed", "car": "car", "fun": "spark", "food": "food", "outdoors": "tree", "culture": "sight", "travel": "car"}
NEAR_M = 70             # a point of a drive this close to a named road is on it
MIN_STEP_KM = 0.45      # a stretch shorter than this between two others is a junction, not a step
MAX_STEPS = 4           # on the ticket
HEAD_PTS = 8            # resampled points (40 m apart) a heading is measured over
ROUTE_POINTS = 260      # a day's drive line on the page, at most (the paper map is 1000 units across)


# ---- small pure helpers ------------------------------------------------------------------------------------------------

def mask(ref) -> str:
    """'••821' for 'KQ7821'; '' for nothing. A reference is never drawn whole on the cockpit (the booking's own sheet shows it behind a tap)."""
    if str(ref or "").strip().lower() in ("", "none given"):
        return ""
    ref = "".join(str(ref).split())
    return "••" + ref[-3:] if len(ref) > 3 else "•••"


def clock(m) -> str:
    """'9:35', '1:30 PM' style without the AM: the ticket's big numbers ('9:35', '10:00') read in the trip's own day."""
    h, mm = divmod(int(m), 60)
    return f"{h % 12 or 12}:{mm:02d}"


def short_time(m) -> str:
    """'8:45 AM', '1:30 PM' (the stubs' times)."""
    return cal.fmt_time(int(m))


def _xy(lon, lat, lat0):
    """Metres east and north of (0, lat0): a flat projection, exact enough inside one trip's region."""
    return lon * 111_320 * math.cos(math.radians(lat0)), lat * 110_574


def distance_km(line) -> float:
    """Length of a [(lon, lat)] line in kilometres."""
    return sum(geopack.km_between((a[1], a[0]), (b[1], b[0])) for a, b in zip(line, line[1:]))


def miles(km) -> float:
    return round(km / 1.609344, 1)


def _bearing(a, b, lat0):
    (x1, y1), (x2, y2) = _xy(a[0], a[1], lat0), _xy(b[0], b[1], lat0)
    return math.degrees(math.atan2(x2 - x1, y2 - y1)) % 360


COMPASS = ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest")


@dataclass(frozen=True)
class Step:
    verb: str           # "Head north on", "Turn left on", "Continue on", "Bear right onto", "Head north"
    road: str           # "Lake Tahoe Boulevard (US 50)", or "" for a road the pack has no name for
    mi: float
    icon: str           # "up", "turn-left", "turn-right", "bear-left", "bear-right"


def road_label(ref, name) -> str:
    return f"{name} ({ref})" if ref and name else ref or name


def _resample(line, lat0, every=40.0):
    """Points every `every` metres along the line (the ends kept), as (lon, lat)."""
    out = [tuple(line[0])]
    left = every
    for a, b in zip(line, line[1:]):
        (x1, y1), (x2, y2) = _xy(a[0], a[1], lat0), _xy(b[0], b[1], lat0)
        seg = math.hypot(x2 - x1, y2 - y1)
        pos = 0.0
        while seg - pos >= left:
            pos += left
            t = pos / seg
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            left = every
        left -= seg - pos
    if out[-1] != tuple(line[-1]):
        out.append(tuple(line[-1]))
    return out


def _segments(roads, bbox, lat0):
    """(x1, y1, x2, y2, label) arrays of every road segment near a box, in metres."""
    w, s, e, n = bbox
    rows, labels = [], []
    for r in roads or []:
        label = road_label(r.get("ref", ""), r.get("name", ""))
        pts = r.get("pts") or []
        for a, b in zip(pts, pts[1:]):
            if max(a[0], b[0]) < w or min(a[0], b[0]) > e or max(a[1], b[1]) < s or min(a[1], b[1]) > n:
                continue
            rows.append((*_xy(a[0], a[1], lat0), *_xy(b[0], b[1], lat0)))
            labels.append(label)
    return rows, labels


def turns(line, roads, max_steps=MAX_STEPS) -> list:
    """The steps of a drive along `line` [(lon, lat), ...]: each stretch of it that runs along one named road of `roads` (the geo pack's
    [{"ref", "name", "pts"}]) is a step, its verb from the angle between the stretch before and this one; a stretch on no named road is
    "Head <compass>" at the start and joins the step before anywhere else. The longest steps are kept, in order, at most `max_steps`."""
    import numpy as np
    if not line or len(line) < 2:
        return []
    lat0 = sum(p[1] for p in line) / len(line)
    pts = _resample(line, lat0)
    pad = NEAR_M / 100_000 * 2
    bbox = (min(p[0] for p in pts) - pad, min(p[1] for p in pts) - pad, max(p[0] for p in pts) + pad, max(p[1] for p in pts) + pad)
    rows, labels = _segments(roads, bbox, lat0)
    names = []
    if rows:
        seg = np.asarray(rows, dtype=float)
        x1, y1, x2, y2 = seg[:, 0], seg[:, 1], seg[:, 2], seg[:, 3]
        dx, dy = x2 - x1, y2 - y1
        ll = np.maximum(dx * dx + dy * dy, 1e-9)
        for p in pts:
            px, py = _xy(p[0], p[1], lat0)
            t = np.clip(((px - x1) * dx + (py - y1) * dy) / ll, 0, 1)
            d = np.hypot(x1 + t * dx - px, y1 + t * dy - py)
            k = int(np.argmin(d))
            names.append(labels[k] if d[k] <= NEAR_M else "")
    else:
        names = [""] * len(pts)
    # runs of one label, with their length
    runs = []
    for i in range(1, len(pts)):
        km = geopack.km_between((pts[i - 1][1], pts[i - 1][0]), (pts[i][1], pts[i][0]))
        label = names[i]
        if runs and runs[-1]["road"] == label:
            runs[-1]["km"] += km
            runs[-1]["end"] = i
        else:
            runs.append({"road": label, "km": km, "start": i - 1, "end": i})
    # a short stretch between two others is a junction: it joins the longer neighbour
    changed = True
    while changed and len(runs) > 1:
        changed = False
        for j, r in enumerate(runs):
            if r["km"] < MIN_STEP_KM and 0 < j < len(runs) - 1:
                into = j - 1 if runs[j - 1]["km"] >= runs[j + 1]["km"] else j + 1
                runs[into]["km"] += r["km"]
                runs[into]["start"], runs[into]["end"] = min(runs[into]["start"], r["start"]), max(runs[into]["end"], r["end"])
                del runs[j]
                changed = True
                break
        merged = []
        for r in runs:   # neighbours with the same road, after a junction left
            if merged and merged[-1]["road"] == r["road"]:
                merged[-1]["km"] += r["km"]
                merged[-1]["end"] = r["end"]
            else:
                merged.append(r)
        runs = merged
    # an unnamed stretch after the first joins the step before it (we cannot name it, so we do not tell it as a turn); a short unnamed end is the arrival
    kept = []
    for j, r in enumerate(runs):
        if j and not r["road"] and kept:
            kept[-1]["km"] += r["km"]
            kept[-1]["end"] = r["end"]
        else:
            kept.append(r)
    steps = []
    for j, r in enumerate(kept):      # headings over about 300 m each side of a junction: a simplified line cuts its corners
        a, b = pts[r["start"]], pts[min(r["start"] + HEAD_PTS, r["end"])]
        if j == 0:
            heading = COMPASS[int(((_bearing(a, b, lat0) + 22.5) % 360) // 45)]
            steps.append(Step(f"Head {heading}" + (" on" if r["road"] else ""), r["road"], miles(r["km"]), "up"))
            continue
        prev = kept[j - 1]
        p1, p2 = pts[max(prev["end"] - HEAD_PTS, prev["start"])], pts[prev["end"]]
        turn = (_bearing(a, b, lat0) - _bearing(p1, p2, lat0) + 540) % 360 - 180
        side = "right" if turn > 0 else "left"
        if abs(turn) < 25:
            verb, ico = "Continue on", "up"
        elif abs(turn) < 60:
            verb, ico = f"Bear {side} onto", f"bear-{side}"
        else:
            verb, ico = f"Turn {side} on", f"turn-{side}"
        steps.append(Step(verb, r["road"], miles(r["km"]), ico))
    if len(steps) > max_steps:
        keep = sorted(sorted(range(1, len(steps)), key=lambda k: -steps[k].mi)[:max_steps - 1])
        steps = [steps[0]] + [steps[k] for k in keep]
    return steps


# ---- what the page draws -----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Line:
    start: int
    time: str           # "8:45 AM"
    title: str
    kind: str           # flight | stay | car | fun | food | outdoors | culture | travel: the colour of its kind
    icon: str
    booked: bool = False
    on: str = ""        # a booking's company ("United", "Hertz"); "" for a plan
    short: str = ""     # what a narrow stub says: "Fly SFO → RNO", "Pick up car", "Check in"; a plan's own title


@dataclass(frozen=True)
class Day:
    i: int
    dow: str            # "Sat"
    num: int            # 19
    date: str           # "Dec 19"
    name: str           # "Fly in · check in", "Snowshoe at Taylor Creek", "Wide open"
    lines: tuple
    wx: dayweather.DayWx
    state: str          # done | today | later
    booked: tuple = ()  # the companies its bookings are with, for the stub's foot
    href: str = ""      # the day view (plans, chat, Ask)


@dataclass(frozen=True)
class Next:
    """Today's ticket: what is next, when to leave and how to drive there."""
    kicker: str         # "Today · up next · leave in 23 min"
    title: str
    starts: str = ""    # "10:00"
    leave: str = ""     # "9:35"
    drive: int = 0      # minutes, 0 when unknown
    mi: float = 0.0
    steps: tuple = ()
    directions: str = ""
    sub: str = ""       # "Tomorrow starts with Ski school at 8:45 AM." on a day that is done
    item_id: str = ""


@dataclass(frozen=True)
class Pass:
    kind: str           # flight | stay | car
    eyebrow: str        # "Flight home · Sat 26"
    title: str          # "RNO → SFO · 1:30 PM"
    sub: str            # "United UA 5522 · 4 seats"
    ref: str = ""       # "••821"
    href: str = ""      # the booking's own sheet over its day (address, phone, the full number behind a tap)
    partner: str = ""   # "Booked on <partner>" (F-198 fills it per booking; today the trip's own "booked on")
    manage: str = ""    # the partner's Change or cancel page (F-198); "" until then


def partner_of(b, kind, spec=None) -> tuple:
    """F-198's hook: (partner name, its Change or cancel page) for one booking. Until F-198 stores the partner per booking it is the trip's own
    "booked on" (an imported trip's template says where it was booked) and no page: the cockpit then shows "Booked on <partner>" with Details."""
    if cal.is_imported(b):
        plan = cal.plan_of(b)
        return (plan.booked_on or "", "")
    return ("", "")


def _when(d, today) -> str:
    return d.strftime("%a ") + str(d.day)


def passes(b, t, today, now_min, curl) -> list:
    """The wallet: the next flight (else the last), the stay and the car, each with its reference masked. `curl(day=, booked=)` is the booking sheet's address."""
    out = []
    dates = cal.days(t)
    if cal.is_imported(b):
        plan = cal.plan_of(b)
        specs = {s.id: s for s in tripimport.block_specs(plan)}
        legs = [s for s in specs.values() if s.kind == "leg"]
        if legs:
            later = [s for s in legs if (s.item.depart.date(), s.item.depart.hour * 60 + s.item.depart.minute) >= (today, now_min)]
            s = later[0] if later else legs[-1]
            x = s.item
            home = s.id == "b-back" or x.dest == plan.legs[0].origin
            seats = len([p for p in (x.seats or "").split(",") if p.strip()])
            name, page = partner_of(b, "flight", s)
            out.append(Pass("flight", f"Flight {'home' if home else 'in' if s.id == 'b-out' else ''} · {_when(x.depart.date(), today)}".replace("Flight  ·", "Flight ·"),
                            f"{x.origin} → {x.dest} · {cal.fmt_time(x.depart.hour * 60 + x.depart.minute)}",
                            " · ".join(p for p in (x.name, f"{seats} seats" if seats else "") if p), mask(x.confirmation),
                            curl(day=(x.depart.date() - t.depart).days, booked=s.id), name, page))
        stays = [s for s in specs.values() if s.kind == "checkin"]
        if stays:
            s = next((s for s in stays if s.item.check_out.date() > today), stays[-1])
            h = s.item
            left = (h.check_out.date() - max(today, h.check_in.date())).days
            name, page = partner_of(b, "stay", s)
            eyebrow = f"Stay · {left} night{'s' if left != 1 else ''} left" if h.check_in.date() <= today < h.check_out.date() else f"Stay · {(h.check_out.date() - h.check_in.date()).days} nights"
            out.append(Pass("stay", eyebrow, h.name, f"Check out {_when(h.check_out.date(), today)} · {cal.fmt_time(h.check_out.hour * 60 + h.check_out.minute)}",
                            mask(h.confirmation), curl(day=max(0, (h.check_in.date() - t.depart).days), booked=s.id), name, page))
        car = specs.get("b-car-pick")
        if car:
            r = car.item
            name, page = partner_of(b, "car", car)
            back = r.dropoff
            out.append(Pass("car", "Car" + (f" · {r.pickup_place} to {r.dropoff_place}" if r.pickup_place != r.dropoff_place else ""), r.car or f"{r.company} car",
                            f"{r.company} · return {_when(back.date(), today)} {cal.fmt_time(back.hour * 60 + back.minute)}", mask(r.confirmation),
                            curl(day=max(0, (r.pickup.date() - t.depart).days), booked="b-car-pick"), name, page))
        return out
    flight, stay, car = cal.flight_of(b), cal.stay_of(b), cal.car_of(b)
    last = len(dates) - 1
    if flight:
        back = (dates[last], flight.back_depart_min) >= (today, now_min) and (dates[0], flight.depart_min) < (today, now_min)
        out.append(Pass("flight", f"Flight {'home' if back else 'in'} · {_when(dates[last] if back else dates[0], today)}",
                        f"{flight.airport} → {t.origin} · {cal.fmt_time(flight.back_depart_min)}" if back else f"{t.origin} → {flight.airport} · {cal.fmt_time(flight.depart_min)}",
                        flight.name, "", curl(day=last if back else 0, booked="b-back" if back else "b-out")))
    if stay:
        out.append(Pass("stay", f"Stay · {last} night{'s' if last != 1 else ''}", stay.name, f"Check out {_when(dates[last], today)} · {cal.fmt_time(cal.CHECK_OUT)}", "", curl(day=0, booked="b-in")))
    if car:
        out.append(Pass("car", "Car", car.name, f"Return {_when(dates[last], today)}", "", curl(day=0, booked="b-car-pick") if any(x.id == "b-car-pick" for x in cal.booked_blocks(b, t)) else ""))
    return out


def _company(blk) -> str:
    """The company on a booking line's stub: the airline of a flight ("United"), the rental company of a car, "Stay" for a hotel."""
    if blk.icon == "plane":
        name = blk.title.split(" · ")[0]
        return name.rsplit(" ", 2)[0] if len(name.split()) > 2 and any(c.isdigit() for c in name.split()[-1]) else name.split(" ")[0]
    if blk.icon == "car":
        words = blk.title.split(" · ")[0].replace("Pick up ", "").replace("Drop off ", "").replace(" car", "")
        return words.strip()
    return "Stay"


def short_booking(blk) -> str:
    """A booking line in a few words, for a narrow stub: 'Fly SFO → RNO', 'Pick up car', 'Return car', 'Check in', 'Check out'."""
    if blk.icon == "plane":
        leg = td._LEG.search(blk.title)
        return f"Fly {leg.group(1)} → {leg.group(2)}" if leg else blk.title.split(" · ")[0]
    if blk.icon == "car":
        return "Return car" if blk.title.startswith("Drop off") else "Pick up car"
    if blk.icon == "bed":
        return "Check out" if blk.title.startswith("Check out") else "Check in"
    return blk.title


def lines_of(day, blocks, acts) -> list:
    """A day's bookings and plans as Lines in time order (rides left out)."""
    out = [Line(x.at, short_time(x.at), x.title, KIND_OF_ICON.get(x.icon, "travel"), x.icon or "pin", True, _company(x), short_booking(x)) for x in blocks if x.day == day and x.kind != "ride"]
    out += [Line(a.start, short_time(a.start), a.title, a.kind if a.kind in cal.KINDS else "fun", ICON_OF_KIND.get(a.kind, "spark"), short=a.title) for a in acts if a.day == day]
    return sorted(out, key=lambda x: (x.start, not x.booked, x.title))


def _now_kicker(up, left, now_min, item) -> str:
    if up.kicker.startswith("HAPPENING NOW"):
        return f"Today · happening now · ends {td.until(item.end - now_min)}"
    if left is not None:
        return "Today · up next · time to leave" if left <= 0 else f"Today · up next · leave {td.until(left)}"
    return f"Today · up next · {td.until(item.start - now_min)}"


def next_leg(session, tv, item, pack_roads, ua=""):
    """(drive minutes, miles, steps, leave minute or None, minutes left or None) for driving to today's up-next `item` (from where the day puts you), read
    from gitaway.geo's cache only. Unknown parts are 0, () or None."""
    from gitaway.pages import trip as trippage
    got = trippage.leave_info(tv, item)
    at, drive, left = (got[0], got[1], got[2]) if got else (None, 0, None)
    origin = (trippage.leave_from(tv, item) or ("", 0))[0]
    mi, steps = 0.0, ()
    with familydb.using(session) as db:
        a = geo.coords(geo.as_place(origin), db, lookup=False) if origin else None
        b = geo.coords(geo.as_place(item.place), db, lookup=False) if item.place else None
        line = geo.route([(a[0], a[1]), (b[0], b[1])], db, lookup=False) if a and b else None
    if line:
        coords = line["coordinates"]
        mi = miles(distance_km(coords))
        steps = tuple(turns(coords, pack_roads))
    return drive or 0, mi, steps, at, left


def today_ticket(session, today, ua, pack_roads) -> Next | None:
    """Up next on today (drawn by the trip page's own model, gitaway.pages.trip.load), with the next leg; None when the day is not today."""
    from gitaway.pages import trip as trippage
    with geo.cache_scope(session):
        tv = trippage.load(session, str(today), ua)
        up = tv["up"]
        if up is None:
            return None
        item = up.item
        if item is None:
            return Next("Today · all done", "You are all caught up", sub=up.detail)
        drive, mi, steps, at, left = next_leg(session, tv, item, pack_roads, ua) if up.kicker.startswith("UP NEXT") else (0, 0.0, (), None, None)
        now_min = tv["clocks"][item.zone][1] if item.zone in tv["clocks"] else tv["now"]
        return Next(_now_kicker(up, left, now_min, item), item.title, clock(item.start), clock(at) if at is not None else "", drive, mi, steps,
                    td.maps_url(item.place, ua) if item.place else "", item_id=item.id)


def map_days(session, days_stops, kinds, box=None) -> list:
    """For each day: its stops with a known place inside `box` ({"lat", "lon", "label", "time", "kind", "icon"}; a flight's place is the airport it leaves,
    so the home airport falls outside) and its drive line (the known legs between them, joined, at most ROUTE_POINTS points) with the minutes they take.
    Read from gitaway.geo's cache only."""
    out = []
    with familydb.using(session) as db:
        for stops in days_stops:
            pts, legs, minutes = [], [], 0
            for x in stops:
                got = geo.state(x.place, db)[0]
                if not isinstance(got, tuple) or (box and not geopack.covers(box, [got], margin_km=0)):
                    continue
                kind = KIND_OF_ICON.get(x.icon) or kinds.get(x.act, "fun") if x.title else "stay"
                label = "Stay" if x.at < 0 else _label(x)
                pts.append({"lat": round(got[0], 5), "lon": round(got[1], 5), "label": label, "time": short_time(x.at) if x.at >= 0 else "", "kind": kind,
                            "icon": x.icon or ICON_OF_KIND.get(kind, "pin"), "flight": x.flight, "stay": x.at < 0 or x.icon == "bed"})
            for a, b in zip(pts, pts[1:]):
                if a["flight"] or (a["lat"], a["lon"]) == (b["lat"], b["lon"]):
                    continue
                leg = geo._leg((a["lat"], a["lon"]), (b["lat"], b["lon"]), db, fetch_it=False)
                if leg:
                    legs.append(leg["g"]["coordinates"])
                    minutes += leg["m"]
            line = [p for leg in legs for p in leg]
            if len(line) > ROUTE_POINTS:
                tol = 0.00005
                while len(line) > ROUTE_POINTS and tol < 0.01:
                    line = [list(p) for p in geopack.simplify([tuple(p) for leg in legs for p in leg], tol)]
                    tol *= 1.6
            out.append({"stops": [{k: v for k, v in p.items() if k != "flight"} for p in _unique(pts)], "route": [[round(x, 5), round(y, 5)] for x, y in line] or None,
                        "min": minutes})
    return out


def _unique(pts):
    seen, out = {}, []
    for p in pts:
        key = (p["lat"], p["lon"])
        if key in seen:
            first = seen[key]
            if p["time"] and p["label"] != first["label"]:
                first["time"] = first["time"] or p["time"]
            continue
        seen[key] = p
        out.append(p)
    return out


def _label(stop) -> str:
    """A stop's label on the map: a plan's title, an airport's code, the stay's or the car desk's short name."""
    if stop.icon == "plane":
        return stop.place
    if stop.icon == "bed":
        return "Stay"
    if stop.icon == "car":
        return ("Drop off car" if stop.title.startswith("Drop off") else "Pick up car") + (f" · {stop.place}" if stop.place.endswith(" airport") else "")
    return stop.title


@dataclass
class View:
    title: str
    eyebrow: str
    dates: str
    party: str
    days: list
    open_day: int
    today: int | None
    phase: str
    ticket: Next | None
    passes: list
    map: dict = field(default_factory=dict)
    head_day: str = ""          # the phone's big heading: "Monday"
    head_sub: str = ""          # "Dec 21 · 9:12 AM"
    phone_eyebrow: str = ""     # the phone's line above it: "Tahoe at Christmas · day 3 of 8"


def party_text(t) -> str:
    """'2 adults · kids 8 and 11'."""
    adults = f"{t.adults} adult{'s' if t.adults != 1 else ''}"
    kids = sorted(t.kid_ages)
    if not kids:
        return adults
    ages = ", ".join(str(a) for a in kids[:-1]) + (" and " if len(kids) > 1 else "") + str(kids[-1])
    return f"{adults} · {'kid' if len(kids) == 1 else 'kids'} {ages}"


def view(session, day="", ua="", curl=None, pack_state="building") -> View:
    """Everything the cockpit draws for the open trip. `day` (a number) opens that day's ticket; else today during the trip, the first day before it, the last
    after. `curl(day=, booked=)` gives the booking sheet's address (the canvas's own). `pack_state` is what geopack.ensure said ("building", "waiting") when
    there is no pack yet."""
    b = ses.booking(session)
    t = cal.trip("", b)
    dates = cal.days(t)
    blocks = [x for x in cal.booked_blocks(b, t) if x.kind != "ride"]
    acts = cal.activities(session)
    zone = ses.trip_zone(session)
    here = td.clock_zone(cal.plan_of(b) if cal.is_imported(b) else None, zone)
    now = catalog.now_utc().astimezone(ZoneInfo(here))
    today = catalog.today_in(here)
    now_min = td.now_minute(here)
    ph, n = td.phase(t, today)
    today_idx = n if ph == "during" else None
    last = len(dates) - 1
    open_day = int(day) if str(day).isdigit() and int(day) <= last else (n if ph == "during" else 0 if ph == "before" else last)
    summaries = td.day_summaries(dates, blocks, acts, today_idx)
    weather = dayweather.days(t)
    canvas_url = curl or (lambda **q: "")
    out_days = []
    for i, d in enumerate(dates):
        lines = lines_of(i, blocks, acts)
        booked = tuple(dict.fromkeys(x.on for x in lines if x.booked and x.on))
        out_days.append(Day(i, d.strftime("%a"), d.day, f"{d.strftime('%b')} {d.day}", summaries[i].head, tuple(lines), weather[i], summaries[i].state, booked,
                            canvas_url(day=i)))
    row = geopack.stored(session)
    pack_roads = geopack.roads_lonlat(json.loads(row["shapes"])) if row else []
    ticket = today_ticket(session, today_idx, ua, pack_roads) if today_idx is not None else None
    kinds = {a.id: (a.kind if a.kind in cal.KINDS else "fun") for a in acts}
    stops = tripgeo.day_stops(session)
    pts, anchor = geopack.trip_points(session)
    box = geopack.parse_box(row["box"]) if row else geopack.region(pts, anchor)
    state = "ready" if row else ("none" if box is None else pack_state if pack_state in ("building", "waiting") else "building")
    mapdata = {"state": state, "box": list(box) if box else None, "km": [round(v, 2) for v in geopack.box_km(box)] if box else None,
               "pack": {"key": row["key"], "shapes": f"/trip/cockpit/pack/{row['key']}.json", "light": f"/trip/cockpit/pack/{row['key']}-light.webp",
                        "dark": f"/trip/cockpit/pack/{row['key']}-dark.webp"} if row else None,
               "days": map_days(session, stops, kinds, box) if stops else [{"stops": [], "route": None, "min": 0} for _ in dates], "open": open_day}
    who = ses.current_traveler(session)
    family = (who.name.split()[0] + "’s family") if who and who.name else "Your family"
    if ph == "during":
        eyebrow = f"{family} · day {n + 1} of {len(dates)} · {now.strftime('%a %b')} {now.day}, {cal.fmt_time(now_min)}"
    elif ph == "before":
        eyebrow = f"{family} · {td.starts_in(n).lower().replace('trip starts', 'starts')}"
    else:
        eyebrow = f"{family} · back home"
    od = dates[open_day]
    when = f"day {open_day + 1} of {len(dates)}" if ph == "during" or open_day else td.starts_in(n).lower().replace("trip starts", "starts") if ph == "before" else "back home"
    return View(t.title, eyebrow, f"{_long(dates[0])} – {_long(dates[-1])}",
                party_text(t), out_days, open_day, today_idx, ph, ticket, passes(b, t, today, now_min, canvas_url), mapdata,
                od.strftime("%A"), f"{od.strftime('%b')} {od.day}" + (f" · {cal.fmt_time(now_min)}" if open_day == today_idx else ""), f"{t.title} · {when}")


def _long(d) -> str:
    return f"{d.strftime('%a %b')} {d.day}"
