"""The opened square as the prototype's drawer (F-251, D-620..; F-258, D-670..): the stay first and alone, the flights a summary card that opens in place when tapped (the stay then folds to
its own summary card), never side by side and never a change the person did not make; under the matrix, a hotel gallery, the rooms to choose from, other stays, other flights, the total and "Book my trip". Reference: docs/design/booking-v2/index.html (`drawDrawer`).

    drawer(s, lane, w, sq, asked_sq, saved, can_save)    the drawer's inside as an element: for the tile endpoint (assets/js/tripmatrix.js puts it under the card and grows it out of the
                                                          square's column), and for the square's own page (a page without the script, the same words)

Everything the source gave is drawn as an option and only the shown one is visible without the script: the hotels (`sq.stay_alts`), each hotel's rooms (`StayPart.rooms`) and the flights
(`sq.flights`). assets/js/v2drawer.js switches between them in place, moves the total by exactly the difference and keeps the forms' three fields (`fl`, `st`, `rm`: the chosen flight,
hotel and room as indexes) in step, so Book and Save send the choice, never a price: the server reads the indexes again (`tripmatrix.pick`) and prices the trip itself, and a held room is
bound to its choice (pages/matrixbook.py). Nothing is invented: the gallery is the hotel's own photo where the source gave one, else the place's drawing labelled as an illustration; a
sample square's rooms are made-up and the square says Sample prices; the weather is weather_for's (typical days say so).
"""

import re
from datetime import date
from urllib.parse import quote

from fasthtml.common import A, Button, Div, Form, H2, H3, Img, Input, P, Section, Small, Span, Sup

from gitaway import catalog, matrixbook as mb, reviewtrend, tripmatrix as tm, weather
from gitaway.icons import icon
from gitaway.pages.skystrip import weather_for

LEG = re.compile(r"^(?:(?P<day>[A-Z][a-z]{2}, [A-Z][a-z]{2} \d+) · )?(?P<o>[A-Z]{3}) (?P<dt>\d{1,2}:\d{2} [AP]M) → (?P<d>[A-Z]{3}) (?P<at>\d{1,2}:\d{2} [AP]M)(?P<next> next day)?(?: · (?P<stops>.+))?$")
ILLUSTRATION = "Illustration, not the hotel’s photo"
PHOTO = "The hotel’s own photo"


def stops_words(n: int) -> str:
    return "Nonstop" if not n else f"{n} stop" + ("" if n == 1 else "s")


def times(leg: str) -> str:
    """"SFO 8:05 AM → SAN 9:32 AM" out of a leg's words ("Sat, Dec 12 · SFO 8:05 AM → SAN 9:32 AM · Nonstop"), or the words as they are."""
    m = LEG.match(leg or "")
    return f"{m['o']} {m['dt']} → {m['d']} {m['at']}{m['next'] or ''}" if m else (leg or "")


def signed(cents: int) -> str:
    return "same" if cents == 0 else ("+" if cents > 0 else "−") + tm.dollars(abs(cents))


def rooms_of(st: tm.StayPart) -> tuple:
    """The hotel's rooms: what the source gave, else its one room."""
    return st.rooms or (tm.RoomPart(st.room, st.board, st.refundable, st.due_at_stay_cents, st.cents, st.offer_id),)


def party_long(s) -> str:
    kids = len(s.kid_ages)
    return f"{s.adults} adult{'' if s.adults == 1 else 's'}" + (f", {kids} kid{'' if kids == 1 else 's'}" if kids else "")


def _day(d: date) -> str:
    return f"{d:%a}, {d:%b} {d.day}"


def _alts(sq: tm.Square) -> tuple:
    return sq.stay_alts or tuple((st,) for st in sq.stays)


def _stay_media(st: tm.StayPart, place, sample=False):
    """The gallery's slides for a hotel: its own photo when the source gave one, then the place's drawing, each labelled for what it is. A sample hotel (the showcase) has none of its own:
    generic hotel pictures, each captioned a sample (F-275, assets/photos/CREDITS.md)."""
    from gitaway.pages import hotelview, tripmatrix as mx
    slides = []
    if sample:
        slides = [Div(Img(src=url, alt=cap, loading="lazy"), Span(cap, cls="dr-cap"), cls="dr-slide") for url, cap in hotelview.sample_slides()]
    if st.photo:
        slides.append(Div(Img(src=st.photo, alt=f"{st.name}, the hotel’s own photo", loading="lazy", referrerpolicy="no-referrer"), Span(PHOTO, cls="dr-cap"), cls="dr-slide"))
    slides.append(Div(mx._art(place, "dr-art"), Span(ILLUSTRATION, cls="dr-cap"), cls="dr-slide"))
    return slides


