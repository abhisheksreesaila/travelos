"""The frosted widget rail beside the matrix (F-251, D-620..), the prototype's right-hand column (docs/design/booking-v2/index.html `drawRail`): Apple-style translucent cards that follow
the place you look at and the start day you opened. Beside the matrix on a laptop, a swipeable row under it on a phone.

    GET /plan/matrix/rail    the rail for one lane and start day, as JSON {html} for assets/js/v2rail.js: a plain `def` (a drive can wait on the router for a moment)

Each widget has one real source or is not drawn (gitaway/v2rail.py): the weather (weather.py; typical days dotted and labelled, MET Norway's credit under it), where you will be (OSRM drives,
typical, no live traffic; a straight-line distance from home), a cheaper airport (only when another airport's flights for the same days are already known and cost less), food that fits
(hotels whose rate includes breakfast, the source's own; and on the showcase the made-up places that fit the family's interests) and what is known about the place (placefacts, each with its
page). Uber, traffic and what is on are the showcase's made-up samples and say Sample; off the showcase they are not drawn.
"""

from fasthtml.common import A, Button, Div, Header, Li, NotStr, P, Section, Span, Ul, to_xml

from gitaway import catalog, showcase, tripmatrix as tm, v2rail, weather
from gitaway.icons import icon
from gitaway.pages import skystrip, weather_ui

K = {"wx": "var(--wx)", "see": "var(--see)", "ride": "var(--ride-on)", "tix": "var(--tix)", "flight": "var(--flight)", "food": "var(--food)", "stay": "var(--stay)"}
SCHEMATIC = "Schematic, not to scale"
NO_TRAFFIC = "Typical drive by road. No live traffic."


def wg(title: str, ic, k: str, *body, sample=False, i=0):
    """One widget: a frosted card with its kind's coloured icon, a title and, when any of it is made-up, a Sample pill."""
    return Section(Header(Span(icon(ic, 17, 2.2), cls="ic", style=f"--k:{K[k]}"), Span(title, cls="wg-h"), Span("Sample", cls="smp") if sample else ""), *body, cls="wg v2-glass", style=f"--i:{i}")


def _ul(rows, cls="list"):
    return Ul(*rows, cls=cls)


def weather_widget(place, w, i):
    tw = v2rail.sky(place.name, w.depart)
    days = [d for d in tw.days if d]
    if not days:
        return ""
    first = days[0]
    typical = first.kind != weather.FORECAST
    note = (first.label or skystrip.TYPICAL) + "." if typical else f"{first.word}. A forecast."
    strip = Div(*[Div(Span(f"{d.date:%a}"), icon(d.condition if d.condition in skystrip.WORDS else "cloud", 22, 2, cls="wi"), Span(f"{d.high_f}°", cls="num"),
                      cls="d5 " + ("is-typ" if d.kind != weather.FORECAST else "is-fc") + (" is-wet" if d.condition in skystrip.WET else ""), title=weather_ui.describe(d), aria_label=weather_ui.describe(d))
                 for d in days], cls="days5")
    return wg("Weather", "sun", "wx", Div(Span(f"{first.high_f}°", cls="n num"), Span(skystrip.WORDS.get(first.condition, ""), cls="bw"), cls="bigline"), P(note), strip,
              Div(*[A(t, href=h, rel="noopener", cls="fine fine-a") if h else Span(t, cls="fine") for t, h in weather.notes(tw) if not t.startswith("Typical ")], cls="credits"), i=i)


