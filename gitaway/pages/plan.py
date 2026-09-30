"""The booking workspace at /plan (F-015). Context panes (weather, map, news) arrive with F-016.

The picked flight, stay and car live in the URL (?f=&h=&c=). Every price and total is rendered from
gitaway.catalog; the JS only swaps between quotes the server embedded, it never does arithmetic.
"""

import json
from itertools import product
from urllib.parse import quote as urlquote

from fasthtml.common import A, Button, Div, Figcaption, Figure, Img, Kbd, Link, NotStr, Script, Section, Span, Title

from gitaway import catalog
from gitaway.icons import icon
from gitaway.layout import brand

HEAD = (Link(rel="stylesheet", href="/assets/css/workspace.css"),)
DEFAULTS = {"flight": "f1", "stay": "h1", "car": "c1"}
LANES = ("flight", "stay", "car")
TAG_FILLS = ["fill-sun", "fill-sky", "fill-mint", "fill-bubble"]


def resolve_pick(f, h, c):
    """The (flight, stay, car) ids to show. An unknown or wrong-lane id falls back to that lane's default."""
    picked = []
    for kind, given in zip(LANES, (f, h, c)):
        valid = {o.id for o in catalog.offers(kind)}
        picked.append(given if given in valid else DEFAULTS[kind])
    return tuple(picked)


def plan_path(f, h, c):
    return f"/plan?f={f}&h={h}&c={c}"


def book_href(f, h, c):
    return f"/signin?next={urlquote(plan_path(f, h, c), safe='')}&intent=pay"


def delta_text(q):
    if q.above_cheapest_cents == 0:
        return "The cheapest combination"
    return f"{catalog.money(q.above_cheapest_cents)} more than the cheapest combo"


def embedded_data():
    """Every combination's ledger figures, computed by catalog.quote, plus each offer's display strings."""
    quotes = {}
    for f, h, c in product(*(catalog.offers(k) for k in LANES)):
        q = catalog.quote(f.id, h.id, c.id)
        quotes[f"{f.id}|{h.id}|{c.id}"] = {
            "total": catalog.money(q.total_cents),
            "delta": delta_text(q),
            "cheapest": q.above_cheapest_cents == 0,
            "book": book_href(f.id, h.id, c.id),
            "url": plan_path(f.id, h.id, c.id),
        }
    offers = {o.id: {"name": o.name, "price": catalog.money(o.price_cents)} for k in LANES for o in catalog.offers(k)}
    return {"quotes": quotes, "offers": offers}


def _offer_attrs(o, picked):
    return dict(type="button", aria_pressed="true" if o.id == picked else "false", data_lane=o.kind, data_pick=o.id)


def flight_card(o, picked):
    return Button(
        Span(Span(o.name, cls="ws-name"), *[Span(b, cls="ws-badge fill-sun") for b in o.badges],
             Span(catalog.money(o.price_cents), cls="ws-price"), cls="ws-row"),
        Span(o.headline, cls="ws-times"),
        Span(o.detail, cls="ws-detail"),
        Span(f"Lands {o.airport}", cls="ws-badge fill-sky-tint ws-airport"),
        cls="ws-offer ws-offer-flight", **_offer_attrs(o, picked),
    )


def stay_card(o, picked):
    caption = f"{o.headline} area"
    if o.area_photo:
        photo = Figure(Img(src=f"/assets/photos/{o.area_photo}", alt=caption, loading="lazy", width="104", height="118"),
                       Figcaption(caption), cls="ws-photo")
    else:
        photo = Figure(Span(icon("pin", 26), aria_hidden="true"), Figcaption(caption), cls="ws-photo ws-photo-blank")
    return Button(
        photo,
        Span(
            Span(o.name, cls="ws-name"),
            Span(f"{o.headline} · {o.detail}", cls="ws-detail"),
            Span(*[Span(t, cls=f"ws-badge {TAG_FILLS[i % 4]}") for i, t in enumerate(o.tags)], cls="ws-tags"),
            Span(Span(catalog.money(o.price_cents), cls="ws-price-big"), Span(o.rating, cls="ws-rating"), cls="ws-foot"),
            cls="ws-stay-body",
        ),
        cls="ws-offer ws-offer-stay", **_offer_attrs(o, picked),
    )


def car_card(o, picked):
    return Button(
        Span(o.name, cls="ws-name"),
        Span(f"{o.headline} · {o.detail}", cls="ws-detail"),
        Span(catalog.money(o.price_cents), cls="ws-price-big"),
        cls="ws-offer ws-offer-car", **_offer_attrs(o, picked),
    )


