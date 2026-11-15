"""Planning v2 (F-252, D-630..): the trip's calendar, with what is booked placed on it, quick add, drag and resize, a help rail and planning together. Design: docs/design/planning-v2/index.html
(booking v2's language: the sky, the frosted rail, Newsreader and Inter); the model is gitaway/planv2.py, the writes are gitaway/planedit.py (the calendar's own rules and the family's cards).

GET  /trip/plan               the page for the open trip (signed in, with a booking; else the same redirects as the cockpit). `?arrive=1` (the booking's "Plan this trip") plays the arrival: the header
                              rises and the bookings land in the calendar
GET  /trip/plan/cal           the calendar as an HTML fragment for `view` (week | day), `frm` (the first day of the week's window), `cols` (how many days fit) and `day`; the page's script swaps it in
                              (a refresh on return to the tab, a change of view). The server clamps all four and says what it drew in `data-state`
POST /trip/plan/write         one change of the plan: `op` add (day, start, end, title, kind), edit (act, start, end, day, title, kind), delete (act) or undo (the snapshot an earlier answer gave).
                              JSON {toast, undo, plan, grid}; a refusal is 422 {error} in the calendar's own words. Editors only (gitaway.access gates every write)
POST /trip/plan/suggest       the rail's "+": put a suggestion in a free slot that avoids a forecast of rain (planv2.pick_slot); JSON as above plus {landed: "Wed 16 · 12:00 PM"}
GET  /trip/plan/together      the drawer's top (who is in, the waiting invites, what changed) as an HTML fragment, read again each time the drawer opens
GET  /trip/plan/thread?key=   a chat of the trip as JSON {threads, items, last}: "trip" or a plan's id (the existing chats: gitaway/familychats.py); opening it marks it read. Messages are written through the
                              existing POST /trip/family/message and POST /trip/talk/message, open to every member
"""

import json

from fasthtml.common import A, Aside, B, Button, Div, H1, H2, Header, Input, Li, Link, NotStr, P, Script, Section, Small, Span, Ul, to_xml
from starlette.responses import HTMLResponse, JSONResponse

from gitaway import access, placeart, familychats, familythread, interests, members, phone, plantalk, planedit, planv2 as pv, session as ses, showcase, tripcal as cal
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import tripcanvas, tripshare

PATH = "/trip/plan"
HEAD = (Link(rel="stylesheet", href="/assets/css/v2plan.css"), *tripshare.HEAD, Script(src="/assets/js/v2plan.js", defer=True), *[Script(src=s, defer=True) for s in tripshare.SCRIPTS])
WX_ICON = {"sun": "sun", "cloud": "cloud", "rain": "rain", "snow": "snow", "wind": "wind"}
COLS = 7


def _json(data, status=200):
    return JSONResponse(data, status_code=status, headers={"Cache-Control": "no-store"})


def curl(day=0, booked=""):
    return tripcanvas.curl(day=day, booked=booked)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# ---- the calendar ------------------------------------------------------------------------------------------------------------------

def _wx(w, brief=False):
    """A day's sky in its header: the icon and the temperatures; a typical day is dotted and says so (its title, and the caption under the header)."""
    if not w.cond:
        return ""
    cls = "wxl" + (" typ" if w.typical else "") + (" rain" if w.cond in pv.WET else " sun" if w.cond == "sun" else "")
    temps = [Span(f"{w.hi}°", cls="num"), Span(f"/{w.lo}°", cls="num lo")] if w.hi is not None else []
    return Span(icon(WX_ICON.get(w.cond, "cloud"), 20, 2), *temps, cls=cls, title=f"{w.word}. {w.label}".strip(". "))


def _caption(v):
    """One line under the header saying what the weather is: a forecast, typical weather, a mix, or the sample's own."""
    days = [w for w in v.sky if w.cond]
    if not days:
        return ""
    if all(w.sample for w in days):
        return "Sample weather"
    typical = [w for w in days if w.typical]
    if len(typical) == len(days):
        return "Typical weather for the time of year, not a forecast yet."
    if typical:
        return "Forecast first, then typical weather (dotted), not a forecast yet."
    return "Forecast from MET Norway."


