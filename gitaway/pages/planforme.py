"""Plan it for me (F-193): the screens and the Stripe webhook. The rules, the order and the money are gitaway/planforme.py.

GET  /plan-for-me                     the intake: where, dates, home airport, adults, kids with ages, budget, must-dos, pace (`?from=<a creator's trip>` carries its place and title)
POST /plan-for-me                     check it, make the order at the server's price, and go to Stripe Checkout (locally: the stand-in checkout); signed out goes to sign-in first
GET  /plan-for-me/<order>             the order: awaiting payment, paid, building, ready (the link to the trip and booking links) or failed ("we'll refund you"); its buyer only, anyone else a 404
GET  /plan-for-me/<order>/status      {"status": ...} for the page's own polling, buyer only
POST /plan-for-me/<order>/pay         pay for an order that has not been paid (a new Checkout session)
GET  /plan-for-me/<order>/go/<lane>   a booking link (flight, stay or activity) with the order id as the SubID, buyer only; nothing without TRAVELPAYOUTS_MARKER
GET/POST /sandbox/plan-for-me/<order> the local stand-in checkout (404 in production and whenever the showcase is off)
POST /stripe/webhook                  Stripe's `checkout.session.completed`: verified with STRIPE_WEBHOOK_SECRET, idempotent by event id (400 for a body Stripe did not sign, 503 with no secret set)

Writes are an editor's like every other POST (gitaway/access.py): the trip lands in a family a viewer cannot write to. Without STRIPE_SECRET_KEY every /plan-for-me address is a 404 in
production (gitaway/showcase.py).
"""

import json
import logging
import re
from datetime import date
from types import SimpleNamespace
from urllib.parse import quote, urlencode

from fasthtml.common import A, Button, Datalist, Div, Fieldset, Form, H1, H2, Input, Label, Legend, Li, Link, Main, Ol, Option, P, Script, Section, Select, Span, Textarea
from fasthtml.core import FtResponse
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse

from gitaway import access, auth, catalog, community, partners, pickers, planforme as pfm, publish, reports, session as ses, showcase, tripbuild
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import legal
from gitaway.partners import travelpayouts

log = logging.getLogger("gitaway.planforme")
PATH = "/plan-for-me"
HEAD = (*pickers.HEAD, Link(rel="stylesheet", href="/assets/css/planforme.css"), Script(src="/assets/js/planforme.js", defer=True))
LANES = {"flight": ("plane", "Flights", "aviasales"), "stay": ("bed", "Stays", "klook"), "activity": ("star", "Things to do", "klook")}
MAX_KIDS = tripbuild.MAX_KIDS


def money() -> str:
    return catalog.money(pfm.price_cents())


def _gone():
    return showcase.not_found()


def _base(request) -> str:
    """Where Stripe sends the buyer back to: the configured public address in production, else the address the request came to."""
    from gitaway import passkeys
    host = passkeys.public_host() if auth.production() else ""
    return f"https://{host}" if host else str(request.base_url).rstrip("/")


def _mine(session, order_id):
    me = ses.current_traveler(session)
    return pfm.get(order_id, me.id) if me else None


def _summary(intake) -> str:
    s, e = date.fromisoformat(intake["start"]), date.fromisoformat(intake["end"])
    dates = f"{s:%b} {s.day} – {e.day}, {e.year}" if (s.month, s.year) == (e.month, e.year) else f"{s:%b} {s.day} – {e:%b} {e.day}, {e.year}"
    kids = f", {len(intake['kids'])} kid{'s' if len(intake['kids']) != 1 else ''}" if intake["kids"] else ""
    return f"{intake['where']} · {dates} · {intake['adults']} adult{'s' if intake['adults'] != 1 else ''}{kids}"


def _signin(path):
    return RedirectResponse(f"/signin?next={quote(path, safe='/')}", status_code=303)


# ---- the intake -------------------------------------------------------------------------------------------------------

def _from_trip(slug):
    """(where, title) of a creator's real published trip to start from, or ("", "")."""
    row = community.get(slug) if slug and community.is_real(slug) else None
    return (community.trip_of(row).place, row["title"]) if row else ("", "")


