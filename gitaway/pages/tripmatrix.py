"""The trip matrix (F-222): places down and start days across, each square the whole trip (flight + stay), so a family sees the trip they did not know to ask for.

GET  /start               the old Where to? address: redirects here with its place, dates and party (F-231)
GET  /plan/matrix          the sentence ("A family of 4, SFO to San Diego or nearby, Dec 12 to 16 give or take 2 days, under $3,000."), the find, and the matrix: on a laptop
                           calendar lanes (each place a row of days wearing its sky, the nights a band, the whole trip's total under each start day) beside the opened square's
                           panel; on a phone a card per place with its start days as squares, and the opened square in a sheet. `q=` is a retyped sentence.
GET  /plan/matrix/tile     one square as JSON for assets/js/tripmatrix.js: its words, its total and its panel. Plain `def`: a search can wait seconds.
GET  /plan/matrix/peek     what is known for the nights asked (F-237), every square at once, no search: the script asks it when the nights slider is let go.
GET  /plan/matrix/square   one square as its own page: the panel, for a link and for a page without the script. Plain `def` too.
POST /plan/matrix/warm     the head start (F-229): the page's script asks once; the first squares start searching on worker threads. A plain GET starts none.
POST /plan/matrix/save     Save to trip: the square is saved to the family's trip (made if it is new), never booked; the price is read again here, never trusted from the form.
POST /plan/matrix/book     Book the stay (F-233): the sandbox booking sheet and its confirm step, in gitaway/pages/matrixbook.py.

The page draws what is known without a call (gridsource.square `peek`: the sample catalog, or LiteAPI's cache) and a skeleton for the rest; the script then asks
POST /plan/matrix/warm to start the first squares' searches at once (gitaway/matrixwarm.py, F-229), which the tiles join; a plain GET starts none. The script asks for the squares in view like map tiles and marks them with the same rules as gitaway/tripmatrix.py. Without the script every square is a link to its own page.
On the showcase the sample catalog drives every square and says so; off it the routes exist only with LITEAPI_KEY (gitaway/showcase.py `_needs_keys`).
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import quote, urlencode

from fasthtml.common import A, Aside, Button, Details, Div, Form, H1, H2, Input, Label, Link, Nav, Noscript, NotStr, P, Script, Section, Span, Summary, to_xml
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, RedirectResponse

from gitaway import catalog, familydb, firstrun, gridsource, importer, liteapi, matrixwarm, placeart, placefacts, session as ses, showcase, tripmatrix as tm, tripsentence, tripstart, weather
from gitaway.icons import icon
from gitaway.layout import mode_switch, page
from gitaway.pages import plan_search, weather_ui
from gitaway.pages.skystrip import WET, WORDS, weather_for
from gitaway.partners import places

PATH = "/plan/matrix"
TILE, SQUARE, SAVE, WARM, BOOK, PEEK = PATH + "/tile", PATH + "/square", PATH + "/save", PATH + "/warm", PATH + "/book", PATH + "/peek"
HEAD = (Link(rel="stylesheet", href="/assets/css/placeart.css"), Link(rel="stylesheet", href="/assets/css/skystrip.css"),
        Link(rel="stylesheet", href="/assets/css/tripmatrix.css"), Link(rel="stylesheet", href="/assets/css/tripview.css"), Link(rel="stylesheet", href="/assets/css/matrixbook.css"),
        Script(src="/assets/js/tripmatrix.js", defer=True), Script(src="/assets/js/tripview.js", defer=True), Script(src="/assets/js/matrixbook.js", defer=True))
DEFAULT_PLACE, DEFAULT_HOME, DEFAULT_FLEX, DEFAULT_NIGHTS, DEFAULT_KIDS = "San Diego", "SFO", 2, 4, (7, 10)
NIGHTS_MIN, NIGHTS_MAX = 2, 7       # the nights slider's ends (F-237); a trip already longer or shorter in the address widens the range to hold it
LEAD_DAYS = 28                     # the default trip leaves on the first Saturday at least this far ahead
BUDGETS = (2_000, 2_500, 3_000, 4_000, 5_000)
SAMPLE = "Sample prices"
CHEAPEST_FOUND = "The cheapest flight found; more fares were still coming in."
ESTIMATES = "“About” prices are estimates from what is known. Exact prices when you let go."
SLOW = "Flights take a few seconds to search. Each square fills in as its answer lands."
FINE = "Prices are a preview from LiteAPI and change until booked. A stay booked here is a sandbox booking: nothing is charged."
SAMPLE_FINE = "Sample prices from GitAway's made-up catalog, moved by the day of the week. A stay booked here is a sample booking: nothing is booked or charged."
BOOK_WORDS, BOOK_SAMPLE = "Sandbox booking: nothing is charged.", "Sample booking: nothing is booked or charged."      # gitaway/matrixbook.py says the same
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


def ask_of(s: State) -> tripsentence.Ask:
    return tripsentence.Ask(place=s.place.name, origin=s.home, depart=s.depart, return_=s.return_, adults=s.adults, kid_ages=s.kid_ages, ages_given=True,
                            budget_cents=s.budget_cents, party_given=True, nearby=s.nearby and bool(places.nearby(s.place)), flex=s.flex)


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


PAD_DAYS = 2      # the calendar shows two days more than the trips reach on each side (the design's Dec 8 to 20 for starts Dec 10 to 14), never before today


def days_of(windows, nights=None):
    """The calendar's days for trips of `nights` (the windows' own when None). The page draws them for the longest trip the slider allows and hides the days a shorter
    trip does not reach (F-237), so every day's weather is already there when the nights change."""
    last = windows[-1].depart + timedelta(days=nights) if nights else windows[-1].return_
    first, last = windows[0].depart - timedelta(days=PAD_DAYS), last + timedelta(days=PAD_DAYS)
    first = max(first, catalog.today())
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def peek_all(s: State, lanes, windows, family="") -> dict:
    """{square key: Square} for what is known without a call."""
    out = {}
    for x in lanes:
        for w in windows:
            sq = gridsource.square(x, w, s.adults, s.kid_ages, s.home, family, peek=True)
            if sq is not None:
                out[sq.key] = sq
    return out