def _gallery(slides):
    many = len(slides) > 1
    return Div(Div(*slides, cls="dr-track", data_gal="1"),
               Button(icon("chev-left", 18, 2.4), type="button", cls="dr-nav l", data_gal_go="-1", aria_label="Previous picture") if many else "",
               Button(icon("chev-right", 18, 2.4), type="button", cls="dr-nav r", data_gal_go="1", aria_label="Next picture") if many else "",
               Div(*[Span(cls="on" if i == 0 else "") for i in range(len(slides))], cls="dr-dots") if many else "", cls="dr-gal")


def _sample_card(place_name):      # F-284: a sample hotel has no place on a map; its card opens a recorded real hotel, labelled a sample (gitaway/pages/aerialview.py)
    from gitaway.pages import aerialview
    return aerialview.sample_card(place_name)


def _hotel(sq, st: tm.StayPart, place, i: int, j: int, on: bool):
    """One hotel of a stay: the gallery, its name, rating and address, what the source says about it (breakfast, refundable, the drive from the airport)."""
    feats = []
    if st.board == "breakfast":
        feats.append(Span(icon("food", 15, 2), "Breakfast included", cls="dr-feat is-food"))
    if st.refundable:
        feats.append(Span(icon("check", 15, 2.4), "Refundable", cls="dr-feat"))
    if sq.drive and i == 0:      # the drive is from the first airport to the first stay's town
        feats.append(Span(icon("plane", 15, 2), f"{sq.drive} min from the airport", cls="dr-feat"))
    meta = [Span(icon("star", 15, 2), st.rating.split(" · ")[0], cls="dr-star") if st.rating else "", Span(st.rating.split(" · ", 1)[1]) if " · " in st.rating else "",
            Span("· " + st.address) if st.address else ""]
    return Div(_gallery(_stay_media(st, place, sq.sample)), H3(st.name, cls="dr-hname"), P(*[m for m in meta if m != ""], cls="dr-hmeta") if st.rating or st.address else "",
               Div(*feats, cls="dr-feats") if feats else "", _sample_card(place.name) if sq.sample else "", cls="dr-hotel", data_hotel_i=str(j), data_name=st.name, hidden=not on)


def _room_btn(r: tm.RoomPart, k: int, chosen: tm.RoomPart, on: bool):
    words = [("Breakfast included" if r.board == "breakfast" else r.board.capitalize()), "Refundable" if r.refundable else "Non-refundable"]
    due = f"{catalog.money(r.due_at_stay_cents)} of it paid at the hotel" if r.due_at_stay_cents else ""
    diff = r.cents - chosen.cents
    return Button(Span(cls="dr-rad"), Span(Span(r.room, cls="dr-t"), Small(" · ".join(w for w in words if w) + (f" · {due}" if due else "")), cls="dr-tx"),
                  Span("Chosen" if on else signed(diff), cls="dr-d num" + (" is-minus" if diff < 0 and not on else ""), data_d="1"), type="button", cls="dr-opt", role="radio", aria_checked="true" if on else "false",
                  data_room=str(k), data_c=str(r.cents), data_roomname=r.room)


def _alt_btn(sq, st: tm.StayPart, place, j: int, on: bool, base: int):
    from gitaway.pages import tripmatrix as mx
    thumb = Img(src=st.photo, alt="", loading="lazy", referrerpolicy="no-referrer") if st.photo else mx._art(place, "dr-art")
    rate = st.rating.split(" · ")[0] if st.rating else ""
    return Button(Span(thumb, cls="dr-thumb"), Span(st.name, cls="dr-an"),
                  Span(Span(f"★ {rate}" if rate else "", cls="dr-ar"), Span("Chosen" if on else signed(st.cents - base), cls="dr-d num", data_d="1"), cls="dr-as"),
                  type="button", cls="dr-alt", role="radio", aria_checked="true" if on else "false", data_hotel=str(j), data_c=str(st.cents), data_name=st.name)


