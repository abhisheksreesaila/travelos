"""The trip cockpit (F-201, Direction 3 "Ticket line"): the trip's home screen. Design: docs/design/cockpit/3-ticket.html and README.md.

GET /trip/cockpit[?day=N]               the page: the week as a line of day stubs (each with its living sky and its times), the open day's ticket (on today:
                                        Up next with the next leg turn by turn), the wallet's passes and the paper map. The model is gitaway/cockpit.py.
GET /trip/cockpit/map                   the paper map's state as JSON ({state, box, km, pack}), which the page asks again while a pack is being built
GET /trip/cockpit/pack/<key>.json       the open trip's geo pack: its OpenStreetMap shapes (gitaway/geopack.py) ...
GET /trip/cockpit/pack/<key>-light.webp ... and its relief, light or dark. Kept by the browser for good (the key changes with every build) and by the service
                                        worker for this person, so the map works offline once it has loaded.

Everything is drawn by the server, so it works without script: a day stub is a link to ?day=N. With script (assets/js/cockpit.js, wx.js, paper.js) a tap opens
that day's ticket in place and the paper map flies to it; on a phone it grows out of the stub (GA.motion), on a desktop it is the calm fade. "Open map" loads
MapLibre and OpenFreeMap's street map only when tapped. Every function of the trip stays one tap away: each ticket opens its day (plans, notes, chat), the tab
bar and the top bar keep Ask and Family, and the passes open their booking's sheet.
"""

import json
import logging

from fasthtml.common import A, Article, B, Button, Dd, Details, Div, Dl, Dt, Em, H1, H2, Header, I, Li, Link, Main, NotStr, Ol, P, Script, Section, Span, Summary, Ul
from starlette.responses import Response

from gitaway import cockpit as ck, geopack, phone, session as ses, topbar
from gitaway.icons import icon
from gitaway.layout import join_note
from gitaway.pages import tripcanvas

log = logging.getLogger(__name__)
HEAD = (Link(rel="stylesheet", href="/assets/css/cockpit.css"),)
SCRIPTS = ("/assets/js/wx.js", "/assets/js/paper.js", "/assets/js/cockpit.js")
KIND_ICON = {"flight": "plane", "stay": "bed", "car": "car"}
MAP_ICONS = ("plane", "bed", "car", "spark", "food", "tree", "sight", "pin", "x")      # the paper map's labels and the street map's close button (paper.js draws them from the page's data)


def cockpit_url(day=None):
    q = []
    if day is not None:
        q.append(f"day={day}")
    if (trip := ses.open_trip_id()):
        q.append(f"trip={trip}")
    return "/trip/cockpit" + (f"?{'&'.join(q)}" if q else "")


def _wx(w):
    return json.dumps({"kind": w.kind, "gust": w.gust, "ground": w.ground}, separators=(",", ":"))


def temp(w) -> str:
    return f"{w.hi}°" if w.hi is not None else ""


def sky(w, cls="ck-sky", src=False):
    """A day's living sky: the canvas wx.js draws on, the temperature and the words (the flakes fade behind every [data-calm] box). With no weather known (a real
    trip before F-203's forecasts) it is a plain sky that says nothing: no number, no words, no weather drawn, hidden from screen readers."""
    known = w.hi is not None
    label = {"role": "img", "aria_label": f"{w.word}, high {w.hi}°" + (f" ({w.source.lower()})" if w.sample else "")} if known else {"aria_hidden": "true"}
    return Div(NotStr('<canvas aria-hidden="true"></canvas>'), B(temp(w), cls="ck-temp", data_calm="1"), Span(w.word, cls="ck-word", data_calm="1"),
               Span(w.source, cls="ck-src", data_calm="1") if src else "", cls=cls, data_wx=_wx(w), **label)


def closed_body(d):
    """A closed stub: the day, its first items, and "+N more" for the rest (three show on a laptop, two on a phone or a short laptop, so both counts are drawn and
    CSS shows the one that is true; a tap on the stub opens the day's whole ticket)."""
    items = list(d.lines)
    foot = [Span(icon("check", 12, 3), " · ".join(d.booked), cls="ck-on")] if d.booked else [Span("Nothing to book", cls="ck-free")]      # one wrapping line: "United · Hertz · Stay"
    more = [Li(f"+{len(items) - n} more", cls=f"ck-more ck-more{n}") for n in (3, 2) if len(items) > n]
    return Div(Div(B(f"{d.dow} {d.num}"), Span(d.name), cls="ck-d"),
               Ul(*[Li(I(cls=f"ck-dot ck-k-{x.kind}"), Span(x.time, cls="ck-t"), B(x.short or x.title), cls="ck-it") for x in items[:3]], *more, cls="ck-items"),
               Div(*foot, cls="ck-foot"), cls="ck-closed")


