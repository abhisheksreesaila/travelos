"""Schedule an Uber, simulated faithfully (F-038). The model and the provider seam are in gitaway/rides.py; this module is the screens.

GET  /rides/new?leg=arrive|depart&f=&h=&c=none&<trip>   choose a ride (products with price and time), then &p=<product> to confirm
POST /rides                                             schedule it for the guest; redirects to the ride
GET  /rides/{id}                                        the ride: status timeline, driver, Step the simulation, Cancel
POST /rides/{id}/step   POST /rides/{id}/cancel         then back to the ride

The screens talk only to `rides.provider()`, so a real Uber client can replace the simulator. Every figure comes from the provider;
a POST recomputes the leg and the fare id and never trusts a posted price.
"""

from urllib.parse import urlencode, quote as urlquote

from fasthtml.common import A, Button, Div, Form, H1, H2, H3, Input, Label, Li, Link, Ol, P, Span
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import catalog, rides, session as ses, tripcal
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import pay, plan

HEAD = (Link(rel="stylesheet", href="/assets/css/rides.css"),)
LEG_TITLE = {"arrive": "Arrival", "depart": "Departure"}


# ---- context: which picks the ride belongs to ------------------------------------------------------------------------

def _resolve(f, h, c, d, r, a, k):
    """(flight offer, stay offer or None, trip) for the picks in a URL, or a message when there is nothing to ride to or from."""
    fid, hid, cid = plan.resolve_pick(f, h, c)
    trip = plan.resolve_trip(d, r, a, k)
    if fid is None:
        return None, None, trip, "You're driving, so there's no airport to ride from. Pick a flight first."
    if cid is not None:
        return None, None, trip, "You picked a rental car, so there's no ride to schedule. Choose No car to schedule an Uber."
    if catalog.is_past(trip.depart, trip.return_):
        return None, None, trip, catalog.PAST_MESSAGE
    return catalog.offer(fid, trip), catalog.offer(hid, trip) if hid else None, trip, ""


def _params(flight, stay, trip, leg, **extra):
    q = {"leg": leg, "f": flight.id, "h": stay.id if stay else plan.SKIP, "c": plan.SKIP}
    q.update({k: v for k, v in (kv.split("=", 1) for kv in catalog.trip_query(trip).split("&") if kv)})
    q.update({k: v for k, v in extra.items() if v})
    return q


def new_url(flight, stay, trip, leg, product=None):
    return "/rides/new?" + urlencode(_params(flight, stay, trip, leg, p=product), safe=",")


def key_of(flight, stay, trip):
    return rides.context_key(flight.id, stay.id if stay else "", catalog.trip_query(trip))


def hidden(name, value):
    return Input(type="hidden", name=name, value=value)


def ctx_fields(flight, stay, trip, leg):
    return [hidden(k, v) for k, v in _params(flight, stay, trip, leg).items()]


def sim_badge():
    return Span(icon("shield", 16, 2.4), rides.SIMULATED_LABEL, cls="rd-sim", id="rd-sim")


def message_page(title, body, *links, status=200):
    out = page(title, Div(H1(title, cls="rd-title"), P(body, cls="rd-lede"), Div(*links, cls="rd-actions"), cls="rd-wrap rd-narrow"), head=HEAD)
    return FtResponse(out, status_code=status) if status != 200 else out


def sign_in_page(path):
    """Signed out: sign in (with the ride intent, so the dialog says why) and come straight back."""
    return RedirectResponse(f"/signin?next={urlquote(path, safe='')}&intent=ride", status_code=303)


# ---- the two steps ---------------------------------------------------------------------------------------------------

def _clock(p):
    return catalog._clock(p.pickup_time.hour * 60 + p.pickup_time.minute)


def when_text(p):
    return f"{rides.date_label(p.pickup_time)} · {_clock(p)}"


