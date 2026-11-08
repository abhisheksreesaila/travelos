"""The cover (F-206; cover v3, docs/decisions.md D-380 to D-392): what a signed-out visitor sees at /.

One centred story that sells first: "Take a trip. Leave a trail." and one button, then GitAway's three promises, each painted with the app's real
screens (assets/cover/shots/, made by scripts/cover_shots.py) in the visitor's layout and mode:

    1  Book with everything in view: /plan's booking lanes and the panel beside them, one screenshot, three beats that ring (on a phone, zoom into)
       the part they speak of while the screen stays put
    2  A head start, then it comes with you: other families' Tahoe trips (illustrated: that feature is not built yet), the trip to take, then the
       cockpit, the day, Ask and the family chat, then the local tips a search won't tell you (illustrated)
    3  Leave a trail: travellers publish, creators give their post one more audience

and the close: the line again, the doors, Plan it for me when it is offered (D-262), the footer.

The families, trips, tips and thanks are an illustration shown in production too (D-270, extended by D-383), and the story says so where they first
appear and in the footer. No 3D world any more (D-380): the page loads no three.js and no world.js (cover3d/ and assets/js/cover/ stay in the repo,
unused). assets/js/cover.js does the calm reveals, the booking tour and the screenshots' mode; without it every word and picture still shows.
Off production <main> carries data-debug="1" (the review tools' ?beat= switch); production never renders it.
"""

from functools import lru_cache
from pathlib import Path

from fasthtml.common import A, Article, B, Div, Em, Figure, Footer, H1, H2, H3, Header, I, Img, Li, Link, Main, Meta, Nav, NotStr, P, Picture, Script, Section, Source, Span, Title, Ul

from gitaway import auth, session, showcase
from gitaway.icons import icon
from gitaway.layout import brand, preview, seo_meta, styles

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
TITLE = "Take a trip. Leave a trail."
LEDE = "Everything you need to decide, a head start on the plan, and the people who’ve been there."
SUBHEAD = LEDE
OG_IMAGE = "/assets/cover/og.jpg"
SHOTS = "/assets/cover/shots"
# the phone's screenshots and the phone layout: cover.css uses this same query
PHONE_Q = "(max-width: 720px)"
DARK = "(prefers-color-scheme: dark)"
THEME = (("#F2F2F5", "light"), ("#000000", "dark"))            # the browser bar: the cover's grey by day, black by night (cover.css --cv-bg)
DISCLOSURE = "This trip is an example: the families, trips and tips in this story are made up. The places are real."

# each screenshot's encoded widths (scripts/cover_shots.py WIDTHS, CROP_W), its size in css px, and what it shows, for a screen reader
SHOT_W = {"phone": (600,), "wide": (960, 1440)}
SHOT_SIZE = {"phone": (390, 844), "wide": (1440, 900)}
BOOK_W = (960, 1600)
BOOK_SIZE = (960, 817)
ALT = {
    "book": "GitAway's booking page for Lake Tahoe, Feb 5 to 9, two adults and two kids: flights into Reno, stays, a car and things to do, each a search on the "
            "partner's own site, beside the typical weather for those days, the cost so far and the 1 h 23 min drive from Reno.",
    "trail": "Lena and Sam's published trip, Five snowy days at Lake Tahoe, day by day, with a button to make it yours.",
    "cockpit": "The trip's cockpit: each day of the Tahoe trip as a ticket, today's open with when to leave, the drive to Taylor Creek, the weather and a paper map of the lake.",
    "day": "Monday at Tahoe in GitAway: pancakes at the cabin, snowshoeing at Taylor Creek, lunch in town and what is up next.",
    "ask": "Ask GitAway showing a change before it is applied: snowshoeing moved after lunch and hot chocolate at Taylor Creek added.",
    "family": "The family's chat on the trip: Sam booked the sled hill and the snow comes after six.",
    "creators": "GitAway for creators: paste a blog post, a YouTube link or an Instagram caption and it becomes a trip families can take.",
}

