"""Guides in context (F-263, D-730..): a guide opened where you are deciding, in a sheet over booking's matrix or planning's calendar, so you never lose your place.

GET  /guides/sheet?slug=&ctx=book|plan   the sheet's contents as JSON {html, title, css}: assets/js/guidesheet.js puts them in a sheet that grows out of the rail's card and folds back into it.
                                         ctx=book also takes the matrix's own address (to, home, d, r, a, k, x, nb, b, lane, w) and names your search in its bar; ctx=plan reads the family's real
                                         plans for the free time it names and offers to drop it in. It is the guide page's run sheet (gitaway/pages/guideview.py) with the stops opening in place, never a
                                         sheet on a sheet.

The rails' "Guides for <place>" card is `widget_rows` here (the one place its rows are drawn for both rails); which guides it lists is `gitaway/guide.py` `for_place`. Adding is the guide page's own
POST /guides/add (a stop, or with `to` and `after` a free morning dropped into a day in order).
"""

from urllib.parse import quote, urlencode

from fasthtml.common import A, B, Button, Div, Li, P, Span, Ul, to_xml
from starlette.responses import JSONResponse

from gitaway import forks as forks_model, guide as gd, guideplan, planv2 as pv, tripmatrix as tm
from gitaway.icons import icon
from gitaway.pages import guides, guideview

CSS = ("/assets/css/cv2.css", "/assets/css/placeart.css", "/assets/css/guides.css")
CTX = ("book", "plan")
WHO = dict(guides.WHO)


def sheet_href(slug: str, ctx: str, base: str = "") -> str:
    """The address of one guide's sheet. For booking, `base` is the matrix's own query (its address's parameters) plus the lane and start day the rail follows."""
    return "/guides/sheet?" + urlencode({"slug": slug, "ctx": ctx}) + (f"&{base}" if base else "")


def meta(c) -> str:
    kind = next((WHO[k] for k in c.tags if k in WHO), "")
    return " · ".join(x for x in (f"{c.days} day{'s' if c.days != 1 else ''}", kind) if x)


def widget_rows(cards, href_of) -> Ul:
    """The rail card's rows: a thumbnail, the guide's name, how long and who it suits, its creator. Each is a button that opens the guide's sheet from itself (`data-sheet`)."""
    every = all(not c.real for c in cards)
    return Ul(*[Li(Button(guides.art(c), Div(B(c.title, cls="b"), Span(meta(c), cls="sub"), Span(Span(c.author), Span("Sample", cls="smp") if not c.real and not every else "", cls="by")),
                          icon("chev-right", 20, 2.2), type="button", cls="gd-row", data_sheet=href_of(c), aria_haspopup="dialog")) for c in cards], cls="gd-list")


def widget_foot(place: str, total: int, shown: int):
    more = f"All {place} guides" if total <= shown else f"All {total} {place} guides"
    return A(more, href=f"/guides?q={quote(place)}", cls="gd-all")


# ---- the sheet ----------------------------------------------------------------------------------------------------------------------------

def _bar(left: str, text: str, back: str):
    return Div(Button(icon("chev-left", 20, 2.4), type="button", cls="v2-round gs-back", data_close="1", aria_label=back),
               P(B(left), f" · {text}" if text else "", cls="gs-ctx"),
               Button(icon("x", 20, 2.4), type="button", cls="v2-round", data_close="1", aria_label="Close the guide"), cls="gs-bar")


def _peek(g: gd.Guide, line: str):
    """What the sheet shrinks to on a phone while you watch a drop: a bar with the guide's name; tapping it opens the guide again where you left it."""
    return Button(Div(guideview.art(g, True), cls="gs-pa"), Div(B(g.title), Span(line)), icon("up", 20, 2.4), type="button", cls="gs-peek", data_unpeek="1", aria_label=f"Open {g.title} again")


def free_card(g: gd.Guide, free, fit):
    if free is None:
        return ""
    if fit is None:
        return Div(icon("calendar", 22, 2), Div(B(free.said), Span("No day of this guide fits it whole. Add any stop with +.")), cls="gs-free")
    n, keys = fit
    short = free.short
    return Div(icon("calendar", 22, 2), Div(B(free.said), Span(f"Day {n} fits it.")),
               Button(icon("plus", 20, 2.4), f"Add this {free.part} to {short}", type="button", cls="go", data_add_day=" ".join(keys), data_to=str(free.day), data_after=str(free.start), data_when=short, data_n=str(len(keys))),
               cls="gs-free", data_free="1")


