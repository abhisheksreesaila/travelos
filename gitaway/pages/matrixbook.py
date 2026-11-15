"""Booking a trip matrix square (F-233, D-480 to D-489; the checkout redone in F-242, D-570 to D-579): the sheet the square grows into, and its two steps.

POST /plan/matrix/book           step 1: the stays' offers are prebooked (the rooms checked, their final price read); the answer is the checkout: three folding cards (guest,
                                 payment, confirm) and "Sandbox booking: nothing is charged". A fragment for assets/js/matrixbook.js (header `X-Matrix: 1`), else a page.
POST /plan/matrix/book/confirm   step 2: the lead guest is checked, the square becomes the family's trip (the same path as Save to trip), each stay is booked once through
                                 LiteAPI's sandbox, the stay is added to the trip, and the answer is the stamped pass with LiteAPI's booking id. The script plays the progress
                                 (holding the room, paying with the test card, booking, putting the trip together) while this call runs, then throws the confetti.

Both take `fl` and `st`, the flight and stays chosen on the square (indexes into the square's alternatives; gitaway/tripmatrix.py `pick`): the server prices the chosen trip
itself, and a held room is bound to its choice. Both are plain `def` handlers (a prebook or book can wait on the network) and writes, so the access beforeware gives them to editors
only: a viewer is refused (403) before anything is asked of LiteAPI. Flights are not booked here: the pass links to the flight lane's partner like any other search. The words,
prices and the guest's name and email come out through FastHTML's escaping; the guest's email is never logged and never put in a URL.
"""

from datetime import date

from fasthtml.common import A, Button, Div, Form, H2, H3, Input, Label, P, Section, Span, to_xml
from starlette.responses import RedirectResponse, Response

from gitaway import catalog, importer, liteapi, matrixbook as mb, session as ses, showcase, tripmatrix as tm, tripstart
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import plan_search, tripmatrix as mx, tripview
from gitaway.partners import registry

CONFIRM = mx.BOOK + "/confirm"
SIGNIN = "Sign in to book."
STALE = "That room check has expired or is not for this square. Close this and press Book this trip on the square again."
SLOW_DOWN = "That is a lot of booking tries. Wait a minute, or try again tomorrow."
MADE_UP = ("Test", "Traveler", "test.traveler@example.com")      # the sandbox form starts with a made-up guest (D-510)
CARDS = (("guest", "Who’s the lead guest?"), ("pay", "How will you pay?"), ("review", "Look it over and book"))
# What the progress says while a booking runs (D-573): the room was really held when this sheet opened; the payment is the sandbox's test card (staged, no money moves);
# the booking and the trip are the real calls. The script plays them one after another and waits for the real answer before the last one is ticked.
STAGES = {"sandbox": ("Holding your room", "Paying with the test card", "Booking your stay with LiteAPI", "Putting the trip together"),
          "sample": ("Holding your room", "Paying with the sample card", "Confirming your sample stay", "Putting the trip together")}
CONFETTI = 28


def _head(s, lane, w, sample: bool, booked: bool = False):
    return Div(mx._arts(lane, "mxb-art"), Div(H2(f"Book {lane.name}", cls="mxb-h"), P(f"{tm.when(w)} · {w.nights} nights · {mx.party_words(s)}", cls="mxb-sub"), cls="mxb-top"),
               P(icon("shield", 16, 2.4), mb.SAMPLE_WORDS if sample else mb.NOTHING_CHARGED, cls="mxb-sandbox" + (" is-booked" if booked else ""), role="status" if booked else "note"), cls="mxb-head")


def _stay_row(row: mb.Row):
    pre, part = row.prebook, row.part
    nights = (pre.checkout - pre.checkin).days
    words = [pre.room or part.room, f"{nights} night{'s' if nights != 1 else ''}", f"{pre.checkin:%b} {pre.checkin.day} to {pre.checkout:%b} {pre.checkout.day}",
             "Refundable" if pre.refundable else "Non-refundable"]
    return Div(Span(icon("bed", 16, 2.2), cls="mx-kt k-stay"),
               Div(P(part.name, cls="mx-r-h"), P(f"{row.place} · " + " · ".join(w for w in words if w), cls="mx-r-s"),
                   P(f"{catalog.money(pre.due_at_stay_cents)} of it is paid at the hotel", cls="mx-r-s mx-r-due") if pre.due_at_stay_cents else ""),
               Span(catalog.money(row.total_cents), cls="mx-r-n"), cls="mx-row mxb-row")


