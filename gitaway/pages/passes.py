"""Passes & documents (F-083): the section of the Help tab, the flight card on Today's travel day, the full-screen gate view, and the routes behind them.

Help      gitaway/pages/tab_help.py calls `section(...)`: per flight a "Passes & documents" block with one card per traveller (seat, group, gate, boarding
          time, the pass file as a thumbnail that opens full screen, "Open in airline app" only when an editor pasted a link). Editors add flights and passes.
Today     gitaway/pages/trip.py calls `flight_cards(v)`: on the flight's day, before it leaves, the dark focal card with "Show everyone's passes".
GET  /trip/passes/gate?flight=<key>            the gate view: white, large, one traveller per screen, swipe (or the arrows / dots) to the next; `#gp-<pass id>` starts on one
GET  /trip/passes/<id>/<display|thumb|file>    a pass's picture, thumbnail or PDF, only to a signed-in member of its family, `Cache-Control: private, no-cache` with an ETag
POST /trip/help/flight                         (editor) add a flight, or fix one with `flight_id`
POST /trip/help/flight/remove                  (editor) remove a flight that was added by hand, with its passes
POST /trip/help/pass                           (editor, multipart) add a pass, or fix one with `pass_id`; the optional `file` is a PDF or a picture, at most passes.MAX_BYTES
POST /trip/help/pass/remove                    (editor) remove one pass and its files
The writes are not on gitaway.access.OPEN_POSTS: only editors and admins may make them. The rules and the storage are in gitaway/passes.py.
"""

import asyncio
from urllib.parse import quote

from fasthtml.common import A, Button, Datalist, Details, Div, Form, H2, Img, Input, Label, Link, Option, P, Script, Span, Summary, Title
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, PlainTextResponse, RedirectResponse, Response

from gitaway import access, catalog, passes, phone, session as ses, tripcal as cal, tripday as td
from gitaway.icons import icon
from gitaway.layout import styles

HEAD = (Link(rel="stylesheet", href="/assets/css/passes.css"),)
GATE = "/trip/passes/gate"
FORM = "/trip/help/pass"
TINTS = ("sun", "mint", "grape", "sky", "bubble")
ACCEPT = "application/pdf,image/jpeg,image/png,image/webp,image/heic,image/heif,image/*"
MIME = {"display": "image/jpeg", "thumb": "image/jpeg", "file": "application/pdf"}
TOO_BIG = "That file is too large (at most {mb} MB)."


# ---- small helpers ----------------------------------------------------------------------------------------------------------

def clock(minute) -> str:
    return cal.fmt_time(int(minute))


def day_label(d) -> str:
    return f"{d.strftime('%a %b')} {d.day}"


def initials(name) -> str:
    words = [w for w in (name or "").split() if w]
    return ("".join(w[0] for w in words[:2]) or "?").upper()


def tint(i) -> str:
    return TINTS[i % len(TINTS)]


def gate_url(key, pid="") -> str:
    return f"{GATE}?flight={quote(key, safe='')}" + (f"#gp-{pid}" if pid else "")


def flight_line(f) -> str:
    return f"{f['name']} · departs {clock(f['depart_min'])}" + (f" · Terminal {f['terminal']}" if f["terminal"] else "")


def seats_of(ps) -> str:
    seats = [p["seat"] for p in ps if p["seat"]]
    return ", ".join(seats) if len(seats) <= 4 else f"{len(seats)} seats"


def gate_of(ps) -> str:
    gates = {p["gate"] for p in ps if p["gate"]}
    return next(iter(gates)) if len(gates) == 1 else ""


def boards_of(ps):
    times = [p["boards_min"] for p in ps if p["boards_min"] is not None]
    return min(times) if times else None


def _field(label, name, value="", **attrs):
    return Label(Span(label, cls="hp-lab"), Input(name=name, value=value, **attrs), cls="pz-field")


# ---- Help: the "Passes & documents" section ------------------------------------------------------------------------------