def timing_note(p, flight):
    if p.kind == "arrive":
        return (f"You land at {catalog._clock(flight.arrive_min)}. Pickup is {catalog.CURB_MINUTES} minutes later, once you're at the curb with your bags. "
                "Airport pickups use Uber Reserve: your driver tracks the flight and waits up to 45 minutes. Free to cancel until your driver arrives.")
    return (f"Your flight leaves at {catalog._clock(flight.back_depart_min)}. Be at the airport {catalog.AIRPORT_BUFFER // 60} hours ahead; "
            f"with about {p.minutes} minutes on the road, your driver arrives at {_clock(p)}. Free to cancel until your driver arrives.")


def _head(p, flight, step):
    steps = ("Choose a ride", "Confirm", "Scheduled")
    return Div(
        A(icon("chev-left", 16, 2.6), "Back", href=back_href(), cls="rd-back", id="rd-back"),
        H1(f"Schedule an Uber · {LEG_TITLE[p.kind]}", cls="rd-title"),
        Span(p.route, cls="rd-route"),
        sim_badge(),
        Ol(*[Li(Span(str(i), cls="rd-num"), Span(name), cls="rd-step", aria_current="step" if i == step else None) for i, name in enumerate(steps, 1)],
           cls="rd-steps", aria_label="Steps"),
        cls="rd-head",
    )


def back_href():
    return "/calendar"


def estimate_card(e, href):
    price = Span(e.display, cls="rd-price")
    body = [Div(Span(e.name, cls="rd-pname"), Span(f"{e.blurb} · seats {e.seats}", cls="rd-pdesc"), cls="rd-ptext"),
            Div(price, Span(f"{e.trip_minutes} min trip · driver {e.pickup_eta_min} min away", cls="rd-peta"), cls="rd-pnums")]
    if e.fits:
        return Li(*body, Span(e.note, cls="rd-pnote") if e.note else "",
                  A(f"Choose {e.name}", href=href, cls="btn btn-ink btn-sm rd-choose", data_choose=e.key, aria_label=f"Choose {e.name}, {e.display}"),
                  cls="rd-product", data_product=e.key)
    return Li(*body, Span(e.note, cls="rd-pnote"), Span("Not for your group", cls="rd-unfit"), cls="rd-product rd-product-off", data_product=e.key, aria_disabled="true")


def choose_view(p, flight, stay, trip, ests):
    options = Div(
        H2("Choose a ride", cls="rd-h2"),
        Span(f"Pickup {when_text(p)}", cls="rd-when", id="rd-when"),
        P(timing_note(p, flight), cls="rd-note"),
        Ol(*[estimate_card(e, new_url(flight, stay, trip, p.kind, e.key)) for e in ests], cls="rd-products", aria_label="Rides"),
        cls="rd-card rd-main",
    )
    app = Div(
        H3("Prefer to book in Uber?", cls="rd-h3"),
        P("This opens the Uber app with the pickup and dropoff filled in. Uber does the booking: GitAway doesn't schedule or track it, and a deep link can't hold a pickup time.", cls="rd-note"),
        A(icon("arrow-right", 16, 2.6), "Open in Uber app", href=rides.deeplink(p), cls="btn btn-sm rd-app", id="rd-app", rel="noopener"),
        cls="rd-card rd-aside", aria_label="Open in the Uber app",
    )
    return Div(options, app, cls="rd-cols")


def place_row(label, place):
    return Div(Span(icon("pin", 16, 2.4), Span(label), cls="rd-plabel"), Span(place.name, cls="rd-pname"), Span(place.address, cls="rd-pdesc"), cls="rd-place")


