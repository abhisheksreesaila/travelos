"""Landing page (F-060, Landing v2): one clear door.

Plan a trip leads; forking is one quiet line that scrolls to Community trips. Then the four features (each tile animates on hover and
focus), the shared calendar that plays itself, three community trips, and the creators panel. Design: docs/design/landing-v2.md.
"""

from fasthtml.common import A, Article, B, Button, Div, Form, H1, H2, H3, I, Img, Link, NotStr, P, Script, Section, Small, Span

from gitaway import hub, itineraries, session
from gitaway.catalog import SAMPLE_TRIP
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import home_art

HEAD = (Link(rel="stylesheet", href="/assets/css/landing.css"), Script(src="/assets/js/landing.js", defer=True))

FEATURES = [
    ("a-panes", home_art.PANES, "Everything side by side",
     "Flights, stays and cars next to weather, news, events and a map. No more twelve tabs."),
    ("a-total", home_art.TOTAL, "One honest total",
     "A running cost ledger shows what the whole trip costs, and how far you are from the cheapest combo."),
    ("a-together", home_art.TOGETHER, "Plan it together",
     "Invite family and friends to a shared calendar with notes, so everyone knows the plan."),
    ("a-fork", home_art.FORK, "Fork, don’t start over",
     "Copy the best days from a trip someone loved into your own, then change anything."),
]

# The four planners: (name, initial, background token)
PEOPLE = [("Mom", "M", "grape"), ("Dad", "D", "block-sunset"), ("Priya", "P", "sun"), ("Kid", "K", "bubble")]

# Booked items use the per-kind tint and ink pair (F-059): a flight is sky, a stay is grape. Each has a left edge and a lock.
# (day, [(slot id, tall, time, title, added by, tint, ink)]); an ink means a booked item
CALENDAR = [
    ("FRI 16", [(None, False, "8:05 AM", "Flight to LAX", "", "sky", "sky"),
                (None, False, "3:00 PM", "Check in", "", "grape", "grape"),
                ("s1", True, "5:00 PM", "Santa Monica Pier", "Priya", "sun", "")]),
    ("SAT 17", [("s2", False, "9:00 AM", "Venice canals", "Mom", "mint", ""),
                ("s3", True, "12:00 PM", "Tacos on Abbot Kinney", "Dad", "bubble", ""),
                ("s4", False, "5:00 PM", "Griffith Observatory", "Kid", "coral", "")]),
    ("SUN 18", [("s5", True, "10:00 AM", "Travel Town trains", "Kid", "sky", ""),
                ("s6", False, "2:00 PM", "Beach & tide pools", "Mom", "sun", ""),
                ("s7", False, "6:30 PM", "Sunset picnic", "Priya", "mint", "")]),
]


def _search_values(trip=SAMPLE_TRIP):
    return [
        ("from", "From", trip.origin_name),
        ("to", "To", trip.destination_name),
        ("when", "When", f"{trip.depart:%b} {trip.depart.day} – {trip.return_.day}"),
        ("who", "Who", trip.summary),
    ]


def _field(name, label, value):
    """A preview of the sample trip. Nothing to type here: the real form is /start."""
    return Div(Span(label, cls="field-label"), Span(value, cls="field-value"), cls="field", data_field=name)


def _plan_panel():
    return Section(
        Span(cls="blob", aria_hidden="true"),
        Div(
            H2(NotStr("We’re going.<br>Let’s book it."), id="plan-h"),
            P("Flights, stays, cars and the weather side by side, with one running total.", cls="promise"),
        ),
        Form(
            *[_field(*f) for f in _search_values()],
            Button("Plan a trip", icon("arrow-right", 22, 2.6), type="submit", cls="btn btn-ink btn-go"),
            method="get", action="/start", cls="search",
        ),
        cls="plan", aria_labelledby="plan-h",
    )


def _fork_line():
    stack = Span(*[I(style=f"background:var(--{c})") for c in ("block-pacific", "sun", "bubble")], cls="stack", aria_hidden="true")
    return Div(
        A(stack, Span("No plans yet? ", NotStr("<u>Fork a trip a real family took</u>"), " →"), href="#community-trips"),
        cls="forkline",
    )


def _underlined(word):
    return Span(word, NotStr(
        '<svg class="underline" viewBox="0 0 300 20" preserveAspectRatio="none" aria-hidden="true">'
        '<path d="M4 13 C 60 3, 118 19, 176 9 S 268 5, 296 11" stroke="currentColor" stroke-width="7" '
        'fill="none" stroke-linecap="round"/></svg>'), cls="accent-words")


def _hero():
    return Section(
        H1("Fork a ", _underlined("getaway.")),
        P(Span("fork", cls="word"), Span("verb", cls="pos"), Span("copy a trip someone really took, then make it yours", cls="def"), cls="gloss"),
        P("Book everything on one screen, plan it with the people you love, then share a trip anyone can fork.", cls="lede"),
        cls="hero ga-wrap",
    )


def _features():
    return Section(
        Div(H2("Not just a booking site", id="why-h"), cls="sec-head center"),
        Div(*[
            Article(Div(NotStr(art), cls=f"anim {cls}", aria_hidden="true"), H3(title), P(body), cls="feature", tabindex="0")
            for cls, art, title, body in FEATURES
        ], cls="features"),
        cls="sec ga-wrap", aria_labelledby="why-h",
    )


def _booked_item(time, title, tint, ink):
    return Div(Small(time), B(title), icon("lock", 12, 2.6, "lock"), cls="item booked", style=f"--t:var(--{tint}-tint);--k:var(--{ink}-ink)")


