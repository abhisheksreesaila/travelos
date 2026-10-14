"""The desktop day's docked panel (F-140, frame A2 of docs/design/canvas/Web-Trip-v1.html; docs/trip-canvas.md "The docked panel").

`panel(v, day)` draws the right-hand column of the day on a laptop (CSS shows it from 1020px up; below that the day is as it was): an `<aside id="cz-dock" data-mode="idle">`
with a tab row (Plan, Family, Ask), a scrolling body `.cz-dock-body[data-pane]` and a fixed compose bar. The MODE is the one thing the later tickets change: `idle` (nothing
clicked: Up next, Later today, the Ask box) is this ticket; `plan` (F-141), `family` (F-143) and `ask` (F-142) swap the body and set `data-mode` and the selected tab.
Up next reads what Today reads (`pages.trip.load`: the day's timeline, the next item, the drive time when the family's map knows it); nothing is invented.
"""

from fasthtml.common import A, Aside, Button, Div, Form, H2, H3, Header, Input, Nav, Option, P, Section, Select, Span

from gitaway import access, familythread, geo, plantalk, session as ses, tripcal as cal, tripday as td
from gitaway.icons import icon
from gitaway.layout import trip_field
from gitaway.pages import tab_family

LATER_MAX = 6


def _pick(tv, day):
    """(kicker, the item that is up next or "" , the items after it). On today: what Today's dark card shows; on another day of the trip: its first item; a day that is over: nothing."""
    items = [x for x in tv["items"] if x.kind not in ("ride", "offer")]
    today = tv["today_idx"]
    if today == day:
        up = tv["up"]
        item = up.item if up else None
        return (up.kicker if item else ""), item, [x for x in items if x.state in ("next", "later") and x is not item]
    if tv["phase"] == "after" or (today is not None and day < today):
        return "", None, []
    return ("FIRST UP", items[0], items[1:]) if items else ("", None, [])


def _who(v, item):
    """Who is going: the faces of the plan's steps when it has parts and steps, else who added it; a booking says nothing."""
    from gitaway.pages import tripcanvas as tc       # tripcanvas draws this panel: a late import keeps the two from importing each other at load
    if item.id in v["plan"]:
        faces = tc.faces_of(tc._all_steps(v["plan"][item.id]))
        if faces:
            return faces
    if item.kind == "plan" and item.by:
        return Span(f"Added by {v['who'].name if item.by == 'you' else item.by}", cls="cz-up-who")
    return ""


def _open_plan(v, day, item):
    """"Open the plan": a plan with steps zooms to its block, a booking opens its sheet, any other plan opens its card on the grid (day_dock.js clicks its block)."""
    from gitaway.pages import tripcanvas as tc
    if item.id in v["plan"]:
        return A("Open the plan", href=tc.curl(block=item.id), cls="cz-dock-btn is-white", data_zoom="in", id="cz-up-open")
    if item.kind in ("flight", "hotel", "car"):
        return A("Open the plan", href=tc.curl(day=day, booked=item.id), cls="cz-dock-btn is-white", data_zoom="in", id="cz-up-open")
    return A("Open the plan", href=tc.curl(day=day), cls="cz-dock-btn is-white", data_dock_open=item.id, id="cz-up-open")


def up_card(v, tv, day, kicker, item):
    from gitaway.pages import trip as trippage
    drive = None
    if kicker.startswith(("UP NEXT", "FIRST UP")) and (got := trippage.leave_info(tv, item)):
        drive = got[1]
    parts = [Span(td.span_label(item.start, item.end), cls="cz-up-time")]
    if drive:
        parts.append(Span(f"{drive} min drive", cls="cz-up-drive"))
    if (who := _who(v, item)):
        parts.append(who)
    buttons = []
    if item.place:
        buttons.append(A(icon("nav", 16, 2.4), "Directions", href=td.maps_url(item.place, v.get("ua", "")), target="_blank", rel="noopener", cls="cz-dock-btn is-coral", id="cz-up-directions"))
    buttons.append(_open_plan(v, day, item))
    return Div(Span(kicker, cls="cz-up-k"), H2(item.title, cls="cz-up-title"), Div(*parts, cls="cz-up-meta"), Div(*buttons, cls="cz-up-acts"), cls="cz-up", id="cz-up", data_item=item.id)