def _flight_row(sq):
    f = sq.flight
    return Div(Span(icon("plane", 16, 2.2), cls="mx-kt k-flight"),
               Div(P(f.airline, cls="mx-r-h"), P(tripview.times(f.out), cls="mx-r-s"), P(tripview.times(f.back), cls="mx-r-s") if f.back else "",
                   P("You book this on the airline’s site, after this.", cls="mx-r-s")),
               Span(catalog.money(f.cents), cls="mx-r-n"), cls="mx-row mxb-row")


def _moved(prep: mb.Prep):
    if not prep.changed:
        return ""
    was = sum(r.part.cents for r in prep.rows)
    words = (f"The price moved: it was {catalog.money(was)} on the square and is {catalog.money(prep.total_cents)} now."
             if was != prep.total_cents else "The room’s terms changed since the square. Read them below, then book.")
    return P(icon("bell", 16, 2.4), words, cls="mxb-note is-warn", role="status")


def _field(name, label, value, error, **attrs):
    return Div(Label(label, fr=f"mxb-{name}", cls="mxb-l"), Input(id=f"mxb-{name}", name=name, value=value, required=True, aria_invalid="true" if error else None,
                                                                  aria_describedby=f"mxb-{name}-e" if error else None, **attrs),
               P(error, id=f"mxb-{name}-e", cls="mxb-err", role="alert") if error else "", cls="mxb-field" + (" has-err" if error else ""))


def pick_fields(pk: tuple) -> dict:
    """The choice a form carries to the next route: {"fl": "1", "st": "0,2"}, the shown part being index 0."""
    return {"fl": str(pk[0]), "st": ",".join(str(i or 0) for i in pk[1])}


def _hidden(s, lane, w, pk=(0, ()), **more):
    return [Input(type="hidden", name=n, value=str(v)) for n, v in {**mx.params(s, lane=lane.key, w=w.key), **pick_fields(pk), **more}.items()]


def _card(key, n, title, *inside, summary=""):
    """One folding card: a numbered head (a tick once done, its answer in a line, an Edit) and the body that opens when it is the active one. The script sets `data-state`
    (done, active, todo) and folds; without it every card is open."""
    return Section(Div(Span(str(n), cls="mxb-n", data_n=str(n)), Div(H3(title, cls="mxb-q"), P(summary, cls="mxb-sumline", data_sum=key)),
                       Button("Edit", type="button", cls="mxb-edit", data_edit=key, aria_label=f"Change: {title}"), cls="mxb-card-h"),
                   Div(*inside, cls="mxb-card-b"), cls="mxb-card", data_card=key, data_state="active" if key == "guest" else "todo")


def _checkout(s, lane, w, sq, prep, pk, values=None, errors=None):
    """The checkout (folding cards, D-572): guest, payment, confirm, one form. With the script the cards fold one into the next; without it all three are open and the one
    button books. The guest starts as a made-up one (sandbox); LiteAPI's test card pays, so no card number is asked or kept."""
    values, errors = values or dict(zip(("first", "last", "email"), MADE_UP)), errors or {}
    sample = prep.sample
    guest = (P("A made-up guest is filled in: this is the sandbox, so there is no need to type a real name or email. LiteAPI’s test system gets it and GitAway keeps nothing of it.", cls="mxb-hint"),
             Div(_field("first", "First name", values.get("first", ""), errors.get("first"), autocomplete="given-name", maxlength=mb.NAME_MAX),
                 _field("last", "Last name", values.get("last", ""), errors.get("last"), autocomplete="family-name", maxlength=mb.NAME_MAX), cls="mxb-two"),
             _field("email", "Email", values.get("email", ""), errors.get("email"), type="email", autocomplete="email", maxlength=mb.EMAIL_MAX, inputmode="email"),
             Button(Span("Continue"), icon("arrow-right", 18, 2.4), type="button", cls="btn btn-ink mxb-next", data_next="pay"))
    card_words = "Sample card · nothing is charged" if sample else "•••• 4242 · nothing is charged"
    pay = (Div(Span(icon("lock", 18, 2.4), cls="mx-kt k-flight"), Div(P("Sample card" if sample else "LiteAPI test card", cls="mx-r-h"), P(card_words, cls="mx-r-s")), cls="mxb-test"),
           P("This is a sample booking. No card is used and no money moves." if sample else "The sandbox pays with its own test card. Nothing to type, nothing kept, and no money moves.", cls="mxb-hint"),
           Button(Span("Continue"), icon("arrow-right", 18, 2.4), type="button", cls="btn btn-ink mxb-next", data_next="review"))
    stays = prep.total_cents
    review = (Div(_flight_row(sq), *[_stay_row(r) for r in prep.rows], cls="mx-rows"), _moved(prep),
              P(Span("Total for the trip", cls="mxb-tl"), Span(catalog.money(sq.flight.cents + stays), cls="mx-r-n mxb-total"), cls="mxb-sum"),
              P(f"This booking covers the stay{'s' if len(prep.rows) > 1 else ''}: {catalog.money(stays)}. The flight is booked on its airline’s site.", cls="mxb-fine"),
              Button(icon("check", 20, 2.8), Span(f"Book this trip · {catalog.money(stays)}"), type="submit", cls="mxb-go"),
              P(mb.SAMPLE_WORDS if sample else mb.NOTHING_CHARGED + ". LiteAPI’s test card pays; no email is sent.", cls="mxb-fine"))
    cards = [_card("guest", 1, CARDS[0][1], *guest, summary=" ".join(x for x in (values.get("first", ""), values.get("last", "")) if x)),
             _card("pay", 2, CARDS[1][1], *pay, summary="Sample card, nothing charged" if sample else "LiteAPI test card, nothing charged"),
             _card("review", 3, CARDS[2][1], *review)]
    return Form(*_hidden(s, lane, w, pk, token=prep.token), *cards, method="post", action=CONFIRM, cls="mxb-f", data_step="guest", data_stages="|".join(STAGES["sample" if sample else "sandbox"]))


