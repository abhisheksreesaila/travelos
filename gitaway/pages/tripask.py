"""Where would you like to go? (F-241, D-560..; v2's landing F-250; a soft search box since F-257, D-660..): the search before the trip matrix, where a signed-in person with no booked trip starts.

GET  /plan/ask          one calm line, one soft box and Search over the v2 sky (assets/js/v2ask.js, assets/css/tripask.css). Typing shows an autocomplete of the places a search can price and of
                        the who and when that complete the sentence (gitaway/asksuggest.py); the interests are optional chips under the box. The address may carry a search (the matrix's own
                        parameters, or just `to`) so a link in lands with the box filled. The results page keeps its tappable sentence (gitaway/v2sentence.py, assets/js/v2.js).
GET  /plan/ask/suggest  ?q= the autocomplete as JSON, {"items": [...], "say": words}: only known places, never a guess.
POST /plan/ask          Search: the box's sentence `q` (asksuggest.search), or the results sentence's own words (hidden fields, `v2sentence.address`), is read as the matrix's search parameters and the
                        matrix opens on them; what is wrong comes back in words. The picked interests are kept for the family (an editor or admin; a viewer searches without changing the family's
                        settings). With `X-V2: 1` (the script's own post) it answers JSON, {"to": the matrix address} or {"error": words}, so the box can glide up and the skeleton play first.

The ask is the matrix's door, so it exists where the matrix does (showcase.LITEAPI_PAGES); `showcase.planning_path()` is /plan/ask there and /trips/import elsewhere.
"""

from urllib.parse import quote

from fasthtml.common import A, Button, Div, Form, H1, Input, Label, Link, P, Script, Span, Ul
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, RedirectResponse

from gitaway import access, asksuggest, interests, v2sentence
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import tripmatrix

PATH = v2sentence.PATH
SUGGEST = PATH + "/suggest"
HEAD = (Link(rel="stylesheet", href="/assets/css/tripmatrix.css"), Link(rel="stylesheet", href="/assets/css/tripask.css"), Script(src="/assets/js/v2ask.js", defer=True))
ASK = "Where would you like to go?"
SUB = "Start with a place. We add who is coming and when, then price the whole trip: flights and stays, every start day."
PLACEHOLDER = "Try “San Diego” or “a family of 4 in Santa Barbara”"
SHORT_PLACEHOLDER = "Try “Tahoe with kids”"      # a phone's box shows about 22 letters (overnight walk 2026-11-17: the long one was cut mid-word)
LANES, DAYS = 4, 5      # the skeleton's rows and columns: the look of the matrix while it is asked for, not a count of anything


def skeleton() -> Div:
    """The results before they have loaded, hidden until Search: the status, the pick bar and a grid of waiting squares, in the matrix's own look. The script shows it as the box glides up."""
    lane = lambda i: Div(Div(Span(cls="mx-thumb"), Div(Span(cls="mx-l-n"), Span(cls="mx-l-best"), cls="mx-nm"), cls="mx-lead mx-lh"),      # noqa: E731
                         *[Span(cls="mx-sq is-wait skeleton", style=f"grid-column: {j + 2}; --sd: {(i + j) * 0.06:.2f}s") for j in range(DAYS)], cls="mx-lane")
    head = Div(Div(Span("Start day →", cls="mx-ah"), cls="mx-lead mx-lh"), *[Span(cls="mx-day is-skel", style=f"grid-column: {j + 2}") for j in range(DAYS)], cls="mx-head")
    status = Div(Span(Span(cls="v2-spin"), Span("Pricing your trips: flights + stays"), cls="mx-st"), cls="mx-status")
    card = Div(Div(status, cls="mx-top"), Span(cls="mx-find is-skel"), Div(Div(head, *[lane(i) for i in range(LANES)], cls="mx-lanes", style=f"--n: {DAYS}"), cls="mx-scroll"), cls="mx-card")
    return Div(Div(card, cls="mx-main"), cls="mx-results", id="v2-skel", hidden=True, aria_hidden="true")


def chip(key, label, ico, picked) -> Label:
    """An interest: a checkbox drawn as a chip, so it works without script and is a 48px target."""
    return Label(Input(type="checkbox", name="i", value=key, checked=key in picked), Span(icon(ico, 18, 2), label), cls="ak-chip")