def totals_of(known) -> dict:
    return {k: sq.cents for k, sq in known.items() if sq.ok}


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
    if diff < 0:
        return f"{tm.dollars(-diff)} less than {asked_name}"
    return f"the same as {asked_name}" if diff == 0 else f"+{tm.dollars(diff)} vs {asked_name}{' alone' if combo else ''}"


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


def square_el(s: State, lane, w, sq, marks, day=False, style=None, wx=None, on=False):
    k = tm.key(lane.key, w.key)
    cls = " ".join(["mx-sq", state_cls(sq), *[f"is-{m}" for m in marks], "is-asked" if w.asked and lane.asked else "", "is-on" if on else ""]).strip()
    head = [Span(f"{w.depart:%a}", Span(f" {w.depart:%b}", cls="mx-dd"), f" {w.depart.day}", cls="mx-d")] if day else []
    return A(*head, Span(NotStr(inner(sq)), cls="mx-in"), sky_line(wx), href=href(s, SQUARE, lane=lane.key, w=w.key), cls=cls, data_sq=k, aria_label=label(lane, w, sq),
             **({"style": style} if style else {}))


def panel(s: State, lane, w, sq, asked_sq=None, saved="", can_save=True):
    """The opened square (F-242, D-570): the hotel, the flight, the sky for those nights and the total, with "Book this trip" the boldest thing on the screen
    (gitaway/pages/tripview.py). One view for the laptop's side under the calendar, the phone's sheet and the square's own page; CSS lays it out by width."""
    from gitaway.pages import tripview
    return tripview.view(s, lane, w, sq, asked_sq, saved, can_save)


bar = panel


# ---- the page --------------------------------------------------------------------------------------------------------

def _pop(key, words, *inside):
    return Details(Summary(words, cls="mx-tok"), Div(*inside, cls="mx-pop"), cls=f"mx-tk mx-tk-{key}", data_pop=key)


def _chip(text, to, on):
    return A(text, href=to, cls="mx-chip" + (" is-on" if on else ""), aria_current="true" if on else None)


def nights_words(n) -> str:
    return f"{n} night{'' if n == 1 else 's'}"


