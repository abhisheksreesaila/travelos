"""One-tap pay and celebration (F-018).

GET /plan/pay?f=&h=&c=  the workspace dimmed behind a bottom sheet (signed out: sign in first, then back to /plan)
POST /pay               records the booking in the session (idempotent), then redirects to /booked
GET /booked             the celebration card; no booking sends you back to /plan

Every figure comes from catalog.quote; the POST recomputes it from the picks and never trusts a posted total.
"""

from urllib.parse import parse_qsl, quote as urlquote

from fasthtml.common import A, Button, Div, Form, H2, Input, Li, Link, P, Script, Section, Span, Ul
from starlette.responses import RedirectResponse

from gitaway import catalog, rides as ride_model, session as ses, tripcal
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import plan

HEAD = (Link(rel="stylesheet", href="/assets/css/pay.css"),)
PLACE = "LA"
CONFETTI = ("sun", "mint", "sky", "grape", "bubble", "coral")
TILES = (("plane", "fill-sun-tint"), ("bed", "fill-mint-tint"), ("car", "fill-sky-tint"))


def _day(d):
    return f"{d.strftime('%b')} {d.day}"


def trip_title(trip=None):
    trip = trip or catalog.SAMPLE_TRIP
    return f"{trip.place}, {trip.date_label}"


def trip_fields(trip):
    """Hidden inputs that carry the trip through the pay form (none for the sample trip)."""
    return [Input(type="hidden", name=k, value=v) for k, v in parse_qsl(catalog.trip_query(trip))]


def signin_for_pay(path):
    return RedirectResponse(f"/signin?next={urlquote(path, safe='')}&intent=pay", status_code=303)


def _item(i):
    return Li(Span(f"{i.name} ×{i.qty}" if i.qty > 1 else i.name, cls="pay-item-name"), Span(catalog.money(i.cents), cls="pay-item-price"), cls="pay-item")


def _line(q, lane, offer, tile):
    """One lane of the sheet: its name and total, then each priced item in it (rooms and add-ons for the stay, fare and bags for a flight that has any)."""
    items = [i for i in q.items if i.lane == lane]
    icon_name, fill = tile
    detail = f"{q.trip.nights_text} · {offer.headline}" if lane == "stay" else offer.detail
    return Div(
        Div(
            Span(icon(icon_name, 22, 2.1), cls=f"pay-tile {fill}"),
            Span(Span(offer.name, cls="pay-name"), Span(detail, cls="pay-detail"), cls="pay-text"),
            Span(catalog.money(q.lane_cents(lane)), cls="pay-price"),
            cls="pay-line-head",
        ),
        Ul(*[_item(i) for i in items], cls="pay-items", aria_label=f"{offer.name}, itemized") if lane == "stay" or (lane == "flight" and len(items) > 1) else "",
        cls="pay-line",
    )


def rides_row(r):
    """The rides estimate on the sheet: shown, labelled, and clearly not part of what is charged."""
    return Div(
        Span(icon("car", 22, 2.1), cls="pay-tile fill-sky-tint"),
        Span(Span("Rides, estimated", cls="pay-name"), Span(f"{r.title} · not charged", cls="pay-detail"), cls="pay-text"),
        Span(f"about {catalog.money(r.cents)}", cls="pay-price"),
        cls="pay-rides", id="pay-rides",
    )


def pay_label(q):
    """The pay button: "Pay $3,088", or "Pay $2,764 now · about $140 in rides later" when rides are estimated."""
    money = f"Pay {catalog.money(q.paid_cents)}"
    return f"{money} now · about {catalog.money(q.rides.cents)} in rides later" if q.rides else money


def refused(message, back):
    return page("Not booked", Div(H2("We couldn't book that"), P(message), A("Back to my picks", href=back, cls="btn btn-ink"), cls="pay-stage"), head=HEAD)