def pane(key, num, title, meta, cards, tint, *extra):
    return Section(
        Div(
            Kbd(str(num), cls=f"ws-key {tint}", aria_hidden="true"),
            Button(title, type="button", cls="ws-focus", data_focus=key, aria_pressed="false", aria_keyshortcuts=str(num)),
            Span(meta, cls="ws-meta") if meta else "",
            Button(icon("expand", 16, 2.4), type="button", cls="ws-expand", data_expand=key,
                   aria_label=f"Expand {title.lower()} pane", aria_expanded="false"),
            cls="ws-pane-head",
        ),
        Div(*cards, cls="ws-cards"),
        *extra,
        cls="ws-pane", data_pane=key, aria_label=title,
    )


def ledger(q, trip):
    slots = [("FLIGHT", "plane", "fill-sun-tint", q.lines[0], "+"), ("STAY", "bed", "fill-mint-tint", q.lines[1], "+"),
             ("GETTING AROUND", "car", "fill-sky-tint", q.lines[2], "=")]
    slot_els = [
        Div(
            Span(icon(ic, 26, 2.1), cls=f"ws-tile {fill}"),
            Span(Span(label, cls="ws-slot-label"), Span(o.name, cls="ws-slot-name", data_slot=o.kind),
                 Span(catalog.money(o.price_cents), cls="ws-slot-price", data_slot_price=o.kind), cls="ws-slot-text"),
            Span(op, cls="ws-op", aria_hidden="true"), cls="ws-slot",
        )
        for label, ic, fill, o, op in slots
    ]
    return Section(
        Div(*slot_els, cls="ws-slots", id="ws-slots"),
        Div(
            Span(catalog.money(q.total_cents), cls="ws-total", id="ws-total"),
            Span(f"{trip.travelers} people · taxes & fees in", cls="ws-total-note"),
            Span(delta_text(q), cls=f"ws-chip {'fill-mint' if q.above_cheapest_cents == 0 else 'fill-sun-tint'}", id="ws-delta"),
            cls="ws-total-box", aria_live="polite",
        ),
        A("Book this trip", href=book_href(q.flight_id, q.stay_id, q.car_id), id="ws-book", cls="ws-book"),
        Button("Details", type="button", cls="ws-details-toggle", id="ws-details", aria_expanded="false", aria_controls="ws-slots"),
        cls="ws-ledger", aria_label="Cost ledger",
    )


def top_bar(trip):
    def fmt(d):
        return d.strftime("%a %b ") + str(d.day)
    return Div(
        brand(),
        A(Span(f"{trip.origin} → {trip.destination_name}", cls="ws-bold"), Span(f"{fmt(trip.depart)} – {fmt(trip.return_)}"),
          Span(trip.summary), Span("Change", cls="ws-change"), href="/", cls="ws-pill"),
        Span("Press 1–3 to focus a pane", cls="ws-hint"),
        Span("AR", cls="ws-avatar", aria_hidden="true"),
        cls="ws-bar",
    )


def context_placeholder():
    return Section(
        Span("Weather, a map, local news and trips others loved will sit here soon.", cls="ws-quiet"),
        cls="ws-pane ws-context", data_pane="context", aria_label="More context",
    )


def workspace(f, h, c):
    trip = catalog.SAMPLE_TRIP
    q = catalog.quote(f, h, c)
    tip = Div("Tip from 312 families: most skipped the car in Santa Monica and rented one for the Griffith Park day only.", cls="ws-tip")
    body = Div(
        top_bar(trip),
        ledger(q, trip),
        Div(
            pane("flights", 1, "Flights", f"round trip · {len(catalog.offers('flight'))}", [flight_card(o, f) for o in catalog.offers("flight")], "fill-sun-tint"),
            pane("stays", 2, "Stays", f"{trip.nights} nights", [stay_card(o, h) for o in catalog.offers("stay")], "fill-mint-tint"),
            pane("cars", 3, "Getting around", "", [car_card(o, c) for o in catalog.offers("car")], "fill-sky-tint", tip),
            context_placeholder(),
            cls="ws-grid", id="ws-grid", data_focus="flights",
        ),
        cls="ws", id="main", data_theme="sunset",
    )
    data = Script(NotStr(json.dumps(embedded_data()).replace("</", "<\\/")), id="ws-data", type="application/json")
    return (
        Title("GitAway · Plan a trip"),
        *HEAD,
        A("Skip to content", href="#main", cls="ga-skip"),
        body,
        data,
        Script(src="/assets/js/workspace.js", defer=True),
    )


def register(app):
    @app.get("/plan")
    def plan(f: str = "", h: str = "", c: str = ""):
        return workspace(*resolve_pick(f, h, c))
