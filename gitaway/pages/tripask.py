"""What are you after? (F-241, D-560..; redrawn as v2's landing in F-250, D-610..): the search before the trip matrix, where a signed-in person with no booked trip starts.

GET  /plan/ask   the prototype's landing (docs/design/booking-v2/index.html): the sky, one sentence whose every part is a word you tap (who, from, where, the start day,
                 give or take, nights, budget, interests: gitaway/v2sentence.py, assets/js/v2.js), and "Show me the trips". No box to type in. The address may carry a search
                 (the matrix's own parameters) so a link back lands on the same words.
POST /plan/ask   Search: the words (hidden fields) are read as the matrix's own search parameters (`v2sentence.address`) and the matrix opens on them; what is wrong comes back here in
                 words. The picked interests are kept for the family (an editor or admin; a viewer searches without changing the family's settings). With `X-V2: 1` (the script's
                 own post) it answers JSON, {"to": the matrix address} or {"error": words}, so the sentence can glide up and its skeleton play before the matrix opens.

The ask is the matrix's door, so it exists where the matrix does (showcase.LITEAPI_PAGES); `showcase.planning_path()` is /plan/ask there and /trips/import elsewhere.
"""

from fasthtml.common import Button, Div, Link, P, Span
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, RedirectResponse

from gitaway import access, interests, v2sentence
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import tripmatrix

PATH = v2sentence.PATH
HEAD = (Link(rel="stylesheet", href="/assets/css/tripmatrix.css"), Link(rel="stylesheet", href="/assets/css/tripask.css"))
KICKER = "Flights + stays, one total for every place and day"
SUB = "Tap any underlined word to change it."
LANES, DAYS = 4, 5      # the skeleton's rows and columns: the look of the matrix while it is asked for, not a count of anything


def skeleton() -> Div:
    """The results before they have loaded, hidden until Search: the status, the pick bar and a grid of waiting squares, in the matrix's own look. The script shows it as the sentence glides up."""
    lane = lambda i: Div(Div(Span(cls="mx-thumb"), Div(Span(cls="mx-l-n"), Span(cls="mx-l-best"), cls="mx-nm"), cls="mx-lead mx-lh"),      # noqa: E731
                         *[Span(cls="mx-sq is-wait skeleton", style=f"grid-column: {j + 2}; --sd: {(i + j) * 0.06:.2f}s") for j in range(DAYS)], cls="mx-lane")
    head = Div(Div(Span("Start day →", cls="mx-ah"), cls="mx-lead mx-lh"), *[Span(cls="mx-day is-skel", style=f"grid-column: {j + 2}") for j in range(DAYS)], cls="mx-head")
    status = Div(Span(Span(cls="v2-spin"), Span("Pricing your trips: flights + stays"), cls="mx-st"), cls="mx-status")
    card = Div(Div(status, cls="mx-top"), Span(cls="mx-find is-skel"), Div(Div(head, *[lane(i) for i in range(LANES)], cls="mx-lanes", style=f"--n: {DAYS}"), cls="mx-scroll"), cls="mx-card")
    return Div(Div(card, cls="mx-main"), cls="mx-results", id="v2-skel", hidden=True, aria_hidden="true")


def ask_page(s=None, picked=(), problem=""):
    """The landing on a search `s` (the matrix's own defaults when none)."""
    spec = v2sentence.spec_of(s or tripmatrix.state(), picked)
    err = P(problem, cls="v2-error", id="v2-error", role="alert", **({} if problem else {"hidden": True}))
    go = Button("Show me the trips", icon("arrow-right", 22, 2.2), type="submit", cls="v2-go", id="v2-go")
    hero = Div(v2sentence.form_el(spec, Span(Span(cls="dot"), KICKER, cls="v2-kicker"), v2sentence.sentence(spec), err, go, P(SUB, cls="v2-hero-sub"), tripmatrix.import_el("ak-import")), cls="v2-hero")
    return page("What are you after?", Div(hero, skeleton(), *v2sentence.machinery(spec), cls="v2-stage", data_v2="landing"), current="/plan/matrix", head=HEAD, noindex=True, footer=False, v2=True)


def register(app):
    @app.get(PATH)
    def ask(session, to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        s = tripmatrix.state(to, home, d, r, a, k, x, nb, b)
        return ask_page(s, interests.get(session))

    @app.post(PATH)
    async def ask_search(request, session):
        form = await request.form()
        picked = interests.clean([v for v in form.getlist("i") if isinstance(v, str)])
        to, problem = v2sentence.address(form)
        scripted = request.headers.get("x-v2") == "1"
        if problem:
            if scripted:
                return JSONResponse({"error": problem}, status_code=400)
            return ask_page(tripmatrix.state(str(form.get("to") or ""), str(form.get("home") or "")), picked, problem)
        if access.can_edit(access.request_role()):
            await run_in_threadpool(interests.save, session, picked)
        return JSONResponse({"to": to}, headers={"Cache-Control": "no-store"}) if scripted else RedirectResponse(to, status_code=303)
