"""Booking a trip matrix square (F-233, D-480 to D-489): the sheet the square grows into, and its two steps.

POST /plan/matrix/book           step 1: the stays' offers are prebooked (the rooms checked, their final price read); the answer is the booking sheet: the rooms, one
                                 guest form, and "Sandbox booking: nothing is charged". A fragment for assets/js/matrixbook.js (header `X-Matrix: 1`), else a page.
POST /plan/matrix/book/confirm   step 2: the lead guest is checked, the square becomes the family's trip (the same path as Save to trip), each stay is booked once through
                                 LiteAPI's sandbox, the stay is added to the trip, and the answer is the confirmation with LiteAPI's booking id.

Both are plain `def` handlers (a prebook or book can wait on the network) and writes, so the access beforeware gives them to editors only: a viewer is refused (403) before
anything is asked of LiteAPI. Flights are not booked here: the confirmation links to the flight lane's partner like any other search. The words, prices and the guest's name
and email come out through FastHTML's escaping; the guest's email is never logged and never put in a URL.
"""

from datetime import date

from fasthtml.common import A, Button, Div, Form, H2, H3, Input, Label, Li, Ol, P, Span, to_xml
from starlette.responses import RedirectResponse, Response

from gitaway import catalog, importer, liteapi, matrixbook as mb, session as ses, showcase, tripmatrix as tm, tripstart
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import plan_search, tripmatrix as mx
from gitaway.partners import registry

CONFIRM = mx.BOOK + "/confirm"
SIGNIN = "Sign in to book."
STEPS = (("room", "Room", "bed", "k-stay"), ("guest", "Guest", "users", "k-flight"), ("booked", "Booked", "check", "k-car"))
STALE = "That room check has expired or is not for this square. Close this and press Book on the square again."
SLOW_DOWN = "That is a lot of booking tries. Wait a minute, or try again tomorrow."
MADE_UP = ("Test", "Traveler", "test.traveler@example.com")      # the sandbox form starts with a made-up guest (D-494)


def _steps(at: str):
    """The three steps as chips: those before `at` done, `at` active, the rest waiting. The CSS settles each chip as it changes."""
    order = [k for k, *_ in STEPS]
    return Ol(*[Li(Span(icon(ic, 16, 2.4), cls=f"mxb-chip {kind}"), Span(name, cls="mxb-step-n"), cls="mxb-step", data_state="done" if order.index(k) < order.index(at) else
                  "active" if k == at else "todo") for k, name, ic, kind in STEPS], cls="mxb-steps", aria_label="Booking steps")


def _head(s, lane, w, sample: bool, booked: bool = False):
    return Div(mx._arts(lane, "mxb-art"), Div(H2(f"Book {lane.name}", cls="mxb-h"), P(f"{tm.when(w)} · {w.nights} nights · {mx.party_words(s)}", cls="mxb-sub"), cls="mxb-top"),
               P(icon("shield", 16, 2.4), mb.SAMPLE_WORDS if sample else mb.NOTHING_CHARGED, cls="mxb-sandbox" + (" is-booked" if booked else ""), role="status" if booked else "note"), cls="mxb-head")


def _stay_row(row: mb.Row, sample: bool):
    pre, part = row.prebook, row.part
    nights = (pre.checkout - pre.checkin).days
    words = [pre.room or part.room, f"{nights} night{'s' if nights != 1 else ''}", f"{pre.checkin:%b} {pre.checkin.day} to {pre.checkout:%b} {pre.checkout.day}",
             "Refundable" if pre.refundable else "Non-refundable"]
    return Div(Span(icon("bed", 16, 2.2), cls="mx-kt k-stay"),
               Div(P(part.name, cls="mx-r-h"), P(f"{row.place} · " + " · ".join(w for w in words if w), cls="mx-r-s"),
                   P(f"{catalog.money(pre.due_at_stay_cents)} of it is paid at the hotel", cls="mx-r-s mx-r-due") if pre.due_at_stay_cents else ""),
               Span(catalog.money(row.total_cents), cls="mx-r-n"), cls="mx-row mxb-row")


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


def _hidden(s, lane, w, **more):
    return [Input(type="hidden", name=n, value=str(v)) for n, v in {**mx.params(s, lane=lane.key, w=w.key), **more}.items()]


