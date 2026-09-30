"""One-tap pay and celebration (F-018).

GET /plan/pay?f=&h=&c=  the workspace dimmed behind a bottom sheet (signed out: sign in first, then back to /plan)
POST /pay               records the booking in the session (idempotent), then redirects to /booked
GET /booked             the celebration card; no booking sends you back to /plan

Every figure comes from catalog.quote; the POST recomputes it from the picks and never trusts a posted total.
"""

from urllib.parse import quote as urlquote

from fasthtml.common import A, Button, Div, Form, H2, Input, Li, Link, P, Script, Section, Span, Ul
from starlette.responses import RedirectResponse

from gitaway import catalog, session as ses, tripcal
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


def _item(i):
    return Li(Span(f"{i.name} ×{i.qty}" if i.qty > 1 else i.name, cls="pay-item-name"), Span(catalog.money(i.cents), cls="pay-item-price"), cls="pay-item")


def _line(q, lane, offer, tile):
    """One lane of the sheet: its name and total, then each priced item in it (rooms and add-ons for the stay)."""
    icon_name, fill = tile
    detail = f"{catalog.SAMPLE_TRIP.nights} nights · {offer.headline}" if lane == "stay" else offer.detail
    return Div(
        Div(
            Span(icon(icon_name, 22, 2.1), cls=f"pay-tile {fill}"),
            Span(Span(offer.name, cls="pay-name"), Span(detail, cls="pay-detail"), cls="pay-text"),
            Span(catalog.money(q.lane_cents(lane)), cls="pay-price"),
            cls="pay-line-head",
        ),
        Ul(*[_item(i) for i in q.items if i.lane == lane], cls="pay-items", aria_label=f"{offer.name}, itemized") if lane == "stay" else "",
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
                *[_line(q, lane, o, tile) for lane, o, tile in zip(plan.LANES, q.lines, TILES)],
                Div(Span("Total, taxes & fees in"), Span(money, cls="pay-total", id="pay-total"), cls="pay-sum"),
                cls="pay-lines",
            ),
            Div(
                Span("DEMO", cls="pay-chip", aria_hidden="true"),
                Span("Demo card ending 4242", cls="pay-card"),
                Span(f"{who.name} pays", cls="pay-payer"),
                cls="pay-method",
            ),
            Form(
                Input(type="hidden", name="f", value=q.flight_id),
                Input(type="hidden", name="h", value=q.stay_id),
                Input(type="hidden", name="c", value=q.car_id),
                *([Input(type="hidden", name="rooms", value=q.stay.rooms_code)] if q.stay.rooms_code else []),
                *([Input(type="hidden", name="add", value=q.stay.add_code)] if q.stay.addons else []),
                Button(f"Pay {money}", type="submit", cls="btn btn-ink pay-go", id="pay-go"),
                A("Back to my picks", href=plan.plan_path(q.flight_id, q.stay_id, q.car_id, q.stay), id="pay-cancel", cls="pay-back"),
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
    pick = tripcal.stay_pick_of(b)
    confetti = Div(
        *[Span(cls="pay-conf", style=f"--c:var(--{CONFETTI[i % 6]});--x:{(i * 37) % 100}%;--d:{(i % 9) * 0.07:.2f}s;"
                                     f"--w:{8 + i % 3 * 4}px;--h:{14 + i % 4 * 3}px;--r:{(i * 53) % 360}deg")
          for i in range(28)],
        cls="pay-confetti", aria_hidden="true",
    )
    card = Section(
        Span(icon("plane", 48, 2), cls="pay-badge", aria_hidden="true"),
        H2(f"You're going to {PLACE}!", id="pay-done-title"),
        P("Your flights and hotel are on the trip calendar. Now the fun part: fill the gaps with your crew."),
        Div(Span(flight_chip(flight), cls="pay-pill"), Span(f"{stay.name} · {trip.nights} nights", cls="pay-pill"),
            Span(pick.summary, cls="pay-pill"), cls="pay-pills"),
        A("Open my trip calendar", href="/calendar", cls="btn btn-ink pay-cal", id="pay-cal"),
        Span(f"Booking {b['id']} · simulated, nothing was charged", cls="pay-ref"),
        aria_labelledby="pay-done-title", cls="pay-done",
    )
    return page("You're booked", Div(confetti, card, cls="pay-stage"), head=HEAD)


def register(app):
    @app.get("/plan/pay")
    def pay_sheet(session, f: str = "", h: str = "", c: str = "", rooms: str = None, add: str = None):
        picks = plan.resolve_pick(f, h, c)
        stay = plan.resolve_stay(picks[1], rooms, add)
        who = ses.current_traveler(session)
        if not who:
            return signin_for_pay(plan.pay_path(*picks, stay))
        return plan.workspace(*picks, stay=stay, overlay=(sheet(catalog.quote(*picks, stay), who), Script(src="/assets/js/pay.js", defer=True)), head=HEAD)

    @app.post("/pay")
    def pay(session, f: str = "", h: str = "", c: str = "", rooms: str = None, add: str = None):
        """Books the picks. The total is always recomputed here; rooms that sleep too few become the default room."""
        picks = plan.resolve_pick(f, h, c)
        stay = plan.resolve_stay(picks[1], rooms, add)
        if not ses.book(session, catalog.quote(*picks, stay)):
            return signin_for_pay(plan.pay_path(*picks, stay))
        return RedirectResponse("/booked", status_code=303)

    @app.get("/booked")
    def booked(session):
        b = ses.booking(session)
        if not b:
            return RedirectResponse("/plan", status_code=303)
        return celebration(b)
