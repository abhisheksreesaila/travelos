"""The Map tab (F-068): the day's stops, numbered in order, on an OpenStreetMap map with the route between them.

GET /trip/map[?day=<index>]   the day's stops; ?view=around is the second segment, "Around you" (gitaway/pages/around_ui.py, F-073). `content(request, session)` is the tab's body; gitaway/pages/phone_tabs.py draws the route, header and tab bar around it.

Every stop that has a place (a flight's airport, the hotel, a plan, the car desk) gets a number. Where a place is comes from gitaway.geo (OpenStreetMap's
geocoder, cached per family, one lookup a second): what is not known yet is looked up for a couple of seconds while the page is made, the rest in
the background, and the page says "finding places" and looks again. A place the geocoder does not know is listed under the map with an Edit trip link.
The map itself is Leaflet (assets/vendor/leaflet, self-hosted) drawn by assets/js/map.js from the JSON in #mp-data; tapping a pin opens the bottom sheet.
The list of stops below the map does the same without the map, and is all there is when the scripts or tiles cannot load.
"""

import json

from fasthtml.common import A, Button, Div, H2, Li, Link, Nav, NotStr, Ol, P, Script, Span

from gitaway import access, familydb, geo, session as ses, tripcal as cal, tripday as td
from gitaway.icons import icon
from gitaway.pages import around_ui, calendar as calui, trip as trip_ui

TITLE = "Map"
HEAD = (Link(rel="stylesheet", href="/assets/vendor/leaflet/leaflet.css"), Link(rel="stylesheet", href="/assets/css/map.css"), *around_ui.HEAD)  # trip.css and phone.css come with the shell
SCRIPTS = ("/assets/vendor/leaflet/leaflet.js", "/assets/js/map.js", *around_ui.SCRIPTS)
NOT_FOUND = "Couldn’t find this place on the map."


def map_url(**q):
    return "/trip/map" + (f"?day={q['day']}" if q.get("day") not in ("", None) else "")


def _phone_of(v, item) -> str:
    """The front desk's number for the hotel stop, when the trip says it (an imported trip's `phone:`)."""
    if item.kind != "hotel" or not cal.is_imported(v["b"]):
        return ""
    d = v["dates"][v["sel"]]
    hotels = cal.plan_of(v["b"]).hotels
    h = next((h for h in hotels if h.check_in.date() == d), None) or next((h for h in hotels if h.check_in.date() <= d < h.check_out.date()), None)
    return (h.phone or "") if h else ""


def _place(item) -> str:
    return geo.as_place(item.place)


def _when(item) -> str:
    return td.span_label(item.start, item.end) if item.kind == "plan" else cal.fmt_time(item.start)


def stops_of(v, db):
    """The day's stops in order: [{n, id, title, label, addr, when, pos: (lat, lon) | None, drive, ...}]. Reads only what is cached."""
    out, prev = [], None
    for x in (x for x in v["items"] if x.place and x.kind not in ("ride", "offer")):
        got, name = geo.state(_place(x), db)
        pos = got if isinstance(got, tuple) else None
        drive = None
        if pos and prev and x.kind != "flight":
            drive = geo.drive_minutes(prev[1], pos, db, lookup=False)
        out.append(dict(n=len(out) + 1, id=x.id, title=x.title, label=x.label, kind=x.kind, place=_place(x), pos=pos, state="found" if pos else ("missing" if got == geo.MISSING else "pending"),
                        addr=_place(x), when=_when(x), drive=drive, tel=_phone_of(v, x),
                        dir=td.maps_url(_place(x), v["ua"]), uber=td.uber_url(_place(x), pos)))
        if pos and x.kind != "flight":
            prev = (x, pos)
    return out


def located_stops(v, session, budget=2.0):
    """The open day's stops that have a place on the map, in order, looking up what is not known yet for up to `budget` seconds (the fallback for Around you
    when the phone will not say where it is: the hotel, else the first stop)."""
    items = [x for x in v["items"] if x.place and x.kind not in ("ride", "offer")]
    places = [(_place(x), True) if x.kind == "flight" else _place(x) for x in items]
    with familydb.using(session) as db:
        if db and places:
            geo.warm(db, places, budget=budget)
        return [s for s in stops_of(v, db) if s["pos"]]


def _drive_from(stops):
    """Say which stop each drive time is from (the nearest earlier one on the map)."""
    last = None
    for s in stops:
        if s["drive"] and last:
            s["from"] = last["title"]
        if s["pos"] and s["kind"] != "flight":
            last = s
    return stops


def _json(data) -> NotStr:
    return NotStr(json.dumps(data, separators=(",", ":")).replace("<", "\\u003c"))


def day_picker(v):
    chips = []
    for d in v["days"]:
        cur = d.index == v["sel"]
        chips.append(A(Span(str(d.num), cls=f"tp-chip-num ink-{d.tint}"), Span(d.dow, cls="tp-chip-dow"), href=map_url(day=d.index), cls=f"tp-chip tp-t-{d.tint}{' is-today' if d.state == 'today' else ''}",
                       data_day=str(d.index), aria_current="date" if cur else None, aria_label=f"{v['dates'][d.index].strftime('%A %b')} {d.num}" + (", today" if d.state == "today" else "")))
    return Nav(*chips, cls="tp-strip", aria_label="Days of the trip", id="mp-strip")