def _ev(e, lane, across, can_edit, gs, i=0):
    """One block. A booking is a link to its booking (locked); a plan is a button that opens its editor, can be dragged and resized."""
    dur = e.end - e.start
    cls = f"ev k-{e.kind}" + (" lock" if e.locked else "") + (" short" if dur <= 35 else "") + (" narrow" if across > 1 else "")
    style = f"--s:{e.start - gs};--d:{dur};--lane:{lane};--lanes:{across};--i:{i}"
    body = [B(e.title), Span(e.when, cls="tm")]
    if e.by and not e.locked:
        body.append(Span(e.by, cls="by"))
    if e.locked:
        body.append(icon("lock", 14, 2.4, cls="lk"))
        return A(*body, href=e.href, cls=cls, style=style, data_id=e.id, data_locked="1", aria_label=f"{e.title}, {e.when}. Booked: opens the booking")
    body.append(Span(cls="rz", data_rz="1", aria_hidden="true"))
    return Div(*body, cls=cls, style=style, data_id=e.id, data_start=str(e.start), data_end=str(e.end), data_kind=e.kind, data_title=e.title, role="button", tabindex="0",
               aria_label=f"{e.title}, {e.when}. Tap to change" + (" or drag to move" if can_edit else ""))


def _column(v, i, can_edit, gs, wide):
    lo, hi = v.windows[i]
    day_ev = v.on(i)
    shown, more = pv.lanes(day_ev)
    off = []
    if lo > gs:
        off.append(Div(cls="offwin", style=f"--s:{0};--d:{lo - gs}"))
    if hi < v.ge:
        off.append(Div(cls="offwin", style=f"--s:{hi - gs};--d:{v.ge - hi}"))
    evs = [_ev(e, lane, across, can_edit, gs, k) for k, (e, lane, across) in enumerate(shown)]      # an event's top is measured from the grid's first minute
    chips = [Button(f"+{len(hid)}", cls="more", style=f"--s:{start - gs}", data_more=",".join(e.id for e in hid), aria_label=f"{len(hid)} more at the same time",
                    aria_haspopup="dialog") for start, hid in more]
    return Div(*off, *evs, *chips, cls="col" + (" wet" if v.sky[i].wet else ""), data_day=str(i), style="")


def _stayband(v, frm, cols, n):
    stays = [e for e in v.booked if e.kind == "stay"]
    if not stays:
        return ""
    a, b = min(e.day for e in stays), max(e.day for e in stays)
    first = next(e for e in sorted(stays, key=lambda e: (e.day, e.start)))
    name = first.title.removeprefix("Check in · ").split(" · ")[0]
    lo, hi = max(a, frm), min(b, frm + n - 1)
    if lo > hi:
        return ""
    d = lambda k: dict(v.days)[k]       # noqa: E731
    k = b - a
    text = f"{name} · {k} night{'s' if k != 1 else ''} · check in {d(a).strftime('%a')}, out {d(b).strftime('%a')}"
    return Div(icon("bed", 16, 2.2), Span(text), cls="stayband", style=f"grid-column:{lo - frm + 2} / {hi - frm + 3}")


def _fmt_h(m):
    h = m // 60
    return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"


def _title(days, view):
    a, z = days[0], days[-1]
    if view == "day":
        return a.strftime("%A, %b ") + str(a.day), ""
    month = a.strftime("%B")
    end = str(z.day) if (a.year, a.month) == (z.year, z.month) else f"{z.strftime('%B')} {z.day}"
    return f"{month} {a.day} to {end}", f"{len(days)} days"


