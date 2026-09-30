"""The booking workspace at /plan (F-015), with the context panes (weather, map, news, community) from F-016.

The picked flight, stay and car live in the URL (?f=&h=&c=). Every price and total is rendered from
gitaway.catalog; the JS only swaps between quotes the server embedded, it never does arithmetic.
"""

import json
from itertools import product
from urllib.parse import quote as urlquote

from fasthtml.common import A, Button, Div, Figcaption, Figure, Img, Kbd, Link, Main, NotStr, Script, Section, Span, Svg, Title

from gitaway import catalog, context, itineraries, session
from gitaway.icons import icon
from gitaway.itinerary_view import fork_href
from gitaway.layout import avatar, brand, styles

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


def pay_path(f, h, c):
    return f"/plan/pay?f={f}&h={h}&c={c}"


def book_href(f, h, c):
    """Signed in: straight to the pay sheet. Signed out: sign in first, then back to /plan with the same picks."""
    if session.request_traveler():
        return pay_path(f, h, c)
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
    maps = {o.id: context.map_for_stay(o) for o in catalog.offers("stay")}
    return {"quotes": quotes, "offers": offers, "map": maps}


def script_json(obj) -> str:
    """JSON safe inside a <script> block: every '<' becomes \\u003c."""
    return json.dumps(obj).replace("<", "\\u003c")


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


def pane(key, num, title, meta, cards, tint, *extra, cls_extra=""):
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
        cls=f"ws-pane {cls_extra}".strip(), data_pane=key, aria_label=title,
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
        A("Book this trip", href=book_href(q.flight_id, q.stay_id, q.car_id), id="ws-book", cls="btn btn-ink ws-book"),
        Button("Details", type="button", cls="ws-details-toggle", id="ws-details", aria_expanded="false", aria_controls="ws-slots"),
        cls="ws-ledger", aria_label="Cost ledger",
    )


def top_bar(trip):
    def fmt(d):
        return d.strftime("%a %b ") + str(d.day)
    who = session.request_traveler()
    return Div(
        brand(),
        A(Span(f"{trip.origin} → {trip.destination_name}", cls="ws-bold"), Span(f"{fmt(trip.depart)} – {fmt(trip.return_)}"),
          Span(trip.summary), Span("Change", cls="ws-change"), href="/", cls="ws-pill"),
        Span("Press 1–7 to focus a pane", cls="ws-hint"),
        avatar(who, "ws-avatar") if who else A("Sign in", href=session.signin_href(), cls="btn btn-sm"),
        cls="ws-bar",
    )


def _pct(v, total):
    return f"{v / total * 100:.2f}%"


def weather_pane():
    days = [
        Div(Span(w.day, cls="ws-wday"), icon(w.icon, 22, 2), Span(f"{w.temp_f}°", cls="ws-temp"), Span(w.sky, cls="ws-sky"),
            cls=f"ws-wcell fill-{w.fill}-tint")
        for w in context.WEATHER
    ]
    return pane("weather", 4, "Weather", "°F", [Div(*days, cls="ws-weather"), Span(context.SAMPLE_NOTE, cls="ws-sample")], "fill-sun-tint")


def _map_label(pt, cls, extra=None):
    w, h = context.MAP_SIZE
    return Span(pt.label, cls=f"ws-mark {cls}", style=f"left:{_pct(pt.x, w)};top:{_pct(pt.y, h)}", **(extra or {}))


