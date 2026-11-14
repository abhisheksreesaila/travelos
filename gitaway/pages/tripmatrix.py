"""The trip matrix (F-222): places down and start days across, each square the whole trip (flight + stay), so a family sees the trip they did not know to ask for.

GET  /start               the old Where to? address: redirects here with its place, dates and party (F-231)
GET  /plan/matrix          the sentence ("A family of 4, SFO to San Diego or nearby, Dec 12 to 16 give or take 2 days, under $3,000."), the find, and the matrix: on a laptop
                           calendar lanes (each place a row of days wearing its sky, the nights a band, the whole trip's total under each start day) beside the opened square's
                           panel; on a phone a card per place with its start days as squares, and the opened square in a sheet. `q=` is a retyped sentence.
GET  /plan/matrix/tile     one square as JSON for assets/js/tripmatrix.js: its words, its total and its panel. Plain `def`: a search can wait seconds.
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
from dataclasses import dataclass, replace
from datetime import date, timedelta
from urllib.parse import quote, urlencode

from fasthtml.common import A, Aside, Button, Details, Div, Form, H1, H2, H3, Img, Input, Label, Link, NotStr, P, Script, Section, Span, Summary, to_xml
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, RedirectResponse

from gitaway import catalog, familydb, firstrun, gridsource, importer, liteapi, matrixwarm, placeart, placefacts, session as ses, showcase, tripmatrix as tm, tripsentence, tripstart, weather
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import plan_search, weather_ui
from gitaway.pages.skystrip import WET, WORDS, sky_strip, weather_for
from gitaway.partners import places

PATH = "/plan/matrix"
TILE, SQUARE, SAVE, WARM, BOOK = PATH + "/tile", PATH + "/square", PATH + "/save", PATH + "/warm", PATH + "/book"
HEAD = (Link(rel="stylesheet", href="/assets/css/placeart.css"), Link(rel="stylesheet", href="/assets/css/skystrip.css"),
        Link(rel="stylesheet", href="/assets/css/tripmatrix.css"), Link(rel="stylesheet", href="/assets/css/matrixbook.css"),
        Script(src="/assets/js/tripmatrix.js", defer=True), Script(src="/assets/js/matrixbook.js", defer=True))
DEFAULT_PLACE, DEFAULT_HOME, DEFAULT_FLEX, DEFAULT_NIGHTS, DEFAULT_KIDS = "San Diego", "SFO", 2, 4, (7, 10)
LEAD_DAYS = 28                      # the default trip leaves on the first Saturday at least this far ahead
BUDGETS = (2_000, 2_500, 3_000, 4_000, 5_000)
SAMPLE = "Sample prices"
CHEAPEST_FOUND = "The cheapest flight found; more fares were still coming in."
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
    return tm.lanes(s.place, s.nearby)


def windows_of(s: State):
    return tm.windows(s.depart, s.return_, s.flex, catalog.today())


def days_of(windows):
    first, last = windows[0].depart, windows[-1].return_
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


def square_el(s: State, lane, w, sq, marks, day=False, style=None, wx=None):
    k = tm.key(lane.key, w.key)
    cls = " ".join(["mx-sq", state_cls(sq), *[f"is-{m}" for m in marks], "is-asked" if w.asked and lane.asked else ""]).strip()
    head = [Span(f"{w.depart:%a}", Span(f" {w.depart:%b}", cls="mx-dd"), f" {w.depart.day}", cls="mx-d")] if day else []
    return A(*head, Span(NotStr(inner(sq)), cls="mx-in"), sky_line(wx), href=href(s, SQUARE, lane=lane.key, w=w.key), cls=cls, data_sq=k, aria_label=label(lane, w, sq),
             **({"style": style} if style else {}))


def book_form(s: State, lane, w, sq):
    """The square's Book button (F-233): a form that posts to /plan/matrix/book; assets/js/matrixbook.js opens the answer as a sheet that grows out of the square."""
    return Form(*[Input(type="hidden", name=n, value=str(v)) for n, v in params(s, lane=lane.key, w=w.key).items()],
                Button(icon("bed", 16, 2.4), "Book the stay" + ("s" if len(sq.stays) > 1 else ""), type="submit", cls="btn btn-ink mx-book"), method="post", action=BOOK, cls="mx-book-f")