def _stay_pane(sq, i: int, place, alts: tuple, active: bool, party: int, ptype: str = ""):
    shown = alts[0]
    hotels = [_hotel(sq, st, place, i, j, j == 0) for j, st in enumerate(alts)]
    room_lists = [Div(*[_room_btn(r, k, rooms_of(st)[0], k == 0) for k, r in enumerate(rooms_of(st))], cls="dr-rooms", role="radiogroup", aria_label=f"Rooms at {st.name}", data_for=str(j), hidden=j != 0)
                  for j, st in enumerate(alts)]
    nights = shown.nights
    sub = Div(f"Rooms for {party} · {nights} night{'s' if nights != 1 else ''}", cls="dr-sub")
    from gitaway.pages import hotelview
    slots = [Div(P(icon("image", 16, 2), "Loading the hotel’s photos and reviews…", cls="dr-fine"), cls="dr-rich", data_state="idle", data_for=str(j), data_hid=hotelview.token(st.hotel_id), data_pt=ptype, hidden=j != 0,
                 role="region", aria_label=f"About {st.name}") for j, st in enumerate(alts) if st.hotel_id and not sq.sample]
    return Div(Div(*hotels, cls="dr-hl"),
               Div(sub, *room_lists,
                   Div(f"Other stays in {place.name}", cls="dr-sub") if len(alts) > 1 else "",
                   Div(*[_alt_btn(sq, st, place, j, j == 0, shown.cents) for j, st in enumerate(alts)], cls="dr-alts", role="radiogroup", aria_label="Other stays") if len(alts) > 1 else "", cls="dr-hr"), *slots,
               cls="dr-stay-grid dr-sp", data_stay_i=str(i), hidden=not active)


def _leg(label: str, day: str, words: str, airline: str, fallback=""):
    m = LEG.match(words or "")
    if not m:
        return Div(Span(f"{label} · {day}" if day else label, cls="dr-lbl"), Span(words, cls="dr-car"), cls="dr-leg")
    stops = m["stops"] or ""
    return Div(Span(f"{label} · {m['day'] or day}", cls="dr-lbl"), Span(m["dt"], Small(m["o"]), cls="dr-tm num"),
               Span(Span(cls="dr-dot"), Span(cls="dr-rule"), icon("plane", 18, 2), Span(stops or "Nonstop", cls="dr-stops"), cls="dr-ln"),
               Span(m["at"], Sup("+1", cls="dr-p1", title="Arrives the next day", aria_label="plus one day") if m["next"] else "", Small(m["d"]), cls="dr-tm r num"), Span(airline, cls="dr-car"), cls="dr-leg")


def _flight_view(f: tm.FlightPart, k: int, o: tm.Window, on: bool):
    out = _leg("Out", _day(o.depart), f.out, f.airline)
    back = _leg("Back", _day(o.return_), f.back, f.airline) if f.back else ""
    more = P("The cheapest flight found; more fares were still coming in.", cls="dr-fine") if not f.complete else ""
    return Div(out, back, more, cls="dr-flt", data_flt_i=str(k), hidden=not on)


def _plus(words: str) -> str:
    """The way flights say a next-day landing in a line of words: "9:32 AM +1" (the leg's own rows draw it as a small raised +1)."""
    return words.replace(" next day", " +1")


def _clock(words: str, first=True) -> str:
    """"SFO 8:05 AM → SAN 9:32 AM": the clock of its first (or last) airport, "8:05 AM"."""
    parts = words.split(" → ")
    return parts[0 if first else -1].split(" ", 1)[-1] if len(parts) == 2 else ""


def _flight_btn(f: tm.FlightPart, k: int, base: int, on: bool):
    out, back = times(f.out), times(f.back)
    head = _plus(f"{_clock(out)} → {_clock(out, False)}") if " → " in out else out
    tail = _plus(f"back {_clock(back)} · ") if " → " in back else ""
    return Button(Span(cls="dr-rad"), Span(Span(head, cls="dr-t num"), Small(f"{tail}{f.airline} · {stops_words(f.stops).lower()}"), cls="dr-tx"),
                  Span("Chosen" if on else signed(f.cents - base), cls="dr-d num" + (" is-minus" if f.cents < base and not on else ""), data_d="1"), type="button", cls="dr-opt", role="radio",
                  aria_checked="true" if on else "false", data_fl=str(k), data_c=str(f.cents), data_al=f.airline, data_stops=stops_words(f.stops).lower(),
                  data_times=_plus(f"{_clock(out)} out" + (f" · {_clock(back)} back" if " → " in back else "")))


ADJ = {"sun": "sunny", "cloud": "cloudy", "rain": "rainy", "snow": "snowy", "wind": "windy"}


