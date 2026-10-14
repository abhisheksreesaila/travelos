"""The desktop day's docked panel (F-140, frame A2 of docs/design/canvas/Web-Trip-v1.html; docs/trip-canvas.md "The docked panel").

`panel(v, day)` draws the right-hand column of the day on a laptop (CSS shows it from 1020px up; below that the day is as it was): an `<aside id="cz-dock" data-mode="idle">`
with a tab row (Plan, Family, Ask), a scrolling body `.cz-dock-body[data-pane]` and a fixed compose bar. The MODE is the one thing the later tickets change: `idle` (nothing
clicked: Up next, Later today, the Ask box) is this ticket; `plan` (F-141), `family` (F-143) and `ask` (F-142) swap the body and set `data-mode` and the selected tab.
Up next reads what Today reads (`pages.trip.load`: the day's timeline, the next item, the drive time when the family's map knows it); nothing is invented.
"""
from fasthtml.common import A, Aside, Button, Div, H2, H3, Nav, P, Span

from gitaway import access, geo, tripcal as cal, tripday as td
from gitaway.icons import icon

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


def tabs(day, active="plan"):
    def tab(key, label, ico, **kw):
        on = key == active
        return (Button if "href" not in kw else A)(icon(ico, 16, 2.4), Span(label), role="tab", aria_selected="true" if on else "false", cls=f"cz-dock-tab{' is-on' if on else ''}", data_tab=key, **({"type": "button"} if "href" not in kw else {}), **kw)
    return Nav(tab("plan", "Plan", "calendar"), tab("family", "Family", "chat", href="/trip/family"), tab("ask", "Ask", "mic", href=f"/trip/ask?day={day}"), cls="cz-dock-tabs", role="tablist", aria_label="Panel")


def panel(v, day):
    compose = A(Span("Type to Ask", cls="cz-compose-t"), Span(icon("arrow-right", 16, 2.6), cls="cz-compose-go"), href=f"/trip/ask?day={day}", cls="cz-compose", id="cz-dock-compose") \
        if access.can_edit(v["role"]) else ""
    return Aside(tabs(day), Div(*idle(v, day), cls="cz-dock-body", data_pane="idle"), compose, cls="cz-dock", id="cz-dock", data_mode="idle", data_day=str(day), aria_label="The day's panel")