# the booking tour: each beat's words, the parts of the screenshot it rings (x, y, w, h as fractions of BOOK_SIZE, read off the crop), and on a
# phone the part it zooms to
BEATS = (
    ("A cheaper flight, a pricier cabin? See both at once and decide.",
     ((0.0167, 0.011, 0.6365, 0.2766), (0.0167, 0.2999, 0.6365, 0.2093)), (0.0167, 0.011, 0.47, 0.4982)),
    ("The weather for your dates and the drive from the airport, right where you book.",
     ((0.6698, 0.011, 0.3125, 0.4798), (0.6698, 0.8409, 0.3125, 0.1432)), (0.6698, 0.011, 0.3125, 0.9731)),
    ("Book on the sites you trust. Your bookings stay yours.",
     ((0.078, 0.116, 0.201, 0.051), (0.078, 0.368, 0.213, 0.051), (0.078, 0.450, 0.188, 0.042), (0.078, 0.614, 0.204, 0.051)), (0.0625, 0.104, 0.36, 0.57)),
)

# the made-up families' Tahoe trips (D-381: the recommendation is not built yet, so it is drawn, in the app's own look): title, by, days, stops
# (name, kind), thanks
TRIPS = (
    ("Five snowy days at Lake Tahoe", "Lena & Sam", 5, (("Heavenly", "tix"), ("Taylor Creek", "see"), ("Tahoe City", "food")), 212),
    ("Tahoe in three days, kids in tow", "the Okafors", 3, (("Emerald Bay", "see"), ("Sand Harbor", "see"), ("Spooner Lake", "fun")), 148),
    ("A slow long weekend on the lake", "Priya & Dev", 3, (("Kings Beach", "see"), ("Tahoe City", "food"), ("Cabin", "stay")), 67),
)
# what a search won't tell you (D-382: made up, plausible, local): icon, tip, who and when, how many found it useful
TIPS = (
    ("snow", "Chain controls on US-50 at Echo Summit this morning. Chains on before Meyers.", "the Okafors · 2 h ago", 31),
    ("map", "Emerald Bay Rd closes in heavy snow; take 89 the other way, through Tahoe City.", "Priya · yesterday", 24),
    ("car", "Heavenly’s Stagecoach lot fills by 8:30. After that, the shuttle from Stateline.", "Sam · this week", 19),
    ("tree", "Locals’ sledding at Spooner, free. Bring your own sled.", "a Tahoe local · this week", 42),
)
KIND_ICON = {"tix": "ticket", "see": "sight", "food": "food", "fun": "star", "stay": "bed"}


@lru_cache(maxsize=1)
def _boot():
    return (ASSETS / "js" / "cover_boot.js").read_text(encoding="utf-8").strip()


def debug():
    """Off production the page turns on the review tools' switch (?beat=); production never does."""
    return not auth.production()


def shot_srcs(name, layout, mode):
    """The files of one screenshot for a layout and mode, smallest first (scripts/cover_shots.py names them)."""
    if name == "book":
        return [f"{SHOTS}/book-wide-{mode}-{w}.webp" for w in BOOK_W]
    return [f"{SHOTS}/{name}-{layout}-{mode}-{w}.webp" for w in SHOT_W[layout]]


def _srcset(name, layout, mode):
    widths = BOOK_W if name == "book" else SHOT_W[layout]
    return ", ".join(f"{src} {w}w" for src, w in zip(shot_srcs(name, layout, mode), widths))


SIZES = {"phone": "18.75rem", "wide": "min(75rem, 88vw)", "book": "(max-width: 720px) 250vw, min(75rem, 88vw)"}