def panel(s: State, lane, w, sq, asked_sq=None, saved="", can_save=True):
    """The opened square: what the whole trip is made of (option A's panel). The same function draws the laptop's side, the phone's sheet and the square's page."""
    nights = (f"{w.nights // 2} nights each" if lane.combo and w.nights % 2 == 0 else
              " · ".join(f"{(b - a).days} in {p.name}" for p, a, b in tm.stays_for(lane, w)) if lane.combo else f"{w.nights} nights")
    head = [_arts(lane, "mx-p-art"), Div(H3(f"{lane.name} · {tm.when(w)}", cls="mx-p-h"), P(f"{nights} · {party_words(s)}", cls="mx-p-sub"), cls="mx-p-top")]
    if sq is None:
        return Div(*head, P("Searching this square…", cls="mx-p-note", role="status"), cls="mx-p", data_open=tm.key(lane.key, w.key))
    if not sq.ok:
        return Div(*head, P(tm.SAID[sq.status], cls="mx-p-note", role="status"), cls="mx-p", data_open=sq.key)
    vs = ""
    if asked_sq is not None and asked_sq.ok and not lane.asked:
        vs = vs_words(sq.cents - asked_sq.cents, s.place.name, lane.combo)
    age = age_words(sq.fetched)
    rows = [Div(Span(icon("plane", 16, 2.2), cls="mx-kt k-flight"), Div(P(sq.flight.airline, cls="mx-r-h"), P(sq.flight.out, cls="mx-r-s"), P(sq.flight.back, cls="mx-r-s") if sq.flight.back else "",
                                                                                     P(CHEAPEST_FOUND, cls="mx-r-s") if not sq.flight.complete else ""),
                Span(catalog.money(sq.flight.cents), cls="mx-r-n"), cls="mx-row")]
    for st in sq.stays:
        bits = [st.room, "Breakfast" if st.board == "breakfast" else st.board.capitalize(), "Refundable" if st.refundable else "Non-refundable"]
        rows.append(Div(Span(icon("bed", 16, 2.2), cls="mx-kt k-stay"),
                        Div(P(f"{st.name}", cls="mx-r-h"), P(f"{st.nights} nights in {st.place}" if lane.combo else f"{st.nights} nights", " · ", " · ".join(b for b in bits if b), cls="mx-r-s"),
                            P(st.rating, cls="mx-r-s") if st.rating else "",
                            P(f"{catalog.money(st.due_at_stay_cents)} of it paid at the hotel", cls="mx-r-s mx-r-due") if st.due_at_stay_cents else ""),
                        Span(catalog.money(st.cents), cls="mx-r-n"),
                        Img(src=st.photo, alt=f"{st.name}, the hotel's own photo", loading="lazy", cls="mx-photo", referrerpolicy="no-referrer") if st.photo else "", cls="mx-row mx-row-stay"))
    first = lane.places[0]
    rows.append(Div(Span(icon("car", 16, 2.2), cls="mx-kt k-car"),
                    Div(P("Airport drive", cls="mx-r-h"), P(f"{sq.drive} min from {first.iata} to {first.name}" if sq.drive else f"From {first.iata}: no drive time yet", cls="mx-r-s")),
                    Span("", cls="mx-r-n"), cls="mx-row"))
    sky = sky_strip(first.name, weather_for(first.name, w.depart, w.return_), asked=(w.depart, w.return_))
    form = (Form(*[Input(type="hidden", name=n, value=str(v)) for n, v in params(s, lane=lane.key, w=w.key).items()],
                 Button(icon("check", 16, 2.4), "Save to trip", type="submit", cls="btn btn-ink mx-save"), method="post", action=SAVE, cls="mx-save-f")
            if can_save else "")
    return Div(*head,
               Div(Span(tm.dollars(sq.cents), cls="mx-p-n", data_slot="total"), Span(vs, cls="mx-vs" + ("" if vs else " is-empty"), data_vs="1"), cls="mx-p-tot"),
               P(Span(f"Preview · {age}" if age else "Preview", cls="mx-preview"), Span(SAMPLE, cls="mx-sample") if sq.sample else "", cls="mx-p-meta"),
               Div(*rows, cls="mx-rows"), Div(sky, cls="mx-p-sky") if sky is not None else "",
               Div(P(Span(BOOK_SAMPLE if sq.sample else BOOK_WORDS, cls="mx-soon-h"), " Books the stay" + ("s" if len(sq.stays) > 1 else "") + " here; the flight books on its airline’s site.", cls="mx-soon"),
                   book_form(s, lane, w, sq) if can_save else "",
                   P(saved, cls="mx-saved", role="status") if saved else form, cls="mx-acts"),
               cls="mx-p", data_open=sq.key)


# ---- the page --------------------------------------------------------------------------------------------------------

def _pop(key, words, *inside):
    return Details(Summary(words, cls="mx-tok"), Div(*inside, cls="mx-pop"), cls=f"mx-tk mx-tk-{key}", data_pop=key)


