"""The frosted widget rail beside the matrix (F-251, D-620..), the prototype's right-hand column (docs/design/booking-v2/index.html `drawRail`): Apple-style translucent cards that follow
the place you look at and the start day you opened. Beside the matrix on a laptop, a swipeable row under it on a phone.

    GET /plan/matrix/rail            the chips for one lane and start day, as JSON {html} for assets/js/v2rail.js: only labels that cost nothing to know (F-277, D-870)
    GET /plan/matrix/rail?wg=<name>  one chip's card, as JSON {card}: asked when its chip is tapped, never before (a drive can wait on the router, the weather on MET Norway), so a plain `def`

Each widget has one real source or is not drawn (gitaway/v2rail.py): the weather (weather.py; typical days dotted and labelled, MET Norway's credit under it), where you will be (OSRM drives,
typical, no live traffic; a straight-line distance from home), a cheaper airport (only when another airport's flights for the same days are already known and cost less), food that fits
(hotels whose rate includes breakfast, the source's own; and on the showcase the made-up places that fit the family's interests) and what is known about the place (placefacts, each with its
page). Uber, traffic and what is on are the showcase's made-up samples and say Sample; off the showcase they are not drawn.
"""

from fasthtml.common import A, Button, Div, Header, Li, NotStr, P, Section, Small, Span, Ul, to_xml

from gitaway import airportdrive, catalog, showcase, tripmatrix as tm, v2rail, weather
from gitaway.icons import icon
from gitaway.pages import skystrip, weather_ui

K = {"wx": "wx", "see": "see", "ride": "grey", "tix": "grey", "flight": "flight", "food": "food", "stay": "stay"}      # the kind of a widget -> its icon tile (--tl-*, v2-tokens.css, D-958)


def tile(k: str) -> str:
    """The style that gives an icon tile its vivid fill and the glyph colour that passes on it."""
    return f"--k:var(--tl-{K[k]});--kon:var(--tl-{K[k]}-on)"
SCHEMATIC = "Schematic, not to scale"
NO_TRAFFIC = "Typical drive by road. No live traffic."


def chip_of(title: str, ic, k: str, name: str, label: str = "", teaser: str = "", count: str = ""):
    """A chip that fetches its card when tapped (assets/js/v2rail.js), the Fill treatment (F-281, D-892): a coloured icon, a title, a teaser line and a count. Only what is cheap to know goes on it:
    the teaser says what is inside and the count is a number the server already has (never one that waits on a service)."""
    return Button(Span(icon(ic, 17, 2.2), cls="ic", style=tile(k)), Span(Span(label or title), Small(teaser) if teaser else "", cls="tx"), Span(count, cls="ct num") if count else "",
                  type="button", cls="wchip", aria_expanded="false", aria_controls=f"wg-{name}", data_wg=name)


def wg(title: str, ic, k: str, *body, sample=False, name="", chip="", teaser="", count=""):
    """One widget, folded (F-275, D-862): a chip and the frosted card it opens, with its kind's coloured icon, a title and, when any of it is made-up, a Sample pill. The card is only
    drawn when asked for (F-277, D-870). Returns (chip, card)."""
    card = Section(Header(Span(icon(ic, 17, 2.2), cls="ic", style=tile(k)), Span(title, cls="wg-h"), Span("Sample", cls="smp") if sample else "", Button(icon("x", 18, 2.4), type="button", cls="wg-x", data_wg_close=name, aria_label=f"Close {title}")),
                   *body, cls="wg v2-glass", id=f"wg-{name}")
    return chip_of(title, ic, k, name, chip, teaser, count), card


def _ul(rows, cls="list"):
    return Ul(*rows, cls=cls)


def weather_widget(place, w, name, lazy=False):
    if lazy:      # a chip with a real source behind it (a station for the place) and nothing asked yet: no forecast is fetched until the chip is tapped
        return (chip_of("Weather", "sun", "wx", name, teaser="Your dates, day by day", count=f"{v2rail.DAYS} days"), None) if v2rail.has_weather(place.name, w.depart) else ""
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
              Div(*[A(t, href=h, rel="noopener", cls="fine fine-a") if h else Span(t, cls="fine") for t, h in weather.notes(tw) if not t.startswith("Typical ")], cls="credits"),
              name=name)


