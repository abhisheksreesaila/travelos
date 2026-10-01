"""The booking workspace at /plan (F-015), with the context panes (weather, map, news, community) from F-016.

The picked flight, stay and car live in the URL (?f=&h=&c=; "none" skips a lane, see SKIP), plus the stay's rooms and add-ons when they are not the
defaults (&rooms=ok2&add=bf, see catalog.StayPick) and the flight's fare and checked bags (&fare=main&bags=2, see catalog.FlightPick). Every price and total is rendered from gitaway.catalog; the JS never
does arithmetic: it asks GET /plan/quote for the ledger figures of whatever is picked and swaps them in.
"""

import json
from urllib.parse import quote as urlquote

from starlette.responses import HTMLResponse

from fasthtml.common import to_xml, A, Article, Button, Div, Figcaption, Figure, H2, H3, Img, Kbd, Li, Link, Main, NotStr, P, Script, Section, Span, Svg, Title, Ul

from gitaway import catalog, context, itineraries, session
from gitaway import session as session_helpers
from gitaway.icons import icon
from gitaway.itinerary_view import fork_href
from gitaway.layout import avatar, brand, styles
from gitaway.pages import flight_detail as flight_ui, stay_detail as stay_ui

HEAD = (Link(rel="stylesheet", href="/assets/css/workspace.css"),)
DEFAULTS = {"flight": "f1", "stay": "h1", "car": "c1"}
LANES = ("flight", "stay", "car")
TAG_FILLS = ["fill-sun", "fill-sky", "fill-mint", "fill-bubble"]
SPLIT_LANES = {"flights": "flight", "stays": "stay"}  # panes that expand into a list plus a detail panel
SKIP = "none"  # f=none, h=none or c=none: the traveler skips that lane (F-033)
LEGACY_NO_CAR = "c3"  # the old "No car" offer; it is the car skip now
PANE_OF = {"flight": "flights", "stay": "stays", "car": "cars"}
# What each lane's skip says: the button label and its small line, the slim row's text, what undo brings back.
SKIPS = {
    "flight": {"label": "I'll drive", "sub": "No flight needed", "note": "You're driving there. No flight needed.", "undo": "Add a flight", "icon": "car"},
    "stay": {"label": "Staying with friends", "sub": "No hotel needed", "note": "Staying with friends. No hotel needed.", "undo": "Add a stay", "icon": "users"},
    "car": {"label": "No car", "sub": "We'll estimate Uber and Lyft rides", "note": "No car. We'll estimate Uber and Lyft rides instead.", "undo": "Add a car", "icon": "car"},
}
NO_STAY_MAP = "Staying with friends: no hotel pin."


def resolve_pick(f, h, c):
    """The (flight, stay, car) ids to show; None for a lane that is skipped ("none", and the old car "c3").

    An unknown or wrong-lane id falls back to that lane's default, so a bad link never skips anything.
    """
    picked = []
    for kind, given in zip(LANES, (f, h, c)):
        valid = {o.id for o in catalog.offers(kind)}
        if given == SKIP or (kind == "car" and given == LEGACY_NO_CAR):
            picked.append(None)
        else:
            picked.append(given if given in valid else DEFAULTS[kind])
    return tuple(picked)


def resolve_trip(d="", r="", a="", k=""):
    """The trip the URL names (d, r, a, k: see catalog.trip_query). Nothing or anything bad means the sample trip."""
    return catalog.trip_from_url(d, r, a, k)


def resolve_stay(h, rooms=None, add=None, trip=catalog.SAMPLE_TRIP):
    """The bookable StayPick for stay `h` from URL text: bad or missing rooms, or rooms that sleep fewer than the party, become the default.
    None when the stay is skipped."""
    return catalog.stay_pick(h, rooms, add, trip) if h else None


def resolve_flight(f, fare=None, bags=None, trip=catalog.SAMPLE_TRIP):
    """The FlightPick for flight `f` from URL text: a bad fare means Basic and bad bags mean none. None when the flight is skipped."""
    return catalog.flight_pick(f, fare, bags, trip) if f else None


def trip_tail(trip):
    """The trip's URL params as a "&d=...&r=..." tail ("" for the sample trip, whose URLs stay clean)."""
    q = catalog.trip_query(trip)
    return f"&{q}" if q else ""


