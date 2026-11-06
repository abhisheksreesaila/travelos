"""The honest booking page (F-195): what /plan shows a reader who came from a creator's trip, off the showcase.

The workspace behind /plan is an invented catalog (airlines, hotels and prices that do not exist, labelled "Preview: sample prices"), so a creator's reader who followed
"Plan this trip" landed on things that cannot be booked. This page has no offers of its own: one card per lane (flights on Aviasales, stays on Klook, tickets and things to do
on Klook), each a search at the partner for this place, these dates and this party, where the partner shows today's real prices. The reader can say where they fly from;
without it the flight link leaves the origin out and Aviasales asks. It is drawn by `plan.py`'s route, not registered on its own.
"""

from dataclasses import replace

from fasthtml.common import A, Button, Div, Form, H1, H2, Input, Label, Link, Main, P, Section, Span

from gitaway import catalog, partners
from gitaway.icons import icon
from gitaway.layout import page

HEAD = (Link(rel="stylesheet", href="/assets/css/plansearch.css"),)
ICONS = {"flight": "plane", "stay": "bed", "todo": "ticket"}
GO_LABELS = {"flight": "Search on Aviasales", "stay": "Find stays on Klook"}
FINE = "Links open our partners. They keep your booking; we may earn a commission."


def ahead(trip):
    """`trip` with its dates moved to the next ones worth searching, the same length, when they have passed (a stale link, or a bare /plan with the sample's old dates): a search for the past books nothing."""
    if trip.depart >= catalog.today():
        return trip
    from gitaway import publish  # here, not at the top: publish reads the community database
    depart, ret = publish.sample_dates(trip.nights + 1)
    return replace(trip, depart=depart, return_=ret)


def _go_label(offer, trip):
    return GO_LABELS.get(offer.kind) or ("See tickets on Klook" if trip.focus == "disney" else "See things to do on Klook")


def _airport(trip, via, raw, error):
    """Where the reader flies from: one small GET form back to this page. Empty means Aviasales asks."""
    keep = {"to": trip.key, "d": trip.depart.isoformat(), "r": trip.return_.isoformat(), "a": trip.adults,
            **({"k": ",".join(map(str, trip.kid_ages))} if trip.kid_ages else {}), **({"focus": trip.focus} if trip.focus else {}), **({"via": via} if via else {})}
    return Form(
        *[Input(type="hidden", name=n, value=str(v)) for n, v in keep.items()],
        Label(Span("Flying from", cls="ps-label"),
              Input(name="home", value=raw or trip.home, type="text", maxlength="3", placeholder="Any, Aviasales asks", autocomplete="off", autocapitalize="characters", spellcheck="false",
                    **({"aria_invalid": "true", "aria_describedby": "ps-err"} if error else {})),
              cls="ps-field"),
        Button("Update", type="submit", cls="btn btn-sm"),
        Span(error, id="ps-err", role="alert", cls="ps-error") if error else "",
        action="/plan", method="get", cls="ps-from")


def _card(offer, trip, live, *extra):
    blurb = {"flight": f"Aviasales shows today's fares for {trip.date_label}, {trip.summary}.",
             "stay": f"Klook lists hotels for {trip.date_label} and keeps your booking.",
             "todo": "Klook sells the tickets and keeps your booking."}[offer.kind]
    go = A(icon(ICONS[offer.kind], 20, 2.2), _go_label(offer, trip), href=partners.go_href(offer, trip), cls="btn btn-ink ps-go", rel="sponsored noopener", data_lane=offer.kind) if live else ""
    return Section(Span(icon(ICONS[offer.kind], 26, 2.1), cls=f"ps-tile ps-k-{offer.kind}", aria_hidden="true"),
                   Div(H2(offer.name, cls="ps-name"), P(offer.headline, cls="ps-what") if offer.headline else "", P(blurb, cls="ps-blurb"), *extra, go, cls="ps-text"),
                   cls=f"ps-card ps-{offer.kind}", aria_label=offer.name)


def search_page(trip, via="", home_raw="", error=""):
    """The honest page for `trip`. `via` is the creator handle to keep on the airport form; `home_raw` and `error` are a mistyped airport code and what is wrong with it."""
    trip = ahead(trip)
    live = partners.available()
    flight, stay, todo = (catalog.search_offer(k, trip) for k in ("flight", "stay", "todo"))
    query = catalog.trip_query(trip)
    return page("Plan this trip", Main(
        Div(Span("PLAN THIS TRIP", cls="eyebrow"), H1(f"Book your trip to {trip.destination_name}", cls="ps-title"),
            P(f"{trip.date_label} · {trip.summary}" + (f" · flying from {trip.home}" if trip.home else ""), cls="ps-lede", id="ps-lede"),
            P("The dates are a starting guess. We show no prices of our own: the partners show today's.", cls="ps-fine"),
            A("Change dates or who is coming", href="/start" + (f"?{query}" if query else ""), cls="btn btn-sm ps-change"),
            Div(_card(flight, trip, live, _airport(trip, via, home_raw, error)), _card(stay, trip, live), _card(todo, trip, live), cls="ps-cards"),
            P(FINE if live else "Booking links are not switched on yet.", cls="ps-fine", id="ps-fine"),
            cls="ps ga-wrap"), id="plan-search"), head=HEAD)
