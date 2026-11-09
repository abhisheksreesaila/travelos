"""The cover (F-206; cover v5, docs/decisions.md D-410 on, over v4's D-400 to D-406 and v3's D-380 to D-392): what a signed-out visitor sees at /.

v3's story, copy and honesty, filmed as a camera over the app's real screens (assets/cover/shots/, made by scripts/cover_shots.py). Each chapter is a
stage: a tall <section> whose screen stays (position: sticky) while the scroll moves the camera inside it, and each stage has its own colour:

    0  Top          the line over a laptop and a phone showing the cockpit, tilted; the scroll sets them down and the story starts
    1  Book         the booking screen in a frame: zoom to the flight beside the stay, glide over the weather and the drive, pull back to the
                    whole page; the partners show as plain chips (Aviasales and Klook live, the rest "Soon": D-411)
    2  Head start   other families' Tahoe trips deal in, one is imported and turns into Lena and Sam's trip
    3  With you     the cockpit dives into a day, then the screen plays a short loop of the day, Ask and the family chat (D-412)
    4  Tips         a drawn Tahoe: the roads draw themselves, pins drop, each with its tip
    5  Trail        the published trail slides in
    6  Creators     a blog post turns into a GitAway trip
    and the close: a snowy Tahoe forest that opens out behind "Take a trip. Leave a trail." and the doors, then the footer (D-410).

assets/js/cover.js is the conductor (one rAF read of the scroll, each stage's progress 0..1, transforms and opacity only); without it, under reduced
motion, or on a screen under 560 px tall every stage is a still, readable block. The made-up families, trips, tips and thanks are an illustration
shown in production too (D-270, D-383) and the story says so where they first appear and in the footer. No 3D world (D-380).
Off production <main> carries data-debug="1" (the review tools' ?scene= and ?p= switches); production never renders it.
"""

from functools import lru_cache
from pathlib import Path

from fasthtml.common import A, Article, B, Div, Em, Figure, Footer, H1, H2, H3, Header, I, Img, Li, Link, Main, Meta, Nav, NotStr, Ol, P, Picture, Script, Section, Source, Span, Title, Ul

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
THEME = (("#E6EEF9", "light"), ("#070B14", "dark"))            # the browser bar: the opening's winter sky by day, its night by night (cover.css)
DISCLOSURE = "This trip is an example: the families, trips and tips in this story are made up. The places are real."
# the close's photo (D-410): a snowy forest at Lake Tahoe, CC0 (assets/photos/CREDITS.md): the laptop's file, its size, the phone's portrait cut, credit
CLOSE_PHOTO = ("/assets/photos/tahoe-winter-forest-1440.webp", 1440, 1012, "/assets/photos/tahoe-winter-forest-phone-660.webp", "A snowy forest at Lake Tahoe",
               "Todd Diemer")
# the made-up blog post's picture: South Lake Tahoe from Heavenly in February, CC0 (assets/photos/CREDITS.md)
POST_PHOTO = ("/assets/photos/tahoe-winter-heavenly-720.webp", 720, 300, "South Lake Tahoe from Heavenly", "Blake Everett")

# each screenshot's encoded widths (scripts/cover_shots.py WIDTHS, CROP_W), its size in css px, and what it shows, for a screen reader
SHOT_W = {"phone": (600,), "wide": (960, 1440)}
SHOT_SIZE = {"phone": (390, 844), "wide": (1440, 900)}
BOOK_W = (960, 1600)
BOOK_SIZE = (960, 817)
ALT = {
    "book": "GitAway's booking page for Lake Tahoe, Feb 5 to 9, two adults and two kids: flights into Reno, stays, a car and things to do, each a search on the "
            "booking site's own pages, beside the typical weather for those days, the cost so far and the 1 h 23 min drive from Reno.",
    "trail": "Lena and Sam's published trip, Five snowy days at Lake Tahoe, day by day, with a button to make it yours.",
    "cockpit": "The trip's cockpit: each day of the Tahoe trip as a ticket, today's open with when to leave, the drive to Taylor Creek, the weather and a paper map of the lake.",
    "day": "Monday at Tahoe in GitAway: pancakes at the cabin, snowshoeing at Taylor Creek, lunch in town and what is up next.",
    "ask": "Ask GitAway showing a change before it is applied: snowshoeing moved after lunch and hot chocolate at Taylor Creek added.",
    "family": "The family's chat on the trip: Sam booked the sled hill and the snow comes after six.",
    "creators": "GitAway for creators: paste a blog post, a YouTube link or an Instagram caption and it becomes a trip families can take.",
}

