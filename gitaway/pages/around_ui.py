"""Around you (F-073), the Map tab's second segment: GET /trip/map?view=around[&cat=veg][&day=N], and POST /trip/map/around for the cards.

The page (frame 5 of docs/design/canvas/Mobile-Storyboards-v1.html) has the seven chips, the walk/drive range and the family's food preference. Nothing is searched
until a person taps: a chip, or "Use my location". assets/js/around.js then asks the phone where it is (navigator.geolocation, only while this page is open),
posts that with the chip to /trip/map/around and puts the cards it gets back into the page. The place a person is standing is in that one request and
nowhere else: it is not stored, not put in a link and not logged. If the phone says no, the cards are for the day's hotel (else its first stop on the map), and the
page says so.

Every card: the name, distance and walk time, open now or hours unknown (no rating, OpenStreetMap has none), Directions, Call when there is a phone, and
Add to plan, which opens the calendar's add form for the day with the name and the next free half hour filled in (an editor only; the calendar validates it, writes
the change card and tells the family like any other add). The model is gitaway/around.py. POST /trip/map/around writes only the place-lookup cache (in memory), so every member may call it (limited per person)
(gitaway.access OPEN_POSTS).
"""

import re
import threading
import time
from urllib.parse import quote

from fasthtml.common import A, Button, Div, Form, H2, H3, Input, Link, P, Span
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse

from gitaway import access, around, familydb, session as ses, tripcal as cal, tripday as td
from gitaway.icons import icon
from gitaway.layout import trip_field

HEAD = (Link(rel="stylesheet", href="/assets/css/around.css"),)
SCRIPTS = ("/assets/js/around.js",)
MODE_WORDS = {"walk": "Walking", "drive": "Driving"}
RANGE_WORDS = {"walk": "about a mile on foot", "drive": "about 5 miles by car"}
GAP, PER_MINUTE = 2.0, 10      # one search per person every 2 seconds and ten a minute, counted in this process's memory
SLOW_DOWN = "One moment, you are searching a little fast. Try again in a few seconds."
LIMITS: dict = {}
_limit_lock = threading.Lock()
_now = time.monotonic
LOCATING = "Asking your phone where you are…"


def too_fast(user) -> bool:
    """True when `user` (an id) has searched too fast: under GAP seconds since the last, or PER_MINUTE in the last minute. Counts a search that is allowed."""
    t = _now()
    with _limit_lock:
        stamps = [x for x in LIMITS.get(user, []) if t - x < 60]
        if (stamps and t - stamps[-1] < GAP) or len(stamps) >= PER_MINUTE:
            LIMITS[user] = stamps
            return True
        LIMITS[user] = [*stamps, t]
        if len(LIMITS) > 5000:
            for k in [k for k, v in LIMITS.items() if not v or t - v[-1] >= 60]:
                LIMITS.pop(k, None)
        return False


def around_url(day=None, cat=None) -> str:
    q = [f"{k}={v}" for k, v in (("view", "around"), ("day", day), ("cat", cat)) if v not in (None, "")]
    return "/trip/map?" + "&".join(q)


def stops_url(day=None) -> str:
    return "/trip/map" + (f"?day={day}" if day not in (None, "") else "")


def segment(view, day):
    on = lambda v: "true" if view == v else None  # noqa: E731
    return Div(A("Today’s stops", href=stops_url(day), cls="mp-seg", id="mp-seg-stops", aria_current=on("stops")),
               A("Around you", href=around_url(day), cls="mp-seg", id="mp-seg-around", aria_current=on("around")),
               cls="mp-segs", role="group", aria_label="Map view")


# ---- the page ----------------------------------------------------------------------------------------------------------------

def _chip(key, c, picked):
    return Button(icon(c["icon"], 18, 2.4), c["label"], type="button", cls="ar-chip", data_cat=key, aria_pressed="true" if key == picked else "false", id=f"ar-chip-{key}")


def _prefs(pref, admin_or_editor):
    if pref:
        pill = Span(Span(icon("check", 14, 3), cls="ar-bx"), "Vegetarian", cls="ar-pref is-on", id="ar-pref")
        return Div(Span("From your family profile:", cls="ar-pt"), pill, Span("only places that serve real vegetarian dishes", cls="ar-pt"), cls="ar-prefs")
    more = A("Turn it on in Family settings", href="/family#fam-food", id="ar-pref-link") if admin_or_editor else Span("An editor can turn it on in Family settings.", cls="ar-pt")
    return Div(Span("Family food preference: none.", cls="ar-pt", id="ar-pref"), more, cls="ar-prefs")


