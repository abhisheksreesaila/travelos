"""The opened square, as one view of the whole trip (F-242, D-570 to D-579): the hotel, the flight, the sky for those nights and the total, with "Book this trip" the boldest
thing on the screen. One function, `view`, draws it for the laptop's side (the design's A2 "Trip line": the sky over a timeline of flight, stay and rides, then the cards),
the phone's sheet (A3 "Bento": coloured tiles, a sticky total and Book bar) and the square's own page; CSS (assets/css/tripview.css) lays it out by width.

Where the source gave alternatives (`Square.flights`, `Square.stay_alts`) each is drawn as an option of its tile; assets/js/tripview.js flips between them in place, moves the
total, and keeps the forms' `fl` and `st` fields (the chosen indexes) in step, so Book and Save to trip send the choice, never a price. The server reads the indexes again
(`tm.pick`) and prices the trip itself. Nothing here is invented: a photo is the source's own, else the place's art; the weather is weather_for's (typical days say so).
"""

import re

from fasthtml.common import Button, Div, Form, H3, H4, Img, Input, P, Section, Span

from gitaway import catalog, tripmatrix as tm
from gitaway.icons import icon
from gitaway.pages.tripmatrix import CHEAPEST_FOUND
from gitaway.pages.skystrip import sky_strip, weather_for

CLOCKS = re.compile(r"[A-Z]{3} \d{1,2}:\d{2} [AP]M → [A-Z]{3} \d{1,2}:\d{2} [AP]M(?: next day)?")


def times(leg: str) -> str:
    """"SFO 8:05 AM → SAN 9:32 AM" out of a leg's words ("Sat, Dec 12 · SFO 8:05 AM → SAN 9:32 AM · Nonstop"), or the words as they are."""
    m = CLOCKS.search(leg or "")
    return m.group(0) if m else (leg or "")


def stops_words(n: int) -> str:
    return "Nonstop" if not n else f"{n} stop" + ("" if n == 1 else "s")


def _flip(kind, n, i=0):
    """The counter and the two arrows of a tile with a choice; nothing at all where the source gave one."""
    if n < 2:
        return ""
    return Div(Span(f"{i + 1} of {n}", cls="mx-ct", data_count="1"),
               Button(icon("chev-left", 18, 2.6), type="button", cls="mx-flip", data_flip="-1", aria_label=f"The previous {kind}"),
               Button(icon("chev-right", 18, 2.6), type="button", cls="mx-flip", data_flip="1", aria_label=f"The next {kind}"), cls="mx-flips")


def _flight_opt(f: tm.FlightPart, i: int, home_back: str = ""):
    return Div(Div(P(f.airline, cls="mx-o-h"), Span(stops_words(f.stops), cls="mx-o-chip"), Span(catalog.money(f.cents), cls="mx-o-n"), cls="mx-o-top"),
               Div(Span("Out", cls="mx-leg-k"), Span(times(f.out), cls="mx-leg-t"), cls="mx-leg"),
               Div(Span("Back", cls="mx-leg-k"), Span(times(f.back), cls="mx-leg-t"), cls="mx-leg") if f.back else "",
               P(CHEAPEST_FOUND, cls="mx-o-s") if not f.complete else "",
               cls="mx-opt", data_c=f.cents, data_short=f.airline, data_out=times(f.out), data_back=times(f.back), hidden=i != 0)


def _stay_media(st: tm.StayPart, place):
    from gitaway.pages import tripmatrix as mx
    if st.photo:
        return Img(src=st.photo, alt=f"{st.name}, the hotel's own photo", loading="lazy", cls="mx-o-photo", referrerpolicy="no-referrer")
    return mx._art(place, "mx-o-photo mx-o-art")      # the source gave no photo: the place's own drawing, never an area photo as the hotel


