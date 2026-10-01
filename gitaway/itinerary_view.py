"""FastHTML components for the scrapbook itinerary page (F-014)."""

from fasthtml.common import (A, Button, Details, Div, H1, H2, H3, Img, Link, NotStr, P, Script,
                             Section, Span, Summary)

from gitaway.icons import icon
from gitaway.itineraries import STOP_LIMIT, Day, Itinerary, Stop, board_cards, day_color, safe_href
from gitaway.layout import page

THEMES = ("sunset", "pacific")
HEAD = (Link(rel="stylesheet", href="/assets/css/itinerary.css"),)

# Small icons the shared set lacks (used by the sticker tags only).
_SVG = '<svg width="22" height="22" style="--ico:1.375rem" viewBox="0 0 24 24" {a} aria-hidden="true">{p}</svg>'
_STROKE = 'fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"'
EXTRA = {
    "kid": _SVG.format(a=_STROKE, p='<circle cx="12" cy="8" r="4"/><path d="M6 21v-1a6 6 0 0 1 12 0v1"/>'),
    "clock": _SVG.format(a=_STROKE, p='<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
    "couple": _SVG.format(a=_STROKE, p='<path d="M9 19c-3-2-6-4.2-6-7.5A3.5 3.5 0 0 1 9 9.3a3.5 3.5 0 0 1 6 2.2c0 3.3-3 5.5-6 7.5Z"/>'
                                       '<path d="M15 13.5c.7-.3 1.4-.5 2.2-.5a3 3 0 0 1 3 3c0 2.6-2.7 4.4-5.2 5.5"/>'),
    "paw": _SVG.format(
        a='fill="currentColor"',
        p='<circle cx="5.5" cy="10" r="2.2"/><circle cx="9.5" cy="5.5" r="2.2"/><circle cx="14.5" cy="5.5" r="2.2"/>'
          '<circle cx="18.5" cy="10" r="2.2"/><path d="M12 11c-3 0-6 4.5-6 7 0 1.7 1.3 2.5 3 2.5 1.2 0 2-.6 3-.6s1.8.6 '
          '3 .6c1.7 0 3-.8 3-2.5 0-2.5-3-7-6-7Z"/>'),
}


def _icon(name, size=22, stroke=2.2):
    if name in EXTRA:
        return NotStr(EXTRA[name])
    try:
        return icon(name, size, stroke)
    except KeyError:
        return ""  # an unknown icon name shows no icon rather than a 500


def resolve_theme(requested, trip: Itinerary) -> str:
    """The trip record's theme, unless a valid ?theme= override is given."""
    return requested if requested in THEMES else trip.theme


def fork_href(trip):
    return f"/signin?next=/trips/{trip.slug}&intent=fork"


# ---------- hero ----------

def _tag(t):
    return Span(_icon(t.icon), t.label, cls=f"sticker fill-{t.color}" + (" ga-bob" if t.tilt == -3 else ""),
                style=f"--r:{t.tilt}deg")


def _stats(trip):
    return Div(*[Div(Span(v, cls="stat-v"), Span(label, cls="stat-l"), cls="stat") for v, label in trip.stats],
               cls="stats")


def _actions(trip):
    return Div(
        A(icon("fork", 22, 2.4), "Fork this trip", href=fork_href(trip), cls="btn btn-primary btn-hero"),
        Button(icon("share", 20), "Share", type="button", cls="btn btn-hero"),
        Button(icon("heart", 22, 2.3), type="button", cls="btn btn-round", aria_label="Save to favourites"),
        cls="hero-actions",
    )


def _source_card(src):
    href = safe_href(src.url)  # a creator's link is only ever an http(s) address
    return Div(
        Span(cls="tape"),
        Div(Img(src=src.thumb, alt=src.thumb_alt) if src.thumb else "", Span(icon("play", 16), cls="play"), cls="src-thumb"),
        Div(Span("From the vlog", cls="src-kicker"),
            Span(src.title, cls="src-title"),
            Span(src.byline, cls="src-by"),
            A(src.link_label, href=href, rel="noopener noreferrer", target="_blank", cls="src-link") if href else "",
            cls="src-body"),
        cls="source-card",
    )


def _polaroid(p, cls):
    return Div(Img(src=p.src, alt=p.alt), Span(p.caption, cls="cap"), Span(cls="tape"), cls=f"polaroid {cls}")


def _collage(trip):
    temp, sky = trip.weather
    weather = Div(icon("sun", 36, 2), Span(temp, cls="w-temp"), Span(sky, cls="w-sky"), cls="weather ga-bob",
                  style="--r:8deg")
    plane = Div(icon("plane", 28, 2), cls="plane-badge")
    route = NotStr('<svg class="squiggle" viewBox="0 0 220 250" fill="none" aria-hidden="true"><path d="M10 240 C 90 230, '
                   '60 150, 130 130 S 200 70, 170 10" stroke="currentColor" stroke-width="3" stroke-dasharray="2 10" '
                   'stroke-linecap="round"/></svg>')
    stamp = Div(trip.route, cls="stamp")
    if trip.polaroids:
        shots = [_polaroid(p, f"polaroid-{i}") for i, p in enumerate(trip.polaroids[:2])]
        return Div(*shots, route, plane, weather, stamp, cls="collage")
    stickers = [
        Span(icon("pin", 40, 2), cls="sticker-big s1 fill-mint"),
        Span(icon("waves", 44, 2), cls="sticker-big s2 fill-sky"),
        Span(icon("star", 40, 2), cls="sticker-big s3 fill-bubble"),
    ]
    return Div(*stickers, route, plane, weather, stamp, cls="collage collage-stickers")


def _hero(trip):
    underline = NotStr('<svg class="underline" viewBox="0 0 300 20" preserveAspectRatio="none" aria-hidden="true">'
                       '<path d="M4 13 C 60 3, 118 19, 176 9 S 268 5, 296 11" stroke="var(--accent-2)" stroke-width="7" '
                       'fill="none" stroke-linecap="round"/></svg>')
    return Section(
        Div(
            Div(Span(icon("pin", 16, 2.2), trip.place, cls="place-pill"), Span("Community itinerary"), cls="kicker"),
            H1(f"{trip.headline} ", Span(trip.accent, underline, cls="accent-words"), cls="hero-title"),
            P(trip.lede, cls="lede"),
            Div(*[_tag(t) for t in trip.tags], cls="tags") if trip.tags else "",
            _stats(trip),
            _actions(trip),
            _source_card(trip.source) if trip.source else "",
            cls="hero-copy",
        ),
        _collage(trip),
        cls="hero ga-wrap",
    )


# ---------- board ----------

def _mini(stop: Stop, i: int):
    return Span(Span(stop.time, cls="mini-t"), Span(stop.title, cls="mini-title"),
                cls="mini" + (" mini-booked" if stop.booked else ""), style=f"--tilt:{(-1.2, .8, -.4, 1)[i % 4]}deg")


def _board(trip):
    if len(trip.days) < 2:
        return ""
    cols = []
    for d in trip.days:
        shown, extra = board_cards(d)
        body = [_mini(s, i) for i, s in enumerate(shown)] or [Span("Free day", cls="mini mini-free")]
        if extra:
            body.append(Span(f"+{extra} more", cls="mini-more"))
        cols.append(A(
            Span(Span(f"{d.n:02d}", cls="board-n"), Span(d.date, cls="board-date"), Span(d.title, cls="board-title"),
                 cls="board-head"),
            *body, href=f"#day-{d.n}", cls=f"board-col day-{day_color(d.n)}", aria_label=f"Day {d.n}: {d.title}"))
    return Section(
        Div(Div(H2("The whole trip on one board"), Span("Tap a day to jump to its story below.", cls="sub"),
                cls="sec-head-text"),
            Div(Span("Booked", cls="key key-booked"), Span("Planned", cls="key"), cls="keys", aria_hidden="true"),
            cls="sec-head"),
        Div(*cols, cls="board", role="region", aria_label="All days of the trip", tabindex="0"),
        cls="board-sec ga-wrap",
    )


# ---------- day stories ----------

def _stop(s: Stop, last: bool):
    title = [Span(s.title, cls="stop-title")]
    if s.booked:
        title.append(Span("BOOKED", cls="tag tag-booked"))
    if s.tag:
        title.append(Span(s.tag, cls=f"tag fill-{s.tag_color}"))
    body = [Div(*title, cls="stop-head")]
    if s.meta:
        body.append(P(s.meta, cls="stop-meta"))
    if s.note:
        body.append(Span(s.note, cls="note"))
    if s.photo:
        body.append(Img(src=s.photo, alt=s.photo_alt, cls="stop-photo", loading="lazy"))
    return Div(
        Span(s.time, cls="stop-time"),
        Div(Span(_icon(s.kind, 24, 2.1), cls=f"bubble bub-{s.bubble}"), Span(cls="line" + (" line-end" if last else "")),
            cls="stop-rail"),
        Div(*body, cls="stop-body"),
        cls="stop",
    )


def _timeline(d: Day):
    if not d.stops:
        return Div(P("Free day, nothing planned", cls="free-day"),
                   P("Sleep in, wander, or ask the author what they'd add.", cls="free-sub"), cls="card story-card")
    stops = d.stops
    head, rest = stops[:STOP_LIMIT], stops[STOP_LIMIT:]
    items = [_stop(s, last=(not rest and i == len(head) - 1)) for i, s in enumerate(head)]
    if rest:
        items.append(Details(
            Summary(f"Show all {len(stops)} stops", cls="more-stops"),
            *[_stop(s, last=(i == len(rest) - 1)) for i, s in enumerate(rest)], cls="stops-more"))
    return Div(*items, cls="card story-card")


def _weather(d: Day):
    return Span(icon("sun", 20, 2), d.weather, cls="rail-weather") if d.weather else ""


def _day_story(d: Day):
    rail = Div(
        Div(Span("day", cls="badge-l"), Span(str(d.n), cls="badge-n"), cls="day-badge"),
        Span(d.date, cls="rail-date"), H3(d.title, cls="rail-title"), _weather(d), cls="day-rail")
    return Div(rail, _timeline(d), id=f"day-{d.n}", cls=f"day-story day-{day_color(d.n)}", style=f"--i:{d.n}")


def _folded(d: Day):
    card = Summary(
        Span(str(d.n), cls="fold-n"),
        Span(Span(d.date.title(), cls="fold-date"), Span(d.title, cls="fold-title"), cls="fold-text"),
        Span("Open day", cls="fold-cta fold-open"), Span("Close day", cls="fold-cta fold-close"),
        cls="fold-card")
    return Details(card, Div(_weather(d), _timeline(d), cls="fold-story"),
                   id=f"day-{d.n}", cls=f"fold day-{day_color(d.n)}", style=f"--i:{d.n}")


def _days(trip):
    open_days = [_day_story(d) for d in trip.days if not d.collapsed]
    folds = [_folded(d) for d in trip.days if d.collapsed]
    return Section(*open_days, Div(*folds, cls="folds") if folds else "", cls="days ga-wrap")


# ---------- make it yours ----------

def _yours(trip):
    who = trip.source.byline.split(" · ")[0] if trip.source else trip.author
    return Section(
        Div(
            H2("Make this trip yours"),
            P(f"Fork it into your trips, then drop the days you love into your own calendar. "
              f"The original stays exactly as {who} shared it."),
            Div(A(icon("fork", 22, 2.4), "Fork this trip", href=fork_href(trip), cls="btn btn-primary btn-hero"),
                A("Plan my own trip", href="/plan", cls="btn btn-hero"), cls="hero-actions"),
            cls="yours-copy"),
        Div(Div(cls="fork-back"),
            Div(Span("YOUR FORKS", cls="fork-kicker"), Span(trip.title, cls="fork-title"),
                Span(Span("Kid friendly", cls="tag fill-sun"), Span(f"{len(trip.days)} days", cls="tag fill-mint"),
                     cls="fork-tags"),
                Span("Apply to my trip", cls="fork-apply"), cls="fork-front"),
            cls="fork-stack", aria_hidden="true"),
        cls="yours ga-wrap",
    )


# ---------- skeleton ----------

def skeleton(trip: Itinerary):
    hero = Section(
        Div(Div(cls="skeleton sk-pill"), Div(cls="skeleton sk-title"), Div(cls="skeleton sk-title sk-short"),
            Div(cls="skeleton sk-line"), Div(cls="skeleton sk-line sk-short"),
            Div(*[Div(cls="skeleton sk-stat") for _ in trip.stats], cls="stats"),
            Div(Div(cls="skeleton sk-btn"), Div(cls="skeleton sk-btn"), cls="hero-actions"),
            cls="hero-copy"),
        Div(cls="skeleton sk-collage"),
        cls="hero ga-wrap")
    board = Section(Div(*[Div(cls="skeleton sk-col") for _ in trip.days], cls="board"), cls="board-sec ga-wrap")
    return Div(hero, board, aria_busy="true", aria_label="Loading the itinerary", role="status", cls="skeleton-page")


# ---------- assembly ----------

SCRIPT = Script("""
(function () {
  function openTarget() {
    openId(location.hash);
  }
  function openId(hash) {
    var id = hash ? hash.slice(1) : '';
    try { id = decodeURIComponent(id); } catch (e) { return; }
    var el = id && document.getElementById(id);
    if (el && el.tagName === 'DETAILS') el.open = true;
  }
  addEventListener('hashchange', openTarget);
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a.board-col');
    if (a) openId(a.getAttribute('href'));
  });
  openTarget();
})();
""")


def itinerary_body(trip: Itinerary, loading: bool = False):
    if loading:
        return skeleton(trip)
    return Div(_hero(trip), _board(trip), _days(trip), _yours(trip), SCRIPT, cls="itinerary")


def itinerary_page(trip: Itinerary, theme=None, loading: bool = False):
    return page(trip.title, itinerary_body(trip, loading), theme=resolve_theme(theme, trip), head=HEAD)
