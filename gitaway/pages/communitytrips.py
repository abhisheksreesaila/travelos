"""Community trips at /community (F-022, F-050): trips people shared and creator itineraries.

GET /community?kid=1&pet=1&couple=1&src=creators&q=tokyo
Every filter is a plain link (or the search form's GET), so the hub works without JavaScript. Chips toggle: a lit chip's
link turns it off and keeps the others. All the facts come from gitaway.hub.
/discover (the old name, kept for old links) redirects here with its filters. The word "Discover" is reserved for deals later.
"""

from urllib.parse import urlencode

from starlette.responses import RedirectResponse
from fasthtml.common import A, Button, Div, Em, Form, H1, H2, I, Input, Label, Link, P, Script, Span

from gitaway import creatorbook as cb, hub, session as ses, showcase
from gitaway.icons import icon
from gitaway.layout import page, plan_href
from gitaway.itinerary_view import _icon
from gitaway.pages import bookview, studio

HEAD = (Link(rel="stylesheet", href="/assets/css/cv2.css"), Link(rel="stylesheet", href="/assets/css/placeart.css"), Script(src="/assets/js/shelf.js", defer=True))
FILTERS = [("kid", "Kid friendly", "sun"), ("pet", "Pet friendly", "mint"), ("couple", "Couple friendly", "bubble")]


def hub_href(tags=(), creators=False, q=""):
    params = [(k, "1") for k, _, _ in FILTERS if k in tags] + ([("src", "creators")] if creators else []) + ([("q", q)] if q else [])
    return "/community" + (f"?{urlencode(params)}" if params else "")


def chip(label, href, on, fill="", ico=""):
    return A(_icon(ico, 18, 2.2) if ico else "", label, href=href, aria_current="true" if on else None, cls="chip")


STICKER = {"Blog": "From the post", "YouTube": "From the video", "Instagram": "From Instagram"}
RIBBON = "Your trip"


def _book(c) -> cb.Book:
    """A shelf card's cover: the trip's own drawing and cloth. A sample says so on its cover."""
    return cb.Book(c.slug, c.title, c.author, c.place, [], [], cb.cloth_of(c.slug), cb.scene_of(c.place, c.title), sticker="Sample book" if not c.real else STICKER.get(c.source, ""), sample=not c.real)


def card(c, i=0):
    """One book on the shelf: its cover, who made it, how long it is. It opens as a book (/trips/<slug>/book), which plays itself. The cover names the trip once: it is the link's name."""
    return Div(Span(RIBBON, cls="ribbon") if c.mine else "",
               A(bookview.mini_cover(_book(c)), href=f"/trips/{c.slug}/book", cls="bk-open"),
               Div(Span(c.author + (f" · {c.source}" if c.source else "")), Span(f"{c.days} day{'s' if c.days != 1 else ''}", cls="hc"), cls="meta"),
               cls="bk hub-card", style=f"--i:{i};--r:{(-1.6, 1.2, -.6, 1.8, -1.1, .8, -1.4)[i % 7]}deg")


def _head(*inside, share_href=""):
    return Div(Div(Span(I(style="background:var(--see)"), "Community", cls="kicker"), H1("Trips people ", Em("have taken"), cls="disp"),
                   P("Flip through a trip as its maker lived it. Save the ones you love, and plan your own from any page."),
                   Div(A(icon("plus", 20, 2.4), "Share yours" if showcase.on() else "Publish yours", href=share_href, cls="tonal"), A("Turn a post into a book", href="/for-creators", cls="tonal"), cls="hub-cta") if share_href else ""),
               *inside, cls="sh-head")


def empty_page():
    """Off the showcase, before anyone has shared a trip (D-458): the page is in every header, so it exists and says so, with the two ways a trip gets here."""
    return page("Community trips", Div(
        _head(),
        Div(icon("fork", 28, 2.2), Div(H2("No one has shared a trip yet"),
            P("Creators turn a post into a trip readers can plan; families share theirs once they are back. The first ones show up here."),
            Div(A("For creators", href="/for-creators", cls="go"), A("Plan a trip", href=plan_href(), cls="tonal"), cls="hub-cta")),
            cls="hub-first v2-glass", role="status"), cls="shelfv"), studio.foot(), current="/community", head=HEAD, v2="cv is-results")


def hub_page(session, tags=(), creators=False, q=""):
    if not showcase.community_open():
        return empty_page()
    shown = hub.cards(session, tags=tags, creators=creators, q=q)
    on = set(tags)
    chips = [chip(label, hub_href(on ^ {k}, creators, q), k in on, fill, hub.TAGS[k][2]) for k, label, fill in FILTERS]
    if showcase.on():  # the "from a vlog" filter is for the sample creator trips; every real trip is a family's own
        chips.append(chip("From creators", hub_href(on, not creators, q), creators, "", "play"))
    search = Form(Label(icon("target", 20, 2.2), Span("Where to", cls="v2-sr"), Input(type="search", name="q", value=q, placeholder="Where to?", autocomplete="off", maxlength="40"), cls="hub-search"),
                  *[Input(type="hidden", name=k, value="1") for k in tags], *([Input(type="hidden", name="src", value="creators")] if creators else []),
                  Button("Search", type="submit", cls="tonal"), action="/community", method="get", cls="hub-form", role="search")
    filtered = bool(tags or creators or q)
    body = (Div(*[card(c, i) for i, c in enumerate(shown)], cls="shelf hub-grid") if shown else
            Div(H2("No trips match those filters"), P("Try fewer filters, or start again."), A("Show every trip", href="/community", cls="go"), cls="hub-empty v2-glass", role="status"))
    share_href = ("/share" if showcase.on() else "/trip/publish") if ses.booking(session) else showcase.planning_path()  # a trip to share, or the way to start one
    first = ("" if filtered or hub.has_shared() or not showcase.on() else
             Div(icon("fork", 28, 2.2), Div(H2("Be the first to share one"), P("These are sample books. Share yours and it shows up here for every traveler, ready to plan from."),
                                           A("Share yours", href=share_href, cls="go")), cls="hub-first v2-glass", role="status"))
    return page("Community trips", Div(
        _head(Span("Sample books: made up so you can see the shelf", cls="smp") if showcase.on() else "", share_href=share_href),
        Div(search, Div(*chips, cls="filters", role="group", aria_label="Filter trips"), cls="hub-tools"),
        P(f"{len(shown)} trip{'s' if len(shown) != 1 else ''}" + (" match" if filtered else ""), cls="hub-count", role="status") if shown else "",
        body, first, Div(Span("Written a trip up? Make it a book."), A("Paste your post", bookview.ico("arrow"), href="/for-creators", cls="go"), cls="sh-cta v2-glass"),
        cls="shelfv"), studio.foot(), current="/community", head=HEAD, v2="cv is-results")


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
