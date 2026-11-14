"""Community trips at /community (F-022, F-050): trips people shared and creator itineraries.

GET /community?kid=1&pet=1&couple=1&src=creators&q=tokyo
Every filter is a plain link (or the search form's GET), so the hub works without JavaScript. Chips toggle: a lit chip's
link turns it off and keeps the others. All the facts come from gitaway.hub.
/discover (the old name, kept for old links) redirects here with its filters. The word "Discover" is reserved for deals later.
"""

import re
from urllib.parse import urlencode

from starlette.responses import RedirectResponse
from fasthtml.common import A, Button, Div, Form, H1, H2, Img, Input, Label, Link, P, Section, Span

from gitaway import hub, session as ses, showcase
from gitaway.icons import icon
from gitaway.layout import page, plan_href
from gitaway.itinerary_view import _icon

HEAD = (Link(rel="stylesheet", href="/assets/css/hub.css"),)
TILTS = (-1, 1, -0.5, 0.8, -1.2, 0.6)
FILTERS = [("kid", "Kid friendly", "sun"), ("pet", "Pet friendly", "mint"), ("couple", "Couple friendly", "bubble")]


def hub_href(tags=(), creators=False, q=""):
    params = [(k, "1") for k, _, _ in FILTERS if k in tags] + ([("src", "creators")] if creators else []) + ([("q", q)] if q else [])
    return "/community" + (f"?{urlencode(params)}" if params else "")


def chip(label, href, on, fill="", ico=""):
    return A(_icon(ico, 18, 2.2) if ico else "", label, href=href, aria_current="true" if on else None, cls=f"hub-chip{' fill-' + fill if fill else ''}")


def _stamp(place):
    """The postcard's stamp: the place's initials (Los Angeles is LA) or its first three letters; drawn, so it is hidden from screen readers."""
    words = [w for w in re.split(r"[\s,]+", place or "") if w]
    return ("".join(w[0] for w in words[:2]) if len(words) > 1 else (words[0][:3] if words else "")).upper()


def _sky(*inside, cls=""):
    """The postcard sky: a sun and two clouds, drawn in CSS, behind whatever is inside."""
    return Section(Span(cls="hub-sun", aria_hidden="true"), Span(cls="hub-cloud hub-cloud-1", aria_hidden="true"), Span(cls="hub-cloud hub-cloud-2", aria_hidden="true"),
                   Div(*inside, cls="hub-hero-in ga-wrap"), cls=f"hub-hero {cls}".strip())


def card(c, i=0):
    tint = hub.TAGS[c.tags[0]][1] if c.tags else "sun"
    photo = Img(src=c.photo, alt=c.alt, loading="lazy") if c.photo else Span(icon("pin", 44, 2), cls="hub-pin")
    badges = [Span(c.source, cls="hub-badge hub-badge-src")] if c.source else []
    stamp = Span(_stamp(c.place), Span(icon("fork", 14, 2.4)), cls="hub-stamp", aria_hidden="true")
    count = Span("Your trip", cls="hub-badge hub-badge-forks") if c.mine else "" if c.real else Span(f"{c.forks} forks", cls="hub-badge hub-badge-forks")   # a real trip has no sample fork count
    return A(
        Div(photo, *badges, stamp, count, cls=f"hub-photo tint-{tint}"),
        Div(Span(c.title, cls="hub-title"),
            Span(f"{c.place} · {c.days} days · {c.author}", cls="hub-meta"),
            Span(*[Span(hub.TAGS[k][0], cls=f"tag fill-{hub.TAGS[k][1]}") for k in c.tags], cls="hub-tags") if c.tags else "",
            Span("Plan this trip", icon("chev-right", 16, 2.6), cls="hub-plan"),
            cls="hub-info"),
        href=f"/trips/{c.slug}", cls="hub-card", style=f"--tilt:{TILTS[i % len(TILTS)]}deg")


