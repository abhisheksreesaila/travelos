"""The booking workspace at /plan (F-015), with the context panes (weather, map, news, community) from F-016.

The picked flight, stay and car live in the URL (?f=&h=&c=), plus the stay's rooms and add-ons when they are not the
defaults (&rooms=ok2&add=bf, see catalog.StayPick). Every price and total is rendered from gitaway.catalog; the JS never
does arithmetic: it asks GET /plan/quote for the ledger figures of whatever is picked and swaps them in.
"""

import json
from urllib.parse import quote as urlquote

from starlette.responses import HTMLResponse

from fasthtml.common import to_xml, A, Article, Button, Div, Figcaption, Figure, H2, Img, Kbd, Link, Main, NotStr, P, Script, Section, Span, Svg, Title

from gitaway import catalog, context, itineraries, session
from gitaway.tripcal import fmt_time
from gitaway.icons import icon
from gitaway.itinerary_view import fork_href
from gitaway.layout import avatar, brand, styles
from gitaway.pages import stay_detail as stay_ui

HEAD = (Link(rel="stylesheet", href="/assets/css/workspace.css"),)
DEFAULTS = {"flight": "f1", "stay": "h1", "car": "c1"}
LANES = ("flight", "stay", "car")
TAG_FILLS = ["fill-sun", "fill-sky", "fill-mint", "fill-bubble"]
SPLIT_LANES = {"flights": "flight", "stays": "stay"}  # panes that expand into a list plus a detail panel


def resolve_pick(f, h, c):
    """The (flight, stay, car) ids to show. An unknown or wrong-lane id falls back to that lane's default."""
    picked = []
    for kind, given in zip(LANES, (f, h, c)):
        valid = {o.id for o in catalog.offers(kind)}
        picked.append(given if given in valid else DEFAULTS[kind])
    return tuple(picked)


def resolve_stay(h, rooms=None, add=None):
    """The bookable StayPick for stay `h` from URL text: bad or missing rooms, or rooms that sleep fewer than the party, become the default."""
    return catalog.stay_pick(h, rooms, add)


def plan_path(f, h, c, stay=None):
    return f"/plan?f={f}&h={h}&c={c}" + (stay.query if stay else "")


def pay_path(f, h, c, stay=None):
    return f"/plan/pay?f={f}&h={h}&c={c}" + (stay.query if stay else "")


def book_href(f, h, c, stay=None):
    """Signed in: straight to the pay sheet. Signed out: sign in first, which comes straight back to the sheet with the same picks."""
    if session.request_traveler():
        return pay_path(f, h, c, stay)
    return f"/signin?next={urlquote(pay_path(f, h, c, stay), safe='')}&intent=pay"


def delta_text(q):
    if q.above_cheapest_cents == 0:
        return "The cheapest combination"
    return f"{catalog.money(q.above_cheapest_cents)} more than the cheapest combo"


def explicit_rooms(state):
    """Rooms as spelled out in a request ("cq1" even for the default room), so "" can mean no rooms picked."""
    return "".join(f"{i}{n}" for i, n in state.rooms)


def ledger_json(q):
    """The ledger figures for quote `q`, straight from the catalog. The page swaps these in and never computes them."""
    f, h, c = q.flight_id, q.stay_id, q.car_id
    names = {"flight": q.lines[0].name, "stay": q.lines[1].name, "car": q.lines[2].name}
    subs = {"flight": "", "stay": q.stay.summary, "car": ""}
    return {
        "total": catalog.money(q.total_cents),
        "delta": delta_text(q),
        "cheapest": q.above_cheapest_cents == 0,
        "book": book_href(f, h, c, q.stay),
        "url": plan_path(f, h, c, q.stay),
        "pick": {"f": f, "h": h, "c": c, "rooms": explicit_rooms(q.stay), "add": q.stay.add_code},
        "slots": {k: {"name": names[k], "price": catalog.money(q.lane_cents(k)), "sub": subs[k]} for k in LANES},
    }