def plan_body(d, day_href):
    rows = [Li(Span(ck.clock(x.start), cls="ck-p-t"),
               Span(I(icon(x.icon if x.booked else ck.ICON_OF_KIND.get(x.kind, "spark"), 15, 2.4), cls="ck-tile"), B(x.title), Em("Booked") if x.booked else "", cls=f"ck-p-b ck-k-{x.kind}"),
               cls="ck-p") for x in d.lines]
    return Div(Span(f"{d.dow} {d.date} · {d.name}", cls="ck-eyebrow"),
               Ol(*rows, cls="ck-plan") if rows else P("Nothing planned yet.", cls="ck-none"),
               Div(A(icon("calendar", 16, 2.4), "Open the day", href=day_href, cls="ck-btn ck-btn-fill", data_open_day=str(d.i)), cls="ck-acts"),
               cls="ck-open")


def up_body(t, day_href):
    """Today's ticket: Up next, when to leave, how far, the leg turn by turn, Start directions."""
    if t.title == "You are all caught up":
        return Div(Span(t.kicker, cls="ck-eyebrow"), H2(t.title, cls="ck-up-t"), P(t.sub, cls="ck-up-sub") if t.sub else "",
                   Div(A(icon("calendar", 16, 2.4), "Today’s plan", href=day_href, cls="ck-btn ck-btn-fill", data_open_day="today"), cls="ck-acts"), cls="ck-open ck-up")
    kv = [(label, value) for label, value in (("Leave", t.leave), ("Drive", f"{t.drive} min" if t.drive else ""), ("Starts", t.starts), ("Distance", f"{t.mi:g} mi" if t.mi else "")) if value]
    legs = [Li(Span(icon(s.icon, 15, 2.6), cls="ck-lg-i"), Span(s.verb, " ", B(s.road) if s.road else "", cls="ck-lg-t"), Span(f"{s.mi:g} mi", cls="ck-lg-d"), cls="ck-lg")
            for s in t.steps]
    shown, rest = legs[:ck.SHOWN_STEPS], legs[ck.SHOWN_STEPS:]      # the rest of the drive opens in place: nothing is cut without saying so
    acts = [A(icon("nav", 16, 2.4), "Start directions", href=t.directions, target="_blank", rel="noopener", cls="ck-btn ck-btn-fill", data_go="1")] if t.directions else []      # (drawn twice: the desktop's stub and the phone's ticket, so no ids)
    if t.kind == "flight" and t.passes:      # a flight day: everyone's boarding passes are in the flight's own sheet, one tap from home
        acts.append(A(icon("ticket", 16, 2.4), "Boarding passes", href=t.passes, cls="ck-btn ck-btn-tonal", data_passes="1"))
    acts.append(A(icon("calendar", 16, 2.4), "Today’s plan", href=day_href, cls="ck-btn ck-btn-tonal", data_open_day="today"))
    return Div(Span(t.kicker, cls="ck-eyebrow ck-kicker"), H2(t.title, cls="ck-up-t"),
               Dl(*[Div(Dt(label), Dd(value), cls="ck-kv-i") for label, value in kv], cls="ck-kv") if kv else "",
               Div(cls="ck-perf", aria_hidden="true") if legs else "",
               Ol(*shown, cls="ck-legs", aria_label="The drive, turn by turn") if legs else "",
               Details(Summary(f"+{len(rest)} more", Span(f" step{'s' if len(rest) != 1 else ''} of the drive", cls="sr-only"), cls="ck-more-s"), Ol(*rest, cls="ck-legs", start=str(len(shown) + 1)),
                       cls="ck-more") if rest else "",
               Div(*acts, cls="ck-acts"), cls="ck-open ck-up")


def open_body(v, d):
    href = tripcanvas.curl(day=d.i)
    return up_body(v.ticket, href) if d.i == v.today and v.ticket else plan_body(d, href)


def stub(v, d):
    is_open = d.i == v.open_day
    cls = "ck-stub" + (" is-open" if is_open else "") + (" is-today" if d.i == v.today else "") + (" is-done" if d.state == "done" else "")
    label = f"{d.dow} {d.date}: {d.name}" + (" (today)" if d.i == v.today else "")
    return Article(A(Span(label, cls="sr-only"), href=cockpit_url(d.i), cls="ck-hit", data_day=str(d.i), aria_current="true" if is_open else None),
                   sky(d.wx), Div(closed_body(d), open_body(v, d), cls="ck-body"), cls=cls, data_day=str(d.i), id=f"ck-stub-{d.i}")