def nights_pop(s: State):
    """"4 nights" is a word of the sentence like the others (F-238, D-542): tapping it opens a small popover with the nights slider (F-237, D-530), the only one.
    Sliding shows estimates ("about $X") at once; letting go searches the squares in view. Without the script the popover holds plain links to each nights."""
    lo, hi = nights_range(s)
    chips = Noscript(Div(*[_chip(nights_words(n), href(s, r=(s.depart + timedelta(days=n)).isoformat()), n == s.nights) for n in range(lo, hi + 1)], cls="mx-chips mx-nights-links"))
    return Details(Summary(Span(nights_words(s.nights), data_nights_out="1"), cls="mx-tok"),
                   Div(P("Nights", cls="mx-pop-h"),
                       Input(type="range", min=str(lo), max=str(hi), step="1", value=str(s.nights), cls="mx-range", data_nights="1", aria_label="Nights",
                             aria_valuetext=nights_words(s.nights), style=f"--fill: {round((s.nights - lo) * 100 / (hi - lo))}%"),
                       Div(Span(str(lo)), Span(str(hi)), cls="mx-range-ends", aria_hidden="true"), chips, cls="mx-pop mx-pop-nights"),
                   cls="mx-tk mx-tk-nights", data_pop="nights")


def sentence(s: State, typed="", problems=()):
    found = dict(tripsentence.parts(ask_of(s)))
    out = [Span(found["party"] + ",", cls="mx-word")]
    near = places.nearby(s.place)
    route = f"{s.home} to {s.place.name}" if s.home else f"to {s.place.name}"
    if near:
        out.append(_pop("near", route + (" or nearby" if s.nearby else "") + ",", P("Where", cls="mx-pop-h"),
                        Div(_chip(f"{s.place.name} or nearby", href(s, nb=""), s.nearby), _chip(f"Only {s.place.name}", href(s, nb="0"), not s.nearby), cls="mx-chips"),
                        P("Nearby: " + ", ".join(p.name for p in near) + ", and each of them with " + s.place.name + ".", cls="mx-pop-note")))
    else:
        out.append(Span(route + ",", cls="mx-word"))
    out.append(Span(found["dates"], cls="mx-word", data_dates="1"))
    out.append(nights_pop(s))
    out.append(_pop("flex", (found.get("flex") or "") + ",", P("Start days", cls="mx-pop-h"),
                    Div(*[_chip("Exactly" if n == 0 else f"± {n} day{'s' if n > 1 else ''}", href(s, x=n), s.flex == n) for n in range(tm.MAX_FLEX + 1)], cls="mx-chips")))
    out.append(_pop("budget", found.get("budget", "any budget") + ".", P("Your budget, all in", cls="mx-pop-h"),
                    Div(*[_chip(catalog.money(v * 100), href(s, b=v), s.budget_cents == v * 100) for v in BUDGETS], _chip("No budget", href(s, b=""), not s.budget_cents), cls="mx-chips"),
                    P("Squares over it are marked.", cls="mx-pop-note")))
    edit = Details(Summary(icon("pencil", 18, 2.2), Span("Retype the search", cls="mx-sr"), cls="mx-pen", aria_label="Retype the search"),
                   Form(Label(Span("Say it your way", cls="mx-pop-h"), Input(type="text", name="q", value=typed or tripsentence.write(ask_of(s)), maxlength=str(tripsentence.MAX_TEXT),
                                                                            autocomplete="off", spellcheck="false", id="mx-q", **({"aria_invalid": "true", "aria_describedby": "mx-q-err"} if problems else {}))),
                        *[Input(type="hidden", name=n, value=str(v)) for n, v in params(s).items() if n == "home"],
                        *([P(" ".join(problems), cls="mx-err", id="mx-q-err", role="alert")] if problems else []),
                        Button("Search", type="submit", cls="btn btn-ink"), method="get", action=PATH, cls="mx-pop mx-pop-edit"),
                   cls="mx-tk mx-edit", data_pop="edit", open=bool(problems))
    return Div(*out, edit, cls="mx-sent", id="mx-sent")


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


def find_el(s: State, found):
    if found is None:
        return Div(cls="mx-find is-empty", id="mx-find", aria_live="polite")
    return Div(Span(icon("spark", 16, 2.2), "Found", cls="mx-found"),
               A(Span(found.words, cls="mx-find-w", id="mx-find-w"), Span(f" · {found.when}", cls="mx-find-d", id="mx-find-d"),
                 href=href(s, SQUARE, lane=found.lane, w=found.window), cls="mx-find-a", id="mx-find-a", data_open=found.key),
               cls="mx-find", id="mx-find", aria_live="polite", data_key=found.key)