def stay_json(state):
    """One stay's editor state (rooms, add-ons, fit, summary and price) for the choose bar and the room cards."""
    return {
        "id": state.stay_id, "rooms": state.counts, "rooms_code": explicit_rooms(state), "add": list(state.addons), "add_code": state.add_code,
        "summary": state.summary, "price": catalog.money(state.cents), "fits": state.fits, "fit": state.fit, "fit_text": state.fit_text,
    }


def embedded_data(f, h, c, stay):
    """What the page needs at load: each offer's display strings, the map points, and the current pick."""
    offers = {o.id: {"name": o.name, "price": catalog.money(o.price_cents)} for k in LANES for o in catalog.offers(k)}
    maps = {o.id: context.map_for_stay(o) for o in catalog.offers("stay")}
    return {"offers": offers, "map": maps, "pick": {"f": f, "h": h, "c": c, "rooms": explicit_rooms(stay), "add": stay.add_code},
            "base": plan_path(f, h, c, stay)}


def script_json(obj) -> str:
    """JSON safe inside a <script> block: every '<' becomes \\u003c."""
    return json.dumps(obj).replace("<", "\\u003c")


def _offer_attrs(o, picked, viewing=""):
    attrs = dict(type="button", aria_pressed="true" if o.id == picked else "false", data_lane=o.kind, data_pick=o.id)
    if viewing and o.id == viewing:
        attrs["aria_current"] = "true"
    return attrs


def pick_pill():
    return Span("Your pick", cls="ws-pickpill")


def flight_card(o, picked, viewing=""):
    return Button(
        Span(Span(o.name, cls="ws-name"), *[Span(b, cls="ws-badge fill-sun") for b in o.badges],
             pick_pill(), Span(catalog.money(o.price_cents), cls="ws-price"), cls="ws-row"),
        Span(o.headline, cls="ws-times"),
        Span(o.detail, cls="ws-detail"),
        Span(f"Lands {o.airport}", cls="ws-badge fill-sky-tint ws-airport"),
        cls="ws-offer ws-offer-flight", **_offer_attrs(o, picked, viewing),
    )


def stay_card(o, picked, viewing="", cents=None):
    """`cents`: the price to show (the picked stay shows its rooms and add-ons); default is the stay's list price."""
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
            Span(Span(catalog.money(o.price_cents if cents is None else cents), cls="ws-price-big", data_stay_price=o.id), Span(o.rating, cls="ws-rating"),
                 pick_pill(), cls="ws-foot"),
            cls="ws-stay-body",
        ),
        cls="ws-offer ws-offer-stay", **_offer_attrs(o, picked, viewing),
    )


def car_card(o, picked):
    return Button(
        Span(o.name, cls="ws-name"),
        Span(f"{o.headline} · {o.detail}", cls="ws-detail"),
        Span(catalog.money(o.price_cents), cls="ws-price-big"),
        cls="ws-offer ws-offer-car", **_offer_attrs(o, picked),
    )


def pane(key, num, title, meta, cards, tint, *extra, cls_extra="", detail=None, expanded=False, screen="list"):
    """One workspace pane. `detail` (flights and stays) is the list of detail articles shown beside the cards when expanded."""
    attrs = dict(data_screen=screen) if detail else {}
    return Section(
        Div(
            Kbd(str(num), cls=f"ws-key {tint}", aria_hidden="true"),
            Button(title, type="button", cls="ws-focus", data_focus=key, aria_pressed="false", aria_keyshortcuts=str(num)),
            Span(meta, cls="ws-meta") if meta else "",
            Span(Kbd("Esc"), " back to workspace", cls="ws-esc", aria_hidden="true") if detail else "",
            Button(icon("expand", 16, 2.4), icon("collapse", 16, 2.4), type="button", cls="ws-expand", data_expand=key,
                   aria_label=f"{'Collapse' if expanded else 'Expand'} {title.lower()} pane", data_title=title.lower(),
                   aria_expanded="true" if expanded else "false", **(dict(aria_keyshortcuts="Escape") if detail else {})),
            cls="ws-pane-head",
        ),
        Div(*cards, cls="ws-cards"),
        Div(*detail, cls="ws-dcol") if detail else "",
        *extra,
        cls=f"ws-pane {'ws-split' if detail else ''} {cls_extra}".strip(), data_pane=key, aria_label=title, **attrs,
    )