def ticket(v):
    """The phone's ticket at the top: the open day's sky and its open body (every day's is here, the open one shown)."""
    d = v.days[v.open_day]
    panels = [Div(open_body(v, x), cls="ck-tk", data_day=str(x.i), data_wx=_wx(x.wx), data_temp=temp(x.wx), data_word=x.wx.word, data_src=x.wx.source,
                  hidden=x.i != v.open_day) for x in v.days]
    return Section(sky(d.wx, "ck-sky ck-sky-wide", src=True), *panels, cls="ck-ticket" + (" is-today" if v.open_day == v.today else ""), id="ck-ticket",
                   aria_label="The open day", data_day=str(v.open_day))


def pass_card(p):
    partner = ck.partner_name(p.partner)
    manage = ck.safe_manage(p.manage, partner)      # F-198: an https page on the partner's own site, or nothing; GitAway is never the support centre
    foot = [Span(Span(icon("check", 12, 3.2), cls="ck-ck"), f"Booked on {partner}" if partner else "Booked", cls="ck-bo")]
    if p.ref:
        foot.append(Span("Ref ", B(p.ref), cls="ck-ref"))
    if manage:
        foot.append(A("Change or cancel", icon("ext", 13, 2.4), href=manage, target="_blank", rel="noopener", cls="ck-cxl"))
    elif p.href:
        foot.append(A("Details", icon("chev-right", 13, 2.6), href=p.href, cls="ck-cxl"))
    return Article(Div(Span(p.eyebrow, cls="ck-eyebrow"), icon(KIND_ICON[p.kind], 18, 2.2), cls="ck-pass-h"),
                   Div(p.title, cls="ck-pass-t"), Div(p.sub, cls="ck-pass-s"), Div(cls="ck-perf", aria_hidden="true"), Div(*foot, cls="ck-pass-f"),
                   cls=f"ck-pass ck-k-{p.kind}", data_pass=p.kind)


MAP_NOTE = {"building": "Drawing your map: the relief appears in a moment.", "none": "The map appears once a stop of the trip has a place.",
            "waiting": "The map's relief could not be drawn just now. It will try again."}


OSM_COPYRIGHT = "https://www.openstreetmap.org/copyright"
TERRAIN_CREDITS = "https://github.com/tilezen/joerd/blob/master/docs/attribution.md"      # the terrain tiles' sources: USGS 3DEP for the US, SRTM, GMTED and others


def credits(wx_notes=()):
    """The map's credits, then what the weather must say (F-203, dayweather.notes: MET's credit as a link, the typical-weather labels)."""
    wx = [x for text, href in wx_notes for x in (Span(" · ", aria_hidden="true"), A(text, href=href, target="_blank", rel="noopener") if href else Span(text))]
    return (A("© OpenStreetMap contributors", href=OSM_COPYRIGHT, target="_blank", rel="noopener"), Span(" · ", aria_hidden="true"),
            A("Terrain: USGS and others", href=TERRAIN_CREDITS, target="_blank", rel="noopener"), *wx)


def map_card(v):
    m = v.map
    return Section(Div(cls="ck-paper", id="ck-paper", data_state=m["state"]),
                   Div(Span(icon("layers", 14, 2.4), "Paper map · real relief", cls="ck-tag"), Span("Tap a day: the map flies there", cls="ck-tag ck-soft"), cls="ck-map-tools"),
                   Button(icon("map", 16, 2.4), "Open map", type="button", cls="ck-btn ck-btn-map", id="ck-open-map", aria_haspopup="dialog", hidden=m["state"] == "none"),      # (shown when a place arrives)
                   P(MAP_NOTE[m["state"]], cls="ck-map-note", id="ck-map-note") if m["state"] != "ready" else "",
                   P(*credits(v.wx_notes), cls="ck-cap"),
                   cls="ck-map", aria_label="Map of the trip"), P(*credits(v.wx_notes), cls="ck-credits")      # the laptop's caption over the map; a phone's line under it (48px links)