def _stay_opt(st: tm.StayPart, i: int, place, multi: bool):
    bits = [st.room, "Breakfast" if st.board == "breakfast" else st.board.capitalize(), "Refundable" if st.refundable else "Non-refundable"]
    return Div(_stay_media(st, place),
               Div(Div(H4(st.name, cls="mx-o-h"), Span(catalog.money(st.cents), cls="mx-o-n"), cls="mx-o-top"),
                   P(icon("star", 14, 2), st.rating, cls="mx-o-rate") if st.rating else "",
                   P(icon("pin", 14, 2.2), st.address, cls="mx-o-addr") if st.address else "",
                   P(" · ".join(b for b in bits if b), cls="mx-o-s"),
                   P(f"{st.nights} nights" + (f" in {st.place}" if multi else ""), cls="mx-o-s"),
                   P(f"{catalog.money(st.due_at_stay_cents)} of it paid at the hotel", cls="mx-o-s mx-r-due") if st.due_at_stay_cents else "", cls="mx-o-body"),
               cls="mx-opt", data_c=st.cents, data_short=st.name, hidden=i != 0)


def _tile(kind, label, ic, opts, flip, cls=""):
    return Section(Div(Span(icon(ic, 16, 2.4), cls="mx-kt k-" + kind), Span(label, cls="mx-tile-k"), flip, cls="mx-tile-top"),
                   Div(*opts, cls="mx-opts"), cls=f"mx-tile mx-tile-{kind} {cls}".strip(), data_slot_kind=kind, data_i="0")


def _block(kind, ic, *words, col, mirror=""):
    return Div(icon(ic, 14, 2.4), *([Span(words[0], data_mirror=mirror)] if mirror else [words[0]]), *words[1:], cls=f"mx-g-b k-{kind}", style=f"grid-column: {col}")


def _row(kind, ic, label, *blocks):
    return Div(Div(Span(icon(ic, 14, 2.4), cls=f"mx-kt k-{kind}"), Span(label, cls="mx-g-n"), cls="mx-g-l"), Div(*blocks, cls="mx-g-days"), cls="mx-g-row")


def _gantt_el(lane, w, sq, s):
    """The timeline under the sky (laptop): a column a day; the flights on the first and last day, each stay across its nights, the rides from and to the airport. A block carries
    the chosen option's words (data-mirror), which assets/js/tripview.js keeps in step when a choice is switched."""
    n = w.nights + 1
    stays, at = [], 1
    for i, (st, (_, a, b)) in enumerate(zip(sq.stays, tm.stays_for(lane, w))):
        nights = (b - a).days
        span = nights + (1 if i == len(sq.stays) - 1 else 0)
        stays.append(_block("stay", "bed", st.name, Span(f" · {st.nights} nights", cls="mx-g-s"), col=f"{at} / span {span}", mirror=f"stay{i}"))
        at += nights
    rows = [_row("flight", "plane", "Flights", _block("flight", "plane", sq.flight.airline, col="1 / span 2", mirror="flight"),
                 _block("flight", "plane", sq.flight.airline, col=f"{max(1, n - 1)} / span 2", mirror="flight") if sq.flight.back else ""),
            _row("stay", "bed", "Stay", *stays)]
    if sq.drive:
        rows.append(_row("car", "car", "Rides", _block("car", "car", f"{sq.drive} min", col="1"), _block("car", "car", f"{sq.drive} min", col=str(n))))
    return Div(*rows, cls="mx-gantt", style=f"--mx-n: {n}", aria_hidden="true")


def _cost(sq, lane, view_id=""):
    rows = [Div(Span(icon("plane", 14, 2.4), cls="mx-kt k-flight"), Span(sq.flight.airline, cls="mx-c-t", data_mirror="flight"), Span(catalog.money(sq.flight.cents), cls="mx-c-n", data_cost="flight"),
               cls="mx-c-row")]
    for i, st in enumerate(sq.stays):
        rows.append(Div(Span(icon("bed", 14, 2.4), cls="mx-kt k-stay"), Span(f"{st.nights} nights · ", Span(st.name, data_mirror=f"stay{i}"), cls="mx-c-t"),
                        Span(catalog.money(st.cents), cls="mx-c-n", data_cost=f"stay{i}"), cls="mx-c-row"))
    return Div(*rows, cls="mx-c-rows")