def calendar(v, view="week", frm=0, cols=COLS, day=0, role="viewer"):
    """The calendar's whole inside (the bar of controls, the day chips, the header, the grid) for one state. -> (the elements, the state the server drew)."""
    n = len(v.days)
    view = view if view in ("week", "day") else "week"
    cols = _clamp(_int(cols, COLS), 3, COLS)
    frm = _clamp(_int(frm), 0, max(0, n - cols))
    day = _clamp(_int(day), 0, n - 1)
    shown = [day] if view == "day" else list(range(frm, min(n, frm + cols)))
    can_edit = access.can_edit(role)
    dates = dict(v.days)
    title, sub = _title([dates[i] for i in shown], view)
    gs, ge = v.gs, v.ge
    hours = (ge - gs) // 60
    first = shown[0]
    stay = _stayband(v, first, len(shown), n)
    prev_ok, next_ok = (day > 0, day < n - 1) if view == "day" else (frm > 0, frm + cols < n)
    nav = Span(Button(icon("chev-left", 18, 2.6), type="button", cls="v2-round pl-nav", data_nav="-1", disabled=not prev_ok, aria_label="Earlier" if view == "week" else "Previous day"),
               Button(icon("chev-right", 18, 2.6), type="button", cls="v2-round pl-nav", data_nav="1", disabled=not next_ok, aria_label="Later" if view == "week" else "Next day"),
               cls="nav2") if (view == "day" or n > cols) else ""
    top = Div(Div(Button("Week", type="button", data_view="week", aria_pressed=str(view == "week").lower()), Button("Day", type="button", data_view="day", aria_pressed=str(view == "day").lower()),
                  cls="seg", role="group", aria_label="Calendar view"),
              nav, Span(title, Small_(sub), cls="cal-title", aria_live="polite"),
              Div(*[Span(Span(cls=f"sw k-{k}"), lab, cls="lg") for k, lab in pv.LEGEND if k in {e.kind for e in v.events}], cls="legend"),
              Button(icon("plus", 18, 2.8), "Add", type="button", cls="addbtn", data_add="1", disabled=not can_edit) if can_edit else "", cls="cal-top")
    chips = Div(*[Button(Span(_wx(v.sky[i]) or "", cls="w"), B(f"{dates[i].strftime('%a')}"), Span(f"{dates[i].strftime('%b')} {dates[i].day}", cls="num"), type="button", cls="dchip", data_day=str(i),
                         aria_pressed=str(i == day).lower()) for i in range(n)], cls="chipsrow", role="group", aria_label="Pick a day") if view == "day" else ""
    head = Div(Span(), *[Button(Span(dates[i].strftime("%a"), cls="dw"), Span(str(dates[i].day), cls="dn"), _wx(v.sky[i]) or Span(),
                                Span(icon("rain", 15, 2.2), "Rain likely", cls="note") if v.sky[i].wet else "",
                                type="button", cls="dh" + (" wet" if v.sky[i].wet else ""), data_day=str(i), aria_label=f"{dates[i].strftime('%A, %b')} {dates[i].day}: open the day") for i in shown],
               cls="g-head")
    allday = Div(Span(icon("bed", 16, 2.2), Span("Stay", cls="lblt"), cls="lbl"), stay, cls="g-all") if stay else ""
    gut = Div(*[Span(_fmt_h(gs + k * 60), style=f"--k:{k}") for k in range(hours)], cls="gut")
    body = Div(Div(gut, *[_column(v, i, can_edit, gs, view == "day") for i in shown], cls="g-inner", style=f"--hours:{hours};--n:{len(shown)};--gs:{gs}", data_gs=str(gs)), cls="g-body")
    cap = _caption(v)
    grid = Div(head, allday, body, cls="grid", data_state=f"{view}|{frm}|{cols}|{day}", style=f"--n:{len(shown)}")
    summary = {"plans": [{"day": e.day, "kind": e.kind} for e in v.plans], "titles": [e.title for e in v.plans], "booked": len(v.booked), "days": n, "people": len(v.people)}
    return [top, chips, P(cap, cls="wx-cap") if cap else "", grid, Script(NotStr(_safe(summary)), type="application/json", cls="pl-sum")], (view, frm, cols, day)


def Small_(text):
    return Small(text) if text else ""


