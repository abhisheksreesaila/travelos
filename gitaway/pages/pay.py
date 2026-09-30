"""One-tap pay and celebration (F-018).

GET /plan/pay?f=&h=&c=  the workspace dimmed behind a bottom sheet (signed out: sign in first, then back to /plan)
POST /pay               records the booking in the session (idempotent), then redirects to /booked
GET /booked             the celebration card; no booking sends you back to /plan

Every figure comes from catalog.quote; the POST recomputes it from the picks and never trusts a posted total.
"""

from urllib.parse import quote as urlquote

from fasthtml.common import A, Button, Div, Form, H2, Input, Link, P, Script, Span
from starlette.responses import RedirectResponse

from gitaway import catalog, session as ses
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
    return f"{PLACE}, {_day(trip.depart)} – {trip.return_.day}"


def signin_for_pay(path):
    return RedirectResponse(f"/signin?next={urlquote(path, safe='')}&intent=pay", status_code=303)


def _line(offer, tile):
    icon_name, fill = tile
    return Div(
        Span(icon(icon_name, 22, 2.1), cls=f"pay-tile {fill}"),
        Span(Span(offer.name, cls="pay-name"), Span(offer.detail, cls="pay-detail"), cls="pay-text"),
        Span(catalog.money(offer.price_cents), cls="pay-price"),
        cls="pay-line",
    )


def sheet(q, who):
    trip = catalog.SAMPLE_TRIP
    money = catalog.money(q.total_cents)
    return Div(
        Div(cls="pay-backdrop", aria_hidden="true"),
        Div(
            Span(cls="pay-grip", aria_hidden="true"),
            Div(H2(trip_title(trip), id="pay-title"), Span(f"{trip.travelers} travelers", cls="pay-who"), cls="pay-head"),
            Div(
                *[_line(o, tile) for o, tile in zip(q.lines, TILES)],
                Div(Span("Total, taxes & fees in"), Span(money, cls="pay-total", id="pay-total"), cls="pay-sum"),
                cls="pay-lines",
            ),
            Div(
                Span("DEMO", cls="pay-chip", aria_hidden="true"),
                Span("Demo card ending 4242", cls="pay-card"),
                Span(f"{who.name.split()[0]} pays", cls="pay-payer"),
                cls="pay-method",
            ),
            Form(
                Input(type="hidden", name="f", value=q.flight_id),
                Input(type="hidden", name="h", value=q.stay_id),
                Input(type="hidden", name="c", value=q.car_id),
                Button(f"Pay {money}", type="submit", cls="btn btn-ink pay-go", id="pay-go"),
                A("Back to my picks", href=plan.plan_path(q.flight_id, q.stay_id, q.car_id), id="pay-cancel", cls="pay-back"),
                action="/pay", method="post", cls="pay-form",
            ),
            P("Simulated checkout. No money moves and nothing is really booked.", cls="pay-note"),
            role="dialog", aria_modal="true", aria_labelledby="pay-title", id="pay-dialog", cls="pay-sheet",
        ),
        cls="pay-layer",
    )


def flight_chip(o):
    trip = catalog.SAMPLE_TRIP
    when = f"{trip.depart.strftime('%a')} {_day(trip.depart)}"
    return f"{o.name} · {when} · {o.headline.split(' → ')[0]} · {trip.origin} → {o.airport}"


def celebration(b):
    trip = catalog.SAMPLE_TRIP
    flight, stay = catalog.offer(b["flight"]), catalog.offer(b["stay"])
    confetti = Div(
        *[Span(cls="pay-conf", style=f"--c:var(--{CONFETTI[i % 6]});--x:{(i * 37) % 100}%;--d:{(i % 9) * 0.07:.2f}s;"
                                     f"--w:{8 + i % 3 * 4}px;--h:{14 + i % 4 * 3}px;--r:{(i * 53) % 360}deg")
          for i in range(28)],
        cls="pay-confetti", aria_hidden="true",
    )
    card = Div(
        Span(icon("plane", 48, 2), cls="pay-badge", aria_hidden="true"),
        H2(f"You're going to {PLACE}!", id="pay-done-title"),
        P("Your flights and hotel are on the trip calendar. Now the fun part: fill the gaps with your crew."),
        Div(Span(flight_chip(flight), cls="pay-pill"), Span(f"{stay.name} · {trip.nights} nights", cls="pay-pill"), cls="pay-pills"),
        A("Open my trip calendar", href="/calendar", cls="btn btn-ink pay-cal", id="pay-cal"),
        Span(f"Booking {b['id']} · simulated, nothing was charged", cls="pay-ref"),
        role="dialog", aria_modal="true", aria_labelledby="pay-done-title", cls="pay-done",
    )
    return page("You're booked", Div(confetti, card, cls="pay-stage"), head=HEAD)


def register(app):
    @app.get("/plan/pay")
    def pay_sheet(session, f: str = "", h: str = "", c: str = ""):
        picks = plan.resolve_pick(f, h, c)
        who = ses.current_traveler(session)
        if not who:
            return signin_for_pay(plan.plan_path(*picks))
        return plan.workspace(*picks, overlay=(sheet(catalog.quote(*picks), who), Script(src="/assets/js/pay.js", defer=True)), head=HEAD)

    @app.post("/pay")
    def pay(session, f: str = "", h: str = "", c: str = ""):
        picks = plan.resolve_pick(f, h, c)
        if not ses.book(session, catalog.quote(*picks)):
            return signin_for_pay(plan.plan_path(*picks))
        return RedirectResponse("/booked", status_code=303)

    @app.get("/booked")
    def booked(session):
        b = ses.booking(session)
        if not b:
            return RedirectResponse("/plan", status_code=303)
        return celebration(b)