def _tail(stay, trip, flight=None):
    """The URL params beyond f, h and c: the stay's rooms and add-ons, the flight's fare and bags, then the trip."""
    return (stay.query if stay else "") + (flight.query if flight else "") + trip_tail(trip or (stay.trip if stay else flight.trip if flight else catalog.SAMPLE_TRIP))


def lane_id(picked):
    """A lane's id as the URL spells it: "none" for a skipped lane."""
    return picked or SKIP


def plan_path(f, h, c, stay=None, trip=None, flight=None):
    return f"/plan?f={lane_id(f)}&h={lane_id(h)}&c={lane_id(c)}" + _tail(stay, trip, flight)


def pay_path(f, h, c, stay=None, trip=None, flight=None):
    return f"/plan/pay?f={lane_id(f)}&h={lane_id(h)}&c={lane_id(c)}" + _tail(stay, trip, flight)


def book_href(f, h, c, stay=None, trip=None, flight=None):
    """Signed in: straight to the pay sheet. Signed out: sign in first, which comes straight back to the sheet with the same picks."""
    if session.request_traveler():
        return pay_path(f, h, c, stay, trip, flight)
    return f"/signin?next={urlquote(pay_path(f, h, c, stay, trip, flight), safe='')}&intent=pay"


def delta_text(q):
    if q.empty:
        return "Pick a flight, a stay or a car"
    if q.above_cheapest_cents == 0:
        return "The cheapest combination"
    return f"{catalog.money(q.above_cheapest_cents)} more than the cheapest combo"


def explicit_rooms(state):
    """Rooms as spelled out in a request ("cq1" even for the default room), so "" can mean no rooms picked."""
    return "".join(f"{i}{n}" for i, n in state.rooms)


def slot_figures(q):
    """The ledger's lines in order, one per lane that is picked, plus the rides estimate: [(lane, name, price, sub)].

    A skipped lane has no line at all, so there is never an empty or $0 one.
    """
    out = []
    names = {"flight": q.lines[0].name if q.lines[0] else "", "stay": q.lines[1].name if q.lines[1] else "", "car": q.lines[2].name if q.lines[2] else ""}
    subs = {"flight": "" if not q.flight or q.flight.is_default else q.flight.summary, "stay": q.stay.summary if q.stay else "", "car": ""}
    for lane in LANES:
        if q.lines[LANES.index(lane)] is not None:
            out.append((lane, names[lane], catalog.money(q.lane_cents(lane)), subs[lane]))
    if q.rides:
        out.append(("rides", q.rides.title, catalog.money(q.rides.cents), "Estimate, not charged"))
    return out


LEDGER_LANES = [("FLIGHT", "plane", "fill-sun-tint", "flight"), ("STAY", "bed", "fill-mint-tint", "stay"),
                ("GETTING AROUND", "car", "fill-sky-tint", "car"), ("RIDES, ESTIMATED", "car", "fill-sky-tint", "rides")]
_LEDGER = {lane: (label, ic, fill) for label, ic, fill, lane in LEDGER_LANES}


def line_items(q):
    """The slim line's pieces: icon + price per picked lane (the rides marked "est."), "+" between them and "=" at the end."""
    figs = slot_figures(q)
    parts = []
    for n, (lane, name, price, _sub) in enumerate(figs):
        label, ic, _fill = _LEDGER[lane]
        parts.append(Span(icon(ic, 16, 2.2), Span(label.title() if lane != "rides" else "Rides, estimated", cls="sr-only"), Span(price, data_line_price=lane),
                          *([Span("est.", cls="ws-est")] if lane == "rides" else []), cls="ws-line-item", title=name))
        parts.append(Span("+" if n < len(figs) - 1 else "=", cls="ws-op", aria_hidden="true"))
    return parts


def slot_items(q):
    """The popover's itemized lines, one per figure of `slot_figures`."""
    out = []
    for lane, name, price, sub in slot_figures(q):
        label, ic, fill = _LEDGER[lane]
        out.append(Div(
            Span(icon(ic, 22, 2.1), cls=f"ws-tile {fill}"),
            Span(Span(label, cls="ws-slot-label"), Span(name, cls="ws-slot-name", data_slot=lane), Span(sub, cls="ws-slot-sub", data_slot_sub=lane), cls="ws-slot-text"),
            Span(price, cls="ws-slot-price", data_slot_price=lane), cls="ws-slot",
        ))
    return out