def empty_page():
    """Off the showcase, before anyone has shared a trip (D-458): the page is in every header, so it exists and says so, with the two ways a
    trip gets here."""
    return page("Community trips", Div(
        _sky(Span(icon("fork", 16, 2.4), "Trips others took", cls="hub-eyebrow"), H1("Community trips"),
             P("Trips shared by families and creators, ready to plan for your own dates.", cls="hub-lede"), cls="hub-head"),
        Div(Div(icon("fork", 28, 2.2), Div(H2("No one has shared a trip yet"),
            P("Creators turn a post into a trip readers can plan; families share theirs once they are back. The first ones show up here."),
            Div(A("For creators", href="/for-creators", cls="btn btn-primary btn-sm"), A("Plan a trip", href=plan_href(), cls="btn btn-sm"), cls="hub-cta")),
            cls="hub-first card", role="status"), cls="hub-body ga-wrap"),
        cls="hub"), current="/community", head=HEAD)


def _ctas(share_href):
    return Div(A(icon("plus", 20, 2.4), "Share yours" if showcase.on() else "Publish yours", href=share_href, cls="btn btn-primary"),
               *([A(icon("play", 20, 2.2), "Turn a link into a trip", href="/creators", cls="btn")] if showcase.on() else [A("For creators", href="/for-creators", cls="btn")]), cls="hub-cta")


def hub_page(session, tags=(), creators=False, q=""):
    if not showcase.community_open():
        return empty_page()
    shown = hub.cards(session, tags=tags, creators=creators, q=q)
    on = set(tags)
    chips = [chip(label, hub_href(on ^ {k}, creators, q), k in on, fill, hub.TAGS[k][2]) for k, label, fill in FILTERS]
    if showcase.on():  # the "from a vlog" filter is for the sample creator trips; every real trip is a family's own
        chips.append(chip("From creators", hub_href(on, not creators, q), creators, "", "play"))
    search = Form(
        Label(icon("target", 20, 2.2), Span("Where to", cls="sr-only"),
              Input(type="search", name="q", value=q, placeholder="Where to?", autocomplete="off", maxlength="40"), cls="hub-search"),
        *[Input(type="hidden", name=k, value="1") for k in tags],
        *([Input(type="hidden", name="src", value="creators")] if creators else []),
        Button("Search", type="submit", cls="btn btn-sm"),
        action="/community", method="get", cls="hub-form", role="search")
    filtered = bool(tags or creators or q)
    body = (Div(*[card(c, i) for i, c in enumerate(shown)], cls="hub-grid") if shown else
            Div(H2("No trips match those filters"), P("Try fewer filters, or start again."),
                A("Show every trip", href="/community", cls="btn btn-primary btn-sm"), cls="hub-empty card", role="status"))
    share_href = ("/share" if showcase.on() else "/trip/publish") if ses.booking(session) else "/start"  # a trip to share, or the way to start one
    first = ("" if filtered or hub.has_shared() or not showcase.on() else
             Div(icon("fork", 28, 2.2), Div(H2("Be the first to share one"),
                 P("These are sample trips. Share yours and it shows up here for every traveler, ready to fork."),
                 A("Share yours", href=share_href, cls="btn btn-primary btn-sm")), cls="hub-first card", role="status"))
    return page("Community trips", Div(
        _sky(Span(icon("fork", 16, 2.4), "Trips others took", cls="hub-eyebrow"), H1("Community trips"),
             P("Trips shared by travelers and creators. Fork one into your calendar.", cls="hub-lede"),
             _ctas(share_href), search, Div(*chips, cls="hub-chips", role="group", aria_label="Filter trips"),
             cls="hub-head"),
        Div(P(f"{len(shown)} trip{'s' if len(shown) != 1 else ''}" + (" match" if filtered else ""), cls="hub-count", role="status") if shown else "",
            body, first,
            Div(H2("Back from somewhere wonderful?"), _ctas(share_href), cls="hub-share"),
            cls="hub-body ga-wrap"),
        cls="hub"), current="/community", head=HEAD)


def register(app):
    @app.get("/community")
    def community(session, kid: str = "", pet: str = "", couple: str = "", src: str = "", q: str = ""):
        tags = tuple(k for k, v in (("kid", kid), ("pet", pet), ("couple", couple)) if v)
        return hub_page(session, tags, src == "creators", " ".join(q.split())[:40])

    @app.get("/discover")
    def discover(request):
        """The old name: a permanent redirect that keeps the query filters."""
        query = request.url.query
        return RedirectResponse("/community" + (f"?{query}" if query else ""), status_code=301)