def later_rows(day, today, rest):
    if not rest:
        return ""
    rows = [Div(Span(cal.fmt_time(x.start), cls="cz-later-time"), Span(x.title, cls="cz-later-t"), Span(x.label, cls="cz-later-tag"), cls="cz-later-row") for x in rest[:LATER_MAX]]
    return Div(H3("Later today" if day == today else "Later on", cls="cz-dock-k"), *rows, cls="cz-later", id="cz-later")


def ask_box(day):
    """The Ask box of the idle panel: a link into the existing Ask (F-142 puts the whole box here). Editors only (a viewer cannot change the plan)."""
    talk = f"/trip/ask?day={day}&mode=talk"
    return Div(H3("Ask or change something", cls="cz-dock-k"),
               Div(P("“Move lunch to 1:30”", cls="cz-ask-eg"), P("“Where can we eat near the hotel?”", cls="cz-ask-eg"),
                   A(icon("mic", 20, 2.4), Span("Say it", cls="sr-only"), href=talk, cls="cz-ask-mic", id="cz-dock-mic"), cls="cz-ask-card"), cls="cz-dock-ask", id="cz-dock-ask")


def idle(v, day):
    from gitaway.pages import trip as trippage
    with geo.cache_scope(v["session"]):        # the drive time reads the family's map cache (gitaway.geo), as on Today
        tv = trippage.load(v["session"], str(day), v.get("ua", ""))
        kicker, item, rest = _pick(tv, day)
        card = up_card(v, tv, day, kicker, item) if item else Div(Span("UP NEXT", cls="cz-up-k"), H2("Nothing up next", cls="cz-up-title"),
                                                                    P("Nothing else is planned for this day." if tv["phase"] != "after" else "The trip is over.", cls="cz-up-meta"), cls="cz-up is-empty", id="cz-up")
        later = later_rows(day, v["today_idx"], rest)
    return [card, later, ask_box(day) if access.can_edit(v["role"]) else ""]


def tabs(day, active="plan", unread=0):
    """`unread`: how many messages in the trip's chats this person has not read, shown on the Family tab (F-143)."""
    from gitaway.pages import familydock, tripcanvas as tc

    def tab(key, label, ico, *more, **kw):
        on = key == active
        return (Button if "href" not in kw else A)(icon(ico, 16, 2.4), Span(label), *more, role="tab", aria_selected="true" if on else "false", cls=f"cz-dock-tab{' is-on' if on else ''}", data_tab=key, **({"type": "button"} if "href" not in kw else {}), **kw)
    return Nav(tab("plan", "Plan", "calendar"), tab("family", "Family", "chat", familydock.unread_badge(unread), href=tc.curl(day=day, panel="family")), tab("ask", "Ask", "mic", href=f"/trip/ask?day={day}"), cls="cz-dock-tabs", role="tablist", aria_label="Panel")


KIND_ICON = {"fun": "star", "food": "food", "outdoors": "tree", "culture": "sight", "travel": "car"}


def plan_url(day, act):
    """The address that keeps a plan open in the panel (F-141): the day's own address and `plan=<id>`, so a reload shows it again."""
    from gitaway.pages import tripcanvas as tc
    return tc.curl(day=day, plan=act)      # the one helper: F-145's week rows build the same address


def _hidden(name, value):
    return Input(type="hidden", name=name, value=value)


def _names(steps):
    seen = []
    for s in steps:
        for p in s["people"]:
            if p["name"] not in seen:
                seen.append(p["name"])
    return seen


def _who_line(v, a, steps):
    from gitaway.pages import tripcanvas as tc
    if steps and (faces := tc.faces_of(steps, 5)):
        names = _names(steps)
        return Div(faces, Span(", ".join(names[:4]) + (f" and {len(names) - 4} more" if len(names) > 4 else "") if names else "Everyone"), cls="cz-pp-who")
    by = a.by or (v["who"].name if v["who"] else "")
    return Div(Span(f"Added by {by}"), cls="cz-pp-who") if by else ""


def _step_meta(s):
    names = _names([s])
    return s["time"] or (", ".join(names[:2]) if names else "Everyone")


