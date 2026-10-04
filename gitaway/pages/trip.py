"""The phone-first trip home at /trip (F-054): Today, All days and Notes, with a + that adds a plan in two taps.

GET  /trip[?tab=today|days|notes][&day=<index>][&add=1][&new=<activity id>]   the page. Everything is drawn by the server; trip.js only
                                                                                 switches tabs and opens the add sheet without a reload.
POST /trip/plans                                                                 add a plan (title, start, kind) with the calendar's own validation
POST /trip/notes                                                                 add a trip note

Phones are sent here from a plain /calendar (gitaway.pages.calendar); anyone can open /trip, and "Open the full calendar" goes the
other way. It is the installed app's start page (the manifest's start_url). The data and the rules are the calendar's: gitaway.tripcal
validates, the roles come from gitaway.access (a viewer sees no + and no composer), and every form carries `trip`.
"""

from dataclasses import replace
import logging
from urllib.parse import urlencode

from fasthtml.common import NotStr, A, Button, Details, Div, Form, H1, H2, Header, Input, Label, Link, Main, Nav, P, Script, Section, Span, Summary, Title
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import access, catalog, geo, members, phone, tripgeo, pickers, session as ses, tripcal as cal, tripday as td
from gitaway.icons import icon
from gitaway.layout import avatar, join_note, trip_field
from gitaway.pages import calendar as calui, morning as morning_ui, passes as passes_ui, passkeys as passkeys_ui, rides as rides_ui

log = logging.getLogger(__name__)
HEAD = (*pickers.HEAD, *morning_ui.HEAD, *passkeys_ui.HEAD[:1], *passes_ui.HEAD)  # trip.css and phone.css come with the shell (gitaway.phone.HEAD)
TABS = (("today", "Today"), ("days", "All days"), ("notes", "Notes"))


def trip_url(**q):
    params = [(k, v) for k, v in q.items() if v not in ("", None)]
    return "/trip" + (f"?{urlencode(params)}" if params else "")


def _hidden(name, value):
    return Input(type="hidden", name=name, value=value)


def _day_name(d):
    return f"{d.strftime('%A')}, {d.strftime('%b')} {d.day}"


# ---- loading ------------------------------------------------------------------------------------------------------------

def load(session, day_arg="", ua=""):
    """Everything the page draws, read once. Call it before trip_field() (it opens the family, which resolves the trip)."""
    who, b = ses.current_traveler(session), ses.booking(session)
    t = cal.trip("", b)
    dates = cal.days(t)
    last = len(dates) - 1
    role = access.request_role()
    offers = cal.ride_offers(session, b, t) if role != "viewer" else []  # scheduling an Uber is a write
    acts, notes = cal.activities(session), cal.notes(session)
    zone = ses.trip_zone(session)
    plan = cal.plan_of(b) if cal.is_imported(b) else None
    here = td.clock_zone(plan, zone)  # where the traveler is now: before the arrival flight lands, the departure airport's zone
    blocks = cal.booked_blocks(b, t) + cal.ride_blocks(session, b, t)
    clocks = td.clocks_for([zone, here] + [td.block_zone(x, zone) for x in blocks], t.depart)
    ph, n = td.phase(t, catalog.today_in(here))
    today_idx = n if ph == "during" else None
    sel = int(day_arg) if day_arg.isdigit() and int(day_arg) <= last else (n if ph == "during" else 0 if ph == "before" else last)
    now = clocks[here][1] if sel == today_idx else None
    past = ph == "after" or (today_idx is not None and sel < today_idx)
    ctx = {"booking": b}
    ride_href = lambda blk: calui.ride_href(ctx, blk)  # noqa: E731
    detail_href = lambda blk: calui.cal_url("", view="days", detail=blk.id, trip=ses.open_trip_id())  # noqa: E731
    dest = t.destination_name

    family = members.family_people(session)
    added_name = lambda a: a.by or ("you" if not a.by_id or a.by_id == who.id else family.get(a.by_id, calui.FORMER).name)  # noqa: E731

    def items_of(day, now_=None, past_=False):
        return _with_extras(td.timeline(day, blocks, acts, offers, dest, added_name=added_name, hotel_place=td.hotel_place(b, dates, day), ride_href=ride_href, detail_href=detail_href, now=now_, past=past_, clocks=clocks, zone=zone), b, notes, session, who, family)

    items = items_of(sel, now, past)
    tomorrow = items_of(sel + 1) if sel < last else []
    up = td.up_next(items, now, tomorrow[0] if tomorrow else None, clocks) if now is not None else None
    return dict(zone=zone, session=session, who=who, b=b, t=t, dates=dates, last=last, role=role, blocks=blocks, acts=acts, notes=notes, phase=ph, n=n, today_idx=today_idx, sel=sel, now=now,
                items=items, up=up, clocks=clocks, stay_place=td.hotel_place(b, dates, sel), stay_before=td.hotel_place(b, dates, sel - 1) if sel else "", stay=td.stay_card(b, dates, sel), days=td.day_summaries(dates, blocks, acts, today_idx), ua=ua, past=past, first=items_of(0)[:1],
                crew=members.crew(session), next=cal.next_id(session))