def _flight_link(s, lane, w):
    search, _ = tripstart.read({"place": lane.places[0].name, "d": w.depart.isoformat(), "r": w.return_.isoformat(), "a": str(s.adults), "k": ",".join(map(str, s.kid_ages)),
                                "home": s.home})
    found = registry.lane("flight", search) if search else []
    return (found[0].name, plan_search._href(found[0], plan_search.query(search))) if found else None


def _day(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{day:%b} {day.day}"


def _confetti():
    """Paper thrown once when the pass appears (CSS only, assets/css/matrixbook.css; none under reduced motion). The colours are the kinds'."""
    return Div(*[Span(cls=f"mxb-cf c{i % 6}", style=f"--i:{i}; --x:{(i * 37) % 100}; --r:{(i * 53) % 360}; --d:{(i * 7) % 11}") for i in range(CONFETTI)], cls="mxb-confetti", aria_hidden="true")


def _pass_stay(d: mb.Done, address: str):
    return Div(P("Stay", cls="mxb-k"), P(d.hotel, cls="mxb-pass-h"), P(f"{d.place} · {_day(d.checkin)} to {_day(d.checkout)}" + (f" · {d.room}" if d.room else ""), cls="mx-r-s"),
               P(icon("pin", 14, 2.2), address, cls="mx-r-s mxb-addr") if address else "", cls="mxb-pass-row")


def _confirmation(s, lane, w, sq, prep: mb.Prep, res: mb.Result, who: str):
    """The stamped boarding pass (D-574): where, the flight, each stay with what the answer gives (the booking id, the hotel's confirmation code and its address), the test
    card, and a bold Plan this trip. Only what LiteAPI (or the sample) gave: no phone number or record locator is made up."""
    flight = _flight_link(s, lane, w)
    sample = any(d.sample for d in res.done)
    address = {r.part.name: r.part.address for r in prep.rows}
    end = lane.places[0]
    route = Div(Span(s.home or "Home", cls="mxb-iata"), Span(cls="mxb-dash"), Span(icon("plane", 22, 2.2), cls="mxb-plane"), Span(cls="mxb-dash"), Span(end.iata or end.name, cls="mxb-iata"), cls="mxb-route")
    top = Div(mx._arts(lane, "mxb-pass-art"), route, Span("Sample" if sample else "Booked", cls="mxb-stamp"), P(f"{tm.when(w)} · {mx.party_words(s)}", cls="mxb-pass-when"), cls="mxb-pass-top")
    mid = Div(Div(P("Flight", cls="mxb-k"), P(f"{sq.flight.airline} · {tripview.stops_words(sq.flight.stops).lower()}", cls="mxb-pass-h"), P(tripview.times(sq.flight.out), cls="mx-r-s"),
                  P(tripview.times(sq.flight.back), cls="mx-r-s") if sq.flight.back else "", P("Booked on the airline’s site.", cls="mx-r-s"), cls="mxb-pass-row"),
              *[_pass_stay(d, address.get(d.hotel, "")) for d in res.done],
              Div(P("Lead guest", cls="mxb-k"), P(who, cls="mxb-pass-h"), P(icon("lock", 14, 2.2), "Paid with the " + ("sample" if sample else "LiteAPI test") + " card · nothing was charged", cls="mx-r-s"), cls="mxb-pass-row"),
              cls="mxb-pass-mid")
    stub = Div(*[Div(P("Booking id", cls="mxb-k"), P(Span(d.booking_id, cls="mxb-id", data_booking_id=d.booking_id), cls="mxb-code"),
                     *([P("Hotel confirmation", cls="mxb-k"), P(Span(d.confirmation, cls="mxb-id"), cls="mxb-code")] if d.confirmation else []), cls="mxb-stub-i") for d in res.done], cls="mxb-stub")
    return Div(_confetti(), Div(top, mid, stub, cls="mxb-pass"),
               H3("You’re going to " + lane.name + "!", cls="mxb-q mxb-going"),
               P(f"{who}, your {'sample ' if sample else ''}booking is confirmed.", cls="mxb-hint"),
               A(icon("arrow-right", 22, 2.8), Span("Plan this trip"), href="/trip/cockpit", cls="mxb-plan", data_trip="1"),
               A(f"Search flights on {flight[0]}", href=flight[1], cls="btn mxb-flight", rel="noopener") if flight else "",
               cls="mxb-confirm", data_step="booked")


def _problem(words: str):
    return Div(P(icon("bell", 18, 2.4), words, cls="mxb-note is-warn", role="alert"), A("Back to the square", href="#", cls="btn mxb-back", data_close="1"), cls="mxb-problem", data_step="problem")


def sheet(s, lane, w, *, sq=None, prep=None, pk=(0, ()), values=None, errors=None, note="", res=None, problem="", sample=False, who=""):
    """The checkout's inside (a fragment: assets/js/matrixbook.js puts it in the sheet and settles it): the head and one body, the folding cards or the pass."""
    if problem:
        body, at = _problem(problem), "room"
    elif res is not None and res.ok:
        body, at = _confirmation(s, lane, w, sq, prep, res, who), "booked"
    else:
        body, at = Div(P(icon("bell", 16, 2.4), note, cls="mxb-note", role="status") if note else "", _checkout(s, lane, w, sq, prep, pk, values, errors), cls="mxb-body", data_step="guest"), "guest"
    return Div(_head(s, lane, w, sample or (prep is not None and prep.sample) or (res is not None and any(d.sample for d in res.done)), booked=at == "booked"), body,
               cls="mxb", data_at=at, data_open=tm.key(lane.key, w.key))


def _answer(request, s, lane, w, inner, status=200):
    """The sheet as a fragment for the script, else as a page of its own (no script: the same words, the same two steps)."""
    if request.headers.get("x-matrix") == "1":
        return Response(to_xml(inner), media_type="text/html", status_code=status, headers={"Cache-Control": "no-store"})
    back = A(icon("chev-left", 18, 2.4), "Back to the matrix", href=mx.href(s, mx.SQUARE, lane=lane.key, w=w.key), cls="btn mx-back")
    return page(f"Book {lane.name}", Div(back, Div(inner, cls="mx-side mx-alone mxb-page"), cls="mx mx-one"), current="/plan/matrix", head=mx.HEAD, noindex=True)


def _family(session):
    return mx._family(session)


def _read(s, lane_key, w_key, family, pk):
    """(lane, window, square, choice): the square as it was shown (kept answers first), else asked again, with the flight and stays the person chose on it and that choice
    made to fit the square (a forged index is the shown part)."""
    lane, w, sq, _ = mx._square_of(s, lane_key, w_key, family, True)
    if lane is not None and sq is None:
        lane, w, sq, _ = mx._square_of(s, lane_key, w_key, family)
    if sq is None:
        return lane, w, sq, pk
    pk = tm.clamp(sq, pk)
    return lane, w, tm.pick(sq, *pk), pk


def _prepare(s, lane, w, sq, family):
    dates = [(p.name, a, b) for p, a, b in tm.stays_for(lane, w)]
    prep = mb.prepare(sq.stays, dates, family, sample=sq.sample)
    if prep.status == liteapi.GONE:
        liteapi.forget_stays()      # the kept rooms are stale: the matrix asks again
    return prep


def _square_of(s, lane, w, pk) -> tuple:
    """What a held room is bound to: the square's key, the address words it was asked with, and the flight and stays chosen on it."""
    return tm.key(lane.key, w.key), tuple(sorted((n, str(v)) for n, v in {**mx.params(s, lane=lane.key, w=w.key), **pick_fields(pk)}.items()))


def _first_step(request, session, s, lane, w, sq, pk, note=""):
    family = _family(session)
    if not sq.ok or not sq.stays:
        return _answer(request, s, lane, w, sheet(s, lane, w, problem=tm.SAID.get(sq.status, "That square has no stay to book."), sample=sq.sample))
    prep = _prepare(s, lane, w, sq, family)
    if not prep.ok:
        return _answer(request, s, lane, w, sheet(s, lane, w, problem=mb.SAID.get(prep.status, mb.SAID[liteapi.FAILED]), sample=sq.sample))
    mb.hold(family, prep, _square_of(s, lane, w, pk))
    return _answer(request, s, lane, w, sheet(s, lane, w, sq=sq, prep=prep, pk=pk, note=note))


def _slowed(request, s, lane_key, w_key):
    """Too many presses: the sheet says so (429) from the address alone, with no search and no call."""
    lane = tm.lane(s.place, lane_key, s.nearby)
    w = tm.window(s.depart, s.return_, s.flex, catalog.today(), w_key)
    if lane is None or w is None:
        return RedirectResponse(mx.href(s), status_code=303)
    return _answer(request, s, lane, w, sheet(s, lane, w, problem=SLOW_DOWN, sample=showcase.on()), 429)


def _signed_out(s, lane_key, w_key):
    return RedirectResponse(ses.signin_href(mx.href(s, mx.SQUARE, lane=lane_key, w=w_key)), status_code=303)


def register(app):
    @app.post(mx.BOOK)
    def book_room(request, session, lane: str = "", w: str = "", fl: str = "", st: str = "", to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "",
                  x: str = "", nb: str = "", b: str = ""):
        s = mx.state(to, home, d, r, a, k, x, nb, b)
        if s.problems:
            return RedirectResponse(mx.href(s), status_code=303)
        me = ses.current_traveler(session)
        if not me:
            return _signed_out(s, lane, w)
        if not mb.allow(me.id):      # before anything is read: a refused press starts no search
            return _slowed(request, s, lane, w)
        pk = tm.picks(fl, st)
        lane_, w_, sq, pk = _read(s, lane, w, _family(session), pk)
        if lane_ is None:
            return RedirectResponse(mx.href(s), status_code=303)
        return _first_step(request, session, s, lane_, w_, sq, pk)

    @app.post(CONFIRM)
    def book_confirm(request, session, lane: str = "", w: str = "", fl: str = "", st: str = "", token: str = "", first: str = "", last: str = "", email: str = "", to: str = "",
                     home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        s = mx.state(to, home, d, r, a, k, x, nb, b)
        if s.problems:
            return RedirectResponse(mx.href(s), status_code=303)
        me = ses.current_traveler(session)
        if not me:
            return _signed_out(s, lane, w)
        if not mb.allow(me.id):
            return _slowed(request, s, lane, w)
        family = _family(session)
        pk = tm.picks(fl, st)
        lane_, w_, sq, pk = _read(s, lane, w, family, pk)
        if lane_ is None:
            return RedirectResponse(mx.href(s), status_code=303)
        prep = mb.held(family, token, _square_of(s, lane_, w_, pk))
        if prep is None:      # restarted, kept too long, another family's or another square's (or another choice's) token: nothing is asked of LiteAPI
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, problem=STALE, sample=sq.sample))
        guest, errors = mb.clean_guest(first, last, email)
        if errors:
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, sq=sq, prep=prep, pk=pk, values={"first": first[:mb.NAME_MAX], "last": last[:mb.NAME_MAX], "email": email[:mb.EMAIL_MAX]},
                                                        errors=errors))
        try:
            trip_id = mx.save(session, s, lane_, w_, sq)      # the square becomes the family's trip, as Save to trip does
        except importer.SaveError as e:
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, problem=str(e), sample=prep.sample))
        with ses.family(session) as fam:
            if not fam:      # the family went away between the steps: sign in again, nothing was asked of LiteAPI
                return _answer(request, s, lane_, w_, sheet(s, lane_, w_, problem=SIGNIN, sample=prep.sample))
            res = mb.book(prep, guest, fam.db, family, trip_id, me.id)
        if res.done:
            mb.add_to_trip(session, trip_id, res.done)
        if res.ok:
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, sq=sq, prep=prep, pk=pk, res=res, who=f"{guest.first} {guest.last}"))
        said = mb.SAID.get(res.status, mb.SAID[liteapi.FAILED])
        left = f" {len(res.done)} of {len(prep.rows)} stays are booked; press Book again for the rest." if res.done else ""
        return _answer(request, s, lane_, w_, sheet(s, lane_, w_, sq=sq, prep=prep, pk=pk, values={"first": guest.first, "last": guest.last, "email": guest.email}, note=said + left))