def _chip(text, to, on):
    return A(text, href=to, cls="mx-chip" + (" is-on" if on else ""), aria_current="true" if on else None)


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
    out.append(Span(found["dates"], cls="mx-word"))
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


def lane_el(s: State, lane, windows, days, known, marks, home, skies):
    totals = [known[tm.key(lane.key, w.key)].cents for w in windows if tm.key(lane.key, w.key) in known and known[tm.key(lane.key, w.key)].ok]
    drive = next((sq.drive for k, sq in known.items() if k.startswith(lane.key + "|") and sq.drive), None)
    col = {d: i + 2 for i, d in enumerate(days)}
    band_w = band_window(lane, windows, known)
    via = f"{home} → {lane.places[0].iata}" + (f" · {lane.places[-1].iata} → {home}" if lane.combo else "")
    kids = [Div(_arts(lane, "mx-thumb"), Div(P(lane.name, cls="mx-l-n"), P(via, cls="mx-l-s"),
                                                 P(f"{drive} min drive from {lane.places[0].iata}" if drive else "", cls="mx-l-s", data_lane_drive=lane.key, data_from=lane.places[0].iata),
                                                 P(f"from {tm.dollars(min(totals))}" if totals else "", cls="mx-l-best", data_lane_best=lane.key)), cls="mx-lh"),
            Div(cls="mx-band", data_band=lane.key, data_l=f"{band_w.nights} nights", style=f"grid-column: {col[band_w.depart]} / span {band_w.nights + 1}")]
    for w in windows:
        k = tm.key(lane.key, w.key)
        kids.append(square_el(s, lane, w, known.get(k), marks.get(k, ()), style=f"grid-column: {col[w.depart]}", wx=sky_of(skies, lane, w)))
    found = any("find" in marks.get(tm.key(lane.key, w.key), ()) for w in windows)
    return Div(*kids, cls="mx-lane" + (" is-asked" if lane.asked else "") + (" is-combo" if lane.combo else "") + (" is-found" if found else ""), data_lane=lane.key)


def band_window(lane, windows, known):
    """Where a lane's band sits: its cheapest answered start, else the asked one. assets/js/tripmatrix.js moves it the same way (and to an opened square)."""
    got = [(known[tm.key(lane.key, w.key)].cents, j, w) for j, w in enumerate(windows) if tm.key(lane.key, w.key) in known and known[tm.key(lane.key, w.key)].ok]
    return min(got)[2] if got else next((w for w in windows if w.asked), windows[0])


def skies_of(lanes, windows):
    days = days_of(windows)
    return {p.name: weather_for(p.name, days[0], days[-1]) for x in lanes for p in x.places}


def lanes_el(s: State, lanes, windows, known, marks, skies):
    days = days_of(windows)
    notes = list(dict.fromkeys(text_href for tw in skies.values() for text_href in weather.notes(tw)))
    starts = {w.depart for w in windows}
    axis = Div(Div(Span("Each place, day by day", cls="mx-label"), cls="mx-ah"),
               *[Div(Span(f"{d:%a}", cls="mx-adw"), Span(str(d.day) if d.day != 1 and d != days[0] else f"{d:%b} {d.day}", cls="mx-adn"),
                     cls="mx-ad" + (" is-ask" if d == s.depart else "") + (" is-start" if d in starts else "")) for d in days], cls="mx-axis")
    return Section(Div(axis, *[lane_el(s, x, windows, days, known, marks, s.home, skies) for x in lanes], cls="mx-lanes", style=f"--mx-days: {len(days)}"),
                   P(Span(cls="mx-key-band"), "The nights of the cheapest start (or the one you opened). Under each start day: the flight and the stay for "
                     f"{s.travelers}, all in, and that day’s weather where the trip starts.", cls="mx-legend"),
                   Div(*[A(text, href=to, rel="noopener", cls="mx-wx-n") if to else Span(text, cls="mx-wx-n") for text, to in notes], cls="mx-wx") if notes else "",
                   cls="mx-cal", aria_label="Every place, every start day")