def _shot(name):
    """A real screenshot: the phone's on a phone and the laptop's elsewhere (the booking crop serves both), light or dark by the system; cover.js
    follows the site's own switch too (from the data-* srcsets). Loaded only as it nears the screen."""
    if name == "book":
        w, h = BOOK_SIZE
        sets = {f"data-{m}-{lay}": _srcset(name, "wide", m) for m in ("light", "dark") for lay in ("phone", "wide")}
        return Picture(Source(media=DARK, srcset=_srcset(name, "wide", "dark"), sizes=SIZES["book"]),
                       Img(src=shot_srcs(name, "wide", "light")[0], srcset=_srcset(name, "wide", "light"), sizes=SIZES["book"], alt=ALT[name],
                           width=str(w), height=str(h), loading="lazy", decoding="async"),
                       cls="cv-shot", data_shot=name, data_sizes_phone=SIZES["book"], data_sizes_wide=SIZES["book"], **sets)
    w, h = SHOT_SIZE["wide"]
    phone_dark = f"{DARK} and {PHONE_Q}"
    sets = {f"data-{m}-{lay}": _srcset(name, lay, m) for m in ("light", "dark") for lay in ("phone", "wide")}
    return Picture(
        Source(media=phone_dark, srcset=_srcset(name, "phone", "dark"), sizes=SIZES["phone"]),
        Source(media=DARK, srcset=_srcset(name, "wide", "dark"), sizes=SIZES["wide"]),
        Source(media=PHONE_Q, srcset=_srcset(name, "phone", "light"), sizes=SIZES["phone"]),
        Img(src=shot_srcs(name, "wide", "light")[0], srcset=_srcset(name, "wide", "light"), sizes=SIZES["wide"], alt=ALT[name], width=str(w), height=str(h),
            loading="lazy", decoding="async"),
        cls="cv-shot", data_shot=name, data_sizes_phone=SIZES["phone"], data_sizes_wide=SIZES["wide"], **sets,
    )


def _eyebrow(text):
    return P(I(), text, cls="cv-eyebrow")


def _scene(i, name, *content, cls=""):
    return Section(*content, cls=f"cv-sc {cls}".strip(), data_scene=str(i), data_name=name, id=name.lower().replace(" ", "-"))


def _rv(*content, cls="", tag=Div, **kw):
    """Something that fades in as it reaches the screen (cover.js; shown at once without it, or with reduced motion)."""
    return tag(*content, cls=f"cv-rv {cls}".strip(), **kw)


def _box(b):
    x, y, w, h = b
    return f"left:{x * 100:.2f}%;top:{y * 100:.2f}%;width:{w * 100:.2f}%;height:{h * 100:.2f}%"


def _tour():
    """Beat by beat over one screenshot: the words change, the screen stays, a ring (on a phone, a zoom) shows the part they speak of."""
    beats = [P(text, cls="cv-beat" + (" on" if k == 0 else ""), data_beat=str(k)) for k, (text, _, _) in enumerate(BEATS)]
    rings = [Span(cls="cv-ring" + (" on" if k == 0 else ""), data_beat=str(k), style=_box(b)) for k, (_, boxes, _) in enumerate(BEATS) for b in boxes]
    zooms = {f"data-zoom-{k}": ",".join(f"{v:g}" for v in z) for k, (_, _, z) in enumerate(BEATS)}
    return Div(
        Div(Div(*beats, cls="cv-beats", aria_live="polite"),
            Div(Div(_shot("book"), *rings, cls="cv-lens-in"), cls="cv-lens", **zooms),
            Ul(*[Li(Span(str(k + 1)), cls="on" if k == 0 else None, data_beat=str(k)) for k in range(len(BEATS))], cls="cv-steps", aria_hidden="true"),
            cls="cv-tour-pin"),
        cls="cv-tour", style=f"--beats:{len(BEATS)}",
    )


def _feature(name, h3, text):
    """One of the tools that come with you: a short headline, a line, the real screen."""
    return _rv(H3(*h3), P(*text, cls="cv-say"), Div(_shot(name), cls="cv-frame"), cls="cv-feat", tag=Article)