def _safe(obj) -> str:
    """JSON that can sit inside <script type="application/json">: no less-than, greater-than or ampersand can end the script or open a comment."""
    return json.dumps(obj, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _fragment(session, request, view, frm, cols, day):
    v = pv.view(session, curl)
    els, _ = calendar(v, view, frm, cols, day, access.request_role())
    return to_xml(Div(*els, cls="pl-cal-in"))


# ---- the arrival header ------------------------------------------------------------------------------------------------------------

def _avatar(p, big=False):
    return Span(p.initials, cls="av" + (" big" if big else ""), style=f"--c:var(--k-{('flight', 'stay', 'food', 'see', 'tix')[p.slot]})", title=p.name)


def _trip_card(v, role):
    names = ", ".join(p.name.split()[0] for p in v.people[:6])
    art = Div(NotStr(_art(v.place)), cls="art") if _art(v.place) else ""
    return Section(Div(cls="deco", aria_hidden="true"), art,
                   Div(Span(Span(icon("check", 11, 3.4), cls="chk"), "Booked · planning together", cls="k"), H1(v.title, cls="disp"), P(f"{v.dates} · {v.nights} night{'s' if v.nights != 1 else ''}", cls="meta"), cls="ti"),
                   Div(Span(*[_avatar(p) for p in v.people], cls="stack"), Small_(names), cls="who") if v.people else "",
                   Div(B(v.big, cls="num") if v.big else "", Span(v.small), cls="count" + ("" if v.big else " is-text")),
                   tripshare.open_button(role) or "", cls="pl-trip rise", aria_label="Your trip")


def _art(place):
    art = placeart.art(place)
    return str(art) if art else ""


# ---- the rail ------------------------------------------------------------------------------------------------------------------------

def _wg(title, ic, k, *body, sample=False, i=0):
    return Section(Header(Span(icon(ic, 17, 2.2), cls="ic", style=f"--k:var(--{k})"), Span(title, cls="wg-h"), Span("Sample", cls="smp") if sample else ""), *body, cls="wg v2-glass", style=f"--i:{i}")


def _weather_widget(v, i):
    days = [(k, d) for k, d in v.days if v.sky[k].cond][:7]
    if not days:
        return ""
    sample = all(v.sky[k].sample for k, _ in days)
    strip = Div(*[Button(Span(d.strftime("%a")), icon(WX_ICON.get(v.sky[k].cond, "cloud"), 24, 2), Span(f"{v.sky[k].hi}°", cls="num"), Span(f"{v.sky[k].lo}°", cls="num lo"), type="button",
                         cls="d5" + (" wet" if v.sky[k].wet else "") + (" typ" if v.sky[k].typical else ""), data_day=str(k), title=f"{v.sky[k].word}. {v.sky[k].label}".strip(". "))
                  for k, d in days], cls="days5")
    out = [strip]
    hit = pv.rain(v)
    if hit:
        k, w = hit
        d = dict(v.days)[k]
        out.append(Div(Span(icon("rain", 20, 2.2), cls="ni"), B(f"{w.word.rstrip('.')} on {d.strftime('%A')}"), Span("Take an umbrella, and keep something indoors for that day."),
                       Button("Show me " + d.strftime("%A"), type="button", cls="link-btn", data_show=str(k)), cls="nudge"))
    out.append(P(_caption(v), cls="fine"))
    out += [Span(t, cls="fine") if not h else A(t, href=h, rel="noopener", cls="fine") for t, h in v.sky_notes if not t.startswith("Typical ")]
    return _wg("Weather", "sun", "wx", *out, sample=sample, i=i)


def _fit_row(s):
    return Li(Span(icon("food", 22, 2), cls="art"), Div(B(s["title"]), Span(s["sub"], cls="sub"), cls="t"),
              Button(icon("plus", 18, 2.8), type="button", cls="plus", data_sug=s["id"], aria_label=f"Add {s['title']} to the plan"))


def _fits_widget(v, sugg, i):
    rows = pv.fits(v, sugg)
    if not rows:
        return ""
    labels = {k: lab for k, lab, *_ in interests.LIST}
    said = " and ".join(labels[k].lower() for k in v.interests[:3]) if v.interests else ""
    return _wg("Fits you", "food", "food", P(f"{said.capitalize()}, near where you stay." if said else f"Near where you stay, in {v.place}."), Ul(*[_fit_row(s) for s in rows], cls="fits"), sample=True, i=i)


def _went_widget(v, sugg, i):
    rows = [s for s in sugg if s["kind"] != "food"]
    if not rows:
        return ""
    return _wg("Others went", "star", "tix", Ul(*[Li(Span(icon("sight", 22, 2), cls="art"), Div(B(s["title"]), Span(s["sub"], cls="sub"), cls="t"),
                                                    Button(icon("plus", 18, 2.8), type="button", cls="plus", data_sug=s["id"], aria_label=f"Add {s['title']} to the plan")) for s in rows], cls="fits"), sample=True, i=i)


def _facts_widget(v, i):
    facts = pv.facts(v)
    if not facts:
        return ""
    return _wg(f"About {v.place}", "info", "flight", Ul(*[Li(P(f.text), A("Source", href=f.source, rel="noopener", cls="fine")) for f in facts[:2]], cls="facts"), i=i)


def _rail(v, sugg):
    ws = [_weather_widget(v, 0), _fits_widget(v, sugg, 1), _went_widget(v, sugg, 2), _facts_widget(v, 3)]
    ws = [w for w in ws if w != ""]
    return Div(Div(Span(icon("spark", 20, 2.2), cls="ic ai"), Div(B("Help for this trip", cls="disp"), Span("Tap + to drop it into a free slot")), cls="rail-head"),
               Div(*ws, cls="rail-row"), cls="rail-in") if ws else ""


# ---- planning together ------------------------------------------------------------------------------------------------------------------

def _together(v, request) -> list:
    """The drawer's top: who is in (with roles), an admin's waiting invites, and what changed. Drawn with the page and again each time the drawer opens (GET /trip/plan/together)."""
    people = [Div(_avatar(p, True), Div(B(p.name + (" (you)" if p.me else ""))), Span(members.ROLE_WORDS.get(p.role, p.role), cls="role"), cls="person") for p in v.people]
    invite = ""
    if v.role == "admin":
        base = str(request.base_url).rstrip("/")
        rows = [Div(Span(i["email"], cls="em"), Button("Copy link", type="button", cls="copy", data_copy=f"{base}/join/{i['token']}")) for i in v.pending]
        invite = Section(H2("Invite"), *rows, A("Invite someone", href="/family#invite", cls="v2-import"), cls="sd-sec")
    changes = Section(H2("What changed"), Ul(*[Li(Span(B(c.text)), Span(c.at, cls="tm")) for c in v.changes], cls="feed"), cls="sd-sec", id="pl-changes") if v.changes else ""
    return [Section(H2("Who is in"), Div(*people, cls="people"), cls="sd-sec"), invite, changes]


def _drawer(v, request):
    return Aside(Div(Div(Small_("Planning together"), B(v.title, cls="disp"), cls="t"), Button(icon("x", 16, 2.6), type="button", cls="v2-round pl-x", data_close="1", aria_label="Close"), cls="sd-head"),
                 Div(Div(*_together(v, request), id="pl-top", cls="sd-top"),
                     Section(H2("Talk"), Div(cls="threads", id="pl-threads", role="group", aria_label="Chats"), Div(cls="bubbles", id="pl-bubbles", role="log", aria_live="polite"),
                             Div(Input(type="text", id="pl-say", placeholder="Say something", aria_label="Say something", maxlength="500", autocomplete="off"),
                                 Button(icon("arrow-right", 18, 2.6), type="button", id="pl-send", cls="send", aria_label="Send"), cls="composer"), cls="sd-sec"),
                     cls="sd-body"), id="pl-side", cls="side v2-glass", role="dialog", aria_label="Planning together", hidden=True)


# ---- the page ----------------------------------------------------------------------------------------------------------------------------

def plan_page(session, request, arrive=False):
    role = access.request_role()
    v = pv.view(session, curl)
    sugg = pv.suggestions(v)
    unread = familychats.unread_total(session)
    els, state = calendar(v, "week", 0, COLS, v.open_day, role)
    data = {"days": [{"i": i, "label": f"{d.strftime('%a, %b')} {d.day}", "lo": v.windows[i][0], "hi": v.windows[i][1]} for i, d in v.days], "kinds": [list(k) for k in pv.PLAN_KINDS], "durs": pv.DURATIONS,
            "step": pv.STEP, "sugg": sugg, "edit": access.can_edit(role), "gs": v.gs, "ge": v.ge, "open": v.open_day, "inPlan": [e.title for e in v.plans], "showcase": showcase.on(),
            "plans": [{"id": e.id, "title": e.title, "day": e.day, "start": e.start, "end": e.end, "when": e.when, "kind": e.kind} for e in v.plans],
            "booked": [{"id": e.id, "title": e.title, "day": e.day, "start": e.start, "end": e.end, "when": e.when, "kind": e.kind, "href": e.href} for e in v.booked],
            "summary": {"plans": len(v.plans), "booked": len(v.booked), "people": len(v.people), "title": v.title, "dates": v.dates}}
    bar = Div(Span(Span(cls="dot"), "Booked", Span("·", aria_hidden="true"), "now planning", cls="crumb"), Span(cls="sp"),
              Button(Span(*[_avatar(p) for p in v.people[:3]], cls="stack"), Span("Plan together"), Span(str(unread), cls="badge", id="pl-badge", hidden=not unread), type="button", cls="together", id="pl-together", aria_haspopup="dialog"),
              Button(icon("check", 19, 2.8), Span("Save plan"), type="button", cls="save", id="pl-save"), cls="pl-bar")
    body = Div(bar, _trip_card(v, role),
               Div(Section(*els, cls="pl-cal", id="pl-cal", data_view=state[0], aria_label="Trip calendar"), Aside(_rail(v, sugg), cls="rail", id="pl-rail", aria_label="Help for this trip"), cls="pl-app"),
               Div(Button(Span(*[_avatar(p) for p in v.people[:3]], cls="stack"), "Together", type="button", cls="together", data_together="1"),
                   Button(icon("check", 19, 2.8), Span("Save plan"), type="button", cls="save", data_save="1"), cls="dock v2-glass", id="pl-dock"),
               _drawer(v, request), Div(cls="pl-scrim", id="pl-scrim"), Div(id="pl-pop", cls="pop", role="dialog", hidden=True),
               Div(id="pl-sheet", cls="sheet", role="dialog", aria_modal="true", aria_label="Plan saved", hidden=True),
               Script(NotStr(_safe(data)), type="application/json", id="pl-data"),
               *[NotStr(f'<template id="pl-ico-{n}">{icon(n, 18, 2.6)}</template>') for n in ("x", "minus", "plus", "check", "share")],
               cls="pl" + (" is-arrive" if arrive else ""), data_pl="1")
    return page("Plan the trip", body, current="trip", head=HEAD, noindex=True, footer=False, v2=True)


def register(app):
    @app.get(PATH)
    def plan(session, request, arrive: str = ""):
        if (r := phone.guard(session, PATH)):
            return r
        return plan_page(session, request, arrive == "1")

    @app.get(f"{PATH}/cal")
    def plan_cal(session, request, view: str = "week", frm: str = "0", cols: str = "7", day: str = "0"):
        if (r := phone.guard(session, PATH)):
            return r
        return HTMLResponse(_fragment(session, request, view, frm, cols, day), headers={"Cache-Control": "no-store"})

    @app.get(f"{PATH}/together")
    def together(session, request):
        if (r := phone.guard(session, PATH)):
            return r
        return HTMLResponse(to_xml(Div(*_together(pv.view(session, curl), request))), headers={"Cache-Control": "no-store"})

    @app.post(f"{PATH}/write")
    async def write(session, request):
        if (r := phone.guard(session, PATH)):
            return r
        form = await request.form()
        try:
            got = write_op(session, str(form.get("op") or "")[:8], form)
        except cal.CalendarError as e:
            return _json({"error": str(e)}, 422)
        return _json({**got, "grid": _fragment(session, request, form.get("view") or "week", form.get("frm"), form.get("cols"), form.get("vday"))})

    @app.post(f"{PATH}/suggest")
    async def suggest(session, request):
        if (r := phone.guard(session, PATH)):
            return r
        form = await request.form()
        v = pv.view(session, curl)
        s = next((x for x in pv.suggestions(v) if x["id"] == str(form.get("id") or "")), None)
        if s is None:
            return _json({"error": "That suggestion is not here any more."}, 422)
        slot = pv.pick_slot(v, s["kind"], s["minutes"], s["indoor"])
        if slot is None:
            return _json({"error": "There is no free time left that fits that."}, 409)
        day, start = slot
        try:
            got = planedit.add(session, day=day, start=start, end=start + s["minutes"], title=s["title"], kind=s["kind"])
        except cal.CalendarError as e:
            return _json({"error": str(e)}, 422)
        a = got["act"]
        when = f"{dict(v.days)[a.day].strftime('%a')} {dict(v.days)[a.day].day} · {cal.fmt_time(a.start)}"
        return _json({"toast": f"{a.title} added, {when}", "undo": got["undo"], "plan": plan_of(a), "landed": when,
                      "grid": _fragment(session, request, form.get("view") or "week", form.get("frm"), form.get("cols"), form.get("vday"))})

    @app.get(f"{PATH}/thread")
    def thread(session, key: str = "trip"):
        if (r := phone.guard(session, PATH)):
            return r
        act, part = familychats.split(key)
        chats = familychats.threads(session, key)
        its = familythread.items(session, scope="trip") if not act else plantalk.items(session, act, part)
        its = [i for i in its if i["kind"] in ("message", "photo", "voice")]
        me = (ses.current_traveler(session) or None)
        mine = me.id if me else ""
        last = its[-1]["n"] if its else 0
        if last:
            familychats.mark_read(session, familychats.key_of(act, part), last)
        return _json({"threads": [{"key": c["key"], "title": c["title"], "unread": c["unread"], "n": c["n"]} for c in chats], "key": key,
                      "items": [{"n": i["n"], "name": (i["name"] or "").split(" ")[0], "mine": i["author"] == mine, "kind": i["kind"], "text": i["text"] or {"photo": "Sent a photo", "voice": "Sent a voice note"}.get(i["kind"], "")}
                                for i in its], "last": last})


def plan_of(a) -> dict:
    return {"act": a.id, "day": a.day, "start": a.start, "end": a.end, "title": a.title, "kind": a.kind}


def write_op(session, op, form):
    """One write of the calendar -> {toast, undo, plan}. The calendar's own rules judge it (planedit); a refusal is a CalendarError in its words."""
    def minutes(name):
        raw = str(form.get(name) or "").strip()
        if not raw.isdigit() or len(raw) > 4:
            raise cal.CalendarError("That time is not one we can read.")
        return int(raw)

    act = str(form.get("act") or "")[:20]
    if op == "add":
        got = planedit.add(session, day=str(form.get("day") or "")[:3], start=minutes("start"), end=minutes("end"), title=str(form.get("title") or "")[:200], kind=str(form.get("kind") or "fun")[:12])
        a = got["act"]
        return {"toast": f"{a.title} added", "undo": got["undo"], "plan": plan_of(a)}
    if op == "delete":
        gone = planedit.delete(session, act)
        return {"toast": f"{gone['title']} removed", "undo": {"deleted": act}}
    if op == "undo":
        try:
            snap = json.loads(str(form.get("undo") or "null")[:2000])
        except ValueError:
            snap = None
        if isinstance(snap, dict) and snap.get("added"):
            gone = planedit.unadd(session, snap)
            return {"toast": f"{gone.title} removed"}
        if isinstance(snap, dict) and snap.get("deleted"):
            a = planedit.undelete(session, str(snap["deleted"])[:20])
            return {"toast": f"{a.title} is back", "plan": plan_of(a)}
        a = planedit.restore(session, snap)
        return {"toast": "Put back", "plan": plan_of(a)}
    if op != "edit":
        raise cal.CalendarError("That did not work.")
    got = planedit.change(session, act, start=minutes("start") if form.get("start") else None, end=minutes("end") if form.get("end") else None,
                          title=str(form["title"])[:200] if form.get("title") is not None else None, day=str(form.get("day") or "")[:4] or None, kind=str(form.get("kind") or "")[:12] or None)
    a = got["act"]
    return {"toast": f"{a.title} saved" if got["changed"] else "", "undo": got["undo"] if got["changed"] else None, "plan": plan_of(a)}