def _step_row(s, nxt, editor, aside=False):
    """One step as a tick row: the circle (a button for an editor; one click ticks it, canvas_tick.js), the title, its time or who on the right, and Set aside (or Put back) for an editor."""
    ring = Button(icon("check", 14, 3.2), type="button", cls="cz-ring", aria_label=f"{'Mark not done' if s['done'] else 'Mark done'}: {s['title']}", aria_pressed="true" if s["done"] else "false") \
        if editor else Span(icon("check", 14, 3.2), cls="cz-ring", role="img", aria_label="Done" if s["done"] else "Not done")
    aside_btn = ""
    if editor:
        do, label, ico = ("back", f"Put back: {s['title']}", "undo") if aside else ("aside", f"Set aside: {s['title']}", "x")
        aside_btn = Form(_hidden("step", s["id"]), _hidden("do", do), _hidden("next", nxt), trip_field(), Button(icon(ico, 14, 2.6), Span("Put back" if aside else "Set aside", cls="sr-only"), type="submit", cls="cz-pp-aside-btn", aria_label=label),
                         action="/trip/canvas/step", method="post", data_cz_form="", cls="cz-pp-aside-f")
    return Div(ring, Span(s["title"], cls="cz-ptx"), Span(_step_meta(s), cls="cz-pmeta"), aside_btn, cls=f"cz-pstep{' is-done' if s['done'] else ''}", data_step=s["id"])


def _steps(v, a, nxt, editor):
    from gitaway.pages import tripcanvas as tc
    blk = v["plan"][a.id]
    n, done = tc._counts(blk)
    parts = blk["parts"]
    rows = []
    for p in parts:
        if len(parts) > 1 and p["steps"]:
            rows.append(Span(p["name"], cls="cz-pp-part"))
        rows += [_step_row(s, nxt, editor) for s in p["steps"]]
    if not rows:
        rows = [P("No steps yet.", cls="cz-pp-none")]
    aside = blk["aside"]
    head = Div(H3(f"Steps · {done} of {n} done" if n else "Steps", cls="cz-pp-k"),
               Button(f"Set aside ({len(aside)})", type="button", cls="cz-pp-asidebtn", aria_expanded="false", aria_controls="cz-pp-aside", data_aside_toggle="", data_keep_state="") if aside else "", cls="cz-pp-sec")
    tray = Div(*[_step_row(s, nxt, editor, aside=True) for s in aside], cls="cz-pp-aside", id="cz-pp-aside", hidden=True, data_keep_state="") if aside else ""
    add = ""
    if editor and parts:
        pick = Select(*[Option(p["name"], value=p["id"]) for p in parts], name="part", aria_label="Which part of the day", cls="cz-pp-part-pick") if len(parts) > 1 else _hidden("part", parts[0]["id"])
        add = Div(Button(icon("plus", 16, 2.6), Span("Add a step"), type="button", cls="cz-pp-add", data_add_step="", aria_expanded="false", data_keep_state=""),
                  Form(_hidden("act", a.id), _hidden("who", "all"), _hidden("next", nxt), trip_field(),
                       Input(type="text", name="title", maxlength="80", placeholder="Churro break", aria_label="What is the step", autocomplete="off", cls="cz-pp-in", required=True), pick,
                       Button(icon("plus", 16, 2.6), Span("Add step"), type="submit", cls="cz-dock-btn is-coral cz-pp-go"),
                       P("", role="alert", cls="cz-error"), action="/trip/canvas/add", method="post", data_cz_form="", cls="cz-pp-addf", hidden=True, data_keep_state=""), cls="cz-pp-addwrap")
    return Div(head, Div(*rows, cls="cz-pp-steps"), add, tray, cls="cz-pp-steps-sec")