def box_for(s, given) -> str:
    """What a link into the landing fills the box with: the asked place, and who and when only when the address said them."""
    if not given.get("to") or s.place.name not in {p.name for p in v2sentence.known_places()}:      # a place this search cannot price is not put in the box
        return ""
    when = given.get("d") and given.get("r") and not s.problems
    who = given.get("a") or given.get("k")
    return asksuggest.box_text(s.place.name, s.depart if when else None, s.return_ if when else None, s.adults if who else None, len(s.kid_ages) if who else 0)


def ask_page(s=None, picked=(), problem="", q=""):
    """The landing: the line, the box with its Search, the example places and the optional interests. `s` gives the airport the search leaves from."""
    s = s or tripmatrix.state()
    err = P(problem, cls="v2-error", id="v2-error", role="alert", **({} if problem else {"hidden": True}))
    field = Div(icon("search", 22, 2),
                Input(type="text", name="q", id="v2-q", value=q, placeholder=PLACEHOLDER, data_short=SHORT_PLACEHOLDER, autocomplete="off", autocapitalize="off", spellcheck="false", maxlength=asksuggest.MAX_TEXT,
                      role="combobox", aria_expanded="false", aria_controls="v2-list", aria_autocomplete="list", aria_label=ASK),
                Button("Search", icon("arrow-right", 20, 2.2), type="submit", cls="v2-go", id="v2-go"), cls="ak-field")
    box = Div(field, Ul(id="v2-list", cls="ak-list v2-glass", role="listbox", aria_label="Suggestions", hidden=True), P(id="v2-say", cls="ak-say", role="status", hidden=True), cls="ak-box")
    ex = Div(*[A(n, href=f"{PATH}?to={quote(n)}", cls="ak-ex") for n in asksuggest.popular()], cls="ak-ex-row", role="group", aria_label="Places to start with")
    into = Div(Span("Into something? Optional", cls="ak-into-h"), Div(*[chip(k, label, ico, picked) for k, label, ico, _ in interests.LIST], cls="ak-chips"), cls="ak-into")
    form = Form(Input(type="hidden", name="home", value=s.home), box, err, ex, into, id="v2-form", action=PATH, method="post", cls="v2-form ak-form", data_suggest=SUGGEST)
    hero = Div(H1(ASK, cls="ak-h"), P(SUB, cls="ak-sub"), form, tripmatrix.import_el("ak-import"), cls="v2-hero")
    return page(ASK, Div(hero, skeleton(), cls="v2-stage", data_v2="landing"), current="/plan/matrix", head=HEAD, noindex=True, footer=False, v2=True)


def register(app):
    @app.get(PATH)
    def ask(request, session, to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        s = tripmatrix.state(to, home, d, r, a, k, x, nb, b)
        return ask_page(s, interests.get(session), q=box_for(s, {"to": to, "d": d, "r": r, "a": a, "k": k}))

    @app.get(SUGGEST)
    def suggest(q: str = "", home: str = ""):
        return JSONResponse(asksuggest.suggest(q, tripmatrix.state(home=home).home), headers={"Cache-Control": "no-store"})

    @app.post(PATH)
    async def ask_search(request, session):
        form = await request.form()
        picked = interests.clean([v for v in form.getlist("i") if isinstance(v, str)])
        said = form.get("q")      # the landing's box; the results' sentence posts its words as fields instead
        to, problem = asksuggest.search(said, str(form.get("home") or "")) if isinstance(said, str) else v2sentence.address(form)
        scripted = request.headers.get("x-v2") == "1"
        if problem:
            if scripted:
                return JSONResponse({"error": problem}, status_code=400)
            return ask_page(tripmatrix.state(str(form.get("to") or ""), str(form.get("home") or "")), picked, problem, q=said if isinstance(said, str) else "")
        if access.can_edit(access.request_role()):
            await run_in_threadpool(interests.save, session, picked)
        return JSONResponse({"to": to}, headers={"Cache-Control": "no-store"}) if scripted else RedirectResponse(to, status_code=303)