def _flight_form(f=None):
    """Add a flight, or fix one that was added by hand (f is its dict)."""
    f = f or {}
    trip = ses.open_trip_id()
    return Form(
        Div(_field("Airline", "airline", f.get("airline", ""), maxlength="24", autocomplete="off", placeholder="United", required=True),
            _field("Flight number", "number", f.get("number", ""), maxlength="6", autocomplete="off", placeholder="1234", required=True), cls="pz-two"),
        Div(_field("From (airport code)", "from_code", f.get("origin", ""), maxlength="3", autocomplete="off", placeholder="LAX", required=True, cls="pz-code"),
            _field("To (airport code)", "to_code", f.get("dest", ""), maxlength="3", autocomplete="off", placeholder="SFO", required=True, cls="pz-code"), cls="pz-two"),
        Div(_field("Date it leaves", "fly_on", f["date"].isoformat() if f else "", type="date", required=True),
            _field("Time it leaves", "time", f"{f['depart_min'] // 60:02d}:{f['depart_min'] % 60:02d}" if f else "", type="time", required=True), cls="pz-two"),
        _field("Terminal (optional)", "terminal", f.get("terminal", ""), maxlength="12", autocomplete="off", placeholder="7"),
        Input(type="hidden", name="trip", value=trip), Input(type="hidden", name="flight_id", value=f.get("id", "")),
        Div(Button("Save the flight", type="submit", cls="tp-btn tp-btn-ink pz-save"), cls="hp-fix-acts"),
        action="/trip/help/flight", method="post", enctype="application/x-www-form-urlencoded", cls="hp-fix-form pz-form", data_form="flight")


def _pass_form(flight, p=None, names=()):
    """Add a pass for a traveller on `flight`, or fix `p`. The form posts the file too (multipart)."""
    p = p or {}
    trip, uid = ses.open_trip_id(), f"{flight['key']}-{p.get('id', 'new')}".replace(":", "-")
    boards = f"{p['boards_min'] // 60:02d}:{p['boards_min'] % 60:02d}" if p.get("boards_min") is not None else ""
    return Form(
        Label(Span("Who is it for", cls="hp-lab"), Input(name="traveller", value=p.get("traveller", ""), maxlength="40", autocomplete="off", list=f"pz-names-{uid}", required=True), cls="pz-field"),
        Datalist(*[Option(value=n) for n in names], id=f"pz-names-{uid}"),
        Div(_field("Seat", "seat", p.get("seat", ""), maxlength="6", autocomplete="off", placeholder="21A"), _field("Group", "grp", p.get("grp", ""), maxlength="4", autocomplete="off", placeholder="3"),
            _field("Gate", "gate", p.get("gate", ""), maxlength="6", autocomplete="off", placeholder="71B"), cls="pz-three"),
        _field("Boarding time", "boards", boards, type="time"),
        Label(Span("The boarding pass (PDF or picture, at most 10 MB)", cls="hp-lab"), Input(type="file", name="file", accept=ACCEPT), cls="pz-field pz-file"),
        _field("Airline app link (optional)", "app_url", p.get("app_url", ""), type="url", maxlength="480", autocomplete="off", placeholder="https://"),
        Input(type="hidden", name="trip", value=trip), Input(type="hidden", name="flight", value=flight["key"]), Input(type="hidden", name="pass_id", value=p.get("id", "")),
        Div(Button("Save the pass", type="submit", cls="tp-btn tp-btn-ink pz-save"), cls="hp-fix-acts"),
        action=FORM, method="post", enctype="multipart/form-data", cls="hp-fix-form pz-form", data_form="pass")


def _confirm_remove(action, field, value, what, label):
    """Two taps to remove: open this, then 'Yes, remove it'."""
    return Details(Summary(icon("x", 15, 2.4), label, cls="tp-mini pz-remove-sum"),
                   Form(P(f"Remove {what} for the whole family? This cannot be undone.", cls="tp-sub"), Input(type="hidden", name=field, value=value), Input(type="hidden", name="trip", value=ses.open_trip_id()),
                        Button("Yes, remove it", type="submit", cls="tp-btn tp-btn-white pz-remove-yes"), action=action, method="post", cls="hp-fix-form"), cls="hp-fix pz-remove")