def sheet(q, who):
    trip = q.trip
    money = catalog.money(q.paid_cents)
    return Div(
        Div(cls="pay-backdrop", aria_hidden="true"),
        Div(
            Span(cls="pay-grip", aria_hidden="true"),
            Div(H2(trip_title(trip), id="pay-title"), Span(f"{trip.travelers} travelers", cls="pay-who"), cls="pay-head"),
            Div(
                *[_line(q, lane, o, tile) for lane, o, tile in zip(plan.LANES, q.lines, TILES) if o is not None],
                Div(Span("Total, taxes & fees in"), Span(money, cls="pay-total", id="pay-total"), cls="pay-sum"),
                rides_row(q.rides) if q.rides else "",
                cls="pay-lines",
            ),
            Div(
                Span("DEMO", cls="pay-chip", aria_hidden="true"),
                Span("Demo card ending 4242", cls="pay-card"),
                Span(f"{who.name} pays", cls="pay-payer"),
                cls="pay-method",
            ),
            Form(
                Input(type="hidden", name="f", value=plan.lane_id(q.flight_id)),
                Input(type="hidden", name="h", value=plan.lane_id(q.stay_id)),
                Input(type="hidden", name="c", value=plan.lane_id(q.car_id)),
                *([Input(type="hidden", name="rooms", value=q.stay.rooms_code)] if q.stay and q.stay.rooms_code else []),
                *([Input(type="hidden", name="add", value=q.stay.add_code)] if q.stay and q.stay.addons else []),
                *([Input(type="hidden", name="fare", value=q.flight.fare_code)] if q.flight and q.flight.fare_code else []),
                *([Input(type="hidden", name="bags", value=q.flight.bags_code)] if q.flight and q.flight.bags else []),
                *trip_fields(trip),
                Button(pay_label(q), type="submit", cls="btn btn-ink pay-go", id="pay-go"),
                A("Back to my picks", href=plan.plan_path(q.flight_id, q.stay_id, q.car_id, q.stay, q.trip, q.flight), id="pay-cancel", cls="pay-back"),
                action="/pay", method="post", cls="pay-form",
            ),
            P("Simulated checkout. No money moves and nothing is really booked.", cls="pay-note"),
            role="dialog", aria_modal="true", aria_labelledby="pay-title", id="pay-dialog", cls="pay-sheet",
        ),
        cls="pay-layer",
    )


def flight_chip(o, trip):
    when = f"{trip.depart.strftime('%a')} {_day(trip.depart)}"
    return f"{o.name} · {when} · {o.headline.split(' → ')[0]} · {trip.origin} → {o.airport}"


def rides_list(b, session):
    """The simulated Uber rides for a booking with no car (F-038): each leg shows its scheduled ride, or offers to schedule one."""
    if not tripcal.rides_of(b):
        return ""
    key, flight, stay, trip = ride_model.booking_key(b), tripcal.flight_of(b), tripcal.stay_of(b), tripcal.trip_of(b)
    mine = {r.leg: r for r in ride_model.list_rides(session) if r.key == key and not r.canceled}
    prov, rows = ride_model.provider(), []
    for leg in ride_model.LEGS:
        plan = ride_model.leg_plan(leg, flight, stay, trip)
        when = f"{ride_model.date_label(plan.pickup_time.date())}, {tripcal.fmt_time(plan.pickup_time.hour * 60 + plan.pickup_time.minute)}"
        r = mine.get(leg)
        if r:
            rows.append(Li(A(f"Uber · {r.product_name} · {plan.short_route}", href=f"/rides/{r.id}", cls="pay-ride-link"), Span(f"{when} · {prov.status(r).label}", cls="pay-ride-when"), cls="pay-ride", data_ride=leg))
        else:
            rows.append(Li(A("Schedule an Uber", href=plan_ride_path(leg, flight, stay, trip), cls="pay-ride-link"), Span(f"{plan.short_route} · {when}", cls="pay-ride-when"), cls="pay-ride pay-ride-open", data_ride=leg))
    return Div(Div(Span(icon("car", 16, 2.4), Span("Rides"), cls="pay-rides-title"), Span(ride_model.SIMULATED_LABEL, cls="pay-rides-sim"), cls="pay-rides-head"),
               Ul(*rows, cls="pay-ride-list"), cls="pay-ride-box", id="pay-ride-box")


def plan_ride_path(leg, flight, stay, trip):
    return plan.ride_path(leg, flight.id, stay.id if stay else None, trip)