def map_pane(stay):
    w, h = context.MAP_SIZE
    m = context.map_for_stay(stay)
    coast = "M0 0 H96 C110 40 80 70 104 100 S130 140 120 150 H0 Z"
    road = "M96 0 C110 40 80 70 104 100 S130 140 120 150"
    art = Svg(
        NotStr(f'<path d="{coast}" class="ws-sea"/><path d="{road}" class="ws-shore"/>'
               '<path d="M150 20 C200 50 240 40 300 70" class="ws-road"/><path d="M130 120 C190 110 230 125 310 110" class="ws-road"/>'
               f'<line id="ws-beach-line" class="ws-beach-line" x1="{m["x"]}" y1="{m["y"]}" x2="{m["bx"]}" y2="{m["by"]}"/>'),
        cls="ws-map-art", viewBox=f"0 0 {w} {h}", preserveAspectRatio="none", aria_hidden="true",
    )
    beach = Span(cls="ws-beach-dot", id="ws-beach-dot", style=f"left:{_pct(m['bx'], w)};top:{_pct(m['by'], h)}", aria_hidden="true")
    canvas = Div(
        art, beach,
        _map_label(context.LAX, "ws-mark-airport"), _map_label(context.BUR, "ws-mark-airport"),
        _map_label(context.LANDMARK, "ws-mark-landmark"),
        Span(m["label"], cls="ws-mark ws-mark-pin", id="ws-map-pin", style=f"left:{_pct(m['x'], w)};top:{_pct(m['y'], h)}",
             data_map_pin=stay.id),
        cls="ws-map",
    )
    return pane("map", 5, "Map", "Schematic", [
        canvas, Span(m["caption"], cls="ws-map-caption", id="ws-map-caption", aria_live="polite"),
        Span(f"{context.SAMPLE_NOTE}: a schematic sketch, not a real map", cls="ws-sample"),
    ], "fill-mint-tint")


def news_pane():
    events = [
        Div(Span(e.when, cls=f"ws-when fill-{e.fill}-tint"), Span(Span(e.title, cls="ws-item-title"), Span(e.sub, cls="ws-item-sub"), cls="ws-item"),
            cls="ws-event")
        for e in context.EVENTS
    ]
    news = [Div(Span(n.title, cls="ws-item-title"), Span(n.sub, cls="ws-item-sub"), cls="ws-news") for n in context.NEWS]
    return pane("news", 6, "Happening & news", "", [
        *events, Span("Local news", cls="ws-subhead"), *news, Span(context.SAMPLE_NOTE, cls="ws-sample"),
    ], "fill-bubble-tint")


def community_pane():
    rows = []
    for t in itineraries.ITINERARIES.values():
        kid = any(tag.label == "Kid friendly" for tag in t.tags)
        facts = " · ".join([f"{len(t.days)} days", *(["kid friendly"] if kid else []), f"{t.forks} forks"])
        rows.append(Div(
            Span(Span(t.title, cls="ws-item-title"), Span(facts, cls="ws-item-sub"), cls="ws-item"),
            A("Fork", href=fork_href(t), cls="ws-fork", aria_label=f"Fork {t.title}"),
            cls="ws-trip",
        ))
    return pane("community", 7, "Trips others loved", "", [
        *rows, Span("Your forked trips will be listed here soon.", cls="ws-sample"),
    ], "fill-sun", cls_extra="ws-dark")


def workspace(f, h, c, overlay=(), head=()):
    trip = catalog.SAMPLE_TRIP
    q = catalog.quote(f, h, c)
    tip = Div("Tip from 312 families: most skipped the car in Santa Monica and rented one for the Griffith Park day only.", cls="ws-tip")
    body = Main(
        top_bar(trip),
        ledger(q, trip),
        Div(
            pane("flights", 1, "Flights", f"round trip · {len(catalog.offers('flight'))}", [flight_card(o, f) for o in catalog.offers("flight")], "fill-sun-tint"),
            pane("stays", 2, "Stays", f"{trip.nights} nights", [stay_card(o, h) for o in catalog.offers("stay")], "fill-mint-tint"),
            pane("cars", 3, "Getting around", "", [car_card(o, c) for o in catalog.offers("car")], "fill-sky-tint", tip),
            Div(weather_pane(), map_pane(catalog.offer(h)), news_pane(), community_pane(), cls="ws-context"),
            cls="ws-grid", id="ws-grid", data_focus="flights",
        ),
        cls="ws", id="main", data_theme="sunset",
    )
    data = Script(NotStr(script_json(embedded_data())), id="ws-data", type="application/json")
    return (
        Title("GitAway · Plan a trip"),
        *styles(*HEAD, *head),
        A("Skip to content", href="#main", cls="ga-skip"),
        body,
        data,
        Script(src="/assets/js/workspace.js", defer=True),
        *overlay,
    )


def register(app):
    @app.get("/plan")
    def plan(f: str = "", h: str = "", c: str = ""):
        return workspace(*resolve_pick(f, h, c))