def _body(g: gd.Guide, ctx: str, add: str, free_html):
    actions = Div(A(icon("target", 20, 2.2), "Plan this trip", href=gd.plan_href(g.place, g.nights), cls="go") if ctx == "book" else "",
                  A(icon("ext", 20, 2.2), "Open the full guide", href=f"/trips/{g.slug}", cls="tonal"), cls="gs-act")
    head = Div(guideview.art(g, True), Div(guideview.kicker(g), Div(g.title, cls="gs-h", role="heading", aria_level="1"), guideview.byline(g), cls="g-hmain"), cls="gs-head")
    tiles = Div(*[guideview.tile(t) for t in g.tiles], cls="g-tiles")
    days = [guideview.day_section(g, d, False, add, inplace=True) for d in g.days]
    return [head, actions, P(guideview.ADD_NOTE[add], cls="g-note") if add in guideview.ADD_NOTE and ctx == "plan" else "", free_html, tiles, guideview.strip(g), *days, guideview.trust(g, {"plannable": True})]


def _book_bar(session, q) -> tuple:
    """"Your trips · San Diego, Dec 18 · 4 nights · $1,846 picked": the lane and start day the rail follows, from the matrix's own address (a known answer only: nothing is searched here)."""
    from gitaway import gridsource
    from gitaway.pages import tripmatrix as mx
    s = mx.state(*[q.get(k, "") for k in ("to", "home", "d", "r", "a", "k", "x", "nb", "b")])
    lanes, windows = mx.lanes_of(s), mx.windows_of(s)
    if s.problems or not windows:
        return "Your trips", s.place.name
    lane, w = mx.pick(lanes, windows, q.get("lane", ""), q.get("w", ""))
    sq = gridsource.square(lane, w, s.adults, s.kid_ages, s.home, mx._family(session), peek=True)
    parts = [f"{lane.places[0].name}, {w.depart:%b} {w.depart.day}", f"{w.nights} night{'s' if w.nights != 1 else ''}"]
    if sq is not None and sq.ok:
        parts.append(f"{tm.dollars(sq.cents)} picked")
    return "Your trips", " · ".join(parts)


def _plan_bar(v, free) -> tuple:
    a, z = v.days[0][1], v.days[-1][1]
    span = f"{a:%b} {a.day} to " + (f"{z.day}" if (a.year, a.month) == (z.year, z.month) else f"{z:%b} {z.day}")
    return "Your plan", span + (f" · {free.name} {free.part} free" if free else "")


def sheet(session, q) -> tuple:
    """-> (status, JSON-able dict). 404 for a guide that is not there, 400 for a context we do not know."""
    from gitaway.pages import guidepage
    ctx, slug = q.get("ctx", ""), q.get("slug", "")[:80]
    found = forks_model.resolve(slug)
    if ctx not in CTX:
        return 400, {"error": "That is not a place a guide opens."}
    if not gd.is_guide(found):
        return 404, {"error": "That guide is not here any more."}
    g = gd.from_trip(found)
    free = fit = None
    add = "no"
    if ctx == "plan":
        add = guidepage.add_state(session)
        if add == "yes":
            v = pv.view(session, lambda day=0, booked="": "")
            free = guideplan.free_time(v)
            fit = guideplan.fit_day(g, free) if free else None
            left, text = _plan_bar(v, free)
        else:
            left, text = "Your plan", ""
    else:
        left, text = _book_bar(session, q)
    back = "Back to your plan" if ctx == "plan" else "Back to your trips"
    peek = "Back to the guide, where you left it"
    html = Div(_bar(left, text, back), Div(*_body(g, ctx, add, free_card(g, free, fit)), cls="gs-body", id="gs-body"), _peek(g, peek), cls="gs-in", data_slug=slug, data_ctx=ctx, data_can=add)
    return 200, {"html": to_xml(html), "title": g.title, "css": list(CSS), "sample": g.sample}


def register(app):
    @app.get("/guides/sheet")
    def guide_sheet(session, request):
        status, body = sheet(session, dict(request.query_params))
        return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})