def _stub(p, f):
    """The pass file: a thumbnail (a picture of the first page for a PDF) that opens the gate view on this person, or a quiet 'nothing attached yet'."""
    if not p["kind"]:
        return Div(Span(icon("file", 20, 2.2), cls="pz-pdf", aria_hidden="true"), Span(Span("No boarding pass attached yet", cls="pz-st-t"), Span("An editor can add the file.", cls="tp-sub"), cls="pz-st-x"), cls="pz-stub is-empty")
    pic = Img(src=f"/trip/passes/{p['id']}/thumb", alt="", loading="lazy", cls="pz-thumb") if p["thumb"] else Span(icon("file", 22, 2.2), Span("PDF", cls="pz-pdf-t"), cls="pz-pdf", aria_hidden="true")
    what = "PDF" if p["kind"] == "pdf" else "Picture"
    return A(pic, Span(Span("Boarding pass", cls="pz-st-t"), Span(f"{what} · tap to show full screen", cls="tp-sub"), cls="pz-st-x"), href=gate_url(f["key"], p["id"]), cls="pz-stub", data_open_gate=p["id"],
             aria_label=f"Show {p['traveller']}'s boarding pass full screen")


def _pass_card(p, f, i, can_edit, names):
    name = p["traveller"]
    app = A(icon("ext", 16, 2.4), "Open in airline app", href=p["app_url"], target="_blank", rel="noopener noreferrer", cls="tp-btn tp-btn-white pz-app", data_app=p["id"]) if p["app_url"] else ""
    boards = clock(p["boards_min"]) if p["boards_min"] is not None else "–"
    edit = Div(Details(Summary(icon("pencil", 15, 2.4), "Fix this pass", Span(f" for {name}", cls="sr-only"), cls="tp-mini hp-fix-sum"), _pass_form(f, p, names), cls="hp-fix", data_fix=f"pass-{p['id']}"),
               _confirm_remove("/trip/help/pass/remove", "pass_id", p["id"], f"{name}'s pass", "Remove"), cls="pz-edit") if can_edit else ""
    return Div(
        Div(Span(initials(name), cls=f"hp-av fill-{tint(i)}"), Span(Span(name, cls="pz-name"), Span("Boarding pass" if p["kind"] else "Seat details", cls="tp-sub"), cls="pz-who"),
            Span(Span("SEAT", cls="pz-k"), Span(p["seat"] or "–", cls="pz-seat"), cls="pz-seatbox"), cls="pz-top"),
        Div(Div(Span("GROUP", cls="pz-k"), Span(p["grp"] or "–", cls="pz-v")), Div(Span("GATE", cls="pz-k"), Span(p["gate"] or "–", cls="pz-v")), Div(Span("BOARDS", cls="pz-k"), Span(boards, cls="pz-v")), cls="pz-g3"),
        _stub(p, f), app, edit, cls="pz-pass", data_pass=p["id"])


def _flight_block(f, ps, can_edit, names, n):
    head = Div(Span(icon("plane", 22, 2.2), cls="hp-ico hp-sky", aria_hidden="true"),
               Div(H2(f"{f['name']} · {f['origin']} → {f['dest']}", cls="hp-h"), Span(f"{day_label(f['date'])} · departs {clock(f['depart_min'])}" + (f" · Terminal {f['terminal']}" if f["terminal"] else ""), cls="hp-addr"), cls="hp-who"), cls="hp-row")
    cards = [_pass_card(p, f, i, can_edit, names) for i, p in enumerate(ps)]
    if not cards:
        cards = [P("No passes added yet." + (" Add one for each traveller." if can_edit else ""), cls="hp-empty", data_none="passes")]
    tools = []
    if can_edit:
        tools.append(Details(Summary(icon("plus", 15, 2.4), "Add a pass", cls="tp-mini hp-fix-sum"), _pass_form(f, None, names), cls="hp-fix", data_fix=f"add-pass-{n}"))
        if f["source"] == "added":
            tools.append(Details(Summary(icon("pencil", 15, 2.4), "Fix this flight", cls="tp-mini hp-fix-sum"), _flight_form(f), cls="hp-fix", data_fix=f"flight-{n}"))
            tools.append(_confirm_remove("/trip/help/flight/remove", "flight_id", f["id"], f"{f['name']} and its passes", "Remove this flight"))
    return Div(head, *cards, Div(*tools, cls="pz-tools") if tools else "", cls="hp-card pz-flight", id=f"pz-flight-{n}", data_flight=f["key"])


