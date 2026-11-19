"""Guides (F-262, D-710..), the hub where what other travellers did lives: /guides (it was Community trips at /community and, for makers, /for-creators), drawn as docs/design/guides-v2/index.html.

GET  /guides                    the hub: search a place (with autocomplete over the places GitAway knows, /plan/ask/suggest), filters for what the guides' data supports (who it suits, how long: there is no
                                season or budget in a guide, so there are no such filters), the popular guides (the published creator trips; the sample ones, labelled, on the showcase), "Make a guide"
                                and the signed-in person's own drafts. Every filter is a plain link (or the search form's GET), so the hub works without script.
GET  /guides/make               make a guide from your blog post: the paste box and the magic import (gitaway/pages/forcreators.py, studio.py), landing in the guide
POST /guides/make/trip          make a guide from your planned trip: the calendar becomes a draft (creatordraft.from_plan: flights and stays private), then the guide's editor
GET  /community, /discover, /for-creators   301 to the guide hub (the old filters carry over)

The page of one guide is gitaway/pages/guidepage.py.
"""

from urllib.parse import urlencode

from fasthtml.common import A, Button, Div, Em, Form, H1, H2, H3, Img, Input, Label, Li, Link, P, Script, Span, Ul
from fasthtml.core import FtResponse
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from gitaway import community, creatorbook as cb, creatordraft as cd, draftjobs as dj, hub, session as ses, showcase
from gitaway.hub import HubError
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import bookview, studio
from gitaway.pages.forcreators import HEAD_LINE

PATH = "/guides"
HEAD = (Link(rel="stylesheet", href="/assets/css/cv2.css"), Link(rel="stylesheet", href="/assets/css/placeart.css"), Link(rel="stylesheet", href="/assets/css/guides.css"),
        Script(src="/assets/js/guides.js", defer=True))
WHO = (("kid", "Families"), ("couple", "Couples"), ("pet", "With a pet"))
LENGTHS = (("weekend", "A weekend", 1, 2), ("short", "3 to 4 days", 3, 4), ("week", "A week or more", 5, 99))
SOURCE = {"Blog": "A blog post", "YouTube": "A video", "Instagram": "An Instagram post"}


def href(who="", length="", q="") -> str:
    params = [(k, v) for k, v in (("who", who), ("len", length), ("q", q)) if v]
    return PATH + (f"?{urlencode(params)}" if params else "")


def chip(label, to, on) -> A:
    return A(label, href=to, aria_current="true" if on else None, cls="fchip")


def guides(session, who="", length="", q="") -> list:
    """The hub's cards: every published trip (a creator's guide, or a family's own, which keeps its trip page) and the samples on the showcase, labelled, that match what is asked. `who` is one of
    hub.TAGS, `length` one of LENGTHS, `q` a place or a word of the title. Most planned-from first, then the rest in the order the hub lists them."""
    low = [(a, b) for k, _, a, b in LENGTHS if k == length]
    out = [c for c in hub.cards(session, tags=(who,) if who in hub.TAGS else (), q=q) if not low or low[0][0] <= c.days <= low[0][1]]
    return sorted(out, key=lambda c: -community.fork_count(c.slug) if c.real else 0)


def art(c) -> Div:
    if c.photo:
        return Div(Img(src=c.photo, alt=c.alt, loading="lazy"), cls="art")
    return Div(bookview.drawing(cb.scene_of(c.place, c.title), f"A drawing of {c.place}, not a photograph"), cls="art")


def card(c, i=0) -> A:
    planned = community.fork_count(c.slug) if c.real else 0
    by = Div(Span(c.author[:1].upper() or "?", cls="g-av", aria_hidden="true"), Span(c.author, cls="g-by"), Span(SOURCE.get(c.source, c.source) if c.source else "", cls="g-host2"),
             Span(f"{planned} planned from it", cls="n") if planned else "", cls="by")
    meta = Div(Span(icon("calendar", 16, 2), f"{c.days} day{'s' if c.days != 1 else ''}"), *[Span(icon("users", 16, 2), dict(WHO)[k]) for k in c.tags if k in dict(WHO)][:2], cls="meta")
    return A(Div(art(c), Span("Sample", cls="smp") if not c.real else "", Span(f"{c.days} day{'s' if c.days != 1 else ''}", cls="dz"), Span("Yours", cls="dz mine") if c.mine else "", cls="art-w"),
             Div(Span(c.place, cls="g-kick"), H3(c.title), meta, by, cls="bd"), href=f"/trips/{c.slug}", cls="gcard", style=f"--i:{i}")


def make_panel(session) -> Div:
    """"Make a guide", two ways in. From a planned trip needs a signed-in family with a trip; pasting a blog post needs only the page that does it."""
    me = ses.current_traveler(session)
    trip = ses.booking(session) if me else None
    if trip:
        from_trip = Form(Button(Span(icon("calendar", 22, 2), cls="mk-ic"), Span(Span("From your planned trip", cls="mk-t"), Span("Your calendar becomes the draft. Your flights and stays stay private.", cls="mk-s")),
                                icon("chev-right", 20, 2.2), type="submit", cls="mk"), action="/guides/make/trip", method="post", id="mk-trip")
    else:
        from_trip = A(Span(icon("calendar", 22, 2), cls="mk-ic"), Span(Span("From your planned trip", cls="mk-t"),
                                                                       Span("Book a trip first: its itinerary becomes the draft." if me else "Sign in, book a trip, and its itinerary becomes the draft.", cls="mk-s")),
                      icon("chev-right", 20, 2.2), href=showcase.planning_path() if me else ses.signin_href(PATH), cls="mk", id="mk-trip")
    paste = A(Span(icon("link", 22, 2), cls="mk-ic"), Span(Span("Paste your blog post", cls="mk-t"), Span("We lay it out; your words and your own links stay yours.", cls="mk-s")),
              icon("chev-right", 20, 2.2), href=PATH + "/make", cls="mk", id="mk-paste")
    return Div(Span("Your turn", cls="g-eyebrow"), H2("Send a postcard"), P(HEAD_LINE, " Your trip becomes a postcard people plan, book and take, with your own links. Two ways in:"), from_trip, paste, cls="make v2-glass", id="make")