def page_body(v):
    phone_kicker = Span(v.phone_eyebrow, cls="ck-eyebrow")
    head = Header(Div(Span(v.eyebrow, cls="ck-eyebrow"), H1(v.title, cls="ck-title"), cls="ck-head-t ck-head-desk"),
                  Div(topbar.trip_menu(phone_kicker) or phone_kicker, H1(v.head_day, cls="ck-title"), P(v.head_sub, cls="ck-pday"), cls="ck-head-t ck-head-phone"),   # the phone's eyebrow is the trip menu (switch trips)
                  Div(Span(icon("sun", 15, 2.2), "Sample weather", cls="ck-chip ck-chip-sample") if any(d.wx.sample for d in v.days) else "",      # said where every sky can see it
                      Span(icon("calendar", 15, 2.2), v.dates, cls="ck-chip"), Span(icon("users", 15, 2.2), v.party, cls="ck-chip"), cls="ck-chips"), cls="ck-head")
    week = Section(*[stub(v, d) for d in v.days], cls="ck-week" + (" is-long" if len(v.days) > 9 else ""), id="ck-week", aria_label="The week")
    wallet = Section(*[pass_card(p) for p in v.passes], cls=f"ck-wallet ck-n{len(v.passes)}", id="ck-wallet", aria_label="Bookings") if v.passes else ""
    icons = {name: str(icon(name, 14, 2.4)) for name in MAP_ICONS}
    data = safe_json({**v.map, "icons": icons})
    return (head, ticket(v), *map_card(v),
            Div(B("The week"), Span("Tap a day to open its ticket"), cls="ck-sec", id="ck-sec-week"), week,
            Div(B("Wallet"), Span(f"{len(v.passes)} booking{'s' if len(v.passes) != 1 else ''}, each with its own sheet"), cls="ck-sec") if v.passes else "", wallet,
            Script(NotStr(data), type="application/json", id="ck-data"))


def safe_json(obj) -> str:
    """JSON that can sit inside <script type="application/json">: every less-than, greater-than and ampersand is written as a JSON unicode escape (backslash u003c,
    u003e, u0026), so a plan called "Lunch <!--<script> in town" can neither end the script nor open a comment."""
    return json.dumps(obj, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def map_state(session):
    """The paper map's data for the open trip ({state, box, km, pack, days}), asked again by the page while it waits for a pack or a first place."""
    return ck.map_data(session, geopack.ensure(session))


def _guard(session):
    return phone.guard(session, "/trip/cockpit")


def register(app):
    @app.get("/trip/cockpit")
    def cockpit_page(request, session, day: str = ""):
        """A plain def: Starlette runs it in its thread pool, so the cache reads and the pack check never hold up the event loop."""
        if (r := _guard(session)):
            return r
        try:
            state = geopack.ensure(session)       # the first visit with places starts the pack in the background (F-201); never waits for it
        except Exception:  # the map is never worth failing the trip's home over
            log.exception("could not start the trip's geo pack")
            state = "waiting"
        v = ck.view(session, day[:3], request.headers.get("user-agent", ""), curl=tripcanvas.curl, pack_state=state)
        main = Main(*page_body(v), id="main", cls="ph-main ck", data_open=str(v.open_day), data_today="" if v.today is None else str(v.today))
        return phone.shell("trip", join_note(), main, title=v.title, head=HEAD, scripts=SCRIPTS, id="ck-app", data_cockpit="1")

    @app.get("/trip/cockpit/map")
    def cockpit_map(session):
        if not ses.current_traveler(session) or not ses.booking(session):
            return Response("{}", status_code=401, media_type="application/json")
        return Response(json.dumps(map_state(session)), media_type="application/json", headers={"Cache-Control": "no-store"})

    @app.get("/trip/cockpit/pack/{name}")
    def cockpit_pack(session, name: str):
        """The open trip's pack, only to its own family; the key in the name must be the stored one (so nobody guesses another trip's)."""
        if not ses.current_traveler(session) or not ses.booking(session):
            return Response("not found", status_code=404, media_type="text/plain")
        row = geopack.stored(session)
        key, _, rest = name.partition("-") if name.endswith(".webp") else (name.removesuffix(".json"), "", "json")
        if not row or key != row["key"]:
            return Response("not found", status_code=404, media_type="text/plain")
        forever = {"Cache-Control": "private, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"}
        if rest == "json" and name.endswith(".json"):
            return Response(row["shapes"], media_type="application/json", headers=forever)
        if rest in ("light.webp", "dark.webp"):
            return Response(bytes(row["light" if rest == "light.webp" else "dark"]), media_type="image/webp", headers=forever)
        return Response("not found", status_code=404, media_type="text/plain")