def sky_words(days) -> str:
    """What the trip's days are like, from weather.py's days only: "3 of 4 days typically sunny" when any day is sunny, else what most days are ("Typically snowy · 40°", the average high).
    Never a zero count (live check: "0 of 4 days typically sunny" for a snowy January)."""
    typical = any(d.kind != weather.FORECAST for d in days)
    sunny = sum(1 for d in days if d.condition == "sun")
    if sunny:
        return f"{sunny} of {len(days)} days {'typically ' if typical else ''}sunny"
    kinds = [d.condition for d in days if d.condition in ADJ]
    word = ADJ[max(dict.fromkeys(kinds), key=kinds.count)] if kinds else "mixed"
    high = round(sum(d.high_f for d in days) / len(days))
    return f"{'Typically ' + word if typical else word.capitalize()} · {high}°"


def _why(s, lane, w, sq, asked_sq):
    """One line on why this trip: the sky for its nights, where its total stands against the budget and against the asked place. Each part only where it is known."""
    from gitaway.pages import tripmatrix as mx
    bits = []
    days = [d for p, a, b in tm.stays_for(lane, w) for d in weather_for(p.name, a, b).days if d]
    if days:
        bits.append(Span(sky_words(days)))
    if s.budget_cents:
        gap = s.budget_cents - sq.cents
        bits.append(Span(f"{tm.dollars(abs(gap))} {'under' if gap >= 0 else 'over'} your {tm.dollars(s.budget_cents)}", data_budget=str(s.budget_cents // 100)))
    vs = mx.vs_words(sq.cents - asked_sq.cents, s.place.name, lane.combo) if asked_sq is not None and asked_sq.ok and not lane.asked else ""
    joined = [bits[0]] if bits else []
    for b in bits[1:]:
        joined += [" · ", b]
    # the shown trip's own "+$145 vs San Diego alone": drawn here when the asked place's square is known, else the matrix's script fills it from what it knows (assets/js/tripmatrix.js `vs`)
    joined.append(Span(("" if not bits else " · ") + vs if vs else "", data_vs="1", data_sep="1" if bits else ""))
    return Span(icon("spark", 15, 2.2), Span("Our pick: ", data_pickword="1", hidden=True), *joined, cls="dr-why")


def _mini_stay(names, room, price):
    return Div(Span("Stay", cls="dr-k"), Span(names, cls="dr-mn", data_m="stay-name"), P(room, data_m="stay-room"), Span(price, cls="dr-pp num", data_m="stay-price"),
               Span(icon("expand", 16, 2.2), "Show stay", cls="dr-exp"), cls="dr-mini", data_show="stay", role="button", tabindex="0", aria_label="Show the stay")


def _foot_words(sq):
    return mb.words(sq.sample) + "."


def drawer(s, lane, w, sq, asked_sq=None, saved="", can_save=True):
    """The drawer's inside. A square still searching, or one with a problem, is its head and one sentence (no total, no buttons)."""
    from gitaway.pages import tripmatrix as mx
    sub = f"{_day(w.depart)} → {_day(w.return_)} · {w.nights} nights · {party_long(s)}"
    close = Button(icon("x", 18, 2.4), type="button", cls="dr-x", data_act="close", aria_label="Close")
    head_art = mx._arts(lane, "dr-hart")
    if sq is None or not sq.ok:
        note = "Searching this square…" if sq is None else tm.SAID[sq.status]
        way = A("Sign in to keep comparing", href="/signin?next=" + quote(mx.href(s), safe=""), cls="btn") if sq is not None and sq.status == tm.LIMIT else ""      # F-265: the way on
        return Div(Div(head_art, Div(H2(lane.name, cls="dr-h"), P(sub), cls="dr-ti"), close, cls="dr-head"), Div(P(note, cls="dr-note", role="status"), way, cls="dr-quiet"),
                   cls="dr is-quiet", data_open=tm.key(lane.key, w.key))
    alts_by_stay = _alts(sq)
    multi = len(sq.stays) > 1
    stay_panes = [_stay_pane(sq, i, lane.places[min(i, len(lane.places) - 1)], alts, i == 0, s.travelers, reviewtrend.party_type(s.adults, s.kid_ages)) for i, alts in enumerate(alts_by_stay)]
    tabs = Div(*[Button(f"{lane.places[min(i, len(lane.places) - 1)].name} · {alts[0].nights} night{'s' if alts[0].nights != 1 else ''}", type="button", aria_pressed="true" if i == 0 else "false", data_tab=str(i))
                 for i, alts in enumerate(alts_by_stay)], cls="dr-seg") if multi else ""
    flights = sq.flights if len(sq.flights) > 1 else (sq.flight,)
    stay_h = Div(Span(icon("bed", 17, 2.2), cls="dr-ic k-stay"), H3("Stays" if multi else "Stay"), cls="dr-pn-h")
    fly_h = Div(Span(icon("plane", 17, 2.2), cls="dr-ic k-flight"), H3("Flights"), cls="dr-pn-h")
    names = " + ".join(st.name for st in sq.stays)
    stay = Section(Div(stay_h, tabs, *stay_panes, cls="dr-full"), _mini_stay(names, sq.stays[0].room, catalog.money(sum(st.cents for st in sq.stays))), cls="dr-pn dr-stay", data_pane="stay", aria_label="Stay")
    fly = Section(Div(fly_h, *[_flight_view(f, k, w, k == 0) for k, f in enumerate(flights)],
                      Div(f"Other flights · {s.travelers} seats", cls="dr-sub"),
                      Div(*[_flight_btn(f, k, flights[0].cents, k == 0) for k, f in enumerate(flights)], cls="dr-rooms", role="radiogroup", aria_label="Other flights"), cls="dr-full"),
                  Div(Span("Flights", cls="dr-k"), Span(f"{s.home} ⇄ {lane.places[0].iata}", cls="dr-route num"), Span(_flight_times(flights[0]), cls="dr-mn num", data_m="fly-times"),
                      P(f"{flights[0].airline} · {stops_words(flights[0].stops).lower()}", data_m="fly-al"), Span(catalog.money(flights[0].cents), cls="dr-pp num", data_m="fly-price"),
                      Span(icon("expand", 16, 2.2), "Show flights", cls="dr-exp"), cls="dr-mini", data_show="fly", role="button", tabindex="0", aria_label="Show the flights"),
                  cls="dr-pn dr-fly is-mini", data_pane="fly", aria_label="Flights")
    hidden = [Input(type="hidden", name=n, value=str(v)) for n, v in mx.params(s, lane=lane.key, w=w.key).items()]
    picks = [Input(type="hidden", name="fl", value="0", data_pick="fl"), Input(type="hidden", name="st", value=",".join("0" for _ in sq.stays), data_pick="st"),
             Input(type="hidden", name="rm", value=",".join("0" for _ in sq.stays), data_pick="rm")]
    total = tm.dollars(sq.cents)
    soon = mb.mode() == mb.SOON and not sq.sample      # F-267: a live key in production: Book waits, and Save this trip leads
    book = ("" if not can_save else Button(mb.SOON_WORDS, type="button", disabled=True, cls="dr-book-soon") if soon else
            Form(*hidden, *picks, Button(Span("Book my trip"), Span(total, cls="num", data_mirror="total"), Span(cls="dr-spin"), type="submit", cls="dr-book"), method="post", action=mx.BOOK, cls="mx-book-f dr-book-f"))
    save = ("" if not can_save else P(saved, cls="mx-saved", role="status") if saved else
            Form(*hidden, *picks, Button(icon("plus", 16, 2.4), "Save this trip" if soon else "Save to trip", type="submit", cls="dr-save" + (" is-lead" if soon else "")), method="post", action=mx.SAVE, cls="mx-save-f"))
    why = _why(s, lane, w, sq, asked_sq)
    foot = Div(Span(Span(_foot_words(sq), cls="dr-soon-h"), " Save the trip, then plan it day by day." if soon else f" The stay{'s' if multi else ''} book{'' if multi else 's'} here; the flight books on its airline’s site.", cls="dr-fnote"), save, book, cls="dr-foot")
    head = Div(head_art, Div(H2(lane.name, cls="dr-h"), P(sub), why, cls="dr-ti"),
               Div(Span(total, cls="dr-n num", data_slot="total"), Span(f"total for {s.travelers} · flights + stays", cls="dr-tl"), cls="dr-tot"), close, cls="dr-head")
    out = Div(head, Div(stay, fly, cls="dr-panels", data_open="stay"), foot, cls="dr", data_open=sq.key, data_nights=str(w.nights), data_party=str(s.travelers))
    return out


def _flight_times(f: tm.FlightPart) -> str:
    out, back = times(f.out), times(f.back)
    return _plus(f"{_clock(out)} out" + (f" · {_clock(back)} back" if " → " in back else "") if " → " in out else out)