def confirm_view(p, flight, stay, trip, est, vals=None, error=""):
    vals = vals or {}

    def field(name, label, kind="text", **kw):
        return Label(Span(label), Input(type=kind, name=name, value=vals.get(name, ""), required=True, **kw), cls="rd-field")

    summary = Div(
        H2("Confirm pickup and dropoff", cls="rd-h2"),
        place_row("Pickup", p.pickup), place_row("Dropoff", p.dropoff),
        Div(Span("When", cls="rd-k"), Span(when_text(p), cls="rd-v", id="rd-when"), cls="rd-kv"),
        Div(Span("Ride", cls="rd-k"), Span(f"{est.name}" + (f" × {est.cars}" if est.cars > 1 else ""), cls="rd-v"), cls="rd-kv"),
        Div(Span("Price locked", cls="rd-k"), Span(est.display, cls="rd-v rd-price", id="rd-fare"), cls="rd-kv"),
        P(timing_note(p, flight), cls="rd-note"),
        cls="rd-card rd-main",
    )
    guest = Form(
        H2("Who's riding?", cls="rd-h2"),
        Div(error, role="alert", cls="rd-error", id="rd-error") if error else "",
        Div(field("first", "First name", autocomplete="given-name", maxlength=str(rides.MAX_NAME)), field("last", "Last name", autocomplete="family-name", maxlength=str(rides.MAX_NAME)), cls="rd-two"),
        field("phone", "Mobile phone", "tel", autocomplete="tel", placeholder="(310) 555-0123"),
        P("Uber texts the ride link to this number. In this simulation nothing is sent anywhere: the number stays in your family's private space.", cls="rd-note"),
        *ctx_fields(flight, stay, trip, p.kind), hidden("p", est.key), hidden("fare", est.fare_id),
        Button("Schedule this Uber", type="submit", cls="btn btn-ink rd-go", id="rd-go"),
        A("Choose a different ride", href=new_url(flight, stay, trip, p.kind), cls="rd-link", id="rd-change"),
        sim_badge(),
        action="/rides", method="post", cls="rd-card rd-aside",
    )
    return Div(summary, guest, cls="rd-cols")


def flow(session, path, leg, f, h, c, d, r, a, k, p="", vals=None, error="", status=200):
    if not ses.current_traveler(session):
        return sign_in_page(path)
    flight, stay, trip, problem = _resolve(f, h, c, d, r, a, k)
    if problem:
        return message_page("No Uber to schedule", problem, A("Back to my picks", href=plan.plan_path(*plan.resolve_pick(f, h, c), None, trip), cls="btn btn-ink"))
    try:
        leg_plan = rides.leg_plan(leg, flight, stay, trip)
    except rides.RideError as e:
        return message_page("No Uber to schedule", str(e), A("Back to my picks", href=plan.plan_path(flight.id, stay.id if stay else None, None, None, trip), cls="btn btn-ink"))
    existing = _live(session, key_of(flight, stay, trip), leg)
    if existing:
        return RedirectResponse(f"/rides/{existing.id}", status_code=303)
    ests = rides.provider().estimates(leg_plan)
    est = next((e for e in ests if e.key == p and e.fits), None) if p else None
    body = confirm_view(leg_plan, flight, stay, trip, est, vals, error) if est else choose_view(leg_plan, flight, stay, trip, ests)
    out = page("Schedule an Uber", Div(_head(leg_plan, flight, 2 if est else 1), body, cls="rd-wrap"), head=HEAD)
    return FtResponse(out, status_code=status) if status != 200 else out


def _live(session, key, leg):
    return next((x for x in rides.list_rides(session) if x.key == key and x.leg == leg and not x.canceled), None)


# ---- the ride --------------------------------------------------------------------------------------------------------

def headline(r, s):
    p = r.plan
    return {
        "scheduled": "Your Uber is scheduled. A driver is assigned shortly before pickup.",
        "processing": "We're finding you a driver.",
        "accepted": f"{s.driver} is on the way in a {s.vehicle} (plate {s.plate}).",
        "arriving": f"{s.driver} is arriving at {p.pickup.name}.",
        "in_progress": f"You're on your way to {p.dropoff.name}.",
        "completed": f"You've arrived at {p.dropoff.name}. Thanks for riding.",
        "rider_canceled": "This ride was cancelled.",
    }[s.name]