def card_el(s: State, lane, windows, known, marks, skies):
    got = [(known[tm.key(lane.key, w.key)].cents, j, w) for j, w in enumerate(windows) if tm.key(lane.key, w.key) in known and known[tm.key(lane.key, w.key)].ok]
    best = min(got) if got else None
    via = f"{s.home} → {lane.places[0].iata}" + (f" · {lane.places[-1].iata} → {s.home}" if lane.combo else "")
    return Section(Div(_arts(lane, "mx-c-art"), H2(lane.name, cls="mx-c-n"), cls="mx-c-top"),
                   Div(Div(Span(tm.dollars(best[0]) if best else "", cls="mx-c-v", data_lane_best=lane.key),
                           Span(tm.when(best[2]) + " · its cheapest" if best else "", cls="mx-c-s", data_lane_when=lane.key), cls="mx-c-best"),
                       P(via, cls="mx-c-s"),
                       Div(*[square_el(s, lane, w, known.get(tm.key(lane.key, w.key)), marks.get(tm.key(lane.key, w.key), ()), day=True, wx=sky_of(skies, lane, w))
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
    data = {"lanes": [{"k": x.key, "n": x.name, "a": x.asked, "c": x.combo} for x in lanes],
            "windows": [{"k": w.key, "a": w.asked, "n": w.nights, "when": tm.when(w)} for w in windows],
            "days": [d.isoformat() for d in days_of(windows)],
            "known": {k: {"c": sq.cents, "s": sq.status} for k, sq in known.items()},
            "order": tm.order(lanes, windows), "budget": s.budget_cents, "nearly": tm.NEARLY_CENTS, "tile": href(s, TILE), "warm": href(s, WARM)}
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
    ages = [sq.fetched for sq in known.values() if sq.fetched]
    meta = Div(Span(Span(str(len(known)), id="mx-count-n"), f" of {total} in", cls="mx-count", id="mx-count", aria_live="polite"),
               Span(f"Preview · {age_words(min(ages))}" if ages else "Preview", cls="mx-preview", id="mx-age"),
               Span(SAMPLE, cls="mx-sample") if meta_sample else "", P(SLOW, cls="mx-slow", role="status"), import_el(), cls="mx-meta", id="mx-meta")
    opened = default_open(lanes, windows, known, found)
    if opened:
        o_lane, o_w = next(x for x in lanes if x.key == opened[0]), next(w for w in windows if w.key == opened[1])
        asked = next(x for x in lanes if x.asked)
        side = panel(s, o_lane, o_w, known.get(tm.key(*opened)), known.get(tm.key(asked.key, o_w.key)))
    else:
        side = Div(P("Open a square to see the whole trip: the flight, the stay, the drive.", cls="mx-p-note"), cls="mx-p")
    skies = skies_of(lanes, windows)
    stage = Div(Div(lanes_el(s, lanes, windows, known, marks, skies), cls="mx-main"), Aside(side, cls="mx-side", id="mx-side", aria_label="The square you opened", aria_live="polite"),
                cls="mx-stage")
    notes = list(dict.fromkeys(text_href for tw in skies.values() for text_href in weather.notes(tw)))
    cards = Div(*[card_el(s, x, windows, known, marks, skies) for x in lanes],
                Div(*[A(text, href=to, rel="noopener", cls="mx-wx-n") if to else Span(text, cls="mx-wx-n") for text, to in notes], cls="mx-wx") if notes else "",
                cls="mx-cards")      # the cards say a sky, so they carry its credit and labels too (the calendar's own are hidden on a phone)
    waiting = len(known) < total
    body = Div(H1(f"Trips to {s.place.name}" + (" and nearby" if s.nearby and len(lanes) > 1 else ""), cls="mx-sr"),
               Div(sentence(s, typed, problems), meta, cls="mx-lead"),
               Div(find_el(s, found), cls="mx-news", id="mx-news"),
               stage, cards,
               Div(P(SAMPLE_FINE if meta_sample else FINE, cls="mx-foot-n"), cls="mx-foot"),
               Script(NotStr(page_data(s, lanes, windows, known)), type="application/json", id="mx-data"),
               fact_el(s),      # last in the matrix: sticky to the bottom of the screen while the matrix is in view, never over the footer below it
               cls="mx", id="mx", data_waiting="1" if waiting else "0")
    return page(f"{s.place.name}: the whole trip, every start day", body, current="/plan/matrix", head=HEAD, noindex=True)


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
        return JSONResponse({"key": sq.key, "s": sq.status, "c": sq.cents, "inner": inner(sq), "label": label(lane_, w_, sq), "drive": sq.drive,
                             "age": age_words(sq.fetched), "panel": to_xml(panel(s, lane_, w_, sq, asked_sq))}, headers={"Cache-Control": "no-store"})

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
        try:
            await run_in_threadpool(save, session, s, lane_, w_, sq)      # database writes: off the event loop
        except importer.SaveError as e:
            return square_page(s, lane_, w_, sq, asked_sq, str(e), can_save=False)
        if request.headers.get("x-matrix") == "1":
            return JSONResponse({"saved": "Saved to your trip.", "trip": "/trip/cockpit"})
        return RedirectResponse(back + "&saved=1", status_code=303)
