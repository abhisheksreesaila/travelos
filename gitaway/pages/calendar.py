"""The trip calendar at /calendar (F-019).

GET /calendar                                    the calendar (?demo=long for the 20-day fixture, ?view=days for the hour grid; the default is the compact whole-trip list)
                                                 ?add=<day>&at=HH:MM opens the add form, ?edit=<id> the edit form, ?undo=<id> the undo toast
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

from fasthtml.common import A, Aside, Button, Div, Fieldset, Form, H1, H2, H3, Header, Input, Label, Legend, Li, Link, Main, Option, P, Script, Section, Select, Span, Title, Ul
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import catalog, session as ses, tripcal as cal
from gitaway.icons import icon
from gitaway.layout import avatar, brand, styles
from gitaway.pages import pay

HEAD = (Link(rel="stylesheet", href="/assets/css/calendar.css"),)
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
    return _hidden("demo", cal.LONG) if demo == cal.LONG else ""


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
    """The first half hour from 9 AM (or the grid start) with an hour free of booked items."""
    t = max(9 * 60, gs)
    while t + 60 <= cal.GRID_END:
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

def booked_block(b, gs):
    return Div(
        Span(icon(b.icon, 13, 2.2), " ", Span(cal.fmt_time(b.start), cls="cal-time"), " ", Span(b.title, cls="cal-title"), cls="cal-flow"),
        Span(icon("lock", 12, 2.4), cls="cal-lock"),
        Span("Booked, locked", cls="sr-only"),
        cls="cal-block cal-booked", data_block=b.id, data_day=str(b.day), data_start=str(b.start), data_end=str(b.end),
        style=f"--top:{_px(b.start - gs)};--h:{_px(b.end - b.start)};--lane:0;--lanes:1",
        role="group", tabindex="0",
        aria_label=f"Booked, locked: {b.title}, {cal.fmt_time(b.start)} to {cal.fmt_time(b.end)}",
    )


def activity_block(a, gs, demo, lane, nlanes, n_notes, new, is_live=False):
    label, tint = cal.KINDS[a.kind]
    short, tight = a.end - a.start <= 45, a.end - a.start <= 60
    pop = " cal-pop" if new == a.id else ""
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


def day_column(i, date_, ctx):
    gs, demo, blocks = ctx["gs"], ctx["demo"], ctx["blocks"]
    w = cal.weather_for(i)
    tint = DAY_TINTS[i % 5]
    acts = [a for a in ctx["acts"] if a.day == i]
    lane = lanes(acts)
    n_notes = ctx["note_counts"]
    booked = [b for b in blocks if b.day == i]
    body = [booked_block(b, gs) for b in booked]
    body += [activity_block(a, gs, demo, *lane[a.id], n_notes.get(a.id, 0), ctx["new"], ctx["live"]) for a in acts]
    if not booked and not acts:
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
        Div(*body, cls="cal-body", data_day=str(i), style=f"height:{_px(cal.GRID_END - gs)}"),
        id=f"d{i}", cls="cal-day", aria_label=date_.strftime("%A %B ") + str(date_.day), role="group",
    )


def hour_gutter(gs):
    hours = [Span(_hours_label(h), cls="cal-hour") for h in range(gs // 60, cal.GRID_END // 60)]
    return Div(Div(cls="cal-dayhead cal-corner"), Div(*hours, cls="cal-hours", style=f"height:{_px(cal.GRID_END - gs)}"), cls="cal-gutter", aria_hidden="true")


# ---- strip, whole-trip view, notes ---------------------------------------------------------------------------------

def strip(dates, ctx):
    chips = []
    for i, d in enumerate(dates):
        booked = sum(1 for b in ctx["blocks"] if b.day == i)
        planned = sum(1 for a in ctx["acts"] if a.day == i)
        dots = [Span(cls="cal-dot cal-dot-booked") for _ in range(min(booked, 3))] + [Span(cls="cal-dot cal-dot-plan") for _ in range(min(planned, 3))]
        month = Span(d.strftime("%b"), cls="cal-chip-mon") if i == 0 or d.day == 1 else Span("", cls="cal-chip-mon")
        chips.append(A(
            month, Span(str(d.day), cls="cal-chip-num"), Span(d.strftime("%a"), cls="cal-chip-dow"), Span(*dots, cls="cal-dots"),
            href=f"#d{i}", cls=f"cal-chip fill-{DAY_TINTS[i % 5]}-tint", data_chip=str(i),
            aria_label=f"{d.strftime('%A %b')} {d.day}: {booked} booked, {planned} planned",
        ))
    return Div(*chips, cls="cal-strip", role="navigation", aria_label="Whole trip, one chip per day")


def whole_view(dates, ctx):
    rows = []
    for i, d in enumerate(dates):
        items = sorted([*(b for b in ctx["blocks"] if b.day == i), *(a for a in ctx["acts"] if a.day == i)], key=lambda x: x.start)
        tint = DAY_TINTS[i % 5]
        lines = [Li(Span(cal.fmt_time(x.start), cls="cal-w-time"),
                    Span(x.title, cls=f"cal-w-title{' is-booked' if getattr(x, 'locked', False) else ''}"),
                    Span("Booked", cls="cal-w-booked") if getattr(x, "locked", False) else "") for x in items]
        rows.append(Div(
            A(Span(str(d.day), cls=f"cal-num ink-{tint}"), Span(*day_label(i, d), cls="cal-dow"), Span(" · open in day by day", cls="sr-only"), href=cal_url(ctx["demo"], view="days", w=i),
              cls=f"cal-w-head fill-{tint}-tint"),
            Ul(*lines, cls="cal-w-list") if lines else Div(Span("wide open", cls="cal-hand"), A("Add something fun", href=cal_url(ctx["demo"], view="days", add=i, at=cal.hhmm(free_start(ctx["blocks"], i, ctx["gs"])), w=i, back="whole"), data_soft=""), cls="cal-w-empty"),
            id=f"d{i}", cls="cal-w-row", data_whole_day=str(i),
        ))
    return Div(*rows, cls="cal-whole")


def note_entry(n, acts_by_id, who, people, fresh=False):
    on = acts_by_id.get(n.act)
    author = people.get(n.by.casefold(), who) if n.by else who
    where = "just now" if fresh else f"on {on.title}" if on else "whole trip"
    return Div(
        avatar(author, "cal-noteav"),
        Div(Span(f"{n.by or 'You'} · {where}", cls="cal-notemeta"), Span(n.text, cls="cal-notetext"), cls="cal-noteslip"),
        cls=f"cal-note{' cal-note-live' if fresh else ''}", data_note=n.id,
    )


def notes_panel(ctx, who, b):
    stay = catalog.offer(b["stay"])
    acts_by_id = {a.id: a for a in ctx["acts"]}
    people = {f.name.casefold(): f for f in ctx["friends"]}
    fresh = ctx["new"] if ctx["live"] else ""
    feed = [Div(avatar(who, "cal-noteav"), Div(Span("You · whole trip", cls="cal-notemeta"),
                Span(f"Booked! Your flights and {stay.name} ({cal.stay_pick_of(b).summary}) are on the calendar. Add anything you want to do.", cls="cal-notetext"), cls="cal-noteslip"), cls="cal-note cal-note-first")]
    feed += [note_entry(n, acts_by_id, who, people, bool(fresh) and n.act == fresh and bool(n.by)) for n in ctx["notes"]]
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
            Div(A("Done", href=close, data_soft="", data_close="", cls="cal-cancel"), cls="cal-actions"),
            role="dialog", aria_modal="true", aria_labelledby="cal-form-title", cls="cal-dialog"),
        cls="cal-modal",
    )


def toast(kind, text, *extra):
    return Div(Span(text), *extra, role="alert" if kind == "error" else "status", cls=f"cal-toast cal-toast-{kind}")


# ---- page ----------------------------------------------------------------------------------------------------------

def top_bar(t, b, who, session, ctx):
    forks = len(ses.forks(session))
    friends = ctx["friends"]
    people = [avatar(who, "cal-avatar"), *[Span(avatar(f, "cal-avatar"), Span(cls="cal-presence-dot"), cls="cal-friend") for f in friends]]
    presence = Span(f"{friends[-1].name} is planning with you", cls="cal-presence", role="status") if friends else ""
    return Header(
        brand("/"),
        Div(H1(trip_name(t)), Span(f"{cal.range_label(t.depart, t.return_)} · booked · {catalog.money(b['total_cents'])}", cls="cal-tripline"), cls="cal-title-box"),
        Div(Div(*people, cls="cal-faces"), presence, cls="cal-avatars"),
        Div(A("Your forks", Span(str(forks), cls="cal-count"), href="/forks", cls="cal-btn cal-btn-white"),
            A("Invite", href=cal_url(ctx["demo"], view=ctx["view"], invite="1"), id="cal-invite-btn", data_id="invite", data_soft="", cls="cal-btn cal-btn-coral"),
            A("Share trip", href="/share", cls="cal-btn cal-btn-ink"), cls="cal-actions-top"),
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


def calendar_page(session, demo="", view="", form=None, notice=None, new="", undo="", w="", status=200, invite=None, live=False, back=""):
    who, b = ses.current_traveler(session), ses.booking(session)
    demo = cal.LONG if demo == cal.LONG else ""
    view = pick_view(view, bool(form or new or undo or w))
    t = cal.trip(demo, b)
    dates = cal.days(t)
    blocks = cal.booked_blocks(b, t)
    acts = cal.activities(session, demo)
    notes = cal.notes(session, demo)
    counts = {}
    for n in notes:
        if n.act:
            counts[n.act] = counts.get(n.act, 0) + 1
    gs = cal.grid_start(blocks)
    friends = ses.friends(session)
    ctx = dict(demo=demo, view=view, t=t, dates=dates, blocks=blocks, acts=acts, notes=notes, note_counts=counts, gs=gs, back=back, new=new, next=cal.next_id(session, demo),
               friends=friends, live=bool(live and any(a.id == new and a.by for a in acts)))
    if view == "whole":
        surface = whole_view(dates, ctx)
    else:
        surface = Div(
            Div(hour_gutter(gs), *[day_column(i, d, ctx) for i, d in enumerate(dates)], cls="cal-scroll", id="cal-scroll", tabindex="-1", data_w=w or "0", role="region", aria_label="Days"),
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
    if notice:
        layers.append(toast("error", notice))
    if ctx["live"]:
        mom = next(a for a in acts if a.id == new)
        layers.append(toast("live", f"{mom.by} added {mom.title}", A("Show me", href=f"#d{mom.day}", data_jump=str(mom.day), cls="cal-dismiss"),
                            A("Dismiss", href=cal_url(demo, view=view), data_soft="", cls="cal-dismiss")))
    gone = cal.last_deleted(session, demo)
    if undo and gone and gone.id == undo:
        layers.append(toast("undo", f"Deleted \"{gone.title}\".", Form(_hidden("id", gone.id), _demo_field(demo), _hidden("view", view), Button("Undo", type="submit", cls="cal-undo"),
                                                                     action="/calendar/undo", method="post", data_soft=""),
                           A("Dismiss", href=cal_url(demo, view=view), data_soft="", cls="cal-dismiss")))
    app = Div(top_bar(t, b, who, session, ctx), Div(card, notes_panel(ctx, who, b), cls="cal-layout"), *layers,
              id="cal-app", cls="cal", data_demo=demo, data_view=view, data_grid_start=str(gs), data_grid_end=str(cal.GRID_END),
              data_base=cal_url(demo, view=view), data_live="1" if cal.live_pending(session, demo) else None)
    body = (
        Title(f"GitAway · {trip_name(t)} calendar"),
        *styles(*HEAD),
        Div(A("Skip to content", href="#main", cls="ga-skip"), Main(app, id="main"), data_theme="sunset", cls="cal-shell"),
        Script(src="/assets/js/calendar.js", defer=True),
    )
    return FtResponse(body, status_code=status) if status != 200 else body


def no_booking():
    return (
        Title("GitAway · Trip calendar"),
        *styles(*HEAD),
        Div(A("Skip to content", href="#main", cls="ga-skip"),
            Main(Header(brand("/"), cls="cal-bar"),
                 Section(Div(Span(icon("plane", 40, 2), cls="cal-bignote"), H1("Book a trip first"),
                             P("Your calendar fills in with your flights and hotel as soon as you book. Then the fun part starts: adding the gaps."),
                             A("Plan a trip", href="/start", cls="btn btn-primary"), cls="cal-firstbox"), cls="cal-first"),
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
    def calendar(session, demo: str = "", view: str = "", add: str = "", at: str = "", edit: str = "", new: str = "", undo: str = "", w: str = "", invite: str = "", live: str = "", back: str = ""):
        if not ses.current_traveler(session):
            return _signin(demo, view)
        if not ses.booking(session):
            return no_booking()
        demo = cal.LONG if demo == cal.LONG else ""
        form = None
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
            form = {"vals": _vals(id=f"a{nid}", day=day, start=cal.hhmm(start), end=cal.hhmm(default_end(blocks, day, start)))}
        view = pick_view(view, bool(add or edit or new or undo or w))
        return calendar_page(session, demo, view, form=form, new=new, undo=undo, w=w, invite={} if invite == "1" and not form else None, live=live == "1", back=back if add else "")

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
        return RedirectResponse(cal_url("", invite="1") if ses.booking(session) else "/calendar", status_code=303)

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