def _map(wh: v2rail.Where):
    """A schematic, not a map: the airport, the stay and the asked place as dots joined by their drive times. Drawn the prototype's way (soft land and water) with nothing pretending to be a
    coastline: the words on it are the real numbers and the caption says it is not to scale."""
    def label(x, y, t):
        return f'<g transform="translate({x} {y})"><rect x="-26" y="-10" width="52" height="20" rx="10" fill="#fff"/><text x="0" y="4" text-anchor="middle" font-family="Inter,sans-serif" font-size="11" font-weight="650" fill="#0F1124">{t}</text></g>'
    parts = ['<rect width="300" height="150" fill="#E8EFE3"/><path d="M0 0 H70 Q60 40 78 70 T66 120 Q60 140 72 150 H0Z" fill="#A9D3F0"/>',
             '<path d="M110 0 V150 M200 0 Q190 60 210 150 M92 70 H300 M140 30 H300" stroke="#fff" stroke-width="5" fill="none"/>']
    air, stay, want = (70, 112), (150, 74), (240, 40)
    if wh.airport_min:
        parts.append(f'<path d="M{air[0]} {air[1]} L{stay[0]} {stay[1]}" stroke="#4338CA" stroke-width="3" stroke-dasharray="5 5" fill="none"/>' + label(110, 100, f"{wh.airport_min} min"))
    if wh.asked_min:
        parts.append(f'<path d="M{stay[0]} {stay[1]} L{want[0]} {want[1]}" stroke="#0F766E" stroke-width="3" stroke-dasharray="5 5" fill="none"/>' + label(196, 52, f"{wh.asked_min} min"))
    parts.append(f'<g transform="translate({air[0]} {air[1]})"><circle r="11" fill="#4338CA"/><path d="M-5 0 h10 M1 -5 l5 5 -5 5" stroke="#fff" stroke-width="2" fill="none"/></g>')
    parts.append(f'<g transform="translate({stay[0]} {stay[1]})"><circle r="13" fill="#8B2FC9" stroke="#fff" stroke-width="3"/><path d="M-6 3v-7M-6 1h12v4M6 -1a3 3 0 0 0-3-3h-4v4" stroke="#fff" stroke-width="1.8" fill="none" stroke-linecap="round"/></g>')
    if wh.asked_min:
        parts.append(f'<g transform="translate({want[0]} {want[1]})"><circle r="9" fill="#0F766E"/><circle r="3.5" fill="#fff"/></g>')
    return Div(NotStr(f'<svg class="map" viewBox="0 0 300 150" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Sketch: the airport, the stay and the asked place, with the drive times between them">{"".join(parts)}</svg>'),
               Span(SCHEMATIC, cls="map-cap"), cls="map-w")


def where_widget(s, lane, i, look_up=True):
    wh = v2rail.where(s, lane, look_up)
    if not wh.rows:
        return ""
    rows = []
    if wh.airport_min:
        rows.append(Div(Span(cls="dot", style="--k:var(--flight)"), Span(f"{wh.airport} airport → {wh.town}"), Span(f"{wh.airport_min} min", cls="num"), cls="ro"))
    if wh.asked_min:
        rows.append(Div(Span(cls="dot", style="--k:var(--see)"), Span(f"{wh.town} → {wh.asked}"), Span(f"{wh.asked_min} min", cls="num"), cls="ro"))
    if wh.home_miles:
        rows.append(Div(Span(cls="dot", style="--k:var(--food)"), Span(f"{wh.home} → {wh.airport}, in a straight line"), Span(f"{wh.home_miles:,} mi", cls="num"), cls="ro"))
    drives = bool(wh.airport_min or wh.asked_min)
    return wg("Where you will be", "map", "see", _map(wh) if drives else "", Div(*rows, cls="dist"), P(NO_TRAFFIC, cls="fine") if drives else "", i=i)


def cheaper_widget(s, lane, w, lanes, known, i):
    c = v2rail.cheaper_airport(s, lane, w, lanes, known)
    if c is None:
        return ""
    more = f"{tm.dollars(abs(c.trip_cents))} {'less' if c.trip_cents < 0 else 'more'}"
    return wg("A cheaper airport", "plane", "flight", Div(Span(tm.dollars(c.save_cents), cls="n num"), Span(f"less for {s.travelers}", cls="bw"), cls="bigline"),
              P(Span(f"Flights into {c.iata} ({c.place}) cost less than into {c.base_iata}.", cls="em"), f" The whole trip there is {more} on the same days."),
              Button(f"Look at {c.place}", icon("arrow-right", 18, 2.2), type="button", cls="mini-btn", data_lane=c.lane), i=i)