def total_note(q):
    if q.empty:
        return "Nothing picked yet. Pick a flight, a stay or a car to book."
    note = f"{q.trip.travelers} people · taxes & fees in"
    return note + (f" · rides are an estimate, paid later" if q.rides else "")


def _html(els):
    return "".join(to_xml(e) for e in els)


def ledger_json(q):
    """The ledger figures for quote `q`, straight from the catalog. The page swaps these in and never computes them.

    "slots" has one entry per picked lane (and "rides"); "line_html" and "slots_html" are the slim line and the popover's lines
    rendered by the same code as the page, "rides_html" is the rides card and "skipped" says which lanes are skipped.
    """
    f, h, c = q.flight_id, q.stay_id, q.car_id
    return {
        "total": catalog.money(q.total_cents),
        "delta": delta_text(q),
        "cheapest": q.above_cheapest_cents == 0 and not q.empty,
        "empty": q.empty,
        "book": "" if q.empty else book_href(f, h, c, q.stay, q.trip, q.flight),
        "url": plan_path(f, h, c, q.stay, q.trip, q.flight),
        "pick": {"f": lane_id(f), "h": lane_id(h), "c": lane_id(c), "rooms": explicit_rooms(q.stay) if q.stay else None, "add": q.stay.add_code if q.stay else None,
                 "fare": q.flight.fare_code if q.flight else "", "bags": q.flight.bags_code if q.flight else ""},
        "skipped": {"flight": f is None, "stay": h is None, "car": c is None},
        "slots": {lane: {"name": name, "price": price, "sub": sub} for lane, name, price, sub in slot_figures(q)},
        "line_html": _html(line_items(q)),
        "slots_html": _html(slot_items(q)),
        "note": total_note(q),
        "rides_html": to_xml(rides_card(q.rides)) if q.rides else "",
    }


def stay_json(state):
    """One stay's editor state (rooms, add-ons, fit, summary and price) for the choose bar and the room cards."""
    return {
        "id": state.stay_id, "rooms": state.counts, "rooms_code": explicit_rooms(state), "add": list(state.addons), "add_code": state.add_code,
        "summary": state.summary, "price": catalog.money(state.cents), "fits": state.fits, "fit": state.fit, "fit_text": state.fit_text,
    }


def flight_json(state):
    """One flight's editor state (fare, bags, summary and price) for the choose bar and the fare and bag controls."""
    return {
        "id": state.flight_id, "fare": state.fare, "fare_code": state.fare_code, "bags": state.bags, "bags_code": state.bags_code, "max": state.max_bags,
        "bag_note": state.bag_note, "summary": state.summary, "price": catalog.money(state.cents),
    }


def embedded_data(f, h, c, stay, flight, trip):
    """What the page needs at load: each offer's display strings, the map points, the current pick and the trip's URL params."""
    offers = {o.id: {"name": o.name, "price": catalog.money(o.price_cents)} for k in LANES for o in catalog.offers(k, trip)}
    maps = {o.id: context.map_for_stay(o) for o in catalog.offers("stay")}
    return {"offers": offers, "map": maps, "defaults": DEFAULTS, "no_stay_map": NO_STAY_MAP,
            "pick": {"f": lane_id(f), "h": lane_id(h), "c": lane_id(c), "rooms": explicit_rooms(stay) if stay else None, "add": stay.add_code if stay else None,
                     "fare": flight.fare_code if flight else "", "bags": flight.bags_code if flight else ""},
            "base": plan_path(f, h, c, stay, trip, flight), "tripq": catalog.trip_query(trip)}


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