def celebration(b, session=None):
    trip = tripcal.trip_of(b)
    flight, stay = tripcal.flight_of(b), tripcal.stay_of(b)
    pick, fare = tripcal.stay_pick_of(b), tripcal.flight_pick_of(b)
    rides = tripcal.rides_of(b)
    confetti = Div(
        *[Span(cls="pay-conf", style=f"--c:var(--{CONFETTI[i % 6]});--x:{(i * 37) % 100}%;--d:{(i % 9) * 0.07:.2f}s;"
                                     f"--w:{(8 + i % 3 * 4) / 16:g}rem;--h:{(14 + i % 4 * 3) / 16:g}rem;--r:{(i * 53) % 360}deg")
          for i in range(28)],
        cls="pay-confetti", aria_hidden="true",
    )
    pills = ([Span(flight_chip(flight, trip), cls="pay-pill")] if flight else []) + \
            ([Span(f"{stay.name} · {trip.nights_text}", cls="pay-pill")] if stay else []) + \
            ([Span(tripcal.car_of(b).name, cls="pay-pill")] if tripcal.car_of(b) else []) + \
            ([] if not fare or fare.is_default else [Span(fare.summary, cls="pay-pill")]) + ([Span(pick.summary, cls="pay-pill")] if pick else []) + \
            ([Span(f"Rides, estimated · about {catalog.money(rides.cents)}, paid later", cls="pay-pill pay-pill-soft")] if rides else [])
    card = Section(
        Span(icon("plane", 48, 2), cls="pay-badge", aria_hidden="true"),
        H2(f"You're going to {trip.place}!", id="pay-done-title"),
        P(tripcal.booked_sentence(b)),
        Div(*pills, cls="pay-pills"),
        rides_list(b, session) if session is not None else "",
        A("Open my trip calendar", href="/calendar", cls="btn btn-ink pay-cal", id="pay-cal"),
        Span(f"Booking {b['id']} · simulated, nothing was charged", cls="pay-ref"),
        aria_labelledby="pay-done-title", cls="pay-done",
    )
    return page("You're booked", Div(confetti, card, cls="pay-stage"), head=HEAD)


def register(app):
    @app.get("/plan/pay")
    def pay_sheet(session, f: str = "", h: str = "", c: str = "", rooms: str = None, add: str = None, fare: str = None, bags: str = None,
                  d: str = "", r: str = "", a: str = "", k: str = ""):
        picks, trip = plan.resolve_pick(f, h, c), plan.resolve_trip(d, r, a, k)
        stay, flight = plan.resolve_stay(picks[1], rooms, add, trip), plan.resolve_flight(picks[0], fare, bags, trip)
        who = ses.current_traveler(session)
        if not who:
            return signin_for_pay(plan.pay_path(*picks, stay, trip, flight))
        q = catalog.quote(*picks, stay, trip, flight)
        if q.empty:  # nothing picked: there is nothing to pay for
            return refused(ses.NOTHING_PICKED, plan.plan_path(*picks, stay, trip, flight))
        return plan.workspace(*picks, stay=stay, flight=flight, trip=trip,
                              overlay=(sheet(q, who), Script(src="/assets/js/pay.js", defer=True)), head=HEAD)

    @app.post("/pay")
    def pay(session, f: str = "", h: str = "", c: str = "", rooms: str = None, add: str = None, fare: str = None, bags: str = None,
            d: str = "", r: str = "", a: str = "", k: str = ""):
        """Books the picks. The total is always recomputed here; rooms that sleep too few become the default room, a bad fare Basic and bad bags none."""
        picks, trip = plan.resolve_pick(f, h, c), plan.resolve_trip(d, r, a, k)
        stay, flight = plan.resolve_stay(picks[1], rooms, add, trip), plan.resolve_flight(picks[0], fare, bags, trip)
        if catalog.is_past(trip.depart, trip.return_):  # a stale link must not book the past: back to the form, which says why
            return RedirectResponse(f"/start?go=1&to=la&{catalog.trip_query(trip)}&n={len(trip.kid_ages)}" + "".join(f"&k{i}={a}" for i, a in enumerate(trip.kid_ages, 1)), status_code=303)
        try:
            booked = ses.book(session, catalog.quote(*picks, stay, trip, flight))
        except ses.BookingError as e:
            back = plan.plan_path(*picks, stay, trip, flight)
            return refused(str(e), back)
        if not booked:
            return signin_for_pay(plan.pay_path(*picks, stay, trip, flight))
        return RedirectResponse("/booked", status_code=303)

    @app.get("/booked")
    def booked(session):
        b = ses.booking(session)
        if not b:
            return RedirectResponse("/plan", status_code=303)
        return celebration(b, session)