def _map(wh: v2rail.Where):
    """A schematic, not a map: the airport, the stay and the asked place as dots joined by their drive times. Drawn the prototype's way (soft land and water) with nothing pretending to be a
    coastline: the words on it are the real numbers and the caption says it is not to scale."""
    # labels are made of numbers only; if a place or hotel name is ever added to this SVG it must be escaped (html.escape) first
    def label(x, y, t):
        return f'<g transform="translate({x} {y})"><rect class="m-pill" x="-26" y="-10" width="52" height="20" rx="10"/><text class="m-txt" x="0" y="4" text-anchor="middle" font-size="11" font-weight="650">{t}</text></g>'
    parts = ['<rect class="m-land" width="300" height="150"/><path class="m-water" d="M0 0 H70 Q60 40 78 70 T66 120 Q60 140 72 150 H0Z"/>',
             '<path class="m-road" d="M110 0 V150 M200 0 Q190 60 210 150 M92 70 H300 M140 30 H300"/>']
    air, stay, want = (70, 112), (150, 74), (240, 40)
    if wh.airport_min:
        parts.append(f'<path class="m-leg m-leg-a" d="M{air[0]} {air[1]} L{stay[0]} {stay[1]}"/>' + label(110, 100, f"{wh.airport_min} min"))
    if wh.asked_min:
        parts.append(f'<path class="m-leg m-leg-b" d="M{stay[0]} {stay[1]} L{want[0]} {want[1]}"/>' + label(196, 52, f"{wh.asked_min} min"))
    parts.append(f'<g transform="translate({air[0]} {air[1]})"><circle class="m-air" r="11"/><path class="m-glyph" d="M-5 0 h10 M1 -5 l5 5 -5 5"/></g>')
    parts.append(f'<g transform="translate({stay[0]} {stay[1]})"><circle class="m-stay" r="13"/><path class="m-glyph" d="M-6 3v-7M-6 1h12v4M6 -1a3 3 0 0 0-3-3h-4v4"/></g>')
    if wh.asked_min:
        parts.append(f'<g transform="translate({want[0]} {want[1]})"><circle class="m-want" r="9"/><circle class="m-core" r="3.5"/></g>')
    return Div(NotStr(f'<svg class="map" viewBox="0 0 300 150" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Sketch: the airport, the stay and the asked place, with the drive times between them">{"".join(parts)}</svg>'),
               Span(SCHEMATIC, cls="map-cap"), cls="map-w")


def where_widget(s, lane, name, look_up=True, lazy=False):
    if lazy:      # the airport's coordinates are known (or the lane is another place than the asked one): the drives are asked when the chip is tapped
        place = lane.places[0]
        return (chip_of("Where you will be", "map", "see", name, teaser="Typical drives by road"), None) if place.iata in airportdrive.AIRPORTS or (not lane.asked and s.place.name != place.name) else ""
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
    return wg("Where you will be", "map", "see", _map(wh) if drives else "", Div(*rows, cls="dist"), P(NO_TRAFFIC, cls="fine") if drives else "", name=name)


def cheaper_widget(s, lane, w, lanes, known, name):
    c = v2rail.cheaper_airport(s, lane, w, lanes, known)
    if c is None:
        return ""
    more = f"{tm.dollars(abs(c.trip_cents))} {'less' if c.trip_cents < 0 else 'more'}"
    return wg("A cheaper airport", "plane", "flight", Div(Span(tm.dollars(c.save_cents), cls="n num"), Span(f"less for {s.travelers}", cls="bw"), cls="bigline"),
              P(Span(f"Flights into {c.iata} ({c.place}) cost less than into {c.base_iata}.", cls="em"), f" The whole trip there is {more} on the same days."),
              Button(f"Look at {c.place}", icon("arrow-right", 18, 2.2), type="button", cls="mini-btn", data_lane=c.lane), name=name,
              chip="A cheaper airport", teaser=f"From {c.iata}, about {tm.dollars(c.save_cents)} less", count=f"\u2212{tm.dollars(c.save_cents)}")