def _with_extras(items, b, notes, session, who, family):
    """Each booked item with its confirmation number (shown behind a tap), each plan with the notes written on it."""
    people = {f.name.casefold(): f for f in ses.friends(session)}
    out = []
    for x in items:
        if x.kind in ("flight", "hotel", "car"):
            detail = cal.booking_detail(b, x.id)
            conf = next((v for k, v in detail[1] if k == "Confirmation"), "") if detail else ""
            x = replace(x, confirm=conf)
        elif x.kind == "plan":
            x = replace(x, notes=tuple(f"{calui.note_writer(n, who, people, family)[0]}: {n.text}" for n in notes if n.act == x.id))
        out.append(x)
    return out


# ---- pieces -------------------------------------------------------------------------------------------------------------

def _icon(item, size=22):
    return icon(item.icon or "pin", size, 2.2)


def up_card(v):
    up, ph, t = v["up"], v["phase"], v["t"]
    if ph == "before" and v["sel"] == 0:
        first = v["first"][0] if v["first"] else None
        return Div(Span(td.starts_in(v["n"]).upper(), cls="tp-kicker"), Span(_day_name(v["dates"][0]), cls="tp-up-title"),
                   Span(f"First up: {first.title} at {cal.fmt_time(first.start)}" if first else "Day 1 is wide open. Add something fun!", cls="tp-up-sub"), cls="tp-up", id="tp-up")
    if ph == "after":
        plans = len(v["acts"])
        return Div(Span("WELCOME HOME", cls="tp-kicker"), Span(f"{len(v['dates'])} days in {t.place}", cls="tp-up-title"),
                   Span(f"{plans} plan{'s' if plans != 1 else ''} · {len(v['notes'])} note{'s' if len(v['notes']) != 1 else ''}", cls="tp-up-sub"),
                   A("See all days", href=trip_url(tab="days"), data_tab_link="days", cls="tp-btn tp-btn-white"), cls="tp-up", id="tp-up")
    if not up:
        return ""
    item = up.item
    pulse = Span(cls="tp-pulse", aria_hidden="true") if item else ""  # only UP NEXT and HAPPENING NOW pulse, not "all done"
    leave = leave_line(v, up) if item and up.kicker.startswith("UP NEXT") else ""
    buttons = []
    if item and item.place:
        buttons.append(A(icon("nav", 18, 2.4), "Directions", href=td.maps_url(item.place, v["ua"]), target="_blank", rel="noopener", cls="tp-btn tp-btn-coral", id="tp-directions", data_dir=item.id))
        buttons.append(A(icon("car", 18, 2.4), "Uber", href=td.uber_url(item.place, td.cached_coords(item.place)), target="_blank", rel="noopener", cls="tp-btn tp-btn-white", id="tp-uber"))
    elif up.uber:
        buttons.append(A("Get an Uber" if up.uber.kind == "offer" else "Your Uber", href=up.uber.href, cls="tp-btn tp-btn-white", id="tp-uber"))
    return Div(Span(pulse, up.kicker, cls="tp-kicker"), Span(item.title if item else "You are all caught up", cls="tp-up-title"), Span(up.detail, cls="tp-up-sub"), leave,
               Div(*buttons, cls="tp-up-actions") if buttons else "", up_details(item) if item else "", cls="tp-up", id="tp-up")