def _guest_form(s, lane, w, prep, values=None, errors=None):
    values, errors = values or dict(zip(("first", "last", "email"), MADE_UP)), errors or {}
    return Form(*_hidden(s, lane, w, token=prep.token),
                H3("Who is the lead guest?", cls="mxb-q"),
                P("A made-up guest is filled in: this is the sandbox, so there is no need to type a real name or email. LiteAPI’s test system gets it and GitAway keeps nothing of it.", cls="mxb-hint"),
                Div(_field("first", "First name", values.get("first", ""), errors.get("first"), autocomplete="given-name", maxlength=mb.NAME_MAX),
                    _field("last", "Last name", values.get("last", ""), errors.get("last"), autocomplete="family-name", maxlength=mb.NAME_MAX), cls="mxb-two"),
                _field("email", "Email", values.get("email", ""), errors.get("email"), type="email", autocomplete="email", maxlength=mb.EMAIL_MAX, inputmode="email"),
                Button(icon("check", 16, 2.4), f"Book · {catalog.money(prep.total_cents)}", type="submit", cls="btn btn-ink mxb-go"),
                P(mb.SAMPLE_WORDS if prep.sample else mb.NOTHING_CHARGED + ". LiteAPI’s test card pays; no email is sent.", cls="mxb-fine"),
                method="post", action=CONFIRM, cls="mxb-f", data_step="guest")


def _flight_link(s, lane, w):
    search, _ = tripstart.read({"place": lane.places[0].name, "d": w.depart.isoformat(), "r": w.return_.isoformat(), "a": str(s.adults), "k": ",".join(map(str, s.kid_ages)),
                                "home": s.home})
    found = registry.lane("flight", search) if search else []
    return (found[0].name, plan_search._href(found[0], plan_search.query(search))) if found else None


