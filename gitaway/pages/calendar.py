"""The trip calendar at /calendar (F-019).

GET /calendar                                    the calendar (?demo=long for the 20-day fixture, ?view=days for the hour grid; the default is the compact whole-trip list)
                                                 ?add=<day>&at=HH:MM[&title=..&kind=..] opens the add form (title and kind prefilled), ?edit=<id> the edit form, ?undo=<id> the undo toast
POST /calendar/activities                        add            POST /calendar/activities/{id}         edit
POST /calendar/activities/{id}/move              move/resize    POST /calendar/activities/{id}/delete  delete (then Undo)
POST /calendar/undo                              undo the last delete
POST /calendar/notes                             a trip note, or a note on one activity
GET  /calendar?invite=1                          the invite dialog (GET /invite sends a signed-out traveler through sign-in first)
POST /calendar/friends                           invite a friend (the same friend twice is a no-op)
POST /calendar/live                              the scripted "Mom adds Travel Town" (once per traveler per trip; calendar.js calls it)

The server is the source of truth (gitaway.tripcal). Every POST redirects back to a GET (or re-renders with a 409 and the
reason), so a refresh never repeats a change. calendar.js only enhances: it swaps the server-rendered #cal-app in place,
adds pointer move/resize and the keyboard shortcuts, and drives the day window.
"""

from urllib.parse import quote as urlquote, urlencode

from fasthtml.common import A, Aside, Button, Details, Div, Fieldset, Form, H1, H2, H3, Header, Input, Label, Legend, Li, Link, Main, Option, P, Script, Section, Select, Span, Summary, Title, Ul
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import access, catalog, firstrun, forks as forks_model, members, pickers, session as ses, showcase, tripcal as cal, tripday
from gitaway.icons import icon
from gitaway.layout import avatar, brand, join_note, styles, trip_field
from gitaway import voice as vo
from gitaway.pages import pay, plan as plan_ui, rides as rides_ui, voice as voice_ui

HEAD = (*pickers.HEAD, Link(rel="stylesheet", href="/assets/css/calendar.css"), Link(rel="stylesheet", href="/assets/css/voice.css"))
HH = 48  # one hour is 48px at the 16px base, i.e. 3rem (calendar.js HOUR_REM must match)
DAY_TINTS = ("sun", "mint", "grape", "sky", "bubble")  # day colours cycle in this order


def cal_url(demo="", **q):
    params = ([("demo", demo)] if demo == cal.LONG else []) + [(k, v) for k, v in q.items() if v not in ("", None)]
    return "/calendar" + (f"?{urlencode(params)}" if params else "")


def _px(minutes):
    return f"{minutes * HH / 60 / 16:g}rem"


def trip_name(t):
    return t.title


def day_label(i, d):
    """'FRI', plus an 'OCT' that may drop to its own line, on the first day and whenever the month changes."""
    mon = Span(d.strftime("%b").upper(), cls="cal-mon") if i == 0 or d.day == 1 else ""
    return (Span(d.strftime("%a").upper()), mon)


def _hours_label(h):
    return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"


def _hidden(name, value):
    return Input(type="hidden", name=name, value=value)


def _demo_field(demo):
    """The hidden fields every calendar form carries: the trip it was drawn for, and the ?demo=long fixture when that is open."""
    return (trip_field(), _hidden("demo", cal.LONG) if demo == cal.LONG else "")


# ---- lanes and free gaps -------------------------------------------------------------------------------------------

def lanes(acts):
    """{activity id: (lane, lanes in its cluster)} so overlapping activities sit side by side."""
    out, cluster, ends, cluster_end = {}, [], [], -1

    def flush():
        for a, lane in cluster:
            out[a.id] = (lane, len(ends))

    for a in sorted(acts, key=lambda a: (a.start, a.end, a.id)):
        if a.start >= cluster_end:
            flush()
            cluster, ends = [], []
        lane = next((i for i, e in enumerate(ends) if e <= a.start), len(ends))
        if lane == len(ends):
            ends.append(a.end)
        else:
            ends[lane] = a.end
        cluster.append((a, lane))
        cluster_end = max(cluster_end, a.end)
    flush()
    return out


def _clashes(blocks, day, s, e):
    return any(b.day == day and s < b.end and b.start < e for b in blocks)