def food_widget(sq, place, picked, name):
    rows = [Li(Span(Span(st.name, cls="b"), Span(Span("Breakfast included", cls="tagk"), f"{catalog.money(r.cents)} for the stay"), cls="t")) for st, r in (v2rail.breakfast(sq) if sq is not None and sq.ok else ())[:3]]
    sample = v2rail.sample(place) if showcase.on() else None
    if sample:
        for place_name, what, minutes, _ in v2rail.fits(sample["food"], picked):
            kind, _, rest = what.partition(" · ")
            rows.append(Li(Span(Span(place_name, cls="b"), Span(Span(kind, cls="tagk"), f"{rest + ' · ' if rest else ''}{minutes} min"), cls="t")))
    if not rows:
        return ""
    return wg("Food that fits you", "food", "food", _ul(rows), sample=bool(sample), name=name, chip=f"Food that fits you{' · sample' if sample else ''}",
              teaser="Breakfast included, and picks that fit you", count=str(len(rows)) if len(rows) > 1 else "")


def about_widget(place, name):
    facts = v2rail.about(place)
    if not facts:
        return ""
    items = [Li(Span(Span(f.text, cls="b"), A("Source", href=f.source, rel="noopener", target="_blank", cls="src")), hidden=n > 2) for n, f in enumerate(facts)]
    return wg(f"About {place.name}", "list", "see", _ul(items), Button(f"Show all {len(facts)}", type="button", cls="link-btn", data_more="1") if len(facts) > 3 else "", name=name, chip=f"About {place.name}", teaser="Facts, each with its source", count=str(len(facts)) if len(facts) > 1 else "")


def uber_widget(sample, place, hotel, name):
    a, b = sample["uber"]
    return wg("Uber to the hotel", "car", "ride", Div(Div(Span("UberX", cls="k"), Span(a, cls="num b"), Span("4 seats, tight with bags"), cls="tile"),
                                                      Div(Span("UberXL", cls="k"), Span(b, cls="num b"), Span("6 seats, room for 4 bags"), cls="tile"), cls="tiles2"),
              P(f"{place.iata} to {hotel}, a made-up estimate.", cls="fine"), sample=True, name=name, chip=f"Uber {a} · sample", teaser="The airport to the hotel")


def traffic_widget(sample, name):
    t = sample["traffic"]
    top = max(t)
    bars = Div(*[Div(Span(cls="bar", style=f"height:{round(m / top * 100)}%;--k:{'var(--tix)' if m / top > .8 else 'var(--sun-ink)' if m / top > .55 else 'var(--see)'}"), Span(v2rail.TIMES[n], cls="num"))
                 for n, m in enumerate(t)], cls="bars")
    return wg("Traffic when you land", "road", "tix", P(sample["route"], cls="route"), bars, P(f"Made up: {min(t)} min at the quietest, {top} min at 5 pm.", cls="fine"), sample=True, name=name, chip="Traffic when you land · sample", teaser="Drive times through the day")


def trend_widget(sample, name):
    return wg("Happening that week", "flame", "stay", _ul([Li(Span(Span(n, cls="b"), Span(d), cls="t")) for n, d in sample["trend"]]), sample=True, name=name, chip="Happening that week · sample", teaser="What is on while you are there", count=str(len(sample["trend"])) if len(sample["trend"]) > 1 else "")


def guides_widget(s, lane, w, guides, name):
    """"Guides for San Diego" (F-263): the published guides of the lane's place (and, on the showcase, the labelled sample ones), each opening in a sheet over the matrix that grows out of its row;
    nothing when there are none, which off the showcase is most places."""
    from gitaway.pages import guidesheet as gs, tripmatrix as mx
    cards, total = guides
    if not cards:
        return ""
    place = lane.places[0].name
    base = mx.href(s, "/guides/sheet", lane=lane.key, w=w.key, ctx="book").split("?", 1)[1]
    return wg(f"Guides for {place}", "list", "see", P("What other families did there. It opens over your trips, so you keep your place.", cls="fine"),
              gs.widget_rows(cards, lambda c: f"/guides/sheet?slug={c.slug}&{base}"), gs.widget_foot(place, total, len(cards)), sample=all(not c.real for c in cards), name=name,
              chip=f"{total} guide{'' if total == 1 else 's'} for {place}", teaser="What other families did there", count=str(total) if total > 1 else "")


