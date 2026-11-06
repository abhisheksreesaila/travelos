"""Partner links, the stand-in checkout and the family's partner log (autopilot M2/M3). The rules are gitaway.partners; this module is the screens.

GET  /go/<offer id>?to=&d=&r=&a=&k=         log the click, then 302: with TRAVELPAYOUTS_MARKER to the tracked https link, else to the sandbox (showcase only)
GET  /sandbox/<partner>/<click>?o=&...      a stand-in for the partner's checkout: the offer, its price, "Complete booking on <partner>"
POST /sandbox/<partner>/<click>             the simulated conversion: recorded, and added to the family's trip as "Booked elsewhere · <partner>"
GET  /sandbox/<partner>/<click>/done        says so
GET  /partners                              the family's clicks and bookings with SubID, status and price at the partner (signed in); commission is on /admin (F-185)

Writes are the editor role's like every other POST (gitaway/access.py): a viewer cannot book. Without the showcase, /sandbox is 404, /go is 404
without a marker and /partners is 404 without a token (gitaway/showcase.py).
"""

import re
from urllib.parse import parse_qsl, urlencode

from fasthtml.common import A, Button, Div, Form, H1, H2, Input, Li, Link, Main, P, Span, Title, Ul
from starlette.responses import RedirectResponse

from gitaway import affiliate, catalog, importer, partners, session as ses, showcase
from gitaway.icons import icon
from gitaway.layout import page, styles
from gitaway.partners import log, statistics, travelpayouts

HEAD = (Link(rel="stylesheet", href="/assets/css/partners.css"),)
_CLICK = re.compile(r"[0-9a-f]{10}")
FINE = "GitAway is a control plane: partners keep your booking, refunds and customer service. We may earn a commission when you book through a partner link."


def _trip_tail(trip) -> dict:
    return {"to": trip.key, **dict(parse_qsl(catalog.trip_query(trip)))}


def _offer(offer_id, d, r, a, k):
    """(offer, trip) for an offer id and the trip params, or None for an offer the catalog does not have. The offer's own place wins over any `to`."""
    try:
        place = catalog.offer_place(offer_id)
    except KeyError:
        return None
    trip = catalog.trip_from_url(d, r, a, k, place)
    return catalog.offer(offer_id, trip), trip


def _checkout(partner_key, click, o, d, r, a, k):
    """(partner, offer, trip) of a sandbox page, or None when anything in the address does not belong together (so a forged address is a 404)."""
    partner, found = partners.get(partner_key), _offer(o, d, r, a, k)
    if not partner or not _CLICK.fullmatch(click) or not found or partners.for_offer(found[0]) is not partner:
        return None
    return partner, *found


def _sandbox_path(partner, click, offer, trip, tail=""):
    return f"/sandbox/{partner.key}/{click}{tail}" if tail else f"/sandbox/{partner.key}/{click}?" + urlencode({"o": offer.id, **_trip_tail(trip)})


def _shell(title, *content):
    """A standalone full-screen document (no site header), like the pay sheet's pages."""
    return (Title(f"GitAway · {title}"), *styles(*HEAD), Main(*content, id="main", cls="pt-stage"))


def _offer_card(offer, trip):
    return Div(Span(icon({"flight": "plane", "stay": "bed", "car": "car"}[offer.kind], 22, 2.1), cls=f"pt-tile pt-k-{offer.kind}", aria_hidden="true"),
               Span(Span(offer.name, cls="pt-name"), Span(offer.headline, cls="pt-line"), Span(f"{trip.depart:%b} {trip.depart.day} – {trip.return_:%b} {trip.return_.day}"
                                                                                           f" · {trip.travelers} travelers", cls="pt-line"), cls="pt-text"),
               Span(catalog.money(offer.price_cents), cls="pt-price"), cls="pt-offer")


def checkout_page(partner, click, offer, trip, *, signed_in):
    return _shell(f"{partner.name} checkout", Div(
        Span(f"Sandbox · stand-in for {partner.name}", cls="pt-chip"),
        H1(f"Your {'hotel' if offer.kind == 'stay' else offer.kind} on {partner.name}", cls="pt-title"),
        _offer_card(offer, trip),
        P(f"This page mimics {partner.name}'s checkout so you can feel the whole loop. Nothing is charged and nothing is booked with anyone.", cls="pt-fine"),
        Form(Input(type="hidden", name="o", value=offer.id), *[Input(type="hidden", name=n, value=v) for n, v in _trip_tail(trip).items()],
             Button(f"Complete booking on {partner.name}", type="submit", cls="btn btn-ink pt-go"),
             A("Back to my plan", href="/plan?" + urlencode(_trip_tail(trip)), cls="pt-back"),
             action=f"/sandbox/{partner.key}/{click}", method="post", cls="pt-form"),
        P("" if signed_in else "You will be asked to sign in so the booking can go in your trip.", cls="pt-fine"),
        cls="pt-card"))


def done_page(row, partner, offer_name):
    return _shell("Booked elsewhere", Div(
        Span(icon("check", 28, 2.4), cls="pt-badge", aria_hidden="true"),
        H1(f"Booked elsewhere · {partner.name}", cls="pt-title", id="pt-done"),
        P(f"{offer_name} is booked on {partner.name} (sandbox). It is in your trip now, marked as booked elsewhere. {partner.name} keeps the booking; GitAway keeps a note of it.", cls="pt-lead"),
        Div(Span("Confirmation", cls="pt-k"), Span(row["confirmation"], cls="pt-v"), Span("Paid at the partner", cls="pt-k"), Span(catalog.money(row["price_cents"]), cls="pt-v"),
            cls="pt-facts"),
        Div(A("Open my trip", href="/trip", cls="btn btn-ink"), A("Partner bookings", href="/partners", cls="btn"),
            A("Keep planning", href="/plan?" + row["query"], cls="btn"), cls="pt-actions"),
        cls="pt-card"))