def _plan_item(time, title, by, tint):
    return Div(Small(time), B(title), Span(f"added by {by}", cls="by"), cls="item", style=f"--t:var(--{tint}-tint)")


def _calendar():
    cols = []
    for day, items in CALENDAR:
        slots = []
        for sid, tall, time, title, by, tint, ink in items:
            if ink:
                slots.append(Div(_booked_item(time, title, tint, ink), cls="slot"))
            else:
                slots.append(Div(_plan_item(time, title, by, tint), cls="slot tall on" if tall else "slot on", data_s=sid))
        cols.append(Div(Span(day, cls="day"), *slots, cls="col"))
    faces = Span(*[Span(initial, cls="face", style=f"background:var(--{color})") for _name, initial, color in PEOPLE], cls="faces", aria_hidden="true")
    return Section(
        Div(
            Div(
                Span("After you book", cls="eyebrow"),
                H2("Plan the fun part together", id="tog-h"),
                P("Your flights and check-ins are already on the calendar. Everyone adds what they’re excited about, and the days fill up."),
                Div(Span(cls="live", aria_hidden="true"), faces, Span("4 planning now"), cls="presence"),
                Button("Watch it again", type="button", cls="replay", id="replay"),
                cls="sec-head",
            ),
            Div(*cols, cls="cal", id="cal", role="img", data_people=",".join(f"{n}:{c}" for n, _i, c in PEOPLE),
                aria_label="A shared calendar for three days in Los Angeles. Four family members add plans: the pier, the observatory, "
                           "Venice canals, tacos, Travel Town and the beach."),
            cls="together",
        ),
        cls="sec ga-wrap", aria_labelledby="tog-h",
    )


_COVERS = {"sun-tacos-and-tide-pools": (itineraries.VENICE, "Venice Beach, Los Angeles"),
           "la-for-two-slow-mornings": (itineraries.PIER, "Santa Monica Pier")}
_GRADIENTS = ["linear-gradient(160deg,var(--block-pacific),var(--mint))", "linear-gradient(160deg,var(--bubble),var(--block-sunset))",
              "linear-gradient(160deg,var(--sun),var(--block-sunset))"]


def _community_card(trip, i):
    """A real itinerary. Photos are the CC0 area photos; a trip without one gets a colour wash instead."""
    keys = hub.tag_keys(trip)
    label, tint, _ic = hub.TAGS[keys[0]] if keys else ("Easy pace", "sky", "")
    cover = _COVERS.get(trip.slug)
    pic = Img(src=cover[0], alt=cover[1], width="400", height="260", loading="lazy", cls="ph") if cover else \
        Span(cls="ph", style=f"background:{_GRADIENTS[i % len(_GRADIENTS)]}", aria_hidden="true")
    return A(
        pic, B(trip.title),
        Span(Span(label, cls="tag", style=f"background:var(--{tint}-tint)"), Span(f"{len(trip.days)} days", cls="tag"),
             Span(f"{trip.forks} forks", cls="tag"), cls="meta"),
        href=f"/trips/{trip.slug}", cls="trip", style=f"--r:{-1 if i % 2 == 0 else 1}deg",
    )


def _community():
    trips = list(itineraries.ITINERARIES.values())[:3]
    return Section(
        Div(
            Span("Community trips", cls="eyebrow"),
            H2("Not sure where yet? Borrow a trip that worked.", id="community-h"),
            P("Real trips shared by travelers and creators. Fork one, keep the days you like, and change the rest."),
            cls="sec-head",
        ),
        Div(*[_community_card(t, i) for i, t in enumerate(trips)], cls="trip-row"),
        A("Browse all community trips →", href="/community", cls="more"),
        cls="sec ga-wrap", id="community-trips", aria_labelledby="community-h",
    )


def _trail_card(gradient, title, sub):
    return Div(Span(cls="ph", style=f"background:{gradient}"), Div(B(title), Span(sub)), cls="trail-card")


def _creators():
    return Section(
        Div(
            Div(
                Span("For travelers with stories", cls="eyebrow"),
                H2("Been somewhere wonderful? Leave a trail.", id="cr-h"),
                P("Your vlog, your notes, the little taco place nobody knows about. Turn them into a trip another family can follow, "
                  "and make someone’s first time there a little easier."),
                P("“The world is a book, and those who do not travel read only one page.”",
                  NotStr("<cite>Attributed to Saint Augustine</cite>"), cls="quote"),
                A("Share a trip you loved →", href="/creators", cls="btn-sun"),
                cls="left",
            ),
            Div(
                _trail_card("linear-gradient(160deg,var(--block-pacific),var(--mint))", "Our LA family week", "From a YouTube vlog · 5 days"),
                _trail_card("linear-gradient(160deg,var(--sun),var(--coral))", "Forked by the Rao family", "Kept 3 days, added Disneyland"),
                _trail_card("linear-gradient(160deg,var(--grape),var(--bubble))", "Forked by Sam & Jo", "“The tide pools were the best morning”"),
                cls="trail", aria_hidden="true",
            ),
            cls="creators on-ink",
        ),
        cls="sec ga-wrap", aria_labelledby="cr-h",
    )


def footer_links():
    """The links that left the landing's header. Sign in only while signed out."""
    links = [("Community trips", "/community"), ("For creators", "/creators")]
    return links if session.request_traveler() else [*links, ("Sign in", session.signin_href())]


def register(app):
    @app.get("/")
    def home():
        return page(
            "",
            _hero(),
            Div(_plan_panel(), _fork_line(), cls="ga-wrap"),
            _features(),
            _calendar(),
            _community(),
            _creators(),
            head=HEAD, nav=False, footer_links=footer_links(),
        )