def view(request, session, v):
    """The Around you body for the open day `v` (trip.load). Reads the family's food preference; searches nothing."""
    pref = around.vegetarian(session)
    q = request.query_params.get("cat", "")
    picked = q if q in around.CATEGORIES else (around.DEFAULT_CAT if pref else "")
    day = v["sel"]
    editor = access.can_edit(v["role"])
    return Div(
        segment("around", day),
        Div(Span("Around you", cls="ar-ttl"), Span(icon("pin", 16, 2.4), "Tap a button to look nearby", cls="ar-loc", id="ar-loc", role="status", aria_live="polite"), cls="ar-head"),
        Div(*[_chip(k, c, picked) for k, c in around.CATEGORIES.items()], cls="ar-chips", role="group", aria_label="What are you looking for", id="ar-chips"),
        Div(Button(icon("target", 18, 2.4), "Use my location", type="button", cls="tp-btn tp-btn-white ar-locate", id="ar-locate"),
            Div(*[Button(w, type="button", cls="ar-mode", data_mode=m, aria_pressed="true" if m == "walk" else "false", id=f"ar-mode-{m}") for m, w in MODE_WORDS.items()], cls="ar-modes", role="group", aria_label="How far"), cls="ar-row"),
        P(icon("lock", 14, 2.4), "GitAway asks your phone where you are only when you tap, only while this page is open, and does not keep it. "
          "Places come from OpenStreetMap, which gets your position rounded to within about 100 metres. Results for that rounded point are kept in the server's memory for up to 30 minutes, not linked to you.", cls="ar-fine", id="ar-privacy"),
        _prefs(pref, editor),
        Div(id="ar-results", cls="ar-results", role="region", aria_live="polite", aria_label="Places near you", aria_busy="false"),
        Form(trip_field(), Input(type="hidden", name="day", value=str(day)), id="ar-ctx", cls="ar-ctx", data_url="/trip/map/around", hidden=True),
        cls="ar", id="ar", data_picked=picked)


def _pick_fallback(stops):
    """(title, (lat, lon), is_hotel) of the hotel stop, else the first stop; stops are tab_map.stops_of rows that have a position."""
    for s in stops:
        if s["kind"] == "hotel":
            return s["title"].removeprefix("Check in · ").removeprefix("Check out · "), s["pos"], True
    s = stops[0]
    return s["title"], s["pos"], False


# ---- the cards ---------------------------------------------------------------------------------------------------------------

def directions_url(name, lat, lon, ua="") -> str:
    """Apple Maps on Apple devices, Google Maps elsewhere, for this place: its name and where it is (a place's position, never the person's)."""
    q = quote(f"{name} {lat:.5f},{lon:.5f}")
    return f"https://maps.apple.com/?q={quote(name)}&ll={lat:.5f},{lon:.5f}" if td._APPLE.search(ua or "") else f"https://www.google.com/maps/search/?api=1&query={q}"


def tel_url(phone) -> str:
    digits = re.sub(r"[^\d+]", "", phone or "")
    return f"tel:{digits}" if len(re.sub(r"\D", "", digits)) >= 7 else ""