def duration_text(minutes):
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m" if h and m else (f"{h}h" if h else f"{m}m")


def _date_text(d):
    return d.strftime("%a %b ") + str(d.day)


def choose_bar(o, picked, noun, summary, cents=None, chosen=None, disabled=False):
    """The pinned ink bar. `cents` is the price shown (a stay shows its rooms and add-ons); `chosen` overrides "is this the lane's pick"."""
    on = (o.id == picked) if chosen is None else chosen
    return Div(
        Span(Span(o.name, cls="ws-cb-name"), Span(summary, cls="ws-cb-sum", data_cb_sum=""),
             Span("Price didn't load, try again", cls="ws-cb-err", data_cb_err="", role="status", aria_live="polite", hidden=True), cls="ws-cb-text"),
        Span(catalog.money(o.price_cents if cents is None else cents), cls="ws-cb-price", data_cb_price=""),
        Button("Chosen" if on else f"Choose this {noun}", type="button", cls="ws-choose", data_choose=o.id,
               data_choose_lane=o.kind, data_label=f"Choose this {noun}", disabled=disabled),
        cls="ws-choosebar",
    )


def _article(o, picked, viewing, body, bar):
    return Article(Div(*body, cls="ws-dscroll"), bar, cls="ws-detail-panel", data_detail=o.id, aria_label=o.name,
                   **({} if o.id == viewing else {"hidden": True}))


def stay_detail(o, picked, viewing, state, back_label="Stays", chosen=False):
    """One stay's detail panel. `state` is the StayPick shown in its editor (the pick itself for the picked stay, else the default);
    `chosen` says the editor holds the lane's pick."""
    area = f"The area · {o.headline}"
    back = Button(icon("chev-left", 18, 2.4), back_label, type="button", cls="ws-back", data_back="list",
                  aria_label=f"Back to all {back_label.lower()}")
    if o.area_photo:
        photo = Figure(Img(src=f"/assets/photos/{o.area_photo}", alt=f"{o.headline}, the neighbourhood (not the hotel)", loading="lazy"),
                       Figcaption(area), back, cls="ws-hero")
    else:
        photo = Figure(Span(icon("pin", 40), aria_hidden="true"), Figcaption(area), back, cls="ws-hero ws-hero-blank")
    body = [photo, *stay_ui.body(o, state)]
    bar = choose_bar(o, picked, "stay", state.summary, cents=state.cents, chosen=chosen, disabled=not state.fits)
    art = _article(o, picked, viewing, body, bar)
    art.attrs.update({"data-rooms": explicit_rooms(state), "data-add": state.add_code})
    return art


def _leg(label, date_text, dep, arr, origin, dest, minutes):
    return Div(
        Span(f"{label} · {date_text}", cls="ws-leg-label"),
        Div(
            Span(Span(fmt_time(dep), cls="ws-leg-time"), Span(origin, cls="ws-leg-apt"), cls="ws-leg-end"),
            Span(Span(duration_text(minutes), cls="ws-leg-dur"), Span(cls="ws-leg-line"), cls="ws-leg-mid", aria_hidden="true"),
            Span(Span(fmt_time(arr), cls="ws-leg-time"), Span(dest, cls="ws-leg-apt"), cls="ws-leg-end"),
            cls="ws-leg-row",
        ),
        cls="ws-leg",
    )