def section(request, session, can_edit):
    """The Help tab's "Passes & documents": a block per flight, the form to add a flight, and a line about who sees it."""
    fl, ps = passes.flights(session), passes.listing(session)
    names = passes.travellers(session)
    err = request.query_params.get("err", "")
    problem = Div(passes.ERRORS[err], role="alert", cls="hp-problem", id="pz-problem") if err in passes.ERRORS else ""
    blocks = [_flight_block(f, ps.get(f["key"], []), can_edit, names, n) for n, f in enumerate(fl)]
    if not blocks:
        blocks = [Div(P("No flights on this trip yet." + (" Add one to keep everyone's seats and boarding passes in one place." if can_edit else ""), cls="hp-empty", id="pz-none"), cls="hp-card")]
    add = Details(Summary(icon("plus", 16, 2.4), "Add a flight", cls="tp-mini hp-fix-sum"), _flight_form(), cls="hp-fix pz-addflight", id="pz-add-flight", data_fix="add-flight") if can_edit else ""
    return Div(
        Div(Span("HELP · FAMILY ONLY", cls="hp-k"), H2("Passes & documents", cls="pz-title"), cls="pz-head"),
        problem, *blocks, add,
        Div(icon("shield", 18, 2.4), Span(Span("Only your family sees these.", cls="pz-bold"), " Apple Wallet passes come from the airline's app; add them there, and keep a copy here for the gate."), cls="pz-priv"),
        cls="pz", id="hp-passes")


# ---- Today: the flight on its day ---------------------------------------------------------------------------------------------

def flight_cards(v):
    """(the card or cards, the titles of the timeline items they replace) for the flights that leave on the day Today is showing, else ("", ()).

    Only while the trip is on and the flight has not left yet: the dark focal card with boarding time, gate and seats and "Show everyone's passes"."""
    if v["phase"] != "during":
        return "", ()
    session, day = v["session"], v["dates"][v["sel"]]
    today = [f for f in passes.flights(session) if f["date"] == day]
    if not today:
        return "", ()
    allp, can_edit, cards, hide = passes.listing(session), access.can_edit(v["role"]), [], []
    for n, f in enumerate(today):
        zone = passes.flight_zone(f, v["zone"])
        ps = allp.get(f["key"], [])
        if f["source"] == "import" and not ps:
            continue   # an imported flight is already an ordinary item of the day; it becomes the focal card once it has passes
        boards = boards_of(ps)
        if v["sel"] == v["today_idx"]:
            minute = td.now_minute(zone) if catalog.today_in(zone) == day else (0 if catalog.today_in(zone) < day else 24 * 60)
            if minute >= f["depart_min"]:
                continue   # it has left: the ordinary Up next card takes over
            kicker = f"BOARDING {td.until(boards - minute).upper()}" if boards is not None and minute < boards else f"DEPARTS {td.until(f['depart_min'] - minute).upper()}"
        else:
            kicker = "FLIGHT DAY"
        hide.append(f"{f['name']} · {f['origin']} → {f['dest']}")
        stats = [(label, val) for label, val in (("BOARDING", clock(boards) if boards is not None else ""), ("GATE", gate_of(ps)), ("SEATS", seats_of(ps))) if val]
        groups = {p["grp"] for p in ps if p["grp"]}
        if ps:
            action = A(icon("ticket", 18, 2.4), "Show everyone's passes", href=gate_url(f["key"]), cls="tp-btn tp-btn-coral", id=f"pz-show-{n}", data_show_passes=f["key"])
        elif can_edit:
            action = A(icon("plus", 18, 2.4), "Add the boarding passes", href="/trip/help#hp-passes", cls="tp-btn tp-btn-coral", id=f"pz-show-{n}")
        else:
            action = Span("No passes added yet.", cls="tp-up-sub", id=f"pz-show-{n}")
        cards.append(Div(
            Span(Span(cls="tp-pulse", aria_hidden="true"), kicker, cls="tp-kicker"),
            Span(Span(f["origin"]), icon("plane", 26, 2.2), Span(f["dest"]), cls="tp-up-title pz-route"),
            Span(flight_line(f), cls="tp-up-sub"),
            Div(*[Div(Span(k, cls="pz-sk"), Span(val, cls="pz-sv")) for k, val in stats], cls="pz-stats") if stats else "",
            action,
            Span(f"Group {next(iter(groups))}, all {len(ps)} together" if len(groups) == 1 and len(ps) > 1 else "", cls="tp-up-sub pz-grp") if groups else "",
            cls="tp-up pz-up", id="tp-up" if not cards else f"tp-up-{n}", data_flight=f["key"]))
    return (Div(*cards, cls="pz-ups"), tuple(hide)) if cards else ("", ())