def _trips_card():
    """Trips others took to Lake Tahoe: drawn in GitAway's own look, made up (the recommendation is not built yet, D-381)."""
    rows = []
    for k, (title, by, days, stops, thanks) in enumerate(TRIPS):
        rows.append(Li(
            Div(B(title), Span(f"by {by} · {days} days", cls="cv-mute"),
                Ul(*[Li(icon(KIND_ICON[kind], 16, 2), name, cls=f"k-{kind}") for name, kind in stops], cls="cv-stops"),
                cls="cv-trip-t"),
            Div(Span(icon("heart", 16, 2.2), f"{thanks} thanks", cls="cv-mute cv-thx"),
                Span(icon("fork", 18, 2.2), "Import", cls="cv-fake-btn" + (" ink" if k == 0 else "")), cls="cv-trip-a"),
            cls="cv-trip" + (" pick" if k == 0 else "")))
    return Figure(
        Div(Span(icon("users", 18, 2), cls="cv-ill-ico"), Div(B("Trips others took to Lake Tahoe"), Span("Families who went in winter", cls="cv-mute")), cls="cv-ill-head"),
        Ul(*rows, cls="cv-trips"),
        cls="cv-ill", aria_label="An illustration: three made-up families' Lake Tahoe trips, each with an Import button.",
    )


def _tips_card():
    """Local, fresh, from people who were just there: drawn and made up (D-382)."""
    return Figure(
        Div(Span(icon("spark", 18, 2), cls="cv-ill-ico"), Div(B("Tips for your Tahoe trip"), Span("From families there this week", cls="cv-mute")), cls="cv-ill-head"),
        Ul(*[Li(Span(icon(ico, 20, 2), cls="cv-tip-ico"), Div(P(text), Span(who, cls="cv-mute")), Span(icon("up", 16, 2.2), str(n), cls="cv-mute cv-up"), cls="cv-tip")
             for ico, text, who, n in TIPS], cls="cv-tips"),
        cls="cv-ill", aria_label="An illustration: made-up tips from families at Lake Tahoe this week.",
    )


def _thanks_card():
    """Home again: your trail and the thanks it brings (made up)."""
    return Figure(
        Div(Span(icon("flag", 18, 2), cls="cv-ill-ico"), Div(B("Your trail: Tahoe, our way"), Span("Published · 4 days · public", cls="cv-mute")), cls="cv-ill-head"),
        Ul(Li(Span(icon("fork", 18, 2), cls="cv-tip-ico"), Div(P(B("12 families"), " took your trip this winter")), cls="cv-tip"),
           Li(Span(icon("heart", 18, 2), cls="cv-tip-ico"), Div(P("“Spooner was the best afternoon of our trip. Thank you!”"), Span("the Garcías", cls="cv-mute")), cls="cv-tip"),
           cls="cv-tips"),
        cls="cv-ill cv-ill-small", aria_label="An illustration: a made-up published trip and the thanks it got.",
    )