def free_slot(v, kind, now) -> int:
    """The next half hour with an hour free on the open day, as minutes: from now when it is today, else from noon for food and 10 AM for the rest."""
    day, blocks, acts = v["sel"], v["blocks"], v["acts"]
    lo, hi = cal.day_window(blocks, day)
    start = around.next_half_hour(now) if day == v["today_idx"] else (12 * 60 if kind == "food" else 10 * 60)
    t = -(-max(start, lo) // 30) * 30
    first = t
    while t + 60 <= hi:
        busy = any(b.day == day and t < b.end and b.start < t + 60 for b in blocks) or any(a.day == day and t < a.end and a.start < t + 60 for a in acts)
        if not busy:
            return t
        t += 30
    return min(first, cal.GRID_END - cal.MIN_LEN)


def add_url(v, name, kind, at) -> str:
    from gitaway.pages import calendar as calui
    return calui.cal_url("", view="days", add=v["sel"], at=cal.hhmm(at), title=name[: cal.MAX_TITLE], kind=kind, trip=ses.open_trip_id())


def card(v, c, kind, at, editor):
    acts = [A(icon("nav", 18, 2.4), "Directions", href=directions_url(c["name"], c["lat"], c["lon"], v["ua"]), target="_blank", rel="noopener", cls="tp-btn tp-btn-coral ar-dir")]
    tel = tel_url(c["phone"])
    if tel:
        acts.append(A(icon("phone", 18, 2.4), "Call", href=tel, cls="tp-btn tp-btn-white ar-call", aria_label=f"Call {c['name']}"))
    if editor:
        acts.append(A(icon("plus", 18, 2.6), "Add to plan", href=add_url(v, c["name"], kind, at), cls="tp-btn tp-btn-white ar-add", aria_label=f"Add {c['name']} to the plan at {cal.fmt_time(at)}"))
    state = {True: "is-open", False: "is-closed"}.get(c["open"], "is-unknown")
    meta = Div(Span(c["dist"], cls="ar-pill ar-dist"), Span(c["walk"], cls="ar-pill ar-walk"), Span(c["open_label"], cls=f"ar-pill ar-open {state}"), cls="ar-meta")
    site = A(icon("ext", 14, 2.4), "Website", href=c["website"], target="_blank", rel="noopener", cls="ar-site") if c["website"] else ""
    return Div(H3(c["name"], cls="ar-name"), meta, P(icon("spark", 14, 2.4), c["why"], cls="ar-why") if c["why"] else "", site, Div(*acts, cls="ar-acts"), cls="ar-card", data_place=c["name"])


def _fragment(*body):
    return Div(*body, id="ar-fragment")


def fragment(v, cat, mode, found, near_text, editor, now, note=""):
    """The cards (or why there are none) for one search, as the HTML the page swaps into #ar-results."""
    c = around.CATEGORIES[cat]
    items = found["items"]
    head = Div(H2(c["label"], cls="ar-h2"), Span(near_text, cls="ar-near", id="ar-near"), cls="ar-fh")
    notes = [P(note, cls="ar-note", id="ar-note", role="status")] if note else []
    if not items:
        return _fragment(head, *notes, P(around.NOTHING.format(where=RANGE_WORDS[mode]), cls="ar-empty", id="ar-empty", role="status"))
    at = free_slot(v, c["kind"], now)
    how = "Chosen and explained by GitAway’s assistant, from the places OpenStreetMap lists." if found["ai"] else "Closest first, open places before closed ones."
    return _fragment(head, *notes, *[card(v, p, c["kind"], at, editor) for p in items],
                     P(f"{how} OpenStreetMap has no ratings, so there are none here.", cls="ar-fine", id="ar-how"))


def _num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def point(lat, lon):
    la, lo = _num(lat), _num(lon)
    return (la, lo) if la is not None and lo is not None and -90 <= la <= 90 and -180 <= lo <= 180 else None


def search_for(session, v, cat, mode, pos, denied):
    """(found, near_text, note, center): run the search for the point `pos` (a phone's), else the day's hotel or first stop. Raises around.AroundError."""
    from gitaway.pages import tab_map
    note, near = "", "near you"
    if pos is None:
        stops = tab_map.located_stops(v, session)
        if not stops:
            raise around.AroundError("GitAway can’t tell where you are, and this day has no place on the map yet. Allow your location and try again.")
        title, pos, hotel = _pick_fallback(stops)
        near = f"near {title}"
        why = "we couldn’t use your location, so these are" if denied else "these are"
        note = f"{why[0].upper() + why[1:]} near {title}" + (", your hotel tonight." if hotel else ", the first stop on today’s map.")
    now = around.now_in(v["zone"])
    pref = around.vegetarian(session)
    found = around.search(cat, pos[0], pos[1], mode, now, pref=pref, family=(session or {}).get("tenant_id", ""))
    return found, near, note, now


def register(app):
    @app.post("/trip/map/around")
    async def around_results(request, session):
        from gitaway.pages import trip as trip_ui
        if not ses.current_traveler(session) or not ses.booking(session):
            return HTMLResponse("Sign in first.", status_code=401)
        if too_fast((session or {}).get("user_id", "")):
            return HTMLResponse(_xml(P(SLOW_DOWN, cls="ar-empty", id="ar-error", role="alert")), status_code=429)
        form = await request.form()
        cat = (form.get("cat") or "")[:12]
        mode = form.get("mode") if form.get("mode") in around.RADIUS else "walk"
        if cat not in around.CATEGORIES:
            return HTMLResponse(_xml(P("Pick one of the buttons.", cls="ar-empty", id="ar-error", role="alert")), status_code=422)

        def work():
            v = trip_ui.load(session, str(form.get("day") or "")[:3], request.headers.get("user-agent", ""))
            pos = point(form.get("lat"), form.get("lon"))
            found, near, note, now = search_for(session, v, cat, mode, pos, denied=(form.get("denied") == "1"))
            return v, found, near, note, now
        try:
            v, found, near, note, now = await run_in_threadpool(work)
        except around.AroundError as e:
            return HTMLResponse(_xml(P(str(e), cls="ar-empty", id="ar-error", role="alert")), status_code=503)
        return HTMLResponse(_xml(fragment(v, cat, mode, found, near, access.can_edit(access.request_role()), now, note)))


def _xml(x):
    from fasthtml.common import to_xml
    return to_xml(x)