def food_widget(sq, place, picked, i):
    rows = [Li(Span(Span(st.name, cls="b"), Span(Span("Breakfast included", cls="tagk"), f"{catalog.money(r.cents)} for the stay"), cls="t")) for st, r in (v2rail.breakfast(sq) if sq is not None and sq.ok else ())[:3]]
    sample = v2rail.sample(place) if showcase.on() else None
    if sample:
        for name, what, minutes, _ in v2rail.fits(sample["food"], picked):
            kind, _, rest = what.partition(" · ")
            rows.append(Li(Span(Span(name, cls="b"), Span(Span(kind, cls="tagk"), f"{rest + ' · ' if rest else ''}{minutes} min"), cls="t")))
    if not rows:
        return ""
    return wg("Food that fits you", "food", "food", _ul(rows), sample=bool(sample), i=i)


def about_widget(place, i):
    facts = v2rail.about(place)
    if not facts:
        return ""
    items = [Li(Span(Span(f.text, cls="b"), A("Source", href=f.source, rel="noopener", target="_blank", cls="src")), hidden=n > 2) for n, f in enumerate(facts)]
    return wg(f"About {place.name}", "list", "see", _ul(items), Button(f"Show all {len(facts)}", type="button", cls="link-btn", data_more="1") if len(facts) > 3 else "", i=i)


def uber_widget(sample, place, hotel, i):
    a, b = sample["uber"]
    return wg("Uber to the hotel", "car", "ride", Div(Div(Span("UberX", cls="k"), Span(a, cls="num b"), Span("4 seats, tight with bags"), cls="tile"),
                                                      Div(Span("UberXL", cls="k"), Span(b, cls="num b"), Span("6 seats, room for 4 bags"), cls="tile"), cls="tiles2"),
              P(f"{place.iata} to {hotel}, a made-up estimate.", cls="fine"), sample=True, i=i)


def traffic_widget(sample, i):
    t = sample["traffic"]
    top = max(t)
    bars = Div(*[Div(Span(cls="bar", style=f"height:{round(m / top * 100)}%;--k:{'var(--tix)' if m / top > .8 else 'var(--sun-ink)' if m / top > .55 else 'var(--see)'}"), Span(v2rail.TIMES[n], cls="num"))
                 for n, m in enumerate(t)], cls="bars")
    return wg("Traffic when you land", "road", "tix", P(sample["route"], cls="route"), bars, P(f"Made up: {min(t)} min at the quietest, {top} min at 5 pm.", cls="fine"), sample=True, i=i)


def trend_widget(sample, i):
    return wg("Happening that week", "flame", "stay", _ul([Li(Span(Span(n, cls="b"), Span(d), cls="t")) for n, d in sample["trend"]]), sample=True, i=i)


def rail(s, lane, w, *, sq=None, lanes=(), known=None, picked=(), look_up=True):
    """The rail's widgets for `lane` on start day `w`: the head, then the widgets that have something real (or, on the showcase, made-up) to say."""
    from gitaway.pages import tripmatrix as mx
    place = lane.places[0]
    sample = v2rail.sample(place) if showcase.on() else None
    hotel = sq.stays[0].name if sq is not None and sq.ok else place.city
    items = [weather_widget(place, w, 1), where_widget(s, lane, 2, look_up),
             uber_widget(sample, place, hotel, 3) if sample else "", traffic_widget(sample, 4) if sample else "",
             cheaper_widget(s, lane, w, lanes, known, 5) if known else "", food_widget(sq, place, picked, 6), trend_widget(sample, 7) if sample else "", about_widget(place, 8)]
    head = Div(mx._art(place, "rl-art"), Div(Span(f"Around {place.name}", cls="rl-h"), Span("Follows the place you look at", cls="rl-s")), cls="rl-head")
    return Div(head, Div(*[x for x in items if x != ""], cls="rl-row"), cls="rl-in", data_lane=lane.key, data_w=w.key)


def html(s, lane, w, **kw) -> str:
    return to_xml(rail(s, lane, w, **kw))