def flight_card(o, picked, viewing="", cents=None):
    """`cents`: the price to show (the picked flight shows its fare and bags); default is the flight's list price."""
    return Button(
        Span(Span(o.name, cls="ws-name"), *[Span(b, cls="ws-badge fill-sun") for b in o.badges],
             pick_pill(), Span(catalog.money(o.price_cents if cents is None else cents), cls="ws-price", data_flight_price=o.id), cls="ws-row"),
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


def skip_button(lane):
    """The light, positive choice at the end of a lane's cards: "I'll drive", "Staying with friends", "No car"."""
    k = SKIPS[lane]
    return Button(Span(icon(k["icon"], 18, 2.2), Span(k["label"], cls="ws-skip-label"), cls="ws-skip-row"), Span(k["sub"], cls="ws-skip-sub"),
                  type="button", cls="ws-skip", data_skip=lane)


def skipped_row(lane, with_flight=True):
    """What a skipped lane collapses to: a slim friendly row with a one-tap undo (shown by CSS when the pane is `data-skipped`)."""
    k = SKIPS[lane]
    note = k["note"] if lane != "car" or with_flight else "No car needed."
    return Div(Span(icon(k["icon"], 20, 2.2), cls="ws-skipped-ico", aria_hidden="true"),
               Span(note, cls="ws-skipped-note", data_skipped_note=lane),
               Button("Undo", type="button", cls="ws-undo", data_undo=lane, aria_label=f"Undo: {k['undo'].lower()}"),
               cls="ws-skipped")


def rides_card(r):
    """The "Uber and Lyft from LAX" card (sky tint): sample fares and times for the way in and the way out, and the estimate that
    goes in the total. "Uber" and "Lyft" are plain text. Nothing here is charged."""
    legs = []
    for leg in r.legs:
        legs.append(Div(
            Div(Span(f"{leg.title} · {leg.when}", cls="ws-ride-title"), Span(leg.route, cls="ws-ride-route"), cls="ws-ride-head"),
            Span(leg.note, cls="ws-ride-note"),
            Ul(*[Li(Span(f.provider, cls="ws-ride-who"), Span(f"{f.product}{'' if r.cars == 1 else f' x{r.cars}'} · about {f.minutes} min", cls="ws-ride-what"),
                    Span(catalog.money(f.cents), cls="ws-ride-price"), cls="ws-ride-fare") for f in leg.fares], cls="ws-ride-fares",
               aria_label=f"{leg.title} fares"),
            cls="ws-ride-leg", data_ride=leg.kind,
        ))
    return Div(
        Div(Span(icon("car", 18, 2.2), cls="ws-ride-ico", aria_hidden="true"), H3(r.title, cls="ws-ride-name"), Span("Sample fares", cls="ws-badge fill-sky-tint"), cls="ws-ride-top"),
        *legs,
        Div(Span("Rides, estimated", cls="ws-ride-sum"), Span(catalog.money(r.cents), cls="ws-ride-total"), cls="ws-ride-foot"),
        Span("Added to your total as an estimate. Nothing is charged for rides here; you would pay the driver later." + (" Five or more travelers ride in an XL." if r.xl else ""), cls="ws-ride-fine"),
        cls="ws-rides-card", id="ws-rides-card",
    )


def pane(key, num, title, meta, cards, tint, *extra, cls_extra="", detail=None, expanded=False, screen="list", lane=None, skipped=False, with_flight=True):
    """One workspace pane. `detail` (flights and stays) is the list of detail articles shown beside the cards when expanded.

    `lane` (flight, stay or car) gives it the lane's skip button and slim "skipped" row; `skipped` collapses it to that row."""
    attrs = dict(data_screen=screen) if detail else {}
    if skipped:
        attrs["data_skipped"] = "1"
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
        Div(*cards, *([skip_button(lane)] if lane else []), cls="ws-cards"),
        skipped_row(lane, with_flight) if lane else "",
        Div(*detail, cls="ws-dcol") if detail else "",
        *extra,
        cls=f"ws-pane {'ws-split' if detail else ''} {cls_extra}".strip(), data_pane=key, aria_label=title, **attrs,
    )


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


def flight_detail(o, picked, viewing, state, chosen=False):
    """One flight's detail panel. `state` is the FlightPick shown in its editor (the pick itself for the picked flight, else Basic with no bags);
    `chosen` says the editor holds the lane's pick."""
    trip = state.trip
    body = [
        Div(
            Button(icon("chev-left", 18, 2.4), "Flights", type="button", cls="ws-back ws-back-flat", data_back="list",
                           aria_label="Back to all flights"),
            cls="ws-fback",
        ),
        Div(H2(o.name, cls="ws-dtitle"), *[Span(b, cls="ws-sticker fill-sun") for b in o.badges], cls="ws-dhead ws-dhead-flight"),
        flight_ui.legs(o, trip),
        P(o.detail, cls="ws-dlead"),
        Div(flight_ui.fares_seam(state), data_seam="fares", cls="ws-seam"),
        Div(flight_ui.bags_seam(state), data_seam="bags", cls="ws-seam"),
    ]
    art = _article(o, picked, viewing, body, choose_bar(o, picked, "flight", state.summary, cents=state.cents, chosen=chosen))
    art.attrs.update({"data-fare": state.fare_code, "data-bags": state.bags_code})
    return art