def up_details(item):
    """What the list row would have shown for the up-next item (it is left out of the list): who added it, the notes on it, the confirmation behind a tap."""
    who = item.sub.split(" · ")[-1] if item.by else ""
    if not (item.confirm or item.notes or who.startswith("added by")):
        return ""
    body = [Span(who, cls="tp-sub")] if who.startswith("added by") else []
    body += [Span(icon("pencil", 13, 2.4), n, cls="tp-pnote") for n in item.notes]
    if item.confirm:
        body += [Span("Confirmation number", cls="tp-sub"), Span(item.confirm, cls="tp-conf-num")]
    return Details(Summary("Details", Span(f" for {item.title}", cls="sr-only"), cls="tp-mini"), *body, cls="ph-details tp-confirm", **({"data_confirm": item.id} if item.confirm else {}), data_up_details=item.id)


def leave_line(v, up):
    """The countdown ring and "Leave by 9:35" under the up-next card, only when a drive time is known (gitaway.tripday.leave_by); else nothing."""
    item = up.item
    before = [x for x in v["items"] if x.start < item.start and x.place and x.kind not in ("ride", "offer")]
    flew = any(x.kind == "flight" and x.start < item.start for x in v["items"])  # on a travel day nobody leaves from the stay
    margin = 0
    if item.kind == "flight":  # F-075: a departure flight is driven to from the stop before (or the night's stay), with time to spare; a landing never is
        if not td.is_departure(item.id):
            return ""
        leg = td._LEG.search(item.title)
        margin = td.flight_margin(*leg.groups()) if leg else td.DOMESTIC_EARLY
        origin = "" if before and before[-1].kind == "flight" else before[-1].place if before else v["stay_before"]
    else:
        origin = "" if before and before[-1].kind == "flight" else before[-1].place if before else ("" if flew else v["stay_place"])  # straight after a flight there is no drive to time
    got = td.leave_by(item, origin, v["clocks"][item.zone][1], margin)
    if not got:
        return ""
    at, drive, left = got
    left = max(left, 0)
    ring = NotStr('<svg viewBox="0 0 52 52" aria-hidden="true"><circle cx="26" cy="26" r="22" class="ph-ring-bg"/><circle cx="26" cy="26" r="22" class="ph-ring-fg" stroke-dasharray="138.2" stroke-dashoffset="%.1f"/></svg>' % (138.2 * (1 - min(left, 60) / 60)))
    return Div(Span(ring, Span(str(left), cls="ph-ring-n"), Span("MIN", cls="ph-ring-u"), cls="ph-ring"),
               Span(Span(f"Leave by {cal.fmt_time(at)}" if left else "Time to leave", cls="ph-leave-by"), Span(f"{drive} min drive" + (f" · be there {td.early_label(margin)} early" if margin else ""), cls="tp-up-sub"), cls="ph-leave-text"), cls="ph-leave", id="tp-leave")