def _field(label, control, hint="", error="", name=""):
    return Div(Label(Span(label, cls="pf-lab"), control, cls="pf-field"), P(hint, cls="pf-hint") if hint else "", P(error, role="alert", cls="pf-error", id=f"pf-err-{name}") if error else "", cls="pf-group")


def _pills(name, options, chosen, legend):
    return Fieldset(Legend(legend, cls="pf-lab"),
                    Div(*[Label(Input(type="radio", name=name, value=k, checked=k == chosen or None), Span(label, cls="pf-pill")) for k, label in options.items()], cls="pf-pills"), cls="pf-set")


def intake_page(session, vals=None, errors=None, status=200, note=""):
    errors, today = errors or {}, catalog.today()
    vals = vals or {}
    me = ses.current_traveler(session)
    viewer = access.request_role() == "viewer"
    where, like = _from_trip(vals.get("from", ""))
    where = vals.get("where") or where
    nkids = min(tripbuild._whole(str(vals.get("nkids", "0")), 0), MAX_KIDS)
    places = [d.name for d in catalog.DESTINATIONS] + list(pfm.SUGGESTIONS)
    bad = lambda n: {"aria_invalid": "true", "aria_describedby": f"pf-err-{n}"} if n in errors else {}
    kid = lambda i: Div(Label(Span(f"Kid {i}", cls="pf-lab"), Select(*[Option("Under 1" if a == 0 else str(a), value=str(a), selected=str(a) == str(vals.get(f"k{i}", "5")) or None) for a in range(catalog.MAX_KID_AGE + 1)],
                                                                          name=f"k{i}", id=f"pf-k{i}", data_ga="chips", data_ga_label=f"Kid {i} age", cls="pf-input", **bad(f"k{i}")), cls="pf-field"), P(errors[f"k{i}"], role="alert", cls="pf-error") if f"k{i}" in errors else "",
                        cls="pf-kid", hidden=i > nkids or None)
    form = Form(
        Input(type="hidden", name="from", value=vals.get("from", "")),
        _field("Where are you going?", Input(type="text", name="where", id="pf-where", value=where, list="pf-places", autocomplete="off", maxlength="60", placeholder="Disneyland, California", cls="pf-input", **bad("where")),
               "A city, a park, a region: type it or pick one.", errors.get("where", ""), "where"),
        Datalist(*[Option(value=p) for p in places], id="pf-places"),
        Div(_field("From", Input(type="date", name="start", id="pf-start", value=vals.get("start", ""), min=today.isoformat(), data_ga_range="trip", data_ga_label="From", cls="pf-input", **bad("start")), error=errors.get("start", ""), name="start"),
            _field("To", Input(type="date", name="end", id="pf-end", value=vals.get("end", ""), min=today.isoformat(), data_ga_range="trip", data_ga_end="", data_ga_label="To", cls="pf-input", **bad("end")), error=errors.get("end", ""), name="end"), cls="pf-two"),
        _field("Home airport", Input(type="text", name="home", id="pf-home", value=vals.get("home", ""), maxlength="3", autocapitalize="characters", autocomplete="off", placeholder="SFO", cls="pf-input pf-short", **bad("home")),
               "Optional. Three letters, for the flight link.", errors.get("home", ""), "home"),
        Div(_field("Adults", Select(*[Option(str(n), value=str(n), selected=str(n) == str(vals.get("adults", "2")) or None) for n in range(1, 13)], name="adults", id="pf-adults", data_ga="stepper", data_ga_label="Adults", data_ga_hint="18 and over", cls="pf-input", **bad("adults")),
                   error=errors.get("adults", ""), name="adults"),
            _field("Kids", Select(*[Option(str(n), value=str(n), selected=n == nkids or None) for n in range(MAX_KIDS + 1)], name="nkids", id="pf-nkids", data_ga="stepper", data_ga_label="Kids", data_ga_hint="under 18", cls="pf-input", **bad("nkids")), error=errors.get("nkids", ""), name="nkids"),
            cls="pf-two"),
        Div(*[kid(i) for i in range(1, MAX_KIDS + 1)], cls="pf-kids", id="pf-kids"),
        _pills("budget", pfm.BUDGETS, vals.get("budget", "comfortable"), "Budget"),
        _pills("pace", pfm.PACES, vals.get("pace", "balanced"), "Pace"),
        _field("Anything you must do?", Textarea(vals.get("must", ""), name="must", id="pf-must", rows="4", maxlength=str(pfm.MAX_MUST), placeholder="Space Mountain, a quiet beach morning, a birthday dinner...", cls="pf-input pf-text"),
               "Optional. Rides, places, a nap time, food the kids will eat.", errors.get("must", ""), "must"),
        P(f"You will sign in first, so the trip lands in your family's account." if not me else f"The trip goes into your family's GitAway account ({me.blurb}).", cls="pf-hint", id="pf-who"),
        P(errors["_"], role="alert", cls="pf-error", id="pf-err-all") if "_" in errors else "",
        Button(icon("star", 20, 2.4), f"Plan it for me · {money()}" if me else "Continue", type="submit", cls="btn btn-primary pf-go", id="pf-go", disabled=viewer or None),
        P(pfm.PROMISE, cls="pf-promise", id="pf-promise"),
        action=PATH, method="post", id="pf-form", cls="pf-form", data_signed_out="1" if not me else None)
    body = Section(
        Div(Span(f"{money()} once", cls="pf-chip", id="pf-price"), H1("Plan it for ", Span("me", cls="pf-accent")),
            P("Tell us who is going and what you love. An agent builds your whole trip, day by day, in your GitAway account in a few minutes.", cls="pf-lede"),
            P(f"Starting from “{like}”.", cls="pf-note", id="pf-like") if like else "",
            P("Only a family editor or admin can order, because the trip goes into the family's calendar.", role="status", cls="pf-note", id="pf-viewer") if viewer else "",
            P(note, role="alert", cls="pf-error", id="pf-note") if note else "", cls="pf-top"),
        form, cls="pf ga-wrap", id="pf")
    return FtResponse(page("Plan it for me", body, head=HEAD), status_code=status)