def ledger(q, trip):
    """The slim ledger line for the top bar (F-031): one icon and price per picked lane (and the rides estimate) = total, plus Book.
    Tapping the total opens the popover with the itemized lines and the best-value hint. Every figure is rendered from the catalog;
    the JS swaps in /plan/quote's. A skipped lane has no item, and with nothing picked Book waits."""
    pop = Div(
        Div(*slot_items(q), cls="ws-slots", id="ws-slots"),
        Span(total_note(q), cls="ws-total-note", id="ws-total-note"),
        Span(delta_text(q), cls=f"ws-chip {'fill-mint' if q.above_cheapest_cents == 0 and not q.empty else 'fill-sun-tint'}", id="ws-delta", aria_live="polite"),
        cls="ws-pop", id="ws-pop", role="dialog", aria_label="Cost breakdown", tabindex="-1", hidden=True,
    )
    book = (A("Book", id="ws-book", cls="btn btn-ink ws-book", aria_label="Pick something to book first", aria_disabled="true") if q.empty else
            A("Book", href=book_href(q.flight_id, q.stay_id, q.car_id, q.stay, q.trip, q.flight), id="ws-book", cls="btn btn-ink ws-book", aria_label="Book this trip"))
    return Section(
        Span(*line_items(q), cls="ws-lines"),
        Button(catalog.money(q.total_cents), type="button", id="ws-total", cls="ws-total", aria_expanded="false", aria_controls="ws-pop",
               aria_haspopup="dialog", title="Cost breakdown"),
        Span(f"Total {catalog.money(q.total_cents)}", id="ws-total-live", cls="sr-only", aria_live="polite"),
        book,
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
          Span(trip.summary), Span("Change", cls="ws-change"), href="/start" + (f"?{catalog.trip_query(trip)}" if trip != catalog.SAMPLE_TRIP else ""), cls="ws-pill"),
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
    """The schematic map. `stay` None (staying with friends) draws it for the default stay with no hotel pin or line."""
    w, h = context.MAP_SIZE
    m = context.map_for_stay(stay or catalog.offer(DEFAULTS["stay"]))
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
             data_map_pin=stay.id if stay else ""),
        cls="ws-map ws-nostay" if stay is None else "ws-map",
    )
    return pane("map", 5, "Map", "Schematic", [
        canvas, Span(NO_STAY_MAP if stay is None else m["caption"], cls="ws-map-caption", id="ws-map-caption", aria_live="polite"),
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


def _your_forks():
    n = session.request_fork_count()
    return A(f"Your forks · {n}" if n else "Your forks", href="/forks", cls="ws-forklist")


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
        *rows, _your_forks(),
    ], "fill-sun", cls_extra="ws-dark")


def resolve_view(x, v, f, h):
    """(expanded pane key or '', {lane pane key: offer id being viewed}, screen). Only flights and stays split; a bad x or v is ignored."""
    picks = {"flights": f, "stays": h}
    expanded = x if x in SPLIT_LANES and picks[x] is not None else ""  # a skipped lane has nothing to open
    viewing = dict(picks)
    screen = "list"
    if expanded and v in {o.id for o in catalog.offers(SPLIT_LANES[expanded])}:
        viewing[expanded] = v
        screen = "detail"
    return expanded, viewing, screen