def timeline(s):
    items = []
    for i, (name, label) in enumerate(rides.TIMELINE):
        state = "done" if s.step > i else "now" if s.step == i else "todo"
        items.append(Li(Span(icon("check", 14, 3) if state == "done" else Span(str(i + 1)), cls="rd-dot"), Span(label), cls=f"rd-tl rd-tl-{state}",
                        aria_current="step" if state == "now" else None, data_tl=name))
    return Ol(*items, cls="rd-timeline", aria_label="Ride status")


def ride_view(session, r, error="", status=200):
    prov = rides.provider()
    s = prov.status(r)
    p = r.plan
    b = ses.booking(session)
    on_cal = bool(b and rides.booking_key(b) == r.key and tripcal.rides_of(b))
    controls = []
    if getattr(prov, "can_step", False) and s.can_step:
        controls.append(Form(Button(icon("rotate", 16, 2.4), "Step the simulation", type="submit", cls="btn btn-sm rd-step-btn", id="rd-step"),
                             Span(f"Next: {s.next_action.replace('_', ' ').title()}" if s.next_action else "", cls="rd-hint"),
                             action=f"/rides/{r.id}/step", method="post", cls="rd-ctl"))
    if s.can_cancel:
        controls.append(Form(Button("Cancel this ride", type="submit", cls="btn btn-sm rd-cancel", id="rd-cancel"),
                             Span("Free to cancel until your driver arrives.", cls="rd-hint"),
                             action=f"/rides/{r.id}/cancel", method="post", cls="rd-ctl"))
    driver = Div(Span(icon("car", 20, 2.2), cls="rd-car"), Div(Span(s.driver, cls="rd-pname"), Span(f"{s.vehicle} · plate {s.plate}", cls="rd-pdesc")), cls="rd-driver", id="rd-driver") if s.driver and not r.canceled else ""
    status_block = Div(
        Span(s.label, cls="rd-status", id="rd-status", data_status=s.name),
        P(headline(r, s), cls="rd-headline", id="rd-headline"),
        Div(error, role="alert", cls="rd-error", id="rd-error") if error else "",
        timeline(s) if not r.canceled else "",
        driver,
        cls="rd-card rd-main",
    )
    where = ("Shown on your trip calendar." if on_cal else "It will show on your trip calendar once this trip is booked.")
    details = Div(
        H2(f"{LEG_TITLE[r.leg]} · {r.product_name}" + (f" × {r.cars}" if r.cars > 1 else ""), cls="rd-h2"),
        Div(Span("Pickup", cls="rd-k"), Span(f"{p.pickup.name}", cls="rd-v"), cls="rd-kv"),
        Div(Span("Dropoff", cls="rd-k"), Span(f"{p.dropoff.name}", cls="rd-v"), cls="rd-kv"),
        Div(Span("When", cls="rd-k"), Span(when_text(p), cls="rd-v"), cls="rd-kv"),
        Div(Span("Fare", cls="rd-k"), Span(catalog.money(r.cents), cls="rd-v rd-price"), cls="rd-kv"),
        Div(Span("Rider", cls="rd-k"), Span(f"{r.guest.name} · {r.guest.phone_shown}", cls="rd-v"), cls="rd-kv"),
        Div(Span("Request", cls="rd-k"), Span(r.request_id, cls="rd-v rd-mono", id="rd-request"), cls="rd-kv"),
        P(where, cls="rd-note"),
        *controls,
        Div(A("Open my trip calendar", href="/calendar", cls="btn btn-ink btn-sm", id="rd-cal") if on_cal else
            A("Back to my picks", href="/plan" + (f"?{ses.remembered_plan(session)}" if ses.remembered_plan(session) else ""), cls="btn btn-sm", id="rd-picks"),
            A("Schedule another Uber", href="/calendar", cls="rd-link") if r.canceled and on_cal else "", cls="rd-actions"),
        cls="rd-card rd-aside",
    )
    out = page(f"Your Uber · {LEG_TITLE[r.leg]}", Div(
        Div(H1(f"Your Uber · {LEG_TITLE[r.leg]}", cls="rd-title"), Span(p.short_route, cls="rd-route"), sim_badge(), cls="rd-head"),
        Div(status_block, details, cls="rd-cols"), cls="rd-wrap"), head=HEAD)
    return FtResponse(out, status_code=status) if status != 200 else out