def band_words(lane, w, sq, found, s: State) -> str:
    """The label on a band's top edge: "4 nights · $2,080", or on the find "Found · +$50 vs San Diego alone". assets/js/tripmatrix.js `bandWords` says the same."""
    if sq is None or not sq.ok:
        return f"{w.nights} nights"
    if found is not None and found.key == sq.key:
        return "Found · " + vs_words(found.diff_cents, s.place.name, lane.combo)
    return f"{w.nights} nights · {tm.dollars(sq.cents)}"


def band_window(lane, windows, known, found=None):
    """Where a lane's band sits: the find's start in the lane that holds it, else its cheapest answered start, else the asked one. assets/js/tripmatrix.js moves it
    the same way (and to an opened square)."""
    if found is not None and found.lane == lane.key:
        return next(w for w in windows if w.key == found.window)
    got = [(known[tm.key(lane.key, w.key)].cents, j, w) for j, w in enumerate(windows) if tm.key(lane.key, w.key) in known and known[tm.key(lane.key, w.key)].ok]
    return min(got)[2] if got else next((w for w in windows if w.asked), windows[0])


def day_cell(d, col, wx, band_w, off=False):
    """One day of a lane wearing its sky (F-236): the icon, the high and, for a typical day, the chance of a wet day. Typical weather is dotted and says so in its title;
    a forecast day has no chance to show. A day with no weather (gone by, a place with no station) is an empty cell, never made up."""
    inside = band_w.depart <= d <= band_w.return_
    base = dict(cls="mx-day" + (" is-in" if inside else "") + (" is-off" if off else ""), style=f"grid-column: {col}", data_day=d.isoformat(), aria_hidden="true" if wx is None else None)
    if wx is None:
        return Div(**base)
    typ = wx.kind != weather.FORECAST
    chance = f" {wx.wet_pct}%" if typ and wx.wet_pct is not None else ""
    return Div(icon(wx.condition if wx.condition in WORDS else "cloud", 22, 2, cls="mx-day-i"), Span(f"{wx.high_f}°{chance}", cls="mx-day-t"),
               title=weather_ui.describe(wx) + ("" if wx.wet_pct is None or not typ else f", wet on about {wx.wet_pct}% of days"),
               **{**base, "cls": base["cls"] + (" is-typ" if typ else " is-fc") + (" is-wet" if wx.condition in WET else "")})


def lane_el(s: State, lane, windows, days, known, marks, home, skies, found=None, visible=None):
    col = {d: i + 2 for i, d in enumerate(days)}
    band_w = band_window(lane, windows, known, found)
    sky = skies.get(lane.places[0].name) if skies else None
    by_day = {d.date: d for d in sky.days if d} if sky else {}
    at = known.get(tm.key(lane.key, band_w.key))
    lit = found is not None and found.lane == lane.key and found.window == band_w.key
    kids = [Div(_arts(lane, "mx-thumb"), Div(P(lane.name, cls="mx-l-n"),
                                                 P("No weather for this place yet" if sky is not None and not by_day else "", cls="mx-l-s mx-l-nowx"),
                                                 P(tm.dollars(at.cents) if at is not None and at.ok else "", cls="mx-l-best", data_lane_total=lane.key)), cls="mx-lh"),
            Div(cls="mx-band", data_band=lane.key, data_l=band_words(lane, band_w, at, found, s), style=f"grid-column: {col[band_w.depart]} / span {band_w.nights + 1}")]
    kids += [day_cell(d, col[d], by_day.get(d), band_w, off=i >= (visible or len(days))) for i, d in enumerate(days)]
    for w in windows:
        k = tm.key(lane.key, w.key)
        ms = marks.get(k, ())
        kids.append(square_el(s, lane, w, known.get(k), ms, style=f"grid-column: {col[w.depart]}", on=w.key == band_w.key))
    return Div(*kids, cls="mx-lane" + (" is-asked" if lane.asked else "") + (" is-combo" if lane.combo else "") + (" is-lit" if lit else ""), data_lane=lane.key)


def skies_of(lanes, windows, nights=None):
    days = days_of(windows, nights)
    return {p.name: weather_for(p.name, days[0], days[-1]) for x in lanes for p in x.places}


