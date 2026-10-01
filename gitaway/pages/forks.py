"""Your forks (F-021): the list, the apply preview and the Save heart.

GET  /forks                     the traveler's forks and saved trips beside their calendar
GET  /forks?open=<slug>         preview that fork's plans in the empty slots (nothing changes until Apply)
GET  /forks?applied=a7,a8&src=<slug>   the calendar after an apply, with an Undo
POST /forks/apply               add the picked plans (slug, pick=<plan key>...), then redirect to the applied view
POST /forks/undo                take the plans of one apply back out
POST /save, /unsave             the itinerary page's Save heart (signed out: through the demo sign-in with intent=save)

The server decides everything (gitaway.tripcal places the plans); forks.js only enhances: unchecking a plan hides its
draft on the calendar, the Apply button counts, and Apply animates before it posts (instantly with reduced motion).
Every POST redirects to a GET, so a refresh never repeats a change.
"""

import re
from urllib.parse import quote, urlencode

from fasthtml.common import A, Button, Div, Form, H1, H2, Img, Input, Label, Link, P, Script, Section, Span
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import firstrun, forks as forks_model, hub, session as ses, tripcal as cal
from gitaway.icons import icon
from gitaway.layout import page, trip_field

HEAD = (Link(rel="stylesheet", href="/assets/css/forks.css"),)
HH = 2.75  # rem per calendar hour (forks.css --hh): a little tighter than the calendar so a 6 AM start still fits 1280x800
DAY_TINTS = ("sun", "mint", "grape", "sky", "bubble")
_IDS = re.compile(r"^a\d{1,4}$")
_KEY = re.compile(r"^d\d{1,3}s\d{1,3}$")


def _ids(text):
    """The activity ids in a comma separated string, ignoring anything that is not an id."""
    return [x for x in (text or "").split(",") if _IDS.match(x)][:40]


def forks_url(**q):
    q = {k: v for k, v in q.items() if v}
    return "/forks" + (f"?{urlencode(q, safe=',')}" if q else "")


# ---- the calendar beside the list ----------------------------------------------------------------------------------

def _rem(minutes):
    return f"{minutes * HH / 60:g}rem"


def _event(cls, start, end, gs, title, tag="", key="", hidden=False, by="", fresh=False):
    return Div(
        Span(cal.fmt_time(start), cls="fk-time"), Span(title, cls="fk-title"), Span(tag, cls="fk-tag") if tag else "",
        cls=f"fk-ev {cls}{' fk-pop' if fresh else ''}", style=f"--top:{_rem(start - gs)};--h:{_rem(end - start)}", tabindex="0",
        data_key=key or None, hidden=hidden or None,
        aria_label=f"{title}, {cal.fmt_time(start)} to {cal.fmt_time(end)}" + (f", {tag}" if tag else ""),
    )


