"""Make this a trip (F-210): a booking search becomes the family's trip and opens on the cockpit. The model is gitaway/tripstart.py.

POST /trip/new   from /plan's lanes (`place`, `d`, `r`, `a`, `k`, `home`, `iata`; a sample city `to`, or `from`, `n`, `k1`.. are read too).
                 Made: 303 to /trip/cockpit. Signed out: 303 to sign-in, which comes back to the GET below. A search that does not hold up: 303 to /plan, which says
                 what is wrong. A viewer never gets here (gitaway/access.py refuses every write a viewer makes).
GET  /trip/new   the finish card after a sign-in: the search in words and the one button. It writes nothing (a link must not make a trip).
"""

from urllib.parse import quote, urlencode

from fasthtml.common import A, Button, Div, Form, H1, Input, Link, Main, P, Span
from fasthtml.core import FtResponse
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from gitaway import access, importer, session as ses, tripstart
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import plan_search

HEAD = (Link(rel="stylesheet", href="/assets/css/plansearch.css"),)
COCKPIT = "/trip/cockpit"


def _params(request_params) -> dict:
    return {k: v for k, v in request_params.items() if isinstance(v, str)}


def _back_to_booking(params) -> RedirectResponse:
    """The booking lanes, filled with what was sent, so they say what is wrong with it."""
    keep = ("place", "to", "focus", "home", "from", "d", "r", "a", "k", "iata")
    words = {k: params[k] for k in keep if params.get(k)}
    if not words.get("k") and params.get("n"):        # a count with one age picker per kid
        words["k"] = plan_search.kids_from(params["n"], [params.get(f"k{i}", "") for i in range(1, plan_search.MAX_KIDS + 1)])
    if words.get("from") and not words.get("home"):
        words["home"] = words.pop("from")
    return RedirectResponse("/plan?" + urlencode(words), status_code=303)


def finish_page(search, words, role):
    can = access.can_edit(role)
    who = f"{plan_search.date_label(search)} · {plan_search.summary(search)}"
    return page("Make this a trip", Main(Div(
        Span("MAKE THIS A TRIP", cls="eyebrow"), H1(f"Trip to {search.place.name}", cls="ps-title"),
        P(who, cls="ps-lede", id="tn-lede"),
        P("Your family gets a trip with these dates and who is coming, and a plan for each day. Nothing is booked: you book on the partners' sites.", cls="ps-fine"),
        Form(*[Input(type="hidden", name=k, value=str(v)) for k, v in words.items()],
             Button(icon("arrow-right", 20, 2.4), "Make this a trip", type="submit", cls="btn btn-ink"),
             A("Back to booking", href="/plan?" + urlencode(words), cls="btn btn-sm"),
             action="/trip/new", method="post", cls="ps-from", id="tn-make") if can else
        Div(P(access.VIEWER_MESSAGE, cls="ps-fine", role="note"), A("Back to booking", href="/plan?" + urlencode(words), cls="btn btn-sm"), cls="ps-from"),
        cls="ps ga-wrap"), id="trip-new"), head=HEAD)


def register(app):
    @app.get("/trip/new")
    def trip_new_page(request, session):
        params = _params(request.query_params)
        search, errors = tripstart.read(params)
        if errors or search is None:
            return _back_to_booking(params)
        words = tripstart.words(search, params.get("iata", ""))
        if not ses.current_traveler(session):
            return RedirectResponse("/signin?next=" + quote("/trip/new?" + urlencode(words), safe=""), status_code=303)
        return finish_page(search, words, access.request_role())

    @app.post("/trip/new")
    async def trip_new(request, session):
        params = _params(await request.form())
        search, errors = tripstart.read(params)
        if errors or search is None:
            return _back_to_booking(params)
        words = tripstart.words(search, params.get("iata", ""))
        if not ses.current_traveler(session):
            return RedirectResponse("/signin?next=" + quote("/trip/new?" + urlencode(words), safe=""), status_code=303)
        try:
            await run_in_threadpool(tripstart.start, session, search)      # database writes: off the event loop (tests/test_event_loop.py)
        except importer.SaveError as e:
            return FtResponse(page("Make this a trip", Main(Div(H1("We could not make that trip", cls="ps-title"), P(str(e), cls="ps-fine", role="alert"),
                                                                 A("Back to booking", href="/plan?" + urlencode(words), cls="btn btn-sm"), cls="ps ga-wrap")), head=HEAD),
                              status_code=409)
        return RedirectResponse(COCKPIT, status_code=303)