def row(item, today, ua=""):
    tint = f"tp-k-{item.tint}"
    inner = (Span(item.label.upper(), cls="tp-label"), Span(item.title, cls="tp-what"), Span(item.sub, cls="tp-sub"))
    state = {"done": "Done", "now": "Now", "next": "Next"}.get(item.state, "") if today else ""
    badge = Span(icon("check", 14, 3) if item.state == "done" else "", state, cls=f"tp-state tp-state-{item.state}") if state else ""
    booked = item.kind in ("flight", "hotel", "car")  # a booked item (F-059): tinted by kind, a solid edge in the kind's ink, and a quiet lock
    lock = Span(icon("lock", 14, 2.4), Span("Booked, locked", cls="sr-only"), cls="tp-lock") if booked else ""
    card = (A if item.href else Div)(Div(Span(icon(item.icon, 18, 2.2), cls="tp-ico", aria_hidden="true") if item.icon else "", Div(*inner, cls="tp-card-text"), lock, badge, cls="tp-card-in"),
                                     cls=f"tp-card {tint} is-{item.state} tp-{item.kind}{' tp-bk' if booked else ''}", **({"href": item.href} if item.href else {}), data_item=item.id)
    extras = [Span(icon("pencil", 13, 2.4), n, cls="tp-pnote") for n in item.notes]
    acts = []
    if item.place:
        acts.append(A(icon("pin", 15, 2.4), "Directions", Span(f" to {item.title}", cls="sr-only"), href=td.maps_url(item.place, ua), target="_blank", rel="noopener", cls="tp-mini tp-dir", data_dir=item.id))
    if item.confirm:
        acts.append(Details(Summary(icon("lock", 15, 2.4), "Confirmation", Span(f" for {item.title}", cls="sr-only"), cls="tp-mini"), Span("Confirmation number", cls="tp-sub"), Span(item.confirm, cls="tp-conf-num"), cls="tp-confirm", data_confirm=item.id))
    if acts:
        extras.append(Div(*acts, cls="tp-acts"))
    return Div(Span(cal.fmt_time(item.start), cls="tp-time"), Div(card, *extras, cls="tp-col"), cls=f"tp-row is-{item.state}")


def stay_card(v):
    s = v["stay"]
    if not s:
        return ""
    go = A(icon("chev-right", 20, 2.6), href=s.href, aria_label="Hotel details", cls="tp-go") if s.href else ""
    return Div(Span(icon("bed", 24, 2.2), cls="tp-stay-ico", aria_hidden="true"), Div(Span(s.title, cls="tp-what"), Span(f"{s.name} · {s.where}" if s.where else s.name, cls="tp-sub"), cls="tp-stay-text"), go, cls="tp-stay", id="tp-stay")


def day_strip(v):
    chips = []
    for d in v["days"]:
        cur = d.index == v["sel"]
        chips.append(A(Span(str(d.num), cls=f"tp-chip-num ink-{d.tint}"), Span(d.dow, cls="tp-chip-dow"),
                       href=trip_url(day=d.index), cls=f"tp-chip tp-t-{d.tint}{' is-today' if d.state == 'today' else ''}", data_day=str(d.index),
                       aria_current="date" if cur else None, aria_label=f"{v['dates'][d.index].strftime('%A %b')} {d.num}" + (", today" if d.state == "today" else "")))
    return Nav(*chips, cls="tp-strip", aria_label="Days of the trip", id="tp-strip")


def today_panel(v):
    sel, d = v["sel"], v["dates"][v["sel"]]
    editor = access.can_edit(v["role"])
    parts = [day_strip(v)]
    if v["phase"] == "during" and sel != v["today_idx"]:
        parts.append(Div(Span(f"{_day_name(d)} · day {sel + 1} of {len(v['dates'])}", cls="tp-daynote"), A("Back to today", href=trip_url(), cls="tp-back"), cls="tp-dayhead"))
    elif v["phase"] != "during":
        parts.append(Div(Span(f"{_day_name(d)} · day {sel + 1} of {len(v['dates'])}", cls="tp-daynote"), cls="tp-dayhead"))
    parts.append(share_bar(v))
    flights, flight_titles = passes_ui.flight_cards(v)   # F-083: on the flight's day, before it leaves, the flight is the focal card
    parts.append(flights or up_card(v))
    if v["items"]:
        parts.append(route_strip(v))
        parts.append(Div(Span("THE REST OF TODAY" if v["now"] is not None else "THE DAY"), cls="ph-sec"))
        rest = not flights and v["now"] is not None and v["up"] and v["up"].item  # the up-next item is in the card above, with its details
        parts.append(Div(*[row(x, v["now"] is not None, v["ua"]) for x in v["items"] if not (rest and x.id == v["up"].item.id) and not (x.kind == "flight" and x.title in flight_titles)], cls="tp-list", id="tp-list"))
    else:
        parts.append(Div(Span("wide open!", cls="tp-hand"), A("Add something fun", href=trip_url(add="1", day=sel), data_open_sheet="", cls="tp-btn tp-btn-ink") if editor else Span("Nothing planned yet.", cls="tp-sub"), cls="tp-empty"))
    if cal.is_imported(v["b"]) and any(x.kind in ("flight", "hotel", "car") for x in v["items"]):  # where it was booked is said once, quietly
        parts.append(Div(icon("lock", 13, 2.4), Span(f"Booked elsewhere · {cal.plan_of(v['b']).booked_on}"), cls="tp-elsewhere"))
    parts.append(stay_card(v))
    parts.append(morning_ui.card(v["zone"]))  # F-066: the morning plan push, drawn by its own module
    parts.append(v.get("faceid", ""))  # F-074: "Use Face ID next time", hidden until passkeys.js says this is the Home Screen app
    parts.append(note_strip(v))
    parts.append(A(icon("arrow-right", 18, 2.4), "Open the full calendar", href="/calendar?view=whole", cls="tp-full"))
    return Section(*parts, id="tp-panel-today", cls="tp-panel", role="tabpanel", aria_label="Today", data_title=_title_today(v))