def calendar_view(session, placements=(), author="", fresh=(), demo=""):
    """The traveler's calendar as day columns: bookings, plans, and the fork's draft plans when previewing."""
    b = ses.booking(session)
    t = cal.trip(demo, b)
    dates = cal.days(t)
    blocks = cal.booked_blocks(b, t) + cal.ride_blocks(session, b, t)  # scheduled Ubers are on this calendar too
    gs, ge = cal.grid_start(blocks), cal.grid_end(blocks)
    acts = cal.activities(session, demo)
    drafts = [x for x in placements if not x.hard and x.state != "have"]
    cols = []
    for i, d in enumerate(dates):
        tint = DAY_TINTS[i % 5]
        body = [_event("fk-booked", x.start, x.end, gs, x.title) for x in blocks if x.day == i]
        body += [_event("fk-mine" if not a.by else "fk-friend", a.start, a.end, gs, a.title, a.by, fresh=a.id in fresh) for a in acts if a.day == i]
        body += [_event("fk-draft" + (" fk-half" if x.state == "clash" else ""), x.plan.start, x.plan.end, gs, x.plan.title, "from fork", x.plan.key, hidden=not x.checked)
                 for x in drafts if x.plan.day == i]
        w = cal.weather_for(i)
        cols.append(Div(
            Div(Span(str(d.day), cls="fk-num"), Span(d.strftime("%a").upper(), cls="fk-dow"), Span(f"{w.temp_f}°F", cls="fk-wx"), cls=f"fk-dayhead fill-{tint}-tint"),
            Div(*body, cls="fk-body", style=f"height:{_rem(ge - gs)}"),
            cls="fk-day", aria_label=d.strftime("%A %B ") + str(d.day), role="group"))
    hours = [Span(f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}", cls="fk-hour") for h in range(gs // 60, ge // 60)]
    gutter = Div(Div(cls="fk-dayhead fk-corner"), Div(*hours, cls="fk-hours", style=f"height:{_rem(ge - gs)}"), cls="fk-gutter", aria_hidden="true")
    return Section(
        Div(Span("Your calendar", cls="fk-card-title"),
            Div(Button(icon("chev-left", 16, 2.6), type="button", data_dir="-1", aria_label="Earlier days", cls="fk-navbtn"),
                Button(icon("chev-right", 16, 2.6), type="button", data_dir="1", aria_label="Later days", cls="fk-navbtn"), cls="fk-nav", hidden=True) if len(cols) > 3 else "",
            A("Open the calendar", href="/calendar?view=days", cls="fk-link"), cls="fk-card-head"),
        Div(gutter, Div(*cols, cls="fk-scroll", id="fk-scroll", role="region", aria_label="Days", tabindex="0"), cls="fk-grid", style=f"--n:{len(cols)}"),
        cls="fk-cal card", aria_label="Trip calendar")


def calendar_empty():
    return Section(
        Span(icon("plane", 36, 2), cls="fk-bigicon"), H2("Your calendar fills in once you have a trip"),
        P("A fork's plans drop into the empty slots around your flights and stay. Plan a trip or import one you booked, then come back to apply a fork."),
        firstrun.paths(), cls="fk-cal fk-empty card")


# ---- the list ------------------------------------------------------------------------------------------------------

def _tags(e):
    return Span(*[Span(hub.TAGS[k][0], cls=f"tag fill-{hub.TAGS[k][1]}") for k in e.tags], cls="fk-tags") if e.tags else ""


def _card(e, tag, booked, current=""):
    meta = f"{e.days} days · {e.author}"
    main = [Img(src=e.photo, alt=e.alt, cls="fk-thumb"),
            Span(Span(e.title, cls="fk-name"), Span(meta, cls="fk-meta"), _tags(e), cls="fk-text")]
    href = forks_url(open=e.slug) if booked else "/plan"
    head = A(*main, href=href, cls="fk-pick" + (" is-open" if e.slug == current else ""), aria_current="true" if e.slug == current else None,
             aria_label=f"Preview {e.title} in your calendar" if booked else f"{e.title}. Book a trip to apply it")
    return Div(head, A("View trip page", href=f"/trips/{e.slug}", cls="fk-link"), cls=f"fk-item fk-item-{tag}")


def list_panel(session, booked, current=""):
    mine, kept = forks_model.forked(session), forks_model.saved(session)
    blocks = [H2("Your forks", Span(str(len(mine)), cls="cal-count fk-count"), id="fk-title")]
    if mine:
        blocks += [_card(e, "fork", booked, current) for e in mine]
        blocks.append(P("Pick one to preview its plans in your empty slots. Nothing changes until you apply." if booked
                        else "Book a trip and you can drop a fork's plans into your calendar.", cls="fk-hint"))
    else:
        blocks.append(Div(Span(icon("fork", 28, 2.2), cls="fk-bigicon"), P("Nothing forked or saved yet. Fork a community trip and its plans wait here, ready for your calendar."),
                          A("Browse community trips", href="/community", cls="btn btn-primary btn-sm"), cls="fk-none"))
    if kept:
        blocks += [H2("Saved", Span(str(len(kept)), cls="cal-count fk-count"), cls="fk-sub"),
                   *[Div(_card(e, "saved", booked),
                         Form(Input(type="hidden", name="next", value=f"/trips/{e.slug}"), Button(icon("fork", 16, 2.4), "Fork it", type="submit", cls="btn btn-sm"), action="/fork", method="post", cls="fk-forkit"),
                         cls="fk-saved") for e in kept]]
    return blocks


# ---- the preview ---------------------------------------------------------------------------------------------------

def _row(x, dates):
    p = x.plan
    day = dates[p.day] if 0 <= p.day < len(dates) else None
    when = f"{day.strftime('%a')} {day.day} · " if day else f"Day {p.day + 1} · "
    when += f"{cal.fmt_time(p.start)} – {cal.fmt_time(p.end)}"
    if x.state == "have":
        note = Span("Already on your calendar", cls="fk-note fk-note-have")
    elif x.clash:
        note = Span(x.clash[0].upper() + x.clash[1:], cls="fk-note")
    else:
        note = ""
    off = x.hard or x.state == "have"
    return Label(
        Input(type="checkbox", name="pick", value=p.key, checked=x.checked or None, disabled=off or None, data_plan=p.key, cls="fk-check"),
        Span(Span(p.title, cls="fk-ptitle"), Span(when, cls="fk-when"), note, cls="fk-ptext"),
        cls=f"fk-row{' is-clash' if x.state == 'clash' else ''}{' is-have' if x.state == 'have' else ''}")


def preview_panel(entry, placements, dates):
    free = sum(1 for x in placements if x.checked)
    if not placements:
        body = [P("This trip has no timed plans to add.", cls="fk-hint")]
    else:
        body = [Form(
            Span(f"FROM {entry.title.upper()}", cls="fk-from"),
            Div(*[_row(x, dates) for x in placements], cls="fk-rows", role="group", aria_label="Plans in this fork", tabindex="0"),
            Input(type="hidden", name="slug", value=entry.slug), trip_field(),
            Button(f"Apply {free} plan{'s' if free != 1 else ''}", type="submit", id="fk-apply", cls="btn btn-ink fk-applybtn", disabled=(free == 0) or None, data_count=str(free)),
            Span("Your bookings and your crew's plans stay exactly where they are.", cls="fk-hint"),
            action="/forks/apply", method="post", id="fk-form", cls="fk-preview")]
    return [A(icon("chev-left", 16, 2.6), "All forks", href="/forks", cls="fk-back"), H2(entry.title, id="fk-title"), *body]


def applied_panel(session, ids, source):
    here = {a.id: a for a in cal.activities(session)}
    got = [here[i] for i in ids if i in here]
    who = source.author if source else "your fork"
    if not got:
        return None
    n = len(got)
    return Div(
        Span(icon("check", 20, 2.6), Span(f"Added {n} plan{'s' if n != 1 else ''} from {who}.", id="fk-done-text"), cls="fk-done-text"),
        Form(trip_field(), Input(type="hidden", name="ids", value=",".join(a.id for a in got)), Input(type="hidden", name="src", value=source.slug if source else ""), Button("Undo", type="submit", cls="fk-undo", autofocus=True, aria_describedby="fk-done-text"), action="/forks/undo", method="post"),
        cls="fk-done fk-pop", role="status")


# ---- page ----------------------------------------------------------------------------------------------------------

def signed_out():
    return page("Your forks", Section(
        Div(Span(icon("fork", 36, 2.2), cls="fk-bigicon"), H1("Your forks"),
            P("Fork a trip you love and its plans wait here, ready to drop into your calendar. Sign in to start your list."),
            A("Sign in", href=ses.signin_href("/forks"), cls="btn btn-primary"), A("Find a trip to fork", href="/community", cls="btn"), cls="fk-signedout"),
        cls="ga-soon ga-wrap"), head=HEAD)


def forks_page(session, open_slug="", applied="", source="", error="", status=200):
    booked = bool(ses.booking(session))
    entry = forks_model.entry(session, open_slug) if open_slug else None
    if entry and entry.slug not in ses.forks(session) + ses.saved(session):
        entry = None  # preview only what is in the traveler's list
    placements, dates = [], []
    if entry and booked:
        dates = cal.days(cal.trip("", ses.booking(session)))
        placements = cal.preview_fork(session, entry.trip)
    ids = _ids(applied)
    src = forks_model.entry(session, source) if source else None
    done = applied_panel(session, ids, src) if ids and booked else None
    side = preview_panel(entry, placements, dates) if entry and booked else list_panel(session, booked, entry.slug if entry else "")
    notice = Div(error, role="alert", cls="fk-error") if error else ""
    left = calendar_view(session, placements, fresh=set(ids)) if booked else calendar_empty()
    body = Section(
        Div(left, Div(done or "", notice, *side, id="fk-side", cls="fk-side card", aria_labelledby="fk-title"), cls="fk-layout", data_state="preview" if entry and booked else "list"),
        Script(src="/assets/js/forks.js", defer=True), cls="fk ga-wrap")
    out = page("Your forks", body, head=HEAD)
    return FtResponse(out, status_code=status) if status != 200 else out


def register(app):
    @app.get("/forks")
    def forks(session, open: str = "", applied: str = "", src: str = ""):
        if not ses.current_traveler(session):
            return signed_out()
        return forks_page(session, open, applied, src)

    @app.post("/forks/apply")
    def apply(session, slug: str = "", pick: list[str] = None):
        if not ses.current_traveler(session):
            return RedirectResponse("/signin?next=/forks", status_code=303)
        trip = forks_model.resolve(slug)
        if not trip or slug not in ses.forks(session) + ses.saved(session):
            return forks_page(session, error="That trip is not in your list any more.", status=409)
        try:
            added = cal.apply_fork(session, trip, [k for k in (pick or []) if _KEY.match(k)], by=trip.author)
        except cal.CalendarError as e:
            return forks_page(session, open_slug=slug, error=str(e), status=409)
        if not added:
            return RedirectResponse(forks_url(open=slug), status_code=303)
        return RedirectResponse(forks_url(applied=",".join(a.id for a in added), src=slug), status_code=303)

    @app.post("/forks/undo")
    def undo(session, ids: str = "", src: str = ""):
        if not ses.current_traveler(session):
            return RedirectResponse("/signin?next=/forks", status_code=303)
        trip = forks_model.resolve(src) if src else None
        if trip and ses.booking(session):
            cal.remove_applied(session, trip, _ids(ids), by=trip.author)
        return RedirectResponse("/forks", status_code=303)

    def trip_path(next_path):
        path = ses.safe_next(next_path, "")
        return path if ses.trip_slug(path) else "/community"

    @app.post("/save")
    def save(session, next: str = ""):
        path = trip_path(next)
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={quote(path, safe='/')}&intent=save", status_code=303)
        ses.add_save(session, path)
        return RedirectResponse(path, status_code=303)

    @app.post("/unsave")
    def unsave(session, next: str = ""):
        path = trip_path(next)
        ses.remove_save(session, path)
        return RedirectResponse(path, status_code=303)