# ---- the gate view ----------------------------------------------------------------------------------------------------------

def _slide(p, f, i, n):
    name = p["traveller"]
    if p["kind"] and p["display"]:
        body = Img(src=f"/trip/passes/{p['id']}/display", alt=f"{name}'s boarding pass", cls="gp-img")
    elif p["kind"] == "pdf":
        body = A(icon("file", 28, 2.2), "Open the PDF", href=f"/trip/passes/{p['id']}/file", cls="tp-btn tp-btn-ink gp-pdf")
    else:
        body = P("No boarding pass file added yet. Show the details below.", cls="gp-none")
    line = f"{f['name']} · {f['origin']} → {f['dest']}" + (f" · Seat {p['seat']}" if p["seat"] else "")
    return Div(
        Div(Span(initials(name), cls=f"gp-av fill-{tint(i)}"), Span(name, cls="gp-name"), cls="gp-nm"),
        Span(line, cls="gp-line"),
        Div(body, cls="gp-pass"),
        Div(Div(Span("SEAT", cls="gp-k"), Span(p["seat"] or "–", cls="gp-v")), Div(Span("GROUP", cls="gp-k"), Span(p["grp"] or "–", cls="gp-v")), Div(Span("GATE", cls="gp-k"), Span(p["gate"] or "–", cls="gp-v")), cls="gp-big"),
        cls="gp-slide", id=f"gp-{p['id']}", data_pass=p["id"], data_name=name, role="group", aria_label=f"{name}, {i + 1} of {n}")


def gate_page(session, f, ps):
    n = len(ps)
    dots = [Button(type="button", aria_label=p["traveller"], aria_current="true" if i == 0 else "false", data_dot=str(i), cls="gp-dot") for i, p in enumerate(ps)]
    return (Title("GitAway · Boarding passes"),
            *styles(*HEAD),
            Div(Div(Span(icon("sun", 18, 2.4), "Brightness up", cls="gp-bright"), A(icon("x", 22, 2.6), href="/trip", cls="gp-close", id="gp-close", aria_label="Close"), cls="gp-top"),
                Div(*[_slide(p, f, i, n) for i, p in enumerate(ps)], cls="gp-track", id="gp-track", tabindex="0", aria_label="Boarding passes, swipe for the next person"),
                Div(Button(icon("chev-left", 22, 2.6), type="button", id="gp-prev", cls="gp-round", aria_label="Previous person"), Div(*dots, cls="gp-dots", id="gp-dots") if n > 1 else "",
                    Button(icon("chev-right", 22, 2.6), type="button", id="gp-next", cls="gp-round", aria_label="Next person"), cls="gp-pager", hidden=n < 2),
                Span(f"1 of {n} · swipe for the next person" if n > 1 else "", cls="gp-count", id="gp-count", aria_live="polite"),
                cls="gp", id="gp", data_count=str(n), data_screen="gate"),
            Script(src="/assets/js/passes.js", defer=True))


# ---- the routes -------------------------------------------------------------------------------------------------------------

