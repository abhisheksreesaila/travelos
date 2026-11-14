"""The cover (F-227, "one stage": docs/decisions.md D-426 on, over cover v5's D-410..): what a signed-out visitor sees at /.

The story of the brief (docs/briefs/unified-booking.md "The cover tells this story"), in the founder's pick of the F-221 designs (cover A, one stage):

    the opening   "Compare the whole trip. Choose it together.", two doors and a band of the place art
    the stage     one product frame stays pinned (position: sticky) while three parts scroll past beside it (a laptop) or under it (a phone);
                  the frame cross-fades between them:
                    1 Compare                  a sentence types itself, the matrix fills, one square lights up, the calendar wears the weather
                    2 Plan it together         hearts with faces land on the square, the thread beside it, the owner's "This one"
                    3 Leave a trail            the trip as a card ready to post; a creator's trip opens into its own matrix
    the close     the headline again and Start a trip, then the footer.

The header is the site's way in (founder, 2026-11-13): For creators, Community trips and Plan a trip (`layout.NAV`), then Sign in. Start a trip and
Plan a trip are one door, `layout.plan_href()`: sign in, then Where to? (/start), where a trip already booked comes in too (D-458).

No jitter by construction (D-427): the frame is CSS sticky; assets/js/cover.js only sets data-part on the stage from an IntersectionObserver and adds
.go to a part the first time it shows. cover.css does the rest on the --motion-* tokens: the outgoing screen fades, the incoming one settles in on
the Liquid spring and its small moments play once on the same springs (D-444). No script writes a transform, nothing reads layout while scrolling,
nothing moves with the scroll. Under reduced motion the screens swap with a plain fade, every moment at rest; on a screen under 600 px tall,
without the script or with ?still, every part is a still beside (or under) its words. The made-up families, prices and trips are an illustration shown in production too (D-270,
D-383), said in the first part, where the first of them appears, and in the footer.

The frame's screens are drawn here as HTML from the F-221 artboard (docs/design/trip-matrix/cover-a.html) until the matrix ships (F-222): SCREENS is
the seam, one drawer per part; swap a drawer for a real screenshot then.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path

from fasthtml.common import A, B, Div, Em, Figure, Footer, H1, H2, Header, Link, Main, Nav, NotStr, P, Script, Section, Small, Span, Title

from gitaway import session, weather
from gitaway.icons import icon
from gitaway.layout import NAV, brand, mode_switch, plan_href, preview, seo_meta, styles

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
TITLE = "Compare the whole trip. Choose it together."
LINE = ("Compare the whole trip. ", "Choose it together.")
LEDE = "Flights, stays and the drive, added up for every place and date you might go. Then the family hearts the one they love."
OG_IMAGE = "/assets/cover/og.jpg"
# the phone layout: cover.css uses this same query
PHONE_Q = "(max-width: 720px)"
SHORT = {"For creators": "Creators", "Community trips": "Community"}      # the phone's header row (D-458)
DISCLOSURE = "Every family, price and trip on this page is made up, to show how it works. The places and their weather are real."

# the three parts: (number, its name, its headline, what it says, an id to link to). A headline is its ink words and its soft words, each a run of
# phrases; a phrase with a beat (1 to 3) is marked in the part's colour at the moment the screen shows the same thing (D-457): the words and the
# screen say it together.
PARTS = (
    ("1", "Compare", ((("Every place,", 1), " ", ("every date.", 2), " "), (("One total each.", 3),)),
     "Say it once. The flight, the stay and the airport drive are added up for every square, and the one you didn’t think to ask for lights up.",
     "compare"),
    ("2", "Plan it together", ((("Hearts,", 1), " not group texts. "), (("One person decides.", 2),)),
     "Share it with the family and the friends coming along. Everyone hearts what they love and talks on the square; the owner taps “This one”.",
     "together"),
    ("3", "Leave a trail", ((("Leave a trail", 1), " ", ("others can follow.", 2)), ()),
     "Your trip becomes a card ready to post, with a link back. A creator’s trip opens into a matrix of its own, so readers plan it for their dates.",
     "trail"),
)
TRAIL_SUB = "Bloggers and vloggers welcome"

# ---------- the sample the frame draws (docs/design/trip-matrix/tm.js): a family of 4 from SFO in December ----------
SENTENCE = (("A family of", False), ("4,", True), ("from", False), ("SFO,", True), ("somewhere warm,", True), ("Dec 12 to 16,", True),
            ("give or take", False), ("a day.", True))
WINDOWS = ((11, "Fri"), (12, "Sat"), (13, "Sun"))                  # each a 4-night start: Dec 11-15, 12-16, 13-17 (weekdays of 2026, checked)
# a row: its id, name, the art it wears (one or two places), its totals for the three windows (cents-free dollars: a drawn sample)
ROWS = (
    ("sd", "San Diego", ("san-diego",), (2260, 2140, 2080)),
    ("la", "Los Angeles", ("los-angeles",), (1910, 1840, 1870)),
    ("lasd", "LA + San Diego", ("los-angeles", "san-diego"), (2280, 2190, 2150)),
    ("ps", "Palm Springs", ("palm-springs",), (1720, 1690, 1740)),
)
FIND = ("lasd", 1)                                                  # the square that lights up: LA + San Diego, Dec 12-16
FIND_LINE = "LA + San Diego, $50 more than San Diego alone."
FIND_SUB = "Two nights each, a 2-hour drive down the coast."
STRIP = range(11, 18)                                               # the calendar under the matrix: Dec 11 to 17, the trip Dec 12 to 16
SAN_DIEGO = weather.CATALOG_STATIONS["sd"]                          # its typical weather is NOAA's (normals.json), never invented
# the family (drawn faces: skin, hair, a style; a guest is an outlined initial) and the creator
PEOPLE = {
    "ana": ("Ana", "#C68B65", "#2B1B14", "long"), "dev": ("Dev", "#A9714B", "#1A1210", "short"), "leela": ("Leela", "#C68B65", "#3A2418", "bun"),
    "sam": ("Sam", None, None, "guest"), "maya": ("Maya", "#E0AC86", "#6B3F22", "curly"),
}
HAIR = {
    "long": '<path d="M7 18c0-7 4-10.5 9-10.5S25 11 25 18v8H7z"/>',
    "short": '<path d="M8 15c0-5 3.5-7.5 8-7.5s8 2.5 8 7.5c-2-2.6-5-3.4-8-3.4s-6 .8-8 3.4z"/>',
    "bun": '<circle cx="16" cy="6.5" r="3.4"/><path d="M7.6 16c0-5.4 3.6-8 8.4-8s8.4 2.6 8.4 8c-2.4-3-5.6-3.8-8.4-3.8S10 13 7.6 16z"/>',
    "curly": '<circle cx="9.5" cy="13" r="3.4"/><circle cx="13" cy="9.6" r="3.6"/><circle cx="18" cy="9.4" r="3.6"/><circle cx="22.3" cy="12.6" r="3.4"/>'
             '<circle cx="8.6" cy="17.6" r="3"/><circle cx="23.4" cy="17.6" r="3"/>',
}
THREAD = (("leela", "The beach!!"), ("dev", "Two hours of coast is fine."), ("sam", "We could join for the LA part."))
SHORTLIST = (("1 · LA + San Diego", "4 hearts"), ("2 · San Diego, Dec 13", "1 heart"), ("3 · Palm Springs", "1 heart"))
CREATOR_MINI = (1640, 1520, 1710)
# the opening's band of places: (place, weather)
BAND = (("san-diego", "sun"), ("los-angeles", "sun"), ("lake-tahoe", "snow"), ("new-york", "cloud"), ("palm-springs", "sun"))
ART = ("san-diego", "los-angeles", "lake-tahoe", "new-york", "palm-springs")       # every place drawn here (scripts/cover_art.py PLACES)


@lru_cache(maxsize=1)
def _boot():
    return (ASSETS / "js" / "cover_boot.js").read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def _sprite():
    return (ASSETS / "cover" / "art.svg").read_text(encoding="utf-8").strip()


def money(n):
    return f"${n:,}"


def art(place, wx="sun", cls=""):
    """A place in its drawing (scripts/cover_art.py): the sky is the box's gradient, the scene one <use> of the sprite, its colours the place's
    palette for the mode, its weather a data-wx."""
    return Span(NotStr(f'<svg viewBox="0 0 480 240" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">'
                       f'<use href="#pa-{place}" width="480" height="240"/></svg>'),
                cls=f"pa {cls}".strip(), data_art=place, data_wx=wx)


def _pair(places, cls):
    return Span(*[art(p) for p in places], cls=f"{cls}{' duo' if len(places) > 1 else ''}")


def face(pid):
    """A drawn face (F-221 tm.js face()): skin and hair, no colour code; a guest is an outlined initial."""
    name, skin, hair, style = PEOPLE[pid]
    if style == "guest":
        return Span(name[0], cls="cv-face guest", title=f"{name} (guest)")
    shape = HAIR[style]
    head = (f'<g fill="{hair}">{shape}</g>' if style == "long" else "") + f'<circle cx="16" cy="17" r="8" fill="{skin}"/>' + (
        f'<g fill="{hair}">{shape}</g>' if style != "long" else
        f'<path d="M8.4 15.6C9 11 12 9 16 9s7 2 7.6 6.6c-2.6-2.4-5-3-7.6-3s-5 .6-7.6 3z" fill="{hair}"/>')
    return Span(NotStr('<svg viewBox="0 0 32 32" aria-hidden="true" focusable="false"><path d="M5 32c1.5-6 6-8.6 11-8.6S25.5 26 27 32z" fill="#8E8E98"/>'
                       f'{head}<circle cx="13.2" cy="17.6" r="1" fill="#1A1210"/><circle cx="18.8" cy="17.6" r="1" fill="#1A1210"/>'
                       '<path d="M13.6 20.6q2.4 1.8 4.8 0" stroke="#1A1210" stroke-width="1.1" fill="none" stroke-linecap="round"/></svg>'),
                cls="cv-face", title=name)


def _heart_face(pid, k):
    return Span(face(pid), Span(icon("heart", 10, 2), cls="cv-hb"), cls="cv-hf", style=f"--h:{k}")


def _bar(ico, words, tag):
    return Div(icon(ico, 14), Small(words), Span(cls="cv-sp"), Span(tag, cls="cv-sample"), cls="cv-fbar")


# ---------- the frame's three screens (the F-222 seam: SCREENS) ----------

def _sentence():
    words, k = [], 0
    for text, key in SENTENCE:
        for w in text.split(" "):
            words.append(Span(w, cls="cv-w k" if key else "cv-w", style=f"--w:{k}"))
            words.append(" ")
            k += 1
    return P(*words[:-1], cls="cv-sent")


def _matrix():
    cells, k = [Span(cls="cv-hd")], 0
    cells += [Span(Span(f"Dec {d}–{d + 4}", cls="cv-wide"), Span(f"{dow} {d}", cls="cv-narrow"), cls="cv-hd") for d, dow in WINDOWS]
    for rid, name, places, totals in ROWS:
        cells.append(Span(_pair(places, "cv-th"), Span(name), cls="cv-pl"))
        for j, total in enumerate(totals):
            lit = (rid, j) == FIND
            cells.append(Span(money(total), *((Span("+$50", cls="cv-plus"),) if lit else ()), cls="cv-c lit" if lit else "cv-c", style=f"--i:{k}"))
            k += 1
    return Div(*cells, cls="cv-mx")


def _strip():
    st = weather.station(SAN_DIEGO)
    days = [weather.normal_day(st, date(2026, 12, d)) for d in STRIP]
    cells = [Span(Span(f"{x.date:%a}"), B(str(x.date.day)), icon({"sun": "sun", "cloud": "cloud", "rain": "rain", "snow": "snow"}[x.condition], 16),
                  Span(f"{x.high_f}°"), cls="cv-day in" if 12 <= x.date.day <= 16 else "cv-day") for x in days]
    return Div(Div(*cells, cls="cv-strip"),
               Small(icon("sun", 14), f"{st.name} · {days[1].label} · {days[1].word.lower()}", cls="cv-typ"), cls="cv-stripw")


def screen_compare():
    return (_bar("spark", "Your trip, compared", "Sample prices"), _sentence(), _matrix(),
            Div(_pair(("los-angeles", "san-diego"), "cv-th cv-dth"), Span(B(FIND_LINE), Span(FIND_SUB, cls="cv-dsub")),
                Span(money(ROWS[2][3][1]), cls="cv-num"), cls="cv-disc"),
            _strip())


def screen_together():
    hearts = [_heart_face(p, k) for k, p in enumerate(("ana", "leela", "dev", "sam"))]
    return (
        _bar("users", "Ana’s family · 4 of you + 1 guest", "Sample family"),
        Div(_pair(("los-angeles", "san-diego"), "cv-sqart"),
            Div(Span(B("LA + San Diego"), Small("Dec 12–16 · flight, stay and the drive")), Span(money(2190), cls="cv-num"), cls="cv-sqbody"),
            Div(*hearts, Span("Ana, Leela, Dev and Sam (guest)", cls="cv-who"), cls="cv-hearts"), cls="cv-sq"),
        Div(*[Div(face(p), Span(B(PEOPLE[p][0]), " ", text), cls="cv-bub", style=f"--b:{k}") for k, (p, text) in enumerate(THREAD)], cls="cv-thread"),
        Div(*[Span(B(name), Span(icon("heart", 12), n, cls="cv-hn")) for name, n in SHORTLIST], cls="cv-short"),
        Div(Span(icon("check", 16), "This one", cls="cv-pill"), Small("Ana decides. Hearts are advice."), cls="cv-decide"),
    )


def screen_trail():
    card = Div(_pair(("los-angeles", "san-diego"), "cv-igart"),
               Div(Span("Family of 4 · Dec 12–16", cls="cv-lab"), B("LA + San Diego"), Span("SFO → LAX · drive 2h · SAN → SFO", cls="cv-route"),
                   Span(icon("link", 13), "Plan this trip on GitAway", cls="cv-lk"), cls="cv-igmeta"), cls="cv-ig")
    creator = Div(
        Div(art("lake-tahoe", "snow", "cv-cart"),
            Div(face("maya"), Span(B("Maya’s Tahoe trip"), Small("Opens as a matrix for readers")), cls="cv-ctop"),
            Div(*[Span(money(n), cls="lit" if k == 1 else None) for k, n in enumerate(CREATOR_MINI)], cls="cv-mini"),
            Small("From your airport, for your dates"), cls="cv-crow"),
        Div(Div(icon("link", 16), Span(B("Every post links back"), Small("Readers plan the same trip in one tap")), cls="cv-ctop"), cls="cv-crow cv-more"),
        cls="cv-creator")
    return (_bar("share", "Ready to post", "Sample trip"), Div(card, creator, cls="cv-trailrow"))


# F-222 seam: when the matrix ships, a part's drawer can become a real screenshot (a <picture> in the frame); the frame, the cross-fade and the
# words stay as they are.
SCREENS = {"1": screen_compare, "2": screen_together, "3": screen_trail}
ALT = {
    "1": "An illustration with made-up sample prices: the sentence “A family of 4, from SFO, somewhere warm, Dec 12 to 16”, a matrix of four places "
         "by three dates with one total each, LA + San Diego lit up at $2,190, $50 more than San Diego alone, and San Diego’s typical December weather.",
    "2": "An illustration of a made-up family: Ana, Leela, Dev and their guest Sam heart LA + San Diego, talk about it beside the square, and Ana "
         "decides with “This one”.",
    "3": "An illustration of a made-up trip: LA + San Diego as a card ready to post, and Maya’s Tahoe trip, a made-up creator’s, opening as a "
         "matrix for its readers.",
}


def _frame():
    return Div(Div(*[Figure(*SCREENS[n](), cls=f"cv-L cv-L{n}", data_n=n, aria_label=ALT[n]) for n in SCREENS], cls="cv-frame"), cls="cv-fwrap")


def _phrases(run):
    return [Span(x[0], cls=f"cv-hl b{x[1]}") if isinstance(x, tuple) else x for x in run]


def _part(n, name, two, text, anchor):
    ink, soft = two
    extra = ()
    if n == "1":
        extra = (P(DISCLOSURE, cls="cv-note ga-fine"),)
    if n == "3":
        extra = (A("For creators", icon("arrow-right", stroke=2), href="/for-creators", cls="cv-btn tonal cv-small"),)
    return Div(Div(P(f"0{n} · {name}", cls="cv-n"), H2(*_phrases(ink), *((Em(*_phrases(soft)),) if soft else ())),
                   *((Span(TRAIL_SUB, cls="cv-subpill"),) if n == "3" else ()), P(text, cls="cv-say"), *extra, cls="cv-card"),
               cls=f"cv-ch cv-ch{n}", data_n=n, id=anchor)


def _hero():
    return Section(
        H1(LINE[0], Em(LINE[1])), P(LEDE, cls="cv-lede"),
        Div(A("Start a trip", icon("arrow-right", stroke=2), href=plan_href(), cls="cv-btn fill big"),
            A("See how it works", href="#compare", cls="cv-btn tonal big"), cls="cv-ctas"),
        Div(*[art(p, wx) for p, wx in BAND], cls="cv-band", aria_hidden="true"),
        cls="cv-hero")


def _stage():
    return Section(_frame(), Div(*[_part(*p) for p in PARTS], cls="cv-chs"), cls="cv-stage", data_part="1", aria_label="How it works")


def _close():
    return Section(
        H2(LINE[0], Em(LINE[1])),
        Div(A("Start a trip", icon("arrow-right", stroke=2), href=plan_href(), cls="cv-btn fill big"), cls="cv-ctas"),
        cls="cv-close", id="your-turn")


def _footer(links):
    return Footer(
        Span("GitAway", cls="ga-brand-name"),
        P("Compare the whole trip and choose it together. You book on each booking site, under its terms; GitAway never takes payment."),
        Nav(*[A(label, href=href) for label, href in [*links, ("Privacy", "/privacy"), ("Terms", "/terms")]], aria_label="More"),
        mode_switch(),
        P("Early preview · the families, prices and trips on this page are made up, to show how it works; the places are real and so is their "
          "typical weather (NOAA climate normals, 1991 to 2020). The drawings are GitAway’s own.", cls="cv-fine ga-fine"),
        cls="cv-foot",
    )


def page(footer_links, drive=()):
    """The whole cover document. `footer_links` are the landing's (home.footer_links); `drive` the Travelpayouts Drive tag when it is switched on (home._drive)."""
    head = styles(Link(rel="stylesheet", href="/assets/css/cover.css"),
                  *seo_meta(f"GitAway · {TITLE}", LEDE, OG_IMAGE), *drive,
                  Script(NotStr(_boot())), Script(src="/assets/js/cover.js", defer=True))
    return (
        Title(f"GitAway · {TITLE}"),
        *head,
        NotStr(_sprite()),
        A("Skip to the story", href="#main", cls="ga-skip"),
        Header(brand(), Div(preview(), cls="cv-tag"),
               Nav(*[A(Span(label, cls="cv-nl-full"), Span(SHORT.get(label, label), cls="cv-nl-short", aria_hidden="true"), href=plan_href() if href == "/start" else href,
                       aria_label=label) for label, href in NAV], cls="cv-nav", aria_label="Main"),
               A("Sign in", href=session.signin_href(), cls="cv-btn tonal"), cls="cv-top"),
        Main(_hero(), _stage(), _close(), id="main", data_phone=PHONE_Q),
        _footer(footer_links),
    )