def lanes_el(s: State, lanes, windows, known, marks, skies, found=None):
    """The calendar. Its days run to the longest trip the nights slider allows; the ones a trip of the nights now shown does not reach are `is-off` (hidden), and the
    grid is as many columns as are shown (F-237)."""
    days, visible = days_of(windows, nights_range(s)[1]), len(days_of(windows))
    typical = any(d and d.kind != weather.FORECAST for tw in skies.values() for d in tw.days)
    starts = {w.depart for w in windows}
    axis = Div(Div(Span("Sky each day", cls="mx-label"), Span("typical, not a forecast yet" if typical else "", cls="mx-ah-n"), cls="mx-ah"),
               *[Div(Span(f"{d:%a}", cls="mx-adw"), Span(str(d.day) if d.day != 1 and d != days[0] else f"{d:%b} {d.day}", cls="mx-adn"),
                     cls="mx-ad" + (" is-ask" if d == s.depart else "") + (" is-start" if d in starts else "") + (" is-off" if i >= visible else ""), data_day=d.isoformat())
                 for i, d in enumerate(days)], cls="mx-axis")
    return Section(Div(axis, *[lane_el(s, x, windows, days, known, marks, s.home, skies, found, visible) for x in lanes], cls="mx-lanes", style=f"--mx-days: {visible}"),
                   cls="mx-cal", aria_label="Every place, every start day")