class BodyLimit:
    """Refuse an oversized pass upload from its Content-Length, before a byte of the body is read or parsed."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"] == FORM:
            headers = dict(scope["headers"])
            if b"content-length" not in headers:
                await PlainTextResponse("Send the file with its length.", status_code=411)(scope, receive, send)
                return
            try:
                size = int(headers[b"content-length"] or 0)
            except ValueError:
                size = 0
            if size > passes.MAX_BYTES + 100_000:
                await PlainTextResponse(TOO_BIG.format(mb=passes.MAX_BYTES // (1024 * 1024)), status_code=413)(scope, receive, send)
                return
        await self.app(scope, receive, send)


_SLOT = None


def _slot():
    global _SLOT
    if _SLOT is None:
        _SLOT = asyncio.Semaphore(1)
    return _SLOT


def _signed_in(session):
    return ses.current_traveler(session) is not None


def _back(err="", anchor="hp-passes"):
    return RedirectResponse(("/trip/help" + (f"?err={err}" if err else "")) + f"#{anchor}", status_code=303)


def register(app):
    app.add_middleware(BodyLimit)

    @app.post("/trip/help/flight")
    def save_flight(session, trip: str = "", flight_id: str = "", airline: str = "", number: str = "", from_code: str = "", to_code: str = "", fly_on: str = "", time: str = "", terminal: str = ""):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        try:
            passes.save_flight(session, trip_id=trip, flight_id=flight_id, airline=airline, number=number, origin=from_code, dest=to_code, fly_on=fly_on, time=time, terminal=terminal)
        except passes.PassError as e:
            return _back(e.key)
        return _back()

    @app.post("/trip/help/flight/remove")
    def remove_flight(session, flight_id: str = ""):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        if not passes.remove_flight(session, flight_id):
            return _back("flight_missing")
        return _back()

    @app.post(FORM)
    async def save_pass(request, session):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        form = await request.form()
        f = form.get("file")
        data = None
        if f is not None and hasattr(f, "read") and getattr(f, "filename", ""):
            data = await f.read(passes.MAX_BYTES + 1)
        try:
            async with _slot():   # decoding, resizing and drawing a PDF are heavy: one at a time, and off the event loop
                await run_in_threadpool(lambda: passes.save_pass(
                    session, trip_id=form.get("trip") or "", pass_id=form.get("pass_id") or "", flight=form.get("flight") or "", traveller=form.get("traveller") or "", seat=form.get("seat") or "",
                    grp=form.get("grp") or "", gate=form.get("gate") or "", boards=form.get("boards") or "", app_url=form.get("app_url") or "", data=data or None))
        except passes.PassError as e:
            return _back(e.key)
        return _back()

    @app.post("/trip/help/pass/remove")
    def remove_pass(session, pass_id: str = ""):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        if not passes.remove_pass(session, pass_id):
            return _back("pass_missing")
        return _back()

    @app.get(GATE)
    def gate(request, session, flight: str = ""):
        if (r := phone.guard(session, f"{GATE}?flight={quote(flight, safe='')}")):
            return r
        f = next((x for x in passes.flights(session) if x["key"] == flight), None)
        if f is None:
            return RedirectResponse("/trip/help", status_code=303)
        ps = passes.listing(session).get(flight, [])
        if not ps:
            return RedirectResponse("/trip/help#hp-passes", status_code=303)
        return gate_page(session, f, ps)

    @app.get("/trip/passes/{pid}/{size}")
    def picture(request, session, pid: str, size: str):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        p = passes.get(session, pid)
        path = passes.file_path(p, size) if p else None
        if path is None:
            return Response("Not found.", status_code=404)
        headers = {"Cache-Control": "private, no-cache", "X-Content-Type-Options": "nosniff", "ETag": f'"{pid}-{size}-{path.stat().st_mtime_ns}"'}   # a removal must show at once: revalidate
        if size == "file":
            headers["Content-Disposition"] = 'inline; filename="boarding-pass.pdf"'
        if request.headers.get("if-none-match") == headers["ETag"]:
            return Response(status_code=304, headers=headers)
        return FileResponse(path, media_type=MIME[size], headers=headers)