# ---- the order --------------------------------------------------------------------------------------------------------

def _steps(status):
    order = ["paid", "building", "ready"]
    at = order.index("paid" if status == "paid" else status) if status in order else 0
    labels = {"paid": "Payment received", "building": "Building your days", "ready": "Ready"}
    return Ol(*[Li(Span(icon("check", 16, 3) if i < at else Span(cls="pf-dot"), cls="pf-mark"), Span(labels[k]), cls="pf-step" + (" is-done" if i < at else " is-now" if i == at else ""),
                   aria_current="step" if i == at else None) for i, k in enumerate(order)], cls="pf-steps")


def _links(order):
    """Booking links (flights, stays, things to do), only when a Travelpayouts marker is set; a flight only when the home airport and a destination airport we know are both there."""
    if not travelpayouts.marker():
        return ""
    intake, out = order["intake"], []
    for lane, (ico, label, _partner) in LANES.items():
        if lane == "flight" and not (intake["home"] and _airport(intake["where"])):
            continue
        out.append(A(icon(ico, 18, 2.2), label, href=f"{PATH}/{order['id']}/go/{lane}", rel="sponsored nofollow noopener", target="_blank", cls="btn pf-link", id=f"pf-go-{lane}"))
    return Div(H2("Book what you need"), Div(*out, cls="pf-links"), P(f"We may earn a commission if you book through these links, at no cost to you. {partners_fine()}", cls="pf-hint"), cls="pf-book", id="pf-book") if out else ""


def partners_fine() -> str:
    return "Partners keep your booking, refunds and customer service."


def _airport(where) -> str:
    """The main airport of a destination the catalog knows (Disneyland is Los Angeles), else "": no guessed code."""
    key = publish.place_key(where)
    return next((d.airports[0] for d in catalog.DESTINATIONS if d.key == key), "")