def _day(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{day:%b} {day.day}"


def _done_row(d: mb.Done):
    return Div(Span(icon("check", 16, 2.6), cls="mx-kt k-car mxb-tick"),
               Div(P(d.hotel, cls="mx-r-h"), P(f"{d.place} · {_day(d.checkin)} to {_day(d.checkout)}", cls="mx-r-s"),
                   P("Booking id ", Span(d.booking_id, cls="mxb-id", data_booking_id=d.booking_id), cls="mx-r-s"),
                   P("Hotel confirmation ", Span(d.confirmation, cls="mxb-id"), cls="mx-r-s") if d.confirmation else ""),
               Span(catalog.money(d.total_cents), cls="mx-r-n"), cls="mx-row mxb-row mxb-done")


def _confirmation(s, lane, w, res: mb.Result, who: str):
    first = res.done[0]
    flight = _flight_link(s, lane, w)
    sample = any(d.sample for d in res.done)
    return Div(Div(Span(icon("check", 28, 2.6), cls="mxb-big"), H3("Booked" + ("" if len(res.done) == 1 else f", {len(res.done)} stays"), cls="mxb-q"),
                   P(f"{who}, your {'sample ' if sample else ''}booking is confirmed.", cls="mxb-hint"), cls="mxb-booked"),
               Div(*[_done_row(d) for d in res.done], cls="mx-rows"),
               Div(Span(icon("plane", 16, 2.2), cls="mx-kt k-flight"),
                   Div(P("Flights", cls="mx-r-h"), P("They book on their own site, so you choose the fare.", cls="mx-r-s"),
                       A(f"Search on {flight[0]}", href=flight[1], cls="btn mxb-flight", rel="noopener")), Span(""), cls="mx-row mxb-row") if flight else "",
               A(icon("arrow-right", 18, 2.4), "Open your trip", href="/trip/cockpit", cls="btn btn-ink mxb-go", data_trip="1"),
               cls="mxb-confirm", data_step="booked")


def _problem(words: str):
    return Div(P(icon("bell", 18, 2.4), words, cls="mxb-note is-warn", role="alert"), A("Back to the square", href="#", cls="btn mxb-back", data_close="1"), cls="mxb-problem", data_step="problem")


def sheet(s, lane, w, *, prep=None, at="guest", values=None, errors=None, note="", res=None, problem="", sample=False, who=""):
    """The booking sheet's inside: the head, the steps, and the one step it is at (a fragment: assets/js/matrixbook.js puts it in the sheet and settles it)."""
    if problem:
        body, at = _problem(problem), "room"
    elif res is not None and res.ok:
        body, at = _confirmation(s, lane, w, res, who), "booked"
    else:
        body = Div(Div(*[_stay_row(r, prep.sample) for r in prep.rows], cls="mx-rows"),
                   P(Span("Total", cls="mxb-tl"), Span(catalog.money(prep.total_cents), cls="mx-r-n mxb-total"), cls="mxb-sum"),
                   _moved(prep), P(icon("bell", 16, 2.4), note, cls="mxb-note", role="status") if note else "",
                   _guest_form(s, lane, w, prep, values, errors), cls="mxb-body", data_step="guest")
    return Div(_head(s, lane, w, sample or (prep is not None and prep.sample) or (res is not None and any(d.sample for d in res.done)),
                    booked=at == "booked"), _steps(at), body,
               cls="mxb", data_at=at, data_open=tm.key(lane.key, w.key))


def _answer(request, s, lane, w, inner, status=200):
    """The sheet as a fragment for the script, else as a page of its own (no script: the same words, the same two steps)."""
    if request.headers.get("x-matrix") == "1":
        return Response(to_xml(inner), media_type="text/html", status_code=status, headers={"Cache-Control": "no-store"})
    back = A(icon("chev-left", 18, 2.4), "Back to the matrix", href=mx.href(s, mx.SQUARE, lane=lane.key, w=w.key), cls="btn mx-back")
    return page(f"Book {lane.name}", Div(back, Div(inner, cls="mx-side mx-alone mxb-page"), cls="mx mx-one"), current="/plan/matrix", head=mx.HEAD, noindex=True)


def _family(session):
    return mx._family(session)


def _read(s, lane_key, w_key, family):
    """(lane, window, square): the square as it was shown (kept answers first), else asked again."""
    lane, w, sq, _ = mx._square_of(s, lane_key, w_key, family, True)
    if lane is not None and sq is None:
        lane, w, sq, _ = mx._square_of(s, lane_key, w_key, family)
    return lane, w, sq


def _prepare(s, lane, w, sq, family):
    dates = [(p.name, a, b) for p, a, b in tm.stays_for(lane, w)]
    prep = mb.prepare(sq.stays, dates, family, sample=sq.sample)
    if prep.status == liteapi.GONE:
        liteapi.forget_stays()      # the kept rooms are stale: the matrix asks again
    return prep


def _square_of(s, lane, w) -> tuple:
    """What a held room is bound to: the square's key and the address words it was asked with."""
    return tm.key(lane.key, w.key), tuple(sorted((n, str(v)) for n, v in mx.params(s, lane=lane.key, w=w.key).items()))


def _first_step(request, session, s, lane, w, sq, note=""):
    family = _family(session)
    if not sq.ok or not sq.stays:
        return _answer(request, s, lane, w, sheet(s, lane, w, problem=tm.SAID.get(sq.status, "That square has no stay to book."), sample=sq.sample))
    prep = _prepare(s, lane, w, sq, family)
    if not prep.ok:
        return _answer(request, s, lane, w, sheet(s, lane, w, problem=mb.SAID.get(prep.status, mb.SAID[liteapi.FAILED]), sample=sq.sample))
    mb.hold(family, prep, _square_of(s, lane, w))
    return _answer(request, s, lane, w, sheet(s, lane, w, prep=prep, note=note))


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
    def book_room(request, session, lane: str = "", w: str = "", to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "",
                  b: str = ""):
        s = mx.state(to, home, d, r, a, k, x, nb, b)
        if s.problems:
            return RedirectResponse(mx.href(s), status_code=303)
        me = ses.current_traveler(session)
        if not me:
            return _signed_out(s, lane, w)
        if not mb.allow(me.id):      # before anything is read: a refused press starts no search
            return _slowed(request, s, lane, w)
        lane_, w_, sq = _read(s, lane, w, _family(session))
        if lane_ is None:
            return RedirectResponse(mx.href(s), status_code=303)
        return _first_step(request, session, s, lane_, w_, sq)

    @app.post(CONFIRM)
    def book_confirm(request, session, lane: str = "", w: str = "", token: str = "", first: str = "", last: str = "", email: str = "", to: str = "", home: str = "", d: str = "",
                     r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        s = mx.state(to, home, d, r, a, k, x, nb, b)
        if s.problems:
            return RedirectResponse(mx.href(s), status_code=303)
        me = ses.current_traveler(session)
        if not me:
            return _signed_out(s, lane, w)
        if not mb.allow(me.id):
            return _slowed(request, s, lane, w)
        family = _family(session)
        lane_, w_, sq = _read(s, lane, w, family)
        if lane_ is None:
            return RedirectResponse(mx.href(s), status_code=303)
        prep = mb.held(family, token, _square_of(s, lane_, w_))
        if prep is None:      # restarted, kept too long, another family's or another square's token: nothing is asked of LiteAPI
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, problem=STALE, sample=sq.sample))
        guest, errors = mb.clean_guest(first, last, email)
        if errors:
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, prep=prep, values={"first": first[:mb.NAME_MAX], "last": last[:mb.NAME_MAX], "email": email[:mb.EMAIL_MAX]},
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
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, prep=prep, res=res, who=f"{guest.first} {guest.last}"))
        said = mb.SAID.get(res.status, mb.SAID[liteapi.FAILED])
        left = f" {len(res.done)} of {len(prep.rows)} stays are booked; press Book again for the rest." if res.done else ""
        return _answer(request, s, lane_, w_, sheet(s, lane_, w_, prep=prep, values={"first": guest.first, "last": guest.last, "email": guest.email}, note=said + left))