def view(s, lane, w, sq, asked_sq=None, saved="", can_save=True):
    """The opened square's whole view. A square still searching, or one with a problem, is the title and one sentence (no total, no buttons)."""
    from gitaway.pages import tripmatrix as mx
    nights = (f"{w.nights // 2} nights each" if lane.combo and w.nights % 2 == 0 else
              " · ".join(f"{(b - a).days} in {p.name}" for p, a, b in tm.stays_for(lane, w)) if lane.combo else f"{w.nights} nights")
    head = Div(H3(f"{lane.name} · {tm.when(w)}", cls="mx-p-h"), P(f"{nights} · {mx.party_words(s)}", cls="mx-p-sub"), cls="mx-p-top mx-tv-top")
    if sq is None or not sq.ok:
        note = "Searching this square…" if sq is None else tm.SAID[sq.status]
        return Div(mx._arts(lane, "mx-b-art"), Div(head, P(note, cls="mx-p-note", role="status")), cls="mx-tv is-quiet", data_open=tm.key(lane.key, w.key))
    vs = mx.vs_words(sq.cents - asked_sq.cents, s.place.name, lane.combo) if asked_sq is not None and asked_sq.ok and not lane.asked else ""
    age = mx.age_words(sq.fetched)
    multi = len(sq.stays) > 1
    flights = sq.flights if len(sq.flights) > 1 else (sq.flight,)
    tiles = []
    for i, st in enumerate(sq.stays):
        alts = sq.stay_alts[i] if i < len(sq.stay_alts) and len(sq.stay_alts[i]) > 1 else (st,)
        tiles.append(_tile("stay", f"Stay · {st.place}" if multi else "Stay", "bed", [_stay_opt(x, j, lane.places[i], multi) for j, x in enumerate(alts)], _flip("hotel", len(alts)),
                           cls="mx-tile-hotel"))
    flight_tile = _tile("flight", "Flights", "plane", [_flight_opt(f, j) for j, f in enumerate(flights)], _flip("flight", len(flights)))
    first = lane.places[0]
    days = weather_for(first.name, w.depart, w.return_)
    sky = sky_strip(first.name, days)
    drive = P(icon("car", 16, 2.2), f"Airport drive: {sq.drive} min from {first.iata} to {first.name}" if sq.drive else f"Airport drive: from {first.iata}, no drive time yet", cls="mx-drive")
    hidden = [Input(type="hidden", name=n, value=str(v)) for n, v in mx.params(s, lane=lane.key, w=w.key).items()]
    picks = [Input(type="hidden", name="fl", value="0", data_pick="fl"), Input(type="hidden", name="st", value=",".join("0" for _ in sq.stays), data_pick="st")]
    words = mx.BOOK_SAMPLE if sq.sample else mx.BOOK_WORDS
    book = (Form(*hidden, *picks, Button(icon("check", 20, 2.8), Span("Book this trip"), type="submit", cls="mx-book"), method="post", action=mx.BOOK, cls="mx-book-f") if can_save else "")
    save = (Form(*hidden, *picks, Button(icon("plus", 16, 2.4), "Save to trip", type="submit", cls="btn btn-card mx-save"), method="post", action=mx.SAVE, cls="mx-save-f") if can_save else "")
    buy = Div(Div(Span("Total for the trip", cls="mx-c-k"), Span(tm.dollars(sq.cents), cls="mx-p-n", data_slot="total"), Span(vs, cls="mx-vs" + ("" if vs else " is-empty"), data_vs="1"), cls="mx-c-tot"),
              _cost(sq, lane),
              P(Span(f"Preview · {age}" if age else "Preview", cls="mx-preview"), cls="mx-p-meta mx-c-meta"),
              P(saved, cls="mx-saved", role="status") if saved else save,
              P(Span(words, cls="mx-soon-h"), " Books the stay" + ("s" if multi else "") + " here; the flight books on its airline’s site.", cls="mx-soon"), cls="mx-buy-in")
    acts = Div(Div(Span("Total", cls="mx-c-k"), Span(tm.dollars(sq.cents), cls="mx-bar-n", data_mirror="total"), cls="mx-bar-tot"), book, cls="mx-buy-acts")
    return Div(Div(head, cls="mx-tv-h"),
               Div(sky, _gantt_el(lane, w, sq, s), cls="mx-line mx-p-sky"),
               Div(Div(*tiles, cls="mx-stays"), flight_tile, drive, cls="mx-tiles"),
               Div(buy, acts, cls="mx-buy"),
               cls="mx-tv", data_open=sq.key, data_nights=str(w.nights))