# the booking stage: each beat's words and the parts of the screenshot it speaks of (x, y, w, h as fractions of BOOK_SIZE, read off the crop).
# With the third the camera pulls back to the whole page: PULLBACK leads its words.
BEATS = (
    ("A cheaper flight, a pricier cabin? See both at once and decide.",
     ((0.0167, 0.011, 0.6365, 0.2766), (0.0167, 0.2999, 0.6365, 0.2093))),
    ("The weather for your dates and the drive from the airport, right where you book.",
     ((0.6698, 0.011, 0.3125, 0.4798), (0.6698, 0.8409, 0.3125, 0.1432))),
    ("You book on the booking site itself. Your bookings stay yours.", ()),
)
PULLBACK = "Everything in one view."
# where the camera goes, in order (cover.js keys them to the scroll): the flight beside the stay, the weather, the drive
CAMERA = {"fs": (0.0167, 0.011, 0.6365, 0.5), "wx": (0.6698, 0.011, 0.3125, 0.4798), "drive": (0.6698, 0.8409, 0.3125, 0.1432),
          "fs-phone": (0.0167, 0.011, 0.47, 0.4982)}      # a phone's narrow window: the flight and the stay's left half, bigger
# the spotlights: the flight with the stay, the weather, the drive (the rest of the page dims)
SPOTS = {"fs": (0.0167, 0.011, 0.6365, 0.4982), "wx": BEATS[1][1][0], "drive": BEATS[1][1][1]}
# where a family books (D-411): only the partners GitAway has today are shown live (Aviasales for flights, Klook for stays, cars and things to do);
# the rest are said to be coming, in a muted chip with "Soon". Never name a live partner here that is not one: (name, kind, icon, what it sells, live)
PARTNERS = (
    ("Aviasales", "flight", "plane", "Flights", True),
    ("Klook", "stay", "bed", "Stays, cars, things to do", True),
    ("Expedia", "", "", "", False),
    ("Booking.com", "", "", "", False),
    ("More sites", "", "", "", False),
)
# the cockpit's open day, where the camera dives in to reach the day (x, y, w, h of the wide and the phone screenshot)
TODAY = {"wide": (0.2056, 0.528, 0.3139, 0.45), "phone": (0.04, 0.197, 0.92, 0.42)}
# after the dive into the day, the screen loops through these real screenshots on its own (D-412: a short loop, not a scroll step each)
LOOP = ("day", "ask", "family")