def yours(session):
    """The signed-in person's own drafts and published guides."""
    me = ses.current_traveler(session)
    rows = [r for r in dj.listing(me.id) if r["kind"] == "draft"] if me else []
    if not rows:
        return ""
    return Div(Span("Your postcards", cls="g-eyebrow"), Ul(*[Li(A(Span(r["title"], cls="mk-t"), Span("Published" if r["status"] == "published" else "Draft", cls="st"), href=f"/creators/import/{r['id']}/guide")) for r in rows[:6]],
                                                       cls="mine-l"), A("All my drafts", href="/creators/drafts", cls="g-all"), cls="mine v2-glass", id="mine")


def hub_page(session, who="", length="", q="", error="", status=200):
    shown = guides(session, who, length, q)
    filtered = bool(who or length or q)
    search = Form(Label(icon("search", 22, 2), Span("Search a place", cls="v2-sr"),
                        Input(type="search", name="q", id="gh-q", value=q, placeholder="Search a place: Big Sur", autocomplete="off", maxlength="40", role="combobox", aria_expanded="false",
                              aria_controls="gh-list", aria_autocomplete="list"), cls="gh-search"),
                  *[Input(type="hidden", name=k, value=v) for k, v in (("who", who), ("len", length)) if v], Ul(id="gh-list", cls="ak-list v2-glass", role="listbox", aria_label="Places", hidden=True),
                  action=PATH, method="get", role="search", id="gh-form", data_suggest="/plan/ask/suggest")
    filters = Div(Div(Span("Who", cls="flab"), *[chip(label, href("" if who == k else k, length, q), who == k) for k, label in WHO], cls="fgroup", role="group", aria_label="Who it suits"),
                  Div(Span("Length", cls="flab"), *[chip(label, href(who, "" if length == k else k, q), length == k) for k, label, _, _ in LENGTHS], cls="fgroup", role="group", aria_label="How long"), cls="gh-filters")
    first = ("" if filtered or hub.has_shared() or not showcase.on() else
             Div(icon("fork", 28, 2.2), Div(H2("Be the first to share one"), P("These are sample postcards. Make yours and it shows up here for every traveler, ready to plan from."), A("Send a postcard", href=PATH + "/make", cls="go")),
                 cls="gh-first v2-glass", role="status"))
    body = (Div(*[card(c, i) for i, c in enumerate(shown)], cls="gh-grid") if shown else
            Div(H2("No postcards match that" if filtered else "No postcards yet"), P("Try fewer filters, or another place." if filtered else "Creators turn a post or a trip into a postcard; the first ones show up here."),
                A("Show every postcard", href=PATH, cls="go") if filtered else A("Send a postcard", href=PATH + "/make", cls="go"), cls="gh-empty v2-glass", role="status"))
    hero = Div(Span("Postcards · from people who went", cls="g-kick"), H1("See what people did, ", Em("then make it yours."), cls="disp"),
               P("Real trips laid out to scan in seconds: the days, the stops, the times, what it cost, and the tips."), search, filters, cls="gh-hero")
    head = Div(H2("Popular postcards"), Span(f"{len(shown)} postcard{'s' if len(shown) != 1 else ''}" + (" match" if filtered else ""), cls="n", role="status"), cls="gh-head")
    return FtResponse(page("Postcards", Div(hero, Div(Div(head, P(error, role="alert", cls="v2-error", id="mk-error") if error else "", body, first, cls="gh-main"), Div(make_panel(session), yours(session), cls="gh-side"), cls="gh-body"),
                                         Span("Sample postcards: made up so you can see how they read", cls="smp g-smp") if showcase.on() else "", cls="gh"),
                       studio.foot(), current=PATH, head=HEAD, v2="cv g is-results", description="Postcards from other travellers: real trips laid out stop by stop to plan from."), status_code=status)


def register(app):
    @app.get(PATH)
    def hub_route(session, who: str = "", len: str = "", q: str = ""):      # noqa: A002 - the address's own word
        return hub_page(session, who if who in hub.TAGS else "", len if len in {k for k, *_ in LENGTHS} else "", " ".join(q.split())[:40])

    @app.get("/community")
    @app.get("/discover")
    def community_old(kid: str = "", pet: str = "", couple: str = "", q: str = ""):
        who = next((k for k, v in (("kid", kid), ("pet", pet), ("couple", couple)) if v), "")
        return RedirectResponse(href(who, "", " ".join(q.split())[:40]), status_code=301)

    @app.get("/for-creators")
    def for_creators_old():
        return RedirectResponse(PATH, status_code=301)

    @app.post(PATH + "/make/trip")
    async def make_from_trip(session):
        """From your planned trip: the calendar becomes a draft (flights and stays kept private), then the guide's own page where it is edited and published. A draft needs no family write, so every member may."""
        me = ses.current_traveler(session)
        if not me:
            return RedirectResponse(ses.signin_href(PATH), status_code=303)
        if not ses.booking(session):
            return RedirectResponse(showcase.planning_path(), status_code=303)
        try:
            d = await run_in_threadpool(cd.from_plan, me.id, session, me.name)
        except HubError as e:
            return hub_page(session, error=str(e), status=422)
        return RedirectResponse(f"/creators/import/{d['id']}/guide", status_code=303)