def workspace(f, h, c, overlay=(), head=(), x="", v="", stay=None, trip=None, flight=None):
    """The workspace for the lanes picked (f, h, c ids, None where skipped) on `trip`, with the stay and flight picks that go with them."""
    trip = trip or (stay.trip if stay is not None else flight.trip if flight is not None else catalog.SAMPLE_TRIP)
    expanded, viewing, screen = resolve_view(x, v, f, h)
    flights, stays = catalog.offers("flight", trip), catalog.offers("stay", trip)
    stay = (stay if stay is not None and stay.stay_id == h and stay.trip == trip else catalog.stay_pick(h, trip=trip)) if h else None
    flight = (flight if flight is not None and flight.flight_id == f and flight.trip == trip else catalog.flight_pick(f, trip=trip)) if f else None
    q = catalog.quote(f, h, c, stay, trip, flight)
    tip = Div("Tip from 312 families: most skipped the car in Santa Monica and rented one for the Griffith Park day only.", cls="ws-tip")
    body = Main(
        top_bar(trip, ledger(q, trip)),
        Div(
            pane("flights", 1, "Flights", f"round trip · {len(flights)}",
                 [flight_card(o, f, viewing["flights"] if expanded == "flights" else "", flight.cents if o.id == f else None) for o in flights], "fill-sun-tint",
                 detail=[flight_detail(o, f, viewing["flights"], flight if o.id == f else catalog.flight_pick(o.id, trip=trip), chosen=o.id == f) for o in flights], expanded=expanded == "flights",
                 screen=screen if expanded == "flights" else "list", lane="flight", skipped=f is None),
            pane("stays", 2, "Stays", trip.nights_text,
                 [stay_card(o, h, viewing["stays"] if expanded == "stays" else "", stay.cents if o.id == h else None) for o in stays], "fill-mint-tint",
                 detail=[stay_detail(o, h, viewing["stays"], stay if o.id == h else catalog.stay_pick(o.id, trip=trip), chosen=o.id == h) for o in stays], expanded=expanded == "stays",
                 screen=screen if expanded == "stays" else "list", lane="stay", skipped=h is None),
            pane("cars", 3, "Getting around", "", [car_card(o, c) for o in catalog.offers("car", trip)], "fill-sky-tint",
                 Div(rides_card(q.rides) if q.rides else "", id="ws-rides", cls="ws-rides", aria_live="polite"), tip,
                 lane="car", skipped=c is None, with_flight=f is not None),
            Div(weather_pane(), map_pane(catalog.offer(h) if h else None), news_pane(), community_pane(), cls="ws-context"),
            cls="ws-grid", id="ws-grid", data_focus=expanded or "flights", **(dict(data_expanded=expanded) if expanded else {}),
        ),
        cls="ws", id="main", data_theme="sunset",
    )
    data = Script(NotStr(script_json(embedded_data(f, h, c, stay, flight, trip))), id="ws-data", type="application/json")
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
    def plan(session, f: str = "", h: str = "", c: str = "", x: str = "", v: str = "", rooms: str = None, add: str = None,
             fare: str = None, bags: str = None, d: str = "", r: str = "", a: str = "", k: str = ""):
        picks, trip = resolve_pick(f, h, c), resolve_trip(d, r, a, k)
        stay, flight = resolve_stay(picks[1], rooms, add, trip), resolve_flight(picks[0], fare, bags, trip)
        if any((f, h, c, rooms, add, fare, bags, d, r, a, k)):  # a bare /plan is not "picks"; /start offers to continue the rest
            session_helpers.remember_plan(session, plan_path(*picks, stay, trip, flight)[len("/plan?"):])
        return workspace(*picks, x=x, v=v, stay=stay, flight=flight, trip=trip)

    @app.get("/plan/quote")
    def plan_quote(f: str = "", h: str = "", c: str = "", rooms: str = None, add: str = None, fare: str = None, bags: str = None,
                   d: str = "", r: str = "", a: str = "", k: str = ""):
        """The ledger figures for a pick, the flight editor's state for the fare and bags as asked, and the stay editor's state for the
        rooms as asked (even if they sleep too few).

        "ledger" prices what can really be booked: for a short pick (rooms that sleep fewer than the party) that is the default
        room plus the asked add-ons. "stay" describes the rooms as asked, so the choose bar can say "Sleeps 2 of 4 · add a room".
        """
        picks, trip = resolve_pick(f, h, c), resolve_trip(d, r, a, k)
        asked = catalog.parse_stay(picks[1], rooms, add, trip) if picks[1] else None
        real = (asked if asked.fits else catalog.stay_pick(picks[1], None, asked.add_code, trip)) if asked else None
        flight = resolve_flight(picks[0], fare, bags, trip)
        return {"ledger": ledger_json(catalog.quote(*picks, real, trip, flight)), "stay": stay_json(asked) if asked else None,
                "flight": flight_json(flight) if flight else None}

    @app.get("/plan/explore")
    def plan_explore(h: str = ""):
        """The 3D area explorer for a stay, fetched the first time its tab opens."""
        return HTMLResponse(to_xml(stay_ui.explore(resolve_pick("", h, "")[1] or DEFAULTS["stay"])))
