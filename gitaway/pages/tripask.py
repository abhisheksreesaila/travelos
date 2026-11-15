"""What are you after? (F-241, D-560..): the search before the trip matrix, where a signed-in person with no booked trip starts.

GET  /plan/ask   one big ask like a search engine: a sentence box ("A family of 4, SFO to San Diego, Dec 12 to 16"), tap-to-pick interests (gitaway/interests.py), and example
                 sentences to tap. On Search the page shows a skeleton of the matrix (lanes and days, shimmering) while the browser opens the matrix.
POST /plan/ask   Search: the sentence is read by gitaway/tripsentence.py (plain rules, guesses nothing) and the matrix opens on what it said; a sentence with no place comes back
                 here with the problem said in place. The picked interests are stored for the family (an editor or admin; a viewer searches without changing the family's settings).

The ask is the matrix's door, so it exists where the matrix does (showcase.LITEAPI_PAGES); `showcase.planning_path()` is /plan/ask there and /trips/import elsewhere.
"""

from datetime import timedelta

from fasthtml.common import A, Button, Div, Form, H1, Input, Label, Link, P, Script, Span
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from gitaway import access, firstrun, interests, session as ses, tripsentence
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import tripmatrix
from gitaway.partners import places

PATH = "/plan/ask"
HEAD = (Link(rel="stylesheet", href="/assets/css/tripask.css"), Script(src="/assets/js/tripask.js", defer=True))
NO_PLACE = "I could not find a place in that. Say where to, like “SFO to San Diego, Dec 12 to 16”."
PLACEHOLDER = "A family of 4, SFO to San Diego, Dec 12 to 16"
SAMPLE_TRIPS = (("A family of 4", "SFO", "San Diego"), ("Two of us", "SFO", "Lake Tahoe"), ("A family of 3", "SFO", "Orlando"))      # who, from, to: places the matrix prices on the showcase


def examples() -> list:
    """Sentences to tap, each one the app's own words (a test reads every one back): the matrix's own default dates, a Saturday four weeks out for four nights."""
    first, last = tripmatrix._default_dates()
    when = f"{first:%b} {first.day} to {last.day}" if first.month == last.month else f"{first:%b} {first.day} to {last:%b} {last.day}"
    return [f"{who}, {home} to {to}, {when}" for who, home, to in SAMPLE_TRIPS]


def destination(text: str):
    """(the matrix address, "") for a sentence, or ("", what is wrong in words). A place is the one thing it needs; dates it does not read are the matrix's own defaults."""
    ask = tripsentence.read(text)
    if not ask.place:
        return "", NO_PLACE
    s = tripmatrix.state()
    if ask.depart and ask.return_:
        to, problems = tripmatrix.from_sentence(text, s)
        return (to, "") if to else ("", " ".join(problems))
    place = places.resolve(ask.place)
    if not (place.known and place.iata):
        return "", tripmatrix.MISSING["airport"]
    blocked = [tripmatrix.MISSING[x] for x in ask.unread if x not in ("place", "dates")]
    if blocked:
        return "", " ".join(blocked)
    return tripmatrix.href(s, to=place.name, home=ask.origin or s.home, a=ask.adults, k=",".join(map(str, ask.kid_ages))), ""


def chip(key, label, ico, kind, on) -> Label:
    return Label(Input(type="checkbox", name="i", value=key, checked=on), Span(icon(ico, 20, 2.2), cls="ak-chip-i"), Span(label), cls=f"ak-chip {kind}")


def skeleton() -> Div:
    """The matrix before it has loaded: a place's name, then a row of days, three times. Shown on Search, never to a screen reader (the button says it is searching)."""
    lane = lambda: Div(Div(cls="ak-sk-name skeleton"), Div(*[Div(cls="ak-sk-day skeleton") for _ in range(5)], cls="ak-sk-days"), cls="ak-sk-lane")      # noqa: E731
    return Div(*[lane() for _ in range(3)], cls="ak-skel", id="ak-skel", aria_hidden="true")


def ask_page(typed="", picked=(), problem=""):
    err = P(problem, cls="ak-error", id="ak-error", role="alert") if problem else ""
    field = Input(type="text", name="q", value=typed, placeholder=PLACEHOLDER, autocomplete="off", autocapitalize="sentences", maxlength=tripsentence.MAX_TEXT, cls="ak-q", id="ak-q",
                  aria_label="Where, when and who", aria_describedby="ak-error" if problem else None, aria_invalid="true" if problem else None, enterkeyhint="search")
    form = Form(
        H1("What are you after?", cls="ak-title"),
        P("Say where and when, then tap what you love. We line up the whole trip for you.", cls="ak-sub"),
        Div(field, Button(icon("arrow-right", 22, 2.6), Span("Search"), type="submit", cls="btn btn-primary ak-go", id="ak-go"), cls="ak-box"),
        err,
        Div(*[chip(*c, on=c[0] in picked) for c in interests.LIST], cls="ak-chips", role="group", aria_label="What you love"),
        Div(*[Button(t, type="button", cls="ak-ex", data_say=t) for t in examples()], cls="ak-exs", role="group", aria_label="Ideas to try"),
        A("Already booked? Bring your trip in", href=firstrun.IMPORT, cls="ak-import", id="ak-import") if ses.request_traveler() else "",
        action=PATH, method="post", cls="ak", id="ak")
    return page("What are you after?", Div(form, skeleton(), cls="ak-wrap"), current="/plan/matrix", head=HEAD, noindex=True, footer=False)


def register(app):
    @app.get(PATH)
    def ask(session, q: str = ""):
        return ask_page(q, interests.get(session))

    @app.post(PATH)
    async def ask_search(request, session):
        form = await request.form()
        text = str(form.get("q") or "")[:tripsentence.MAX_TEXT]
        picked = interests.clean([v for v in form.getlist("i") if isinstance(v, str)])
        to, problem = destination(text)
        if problem:
            return ask_page(text, picked, problem)
        if access.can_edit(access.request_role()):
            await run_in_threadpool(interests.save, session, picked)
        return RedirectResponse(to, status_code=303)
