"""Landing page (F-013): "Two doors". One door books a trip, the other forks a real one."""

from fasthtml.common import A, Button, Div, Form, H1, H2, H3, Img, Input, Label, Link, NotStr, P, Section, Span

from gitaway import itineraries
from gitaway.catalog import SAMPLE_TRIP
from gitaway.icons import icon
from gitaway.layout import page

HEAD = (Link(rel="stylesheet", href="/assets/css/landing.css"),)


FEATURES = [
    ("Everything side by side", "Flights, stays and cars next to weather, news, events and a map. No more twelve tabs.",
     icon("panes", 30, 2), "sun", -4),
    ("One honest total", "A running cost ledger shows what the whole trip costs, and how far you are from the cheapest combo.",
     icon("ledger", 30, 2), "coral", 3),
    ("Plan it together", "Invite family and friends to a shared calendar with notes, so everyone knows the plan.",
     icon("users", 30, 2), "mint", -2),
    ("Fork, don’t start over", "Share your trip as a scrapbook page. Others fork it and drop the best days into their own trip.",
     icon("fork", 30, 2), "grape", 4),
]

# (day, [(time, title, booked, tall)])
CALENDAR = [
    ("FRI 16", [("8:05", "Flight to LAX", True, False), ("11:00", "Check in", True, False), ("1:00", "Pier & rides", False, True)]),
    ("SAT 17", [("9:00", "Venice canals", False, False), ("11:00", "Boardwalk", False, True), ("2:30", "Bike the Strand", False, False)]),
    ("SUN 18", [("10:00", "Travel Town", False, True), ("4:00", "Observatory", False, False)]),
]


def _search_values(trip=SAMPLE_TRIP):
    return [
        ("from", "From", f"{trip.origin_name} ({trip.origin})"),
        ("to", "To", f"{trip.destination_name} ({trip.airports[0]})"),
        ("when", "When", f"{trip.depart:%a %b} {trip.depart.day} – {trip.return_:%a %b} {trip.return_.day}"),
        ("who", "Who", trip.summary),
    ]


def _field(name, label, value):
    return Label(Span(label, cls="field-label"),
                 Input(type="text", name=name, value=value, autocomplete="off"), cls="field")


def _search_card():
    return Form(
        *[_field(*f) for f in _search_values()],
        Button("Open my trip workspace", icon("arrow-right", 22, 2.6), type="submit", cls="btn btn-ink btn-go"),
        method="get", action="/plan", cls="search",
    )


def _trip_card(href, photo, alt, title, tag, tag_cls, days, pos):
    return A(
        Img(src=photo, alt=alt, width="500", height="260", loading="lazy"),
        Span(title, cls="tc-title"),
        Span(Span(tag, cls=f"tc-tag {tag_cls}"), Span(f"{days} days", cls="tc-tag tc-plain"), cls="tc-tags"),
        href=href, cls=f"trip-card {pos}",
    )


def _door_one():
    return Div(
        Span("DOOR ONE", cls="eyebrow"),
        H2("We’re going.", NotStr("<br>"), "Let’s book it."),
        _search_card(),
        P("Flights, stays, weather, news and one running total, side by side.", cls="promise"),
        cls="door door-one",
    )


def _door_two():
    sample = itineraries.get("sun-tacos-and-tide-pools")
    forks = sample.forks
    return Div(
        Span("DOOR TWO", cls="eyebrow"),
        H2("No plans yet?", NotStr("<br>"), "Fork a real one."),
        Div(
            _trip_card(f"/trips/{sample.slug}", itineraries.VENICE, "Venice Beach, Los Angeles", sample.title,
                       "Kid friendly", "fill-sun", len(sample.days), "tc-a"),
            # Fictional: there is no page for this trip yet, so it opens the discover list.
            _trip_card("/discover", itineraries.PIER, "Santa Monica Pier", "LA for two, slow mornings",
                       "Couple friendly", "fill-bubble", 4, "tc-b"),
            cls="cards",
        ),
        Span(Span(forks, cls="sticker-n"), "families forked", cls="fork-sticker ga-bob", style="--r:8deg"),
        A("Browse trips people loved", href="/discover", cls="btn btn-white"),
        cls="door door-two",
    )


def _underlined(word):
    return Span(word, NotStr(
        '<svg class="underline" viewBox="0 0 300 20" preserveAspectRatio="none" aria-hidden="true">'
        '<path d="M4 13 C 60 3, 118 19, 176 9 S 268 5, 296 11" stroke="currentColor" stroke-width="7" '
        'fill="none" stroke-linecap="round"/></svg>'), cls="accent-words")


def _features():
    return Section(
        H2("Not just a booking site"),
        Div(*[
            Div(Span(ic, cls=f"tile tile-{color}", style=f"--tilt:{tilt}deg"), H3(title), P(body), cls="feature")
            for title, body, ic, color, tilt in FEATURES
        ], cls="features"),
        cls="why ga-wrap",
    )


def _calendar():
    cols = []
    for day, items in CALENDAR:
        cols.append(Div(
            Span(day, cls="cal-day"),
            *[Span(Span(t, cls="cal-time"), Span(title, cls="cal-title"),
                   cls="cal-item" + (" booked" if booked else "") + (" tall" if tall else ""))
              for t, title, booked, tall in items],
            cls="cal-col",
        ))
    return Section(
        Div(
            Span("AFTER YOU BOOK", cls="eyebrow"),
            H2("Plan the fun part together"),
            P("Your flights and check-ins are already on the calendar. Invite family, drop in the fun stuff, "
              "leave notes like a meeting everyone actually enjoys."),
        ),
        Div(*cols, cls="cal", role="img", aria_label="A sample shared calendar for three days in Los Angeles"),
        cls="teaser teaser-cal ga-wrap",
    )


def _creators():
    return Section(
        Div(
            Span("FOR CREATORS", cls="eyebrow"),
            H2("Your vlog, as a trip people can fork"),
            P("Paste a YouTube or Instagram link. We draft the itinerary, you tidy it up, "
              "and every fork sends people back to your channel."),
            A("Turn a link into a trip", href="/creators", cls="btn btn-sun"),
        ),
        Div(Span("youtube.com/watch?v=our-la-family-week", cls="paste"),
            Span("Make it a trip", cls="paste-go"), cls="paste-row", aria_hidden="true"),
        cls="teaser teaser-creators on-ink ga-wrap",
    )


def register(app):
    @app.get("/")
    def home():
        return page(
            "",
            Section(
                H1("Fork a ", _underlined("getaway.")),
                P("Book with everything on one screen, plan it with the people you love, "
                  "then share a trip anyone can fork."),
                cls="headline ga-wrap",
            ),
            Section(_door_one(), _door_two(), cls="doors ga-wrap"),
            _features(),
            _calendar(),
            _creators(),
            head=HEAD,
        )