# the made-up families' Tahoe trips (D-381: the recommendation is not built yet, so it is drawn, in the app's own look): title, by, days, stops
# (name, kind), thanks
TRIPS = (
    ("Five snowy days at Lake Tahoe", "Lena & Sam", 5, (("Heavenly", "tix"), ("Taylor Creek", "see"), ("Tahoe City", "food")), 212),
    ("Tahoe in three days, kids in tow", "the Okafors", 3, (("Emerald Bay", "see"), ("Sand Harbor", "see"), ("Spooner Lake", "fun")), 148),
    ("A slow long weekend on the lake", "Priya & Dev", 3, (("Kings Beach", "see"), ("Tahoe City", "food"), ("Cabin", "stay")), 67),
)
# what a search won't tell you (D-382: made up, plausible, local): icon, tip, who and when, how many found it useful, where its pin drops on the
# drawn lake (cover.css draws the lake in a 400 x 500 box), in the order the roads reach them
TIPS = (
    ("snow", "Chain controls on US-50 at Echo Summit this morning. Chains on before Meyers.", "the Okafors · 2 h ago", 31, (92, 452)),
    ("car", "Heavenly’s Stagecoach lot fills by 8:30. After that, the shuttle from Stateline.", "Sam · this week", 19, (268, 402)),
    ("tree", "Locals’ sledding at Spooner, free. Bring your own sled.", "a Tahoe local · this week", 42, (318, 236)),
    ("map", "Emerald Bay Rd closes in heavy snow; take 89 the other way, through Tahoe City.", "Priya · yesterday", 24, (118, 342)),
)
# the drawn lake (a 400 x 500 box): its shore, US-50 from Echo Summit through South Lake Tahoe and Stateline to Spooner, and 89 up the west shore
LAKE = "M200 40 C 262 40 300 92 306 160 C 312 228 300 300 292 352 C 284 398 254 416 214 418 C 170 420 150 398 142 368 C 128 318 114 260 118 190 C 122 110 146 40 200 40 Z"
ROAD_50 = "M60 470 C 92 452 120 440 150 436 C 190 430 220 424 262 404 C 292 390 304 360 312 330 C 318 300 320 268 318 236"
ROAD_89 = "M150 436 C 132 412 118 380 118 342 C 116 300 108 250 110 200 C 112 160 120 128 140 104"
TOWNS = (("Echo Summit", 30, 488), ("South Lake Tahoe", 160, 462), ("Stateline", 280, 432), ("Tahoe City", 70, 92), ("Spooner", 330, 222))
KIND_ICON = {"tix": "ticket", "see": "sight", "food": "food", "fun": "star", "stay": "bed"}
# the stickers that float round the opening and the close: a kind and its icon (Direction A's kind colours)
STICKERS = (("flight", "plane"), ("stay", "bed"), ("car", "car"), ("food", "food"), ("wx", "snow"), ("tix", "ticket"))


@lru_cache(maxsize=1)
def _boot():
    return (ASSETS / "js" / "cover_boot.js").read_text(encoding="utf-8").strip()


def debug():
    """Off production the page turns on the review tools' switches (?beat=, ?p=); production never does."""
    return not auth.production()


def shot_srcs(name, layout, mode):
    """The files of one screenshot for a layout and mode, smallest first (scripts/cover_shots.py names them)."""
    if name == "book":
        return [f"{SHOTS}/book-wide-{mode}-{w}.webp" for w in BOOK_W]
    return [f"{SHOTS}/{name}-{layout}-{mode}-{w}.webp" for w in SHOT_W[layout]]


def _srcset(name, layout, mode):
    widths = BOOK_W if name == "book" else SHOT_W[layout]
    return ", ".join(f"{src} {w}w" for src, w in zip(shot_srcs(name, layout, mode), widths))


SIZES = {"phone": "18.75rem", "wide": "min(75rem, 88vw)", "book": "(max-width: 720px) 250vw, 120vw", "laptop": "(max-width: 720px) 1px, 60vw",
         "pocket": "(max-width: 720px) 80vw, 16rem"}


def _img(name, layout, alt, eager=False):
    w, h = BOOK_SIZE if name == "book" else SHOT_SIZE[layout]
    lay = "wide" if name == "book" else layout
    return Img(src=shot_srcs(name, lay, "light")[0], srcset=_srcset(name, lay, "light"), alt=alt, width=str(w), height=str(h),
               loading="eager" if eager else "lazy", decoding="async", **({"fetchpriority": "high"} if eager else {}))


def _shot(name, alt=None, eager=False):
    """A real screenshot in the visitor's layout (the phone's on a phone, the laptop's elsewhere; the booking crop serves both), light or dark by the
    system; cover.js follows the site's own switch too (from the data-* srcsets). Loaded only as it nears the screen."""
    alt = ALT[name] if alt is None else alt
    if name == "book":
        sets = {f"data-{m}-{lay}": _srcset(name, "wide", m) for m in ("light", "dark") for lay in ("phone", "wide")}
        im = _img(name, "wide", alt, eager)
        im.attrs["sizes"] = SIZES["book"]
        return Picture(Source(media=DARK, srcset=_srcset(name, "wide", "dark"), sizes=SIZES["book"]), im,
                       cls="cv-shot", data_shot=name, data_sizes_phone=SIZES["book"], data_sizes_wide=SIZES["book"], **sets)
    phone_dark = f"{DARK} and {PHONE_Q}"
    sets = {f"data-{m}-{lay}": _srcset(name, lay, m) for m in ("light", "dark") for lay in ("phone", "wide")}
    im = _img(name, "wide", alt, eager)
    im.attrs["sizes"] = SIZES["wide"]
    return Picture(
        Source(media=phone_dark, srcset=_srcset(name, "phone", "dark"), sizes=SIZES["phone"]),
        Source(media=DARK, srcset=_srcset(name, "wide", "dark"), sizes=SIZES["wide"]),
        Source(media=PHONE_Q, srcset=_srcset(name, "phone", "light"), sizes=SIZES["phone"]),
        im, cls="cv-shot", data_shot=name, data_sizes_phone=SIZES["phone"], data_sizes_wide=SIZES["wide"], **sets,
    )