def scenes():
    return (
        _scene(0, "Top",
               Div(H1("Take a trip. ", Em("Leave a trail.")), P(LEDE, cls="cv-lede"),
                   Div(A("Plan a trip", icon("arrow-right", stroke=2), href="/start", cls="cv-btn fill big"), cls="cv-ctas"),
                   cls="cv-open-in"),
               P("Scroll", NotStr('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                                  '<path d="m6 9 6 6 6-6"/></svg>'), cls="cv-hint", aria_hidden="true"),
               cls="cv-open"),
        # 1. Book with everything in view
        _scene(1, "Book",
               _rv(_eyebrow("1 · Book with everything in view"), H2("See the whole trip before you pay for ", Em("any of it.")), cls="cv-head"),
               _tour()),
        # 2. A head start, then it comes with you
        _scene(2, "Head start",
               _rv(_eyebrow("2 · A head start, then it comes with you"), H2("Don’t start from a ", Em("blank page.")),
                   P("Families already did Tahoe in three days. Take their trip, make it yours.", cls="cv-say"), cls="cv-head"),
               _rv(_trips_card(), P(DISCLOSURE, cls="cv-disc"), cls="cv-ill-wrap"),
               _rv(Div(_shot("trail"), cls="cv-frame"), P("Lena and Sam’s trip, ready to make yours.", cls="cv-cap"), cls="cv-shotwrap")),
        _scene(3, "With you",
               _rv(H2("Then the plan ", Em("comes with you.")), cls="cv-head"),
               _feature("cockpit", ("Every day on one line.",), ("When to leave, the drive and the weather, for each day of the trip.",)),
               _feature("day", ("Each day, to the hour.",), ("What’s now, what’s next, and how far it is.",)),
               _feature("ask", ("Change it by asking.",), ("“Move snowshoeing after lunch.” You see the new day first; ", B("nothing changes until you tap Apply."))),
               _feature("family", ("Everyone on the same page.",), ("One chat for the trip. Sam books the sled hill and everyone sees it.",))),
        _scene(4, "Tips",
               _rv(H2("Things a search ", Em("won’t tell you.")), P("Fresh, local, from families who were just there.", cls="cv-say"), cls="cv-head"),
               _rv(_tips_card(), cls="cv-ill-wrap")),
        # 3. Leave a trail
        _scene(5, "Leave a trail",
               _rv(_eyebrow("3 · Leave a trail"), H2("Home again? ", Em("Leave a trail.")),
                   P("Publish your trip and the next family starts where you finished.", cls="cv-say"), cls="cv-head"),
               _rv(_thanks_card(), cls="cv-ill-wrap")),
        _scene(6, "Creators",
               _rv(_eyebrow("For travel writers"), H2("You already wrote ", Em("the post.")),
                   P("Give it one more audience: travel only, five minutes, good karma.", cls="cv-say"),
                   Div(A("Bring your post", icon("arrow-right", stroke=2), href="/for-creators", cls="cv-btn tonal"), cls="cv-ctas"), cls="cv-head"),
               _rv(Div(_shot("creators"), cls="cv-frame"), cls="cv-shotwrap")),
    )


def _close(card, links):
    return Div(
        _rv(H2("Take a trip. ", Em("Leave a trail.")),
            Div(A("Plan a trip", icon("arrow-right", stroke=2), href="/start", cls="cv-btn fill big"),
                *((A("See trips people shared", href="/community", cls="cv-btn tonal"),) if showcase.community_open() else ()),
                cls="cv-ctas"), cls="cv-last"),
        card,
        _footer(links),
        cls="cv-close", data_scene="7", data_name="Your turn", id="your-turn",
    )


def _footer(links):
    return Footer(
        Span("GitAway", cls="ga-brand-name"),
        P("Plan a trip together, share it, and follow trips other families shared. Booking always happens on the partner’s site, under their terms, never here."),
        Nav(*[A(label, href=href) for label, href in [*links, ("Privacy", "/privacy"), ("Terms", "/terms")]], aria_label="More"),
        P("Early preview · the families, trips, tips and thanks in this story are made up; the screens are GitAway’s own. Lake Tahoe is real: map data © ",
          A("OpenStreetMap contributors", href="https://www.openstreetmap.org/copyright"), ", elevation from USGS 3DEP via AWS Terrain Tiles.", cls="cv-fine"),
        cls="cv-foot",
    )


def page(footer_links, drive=()):
    """The whole cover document. `footer_links` are the landing's (home.footer_links); `drive` the Travelpayouts Drive tag when it is switched on (home._drive)."""
    from gitaway.itinerary_view import plan_for_me_card
    card = plan_for_me_card("Rather not plan it yourself?", "/plan-for-me", "pf-card cv-pf")
    head = styles(Link(rel="stylesheet", href="/assets/css/cover.css"), *((Link(rel="stylesheet", href="/assets/css/planforme.css"),) if card else ()),
                  *seo_meta(f"GitAway · {TITLE}", SUBHEAD, OG_IMAGE), *drive,
                  Script(NotStr(_boot())), Script(src="/assets/js/cover.js", defer=True))
    return (
        Title(f"GitAway · {TITLE}"),
        *(Meta(name="theme-color", content=c, media=f"(prefers-color-scheme: {m})") for c, m in THEME),
        *(h for h in head if not (h.tag == "meta" and h.attrs.get("name") == "theme-color")),        # the site's cream bar is not the cover's
        A("Skip to the story", href="#main", cls="ga-skip"),
        Header(brand(), Div(preview(), cls="cv-tag"), A("Sign in", href=session.signin_href(), cls="cv-btn tonal"), cls="cv-top"),
        Main(*scenes(), id="main", data_phone=PHONE_Q, data_debug="1" if debug() else None),
        _close(card, footer_links),
    )
