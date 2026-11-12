"""The trip grid (F-217): every flight against every stay, one number a square, so the family weighs both at once.

GET /plan/grid          the grid for a trip: flights across, stays down, each square the whole trip's cost. Above it the search as one sentence and a strip of days
                        (move the trip a day, add a night); beside it the square being looked at, with the first day as the kids, an older traveler or a pet live it.
                        `q=` is a retyped sentence: it is read (gitaway/tripsentence.py) and answered with the same page at its plain address, or with what is missing.
GET /plan/grid/trip     the square that was chosen: its flight and its stay side by side, where each is booked (never here), and cheaper swaps.

Offers come from gitaway/gridsource.py: today only the showcase's sample catalog, so both routes are in showcase.HIDDEN and the page says "sample". The sums are
gitaway/tripgrid.py. Everything works as plain links; assets/js/tripgrid.js adds the look-ahead panel, the live budget and lens, and folds the top and the side
into small islands as the grid scrolls (D-420). It can wait on the weather: a plain `def` handler.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fasthtml.common import A, Aside, Button, Details, Div, Form, H1, H2, Input, Label, Link, NotStr, P, Script, Section, Span, Summary
from starlette.responses import RedirectResponse

from gitaway import catalog, gridsource, showcase, tripgrid, tripsentence, weather, zones
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import plan_search, weather_ui
from gitaway.partners import places

PATH = "/plan/grid"
TRIP = PATH + "/trip"
HEAD = (Link(rel="stylesheet", href="/assets/css/tripgrid.css"), Script(src="/assets/js/tripgrid.js", defer=True))
DAYS_BEFORE, DAYS_SHOWN = 5, 15
MIN_BUDGET, MAX_BUDGET, BUDGET_STEP = tripsentence.MIN_BUDGET_CENTS // 100, tripsentence.MAX_BUDGET_CENTS // 100, 50       # dollars: the slider's ends, and what the sentence reads as a budget
PETS = ("dog", "cat", "pet")
MAX_COLUMNS = 12                                             # tripgrid.css has a column rule for each count up to this
SAMPLE = "Sample prices. Nothing is booked."
FINE = "Every booking happens on the partner's site, under their terms and their support. GitAway never takes payment."
MISSING = {"place": "Say where to, like “to San Diego”.", "dates": "Say when, like “Dec 12 to 16”.", "party": f"GitAway plans for up to {catalog.MAX_TRAVELERS} travelers."}


@dataclass(frozen=True)
class State:
    """What the address says: the trip, and how the grid is being read."""
    trip: object
    budget_cents: int | None = None
    lens: str = "price"          # price | ease
    who: str = ""                # whose first day the Ease lens and the panel show: one of `whos`, or ""
    whos: tuple = ()
    senior: str = ""             # their word for an older traveler ("Grandma")
    pet: str = ""
    near: str = ""
    miles: int | None = None
    f: str = ""                  # the flight picked, or ""
    h: str = ""                  # the stay picked, or ""

    @property
    def pick(self):
        return (self.f, self.h) if self.f and self.h else None


def _whole(text, lo, hi):
    text = (text or "").strip()
    return int(text) if text.isascii() and text.isdigit() and lo <= int(text) <= hi else None


def state(to="", d="", r="", a="", k="", home="", focus="", f="", h="", b="", lens="", who="", senior="", pet="", near="", mi="") -> State:
    trip = plan_search.ahead(catalog.trip_from_url(d, r, a, k, to or "la", home, focus))
    senior = " ".join(re.findall(r"[A-Za-z]+", senior or ""))[:24]
    pet = pet if pet in PETS else ""
    near = " ".join("".join(c for c in (near or "") if c.isprintable()).split())[:places.MAX_NAME]
    whos = tuple(w for w, on in (("kids", trip.kid_ages), ("senior", senior), ("pet", pet)) if on)
    budget = _whole(b, MIN_BUDGET, MAX_BUDGET)
    return State(trip, budget * 100 if budget else None, "ease" if lens == "ease" and whos else "price", who if who in whos else (whos[0] if whos else ""), whos,
                 senior, pet, near, _whole(mi, 1, tripsentence.MAX_MILES) if near else None, f or "", h or "")


def params(s: State, **over) -> dict:
    t = s.trip
    q = {"to": t.key, "d": t.depart.isoformat(), "r": t.return_.isoformat(), "a": t.adults, "k": ",".join(map(str, t.kid_ages)), "home": t.home, "focus": t.focus,
         "senior": s.senior, "pet": s.pet, "near": s.near, "mi": s.miles, "b": s.budget_cents // 100 if s.budget_cents else "",
         "lens": s.lens if s.lens == "ease" else "", "who": s.who if s.whos and s.who != s.whos[0] else "", "f": s.f, "h": s.h}
    q.update(over)
    return {n: v for n, v in q.items() if v not in ("", None)}


def href(s: State, path=PATH, **over) -> str:
    return f"{path}?" + urlencode(params(s, **over))


def ask_of(s: State) -> tripsentence.Ask:
    t = s.trip
    return tripsentence.Ask(place=t.destination_name, origin=t.origin, depart=t.depart, return_=t.return_, adults=t.adults, kid_ages=t.kid_ages, ages_given=True,
                            senior=s.senior, pet=s.pet, near=s.near, miles=s.miles, budget_cents=s.budget_cents, party_given=True)


def who_name(s: State, who) -> str:
    if who == "senior":
        return f"{s.senior}’s day" if " " not in s.senior else "Their day"
    return "Kids’ day" if who == "kids" else f"The {s.pet}’s day"


def place_key(text):
    """(catalog key, focus) for a typed place the sample catalog has, else None."""
    typed = " ".join((text or "").lower().split())
    for dest in catalog.DESTINATIONS:
        if typed in (dest.key, dest.name.lower(), dest.short.lower()):
            return dest.key, ""
    known = places.resolve(text)
    if known and known.known:
        for dest in catalog.DESTINATIONS:
            if dest.name == known.name or (known.focus == "disney" and dest.key == "la"):
                return dest.key, known.focus if known.focus in catalog.FOCUS.get(dest.key, ()) else ""
    return None


def clock_shift(trip) -> int:
    """Minutes the place's clocks run ahead of home's on the first day (negative: behind); 0 when either zone is not known."""
    home, there = zones.AIRPORTS.get(trip.origin), zones.AIRPORTS.get(trip.airports[0] if trip.airports else "")
    if not home or not there:
        return 0
    noon = datetime(trip.depart.year, trip.depart.month, trip.depart.day, 12)
    return int((noon.replace(tzinfo=ZoneInfo(home)).utcoffset() - noon.replace(tzinfo=ZoneInfo(there)).utcoffset()).total_seconds() // -60)


def focus_cell(grid, s: State):
    """The square the panel shows before anything is looked at: the pick; else the best of the picked row or column; else the best of all."""
    cells = [c for c in grid.cells.values() if (not s.f or c.flight.id == s.f) and (not s.h or c.stay.id == s.h)] or list(grid.cells.values())
    ease = s.lens == "ease" and s.who
    return min(cells, key=lambda c: ((c.days[s.who].score,) if ease else ()) + (c.cents, c.flight.id, c.stay.id))


def sub(grid, cell, tone, s: State) -> str:
    """The small line of a square. assets/js/tripgrid.js `sub` says the same words when the budget or the lens changes on the page."""
    if s.lens == "ease" and s.who:
        word = cell.days[s.who].word
        return f"your pick · {word}" if tone == "mine" else (f"easiest · {word}" if tone == "best" else word)
    if tone == "mine":
        return "your pick"
    if tone == "best":
        return "lowest"
    if s.budget_cents and cell.cents > s.budget_cents:
        return f"over by {catalog.money(cell.cents - s.budget_cents)}"
    return f"+{catalog.money(cell.cents - grid.lowest.cents)}"


def left_text(cents, s: State) -> str:
    if not s.budget_cents:
        return "No budget set"
    over = cents - s.budget_cents
    return f"{catalog.money(over)} over your {catalog.money(s.budget_cents)}" if over > 0 else f"{catalog.money(-over)} under your {catalog.money(s.budget_cents)}"


def panel_title(s: State) -> str:
    """What the panel calls the square it starts on. assets/js/tripgrid.js `title` says the same words."""
    if s.pick:
        return "Your pick · all in"
    of = " for this flight" if s.f else (" for this stay" if s.h else "")
    return ("Easiest" if s.lens == "ease" and s.who else "Lowest") + of + " · all in"


def flight_line(f) -> str:
    return f"{tripgrid.clock(f.depart_min)} · {f.stops_text} · {catalog.money(f.cents)}"


def stay_line(st) -> str:
    return f"{st.name} · {catalog.money(st.cents)}"


# ---- the top: the sentence and the days ------------------------------------------------------------------------------------------------

def _pop(key, words, *inside, cls=""):
    return Details(Summary(words, cls="tg-tok"), Div(*inside, cls="tg-pop"), cls=f"tg-tk tg-tk-{key} {cls}".strip(), data_pop=key)


def _hidden(s: State, *skip):
    return [Input(type="hidden", name=n, value=str(v)) for n, v in params(s).items() if n not in skip]


def sentence(s: State, typed="", problems=()):
    found = dict(tripsentence.parts(ask_of(s)))
    out = [Span(found["party"] + ("" if "with" in found else ","), cls="tg-w")]
    if "with" in found:
        tabs = [A(who_name(s, w), href=href(s, who=w, lens="ease"), cls="tg-chip" + (" is-on" if w == s.who else ""), data_who=w, aria_current="true" if w == s.who else None) for w in s.whos]
        out.append(_pop("with", found["with"] + ",", P("Whose first day should be easiest?", cls="tg-pop-h"), Div(*tabs, cls="tg-chips"),
                        P("Ease ranks the squares by that day.", cls="tg-pop-note")))
    out.append(Span(found["route"] + ",", cls="tg-w"))
    out.append(Span(found["dates"] + ",", cls="tg-w"))
    if "near" in found:
        out.append(_pop("near", found["near"] + ",", P(f"Near {s.near}", cls="tg-pop-h"),
                        P("GitAway cannot measure that distance yet. Each stay says its own area, so you can judge.", cls="tg-pop-note")))
    value = s.budget_cents // 100 if s.budget_cents else 3000
    out.append(_pop("budget", found.get("budget", "any budget"),
                    Form(P("Your budget, all in", cls="tg-pop-h"), *_hidden(s, "b"),
                         Label(Input(type="range", name="b", min=str(MIN_BUDGET), max=str(MAX_BUDGET), step=str(BUDGET_STEP), value=str(value), aria_label="Budget in dollars", id="tg-budget"),
                               Span(catalog.money(value * 100), cls="tg-pop-val", id="tg-budget-val"), cls="tg-slide"),
                         Div(Button("Set", type="submit", cls="btn btn-ink tg-set"), A("No budget", href=href(s, b=""), cls="tg-chip", id="tg-budget-none"), cls="tg-chips"),
                         P("Squares over it turn grey.", cls="tg-pop-note"), method="get", action=PATH, id="tg-budget-form")))
    edit = Details(Summary(icon("pencil", 18, 2.2), Span("Retype the search", cls="tg-sr"), cls="tg-pen", aria_label="Retype the search"),
                   Form(Label(Span("Say it your way", cls="tg-pop-h"), Input(type="text", name="q", value=typed or tripsentence.write(ask_of(s)), maxlength=str(tripsentence.MAX_TEXT), autocomplete="off",
                                                                            spellcheck="false", id="tg-q", **({"aria_invalid": "true", "aria_describedby": "tg-q-err"} if problems else {}))),
                        *([P(" ".join(problems), cls="tg-err", id="tg-q-err", role="alert")] if problems else []),
                        Button("Search", type="submit", cls="btn btn-ink tg-set"), method="get", action=PATH, cls="tg-pop tg-pop-edit"),
                   cls="tg-tk tg-edit", data_pop="edit", open=bool(problems))
    return Div(*out, edit, cls="tg-sent", id="tg-sent")


def lens_switch(s: State, cls="tg-seg"):
    if not s.whos:
        return ""
    return Div(*[A(label, href=href(s, lens=key if key == "ease" else ""), cls="tg-seg-b" + (" is-on" if s.lens == key else ""), data_lens=key, aria_current="true" if s.lens == key else None)
                 for key, label in (("price", "Price"), ("ease", "Ease"))], cls=cls, role="group", aria_label="Rank the squares by")


def strip_days(s: State):
    first = max(catalog.today(), s.trip.depart - timedelta(days=DAYS_BEFORE))
    return [first + timedelta(days=i) for i in range(DAYS_SHOWN)]


def strip_weather(s: State, days):
    t = s.trip
    return weather.trip_weather(SimpleNamespace(depart=days[0], return_=days[-1], destination_name=t.destination_name, key=t.key, focus=t.focus, tz=""))


def _move(s: State, by):
    """The trip moved `by` days, the same length, or None when that would start in the past."""
    t = s.trip
    return href(s, d=(t.depart + timedelta(days=by)).isoformat(), r=(t.return_ + timedelta(days=by)).isoformat()) if t.depart + timedelta(days=by) >= catalog.today() else None


def _arrow(to, label, ico, cls="tg-rb"):
    return A(icon(ico, 18, 2.4), href=to, cls=cls, aria_label=label) if to else Span(icon(ico, 18, 2.4), cls=f"{cls} is-off", aria_hidden="true")


def dates(s: State, days, tw):
    t, nights = s.trip, s.trip.nights
    known = {d.date: d for d in tw.days if d}
    cells = []
    for day in days:
        inn, out = t.depart <= day < t.return_, day == t.return_
        w = known.get(day)
        said = f"{day:%A %B} {day.day}" + (f", {'typical high' if w.kind == weather.NORMAL else 'high'} {w.high_f}°F" if w else "") + ", leave this day"
        cells.append(A(Span(f"{day:%b} {day.day}" if day.day == 1 else f"{day:%a}", cls="tg-dow"), Span(str(day.day), cls="tg-num"), Span(f"{w.high_f}°" if w else "", cls="tg-deg"),
                       href=href(s, d=day.isoformat(), r=(day + timedelta(days=nights)).isoformat()), cls="tg-day" + (" is-in" if inn else " is-out" if out else ""), aria_label=said,
                       aria_current="date" if day == t.depart else None))
    fewer = href(s, r=(t.return_ - timedelta(days=1)).isoformat()) if nights > 1 else None
    more = href(s, r=(t.return_ + timedelta(days=1)).isoformat()) if nights < catalog.MAX_NIGHTS else None
    return Div(_arrow(_move(s, -1), "A day earlier", "chev-left"), Div(*cells, cls="tg-days", role="group", aria_label="Trip dates"), _arrow(_move(s, 1), "A day later", "chev-right"),
               _arrow(fewer, "One night fewer", "minus"), Span(t.nights_text, cls="tg-nights"), _arrow(more, "One night more", "plus"), cls="tg-dates", id="tg-dates")


def island(s: State, tw):
    known = [d.high_f for d, day in zip(tw.days, strip_days(s)) if d and s.trip.depart <= day <= s.trip.return_]
    temps = (f" · {min(known)}°" if min(known) == max(known) else f" · {min(known)}–{max(known)}°") if known else ""
    said = Button(Span(tripsentence.dates_words(ask_of(s)), cls="tg-isle-d"), Span(temps + (f" · {catalog.money(s.budget_cents)}" if s.budget_cents else ""), cls="tg-isle-x", id="tg-isle-x"),
                  icon("chev-right", 16, 2.4, "tg-isle-chev"), type="button", cls="tg-isle-b", id="tg-open-top", aria_label="Show the search and the dates")
    return Div(Div(_arrow(_move(s, -1), "A day earlier", "chev-left", "tg-ic"), said, _arrow(_move(s, 1), "A day later", "chev-right", "tg-ic"), lens_switch(s, "tg-seg tg-seg-isle"), cls="tg-isle on-ink"),
               cls="tg-isle-l", id="tg-isle")


# ---- the grid --------------------------------------------------------------------------------------------------------------------------

def grid_el(grid, s: State, sample=False):
    heads = []
    for f in grid.flights:
        on = f.id == s.f
        heads.append(A(Span(Span(tripgrid.clock(f.depart_min), cls="tg-h1"), Span(f"lands {tripgrid.clock(f.arrive_min)}" + (" next day" if f.overnight else ""), cls="tg-h2")),
                       Span(Span(f"{f.name} · {f.stops_text}", cls="tg-h3"), Span(f"{catalog.money(f.cents)} for {s.trip.travelers}", cls="tg-h2 tg-b")),
                       href=href(s, f="" if on else f.id), cls="tg-fh" + (" is-on" if on else ""), data_f=f.id, aria_current="true" if on else None,
                       aria_label=f"{f.name}, leaves {tripgrid.clock(f.depart_min)}, {f.stops_text}, {catalog.money(f.cents)} for {s.trip.travelers}. {'Picked. Unpick' if on else 'Pick'} this flight"))
    rows = [Div(Div(Span(SAMPLE, cls="tg-sample") if sample else "", Span(f"{len(grid.flights)} flights across", cls="tg-k-f"), Span(f"{len(grid.stays)} stays down", cls="tg-k-s"),
                    Span("Each square is the whole trip.", cls="tg-corner-n"), cls="tg-corner"),
                *heads, cls="tg-row tg-head")]
    for st in grid.stays:
        on = st.id == s.h
        head = A(Span(Span(st.name, cls="tg-h1"), Span(catalog.money(st.cents), cls="tg-h1"), cls="tg-sh-top"), Span(" · ".join(x for x in (st.area, st.detail, *st.tags) if x), cls="tg-h3"),
                 href=href(s, h="" if on else st.id), cls="tg-sh" + (" is-on" if on else ""), data_h=st.id, aria_current="true" if on else None,
                 aria_label=f"{st.name}, {st.area}, {catalog.money(st.cents)}. {'Picked. Unpick' if on else 'Pick'} this stay")
        cells = []
        for f in grid.flights:
            cell = grid.cell(f.id, st.id)
            tone = grid.tone(cell, s.pick, s.lens, s.who, s.budget_cents)
            words = sub(grid, cell, tone, s)
            cells.append(A(Span(catalog.money(cell.cents), cls="tg-total"), Span(words, cls="tg-sub"), Span(f"{tripgrid.clock(f.depart_min)} · {f.stops_text}", cls="tg-when"),
                           href=href(s, TRIP, f=f.id, h=st.id), cls=f"tg-cell is-{tone}", data_cell=f"{f.id}|{st.id}",
                           data_say=f"{st.name} with the {tripgrid.clock(f.depart_min)} flight, {catalog.money(cell.cents)}",
                           aria_label=f"{st.name} with the {tripgrid.clock(f.depart_min)} flight, {catalog.money(cell.cents)}, {words}"))
        rows.append(Div(head, Div(*cells, cls="tg-cells"), cls="tg-row"))
    return Div(*rows, cls="tg-grid", id="tg-grid", data_lens=s.lens)


# ---- the side: the square being looked at ------------------------------------------------------------------------------------------------

def _slot(name, text, cls="", tag=Span):
    return tag(text, cls=cls, data_slot=name)


def day_card(s: State, cell):
    if not s.whos:
        return ""
    d = cell.days[s.who]
    tabs = [A(who_name(s, w), href=href(s, who=w), cls="tg-chip" + (" is-on" if w == s.who else ""), data_who=w, aria_current="true" if w == s.who else None) for w in s.whos]
    facts = [Span(_slot(f"k{i}", k, "tg-fk"), _slot(f"v{i}", v, "tg-fv"), cls="tg-fact") for i, (k, v) in enumerate(d.facts)]
    return Section(Div(*tabs, cls="tg-chips tg-whos", role="group", aria_label="Whose first day") if len(s.whos) > 1 else H2(who_name(s, s.who), cls="tg-card-h"),
                   Div(*facts, cls="tg-facts"), _slot("verdict", d.verdict, "tg-verdict", P), _slot("note", d.note, "tg-note", P), cls="tg-card tg-daycard", id="tg-day")


def side(grid, s: State, cell, found):
    title = panel_title(s)
    full = Div(Section(_slot("title", title, "tg-card-h"), _slot("total", catalog.money(cell.cents), "tg-big"), _slot("left", left_text(cell.cents, s), "tg-dim"),
                       Span("Flights and the stay. No car or rides in it.", cls="tg-dim"), cls="tg-card tg-sum on-ink"),
               Section(Div(icon("plane", 18, 2.2), _slot("flight", flight_line(cell.flight)), cls="tg-line tg-k-f"), Div(icon("bed", 18, 2.2), _slot("stay", stay_line(cell.stay)), cls="tg-line tg-k-s"),
                       _slot("room", " · ".join(x for x in (cell.stay.area, cell.stay.detail) if x), "tg-note", P), cls="tg-card"),
               day_card(s, cell),
               A("Continue with this trip", icon("arrow-right", 18, 2.4), href=href(s, TRIP, f=cell.flight.id, h=cell.stay.id), cls="btn btn-ink tg-go", id="tg-go"),
               cls="tg-full")
    word = cell.days[s.who].word.replace(" day", "") if s.whos else ""
    rail = Div(Button(Span(_slot("rail-total", catalog.money(cell.cents), "tg-rail-big"), cls="tg-rail-i"),
                      Span(icon("plane", 18, 2.2), _slot("rail-flight", tripgrid.clock(cell.flight.depart_min)), cls="tg-rail-i"),
                      Span(icon("bed", 18, 2.2), _slot("rail-stay", cell.stay.name), cls="tg-rail-i"),
                      Span(icon("sun", 18, 2.2), _slot("rail-day", word), cls="tg-rail-i") if s.whos else "",
                      type="button", cls="tg-rail on-ink", id="tg-open-side", aria_label="Show this trip's details"),
               A(icon("arrow-right", 20, 2.4), href=href(s, TRIP, f=cell.flight.id, h=cell.stay.id), cls="tg-rail-go on-ink", aria_label="Continue with this trip", data_go="1"),
               cls="tg-mini")
    return Aside(full, rail, cls="tg-side", id="tg-side", aria_label="The trip you are looking at")


def page_data(grid, s: State, cell) -> str:
    """What assets/js/tripgrid.js needs to fill the panel and re-mark the squares without asking again."""
    easy = {w: grid.easiest(w) for w in grid.whos}
    data = {
        "cells": {f"{c.flight.id}|{c.stay.id}": {"c": c.cents, "d": {w: {"s": d.score, "w": d.word, "f": [list(x) for x in d.facts], "v": d.verdict, "n": d.note} for w, d in c.days.items()}}
                  for c in grid.cells.values()},
        "flights": {f.id: {"line": flight_line(f), "at": tripgrid.clock(f.depart_min)} for f in grid.flights},
        "stays": {st.id: {"line": stay_line(st), "name": st.name, "room": " · ".join(x for x in (st.area, st.detail) if x)} for st in grid.stays},
        "low": f"{grid.lowest.flight.id}|{grid.lowest.stay.id}", "easy": {w: f"{c.flight.id}|{c.stay.id}" for w, c in easy.items()},
        "pick": "|".join(s.pick) if s.pick else "", "f": s.f, "h": s.h, "budget": s.budget_cents, "lens": s.lens, "who": s.who, "whos": list(s.whos), "hard": tripgrid.HARD_FROM,
    }
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


# ---- the pages -------------------------------------------------------------------------------------------------------------------------

def _foot(found, tw=None):
    return Div(P(showcase.PREVIEW, cls="tg-foot-n") if found.sample else "", *(weather_ui.notes(tw, "tg-foot-n", "tg-foot-a") if tw else ()), P(FINE, cls="tg-foot-n"), cls="tg-foot")


def grid_page(s: State, found, typed="", problems=()):
    grid = tripgrid.build(found.flights, found.stays, s.whos, found.drive_min, clock_shift(s.trip))
    ids_f, ids_h = {f.id for f in grid.flights}, {st.id for st in grid.stays}
    s = State(**{**s.__dict__, "f": s.f if s.f in ids_f else "", "h": s.h if s.h in ids_h else ""})
    cell = focus_cell(grid, s)
    days = strip_days(s)
    tw = strip_weather(s, days)
    stage = Div(Div(Div(P(SAMPLE, cls="tg-sample tg-sample-top") if found.sample else "", grid_el(grid, s, found.sample), cls="tg-pad", data_n=str(min(len(grid.flights), MAX_COLUMNS))), cls="tg-scroll", id="tg-scroll", tabindex="0", role="region", aria_label="Every flight with every stay"),
                Div(Div(Div(sentence(s, typed, problems), lens_switch(s), cls="tg-top"), dates(s, days, tw), cls="tg-open", id="tg-open"), island(s, tw), cls="tg-chrome", id="tg-chrome"),
                side(grid, s, cell, found), cls="tg-stage", id="tg-stage", data_top="open", data_side="open")
    return page(f"{s.trip.destination_name}: flights and stays", Div(H1(f"Flights and stays for {s.trip.destination_name}", cls="tg-sr"), stage, _foot(found, tw),
                                                                     Script(NotStr(page_data(grid, s, cell)), type="application/json", id="tg-data"), cls="tg"),
                current="/plan", head=HEAD, noindex=True)


def _facts(*rows):
    return Div(*[Div(Span(k, cls="tg-fk"), Span(v, cls="tg-fv"), cls="tg-kv") for k, v in rows if v], cls="tg-kvs")


def _books(found, item, primary=True):
    return Div(*[A(icon("ext", 18, 2.2), label, href=to, cls="btn tg-book" + (" btn-ink" if primary and i == 0 else ""), rel="sponsored noopener") for i, (label, to) in enumerate(found.book(item))], cls="tg-books")


def trip_page(s: State, found):
    grid = tripgrid.build(found.flights, found.stays, s.whos, found.drive_min, clock_shift(s.trip))
    cell = grid.cell(s.f, s.h)
    if cell is None:
        return RedirectResponse(href(s, f="", h=""), status_code=303)
    f, st = cell.flight, cell.stay
    swaps = []
    cheaper_f = min((c for c in grid.cells.values() if c.stay.id == st.id), key=lambda c: (c.cents, c.flight.id))
    if cheaper_f.cents < cell.cents:
        swaps.append((f"Fly at {tripgrid.clock(cheaper_f.flight.depart_min)} ({cheaper_f.flight.stops_text}) and keep {st.name}", cell.cents - cheaper_f.cents, href(s, TRIP, f=cheaper_f.flight.id)))
    cheaper_s = min((c for c in grid.cells.values() if c.flight.id == f.id), key=lambda c: (c.cents, c.stay.id))
    if cheaper_s.cents < cell.cents:
        swaps.append((f"Stay at {cheaper_s.stay.name} ({cheaper_s.stay.area}) and keep your flight", cell.cents - cheaper_s.cents, href(s, TRIP, h=cheaper_s.stay.id)))
    days = [Section(H2(who_name(s, w), cls="tg-card-h"), Div(*[Span(Span(k, cls="tg-fk"), Span(v, cls="tg-fv"), cls="tg-fact") for k, v in d.facts], cls="tg-facts"),
                    P(d.verdict, cls="tg-verdict"), P(d.note, cls="tg-note"), cls="tg-card") for w, d in cell.days.items()]
    body = Div(
        Div(A(icon("chev-left", 18, 2.4), "Back to the grid", href=href(s), cls="btn tg-back"), H1(f"Your trip · {tripsentence.dates_words(ask_of(s))}", cls="tg-rev-h"),
            Span(SAMPLE, cls="tg-sample") if found.sample else "", cls="tg-rev-top"),
        Div(Section(H2(icon("plane", 18, 2.2), f"Flight · {s.trip.origin} to {f.airport}", cls="tg-card-h tg-k-f"), P(f"{tripgrid.clock(f.depart_min)} → {tripgrid.clock(f.arrive_min)}", cls="tg-rev-big"),
                    _facts((f.name, f.stops_text), (f"For the {s.trip.travelers} of you", catalog.money(f.cents)), ("Bags and seats", "shown by the seller")),
                    _books(found, f), cls="tg-card tg-rev-card", id="tg-rev-flight"),
            Section(H2(icon("bed", 18, 2.2), f"Stay · {s.trip.nights_text}", cls="tg-card-h tg-k-s"), P(st.name, cls="tg-rev-big"),
                    _facts(("Where", st.area), ("Room", st.detail), ("Good to know", ", ".join(st.tags)), ("Guests say", st.rating), (s.trip.nights_text.capitalize(), catalog.money(st.cents))),
                    _books(found, st), cls="tg-card tg-rev-card", id="tg-rev-stay"),
            Aside(Section(Span("All in", cls="tg-card-h"), Span(catalog.money(cell.cents), cls="tg-big"), Span(left_text(cell.cents, s), cls="tg-dim"),
                          Span("Flights and the stay. No car or rides in it.", cls="tg-dim"), cls="tg-card tg-sum on-ink"),
                  *days,
                  Section(H2("Before you book", cls="tg-card-h"),
                          *([A(Span(text, cls="tg-swap-t"), Span(f"{catalog.money(save)} less", cls="tg-swap-s"), href=to, cls="tg-swap") for text, save, to in swaps]
                            or [P("Nothing cheaper on these dates.", cls="tg-note")]), cls="tg-card", id="tg-swaps"),
                  cls="tg-rev-side"),
            cls="tg-rev"),
        _foot(found), cls="tg tg-review")
    return page(f"Your trip to {s.trip.destination_name}", body, current="/plan", head=HEAD, noindex=True)


def from_sentence(q, s: State):
    """A retyped sentence: (State at its plain address, None), or (None, a response) that says what is missing or sends an unknown place to the honest lanes."""
    ask = tripsentence.read(q)
    if ask.unread:
        return None, [MISSING[x] for x in ask.unread]
    found = place_key(ask.place)
    kids = ",".join(map(str, ask.kid_ages))
    if not found:
        go = {"place": ask.place, "d": ask.depart.isoformat(), "r": ask.return_.isoformat(), "a": ask.adults, **({"k": kids} if kids else {}), **({"home": ask.origin} if ask.origin else {})}
        return None, RedirectResponse("/plan?" + urlencode(go), status_code=303)
    key, focus = found
    try:
        catalog.parse_trip(ask.origin, key, ask.depart.isoformat(), ask.return_.isoformat(), str(ask.adults), kids, focus=focus)
    except catalog.TripError as e:
        return None, list(dict.fromkeys(m for _, m in e.errors))
    new = state(key, ask.depart.isoformat(), ask.return_.isoformat(), str(ask.adults), kids, ask.origin, focus, "", "", str(ask.budget_cents // 100) if ask.budget_cents else "",
                s.lens, "", ask.senior, ask.pet, ask.near, str(ask.miles or ""))
    return new, None


def register(app):
    @app.get(PATH)
    def trip_grid(q: str = "", to: str = "", d: str = "", r: str = "", a: str = "", k: str = "", home: str = "", focus: str = "", f: str = "", h: str = "", b: str = "", lens: str = "",
                  who: str = "", senior: str = "", pet: str = "", near: str = "", mi: str = ""):
        s = state(to, d, r, a, k, home, focus, f, h, b, lens, who, senior, pet, near, mi)
        problems = ()
        if q.strip():
            new, answer = from_sentence(q, s)
            if new is not None:
                return RedirectResponse(href(new), status_code=303)
            if not isinstance(answer, list):
                return answer
            problems = answer
        found = gridsource.offers(s.trip)
        if found is None:
            return showcase.not_found()
        return grid_page(s, found, typed=q if problems else "", problems=problems)

    @app.get(TRIP)
    def trip_grid_trip(to: str = "", d: str = "", r: str = "", a: str = "", k: str = "", home: str = "", focus: str = "", f: str = "", h: str = "", b: str = "", lens: str = "", who: str = "",
                       senior: str = "", pet: str = "", near: str = "", mi: str = ""):
        s = state(to, d, r, a, k, home, focus, f, h, b, lens, who, senior, pet, near, mi)
        found = gridsource.offers(s.trip)
        if found is None:
            return showcase.not_found()
        return trip_page(s, found)