def flight_detail(o, picked, viewing):
    trip = catalog.SAMPLE_TRIP
    body = [
        Div(
            Button(icon("chev-left", 18, 2.4), "Flights", type="button", cls="ws-back ws-back-flat", data_back="list",
                           aria_label="Back to all flights"),
            cls="ws-fback",
        ),
        Div(H2(o.name, cls="ws-dtitle"), *[Span(b, cls="ws-sticker fill-sun") for b in o.badges], cls="ws-dhead ws-dhead-flight"),
        Div(
            _leg("Out", _date_text(trip.depart), o.depart_min, o.arrive_min, trip.origin, o.airport, o.arrive_min - o.depart_min),
            _leg("Back", _date_text(trip.return_), o.back_depart_min, o.back_arrive_min, o.airport, trip.origin,
                 o.back_arrive_min - o.back_depart_min),
            cls="ws-legs",
        ),
        P(o.detail, cls="ws-dlead"),
        Div(data_seam="fares", cls="ws-seam"),  # F-027: fare types
        Div(data_seam="bags", cls="ws-seam"),  # F-027: checked bags
    ]
    return _article(o, picked, viewing, body, choose_bar(o, picked, "flight", o.detail))


LEDGER_LANES = [("FLIGHT", "plane", "fill-sun-tint", "flight", "+"), ("STAY", "bed", "fill-mint-tint", "stay", "+"),
                ("GETTING AROUND", "car", "fill-sky-tint", "car", "=")]


def ledger(q, trip):
    """The slim ledger line for the top bar (F-031): flight · stay · car = total, plus Book. Tapping the total opens the popover
    with the itemized lines and the best-value hint. Every figure is rendered from the catalog; the JS swaps in /plan/quote's."""
    figures = ledger_json(q)["slots"]  # the same strings GET /plan/quote sends
    line = []
    for label, ic, fill, lane, op in LEDGER_LANES:
        line.append(Span(icon(ic, 16, 2.2), Span(label.title(), cls="sr-only"), Span(figures[lane]["price"], data_line_price=lane),
                         cls="ws-line-item", title=figures[lane]["name"]))
        line.append(Span(op, cls="ws-op", aria_hidden="true"))
    slot_els = [
        Div(
            Span(icon(ic, 22, 2.1), cls=f"ws-tile {fill}"),
            Span(Span(label, cls="ws-slot-label"), Span(figures[lane]["name"], cls="ws-slot-name", data_slot=lane),
                 Span(figures[lane]["sub"], cls="ws-slot-sub", data_slot_sub=lane), cls="ws-slot-text"),
            Span(figures[lane]["price"], cls="ws-slot-price", data_slot_price=lane), cls="ws-slot",
        )
        for label, ic, fill, lane, op in LEDGER_LANES
    ]
    pop = Div(
        Div(*slot_els, cls="ws-slots", id="ws-slots"),
        Span(f"{trip.travelers} people · taxes & fees in", cls="ws-total-note"),
        Span(delta_text(q), cls=f"ws-chip {'fill-mint' if q.above_cheapest_cents == 0 else 'fill-sun-tint'}", id="ws-delta", aria_live="polite"),
        cls="ws-pop", id="ws-pop", role="dialog", aria_label="Cost breakdown", tabindex="-1", hidden=True,
    )
    return Section(
        Span(*line, cls="ws-lines"),
        Button(catalog.money(q.total_cents), type="button", id="ws-total", cls="ws-total", aria_expanded="false", aria_controls="ws-pop",
               aria_haspopup="dialog", title="Cost breakdown"),
        A("Book", href=book_href(q.flight_id, q.stay_id, q.car_id, q.stay), id="ws-book", cls="btn btn-ink ws-book", aria_label="Book this trip"),
        pop,
        cls="ws-ledger", aria_label="Cost ledger",
    )