NAMES = {"guides": "Guides", "weather": "Weather", "where": "Where you will be", "uber": "Uber to the hotel", "traffic": "Traffic when you land", "cheaper": "A cheaper airport",
         "food": "Food that fits you", "trend": "Happening that week", "about": "About this place"}      # in the order the chips come, and the title of a card with nothing to say
EXTRA = "More to know before you pick"
NUDGE = "New: tap for weather, drive times, guides…"


def _widget(name, s, lane, w, *, sq, lanes, known, picked, look_up, guides, lazy):
    """One widget by name: (chip, card), or "" when it has nothing real to say. `lazy` builds only what costs nothing to know (the chip): the weather and the drives are not asked."""
    place = lane.places[0]
    sample = v2rail.sample(place) if showcase.on() else None
    hotel = sq.stays[0].name if sq is not None and sq.ok else place.city
    return {"guides": lambda: guides_widget(s, lane, w, guides, name), "weather": lambda: weather_widget(place, w, name, lazy), "where": lambda: where_widget(s, lane, name, look_up, lazy),
            "uber": lambda: uber_widget(sample, place, hotel, name) if sample else "", "traffic": lambda: traffic_widget(sample, name) if sample else "",
            "cheaper": lambda: cheaper_widget(s, lane, w, lanes, known, name) if known else "", "food": lambda: food_widget(sq, place, picked, name),
            "trend": lambda: trend_widget(sample, name) if sample else "", "about": lambda: about_widget(place, name)}[name]()


def rail(s, lane, w, *, sq=None, lanes=(), known=None, picked=(), look_up=True, guides=((), 0)):
    """The extra-info row for `lane` on start day `w` (F-277, D-870): a tray titled for what it is for, the place, and a scroller of chips for the widgets that have something real (or, on the showcase, made-up)
    to say. No card is drawn and no weather or drive is asked: each chip fetches its card when it is tapped (`card`)."""
    place = lane.places[0]
    got = [c for c in (_widget(n, s, lane, w, sq=sq, lanes=lanes, known=known, picked=picked, look_up=look_up, guides=guides, lazy=True) for n in NAMES) if c != ""]
    top = Div(Span(EXTRA, cls="rl-lab"), Span(f"Around {place.name}", cls="rl-h"), cls="rl-top")
    tray = Div(top, Div(*[c for c, _ in got], cls="rl-chips"), P(NUDGE, cls="rl-nudge"), cls="rl-tray v2-glass", role="group", aria_label=EXTRA)      # a dark frost over the ground (v2rail.css)
    return Div(tray, Div(cls="rl-cards"), cls="rl-in", data_lane=lane.key, data_w=w.key)


def card(name, s, lane, w, **kw):
    """The card of the chip tapped: the widget built for real now, or a card saying there is nothing for it (a drive no router answered). None for a name that is no widget."""
    if name not in NAMES:
        return None
    got = _widget(name, s, lane, w, sq=kw.get("sq"), lanes=kw.get("lanes", ()), known=kw.get("known"), picked=kw.get("picked", ()), look_up=kw.get("look_up", True), guides=kw.get("guides", ((), 0)), lazy=False)
    return got[1] if got != "" else wg(NAMES[name], "list", "see", P("Nothing known for this yet.", cls="fine"), name=name)[1]


def html(s, lane, w, **kw) -> str:
    return to_xml(rail(s, lane, w, **kw))


def card_html(name, s, lane, w, **kw) -> str | None:
    c = card(name, s, lane, w, **kw)
    return None if c is None else to_xml(c)