def free_start(blocks, day, gs):
    """The first half hour from 9 AM (or the grid start, or when you land) with an hour free of booked items, inside the day's window."""
    lo, hi = cal.day_window(blocks, day)
    t = -(-max(9 * 60, gs, lo) // 30) * 30
    while t + 60 <= hi:
        if not _clashes(blocks, day, t, t + 60):
            return t
        t += 30
    return gs


def default_end(blocks, day, start):
    end = min(start + 60, cal.GRID_END)
    for b in blocks:
        if b.day == day and b.start >= start:
            end = min(end, b.start)
    return end if end - start >= cal.MIN_LEN else min(start + 60, cal.GRID_END)


# ---- blocks --------------------------------------------------------------------------------------------------------

def ride_href(ctx, block):
    """Where a ride block goes: the ride itself, or (an offer, id "ro-<leg>") the flow that schedules it for the booked picks."""
    if block.kind == "ride":
        return f"/rides/{block.id}"
    if cal.is_imported(ctx["booking"]):  # an imported trip has no picks: the ride flow names the trip instead (F-042)
        b = ctx["booking"]
        return rides_ui.new_url(cal.flight_of(b), cal.stay_of(b), cal.trip_of(b), block.id[3:])
    return plan_ui.ride_path(block.id[3:], cal.flight_of(ctx["booking"]).id, (cal.stay_of(ctx["booking"]) or None) and cal.stay_of(ctx["booking"]).id, cal.trip_of(ctx["booking"]))


def ride_block(b, gs, ctx, lane=0, nlanes=1):
    """A simulated Uber (F-038) on the grid: a scheduled one is a locked block that opens the ride; an offer is a dashed ghost that starts scheduling it.
    Like any block it keeps its true height (a 25 minute ride is short) and fades what does not fit; hover or focus opens it."""
    offer = b.kind == "rideoffer"
    label = f"{'Simulated, not booked: ' if offer else 'Simulated ride: '}{b.title}, {cal.fmt_time(b.start)} to {cal.fmt_time(b.end)}"
    return A(
        Span(icon(b.icon, 13, 2.2), " ", Span(cal.fmt_time(b.start), cls="cal-time"), " ", Span(b.title, cls="cal-title"), cls="cal-flow"),
        href=ride_href(ctx, b), **({"data_offer": b.id} if offer else {"data_block": b.id}), data_day=str(b.day), data_start=str(b.start), data_end=str(b.end), draggable="false",
        cls=f"cal-block cal-ride{' cal-rideoffer' if offer else ' cal-booked cal-rideset'}{' cal-short' if b.end - b.start <= 45 else ''}{' cal-lane' if nlanes > 1 else ''}",
        style=f"--top:{_px(b.start - ctx['gs'])};--h:{_px(b.end - b.start)};--lane:{lane};--lanes:{nlanes}", aria_label=label,
    )


def detail_href(ctx, block):
    """Where a block booked elsewhere opens its booking detail (F-042): this calendar with ?detail=<block id>, for the trip drawn."""
    return cal_url(ctx["demo"], view=ctx["view"], detail=block.id, trip=ses.open_trip_id())


BOOKED_KIND = {"plane": "flight", "bed": "hotel", "car": "car"}  # the palette of a booked item (F-059): flight sky, hotel lilac, car sunshine


def booked_kind(b):
    return BOOKED_KIND.get(b.icon, "hotel")


def booked_words(b):
    """The words on a booked block: a hotel says what happens and when ("Check in 3:00 PM") with the hotel's name quietly beneath; the rest is time then title."""
    head, _, rest = b.title.partition(" · ")
    if b.icon == "bed" and head in ("Check in", "Check out"):
        return [Span(f"{head} {cal.fmt_time(b.at)}", cls="cal-title"), Span(rest, cls="cal-where")] if rest else [Span(f"{head} {cal.fmt_time(b.at)}", cls="cal-title")]
    return [Span(cal.fmt_time(b.at), cls="cal-time"), " ", Span(b.title, cls="cal-title")]


def booked_block(b, gs, lane=0, nlanes=1, ctx=None):
    """A locked booked block, tinted by its kind with a solid edge in the kind's ink. One booked elsewhere (an imported trip, F-042) opens its booking detail
    (where the confirmation is); where it was booked is said once, in the trip header and the detail, and still in the label a screen reader hears."""
    elsewhere = bool(b.tag and ctx)
    return (A if elsewhere else Div)(
        Span(icon(b.icon, 13, 2.2), " ", *booked_words(b), cls="cal-flow"),
        Span(icon("lock", 12, 2.4), cls="cal-lock"),
        Span("Booked, locked", cls="sr-only"),
        cls=f"cal-block cal-booked cal-bk-{booked_kind(b)}{' cal-lane' if nlanes > 1 else ''}{' cal-short' if elsewhere and b.end - b.start <= 45 else ''}", data_block=b.id, data_day=str(b.day), data_start=str(b.start), data_end=str(b.end),
        style=f"--top:{_px(b.start - gs)};--h:{_px(b.end - b.start)};--lane:{lane};--lanes:{nlanes}",
        **({"href": detail_href(ctx, b), "draggable": "false"} if elsewhere else {"role": "group", "tabindex": "0"}),
        aria_label=f"Booked, locked{', ' + b.tag if b.tag else ''}: {b.title}, {cal.fmt_time(b.at)} to {cal.fmt_time(b.end)}" + (". Press Enter for the booking details." if elsewhere else ""),
    )


def activity_block(a, gs, demo, lane, nlanes, n_notes, new, is_live=False, fresh=()):
    label, tint = cal.KINDS[a.kind]
    short, tight = a.end - a.start <= 45, a.end - a.start <= 60
    pop = " cal-pop" if new == a.id or a.id in fresh else ""
    ring = " cal-livering" if is_live and new == a.id and a.by else ""
    just = Span("just now", cls="cal-justnow") if ring else ""
    return A(
        Span(cal.fmt_time(a.start), cls="cal-time"),
        Span(a.title, cls="cal-title"),
        Span(Span(a.by or "You", cls="cal-by"), just, Span(f"{n_notes} note{'s' if n_notes != 1 else ''}", cls="cal-notecount") if n_notes else "", cls="cal-meta"),
        Span(cls="cal-resize", aria_hidden="true", title="Drag to resize"),
        href=cal_url(demo, edit=a.id), data_soft="", draggable="false", title=a.title,
        cls=f"cal-block cal-act k-{tint}{' cal-short' if short else ''}{' cal-tight' if tight else ''}{' cal-lane' if nlanes > 1 else ''}{pop}{ring}",
        data_id=a.id, data_day=str(a.day), data_start=str(a.start), data_end=str(a.end),
        style=f"--top:{_px(a.start - gs)};--h:{_px(a.end - a.start)};--lane:{lane};--lanes:{nlanes}",
        aria_label=f"{a.title}, {label}, {cal.fmt_time(a.start)} to {cal.fmt_time(a.end)}. Press Enter to edit, arrow keys to move by 15 minutes, Shift and arrows to resize.",
    )


def draft_block(x, gs):
    """A voice plan waiting for Apply: a dashed ghost block that turns solid when added (voice.js hides it when unticked)."""
    p = x.plan
    return Div(
        Span(cal.fmt_time(p.start), cls="cal-time"), Span(p.title, cls="cal-title"), Span("from your voice", cls="cal-draft-tag"),
        cls=f"cal-block cal-draft{' cal-draft-half' if x.state == 'clash' else ''}", data_key=p.key, data_day=str(p.day), data_start=str(p.start), data_end=str(p.end), hidden=None if x.checked else True, tabindex="0",
        style=f"--top:{_px(p.start - gs)};--h:{_px(p.end - p.start)};--lane:{1 if x.state == 'clash' else 0};--lanes:{2 if x.state == 'clash' else 1}",
        aria_label=f"Draft plan: {p.title}, {cal.fmt_time(p.start)} to {cal.fmt_time(p.end)}. Not added yet.")


def day_column(i, date_, ctx):
    gs, demo, blocks = ctx["gs"], ctx["demo"], ctx["blocks"]
    w = cal.weather_for(i)
    tint = DAY_TINTS[i % 5]
    acts = [a for a in ctx["acts"] if a.day == i]
    lane = lanes(acts)
    n_notes = ctx["note_counts"]
    booked = [b for b in blocks if b.day == i]
    offers = [o for o in ctx["offers"] if o.day == i]
    body = [ride_block(b, gs, ctx) if b.kind == "ride" else booked_block(b, gs, ctx=ctx) for b in booked]  # rides come after, so they sit over a check-out tail at full width
    body += [ride_block(o, gs, ctx) for o in offers]
    body += [activity_block(a, gs, demo, *lane[a.id], n_notes.get(a.id, 0), ctx["new"], ctx["live"], ctx["fresh"]) for a in acts]
    here = [x for x in ctx["drafts"] if x.plan.day == i]
    body += [draft_block(x, gs) for x in here]
    if not booked and not acts and not here and not offers:
        body.append(A(Span("wide open!", cls="cal-hand"), Span("Add something fun"), href=cal_url(demo, add=i, at=cal.hhmm(free_start(blocks, i, gs))),
                      data_soft="", cls="cal-empty"))
    at = cal.hhmm(free_start(blocks, i, gs))
    head = Div(
        Span(str(date_.day), cls=f"cal-num ink-{tint}"),
        Span(Span(*day_label(i, date_), cls="cal-dow"),
             Span(icon(w.icon, 15, 2.2), Span(f"{w.temp_f}°F"), Span(f", {w.sky}", cls="sr-only"), cls="cal-wx", title=w.sky), cls="cal-dayinfo"),
        A(icon("plus", 16, 2.6), href=cal_url(demo, add=i, at=at), data_soft="", cls="cal-dayadd",
          aria_label=f"Add something on {date_.strftime('%A')} {date_.strftime('%b')} {date_.day}"),
        cls=f"cal-dayhead fill-{tint}-tint", data_day_head=str(i),
    )
    return Div(
        head,
        Div(*body, cls="cal-body", data_day=str(i), style=f"height:{_px(ctx['ge'] - gs)}"),
        id=f"d{i}", cls="cal-day", aria_label=date_.strftime("%A %B ") + str(date_.day), role="group",
    )


def hour_gutter(gs, ge):
    hours = [Span(_hours_label(h), cls="cal-hour") for h in range(gs // 60, ge // 60)]
    return Div(Div(cls="cal-dayhead cal-corner"), Div(*hours, cls="cal-hours", style=f"height:{_px(ge - gs)}"), cls="cal-gutter", aria_hidden="true")


# ---- strip, whole-trip view, notes ---------------------------------------------------------------------------------

def strip(dates, ctx):
    chips = []
    for i, d in enumerate(dates):
        booked = [b for b in ctx["blocks"] if b.day == i]
        planned = sum(1 for a in ctx["acts"] if a.day == i)
        dots = [Span(cls=f"cal-dot cal-dot-booked cal-bk-{'ride' if b.kind == 'ride' else booked_kind(b)}") for b in booked[:3]] + [Span(cls="cal-dot cal-dot-plan") for _ in range(min(planned, 3))]
        month = Span(d.strftime("%b"), cls="cal-chip-mon") if i == 0 or d.day == 1 else Span("", cls="cal-chip-mon")
        chips.append(A(
            month, Span(str(d.day), cls="cal-chip-num"), Span(d.strftime("%a"), cls="cal-chip-dow"), Span(*dots, cls="cal-dots"),
            href=f"#d{i}", cls=f"cal-chip fill-{DAY_TINTS[i % 5]}-tint", data_chip=str(i),
            aria_label=f"{d.strftime('%A %b')} {d.day}: {len(booked)} booked, {planned} planned",
        ))
    return Div(*chips, cls="cal-strip", role="navigation", aria_label="Whole trip, one chip per day")


def _whole_line(x, ctx):
    kind = getattr(x, "kind", "")
    if kind in ("ride", "rideoffer"):  # a simulated Uber (F-038): a link to the ride, or to scheduling it
        return Li(Span(cal.fmt_time(x.start), cls="cal-w-time"),
                  A(x.title, href=ride_href(ctx, x), cls=f"cal-w-title cal-w-ride{' is-offer' if kind == 'rideoffer' else ''}", data_block=x.id),
                  Span("Simulated", cls="cal-w-booked cal-w-sim") if kind == "ride" else "")
    if getattr(x, "locked", False):  # a booked item (F-059): its kind's icon in its tint, the title (opens the booking detail when booked elsewhere), a quiet lock
        kind = booked_kind(x)
        title = Span(x.title, cls="cal-w-title is-booked")
        if getattr(x, "tag", ""):
            title = A(x.title, href=detail_href(ctx, x), cls="cal-w-title is-booked", data_block=x.id)
        return Li(Span(cal.fmt_time(x.at), cls="cal-w-time"), Span(icon(x.icon or "calendar", 13, 2.2), cls=f"cal-w-ico cal-bk-{kind}", aria_hidden="true"), title,
                  Span(icon("lock", 11, 2.4), Span("Booked, locked", cls="sr-only"), cls=f"cal-w-booked cal-bk-{kind}"), cls=f"cal-w-bk cal-bk-{kind}")
    return Li(Span(cal.fmt_time(x.start), cls="cal-w-time"), Span(x.title, cls="cal-w-title"))


def whole_view(dates, ctx):
    rows = []
    for i, d in enumerate(dates):
        items = sorted([*(b for b in ctx["blocks"] if b.day == i), *(a for a in ctx["acts"] if a.day == i), *(o for o in ctx["offers"] if o.day == i)], key=lambda x: x.start)
        tint = DAY_TINTS[i % 5]
        lines = [_whole_line(x, ctx) for x in items]
        rows.append(Div(
            A(Span(str(d.day), cls=f"cal-num ink-{tint}"), Span(*day_label(i, d), cls="cal-dow"), Span(" · open in day by day", cls="sr-only"), href=cal_url(ctx["demo"], view="days", w=i),
              cls=f"cal-w-head fill-{tint}-tint"),
            Ul(*lines, cls="cal-w-list") if lines else Div(Span("wide open", cls="cal-hand"), A("Add something fun", href=cal_url(ctx["demo"], view="days", add=i, at=cal.hhmm(free_start(ctx["blocks"], i, ctx["gs"])), w=i, back="whole"), data_soft=""), cls="cal-w-empty"),
            id=f"d{i}", cls="cal-w-row", data_whole_day=str(i),
        ))
    return Div(*rows, cls="cal-whole")


FORMER = ses.Friend("Former member", "?", "sky")


def note_writer(n, who, people, family):
    """(name shown, avatar person) for a note: a pretend friend by name, another member by their user id, and "You" only for the viewer's own."""
    if n.by:
        return n.by, people.get(n.by.casefold(), who)
    if not n.by_id or n.by_id == who.id:
        return "You", who
    member = family.get(n.by_id, FORMER)
    return member.name, member


def note_entry(n, acts_by_id, who, people, fresh=False, family=None):
    on = acts_by_id.get(n.act)
    name, author = note_writer(n, who, people, family or {})
    where = "just now" if fresh else f"on {on.title}" if on else "whole trip"
    return Div(
        avatar(author, "cal-noteav"),
        Div(Span(f"{name} · {where}", cls="cal-notemeta"), Span(n.text, cls="cal-notetext"), cls="cal-noteslip"),
        cls=f"cal-note{' cal-note-live' if fresh else ''}", data_note=n.id,
    )


def booked_note(b):
    """The first note on the feed: what was booked, as a list that fits any mix of flight, stay and car. Flights and a stay are
    blocks on the calendar; a car has none, so it is only ever said to be booked."""
    if cal.is_imported(b):
        where = cal.plan_of(b).booked_on
        lanes = [w for w, got in (("flights", cal.flight_of(b)), ("hotel", cal.stay_of(b)), ("car", cal.car_of(b))) if got]  # only what this trip really has
        if not lanes:
            return f"Imported from {where}. Add anything you want to do."
        return f"Imported from {where}. Your {cal.oxford(lanes)} {'is' if len(lanes) == 1 and lanes != ['flights'] else 'are'} on the calendar, locked. Tap one for its details. Add anything you want to do."
    stay, pick, car = cal.stay_of(b), cal.stay_pick_of(b), cal.car_of(b)
    flights = cal.flight_of(b) is not None
    on_cal = (["flights"] if flights else []) + ([f"{stay.name} ({pick.summary})" if flights else f"stay at {stay.name} ({pick.summary})"] if stay else [])
    rental = f"{car.name} rental" if car else ""
    if not on_cal:
        return f"Booked! Your {rental} is booked. It has no block here, but you can still plan the days."
    are = "are" if len(on_cal) > 1 or on_cal == ["flights"] else "is"
    if not car:
        return f"Booked! Your {cal.oxford(on_cal)} {are} on the calendar. Add anything you want to do."
    placed = cal.oxford((["flights"] if flights else []) + (["stay"] if stay else []))
    return f"Booked! Your {cal.oxford(on_cal + [rental])} are all set. The {placed} {are} on the calendar; the car has no block there. Add anything you want to do."


def notes_panel(ctx, who, b):
    acts_by_id = {a.id: a for a in ctx["acts"]}
    people = {f.name.casefold(): f for f in ctx["friends"]}
    fresh = ctx["new"] if ctx["live"] else ""
    family = members.family_people(ctx["session"])
    name, author = note_writer(cal.Note("", "", None, "", b.get("booked_by", "")), who, people, family)  # the first note is from whoever booked or imported the trip
    feed = [Div(avatar(author, "cal-noteav"), Div(Span(f"{name} · whole trip", cls="cal-notemeta"),
                Span(booked_note(b), cls="cal-notetext"), cls="cal-noteslip"), cls="cal-note cal-note-first")]
    feed += [note_entry(n, acts_by_id, who, people, bool(fresh) and n.act == fresh and bool(n.by), family) for n in ctx["notes"]]
    about = Select(Option("Whole trip", value=""), *[Option(a.title, value=a.id) for a in ctx["acts"]], name="act", aria_label="What is this note about?", cls="cal-about") if ctx["acts"] else ""
    return Aside(
        Button(icon("note", 18, 2.2), Span("Trip notes"), Span(str(len(ctx["notes"])), cls="cal-count"), type="button", id="cal-notes-toggle",
               cls="cal-notes-toggle", aria_controls="cal-notes-body", aria_expanded="false"),
        Div(Div(H2("Trip notes"), Span("everyone sees these", cls="cal-sub"), cls="cal-notes-head"),
            Div(*feed, cls="cal-feed", id="cal-feed", tabindex="0", aria_label="Trip notes feed"),
            Form(_hidden("id", f"n{ctx['next']}"), _demo_field(ctx["demo"]), _hidden("view", ctx["view"]), about,
                 Label(Span("Add a note for everyone", cls="sr-only"), Input(type="text", name="text", placeholder="Add a note for everyone", maxlength=str(cal.MAX_NOTE), required=True, autocomplete="off")),
                 Button("Send", type="submit", cls="cal-send"),
                 action="/calendar/notes", method="post", data_soft="", cls="cal-composer"),
            id="cal-notes-body", cls="cal-notes-body"),
        id="cal-notes", aria_label="Trip notes", cls="cal-notes",
    )


# ---- form and toasts -----------------------------------------------------------------------------------------------

def form_modal(ctx, vals, error, edit_id=None):
    demo, dates = ctx["demo"], ctx["dates"]
    editing = edit_id is not None
    close = cal_url(demo, view="whole" if ctx.get("back") == "whole" else ctx["view"])
    kinds = Fieldset(Legend("Kind"), *[
        Label(Input(type="radio", name="kind", value=k, checked=(vals["kind"] == k) or None), Span(label), cls=f"cal-kind k-{tint}")
        for k, (label, tint) in cal.KINDS.items()], cls="cal-kinds")
    day_opts = [Option(f"{d.strftime('%a %b')} {d.day}", value=str(i), selected=(str(vals["day"]) == str(i)) or None) for i, d in enumerate(dates)]
    main = Form(
        _hidden("id", vals["id"]) if not editing else "", _demo_field(demo), _hidden("view", ctx["view"]),
        Label(Span("What are you up to?"), Input(type="text", name="title", value=vals["title"], maxlength=str(cal.MAX_TITLE), required=True, placeholder="Tacos, a beach day, the pier", data_autofocus="", autocomplete="off")),
        Div(Label(Span("Day"), Select(*day_opts, name="day")),
            Label(Span("Start"), Input(type="time", name="start", value=vals["start"], step="900", required=True)),
            Label(Span("End"), Input(type="time", name="end", value=vals["end"], step="900", required=True)), cls="cal-fields"),
        kinds,
        Div(Button("Save changes" if editing else "Add to the trip", type="submit", cls="btn btn-primary cal-save"),
            A("Cancel", href=close, data_soft="", data_close="", cls="cal-cancel"), cls="cal-actions"),
        action=f"/calendar/activities/{edit_id}" if editing else "/calendar/activities", method="post", data_soft="", cls="cal-form",
    )
    extra = []
    if editing:
        mine = [n for n in ctx["notes"] if n.act == edit_id]
        extra = [
            Div(H3("Notes on this one"), *[Span(n.text, cls="cal-formnote") for n in mine] or [Span("No notes yet.", cls="cal-sub")], cls="cal-formnotes"),
            Form(_hidden("id", f"n{ctx['next']}"), _hidden("act", edit_id), _demo_field(demo), _hidden("edit", edit_id),
                 Label(Span("Add a note", cls="sr-only"), Input(type="text", name="text", placeholder="Add a note to this one", maxlength=str(cal.MAX_NOTE), required=True, autocomplete="off")),
                 Button("Add note", type="submit", cls="cal-send"), action="/calendar/notes", method="post", data_soft="", cls="cal-composer cal-inline"),
            Form(_demo_field(demo), Button("Delete", type="submit", cls="cal-delete"), action=f"/calendar/activities/{edit_id}/delete", method="post", data_soft=""),
        ]
    return Div(
        A(href=close, cls="cal-backdrop", data_soft="", data_close="", aria_label="Close", tabindex="-1"),
        Div(H2("Edit activity" if editing else "Add something fun", id="cal-form-title"),
            Div(error, role="alert", cls="cal-error") if error else "", main, *extra,
            role="dialog", aria_modal="true", aria_labelledby="cal-form-title", cls="cal-dialog"),
        cls="cal-modal",
    )


def invite_modal(ctx, b, name, error):
    demo, friends = ctx["demo"], ctx["friends"]
    close = cal_url(demo, view=ctx["view"])
    have = {f.name.casefold() for f in friends}
    chips = [Button(icon("check", 16, 2.6), Span(f"{n} is in"), type="button", disabled=True, cls="cal-chipbtn is-in") if n.casefold() in have
             else Button(icon("plus", 16, 2.6), Span(n), type="submit", name="name", value=n, cls="cal-chipbtn")
             for n in ses.DEMO_FRIENDS]
    link = ses.invite_link(b["id"])
    return Div(
        A(href=close, cls="cal-backdrop", data_soft="", data_close="", aria_label="Close", tabindex="-1"),
        Div(H2("Invite your crew", id="cal-form-title"),
            P("Friends and family see the calendar and add their own ideas. This is a demo: nobody is really emailed.", cls="cal-sub"),
            Div(error, role="alert", cls="cal-error") if error else "",
            Form(Span("Quick picks", cls="cal-sub"), Div(*chips, cls="cal-chiprow"), _demo_field(demo), _hidden("view", ctx["view"]),
                 action="/calendar/friends", method="post", data_soft="", cls="cal-invite"),
            Form(Label(Span("Or type a name"), Input(type="text", name="name", value=name, maxlength=str(ses.MAX_FRIEND_NAME), required=True, placeholder="Grandma, Jo, the neighbours", autocomplete="off", data_autofocus="")),
                 _demo_field(demo), _hidden("view", ctx["view"]),
                 Button("Add to the trip", type="submit", cls="btn btn-primary cal-save"),
                 action="/calendar/friends", method="post", data_soft="", cls="cal-form cal-invite"),
            Div(Span("Or share a link", cls="cal-sub"),
                Div(Input(type="text", value=link, readonly=True, aria_label="Invite link", cls="cal-linkfield"),
                    Button(icon("link", 16, 2.4), Span("Copy invite link"), type="button", data_copy=link, cls="cal-copy"), cls="cal-linkrow"),
                cls="cal-invite"),
            Div(Span("Inviting your real family?", cls="cal-sub"), A("Invite by email on the Family page", href="/family#invite", id="cal-real-invite", cls="cal-realink"), cls="cal-invite"),
            Div(A("Done", href=close, data_soft="", data_close="", cls="cal-cancel"), cls="cal-actions"),
            role="dialog", aria_modal="true", aria_labelledby="cal-form-title", cls="cal-dialog"),
        cls="cal-modal",
    )


def detail_modal(ctx, detail):
    """The booking detail of a block booked elsewhere (F-042), with its confirmation number. Only drawn on this signed-in, family-only page."""
    title, rows = detail
    close = cal_url(ctx["demo"], view=ctx["view"])
    plan = cal.plan_of(ctx["booking"])
    return Div(
        A(href=close, cls="cal-backdrop", data_soft="", data_close="", aria_label="Close", tabindex="-1"),
        Div(H2(title, id="cal-form-title"),
            Span(f"Booked elsewhere · {plan.booked_on}" + (f" · itinerary {plan.itinerary}" if plan.itinerary else ""), cls="cal-sub"),
            Div(*[Div(Span(k, cls="cal-dk"), Span(v, cls="cal-dv", **({"id": "cal-confirmation"} if k == "Confirmation" else {})), cls="cal-drow") for k, v in rows], cls="cal-details"),
            Span("Confirmation numbers are shown only to your family.", cls="cal-sub"),
            Div(A("All trip details", href="/trip/details", cls="btn btn-sm"), A("Close", href=close, data_soft="", data_close="", cls="cal-cancel"), cls="cal-actions"),
            role="dialog", aria_modal="true", aria_labelledby="cal-form-title", cls="cal-dialog"),
        cls="cal-modal", id="cal-detail",
    )


def toast(kind, text, *extra, tid=None):
    return Div(Span(text, id=tid), *extra, role="alert" if kind == "error" else "status", cls=f"cal-toast cal-toast-{kind}")


# ---- page ----------------------------------------------------------------------------------------------------------

def trip_switcher(session):
    """"2 trips" with a menu to open another of the family's trips (F-040). With one trip (F-053) the menu names it and offers to plan or import the next."""
    mine = ses.trips(session)
    if not mine:
        return ""
    rows = [Li(Form(Input(type="hidden", name="trip", value=t.id),
                    Button(Span(t.title, cls="cal-trip-name"), Span(t.detail, cls="cal-trip-dates"), type="submit", data_trip=t.id,
                           aria_current="true" if t.current else None, cls="cal-trip"),
                    action="/trips/switch", method="post")) for t in mine]
    return Details(Summary(icon("plane", 16, 2.2), Span(f"{len(mine)} trip{'s' if len(mine) != 1 else ''}"), cls="cal-trips-sum"),
                   Div(Span("Open a trip", cls="cal-trips-k") if len(mine) > 1 else P("This is your only trip so far. Add another and switch between them here.", cls="cal-trips-solo"),
                       Ul(*rows, cls="cal-trips-list") if len(mine) > 1 else "",
                       A(icon("plus", 16, 2.4), "Plan another trip", href="/start", cls="cal-trip-new"),
                       A(icon("ledger", 16, 2.4), "Import a trip you booked", href="/trips/import", cls="cal-trip-new"),
                       cls="cal-trips-pop"),
                   cls="cal-trips")


def share_controls(session):
    """The Share button; once the trip is shared it says so, updates the snapshot on a tap, and offers Unpublish (owner only)."""
    from gitaway import share
    if not showcase.on():  # sharing a trip publicly is community-facing
        return []
    if not access.can_edit(access.request_role()):  # sharing is an edit: viewers just look
        return []
    row = share.shared(session)
    if not row:
        return [Form(trip_field(), Button("Share trip", type="submit", cls="cal-btn cal-btn-ink"), action="/share", method="post", cls="cal-share")]
    return [Form(trip_field(), Button(icon("check", 16, 2.6), "Shared", Span(" · Update shared page", cls="cal-share-more"), type="submit", cls="cal-btn cal-btn-ink",
                        title="Share again to update the shared page with your latest plans"), action="/share", method="post", cls="cal-share"),
            Form(trip_field(), Input(type="hidden", name="slug", value=row["slug"]), Button("Unpublish", type="submit", cls="cal-btn cal-btn-white"),
                 action="/share/unpublish", method="post", cls="cal-share")]


def presence_text(crew, friends):
    """"Sam is planning with you": the real family members first (newest last), else the demo's pretend friends."""
    names = [p.name for p in crew] or [friends[-1].name]
    if len(names) == 1:
        return f"{names[0]} is planning with you"
    if len(names) == 2:
        return f"{names[0]} and {names[1]} are planning with you"
    return f"{names[-3]}, {names[-2]} and {names[-1]} are planning with you" if len(names) == 3 else f"{names[-2]}, {names[-1]} and {len(names) - 2} more are planning with you"


def invite_button(ctx):
    """Invite: a demo trip opens the pretend-friends dialog (editors and admins); a real trip goes to the Family page, where admins invite by email. Viewers see none."""
    role = ctx["role"]
    if not access.can_edit(role):
        return ""
    if ctx["is_demo"] and showcase.on():  # the pretend-friends dialog is sample data
        return A("Invite", href=cal_url(ctx["demo"], view=ctx["view"], invite="1"), id="cal-invite-btn", data_id="invite", data_soft="", cls="cal-btn cal-btn-coral")
    return A("Invite" if role == "admin" else "Family", href="/family#invite" if role == "admin" else "/family", id="cal-invite-btn", cls="cal-btn cal-btn-coral")


def top_bar(t, b, who, session, ctx):
    forks = forks_model.count(session)
    friends, crew = ctx["friends"], ctx["crew"]
    people = [avatar(who, "cal-avatar"), *[Span(avatar(f, "cal-avatar"), Span(cls="cal-presence-dot"), cls="cal-friend") for f in [*crew, *friends]]]
    presence = Span(presence_text(crew, friends), cls="cal-presence", role="status") if crew or friends else ""
    return Header(
        brand("/"),
        Div(H1(trip_name(t)), Div(Span(f"{cal.range_label(t.depart, t.return_)} · " + (f"booked elsewhere · {cal.plan_of(b).booked_on}" if cal.is_imported(b) else f"booked · {catalog.money(b['total_cents'])}"), cls="cal-tripline"), trip_switcher(session),
                                                                                       A(icon("ledger", 16, 2.4), "Import a booked trip", href="/trips/import", cls="btn btn-sm", id="cal-import") if ctx["role"] != "viewer" else "",
                                                                                       A(icon("pencil", 16, 2.4), "Edit trip", href=f"/trips/build/edit?trip={ses.open_trip_id()}", cls="btn btn-sm", id="cal-edit-trip") if access.can_edit(ctx["role"]) and cal.is_imported(b) and ses.open_trip_id() else "", cls="cal-tripbar"), cls="cal-title-box"),
        Div(Div(*people, cls="cal-faces"), presence, cls="cal-avatars"),
        Div(A(icon("mic", 18, 2.4), "Talk to plan", href=voice_ui.voice_url(ctx["demo"], hear=1), data_soft="", cls="cal-btn cal-btn-mint vo-open") if ctx["role"] != "viewer" and showcase.on() else "",
            A("Your forks", Span(str(forks), cls="cal-count"), href="/forks", cls="cal-btn cal-btn-white") if showcase.on() else "",
            invite_button(ctx),
            A(icon("share", 16, 2.4), "Today, to share", href=f"/trip?trip={ses.open_trip_id()}" if ses.open_trip_id() else "/trip", cls="cal-btn cal-btn-white", id="cal-today-view"),
            *share_controls(session), cls="cal-actions-top"),
        cls="cal-bar",
    )


def pick_view(view, acting=False):
    """whole (the default) or days. An explicit ?view= wins; otherwise any editing flow (add, edit, new, undo) needs the grid."""
    return view if view in ("whole", "days") else "days" if acting else "whole"


def view_toggle(demo, view):
    return Div(
        A("Whole trip", href=cal_url(demo, view="whole"), aria_current="true" if view == "whole" else None, cls="cal-seg"),
        A("Day by day", href=cal_url(demo, view="days"), aria_current="true" if view == "days" else None, cls="cal-seg"),
        cls="cal-toggle", role="group", aria_label="Calendar view",
    )


def calendar_page(session, demo="", view="", form=None, notice=None, new="", undo="", w="", status=200, invite=None, live=False, back="", voice=None, voiced=None, detail=""):
    who, b = ses.current_traveler(session), ses.booking(session)
    demo = cal.LONG if demo == cal.LONG else ""
    view = pick_view(view, bool(form or new or undo or w or voice is not None or voiced))
    t = cal.trip(demo, b)
    dates = cal.days(t)
    blocks = cal.booked_blocks(b, t) + cal.ride_blocks(session, b, t)
    role, is_demo = access.request_role(), ses.open_trip_is_demo(session)
    offers = cal.ride_offers(session, b, t) if role != "viewer" else []  # "Schedule an Uber" is a write: a viewer sees the rides already set, not the offers
    acts = cal.activities(session, demo)
    notes = cal.notes(session, demo)
    counts = {}
    for n in notes:
        if n.act:
            counts[n.act] = counts.get(n.act, 0) + 1
    gs = cal.grid_start(blocks)
    gs_end = cal.grid_end(blocks)
    friends = ses.friends(session)
    if role == "viewer":  # a viewer looks: no add, edit, invite or voice dialogs
        form, invite, voice = None, None, None
    if not is_demo:       # the pretend-friends dialog belongs to the demo trip: its refusal is a plain message
        notice = notice or (invite or {}).get("error")
        invite = None
    question = vo.question(dates)
    night, drafts, vpanel = None, [], None
    if voice is not None:
        night = voice.get("night") if question.option(voice.get("night")) else None
        placed = vo.preview(session, night, demo)
        drafts = [x for x in placed if not x.hard and x.state != "have"]
        vpanel = voice_ui.panel(session, demo, dates, question, placed, night, bool(voice.get("hear")), voice.get("error", ""))
    ctx = dict(session=session, booking=b, offers=offers, drafts=drafts, fresh=set(voiced["ids"]) if voiced else set(), demo=demo, view=view, t=t, dates=dates, blocks=blocks, acts=acts, notes=notes, note_counts=counts, gs=gs, ge=gs_end, back=back, new=new, next=cal.next_id(session, demo),
               friends=friends, crew=members.crew(session), role=role, is_demo=is_demo, live=bool(live and any(a.id == new and a.by for a in acts)))
    if view == "whole":
        surface = whole_view(dates, ctx)
    else:
        surface = Div(
            Div(hour_gutter(gs, gs_end), *[day_column(i, d, ctx) for i, d in enumerate(dates)], cls="cal-scroll", id="cal-scroll", tabindex="-1", data_w=w or "0", role="region", aria_label="Days"),
            A("+ Add something fun", href="#", id="cal-ghost", cls="cal-ghost", data_soft="", hidden=True, tabindex="-1"),
            cls="cal-grid",
        )
    n = len(dates)
    controls = Div(
        view_toggle(demo, view),
        Span("Tap a day, or choose Day by day, to plan by the hour.", cls="cal-viewhint") if view == "whole" else "",
        Div(Button(icon("chev-left", 18, 2.6), type="button", data_dir="-1", aria_label="Earlier days", cls="cal-navbtn"),
            Span(f"Days 1–{min(5, n)} of {n}", cls="cal-range", id="cal-range", aria_live="polite"),
            Button(icon("chev-right", 18, 2.6), type="button", data_dir="1", aria_label="Later days", cls="cal-navbtn"), cls="cal-nav") if view == "days" else "",
        cls="cal-controls",
    )
    card = Section(strip(dates, ctx) if view == "days" else "", controls, surface, cls="cal-card", aria_label="Trip calendar")
    layers = []
    if form:
        layers.append(form_modal(ctx, form["vals"], form.get("error"), form.get("edit")))
    if invite is not None:
        layers.append(invite_modal(ctx, b, invite.get("name", ""), invite.get("error")))
    if detail and (found := cal.booking_detail(b, detail)):
        layers.append(detail_modal(ctx, found))
    if notice:
        layers.append(toast("error", notice))
    if ctx["live"]:
        mom = next(a for a in acts if a.id == new)
        layers.append(toast("live", f"{mom.by} added {mom.title}", A("Show me", href=f"#d{mom.day}", data_jump=str(mom.day), cls="cal-dismiss"),
                            A("Dismiss", href=cal_url(demo, view=view), data_soft="", cls="cal-dismiss")))
    if voiced:
        here = {a.id for a in acts}
        got = [i for i in voiced["ids"] if i in here]
        if got:
            layers.append(toast("undo", f"Added {len(got)} plan{'s' if len(got) != 1 else ''} by voice.",
                                Form(_hidden("ids", ",".join(got)), _hidden("nid", voiced.get("note", "")), _hidden("night", voiced.get("night", "")), _demo_field(demo), Button("Undo", type="submit", cls="cal-undo", autofocus=True, aria_describedby="cal-toast-text"),
                                     action="/calendar/voice/undo", method="post", data_soft=""),
                                A("Dismiss", href=cal_url(demo, view=view), data_soft="", cls="cal-dismiss"), tid="cal-toast-text"))
    gone = cal.last_deleted(session, demo)
    if undo and gone and gone.id == undo:
        layers.append(toast("undo", f"Deleted \"{gone.title}\".", Form(_hidden("id", gone.id), _demo_field(demo), _hidden("view", view), Button("Undo", type="submit", cls="cal-undo"),
                                                                     action="/calendar/undo", method="post", data_soft=""),
                           A("Dismiss", href=cal_url(demo, view=view), data_soft="", cls="cal-dismiss")))
    viewing = P("You are a viewer in this family: you can look at everything but not change it. Ask a family admin to make you an editor.", id="cal-viewer", role="status", cls="cal-viewer") if role == "viewer" else ""
    app = Div(top_bar(t, b, who, session, ctx), join_note(), viewing, Div(card, vpanel or notes_panel(ctx, who, b), cls="cal-layout"), *layers,
              id="cal-app", cls="cal cal-readonly" if role == "viewer" else "cal", data_trip=ses.open_trip_id() or None, data_demo=demo, data_view=view, data_grid_start=str(gs), data_grid_end=str(gs_end),
              data_base=cal_url(demo, view=view), data_live="1" if cal.live_pending(session, demo) else None, data_voice="1" if voice is not None else None)
    body = (
        Title(f"GitAway · {trip_name(t)} calendar"),
        *styles(*HEAD),
        Div(A("Skip to content", href="#main", cls="ga-skip"), Main(app, id="main"), data_theme="sunset", cls="cal-shell"),
        Script(src="/assets/js/calendar.js", defer=True), Script(src="/assets/js/voice.js", defer=True),
    )
    return FtResponse(body, status_code=status) if status != 200 else body


def no_booking():
    return (
        Title("GitAway · Trip calendar"),
        *styles(*HEAD),
        Div(A("Skip to content", href="#main", cls="ga-skip"),
            Main(Header(brand("/"), cls="cal-bar"), join_note(),
                 Section(Div(firstrun.welcome("Your calendar starts with a trip",
                                              "It fills in with your flights and hotel as soon as you plan or import one. Then the fun part starts: adding the gaps.",
                                              heading=H1, eyebrow="NO TRIPS YET"), cls="cal-firstbox"), cls="cal-first"),
                 id="main"), data_theme="sunset", cls="cal-shell"),
    )


# ---- routes --------------------------------------------------------------------------------------------------------

def _signin(demo, view=""):
    return RedirectResponse(f"/signin?next={urlquote(cal_url(demo, view=view), safe='')}", status_code=303)


def _vals(**kw):
    return {"id": "", "title": "", "kind": "fun", **kw}


def register(app):
    def guard(session, demo):
        """A redirect when the traveler cannot use the calendar yet, else None."""
        if not ses.current_traveler(session):
            return _signin(demo)
        if not ses.booking(session):
            return RedirectResponse("/calendar", status_code=303)
        return None

    @app.get("/calendar")
    def calendar(session, request, demo: str = "", view: str = "", add: str = "", at: str = "", edit: str = "", new: str = "", undo: str = "", w: str = "", invite: str = "", live: str = "", back: str = "", voice: str = "", night: str = "", hear: str = "", voiced: str = "", vnote: str = "", vn: str = "", detail: str = "", title: str = "", kind: str = ""):
        if not ses.current_traveler(session):
            return _signin(demo, view)
        if not ses.booking(session):
            return no_booking()
        if not request.url.query and tripday.is_phone(request.headers.get("user-agent")):  # F-054: a phone's plain /calendar is the trip view; "Open the full calendar" asks for ?view=
            return RedirectResponse("/trip", status_code=303)
        demo = cal.LONG if demo == cal.LONG else ""
        form = None
        if access.request_role() == "viewer":  # a viewer cannot open the add, edit, invite or voice dialogs
            add = edit = invite = voice = ""
        if not showcase.on():  # "Talk to plan" is a scripted demo
            voice = hear = voiced = ""
        blocks = cal.booked_blocks(ses.booking(session), cal.trip(demo, ses.booking(session)))
        gs = cal.grid_start(blocks)
        nid = cal.next_id(session, demo)
        if edit:
            a = cal.get_activity(session, edit, demo)
            if a:
                form = {"edit": a.id, "vals": _vals(id=a.id, day=a.day, start=cal.hhmm(a.start), end=cal.hhmm(a.end), title=a.title, kind=a.kind)}
        elif add.isdigit():
            day = int(add)
            try:
                start = cal.parse_time(at, "start")
            except cal.CalendarError:
                start = free_start(blocks, day, gs)
            start = cal.snap(min(max(start, gs), cal.GRID_END - cal.MIN_LEN))
            form = {"vals": _vals(id=f"a{nid}", day=day, start=cal.hhmm(start), end=cal.hhmm(default_end(blocks, day, start)), title=" ".join(title.split())[: cal.MAX_TITLE], kind=kind if kind in cal.KINDS else "fun")}   # ?title= and ?kind= prefill it (Around you, F-073)
        view = pick_view(view, bool(add or edit or new or undo or w or voice == "1" or voiced))
        talk = {"night": voice_ui.parse_night(night), "hear": hear == "1"} if voice == "1" and not form else None
        done = {"ids": voice_ui.parse_ids(voiced), "note": voice_ui.note_id(vnote), "night": str(voice_ui.parse_night(vn) if voice_ui.parse_night(vn) is not None else "")} if voiced else None
        return calendar_page(session, demo, view, form=form, new=new, undo=undo, w=w, invite={} if invite == "1" and not form and showcase.on() else None, live=live == "1", back=back if add else "", voice=talk, voiced=done, detail=detail[:20])

    def refuse(session, demo, view, message, form=None):
        return calendar_page(session, demo, view, form=form, notice=None if form else message, status=409)

    def done(demo, view, **q):
        view = view if view in ("whole", "days") else ""
        return RedirectResponse(cal_url(demo, view=view, **q), status_code=303)

    @app.post("/calendar/activities")
    def add_activity(session, id: str = "", day: str = "", start: str = "", end: str = "", title: str = "", kind: str = "", demo: str = "", view: str = ""):
        if (r := guard(session, demo)):
            return r
        try:
            a = cal.add_activity(session, day=day, start=start, end=end, title=title, kind=kind, demo=demo, id=id or None)
        except cal.CalendarError as e:
            return refuse(session, demo, view, str(e), {"error": str(e), "vals": _vals(id=id, day=day, start=start, end=end, title=title, kind=kind or "fun")})
        return done(demo, view, new=a.id) if a else done(demo, view)

    @app.post("/calendar/activities/{id}")
    def edit_activity(session, id: str, day: str = "", start: str = "", end: str = "", title: str = "", kind: str = "", demo: str = "", view: str = ""):
        if (r := guard(session, demo)):
            return r
        try:
            a = cal.update_activity(session, id, day=day, start=start, end=end, title=title, kind=kind, demo=demo)
        except cal.CalendarError as e:
            return refuse(session, demo, view, str(e), {"error": str(e), "edit": id, "vals": _vals(id=id, day=day, start=start, end=end, title=title, kind=kind or "fun")})
        return done(demo, view, new=a.id)

    @app.post("/calendar/activities/{id}/move")
    def move_activity(session, id: str, day: str = "", start: str = "", end: str = "", demo: str = "", view: str = ""):
        if (r := guard(session, demo)):
            return r
        try:
            cal.update_activity(session, id, day=day, start=start, end=end, demo=demo)
        except cal.CalendarError as e:
            return refuse(session, demo, view, str(e))
        return done(demo, view)

    @app.post("/calendar/activities/{id}/delete")
    def delete_activity(session, id: str, demo: str = "", view: str = ""):
        if (r := guard(session, demo)):
            return r
        gone = cal.delete_activity(session, id, demo)
        return done(demo, view, undo=gone.id) if gone else done(demo, view)

    @app.post("/calendar/undo")
    def undo_delete(session, id: str = "", demo: str = "", view: str = ""):
        if (r := guard(session, demo)):
            return r
        back = cal.undo_delete(session, id, demo)
        return done(demo, view, new=back.id) if back else done(demo, view)

    @app.post("/calendar/notes")
    def add_note(session, id: str = "", text: str = "", act: str = "", edit: str = "", demo: str = "", view: str = ""):
        if (r := guard(session, demo)):
            return r
        try:
            cal.add_note(session, text, act=act or None, demo=demo, id=id or None)
        except cal.CalendarError as e:
            return refuse(session, demo, view, str(e))
        return done(demo, view, edit=edit)

    @app.get("/invite")
    def invite_entry(session):
        """The Invite entry point: signed out goes through sign-in (intent=invite) and comes back to the calendar."""
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={urlquote(cal_url('', invite='1'), safe='')}&intent=invite", status_code=303)
        if not ses.booking(session):
            return RedirectResponse("/calendar", status_code=303)
        return RedirectResponse(cal_url("", invite="1") if ses.open_trip_is_demo(session) else "/family#invite", status_code=303)

    @app.post("/calendar/friends")
    def add_friend(session, name: str = "", demo: str = "", view: str = ""):
        if (r := guard(session, demo)):
            return r
        try:
            ses.add_friend(session, name)
        except ses.FriendError as e:
            return calendar_page(session, demo, view, invite={"name": name, "error": str(e)}, status=409)
        return done(demo, view)

    @app.post("/calendar/live")
    def live_add(session, demo: str = "", view: str = ""):
        if (r := guard(session, demo)):
            return r
        a = cal.live_add(session, demo)
        return done(demo, view, new=a.id, live="1") if a else done(demo, view)