def about_el(s: State, skies, sample: bool):
    """The one quiet "ⓘ About these prices" (F-238, D-540): what the calendar's colours mean, the weather's credit and labels (AGENTS.md: a page showing weather shows
    weather.notes), the preview and sample fine print, and the site's Privacy and Terms and the one light/dark button (the footer's other tenant), closed until it is tapped. It replaces the legend, the notes under the calendar and
    the cards, the fine print and the site footer."""
    notes = list(dict.fromkeys(text_href for tw in skies.values() for text_href in weather.notes(tw)))
    return Details(Summary(icon("info", 18, 2.2), Span("About these prices"), cls="mx-about-btn"),
                   Div(P(Span(cls="mx-key-band"), Span("Your ", Span(nights_words(s.nights), data_nights_out="1"), ", ringed (tap the nights in the sentence to change them, or tap a start price to move them). "
                         f"Under each start day: the flight and the stay for {s.travelers}, all in. Ink: the nights shown; yellow: the find; green: the cheapest start."), cls="mx-legend"),
                       P(SAMPLE_FINE if sample else FINE, cls="mx-foot-n"),
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


def card_el(s: State, lane, windows, known, marks, skies, found=None):
    got = [(known[tm.key(lane.key, w.key)].cents, j, w) for j, w in enumerate(windows) if tm.key(lane.key, w.key) in known and known[tm.key(lane.key, w.key)].ok]
    best = min(got) if got else None
    on = band_window(lane, windows, known, found).key      # the card's ringed start, as the lane's band sits (design B's ink ring on the shown window)
    return Section(Div(_arts(lane, "mx-c-art"), H2(lane.name, cls="mx-c-n"), cls="mx-c-top"),
                   Div(Div(Span(tm.dollars(best[0]) if best else "", cls="mx-c-v", data_lane_best=lane.key),
                           Span(tm.when(best[2]) + " · its cheapest" if best else "", cls="mx-c-s", data_lane_when=lane.key), cls="mx-c-best"),
                       Div(*[square_el(s, lane, w, known.get(tm.key(lane.key, w.key)), marks.get(tm.key(lane.key, w.key), ()), day=True, wx=sky_of(skies, lane, w), on=w.key == on)
                             for w in windows], cls="mx-wins"), cls="mx-c-bd"),
                   cls="mx-card" + (" is-asked" if lane.asked else ""), data_lane=lane.key, aria_label=lane.name)


def default_open(lanes, windows, known, found):
    """The square the laptop's panel starts on: the find, else the asked square, else the cheapest answered one, else none."""
    if found:
        return found.lane, found.window
    asked = next(x for x in lanes if x.asked)
    w = next((w for w in windows if w.asked), windows[0])
    if tm.key(asked.key, w.key) in known:
        return asked.key, w.key
    got = [(sq.cents, k) for k, sq in known.items() if sq.ok]
    return tuple(min(got)[1].split("|")) if got else None


def page_data(s: State, lanes, windows, known) -> str:
    """What assets/js/tripmatrix.js runs on. The nights slider (F-237) needs, for every nights it allows: the address of that trip's last day (`returns`), each start
    day's words (`whens`) and how many of the calendar's days it reaches (`nlast`)."""
    lo, hi = nights_range(s)
    by = {n: windows_of(s, n) for n in range(lo, hi + 1)}
    cell = {tm.key(x.key, w.key): (x, w) for x in lanes for w in windows}
    data = {"lanes": [{"k": x.key, "n": x.name, "a": x.asked, "c": x.combo} for x in lanes],
            "windows": [{"k": w.key, "a": w.asked, "n": w.nights, "when": tm.when(w)} for w in windows],
            "days": [d.isoformat() for d in days_of(windows, hi)], "nights": s.nights, "lo": lo, "hi": hi,
            "returns": {n: (s.depart + timedelta(days=n)).isoformat() for n in by}, "whens": {n: [tm.when(w) for w in ws] for n, ws in by.items()},
            "nlast": {n: len(days_of(ws)) for n, ws in by.items()},
            "known": {k: {"c": sq.cents, "s": sq.status, "e": estimate_of(sq), "i": inner(sq), "l": label(*cell[k], sq)}
                      for k, sq in known.items()},
            "order": tm.order(lanes, windows), "budget": s.budget_cents, "nearly": tm.NEARLY_CENTS, "tile": href(s, TILE), "warm": href(s, WARM), "peek": href(s, PEEK)}
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


def import_el():
    """"Already booked? Bring your trip in" (F-231): a signed-in family that booked elsewhere goes to the import, not through a search."""
    return A("Already booked? Bring your trip in", href=firstrun.IMPORT, cls="mx-import", id="mx-import") if ses.request_traveler() else ""


def matrix_page(s: State, family="", typed="", problems=()):
    lanes, windows = lanes_of(s), windows_of(s)
    meta_sample = showcase.on()
    if s.problems or not windows:
        body = Div(Div(sentence(s, typed, problems or s.problems or [MISSING["dates"]]), Div(import_el(), cls="mx-meta"), cls="mx-lead"), cls="mx mx-blank")
        return page("The trip matrix", H1("The trip matrix", cls="mx-sr"), body, current="/plan/matrix", head=HEAD, noindex=True)
    known = peek_all(s, lanes, windows, family)
    totals = totals_of(known)
    marks, found = tm.marks(lanes, windows, totals, s.budget_cents), tm.find(lanes, windows, totals)
    total = len(lanes) * len(windows)
    skies = skies_of(lanes, windows, nights_range(s)[1])
    opened = default_open(lanes, windows, known, found)
    if opened:
        o_lane, o_w = next(x for x in lanes if x.key == opened[0]), next(w for w in windows if w.key == opened[1])
        asked = next(x for x in lanes if x.asked)
        side = bar(s, o_lane, o_w, known.get(tm.key(*opened)), known.get(tm.key(asked.key, o_w.key)))
    else:
        side = Div(P("Open a square to see the whole trip: the flight, the stay, the drive.", cls="mx-p-note"), cls="mx-b")
    stage = Div(lanes_el(s, lanes, windows, known, marks, skies, found), Aside(side, cls="mx-side", id="mx-side", aria_label="The square you opened", aria_live="polite"), cls="mx-stage")
    cards = Div(*[card_el(s, x, windows, known, marks, skies, found) for x in lanes], cls="mx-cards")      # the credit and labels for the skies they show: the ⓘ in the top row
    meta = Div(Span(Span(str(len(known)), id="mx-count-n"), f" of {total} in", cls="mx-count", id="mx-count", aria_live="polite"),
               Span(SAMPLE, cls="mx-sample") if meta_sample else "", P(SLOW, cls="mx-slow", role="status"), P(ESTIMATES, cls="mx-est-note", id="mx-est", role="status"),
               import_el(), about_el(s, skies, meta_sample), cls="mx-meta", id="mx-meta")
    waiting = len(known) < total
    body = Div(H1(f"Trips to {s.place.name}" + (" and nearby" if s.nearby and len(lanes) > 1 else ""), cls="mx-sr"),
               Div(sentence(s, typed, problems), meta, cls="mx-lead"),
               Div(find_el(s, found), cls="mx-news", id="mx-news"),
               stage, cards, credit_el(skies),
               Script(NotStr(page_data(s, lanes, windows, known)), type="application/json", id="mx-data"),
               fact_el(s),      # last in the matrix: sticky to the bottom of the screen while the matrix is in view, never over the footer below it
               cls="mx", id="mx", data_waiting="1" if waiting else "0")
    return page(f"{s.place.name}: the whole trip, every start day", body, current="/plan/matrix", head=HEAD, noindex=True, footer=False)


def warm(s: State, family="") -> int:
    """The head start (F-229, D-452): the first squares not yet known, queued for gitaway/matrixwarm.py's workers. Asked by the page's script, never by
    drawing the page, so a crawler or a link preview spends no searches."""
    if showcase.on():
        return 0
    lanes, windows = lanes_of(s), windows_of(s)
    first = [(x, w, i) for i, (x, w) in enumerate(tm.head_start(lanes, windows))]
    todo = [(x, w, i) for x, w, i in first if gridsource.square(x, w, s.adults, s.kid_ages, s.home, family, peek=True) is None]
    return matrixwarm.warm(todo, s.adults, s.kid_ages, s.home, family)


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
               H1(f"{lane.name} · {tm.when(w)}", cls="mx-sr"), Div(panel(s, lane, w, sq, asked_sq, saved, can_save), cls="mx-side mx-alone"),
               Div(P(SAMPLE_FINE if sq is not None and sq.sample else FINE, cls="mx-foot-n"), cls="mx-foot"), cls="mx mx-one")
    return page(f"{lane.name}, {tm.when(w)}", body, current="/plan/matrix", head=HEAD, noindex=True)


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
            return matrix_page(s, _family(session), typed=q, problems=problems)
        return matrix_page(s, _family(session))

    @app.get(TILE)
    def trip_matrix_tile(session, lane: str = "", w: str = "", to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        s = state(to, home, d, r, a, k, x, nb, b)
        if s.problems:
            return JSONResponse({"error": " ".join(s.problems)}, status_code=400)
        lane_, w_, sq, asked_sq = _square_of(s, lane, w, _family(session))
        if lane_ is None:
            return JSONResponse({"error": "No such square."}, status_code=404)
        return JSONResponse({**square_json(lane_, w_, sq), "age": age_words(sq.fetched), "panel": to_xml(panel(s, lane_, w_, sq, asked_sq)), "bar": to_xml(bar(s, lane_, w_, sq, asked_sq))},
                            headers={"Cache-Control": "no-store"})

    @app.get(PEEK)
    def trip_matrix_peek(session, to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        """Every square already known for these dates (F-237): the showcase's samples, or LiteAPI's cache. A plain GET that searches nothing and spends no budget."""
        s = state(to, home, d, r, a, k, x, nb, b)
        lanes, windows = lanes_of(s), windows_of(s)
        if s.problems or not windows:
            return JSONResponse({"error": " ".join(s.problems) or MISSING["dates"]}, status_code=400)
        known = peek_all(s, lanes, windows, _family(session))
        cell = {tm.key(x.key, w.key): (x, w) for x in lanes for w in windows}
        return JSONResponse({"known": {k: square_json(*cell[k], sq) for k, sq in known.items()}}, headers={"Cache-Control": "no-store"})

    @app.post(WARM)
    def trip_matrix_warm(session, to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        s = state(to, home, d, r, a, k, x, nb, b)
        if s.problems or not windows_of(s):
            return JSONResponse({"error": " ".join(s.problems) or MISSING["dates"]}, status_code=400)
        return JSONResponse({"queued": warm(s, _family(session))}, headers={"Cache-Control": "no-store"})

    @app.get(SQUARE)
    def trip_matrix_square(session, lane: str = "", w: str = "", saved: str = "", to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "",
                           nb: str = "", b: str = ""):
        s = state(to, home, d, r, a, k, x, nb, b)
        if s.problems:
            return RedirectResponse(href(s), status_code=303)
        lane_, w_, sq, asked_sq = _square_of(s, lane, w, _family(session))
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
        sq = tm.pick(sq, *tm.picks(form.get("fl", ""), form.get("st", "")))      # the flight and stays chosen on the square (F-242), read again here, never a price from the form
        try:
            await run_in_threadpool(save, session, s, lane_, w_, sq)      # database writes: off the event loop
        except importer.SaveError as e:
            return square_page(s, lane_, w_, sq, asked_sq, str(e), can_save=False)
        if request.headers.get("x-matrix") == "1":
            return JSONResponse({"saved": "Saved to your trip.", "trip": "/trip/cockpit"})
        return RedirectResponse(back + "&saved=1", status_code=303)
