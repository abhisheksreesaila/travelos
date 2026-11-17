"""The trip matrix (F-222): places down and start days across, each square the whole trip (flight + stay), so a family sees the trip they did not know to ask for.

GET  /start               the old Where to? address: redirects here with its place, dates and party (F-231)
GET  /plan/matrix          the results of the v2 design (F-250): the sentence on top, each word a tappable picker (gitaway/v2sentence.py, assets/js/v2.js), then one card: the
                           status ("Pricing 3 of 25 trips"), the legend, the pick bar (the find) and the grid, a place a row, a start day a column, each square the whole trip
                           with its start day's sky above its total; the opened square's trip view under it on a laptop, in a sheet on a phone. `q=` is a retyped sentence.
GET  /plan/matrix/tile     one square as JSON for assets/js/tripmatrix.js: its words, its total and its panel. Plain `def`: a search can wait seconds.
GET  /plan/matrix/square   one square as its own page: the panel, for a link and for a page without the script. Plain `def` too.
POST /plan/matrix/warm     the head start (F-229): the page's script asks once; the first squares start searching on worker threads. A plain GET starts none.
POST /plan/matrix/save     Save to trip: the square is saved to the family's trip (made if it is new), never booked; the price is read again here, never trusted from the form.
POST /plan/matrix/book     Book the stay (F-233): the sandbox booking sheet and its confirm step, in gitaway/pages/matrixbook.py.

Every square is drawn as a skeleton and fills from GET /plan/matrix/tile like a map tile (assets/js/tripmatrix.js; the page first asks POST /plan/matrix/warm to start the first
squares' searches at once, gitaway/matrixwarm.py, F-229; a plain GET starts none): only the squares in view are asked for, three at a time, and they are marked with the same rules as
gitaway/tripmatrix.py. Without the script every square is a link to its own page.
On the showcase the sample catalog drives every square and says so; off it the routes exist only with LITEAPI_KEY (gitaway/showcase.py `_needs_keys`).
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import quote, urlencode

from fasthtml.common import A, Aside, B, Br, Button, Details, Div, H1, H2, Header, Link, Nav, NotStr, P, Script, Section, Span, Summary, to_xml
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, RedirectResponse

from gitaway import catalog, familydb, firstrun, gridsource, guide as gd, importer, interests, liteapi, matrixbook as mb, matrixwarm, moods, placeart, placefacts, session as ses, showcase, stats, tripmatrix as tm, tripsentence, tripstart, v2sentence, weather
from gitaway.icons import icon
from gitaway.layout import mode_switch, page
from gitaway.pages import plan_search, v2rail, weather_ui
from gitaway.pages.skystrip import WET, WORDS, weather_for
from gitaway.partners import places

PATH = "/plan/matrix"
TILE, SQUARE, SAVE, WARM, BOOK, RAIL = PATH + "/tile", PATH + "/square", PATH + "/save", PATH + "/warm", PATH + "/book", PATH + "/rail"
HEAD = (Link(rel="stylesheet", href="/assets/css/placeart.css"), Link(rel="stylesheet", href="/assets/css/skystrip.css"),
        Link(rel="stylesheet", href="/assets/css/tripmatrix.css"), Link(rel="stylesheet", href="/assets/css/v2rail.css"), Link(rel="stylesheet", href="/assets/css/v2drawer.css"),
        Link(rel="stylesheet", href="/assets/css/matrixbook.css"),
        Link(rel="stylesheet", href="/assets/css/guidesheet.css"), Script(src="/assets/js/guidesheet.js", defer=True),
        Script(src="/assets/js/v2rail.js", defer=True), Script(src="/assets/js/tripmatrix.js", defer=True), Script(src="/assets/js/v2drawer.js", defer=True), Script(src="/assets/js/matrixbook.js", defer=True),
        Link(rel="stylesheet", href="/assets/css/aerial.css"), Script(src="/assets/js/aerial.js", defer=True))
DEFAULT_PLACE, DEFAULT_HOME, DEFAULT_FLEX, DEFAULT_NIGHTS, DEFAULT_KIDS = "San Diego", "SFO", 2, 4, (7, 10)
NIGHTS_MIN, NIGHTS_MAX = 2, 7       # the nights slider's ends (F-237); a trip already longer or shorter in the address widens the range to hold it
LEAD_DAYS = 28                     # the default trip leaves on the first Saturday at least this far ahead
BUDGETS = (2_000, 2_500, 3_000, 4_000, 5_000)
SAMPLE = "Sample prices"
HINT = "Change any word"      # an instruction under the title, not a tag (F-279)
SEARCH = "Your search"
CHEAPEST_FOUND = "The cheapest flight found; more fares were still coming in."
ESTIMATES = "“About” prices are estimates from what is known. Exact prices when you press Update."
SLOW = "Flights take a few seconds to search. Each square fills in as its answer lands."
FINE = "Prices are a preview from LiteAPI and change until booked. A stay booked here is a sandbox booking: nothing is charged."
SAMPLE_FINE = "Sample prices from GitAway's made-up catalog, moved by the day of the week. A stay booked here is a sample booking: nothing is booked or charged."


def fine_p(sample: bool):
    """The fine print under the prices, for the key the site runs with (F-267, D-769): the showcase's made-up catalog; a live key's prices said to be live from LiteAPI, with where the
    time they were checked goes (the script writes it into #mx-age as squares land) and what Book is; the sandbox's words as they were."""
    if sample:
        return P(SAMPLE_FINE, cls="mx-foot-n")
    if liteapi.mode() == "live":
        what = {mb.SOON: mb.SOON_WORDS + ".", mb.LIVE: mb.LIVE_WORDS + ", on LiteAPI’s own secure form: GitAway never sees your card."}.get(
            mb.mode(), "A stay booked here is a sample booking: nothing is booked or charged.")
        return P("Prices are live from LiteAPI, checked ", Span("when each square is asked", id="mx-age", data_live="1"), f". They change until booked. {what}", cls="mx-foot-n")
    return P(FINE, cls="mx-foot-n")
MISSING = {"place": "Say where to, like “to San Diego”.", "dates": "Say when, like “Dec 12 to 16”.", "party": f"GitAway plans for up to {catalog.MAX_TRAVELERS} travelers.",
           "flex": f"Say give or take 0 to {tm.MAX_FLEX} days, like “give or take 2 days”.", "home": "Say where you fly from, like “from SFO”.",
           "airport": "GitAway does not know that place’s airport yet. Try a place like San Diego, Lake Tahoe or Orlando."}


# ---- what the address says -------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class State:
    place: object                 # partners/places.py Place
    home: str
    depart: date
    return_: date
    adults: int
    kid_ages: tuple
    flex: int
    nearby: bool
    budget_cents: int | None
    problems: tuple = ()          # what stops a search, in words

    @property
    def travelers(self) -> int:
        return self.adults + len(self.kid_ages)

    @property
    def nights(self) -> int:
        return (self.return_ - self.depart).days


def _default_dates():
    first = catalog.today() + timedelta(days=LEAD_DAYS)
    first += timedelta(days=(5 - first.weekday()) % 7)
    return first, first + timedelta(days=DEFAULT_NIGHTS)


def state(to="", home="", d="", r="", a="", k="", x="", nb="", b="") -> State:
    problems = []
    place = places.resolve(to or DEFAULT_PLACE)
    if not (place.known and place.iata):
        problems.append(MISSING["airport"])
    home = catalog.clean_home(home) or (DEFAULT_HOME if showcase.on() else "")
    if not home:
        problems.append(MISSING["home"])
    depart, return_ = _default_dates()
    adults, kids = 2, DEFAULT_KIDS
    if d or r or a or k:
        try:
            t = catalog.parse_trip("", "la", d or depart.isoformat(), r or return_.isoformat(), a or "2", k if (k or a) else ",".join(map(str, kids)), check_past=True)
            depart, return_, adults, kids = t.depart, t.return_, t.adults, t.kid_ages
        except catalog.TripError as e:
            problems += list(dict.fromkeys(m for _, m in e.errors))
    flex = int(x) if x in {str(i) for i in range(tm.MAX_FLEX + 1)} else DEFAULT_FLEX
    budget = int(b) if (b or "").isdigit() and tripsentence.MIN_BUDGET_CENTS <= int(b) * 100 <= tripsentence.MAX_BUDGET_CENTS else None
    return State(place, home, depart, return_, adults, tuple(kids), flex, nb != "0", budget * 100 if budget else None, tuple(problems))


def params(s: State, **over) -> dict:
    q = {"to": s.place.name, "home": s.home, "d": s.depart.isoformat(), "r": s.return_.isoformat(), "a": s.adults, "k": ",".join(map(str, s.kid_ages)),
         "x": s.flex, "nb": "" if s.nearby else "0", "b": s.budget_cents // 100 if s.budget_cents else ""}
    q.update(over)
    return {n: v for n, v in q.items() if v not in ("", None)}


def href(s: State, path=PATH, **over) -> str:
    return f"{path}?" + urlencode(params(s, **over))


def from_sentence(q, s: State):
    """A retyped sentence: (the address it lands on, None), or (None, what is missing in words). An unsaid "give or take" or "or nearby" keeps the page's
    widening (D-438); "exactly" narrows the dates, and the sentence's own menus narrow the places."""
    ask = tripsentence.read(q)
    if ask.unread:
        return None, [MISSING[x] for x in ask.unread]
    place = places.resolve(ask.place)
    if not (place.known and place.iata):
        return None, [MISSING["airport"]]
    over = {"to": place.name, "home": ask.origin or s.home, "d": ask.depart.isoformat(), "r": ask.return_.isoformat(), "a": ask.adults, "k": ",".join(map(str, ask.kid_ages)),
            "x": DEFAULT_FLEX if ask.flex is None else ask.flex, "nb": "", "b": ask.budget_cents // 100 if ask.budget_cents else ""}
    return href(s, **over), None


# ---- the grid of the search ------------------------------------------------------------------------------------------

def lanes_of(s: State):
    """The rows. On the showcase a nearby lane the sample catalog cannot price is not drawn (F-236, D-521): never a row of "No sample" squares; the asked place stays,
    and says so in words. Off it every lane is LiteAPI's to price."""
    lanes = tm.lanes(s.place, s.nearby)
    return tuple(x for x in lanes if x.asked or not showcase.on() or all(gridsource.has_sample(p) for p in x.places))


def windows_of(s: State, nights=None):
    """The start days for `nights` (the address's own when None): the same days and keys whatever the nights, only each trip's last day moves."""
    return tm.windows(s.depart, s.depart + timedelta(days=nights) if nights else s.return_, s.flex, catalog.today())


def nights_range(s: State) -> tuple:
    return min(NIGHTS_MIN, s.nights), max(NIGHTS_MAX, s.nights)


def peek_all(s: State, lanes, windows, family="") -> dict:
    """{square key: Square} for what is known without a call."""
    out = {}
    for x in lanes:
        for w in windows:
            sq = gridsource.square(x, w, s.adults, s.kid_ages, s.home, family, peek=True)
            if sq is not None:
                out[sq.key] = sq
    return out


def estimate_of(sq):
    """What the script needs to guess this square's price for other nights (F-237): [the flight, each stay's rate for a night] in cents, or None. A guess, never a
    price: the marks, the find, the bar, Save and Book only ever use a real square."""
    if sq is None or not sq.ok:
        return None
    return [sq.flight.cents] + [round(st.cents / st.nights) for st in sq.stays if st.nights]


def square_json(lane, w, sq) -> dict:
    """One answered square as the script keeps it: the tile and the peek say the same."""
    return {"key": sq.key, "s": sq.status, "c": sq.cents, "inner": inner(sq), "label": label(lane, w, sq), "drive": sq.drive, "e": estimate_of(sq)}


def party_words(s: State) -> str:
    return f"a family of {s.travelers}" if s.kid_ages else (f"{s.adults} adults" if s.adults > 1 else "one adult")


def age_words(fetched) -> str:
    if fetched is None:
        return ""
    minutes = int((liteapi.now() - fetched).total_seconds() // 60)
    return "just now" if minutes < 1 else (f"{minutes} min ago" if minutes < 60 else f"{minutes // 60} h ago")


def vs_words(diff, asked_name, combo) -> str:
    """The panel's chip beside a nearby square's total. assets/js/tripmatrix.js `vs` says the same words."""
    alone = " alone" if combo else ""
    if diff < 0:
        return f"{tm.dollars(-diff)} less than {asked_name}{alone}"
    return f"the same as {asked_name}{alone}" if diff == 0 else f"{tm.dollars(diff)} more than {asked_name}{alone}"


def _art(place, cls="mx-art"):
    svg, kind = placeart.art(place.slug), placeart.kind(place.slug)
    return Div(NotStr(svg) if svg else "", cls=cls + ("" if svg else " is-plain"), data_kind=kind or "", aria_hidden="true")


def _arts(lane, cls="mx-art"):
    return Div(*[_art(p, "mx-art-i") for p in lane.places], cls=f"{cls} mx-arts n{len(lane.places)}", aria_hidden="true")


# ---- one square ------------------------------------------------------------------------------------------------------

def inner(sq) -> str:
    """What sits inside a square, as HTML: the total, a problem in words, or a skeleton (never a number). The tile answers with the same."""
    if sq is None:
        return to_xml(Span("Searching", cls="mx-sr"))
    if sq.ok:
        return to_xml(Span(tm.dollars(sq.cents), cls="mx-v"))
    return to_xml(Span(tm.SHORT[sq.status], cls="mx-w"))


def state_cls(sq) -> str:
    return "is-wait skeleton" if sq is None else ("is-ok" if sq.ok else "is-said")


def label(lane, w, sq) -> str:
    head = f"{lane.name}, {tm.when(w)}"
    if sq is None:
        return f"{head}: searching"
    return f"{head}: {tm.dollars(sq.cents)} for the whole trip" if sq.ok else f"{head}: {tm.SAID[sq.status]}"


def sky_of(skies, lane, w):
    """The weather of the square's start day where the trip starts (the lane's first place), or None."""
    return next((d for d in skies[lane.places[0].name].days if d and d.date == w.depart), None) if skies else None


def sky_line(wx):
    """F-230: the square's second line, under its total: a small sky and the high, typical weather marked as such (the notes under the matrix say what
    typical means and whose numbers they are). The square's label says the total; the panel's sky strip says the weather in words."""
    if wx is None:
        return ""
    typ = wx.kind != weather.FORECAST
    return Span(icon(wx.condition if wx.condition in WORDS else "cloud", 14, cls="mx-sqw-i"), Span(f"{wx.high_f}°", cls="mx-sqw-t"),
                cls="mx-sqw " + ("is-typ" if typ else "is-fc") + (" is-wet" if wx.condition in WET else ""),
                title=weather_ui.describe(wx), aria_hidden="true")


def square_el(s: State, lane, w, sq, marks, style=None, wx=None, on=False):
    """One square: the sky of its start day above the whole trip's total (a skeleton until its answer lands). A link to its own page without the script."""
    k = tm.key(lane.key, w.key)
    cls = " ".join(["mx-sq", state_cls(sq), *[f"is-{m}" for m in marks], "is-asked" if w.asked and lane.asked else "", "is-on" if on else ""]).strip()
    return A(sky_line(wx), Span(NotStr(inner(sq)), cls="mx-in"), href=href(s, SQUARE, lane=lane.key, w=w.key), cls=cls, data_sq=k, aria_label=label(lane, w, sq),
             **({"style": style} if style else {}))


def panel(s: State, lane, w, sq, asked_sq=None, saved="", can_save=True):
    """The opened square (F-251, D-620): the prototype's drawer, the hotel and the flight side by side, the rooms, the total and "Book my trip" (gitaway/pages/v2drawer.py).
    One view for the drawer under the matrix, on a laptop and on a phone, and the square's own page; CSS lays it out by width."""
    from gitaway.pages import v2drawer
    return v2drawer.drawer(s, lane, w, sq, asked_sq, saved, can_save)

# ---- the page --------------------------------------------------------------------------------------------------------
# F-250 (D-610..): design language v2. The page is the prototype's results (docs/design/booking-v2/index.html): the sentence on top (its words open pickers,
# gitaway/v2sentence.py and assets/js/v2.js), one card holding the status and legend, the pick bar and the grid (a place a row, a start day a column, each square the whole
# trip with its start day's sky above its total), and the opened square's trip view under it. One grid at every width: it scrolls sideways on a phone. Every square starts as a
# skeleton and fills from the tile endpoint like a map tile (assets/js/tripmatrix.js), so the count says "Pricing 3 of 25 trips" while they come in.

def nights_words(n) -> str:
    return f"{n} night{'' if n == 1 else 's'}"


def fact_el(s: State):
    """F-230: while the first squares load, a small floating note (an island) says a sourced fact about the place. Drawn hidden: the script shows it when it
    starts loading squares and lets it go once the first ones land (without the script nothing loads, so there is nothing to wait for)."""
    found = placefacts.facts(s.place.slug)
    if not found:
        return ""
    fact = found[catalog.today().toordinal() % len(found)]
    source = getattr(fact, "source", "")
    cite = A("Source", href=source, cls="mx-fact-src", rel="noopener", target="_blank") if str(source).startswith("https://") else Span(source, cls="mx-fact-src")
    return Aside(Span(icon("spark", 16, 2.2, cls="mx-isle-i"), cls="mx-isle-ic", aria_hidden="true"),
                 Div(P(Span(f"While we search · {s.place.name}", cls="mx-fact-k")), P(fact.text, cls="mx-fact-t"), cite, cls="mx-isle-b"),
                 cls="mx-isle is-gone", id="mx-fact", aria_hidden="true", aria_label=f"A fact about {s.place.name} while the prices load")


def find_el():
    """The pick bar (the prototype's "Our pick"): the find, drawn by assets/js/tripmatrix.js `drawFind` when the squares say one (a nearby trip that costs less than or the same as the
    asked place); a skeleton of it while squares are still coming in, nothing when there is none."""
    return A(Span(cls="mx-pk-art", aria_hidden="true"), Span(Span(cls="mx-pk-h"), Span(cls="mx-pk-s"), cls="mx-pk-t"), Span("Our pick", cls="mx-pk-badge"), Span(cls="mx-pk-p num"),
             Span("Open", icon("arrow-right", 18, 2.2), cls="mx-pk-open"), href="#", cls="mx-find is-empty", id="mx-find", aria_live="polite", data_open="")


def sky_note(skies) -> str:
    """The head cell's small line: the sky under each start day is typical weather, not a forecast (a forecast day has none)."""
    typical = any(d and d.kind != weather.FORECAST for tw in skies.values() for d in tw.days)
    return "Sky: typical, not a forecast yet" if typical else ""


def lane_el(s: State, lane, windows, skies):
    """A place's row: its lead (the art, the name, its cheapest start once it is known), the ringed band of its nights on the asked start, and a square per start day."""
    at = next((i for i, w in enumerate(windows) if w.asked), 0)
    w0 = windows[at]
    kids = [Div(_arts(lane, "mx-thumb"), Div(Span(lane.name, cls="mx-l-n"), Span("Pricing…", cls="mx-l-best", data_lane_best=lane.key), cls="mx-nm"), cls="mx-lead mx-lh"),
            Div(cls="mx-band", data_band=lane.key, data_l=f"{w0.nights} nights", style=f"grid-column: {at + 2} / span {min(w0.nights, len(windows) - at)}")]
    for i, w in enumerate(windows):
        kids.append(square_el(s, lane, w, None, (), style=f"grid-column: {i + 2}", wx=sky_of(skies, lane, w), on=i == at))
    return Div(*kids, cls="mx-lane" + (" is-asked" if lane.asked else "") + (" is-combo" if lane.combo else ""), data_lane=lane.key)


def skies_of(lanes, windows):
    """Each place's weather over the start days (typical or forecast, none for a place with no station): the sky above each square's total."""
    return {p.name: weather_for(p.name, windows[0].depart, windows[-1].depart) for x in lanes for p in x.places}


def lanes_el(s: State, lanes, windows, skies):      # the sky note ("typical, not a forecast yet") is the top row's (sky_note)
    head = Div(Div(Span("Start day →", Br(), "Place ↓", cls="mx-ah"), cls="mx-lead mx-lh"),
               *[Div(Span(f"{w.depart:%b}", cls="mx-mo") if i == 0 or w.depart.day == 1 else "", Span(f"{w.depart:%a}", cls="mx-dw"), Span(str(w.depart.day), cls="mx-dn num"),
                     cls="mx-day" + (" is-wkend" if w.depart.weekday() >= 5 else "") + (" is-ask" if w.asked else ""), style=f"grid-column: {i + 2}", data_day=w.depart.isoformat())
                 for i, w in enumerate(windows)], cls="mx-head")
    return Section(Div(Div(head, *[lane_el(s, x, windows, skies) for x in lanes], cls="mx-lanes", style=f"--n: {len(windows)}"), cls="mx-scroll", id="mx-scroll"),
                   cls="mx-cal", aria_label="Every place, every start day")


def about_el(s: State, skies, sample: bool):
    """The one quiet "ⓘ About these prices" (F-238, D-540), kept: the weather's credit and labels (AGENTS.md: a page showing weather shows weather.notes), the preview and sample
    fine print, the site's Privacy and Terms and the light/dark button. A popover under its button, closed until it is tapped."""
    notes = list(dict.fromkeys(text_href for tw in skies.values() for text_href in weather.notes(tw)))
    return Details(Summary(icon("info", 18, 2.2), Span("About these prices"), cls="mx-about-btn"),
                   Div(P(f"Under each start day: the flight and the stay for {s.travelers}, all in. The ringed band is your {nights_words(s.nights)}; tap a start to move it.", cls="mx-legend-n"),
                       fine_p(sample),
                       Div(*[A(text, href=to, rel="noopener", cls="mx-wx-n") if to else Span(text, cls="mx-wx-n") for text, to in notes], cls="mx-wx") if notes else "",
                       Div(Nav(A("Privacy", href="/privacy"), A("Terms", href="/terms"), cls="mx-about-nav", aria_label="Legal"), mode_switch("about"), cls="mx-about-foot"), cls="mx-pop mx-pop-about"),
                   cls="mx-tk mx-about", data_pop="about")


def credit_el(skies):
    """MET Norway's credit (F-238 review, D-540): CC BY 4.0 asks for credit, a link to the licence and a note of changes "in any reasonable manner", and weather.py promises it
    wherever a forecast shows, so while any forecast (not typical) day is on the page one small linked line says it. The full per-place credits stay in the ⓘ."""
    made = [tw.updated for tw in skies.values() if tw.updated and any(d and d.kind == weather.FORECAST for d in tw.days)]
    if not made:
        return ""
    return P(A(f"Forecast based on data from MET Norway · updated {made[0]}", href=weather.CREDIT_URL, rel="noopener", cls="mx-credit-a"), cls="mx-credit")


def status_el(s: State, total: int):
    """The status line: while squares come in "Pricing 3 of 25 trips: flights from SFO + 4 nights of stays", then "25 whole trips for 4: flights + 4 nights". The page shows one
    by `data-waiting`; the script counts."""
    nights = lambda: Span(nights_words(s.nights), data_nights_out="1")      # noqa: E731
    return Div(Span(Span(cls="v2-spin"), Span("Pricing ", B("0", cls="num", id="mx-count-n"), f" of {total} trips: flights from {s.home} + ", nights(), " of stays"), cls="mx-st mx-st-wait"),
               Span(Span(B(str(total), cls="num", id="mx-done-n"), Span(id="mx-done-of"), f" whole trips for {s.travelers}: flights + ", nights()), cls="mx-st mx-st-done"), cls="mx-status", id="mx-count", aria_live="polite")


def legend_el(s: State):
    lg = lambda mark, text: Span(Span(cls=mark), text, cls="lg")      # noqa: E731
    return Div(lg("i-pick", "Our pick"), lg("i-cheap", "Cheapest"), lg("i-band", "Your nights"),
               *([lg("i-over", f"Over {tm.dollars(s.budget_cents)}")] if s.budget_cents else []), cls="mx-legend")


def page_data(s: State, lanes, windows, known) -> str:
    """What assets/js/tripmatrix.js runs on. The nights slider (F-237) needs, for every nights it allows: the address of that trip's last day (`returns`) and each start
    day's words (`whens`)."""
    lo, hi = nights_range(s)
    by = {n: windows_of(s, n) for n in range(lo, hi + 1)}
    cell = {tm.key(x.key, w.key): (x, w) for x in lanes for w in windows}
    data = {"lanes": [{"k": x.key, "n": x.name, "a": x.asked, "c": x.combo} for x in lanes],
            "windows": [{"k": w.key, "a": w.asked, "n": w.nights, "when": tm.when(w)} for w in windows],
            "nights": s.nights, "lo": lo, "hi": hi,
            "returns": {n: (s.depart + timedelta(days=n)).isoformat() for n in by}, "whens": {n: [tm.when(w) for w in ws] for n, ws in by.items()},
            "known": {k: {"c": sq.cents, "s": sq.status, "e": estimate_of(sq), "i": inner(sq), "l": label(*cell[k], sq)}
                      for k, sq in known.items()},
            "order": tm.order(lanes, windows), "budget": s.budget_cents, "nearly": tm.NEARLY_CENTS, "at_once": liteapi.at_once(), "tile": href(s, TILE), "warm": href(s, WARM), "rail": href(s, RAIL)}
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


def import_el(id="mx-import"):
    """"Already booked? Bring your trip in" (F-231): a signed-in family that booked elsewhere goes to the import, not through a search."""
    return A("Already booked? Bring your trip in", href=firstrun.IMPORT, cls="v2-import", id=id) if ses.request_traveler() else ""


def hero_el(spec, problems=()):
    """The sentence on top of the results: its form (hidden fields, posted by the script when a word changes), the sentence, and what is wrong in words when a search cannot run."""
    err = P(" ".join(problems), cls="v2-error", id="v2-error", role="alert") if problems else ""
    sug = v2sentence.suggestions(spec)
    head = Div(Span(icon("search", 20, 2.4), cls="v2-qic", aria_hidden="true"), H2(SEARCH, cls="v2-qtitle", id="v2-qtitle"), Span(icon("pencil", 16, 2.2), HINT, cls="v2-hint"), cls="v2-qhead")
    tries = Nav(Span("Try", cls="v2-ql"), *[A(icon("plus", 16, 2.4), label, href=to, cls="v2-sug") for label, to in sug], cls="v2-sugs", aria_label="Suggested changes") if sug else ""
    upd = Div(P("Your changes aren't searched yet.", cls="v2-staged-note", role="status"), Button("Reset", type="button", cls="v2-reset"), Button("Update", type="submit", cls="v2-update"), id="v2-upd", cls="v2-upd", data_n="0")
    nojs = NotStr("<noscript><style>.v2-upd { display: flex; } .v2-reset { display: none; }</style></noscript>")      # without script the form is a plain one: its button searches
    return Div(Section(head, Div(v2sentence.form_el(spec, v2sentence.sentence(spec), err, upd, nojs), cls="v2-qfield"), tries, cls="v2-qcard", aria_labelledby="v2-qtitle"), import_el(), cls="v2-hero")


def matrix_page(s: State, family="", typed="", problems=(), picked=()):
    lanes, windows = lanes_of(s), windows_of(s)
    spec = v2sentence.spec_of(s, picked)
    machinery = v2sentence.machinery(spec)
    if s.problems or not windows:
        body = Div(hero_el(spec, problems or s.problems or [MISSING["dates"]]), *machinery, cls="v2-stage mx mx-blank", id="mx", data_v2="results")
        return page("The trip matrix", H1("The trip matrix", cls="v2-sr"), body, current="/plan/matrix", head=HEAD, noindex=True, footer=False, v2="is-results", mood=moods.choose(s.place, s.depart, s.return_))
    skies = skies_of(lanes, windows)
    sample = showcase.on()
    total = len(lanes) * len(windows)
    card = Div(Div(status_el(s, total), legend_el(s), about_el(s, skies, sample), P(sky_note(skies), cls="mx-ah-n"), P(SLOW, cls="mx-slow", role="status"), P(ESTIMATES, cls="mx-est-note", id="mx-est", role="status"), cls="mx-top"),
               find_el(), lanes_el(s, lanes, windows, skies), credit_el(skies), cls="mx-card")
    drawer = Div(id="mx-drawer", cls="dr-wrap", aria_label="The square you opened", aria_live="polite", hidden=True)      # the drawer grows into it (assets/js/tripmatrix.js, v2drawer.js)
    rail = Aside(Div(Div(Div(Span(v2rail.EXTRA, cls="rl-lab"), cls="rl-top"), Div(*[Span(Span(cls="ic"), Span(Span("Looking around…"), cls="tx"), cls="wchip is-skel") for _ in range(3)], cls="rl-chips"), cls="rl-tray v2-glass"), cls="rl-in"), id="mx-rail", cls="rl", aria_label="Around the place", aria_live="polite")
    results = Div(Div(card, drawer, cls="mx-main"), cls="mx-results")
    body = Div(H1(f"Trips to {s.place.name}" + (" and nearby" if s.nearby and len(lanes) > 1 else ""), cls="v2-sr"), hero_el(spec, problems), rail, results,
               Script(NotStr(page_data(s, lanes, windows, {})), type="application/json", id="mx-data"), fact_el(s), *machinery,
               cls="v2-stage mx", id="mx", data_v2="results", data_waiting="1")
    return page(f"{s.place.name}: the whole trip, every start day", body, current="/plan/matrix", head=HEAD, noindex=True, footer=False, v2="is-results", mood=moods.choose(s.place, s.depart, s.return_))


def warm(s: State, family="") -> int:
    """The head start (F-229, D-452): the first squares not yet known, queued for gitaway/matrixwarm.py's workers. Asked by the page's script, never by
    drawing the page, so a crawler or a link preview spends no searches."""
    if showcase.on():
        return 0
    lanes, windows = lanes_of(s), windows_of(s)
    if liteapi.mode() == "live":      # F-273: a live key's gate takes the whole first view at once, the head start's squares first
        ranks, cell = tm.rank(lanes, windows), {tm.key(x.key, w.key): (x, w) for x in lanes for w in windows}
        first = [(*cell[k], i) for k, i in sorted(ranks.items(), key=lambda kv: kv[1]) if k in cell]
    else:
        first = [(x, w, i) for i, (x, w) in enumerate(tm.head_start(lanes, windows))]
    todo = [(x, w, i) for x, w, i in first if gridsource.square(x, w, s.adults, s.kid_ages, s.home, family, peek=True) is None]
    return matrixwarm.warm(todo, s.adults, s.kid_ages, s.home, family)


def pick(lanes, windows, lane, w):
    """The lane and start day the rail (and a guide's sheet) follows: the ones named, else the asked place and its asked start day."""
    return (next((x for x in lanes if x.key == lane), None) or next(x for x in lanes if x.asked),
            next((x for x in windows if x.key == w), None) or next((x for x in windows if x.asked), windows[0]))


def _square_of(s, lane_key, w_key, family="", peek=False):
    lane = tm.lane(s.place, lane_key, s.nearby)
    w = tm.window(s.depart, s.return_, s.flex, catalog.today(), w_key)
    if lane is None or w is None:
        return None, None, None, None
    rank = tm.rank(lanes_of(s), windows_of(s)).get(tm.key(lane.key, w.key), 0)
    sq = gridsource.square(lane, w, s.adults, s.kid_ages, s.home, family, peek=peek, rank=rank, wait=liteapi.TILE_WAIT)      # a request thread: a short wait at the gate
    asked = next(x for x in lanes_of(s) if x.asked)
    asked_sq = sq if lane.asked else gridsource.square(asked, w, s.adults, s.kid_ages, s.home, family, peek=True)
    return lane, w, sq, asked_sq


def square_page(s: State, lane, w, sq, asked_sq, saved="", can_save=True):
    body = Div(A(icon("chev-left", 18, 2.4), "Back to the matrix", href=href(s), cls="btn mx-back"),
               H1(f"{lane.name} · {tm.when(w)}", cls="mx-sr"), Div(panel(s, lane, w, sq, asked_sq, saved, can_save), cls="dr-wrap dr-alone"),
               Div(fine_p(sq is not None and sq.sample), cls="mx-foot"), cls="mx mx-one")
    return page(f"{lane.name}, {tm.when(w)}", body, current="/plan/matrix", head=HEAD, noindex=True, v2=True, mood=moods.choose(s.place, s.depart, s.return_))


def _save_id(trip_id, sq) -> str:
    return hashlib.sha256(f"{trip_id}|{sq.key}".encode()).hexdigest()[:20]


def save(session, s: State, lane, w, sq) -> str:
    """Make (or reopen) the family's trip for this square and keep the square on it. Returns the trip id; raises importer.SaveError."""
    search, errors = tripstart.read({"place": lane.places[0].name, "d": w.depart.isoformat(), "r": w.return_.isoformat(), "a": str(s.adults),
                                     "k": ",".join(map(str, s.kid_ages)), "home": s.home})
    if errors or search is None:
        raise importer.SaveError(" ".join(errors.values()) if errors else "That trip could not be made.")
    trip_id = tripstart.start(session, search)
    me = ses.current_traveler(session)
    flight = f"{sq.flight.airline} · {sq.flight.out}" + (f" · back {sq.flight.back}" if sq.flight.back else "")
    stays = " · ".join(f"{st.nights} nights at {st.name}, {st.place}" for st in sq.stays)
    with ses.family(session) as fam:
        if fam:
            with familydb.transaction(fam.db):
                familydb.run(fam.db, "DELETE FROM matrix_saves WHERE id = :i", i=_save_id(trip_id, sq))
                familydb.run(fam.db, "INSERT INTO matrix_saves (id, trip_id, user_id, lane, depart, return_, total_cents, flight, stays, fetched, sample, saved_at) "
                                     "VALUES (:i, :t, :u, :l, :d, :r, :c, :f, :s, :at, :sm, :now)",
                             i=_save_id(trip_id, sq), t=trip_id, u=me.id if me else "", l=lane.name, d=w.depart.isoformat(), r=w.return_.isoformat(), c=sq.cents,
                             f=flight[:300], s=stays[:300], at=sq.fetched.isoformat() if sq.fetched else "", sm=1 if sq.sample else 0, now=familydb.now())
    return trip_id


def saved_squares(session, trip_id) -> list:
    with ses.family(session) as fam:
        return familydb.rows(fam.db, "SELECT * FROM matrix_saves WHERE trip_id = :t ORDER BY saved_at", t=trip_id) if fam else []


def _family(session):
    return (session or {}).get("tenant_id", "")


def _who(request, session):
    """Whose searches a request spends (F-265, D-763): the signed-in family's, else the signed-out visitor's own allowance (a salted daily code, no cookie)."""
    return _family(session) or stats.searcher(request)


def register(app):
    @app.get("/start")
    def start(request):
        """The old Where to? form is gone (F-231, D-461): its address, and every link made of it, opens the matrix with the place, dates and party it carried."""
        return RedirectResponse(plan_search.matrix_href(request.query_params), status_code=303)

    @app.get(PATH)
    def trip_matrix(session, q: str = "", to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        s = state(to, home, d, r, a, k, x, nb, b)
        if q.strip():
            to_, problems = from_sentence(q, s)
            if to_:
                return RedirectResponse(to_, status_code=303)
            return matrix_page(s, _family(session), typed=q, problems=problems, picked=interests.get(session))
        return matrix_page(s, _family(session), picked=interests.get(session))

    @app.get(TILE)
    def trip_matrix_tile(request, session, lane: str = "", w: str = "", to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        s = state(to, home, d, r, a, k, x, nb, b)
        if s.problems:
            return JSONResponse({"error": " ".join(s.problems)}, status_code=400)
        lane_, w_, sq, asked_sq = _square_of(s, lane, w, _who(request, session))
        if lane_ is None:
            return JSONResponse({"error": "No such square."}, status_code=404)
        return JSONResponse({**square_json(lane_, w_, sq), "age": age_words(sq.fetched), "drawer": to_xml(panel(s, lane_, w_, sq, asked_sq))},
                            headers={"Cache-Control": "no-store"})

    @app.get(RAIL)
    def trip_matrix_rail(session, lane: str = "", w: str = "", to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = "", wg: str = ""):
        """The widget rail for one lane and start day (F-251): what is real about the place, as chips (F-277: `wg=` is one chip's card, asked when it is tapped). Squares are only read from what is already known
        (a cheaper airport needs two answers): nothing is searched here. A plain `def`: a drive can wait on the router for a moment, but only for a signed-in person
        (L-1): a stranger is shown the drives already kept, so the open page cannot spend the router's budget."""
        s = state(to, home, d, r, a, k, x, nb, b)
        lanes, windows = lanes_of(s), windows_of(s)
        if s.problems or not windows:
            return JSONResponse({"error": " ".join(s.problems) or MISSING["dates"]}, status_code=400)
        lane_, w_ = pick(lanes, windows, lane, w)
        family = _family(session)
        known = lambda ln, win: gridsource.square(ln, win, s.adults, s.kid_ages, s.home, family, peek=True)      # noqa: E731
        kw = dict(sq=known(lane_, w_), lanes=lanes, known=known, picked=interests.get(session), look_up=bool(ses.current_traveler(session)), guides=gd.for_place(session, lane_.places[0].name))
        if wg:      # one chip was tapped (F-277, D-870): its card is built now, and only now
            card = v2rail.card_html(wg, s, lane_, w_, **kw)
            return JSONResponse({"error": "No such widget."} if card is None else {"card": card, "lane": lane_.key}, status_code=404 if card is None else 200, headers={"Cache-Control": "no-store"})
        return JSONResponse({"html": v2rail.html(s, lane_, w_, **kw), "lane": lane_.key}, headers={"Cache-Control": "no-store"})

    @app.post(WARM)
    def trip_matrix_warm(request, session, to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        s = state(to, home, d, r, a, k, x, nb, b)
        if s.problems or not windows_of(s):
            return JSONResponse({"error": " ".join(s.problems) or MISSING["dates"]}, status_code=400)
        return JSONResponse({"queued": warm(s, _who(request, session))}, headers={"Cache-Control": "no-store"})

    @app.get(SQUARE)
    def trip_matrix_square(request, session, lane: str = "", w: str = "", saved: str = "", to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "",
                           nb: str = "", b: str = ""):
        s = state(to, home, d, r, a, k, x, nb, b)
        if s.problems:
            return RedirectResponse(href(s), status_code=303)
        lane_, w_, sq, asked_sq = _square_of(s, lane, w, _who(request, session))
        if lane_ is None:
            return RedirectResponse(href(s), status_code=303)
        note = "Saved to your trip." if saved == "1" else ""
        return square_page(s, lane_, w_, sq, asked_sq, note)

    @app.post(SAVE)
    async def trip_matrix_save(request, session):
        form = {n: v for n, v in (await request.form()).items() if isinstance(v, str)}
        s = state(*(form.get(n, "") for n in ("to", "home", "d", "r", "a", "k", "x", "nb", "b")))
        lane_key, w_key = form.get("lane", ""), form.get("w", "")
        back = href(s, SQUARE, lane=lane_key, w=w_key)
        if s.problems:
            return RedirectResponse(href(s), status_code=303)
        if not ses.current_traveler(session):
            return RedirectResponse("/signin?next=" + quote(back, safe=""), status_code=303)
        lane_, w_, sq, asked_sq = await run_in_threadpool(_square_of, s, lane_key, w_key, _family(session), True)      # what was shown is in the cache; never the form's price
        if lane_ is None:
            return RedirectResponse(href(s), status_code=303)
        if sq is None:
            lane_, w_, sq, asked_sq = await run_in_threadpool(_square_of, s, lane_key, w_key, _family(session))
        if not sq.ok:
            return square_page(s, lane_, w_, sq, asked_sq)
        sq = tm.pick(sq, *tm.picks(form.get("fl", ""), form.get("st", ""), form.get("rm", "")))      # the flight, stays and rooms chosen on the square (F-242, F-251), read again here, never a price from the form
        try:
            await run_in_threadpool(save, session, s, lane_, w_, sq)      # database writes: off the event loop
        except importer.SaveError as e:
            return square_page(s, lane_, w_, sq, asked_sq, str(e), can_save=False)
        if request.headers.get("x-matrix") == "1":
            return JSONResponse({"saved": "Saved to your trip.", "trip": "/trip/plan", "next": "Open the trip" if mb.mode() in (mb.SANDBOX, mb.LIVE) and not sq.sample else "Plan this trip"})      # F-269: with nothing to book yet, planning is the next step
        return RedirectResponse(back + "&saved=1", status_code=303)
