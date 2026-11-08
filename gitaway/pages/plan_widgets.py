"""The trip's context beside the booking lanes (F-210): weather at the place for the dates, the cost known so far, and the drive from the airport.

"No fakes please": every widget shows a real, sourced value with its credit, or does not appear; money, which always shows, says plainly what is missing.
    weather   gitaway/weather.py `trip_weather` (MET Norway's forecast when its terms are accepted and the trip is in reach, else NOAA's typical weather,
              labelled "not a forecast yet", else nothing), drawn with pages/weather_ui.py and always with `weather.notes`
    money     the Aviasales Data API's cached fare (gitaway/partners/prices.py), a person, never multiplied out (a kid's fare is not an adult's); every other
              lane says "No price yet — check on <site>". Pasted confirmations carry no prices (confirmations.py never reads them), so nothing else is counted.
    drive     gitaway/airportdrive.py: the router's own minutes from the airport to the stay town, or no widget

On a phone the panel is a strip above the lanes (first in the source); from 1020px it stands beside them (assets/css/planwidgets.css).
Weather and the drive can wait on the network (each to its own deadline, side by side): only from a plain `def` handler (plan.py's /plan is one).
"""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from fasthtml.common import A, Aside, Div, H2, Link, P, Section, Span

from gitaway import airportdrive, catalog, weather
from gitaway.icons import icon
from gitaway.pages import weather_ui
from gitaway.partners import prices, registry

CSS = Link(rel="stylesheet", href="/assets/css/planwidgets.css")
DAYS_SHOWN = 8
MONEY_LANES = (("flight", "Flights"), ("stay", "Stays"), ("car", "Car"), ("todo", "Things to do"))


def _trip(search):
    """What weather.trip_weather reads, for a booking search: its dates and its place (a catalog place keeps its key; a Disneyland trip is Anaheim's)."""
    p = search.place
    key = next((d.key for d in catalog.DESTINATIONS if d.name == p.name), "")
    return SimpleNamespace(depart=search.depart, return_=search.return_, destination_name=p.name, key=key, focus=p.focus, tz="")


def _card(name, tile, title, value, *rest):
    return Section(Span(icon(tile, 20, 2.1), cls=f"pw-tile pw-k-{name}", aria_hidden="true"),
                   Div(H2(title, cls="pw-title"), P(value, cls="pw-value"), *rest, cls="pw-text"),
                   cls=f"pw-card pw-{name}", id=f"pw-{name}", aria_label=title)


# ---- weather -----------------------------------------------------------------------------------------------------------------------

def _range(nums) -> str:
    lo, hi = min(nums), max(nums)
    return f"{lo}°" if lo == hi else f"{lo}–{hi}°"


def weather_card(tw):
    known = [d for d in tw.days if d]
    if not known:
        return ""
    value = f"Highs {_range([d.high_f for d in known])}F · lows {_range([d.low_f for d in known])}F"
    cells = [Div(Span(f"{d.date:%a} {d.date.day}", cls="pw-wday"), icon(d.condition, 18, 2), Span(f"{d.high_f}°", cls="pw-hi"), Span(f"{d.low_f}°", cls="pw-lo"),
                 Span("typical" if d.kind == weather.NORMAL else d.word, cls="pw-sky"),
                 cls="pw-wcell", role="group", aria_label=weather_ui.describe(d)) for d in known[:DAYS_SHOWN]]
    return _card("weather", "snow" if any(d.condition == "snow" for d in known) else known[0].condition, f"Weather in {tw.place}", value,
                 Div(*cells, cls="pw-days"), *weather_ui.notes(tw, "pw-note", "pw-link"))


# ---- money -------------------------------------------------------------------------------------------------------------------------

def money_card(search, found):
    p = search.place
    flight = found.get("flight") or []
    price = prices.flight_from(search.home, p.iata, search.depart, search.return_) if flight and search.home and p.known else None   # as the flight card asks: cached
    rows = []
    for lane, label in MONEY_LANES:
        sites = found.get(lane) or []
        if lane == "flight" and price:
            said = f"from {catalog.money(price.cents)} a person, round trip"
        elif sites:
            said = f"No price yet — check on {sites[0].name}"
        elif lane == "flight":
            said = "No price yet — tell us the nearest airport"
        else:
            continue
        rows.append(Div(Span(label, cls="pw-mlane"), Span(said, cls="pw-msaid" + (" is-real" if lane == "flight" and price else "")), cls="pw-mrow"))
    value = f"From {catalog.money(price.cents)} a person, flights only" if price else "No prices yet"
    lines = [P(f"The cheapest fare Aviasales travellers saw for these dates, checked {prices.when(price.checked)}. A hint, not a quote.", cls="pw-note")] if price else []
    return _card("money", "ledger", "Cost so far", value, Div(*rows, cls="pw-mrows"), *lines,
                 P("Each site shows today's price. GitAway adds up only prices it has really seen.", cls="pw-note"))


# ---- drive -------------------------------------------------------------------------------------------------------------------------

def drive_card(search, drive):
    if not drive:
        return ""
    why = "without traffic or chain controls" if search.winter_snow else "without traffic"
    return _card("drive", "car", f"Drive from {drive.iata}", f"{drive.label()} to {search.place.city}",
                 A(f"OSRM's route, {why} · map data © OpenStreetMap contributors", href=airportdrive.CREDIT_URL, rel="noopener", cls="pw-note pw-link"))


# ---- the panel ---------------------------------------------------------------------------------------------------------------------

def panel(search):
    """The side panel for `search`: weather and the drive asked side by side, each to its own deadline."""
    p = search.place
    with ThreadPoolExecutor(2, thread_name_prefix="plan-widgets") as pool:
        tw = pool.submit(weather.trip_weather, _trip(search))
        drive = pool.submit(airportdrive.drive, p.iata, p.town) if p.iata else None
        tw, drive = tw.result(), drive.result() if drive else None
    found = registry.lanes(search)
    return Aside(weather_card(tw), money_card(search, found), drive_card(search, drive), cls="pw", id="pw", aria_label="Your trip so far")


def beside(search, lanes):
    """The booking lanes with the panel: above them on a phone, beside them from 1020px."""
    return Div(panel(search), lanes, cls="pw-with")