def _device_shot(name, layout, alt="", eager=False):
    """A screenshot that always shows one layout, whatever the window (the laptop in a laptop, the phone in a phone): the laptop's is never
    downloaded on a phone (its frame is not drawn there)."""
    sizes = SIZES["laptop" if layout == "wide" else "pocket"]
    sets = {f"data-{m}-{lay}": _srcset(name, layout, m) for m in ("light", "dark") for lay in ("phone", "wide")}
    im = _img(name, layout, alt, eager)
    im.attrs["sizes"] = sizes
    if not alt:
        im.attrs["aria-hidden"] = "true"
    return Picture(Source(media=DARK, srcset=_srcset(name, layout, "dark"), sizes=sizes), im,
                   cls="cv-shot", data_shot=name, data_layout=layout, data_sizes_phone=sizes, data_sizes_wide=sizes, **sets)


def _eyebrow(text):
    return P(I(), text, cls="cv-eyebrow")


def _stage(i, name, key, length, stick, *after, cls=""):
    """One chapter: a tall section whose screen (the stick) stays while `length` screens of scroll pass under it."""
    return Section(Div(*stick, cls="cv-stick"), *after, cls=f"cv-stage cv-{key} {cls}".strip(), data_stage=key, data_scene=str(i), data_name=name,
                   id=name.lower().replace(" ", "-"), style=f"--len:{length}")


def _pct(b):
    x, y, w, h = b
    return f"left:{x * 100:.2f}%;top:{y * 100:.2f}%;width:{w * 100:.2f}%;height:{h * 100:.2f}%"


def _spot(key):
    """A spotlight on one part of the booking screenshot: a ring round it and the rest of the page dimmed (one solid shadow: cheap to draw at any
    zoom, D-403)."""
    return Span(cls="cv-spot", data_spot=key, style=_pct(SPOTS[key]))


def _sticker(kind, ico, k):
    return Span(icon(ico, 22, 2.2), cls=f"cv-stk k-{kind}", data_k=str(k), aria_hidden="true")


def _two(ink, hue):
    """A two-tone headline: the ink part and the chapter's colour."""
    return (ink, Em(hue))


# ---------- 0. the opening ----------