def order_page(order, paid_back=False, trouble=False):
    status, intake = order["status"], order["intake"]
    head = {"awaiting_payment": ("Almost there", "Pay to start building your trip."), "paid": ("Payment received", "An agent is about to start on your trip."),
            "building": ("Building your trip", "This takes a few minutes. You can leave this page: your trip will be in your calendar."),
            "ready": ("Your trip is ready", "It is in your family's calendar now, day by day."),
            "failed": ("We couldn't finish your trip", "We'll refund you in full. There is nothing you need to do.")}[status]
    if status == "awaiting_payment" and paid_back:
        head = ("Confirming your payment", "Stripe is telling us it went through. This takes a few seconds.")
    body = [Div(Span(f"Order {order['id'][:8]}", cls="pf-chip", id="pf-order"), H1(head[0], id="pf-title"), P(head[1], cls="pf-lede", id="pf-lede"), P(_summary(intake), cls="pf-sum", id="pf-sum"), cls="pf-top")]
    if status in ("paid", "building") or (status == "awaiting_payment" and paid_back):
        body.append(_steps("paid" if status == "awaiting_payment" else status))
    if status == "awaiting_payment" and not paid_back:
        if trouble:
            body.append(P("We could not open the payment page just now. Nothing was charged. Try again in a moment.", role="alert", cls="pf-error", id="pf-trouble"))
        body.append(Form(Button(icon("lock", 18, 2.4), f"Pay {catalog.money(order['amount_cents'])}", type="submit", cls="btn btn-primary pf-go", id="pf-pay"), action=f"{PATH}/{order['id']}/pay", method="post", cls="pf-act"))
    if status == "ready":
        body.append(Div(A(icon("calendar", 20, 2.4), "Open your trip", href=f"/trip?trip={order['trip_id']}", cls="btn btn-primary pf-go", id="pf-open"), cls="pf-act"))
        if order["sample"]:
            body.append(P("This is a sample trip: this copy of GitAway has no AI key, so the days are placeholders.", role="status", cls="pf-note", id="pf-sample"))
        body.append(_links(order))
    if status == "failed":
        body.append(P(f"Reference {order['id']}. ", legal.contact(), cls="pf-hint", id="pf-ref"))
    body.append(P(pfm.PROMISE, cls="pf-promise", id="pf-promise"))
    return page("Plan it for me", Section(*body, cls="pf ga-wrap", id="pf", data_pf_poll=f"{PATH}/{order['id']}/status" if status in ("paid", "building") or (status == "awaiting_payment" and paid_back) else None,
                                          data_status=status), head=HEAD)


# ---- the stand-in checkout (local only) -------------------------------------------------------------------------------

def standin_page(order):
    return page("Checkout (stand-in)", Section(
        Div(Span("Sandbox · stand-in for Stripe", cls="pf-chip"), H1("Pay for Plan it for me"), P(_summary(order["intake"]), cls="pf-sum"),
            P(f"This page mimics Stripe Checkout so you can click the whole loop on this machine. Nothing is charged.", cls="pf-lede"), cls="pf-top"),
        Form(Button(icon("lock", 18, 2.4), f"Pay {catalog.money(order['amount_cents'])} (simulated)", type="submit", cls="btn btn-primary pf-go", id="pf-standin-pay"),
             A("Back", href=f"{PATH}/{order['id']}", cls="pf-back"), action=f"/sandbox/plan-for-me/{order['id']}", method="post", cls="pf-act"),
        cls="pf ga-wrap", id="pf"), head=HEAD)