def plan_pane(v, a):
    """What the panel shows for a clicked plan (F-141, frame A1): its icon tile, eyebrow (day and time), title, the esc hint and close, who, the note slip (the phone card's own markup), the plan's
    steps when it has parts (tick, Add a step, Set aside), and the plan's chat. -> (the scrolling pane, the compose form at the panel's foot). Every role sees it; a viewer has no write controls."""
    from gitaway.pages import daycard, tripcanvas as tc
    session, editor = v["session"], access.can_edit(v["role"])
    d = v["dates"][a.day]
    park = tc.has_block(v, a.id)
    steps = tc._all_steps(v["plan"][a.id]) if park else []
    nxt = plan_url(a.day, a.id)
    tint = a.kind if a.kind in tc.KIND_TINT else "fun"
    head = Header(Span(icon(KIND_ICON.get(a.kind, "star"), 24, 2.2), cls=f"cz-pp-ic cz-k-{tint}", aria_hidden="true"),
                  Div(Div(f"Plan · {d.strftime('%a')} {tc.span_label(a.start, a.end)}", cls="cz-pp-eb"), H2(a.title, id="cz-pp-title", cls="cz-pp-t"), cls="cz-pp-ti"),
                  Span(Span("esc", cls="cz-pp-kbd", aria_hidden="true"), Button(icon("x", 18, 2.6), type="button", cls="cz-pp-close", aria_label="Close the plan", data_dock_close=""), cls="cz-pp-x"), cls="cz-pp-hd")
    link = daycard.plan_link(v, a)
    notes = daycard.notes_view(session, a.id, editor)
    chat_items = plantalk.items(session, a.id, "")
    me, zone = ses.current_traveler(session).id, ses.trip_zone(session)
    last = chat_items[-1]["n"] if chat_items else 0
    chat = Div(Div(H3("Chat on this plan", cls="cz-pp-k"), A("Open in Family", href=plantalk.url(a.id, "", ses.open_trip_id()), cls="cz-pp-open", id="cz-pp-family"), cls="cz-pp-sec"),
                   Div(*tab_family.fragment(chat_items, me, zone), cls="cz-pp-msgs ft-thread", id="cz-pp-msgs", data_last=str(last), role="log", aria_live="polite", aria_label=f"Chat: {a.title}"),
                   P("Nothing said here yet.", cls="cz-pp-none", id="cz-pp-quiet", hidden=bool(chat_items)), cls="cz-pp-chat")
    pane = Section(head, _who_line(v, a, steps), notes or "", link or "", _steps(v, a, nxt, editor) if park else "", chat,
                   cls="cz-dock-body cz-pp", data_pane="plan", data_act=a.id, aria_labelledby="cz-pp-title")
    foot = Form(_hidden("trip", ses.open_trip_id() or ""), _hidden("act", a.id), _hidden("part", ""), _hidden("since", str(last)),
                Input(type="text", name="text", maxlength=str(familythread.MAX_MESSAGE), placeholder="Message the family", aria_label=f"Message about {a.title}", autocomplete="off", cls="cz-pp-text", required=True),
                Button(icon("arrow-right", 16, 2.6), Span("Send", cls="sr-only"), type="submit", cls="cz-compose-go cz-pp-send"),
                P("", role="alert", cls="cz-error", id="cz-pp-err"), action="/trip/talk/message", method="post", cls="cz-pp-foot", data_pane="plan-foot")
    return pane, foot


def panel(v, day, plan="", family=None):
    """`plan`: the id of a plan on this day to open in the panel (the address's `plan=`); anything else leaves the panel idle. Both panes are always drawn so Esc can show Up next again.
    `family`: the key of a chat to open in the Family mode instead (the address's `panel=family&thread=`, F-143; gitaway/pages/familydock.py draws it); a plan wins."""
    from gitaway import familychats
    from gitaway.pages import familydock, tripcanvas as tc
    a = v["by_id"].get(plan) if plan else None
    a = a if a is not None and a.day == day else None
    fam = familydock.pane(v["session"], day, family) if family and not a else ()      # (drawing a chat reads it: the count below leaves it out)
    compose = A(Span("Type to Ask", cls="cz-compose-t"), Span(icon("arrow-right", 16, 2.6), cls="cz-compose-go"), href=f"/trip/ask?day={day}", cls="cz-compose", id="cz-dock-compose") \
        if access.can_edit(v["role"]) else ""
    mode = "plan" if a else "family" if fam else "idle"
    return Aside(tabs(day, mode if mode == "family" else "plan", familychats.unread_total(v["session"])), Div(*idle(v, day), cls="cz-dock-body", data_pane="idle"), *(plan_pane(v, a) if a else ()), *fam, compose,
                 cls="cz-dock", id="cz-dock", data_mode=mode, data_day=str(day), data_base=tc.curl(day=day), data_plan_url=tc.curl(day=day, plan="PLAN"), data_family_url=tc.curl(day=day, panel="family", thread="THREAD"),
                 data_dow=v["dates"][day].strftime("%a"), aria_label="The day's panel")