def route_strip(v):
    """A schematic strip of the day's stops in order (numbered, the up-next one in coral), then the hotel. No map tiles. Needs two stops or more."""
    stops = [(x.id, x.title) for x in v["items"] if x.place and x.kind not in ("ride", "offer")]
    if v["stay"]:
        stops.append(("stay", v["stay"].name))
    if len(stops) < 2:
        return ""
    nxt = v["up"].item.id if v["up"] and v["up"].item else None
    w, h, ys = 358, 74, (46, 28, 50, 32, 48)
    pts = [(40 + i * (w - 80) / (len(stops) - 1), ys[i % len(ys)]) for i in range(len(stops))]
    d = f"M{pts[0][0]:.1f} {pts[0][1]}" + "".join(f" C{(a[0] + b[0]) / 2:.1f} {a[1]} {(a[0] + b[0]) / 2:.1f} {b[1]} {b[0]:.1f} {b[1]}" for a, b in zip(pts, pts[1:]))
    svg = NotStr(f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true"><path d="{d}" class="ph-route-casing"/><path d="{d}" class="ph-route-line"/></svg>')
    dots = [Span(str(i + 1), cls=f"ph-stop{' is-next' if sid == nxt else ''}", style=f"left:{x / w * 100:.2f}%;top:{y / h * 100:.2f}%") for i, ((sid, _), (x, y)) in enumerate(zip(stops, pts))]
    return Div(svg, *dots, Span(f"{len(stops)} stops", cls="ph-route-lab"), role="img", aria_label="Today's route: " + ", ".join(t for _, t in stops), cls="ph-route", id="tp-route")


def share_text(v):
    return td.share_text(v["t"].title, v["dates"][v["sel"]], v["items"], v["stay"])


def share_bar(v):
    """The Share button (F-065): the day as a short plain text through the phone's share sheet, else copied. Everyone, viewers too, can share."""
    d = v["dates"][v["sel"]]
    return Div(Button(icon("share", 18, 2.4), "Share this day", type="button", cls="tp-btn tp-btn-white tp-share", id="tp-share", data_share_title=f"{v['t'].title} · {d.strftime('%a %b')} {d.day}", data_share_text=share_text(v)),
               Span("", role="status", id="tp-share-status", cls="tp-share-status"), cls="tp-sharebar")


def _title_today(v):
    d = v["dates"][v["sel"]]
    return d.strftime("%A") if v["sel"] == v["today_idx"] else f"{d.strftime('%a')}, {d.strftime('%b')} {d.day}"


def note_strip(v):
    """The newest one or two trip notes under the hotel card, as slips, with a link to the Notes tab."""
    if not v["notes"]:
        return ""
    people = {f.name.casefold(): f for f in ses.friends(v["session"])}
    family = members.family_people(v["session"])
    acts_by_id = {a.id: a for a in v["acts"]}
    slips = []
    for i, n in enumerate(v["notes"][-2:]):
        name, author = calui.note_writer(n, v["who"], people, family)
        on = acts_by_id.get(n.act)
        slips.append(_slip(author, f"{name} · {'on ' + on.title if on else 'whole trip'}", n.text, i + 1, n.id))
    return Div(*slips, A("All notes", href=trip_url(tab="notes"), data_tab_link="notes", cls="tp-full"), cls="tp-notestrip", id="tp-notestrip")


def days_panel(v):
    tiles = []
    for d in v["days"]:
        tiles.append(A(Span(Span(str(d.num), cls=f"tp-tile-num ink-{d.tint}"), Span(d.dow, cls="tp-tile-dow"), cls=f"tp-tile-day tp-t-{d.tint}"),
                       Span(Span(d.head, cls="tp-what"), Span(d.line, cls="tp-sub"), cls="tp-tile-text"),
                       href=trip_url(day=d.index), cls=f"tp-tile{' is-today' if d.state == 'today' else ' is-done' if d.state == 'done' else ''}", data_day=str(d.index),
                       aria_label=f"{v['dates'][d.index].strftime('%A %b')} {d.num}: {d.head}"))
    return Section(Div(*tiles, cls="tp-tiles"), id="tp-panel-days", cls="tp-panel", role="tabpanel", aria_label="All days", data_title=f"Your {len(v['dates'])} days")


def notes_panel(v, error=""):
    editor = access.can_edit(v["role"])
    acts_by_id = {a.id: a for a in v["acts"]}
    people = {f.name.casefold(): f for f in ses.friends(v["session"])}
    family = members.family_people(v["session"])
    who = v["who"]
    first_name, first_author = calui.note_writer(cal.Note("", "", None, "", v["b"].get("booked_by", "")), who, people, family)
    feed = [_slip(first_author, f"{first_name} · whole trip", calui.booked_note(v["b"]), 0)]
    for i, n in enumerate(v["notes"], 1):
        name, author = calui.note_writer(n, who, people, family)
        on = acts_by_id.get(n.act)
        feed.append(_slip(author, f"{name} · {'on ' + on.title if on else 'whole trip'}", n.text, i, n.id))
    composer = Form(_hidden("id", f"n{v['next']}"), trip_field(),
                    Div(error, role="alert", cls="tp-error") if error else "",
                    Label(Span("Add a note for everyone", cls="sr-only"), Input(type="text", name="text", placeholder="Add a note for everyone", maxlength=str(cal.MAX_NOTE), required=True, autocomplete="off", id="tp-note-text")),
                    Button("Send", type="submit", cls="tp-btn tp-btn-coral"), action="/trip/notes", method="post", cls="tp-composer", id="tp-composer") if editor else ""
    return Section(composer, Div(*reversed(feed), cls="tp-feed", id="tp-feed"), id="tp-panel-notes", cls="tp-panel", role="tabpanel", aria_label="Notes", data_title="Trip notes")


def _slip(author, meta, text, i, note_id=""):
    return Div(avatar(author, "tp-av"), Div(Span(meta, cls="tp-notemeta"), Span(text, cls="tp-notetext"), cls=f"tp-slip tp-slip-{'a' if i % 2 else 'b'}"), cls="tp-note", **({"data_note": note_id} if note_id else {}))


def add_sheet(v, sheet):
    """The bottom sheet: title, start time, kind. `sheet` is None (closed) or {"vals", "error"}."""
    sel = v["sel"]
    vals = (sheet or {}).get("vals") or {}
    if "start" not in vals:
        gs = cal.grid_start(v["blocks"])
        floor = max(gs, -(-v["now"] // 30) * 30) if v["now"] is not None else gs
        vals = {**vals, "start": cal.hhmm(calui.free_start(v["blocks"], sel, floor))}
    kind = vals.get("kind") or "fun"
    error = (sheet or {}).get("error", "")
    kinds = Div(*[Label(Input(type="radio", name="kind", value=k, checked=(kind == k) or None), Span(label), cls=f"tp-kind tp-t-{tint}") for k, (label, tint) in cal.KINDS.items()], cls="tp-kinds", role="radiogroup", aria_label="Kind")
    form = Form(
        _hidden("id", vals.get("id") or f"a{v['next']}"), _hidden("day", str(sel)), trip_field(),
        Label(Span("What are you up to?"), Input(type="text", name="title", value=vals.get("title", ""), maxlength=str(cal.MAX_TITLE), required=True, placeholder="Tacos, a beach day, the pier", autocomplete="off", id="tp-title", data_autofocus="")),
        # F-051 hook: this is a plain native time input for now; the themed picker attaches to [data-time-picker].
        Label(Span("Starts at"), Input(type="time", name="start", value=vals["start"], step="900", required=True, id="tp-start", data_time_picker="")),
        kinds,
        Div(Button("Add to the trip", type="submit", cls="tp-btn tp-btn-coral", id="tp-save"), A("Cancel", href=trip_url(day=sel), data_close_sheet="", cls="tp-btn tp-btn-plain"), cls="tp-sheet-actions"),
        action="/trip/plans", method="post", cls="tp-form", id="tp-form")
    return Div(A(href=trip_url(day=sel), cls="tp-backdrop", data_close_sheet="", aria_label="Close", tabindex="-1"),
               Div(H2(f"Add to {_day_name(v['dates'][sel])}", id="tp-sheet-title"), Div(error, role="alert", cls="tp-error") if error else "", form, cls="tp-sheet-body", role="dialog", aria_modal="true", aria_labelledby="tp-sheet-title"),
               id="tp-sheet", cls="tp-sheet", **({"data_open": ""} if sheet is not None else {}))


def header(v, tab):
    t = v["t"]
    faces = [avatar(v["who"], "tp-av"), *[avatar(f, "tp-av") for f in v["crew"]]]
    dates = f"{t.title.upper()} · {cal.range_label(t.depart, t.return_).upper()}"
    day_of = f"{t.title.upper()} · DAY {v['sel'] + 1} OF {len(v['dates'])}" if v["phase"] == "during" and v["today_idx"] == v["sel"] else dates
    kicker = day_of if tab == "today" else dates
    return Header(Div(Span(kicker, cls="tp-head-k", id="tp-head-k", data_today=day_of, data_other=dates),
                      H1({"today": _title_today(v), "days": f"Your {len(v['dates'])} days", "notes": "Trip notes"}[tab], id="tp-title-h"),
                      A(icon("pencil", 14, 2.4), "Edit trip", href=f"/trips/build/edit?trip={ses.open_trip_id()}", cls="btn btn-sm tp-edit", id="tp-edit-trip") if access.can_edit(v["role"]) and cal.is_imported(v["b"]) and ses.open_trip_id() else "",
                      cls="tp-head-text"),
                  Div(*faces, cls="tp-faces"), cls="tp-head")


def tab_bar(tab):
    return Nav(*[A(name, href=trip_url(tab="" if key == "today" else key), data_tab_link=key, aria_current="page" if key == tab else None, cls="tp-tab", id=f"tp-tab-{key}") for key, name in TABS],
               cls="tp-tabs", aria_label="Trip")


# ---- the page -----------------------------------------------------------------------------------------------------------

def trip_page(session, *args, **kw):
    """The page, with the family's map cache open while it is drawn (Today's Leave by and Uber coordinates read it; gitaway.geo.cache_scope)."""
    with geo.cache_scope(session):
        return _trip_page(session, *args, **kw)


def _trip_page(session, ua="", tab="today", day="", sheet=None, new="", notice="", note_error="", status=200):
    v = load(session, day, ua)
    tab = tab if tab in dict(TABS) else "today"
    editor = access.can_edit(v["role"])
    if sheet is not None and not editor:
        sheet = None
    added = next((a for a in v["acts"] if a.id == new), None) if new else None
    v["faceid"] = passkeys_ui.today_card(session)
    panels = [today_panel(v), days_panel(v), notes_panel(v, note_error)]
    for key, p in zip(("today", "days", "notes"), panels):
        if key != tab:
            p(hidden=True)
    toast = Div(f"Added “{added.title}” at {cal.fmt_time(added.start)}", role="status", cls="tp-toast", id="tp-toast") if added else (Div(notice, role="alert", cls="tp-toast tp-toast-error") if notice else "")
    viewing = P("You are a viewer in this family: you can look at everything but not change it.", id="tp-viewer", role="status", cls="tp-viewer") if v["role"] == "viewer" else ""
    plus = A(icon("plus", 28, 2.8), href=trip_url(add="1", day=v["sel"]), id="tp-add", aria_label="Add a plan", cls="tp-plus", data_open_sheet="") if editor else ""
    body = phone.shell("today", header(v, tab), join_note(), viewing, tab_bar(tab), Main(*panels, id="main"), toast, plus, add_sheet(v, sheet) if editor else "",
                       title=v["t"].title, head=HEAD, scripts=("/assets/js/trip.js",), id="tp-app", data_tab=tab, data_day=str(v["sel"]),
                       data_today=str(v["today_idx"]) if v["today_idx"] is not None else "", data_trip=ses.open_trip_id() or None)
    return FtResponse(body, status_code=status) if status != 200 else body


# ---- routes -------------------------------------------------------------------------------------------------------------

def _guard(session):
    """A redirect when the traveler cannot use the trip view yet, else None."""
    if not ses.current_traveler(session):
        return RedirectResponse("/signin?next=%2Ftrip", status_code=303)
    if not ses.booking(session):
        return RedirectResponse("/start", status_code=303)
    return None


def register(app):
    @app.get("/trip")
    def trip(session, request, tab: str = "", day: str = "", add: str = "", new: str = ""):
        if (r := _guard(session)):
            return r
        ua = request.headers.get("user-agent", "")
        sheet = {} if add == "1" else None
        try:
            tripgeo.warm(session)  # fill the map cache in the background, at most once an hour (F-068)
        except Exception:  # Today never fails because the map cache could not be filled
            log.exception("could not start the map fill")
        return trip_page(session, ua, tab or "today", day[:3], sheet, new[:8])

    @app.post("/trip/plans")
    def add_plan(session, request, id: str = "", day: str = "", start: str = "", title: str = "", kind: str = ""):
        if (r := _guard(session)):
            return r
        ua = request.headers.get("user-agent", "")
        b = ses.booking(session)
        t = cal.trip("", b)
        blocks = cal.booked_blocks(b, t) + cal.ride_blocks(session, b, t)
        vals = {"id": id, "title": title, "start": start, "kind": kind or "fun"}
        try:
            if not (day.isdigit() and 0 <= int(day) <= (t.return_ - t.depart).days):
                raise cal.CalendarError("Pick a day inside your trip.")
            s = cal.snap(cal.parse_time(start, "start"))
            end = calui.default_end(blocks, int(day), s)  # an hour, or until the next booked block; the calendar's own validation judges the rest
            end = end // cal.SNAP * cal.SNAP if end // cal.SNAP * cal.SNAP - s >= cal.MIN_LEN else end  # snapping must not round up into the block that cut it short
            a = cal.add_activity(session, day=day, start=start, end=cal.hhmm(end), title=title, kind=kind, id=id or None)
        except cal.CalendarError as e:
            return trip_page(session, ua, "today", day[:3], {"vals": vals, "error": str(e)}, status=409)
        return RedirectResponse(trip_url(day=day, new=a.id if a else ""), status_code=303)

    @app.post("/trip/notes")
    def add_note(session, request, id: str = "", text: str = ""):
        if (r := _guard(session)):
            return r
        try:
            cal.add_note(session, text, id=id or None)
        except cal.CalendarError as e:
            return trip_page(session, request.headers.get("user-agent", ""), "notes", note_error=str(e), status=409)
        return RedirectResponse(trip_url(tab="notes"), status_code=303)