def register(app):
    @app.get(PATH)
    def intake(session, request):
        q = request.query_params
        return intake_page(session, {k: q.get(k, "") for k in ("from", "where", "start", "end", "home", "adults", "nkids", "budget", "pace", "must")} | {f"k{i}": q.get(f"k{i}", "") for i in range(1, MAX_KIDS + 1)})

    async def _checkout(request, order):
        """Where an unpaid order goes to be paid: the stand-in locally, else Stripe. (url, error sentence)."""
        if pfm.standin():
            return f"/sandbox/plan-for-me/{order['id']}", ""
        try:
            return await run_in_threadpool(pfm.start_checkout, order, _base(request)), ""
        except Exception:  # noqa: BLE001 - the SDK's own errors, a timeout: the log has the type, the buyer a plain sentence
            log.exception("could not open a Stripe Checkout session for order %s", order["id"])
            return "", "We could not open the payment page just now. Nothing was charged. Try again in a moment."

    @app.post(PATH)
    async def intake_post(request, session):
        if not reports.same_site(request):
            return PlainTextResponse("Not allowed", status_code=403)
        form = await request.form()
        me = ses.current_traveler(session)
        if me is None:
            return _signin(PATH)
        intake_, errors = await run_in_threadpool(pfm.read_intake, form)
        vals = {k: str(v) for k, v in form.items() if isinstance(v, str)}
        if errors:
            return intake_page(session, vals, errors, 422)
        order = await run_in_threadpool(pfm.create_order, me.id, session.get("tenant_id") or "", session.get("email") or "", intake_)
        url, _why = await _checkout(request, order)
        return RedirectResponse(url or f"{PATH}/{order['id']}?err=1", status_code=303)

    @app.get(PATH + "/{order_id}")
    def order(session, request, order_id: str):
        me = ses.current_traveler(session)
        if me is None:
            return _signin(f"{PATH}/{order_id}")
        found = _mine(session, order_id)
        if not found:
            return _gone()
        return order_page(found, paid_back=request.query_params.get("paid") == "1" and found["status"] == "awaiting_payment", trouble=request.query_params.get("err") == "1")

    @app.get(PATH + "/{order_id}/status")
    def status(session, order_id: str):
        found = _mine(session, order_id)
        return JSONResponse({"status": found["status"]}, headers={"Cache-Control": "no-store"}) if found else _gone()

    @app.post(PATH + "/{order_id}/pay")
    async def pay(request, session, order_id: str):
        if not reports.same_site(request):
            return PlainTextResponse("Not allowed", status_code=403)
        found = _mine(session, order_id)
        if not found:
            return _gone()
        if found["status"] != "awaiting_payment":
            return RedirectResponse(f"{PATH}/{order_id}", status_code=303)
        url, _why = await _checkout(request, found)
        return RedirectResponse(url or f"{PATH}/{order_id}?err=1", status_code=303)

    @app.get(PATH + "/{order_id}/go/{lane}")
    def go(session, order_id: str, lane: str):
        found = _mine(session, order_id)
        if not found or lane not in LANES or found["status"] not in ("ready",) or not travelpayouts.marker():
            return _gone()
        intake_ = found["intake"]
        start, end = date.fromisoformat(intake_["start"]), date.fromisoformat(intake_["end"])
        trip = SimpleNamespace(origin=intake_["home"], depart=start, return_=end, travelers=intake_["adults"] + len(intake_["kids"]), destination_name=intake_["where"])
        if lane == "flight" and not (intake_["home"] and _airport(intake_["where"])):
            return _gone()
        offer = SimpleNamespace(kind=lane, airport=_airport(intake_["where"]))
        return RedirectResponse(travelpayouts.link_for(partners.get(LANES[lane][2]), offer, trip, found["id"]), status_code=302)

    @app.get("/sandbox/plan-for-me/{order_id}")
    def standin_get(session, order_id: str):
        found = _mine(session, order_id)
        return standin_page(found) if found and pfm.standin() and found["status"] == "awaiting_payment" else _gone()

    @app.post("/sandbox/plan-for-me/{order_id}")
    async def standin_post(request, session, order_id: str):
        found = _mine(session, order_id)
        if not found or not pfm.standin() or not reports.same_site(request):
            return _gone()
        paid = {"id": f"standin_{found['id']}", "type": "checkout.session.completed", "data": {"object": {"id": f"standin_{found['id']}", "mode": "payment", "payment_status": "paid",
                                                                                                         "client_reference_id": found["id"], "amount_total": found["amount_cents"], "currency": "usd"}}}
        await run_in_threadpool(pfm.handle_event, paid)      # the same path a verified Stripe event takes
        return RedirectResponse(f"{PATH}/{order_id}", status_code=303)

    @app.post("/stripe/webhook")
    async def stripe_webhook(request):
        status_, answer = await run_in_threadpool(pfm.receive, await request.body(), request.headers.get("stripe-signature", ""))
        return PlainTextResponse(answer, status_code=status_)