def _status(row):
    return ("Booked", "pt-st-booked") if row["state"] == "booked" else ("Clicked", "pt-st-clicked")


def _row(row):
    partner = partners.get(row["partner"])
    label, cls = _status(row)
    price = catalog.money(row["price_cents"]) if row["state"] == "booked" else "–"   # what the family paid the partner; what GitAway earns is on the admin page (F-185)
    return Li(Div(Span(partner.name if partner else row["partner"], cls="pt-who"), Span(label, cls=f"pt-status {cls}")),
              Span(row["offer_name"], cls="pt-what"),
              Div(Span("SubID", cls="pt-k"), Span(row["sub_id"], cls="pt-code"), Span("Price at the partner", cls="pt-k"), Span(price, cls="pt-v"),
                *([Span("Partner status", cls="pt-k"), Span(statistics.row(row)["state"], cls="pt-v")] if row["state"] == "booked" else []), cls="pt-meta"),
              cls="pt-row", data_state=row["state"])


def partners_page(rows, *, live):
    booked = [r for r in rows if r["state"] == "booked"]
    note = "Live statistics are not connected yet." if live else "Sample data: clicks and bookings made in the sandbox."
    return page("Partners", Main(
        Div(H1("Partner bookings", cls="pt-title"),
            P(f"{len(rows)} click{'s' if len(rows) != 1 else ''} · {len(booked)} booked", cls="pt-lead", id="pt-summary"),
            P(note, cls="pt-fine"), P(FINE, cls="pt-fine"),
            Ul(*[_row(r) for r in rows], cls="pt-list", aria_label="Clicks and bookings") if rows else
            Div(P("No clicks yet. Pick a flight, a stay or a car and press Book on a partner.", cls="pt-lead"), A("Plan a trip", href="/plan", cls="btn btn-ink"), cls="pt-empty"),
            cls="pt-card pt-wide"), cls="pt-stage", id="partners"), head=HEAD)


def register(app):
    @app.get("/go/{offer_id}")
    def go(request, session, offer_id: str, d: str = "", r: str = "", a: str = "", k: str = ""):
        found = _offer(offer_id, d, r, a, k)
        if not found:
            return showcase.not_found()
        offer, trip = found
        partner, click = partners.for_offer(offer), log.new_click_id()
        sub = log.record_click(session, click, offer, trip, partner)
        if travelpayouts.marker():
            via = affiliate.valid_via(request.cookies.get(affiliate.COOKIE))   # F-184: the creator whose trip this family planned from, if any
            own = affiliate.marker_for(via) if via else ""
            if via:
                affiliate.log_click(via, partner.key, offer.kind, own and partner.key == "aviasales")
            return RedirectResponse(travelpayouts.link_for(partner, offer, trip, sub, own), status_code=302)
        return RedirectResponse(_sandbox_path(partner, click, offer, trip), status_code=302)

    @app.get("/sandbox/{partner}/{click}")
    def sandbox(session, partner: str, click: str, o: str = "", d: str = "", r: str = "", a: str = "", k: str = ""):
        found = _checkout(partner, click, o, d, r, a, k)
        if not found:
            return showcase.not_found()
        return checkout_page(found[0], click, found[1], found[2], signed_in=bool(ses.current_traveler(session)))

    @app.post("/sandbox/{partner}/{click}")
    def sandbox_book(session, partner: str, click: str, o: str = "", d: str = "", r: str = "", a: str = "", k: str = ""):
        found = _checkout(partner, click, o, d, r, a, k)
        if not found:
            return showcase.not_found()
        pt, offer, trip = found
        if not ses.current_traveler(session):
            return RedirectResponse(ses.signin_href(_sandbox_path(pt, click, offer, trip)), status_code=303)
        earlier = log.get(session, click)
        if earlier and earlier["offer_id"] != offer.id:   # a click id belongs to the offer it was made for
            return showcase.not_found()
        try:
            log.book(session, click, offer, trip, pt)
        except importer.SaveError as e:
            return page("Not booked", Div(H2("We couldn't add that to your trip"), P(str(e)), A("Back to my plan", href="/plan", cls="btn btn-ink"), cls="pt-card"), head=HEAD)
        return RedirectResponse(f"/sandbox/{pt.key}/{click}/done", status_code=303)

    @app.get("/sandbox/{partner}/{click}/done")
    def sandbox_done(session, partner: str, click: str):
        pt, row = partners.get(partner), log.get(session, click) if _CLICK.fullmatch(click) else None
        if not pt or not row or row["state"] != "booked" or row["partner"] != pt.key:
            return showcase.not_found()
        return done_page(row, pt, row["offer_name"])

    @app.get("/partners")
    def partners_log(session):
        if not ses.current_traveler(session):
            return RedirectResponse(ses.signin_href("/partners"), status_code=303)
        return partners_page(log.clicks(session), live=bool(travelpayouts.token()))   # with a token the real statistics would be read here; not wired yet