def edit_link(v, stop):
    """How to fix a place the map could not find: a booking (flight, hotel, car) is fixed in Edit trip, a plan in the calendar on its day."""
    if not access.can_edit(v["role"]):
        return ""
    if stop["kind"] == "plan":
        return A(icon("pencil", 14, 2.4), "Fix it in the calendar", href=f"{calui.cal_url('', view='whole')}#d{v['sel']}", cls="btn btn-sm mp-edit")
    if cal.is_imported(v["b"]) and ses.open_trip_id():
        return A(icon("pencil", 14, 2.4), "Edit trip", href=f"/trips/build/edit?trip={ses.open_trip_id()}", cls="btn btn-sm mp-edit")
    return ""


def sheet():
    return Div(Span(cls="mp-grab", aria_hidden="true"),
               Button(icon("x", 18, 2.6), Span("Close", cls="sr-only"), type="button", cls="mp-close", id="mp-close"),
               Div(Span("", cls="mp-num", id="mp-s-n"), Div(H2("", id="mp-s-name"), Span("", cls="mp-addr", id="mp-s-addr"), cls="mp-s-text"), cls="mp-s-row"),
               Div(Span("", cls="mp-pill mp-when", id="mp-s-when"), Span("", cls="mp-pill mp-drive", id="mp-s-drive", hidden=True), cls="mp-meta"),
               Div(A(icon("pin", 18, 2.4), "Directions", href="#", target="_blank", rel="noopener", cls="tp-btn tp-btn-coral", id="mp-s-dir"),
                   A(icon("car", 18, 2.4), "Uber", href="#", target="_blank", rel="noopener", cls="tp-btn tp-btn-white", id="mp-s-uber"),
                   A(icon("phone", 18, 2.4), Span("Call", cls="sr-only"), href="#", cls="tp-btn tp-btn-white mp-call", id="mp-s-tel", hidden=True), cls="mp-acts"),
               id="mp-sheet", cls="mp-sheet", hidden=True, role="region", aria_label="Stop details", aria_live="polite")


def stop_list(stops, v):
    rows = []
    for s in stops:
        head = (Span(str(s["n"]), cls="mp-num"), Div(Span(s["title"], cls="tp-what"), Span(s["when"], cls="tp-sub"), cls="mp-li-text"))
        if s["pos"]:
            rows.append(Li(Button(*head, type="button", cls="mp-li", data_stop=str(s["n"]), aria_label=f"Stop {s['n']}, {s['title']}, show on the map"), cls="mp-item"))
        else:
            why = NOT_FOUND if s["state"] == "missing" else "Still finding this place…"
            rows.append(Li(Div(*head, cls="mp-li mp-li-off"), P(why, cls="mp-unknown", data_unknown=str(s["n"])), edit_link(v, s) if s["state"] == "missing" else "", cls="mp-item"))
    return Ol(*rows, cls="mp-list", id="mp-list")


def content(request, session):
    """The map tab's body for the day in ?day= (else today, else the first day)."""
    ua = request.headers.get("user-agent", "")
    v = trip_ui.load(session, request.query_params.get("day", "")[:3], ua)
    if request.query_params.get("view") == "around":   # the second segment (F-073)
        return around_ui.view(request, session, v)
    items = [x for x in v["items"] if x.place and x.kind not in ("ride", "offer")]
    places = [(_place(x), True) if x.kind == "flight" else _place(x) for x in items]
    with familydb.using(session) as db:
        left = geo.warm(db, places, budget=2.0) if db and places else 0
        stops = _drive_from(stops_of(v, db))
        located = [s["pos"] for s in stops if s["pos"] and s["kind"] != "flight"]
        line = geo.route(located, db, lookup=False) if db else None
    if left:
        geo.warm_async(session, places)
    d = v["dates"][v["sel"]]
    n = len(stops)
    chip = Div(Span(str(d.day), cls="mp-chip-num"), f"{d.strftime('%A')} · {n} stop{'s' if n != 1 else ''}, in order" if n else f"{d.strftime('%A')} · nothing with a place today", cls="mp-daychip", id="mp-daychip")
    data = dict(stops=[dict(n=s["n"], kind=s["kind"], title=s["title"], addr=s["addr"], when=s["when"], lat=s["pos"][0], lon=s["pos"][1], drive=s["drive"], frm=s.get("from", ""), dir=s["dir"], uber=s["uber"], tel=s["tel"])
                       for s in stops if s["pos"]], route=line, pending=left)
    body = []
    if not n:
        body.append(Div(Span("nothing to find!", cls="tp-hand"), P("Plans, hotels and flights with a place show up here.", cls="tp-sub"), cls="tp-empty", id="mp-empty"))
    else:
        found = bool(data["stops"])
        body.append(Div(Div(id="mp-map", cls="mp-map", role="application", aria_label="Map of the day's stops"), sheet(), cls="mp-stage", id="mp-stage") if found else "")
        if left:
            body.append(P("Finding places on the map…", role="status", cls="mp-finding", id="mp-finding"))
        body.append(stop_list(stops, v))
    back = A(icon("chev-left", 18, 2.6), f"Back to {d.strftime('%A')}", href=f"/trip/canvas?day={v['sel']}", cls="mp-back", id="mp-back")   # F-096: Map has no tab now; this is the way back to the day
    return (back, around_ui.segment("stops", v["sel"]), day_picker(v), chip, *body,
            Script(_json(data), type="application/json", id="mp-data"))


def register(app):
    around_ui.register(app)   # POST /trip/map/around: the cards for Around you (F-073)
