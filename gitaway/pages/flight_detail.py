"""The flight detail panel's body (F-027): out and back legs, the fare radiogroup and the checked-bag stepper.

Everything is rendered from gitaway.catalog; the page JS only toggles and swaps server figures (see assets/js/workspace.js).
"""

from fasthtml.common import Button, Div, H3, Span

from gitaway import catalog
from gitaway.icons import icon
from gitaway.tripcal import fmt_time


def duration_text(minutes):
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m" if h and m else (f"{h}h" if h else f"{m}m")


def date_text(d):
    return d.strftime("%a %b ") + str(d.day)


def leg(label, date, dep, arr, origin, dest, stops, aircraft):
    nonstop = stops == "Nonstop"
    return Div(
        Span(f"{label} · {date}", cls="ws-leg-label"),
        Div(
            Span(Span(fmt_time(dep), cls="ws-leg-time"), Span(origin, cls="ws-leg-apt"), cls="ws-leg-end"),
            Span(Span(duration_text(arr - dep), cls="ws-leg-dur"), Span(Span(cls="ws-leg-stop" + ("" if nonstop else " ws-leg-stop-on")), cls="ws-leg-line"),
                 Span(stops, cls="ws-leg-stops"), cls="ws-leg-mid"),
            Span(Span(fmt_time(arr), cls="ws-leg-time"), Span(dest, cls="ws-leg-apt"), cls="ws-leg-end"),
            cls="ws-leg-row",
        ),
        Span(aircraft, cls="ws-leg-craft"),
        cls="ws-leg",
    )


def legs(o, trip):
    return Div(
        leg("Out", date_text(trip.depart), o.depart_min, o.arrive_min, trip.origin, o.airport, o.stops, o.aircraft),
        leg("Back", date_text(trip.return_), o.back_depart_min, o.back_arrive_min, o.airport, trip.origin, o.stops, o.aircraft),
        cls="ws-legs", data_legs="",
    )


def perk(included, text):
    mark = icon("check", 12, 3.4) if included else Span("–")
    return Span(Span(mark, cls="ws-perk-mark", aria_hidden="true"), Span(text), cls=f"ws-perk {'is-on' if included else 'is-off'}")


def fare_card(f, state):
    on = f.id == state.fare
    flight_cents = state.offer.price_cents + f.extra_cents
    return Button(
        Span(Span(Span(cls="ws-radio-dot"), cls="ws-radio", aria_hidden="true"), Span(f.name, cls="ws-fare-name"),
             Span(f"+{catalog.money(f.extra_cents)}", cls="ws-fare-extra") if f.extra_cents else "", cls="ws-fare-head"),
        Span(catalog.money(flight_cents), cls="ws-fare-price"),
        Span(*[perk(i, t) for i, t in f.perks], cls="ws-perks"),
        type="button", role="radio", aria_checked="true" if on else "false", tabindex="0" if on else "-1", data_fare_pick=f.id, cls="ws-fare",
    )


def fares_seam(state):
    trip = state.trip
    return Div(
        Div(H3("Pick a fare", cls="ws-h3"), Span(f"Round trip for all {trip.travelers}, taxes in", cls="ws-h3-sub"), cls="ws-h3-row"),
        Div(*[fare_card(f, state) for f in catalog.fares(trip)], role="radiogroup", aria_label="Fare", cls="ws-fares", data_fares=""),
        cls="ws-fare-block",
    )


def bags_seam(state):
    n = state.bags
    return Div(
        icon("bag", 28, 2.2, "ws-bag-ico"),
        Span(Span("Checked bags", cls="ws-bag-title"), Span(state.bag_note, cls="ws-bag-note", data_bag_note=""), cls="ws-bag-text"),
        Span(
            Button(icon("minus", 16, 3), type="button", cls="ws-step", aria_label="One fewer checked bag", data_bag_step="-1", disabled=n <= 0),
            Span(str(n), cls="ws-count ws-bag-count", aria_live="polite"),
            Button(icon("plus", 16, 3), type="button", cls="ws-step ws-step-more", aria_label="One more checked bag", data_bag_step="1", disabled=n >= state.max_bags),
            cls="ws-stepper",
        ),
        cls="ws-bags", data_max=str(state.max_bags),
    )