def _hero():
    return _stage(0, "Top", "hero", 1.3, (
        Div(H1(*_two("Take a trip. ", "Leave a trail.")), P(LEDE, cls="cv-lede"),
            Div(A("Plan a trip", icon("arrow-right", stroke=2), href="/start", cls="cv-btn fill big"), cls="cv-ctas"), cls="cv-hero-copy"),
        Div(Div(Div(Div(_device_shot("cockpit", "wide", ALT["cockpit"]), cls="cv-screen"), Span(cls="cv-base"), cls="cv-laptop"),
                Div(Div(_device_shot("cockpit", "phone", "", eager=True), cls="cv-screen"), cls="cv-phone"),
                cls="cv-sway"),
            *[_sticker(kind, ico, k) for k, (kind, ico) in enumerate(STICKERS)],
            cls="cv-devices"),
        P("Scroll", NotStr('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                           '<path d="m6 9 6 6 6-6"/></svg>'), cls="cv-hint", aria_hidden="true"),
    ))


# ---------- 1. book with everything in view ----------

def _book():
    words = [P(*((Span(PULLBACK, cls="cv-beat-all"), " ") if k == 2 else ()), text, cls="cv-beat", data_beat=str(k)) for k, (text, _) in enumerate(BEATS)]
    cam = {f"data-cam-{k}": ",".join(f"{v:g}" for v in r) for k, r in CAMERA.items()}
    return _stage(1, "Book", "book", 3.5, (
        Div(cls="cv-field", aria_hidden="true"),
        Div(_eyebrow("1 · Book with everything in view"), H2(*_two("See the whole trip before you pay for ", "any of it.")),
            Div(*words, cls="cv-beats", aria_live="polite"), _partners(), cls="cv-copy"),
        Div(Div(_shot("book"), *[_spot(k) for k in SPOTS], cls="cv-cam"), cls="cv-lens", **cam),
    ))


def _partners():
    """Where a family books today, honestly (D-411): the live partners in their kind's colour, the coming ones muted with a small "Soon"."""
    chips = [Li(icon(ico, 18, 2.2), B(name), Span(what, cls="cv-chip-what"), cls=f"cv-chip k-{kind}") if live else
             Li(Span(name, cls="cv-chip-name"), Span("Soon", cls="cv-soon"), cls="cv-chip soon")
             for name, kind, ico, what, live in PARTNERS]
    return Ul(*chips, cls="cv-partners", aria_label="Where you book: Aviasales and Klook today; Expedia, Booking.com and more sites soon")


# ---------- 2. a head start ----------

def _trips_card():
    """Trips others took to Lake Tahoe: drawn in GitAway's own look, made up (the recommendation is not built yet, D-381)."""
    rows = []
    for k, (title, by, days, stops, thanks) in enumerate(TRIPS):
        rows.append(Li(
            Div(B(title), Span(f"by {by} · {days} days", cls="cv-mute"),
                Ul(*[Li(icon(KIND_ICON[kind], 16, 2), name, cls=f"k-{kind}") for name, kind in stops], cls="cv-stops"),
                cls="cv-trip-t"),
            Div(Span(icon("heart", 16, 2.2), f"{thanks} thanks", cls="cv-mute cv-thx"),
                Span(Span(icon("fork", 18, 2.2), "Import", cls="cv-fb-a"),
                     *((Span(icon("check", 18, 2.4), "Imported", cls="cv-fb-b", aria_hidden="true"),) if k == 0 else ()),
                     cls="cv-fake-btn" + (" ink" if k == 0 else "")),
                cls="cv-trip-a"),
            cls="cv-trip" + (" pick" if k == 0 else ""), data_k=str(k)))
    return Figure(
        Div(Span(icon("users", 18, 2), cls="cv-ill-ico"), Div(B("Trips others took to Lake Tahoe"), Span("Families who went in winter", cls="cv-mute")), cls="cv-ill-head"),
        Ul(*rows, cls="cv-trips"),
        cls="cv-ill cv-tripsfig", aria_label="An illustration: three made-up families' Lake Tahoe trips, each with an Import button.",
    )


def _head():
    return _stage(2, "Head start", "head", 2.5, (
        Div(_eyebrow("2 · A head start, then it comes with you"), H2(*_two("Don’t start from a ", "blank page.")),
            P("Families already did Tahoe in three days. Take their trip, make it yours.", cls="cv-say"),
            P(DISCLOSURE, cls="cv-disc"), cls="cv-copy"),
        Div(_trips_card(), cls="cv-deal"),
        Div(Div(_shot("trail"), cls="cv-frame"), P("Lena and Sam’s trip, ready to make yours.", cls="cv-cap"), cls="cv-morph"),
    ))


# ---------- 3. then it comes with you ----------

FEATURES = (
    ("cockpit", "Every day on one line.", ("When to leave, the drive and the weather, for each day of the trip.",)),
    ("day", "Each day, to the hour.", ("What’s now, what’s next, and how far it is.",)),
    ("ask", "Change it by asking.", ("“Move snowshoeing after lunch.” You see the new day first; ", B("nothing changes until you tap Apply."))),
    ("family", "Everyone on the same page.", ("One chat for the trip. Sam books the sled hill and everyone sees it.",)),
)


def _with():
    feats = [Article(H3(h3), P(*text, cls="cv-say"), cls="cv-feat", data_feat=name) for name, h3, text in FEATURES]
    laptop = [Div(_device_shot(name, "wide", ALT[name]), cls="cv-layer", data_layer=name) for name, *_ in FEATURES]
    phone = [Div(_device_shot(name, "phone", ALT[name]), cls="cv-layer", data_layer=name) for name, *_ in FEATURES]
    today = {f"data-today-{k}": ",".join(f"{v:g}" for v in r) for k, r in TODAY.items()}
    return _stage(3, "With you", "with", 3, (
        Div(H2(*_two("Then the plan ", "comes with you.")), Div(*feats, cls="cv-feats"), cls="cv-copy"),
        Div(Div(Div(*laptop, cls="cv-screen"), Span(cls="cv-base"), cls="cv-laptop"),
            Div(Div(*phone, cls="cv-screen"), cls="cv-phone"),
            cls="cv-devices", data_loop=",".join(LOOP), **today),
    ))


# ---------- 4. things a search won't tell you ----------

def _map():
    """A drawn Lake Tahoe (not a map: a picture of the idea), its two roads and a numbered pin for each tip."""
    towns = "".join(f'<text x="{x}" y="{y}" font-size="15">{n}</text>' for n, x, y in TOWNS)
    pins = "".join(f'<g class="cv-mpin" data-k="{k}" transform="translate({x} {y})"><g class="cv-mpin-in"><path d="M0 0 C -4 -10 -16 -16 -16 -28 A 16 16 0 1 1 16 -28 C 16 -16 4 -10 0 0 Z"/>'
                   f'<text x="0" y="-27" font-size="16">{k + 1}</text></g></g>' for k, (*_, (x, y)) in enumerate(TIPS))
    return NotStr(
        '<svg class="cv-lake" viewBox="0 0 400 500" role="presentation" aria-hidden="true">'
        f'<path class="cv-lake-water" d="{LAKE}"/><text class="cv-lake-name" x="212" y="236" font-size="24">Lake Tahoe</text>'
        f'<path class="cv-road cv-road-bed" d="{ROAD_50}"/><path class="cv-road cv-road-bed" d="{ROAD_89}"/>'
        f'<path class="cv-road cv-draw" data-road="50" pathLength="1" d="{ROAD_50}"/><path class="cv-road cv-draw" data-road="89" pathLength="1" d="{ROAD_89}"/>'
        f'<g class="cv-towns">{towns}</g>{pins}</svg>')


def _tips():
    cards = Ol(*[Li(Span(str(k + 1), cls="cv-tip-n"), Span(icon(ico, 20, 2), cls="cv-tip-ico"), Div(P(text), Span(who, cls="cv-mute")),
                    Span(icon("up", 16, 2.2), str(n), cls="cv-mute cv-up"), cls="cv-tip", data_k=str(k))
                 for k, (ico, text, who, n, _) in enumerate(TIPS)], cls="cv-tips")
    return _stage(4, "Tips", "tips", 2.5, (
        Div(H2(*_two("Things a search ", "won’t tell you.")), P("Fresh, local, from families who were just there.", cls="cv-say"), cls="cv-copy"),
        Figure(Div(_map(), cls="cv-mapbox"),
               Div(Div(Span(icon("spark", 18, 2), cls="cv-ill-ico"), Div(B("Tips for your Tahoe trip"), Span("From families there this week", cls="cv-mute")), cls="cv-ill-head"),
                   cards, cls="cv-ill cv-tipsfig"),
               cls="cv-tipsmap", aria_label="An illustration: made-up tips from families at Lake Tahoe this week, pinned on a drawing of the lake."),
    ))


# ---------- 5. leave a trail ----------

def _trail():
    card = Figure(
        Div(Span(icon("flag", 18, 2), cls="cv-ill-ico"), Div(B("Your trail: Tahoe, our way"), Span("Published · 4 days · public", cls="cv-mute")), cls="cv-ill-head"),
        Div(Div(Span("12", cls="cv-num"), Span("families took your trip this winter", cls="cv-big-l"), Span(icon("heart", 22, 2.4), cls="cv-beat-heart", aria_hidden="true"),
                cls="cv-big"), cls="cv-bigwrap"),
        Ul(Li(Span(icon("heart", 18, 2), cls="cv-tip-ico"), Div(P("“Spooner was the best afternoon of our trip. Thank you!”"), Span("the Garcías", cls="cv-mute")), cls="cv-tip cv-quote"),
           cls="cv-tips"),
        cls="cv-ill cv-trailfig", aria_label="An illustration: a made-up published trip and the thanks it got.",
    )
    return _stage(5, "Leave a trail", "trail", 1.5, (
        Div(_eyebrow("3 · Leave a trail"), H2(*_two("Home again? ", "Leave a trail.")),
            P("Publish your trip and the next family starts where you finished.", cls="cv-say"), cls="cv-copy"),
        Div(card, cls="cv-deal"),
    ))


# ---------- 6. for creators ----------

def _creators():
    post = Figure(
        Div(I(), I(), I(), Span("lenaandsam.blog", cls="cv-url"), cls="cv-post-bar"),
        Div(Img(src=POST_PHOTO[0], alt="", width=str(POST_PHOTO[1]), height=str(POST_PHOTO[2]), loading="lazy", decoding="async"), cls="cv-post-pic"),
        Div(B("Five snowy days at Lake Tahoe"), Span("A travel blog · 9 min read", cls="cv-mute"),
            *[I(cls="cv-line") for _ in range(4)], cls="cv-post-t"),
        cls="cv-post", aria_label="An illustration: a made-up travel blog post about Lake Tahoe.",
    )
    return _stage(6, "Creators", "creators", 2, (
        Div(_eyebrow("For travel writers"), H2(*_two("You already wrote ", "the post.")),
            P("Give it one more audience: travel only, five minutes, good karma.", cls="cv-say"),
            Div(A("Bring your post", icon("arrow-right", stroke=2), href="/for-creators", cls="cv-btn fill"), cls="cv-ctas"), cls="cv-copy"),
        Div(post, cls="cv-deal"),
        Div(Div(_shot("creators"), cls="cv-frame"), Span("Now a trip", cls="cv-stamp", aria_hidden="true"), cls="cv-morph"),
    ))


def scenes():
    return (_hero(), _book(), _head(), _with(), _tips(), _trail(), _creators())


def _close(card, links):
    src, w, h, phone_src, place, by = CLOSE_PHOTO
    photo = Picture(Source(media=PHONE_Q, srcset=phone_src), Img(src=src, alt="", width=str(w), height=str(h), loading="lazy", decoding="async"))
    end = Section(
        Div(Div(photo, cls="cv-photo"),
            *[_sticker(kind, ico, k) for k, (kind, ico) in enumerate(STICKERS)],
            Div(H2(*_two("Take a trip. ", "Leave a trail.")),
                Div(A("Plan a trip", icon("arrow-right", stroke=2), href="/start", cls="cv-btn fill big"),
                    *((A("See trips people shared", href="/community", cls="cv-btn tonal"),) if showcase.community_open() else ()),
                    cls="cv-ctas"), cls="cv-last"),
            P(f"{place} · photo {by}, CC0", cls="cv-credit"),
            cls="cv-stick"),
        cls="cv-stage cv-end", data_stage="end", style="--len:1",
    )
    return Div(end, Div(card, _footer(links), cls="cv-after"), cls="cv-close", data_scene="7", data_name="Your turn", id="your-turn")


def _footer(links):
    return Footer(
        Span("GitAway", cls="ga-brand-name"),
        P("Plan a trip together, share it, and follow trips other families shared. Booking always happens on the booking site, under its terms, never here."),
        Nav(*[A(label, href=href) for label, href in [*links, ("Privacy", "/privacy"), ("Terms", "/terms")]], aria_label="More"),
        P("Early preview · the families, trips, tips and thanks in this story are made up; the screens are GitAway’s own. Lake Tahoe is real: map data © ",
          A("OpenStreetMap contributors", href="https://www.openstreetmap.org/copyright"), ", elevation from USGS 3DEP via AWS Terrain Tiles. "
          f"The photos are CC0, from Wikimedia Commons: the snowy forest at Lake Tahoe by {CLOSE_PHOTO[5]} and {POST_PHOTO[3]} by {POST_PHOTO[4]}.",
          cls="cv-fine"),
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
        Div(Span(cls="cv-rail-fill"), cls="cv-rail", aria_hidden="true"),
        Main(*scenes(), id="main", data_phone=PHONE_Q, data_debug="1" if debug() else None),
        _close(card, footer_links),
    )