def not_found():
    return message_page("We couldn't find that ride", "It may have been removed, or it belongs to another traveler.", A("Open my trip calendar", href="/calendar", cls="btn btn-ink"), status=404)


# ---- routes ----------------------------------------------------------------------------------------------------------

def register(app):
    @app.get("/rides/new")
    def new(session, request, leg: str = "", f: str = "", h: str = "", c: str = "none", d: str = "", r: str = "", a: str = "", k: str = "", p: str = ""):
        path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return flow(session, path, leg, f, h, c, d, r, a, k, p)

    @app.post("/rides")
    def schedule(session, request, leg: str = "", f: str = "", h: str = "", c: str = "none", d: str = "", r: str = "", a: str = "", k: str = "",
                 p: str = "", fare: str = "", first: str = "", last: str = "", phone: str = ""):
        if not ses.current_traveler(session):
            return sign_in_page("/rides/new")
        vals = {"first": first, "last": last, "phone": phone}
        flight, stay, trip, problem = _resolve(f, h, c, d, r, a, k)
        if problem:
            return message_page("No Uber to schedule", problem, A("Back to my picks", href="/plan", cls="btn btn-ink"))
        try:
            leg_plan = rides.leg_plan(leg, flight, stay, trip)
        except rides.RideError as e:  # a bad leg: nothing to quote or schedule
            return message_page("We couldn't schedule that", str(e), A("Back to my picks", href=plan.plan_path(flight.id, stay.id if stay else None, None, None, trip), cls="btn btn-ink"), status=422)
        try:
            est = next((e for e in rides.provider().estimates(leg_plan) if e.key == p), None)
            if not est:
                raise rides.RideError("Pick one of the rides.")
            guest = rides.validate_guest(first, last, phone)
            req = rides.ScheduleRequest(leg_plan, guest, est.product_id, fare, rides.next_ride_id(session), key_of(flight, stay, trip))
            ride = rides.schedule_ride(session, req)
        except rides.RideError as e:
            path = "/rides/new?" + urlencode(_params(flight, stay, trip, leg, p=p), safe=",")
            return flow(session, path, leg, f, h, c, d, r, a, k, p, vals, str(e), status=422) if est_fits(session, leg_plan, p) else \
                message_page("We couldn't schedule that", str(e), A("Start again", href=new_url(flight, stay, trip, leg), cls="btn btn-ink"), status=409)
        return RedirectResponse(f"/rides/{ride.id}", status_code=303)

    @app.get("/rides/{ride_id}")
    def ride(session, ride_id: str):
        if not ses.current_traveler(session):
            return sign_in_page(f"/rides/{ride_id}")
        found = rides.get_ride(session, ride_id)
        return ride_view(session, found) if found else not_found()

    @app.post("/rides/{ride_id}/step")
    def step(session, ride_id: str):
        return _act(session, ride_id, rides.step_ride)

    @app.post("/rides/{ride_id}/cancel")
    def cancel(session, ride_id: str):
        return _act(session, ride_id, rides.cancel_ride)


def est_fits(session, leg_plan, p):
    try:
        return any(e.key == p and e.fits for e in rides.provider().estimates(leg_plan))
    except rides.RideError:
        return False


def _act(session, ride_id, action):
    if not ses.current_traveler(session):
        return sign_in_page(f"/rides/{ride_id}")
    try:
        action(session, ride_id)
    except rides.RideError as e:
        found = rides.get_ride(session, ride_id)
        return ride_view(session, found, str(e), 409) if found else not_found()
    return RedirectResponse(f"/rides/{ride_id}", status_code=303)