def top_bar(trip, ledger_el=None):
    def fmt(d):
        return d.strftime("%a %b ") + str(d.day)
    who = session.request_traveler()
    return Div(
        brand(),
        A(Span(f"{trip.origin} → {trip.destination_name}", cls="ws-bold"), Span(f"{fmt(trip.depart)} – {fmt(trip.return_)}"),
          Span(trip.summary), Span("Change", cls="ws-change"), href="/", cls="ws-pill"),
        ledger_el or "",
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


def resolve_view(x, v, f, h):
    """(expanded pane key or '', {lane pane key: offer id being viewed}, screen). Only flights and stays split; a bad x or v is ignored."""
    picks = {"flights": f, "stays": h}
    expanded = x if x in SPLIT_LANES else ""
    viewing = dict(picks)
    screen = "list"
    if expanded and v in {o.id for o in catalog.offers(SPLIT_LANES[expanded])}:
        viewing[expanded] = v
        screen = "detail"
    return expanded, viewing, screen


def workspace(f, h, c, overlay=(), head=(), x="", v="", stay=None):
    trip = catalog.SAMPLE_TRIP
    expanded, viewing, screen = resolve_view(x, v, f, h)
    flights, stays = catalog.offers("flight"), catalog.offers("stay")
    stay = stay if stay is not None and stay.stay_id == h else catalog.stay_pick(h)
    q = catalog.quote(f, h, c, stay)
    tip = Div("Tip from 312 families: most skipped the car in Santa Monica and rented one for the Griffith Park day only.", cls="ws-tip")
    body = Main(
        top_bar(trip, ledger(q, trip)),
        Div(
            pane("flights", 1, "Flights", f"round trip · {len(flights)}",
                 [flight_card(o, f, viewing["flights"] if expanded == "flights" else "") for o in flights], "fill-sun-tint",
                 detail=[flight_detail(o, f, viewing["flights"]) for o in flights], expanded=expanded == "flights",
                 screen=screen if expanded == "flights" else "list"),
            pane("stays", 2, "Stays", f"{trip.nights} nights",
                 [stay_card(o, h, viewing["stays"] if expanded == "stays" else "", stay.cents if o.id == h else None) for o in stays], "fill-mint-tint",
                 detail=[stay_detail(o, h, viewing["stays"], stay if o.id == h else catalog.stay_pick(o.id), chosen=o.id == h) for o in stays], expanded=expanded == "stays",
                 screen=screen if expanded == "stays" else "list"),
            pane("cars", 3, "Getting around", "", [car_card(o, c) for o in catalog.offers("car")], "fill-sky-tint", tip),
            Div(weather_pane(), map_pane(catalog.offer(h)), news_pane(), community_pane(), cls="ws-context"),
            cls="ws-grid", id="ws-grid", data_focus=expanded or "flights", **(dict(data_expanded=expanded) if expanded else {}),
        ),
        cls="ws", id="main", data_theme="sunset",
    )
    data = Script(NotStr(script_json(embedded_data(f, h, c, stay))), id="ws-data", type="application/json")
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
    def plan(f: str = "", h: str = "", c: str = "", x: str = "", v: str = "", rooms: str = None, add: str = None):
        picks = resolve_pick(f, h, c)
        return workspace(*picks, x=x, v=v, stay=resolve_stay(picks[1], rooms, add))

    @app.get("/plan/quote")
    def plan_quote(f: str = "", h: str = "", c: str = "", rooms: str = None, add: str = None):
        """The ledger figures for a pick, and the stay editor's state for the rooms as asked (even if they sleep too few).

        "ledger" prices what can really be booked: for a short pick (rooms that sleep fewer than the party) that is the default
        room plus the asked add-ons. "stay" describes the rooms as asked, so the choose bar can say "Sleeps 2 of 4 · add a room".
        """
        picks = resolve_pick(f, h, c)
        asked = catalog.parse_stay(picks[1], rooms, add)
        real = asked if asked.fits else catalog.stay_pick(picks[1], None, asked.add_code)
        return {"ledger": ledger_json(catalog.quote(*picks, real)), "stay": stay_json(asked)}

    @app.get("/plan/explore")
    def plan_explore(h: str = ""):
        """The 3D area explorer for a stay, fetched the first time its tab opens."""
        return HTMLResponse(to_xml(stay_ui.explore(resolve_pick("", h, "")[1])))
