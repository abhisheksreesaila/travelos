"""The cover (F-206, rebuilt on the agreed story: docs/decisions.md D-354 to D-363): what a signed-out visitor sees at /.

One travel story, told in four acts with a plain headline per scene: (1) why GitAway exists (planning a trip feels like homework), (2) booking with
everything in view, (3) the planning tools (the trip's cockpit, the day, Ask, the family chat), (4) leave a trail (publish it; others follow it;
creators), closing on "Take a trip. Leave a trail." The family is the made-up Lena and Sam on a real Lake Tahoe trip (D-270), and every feature
is shown by a real screenshot of the app (assets/cover/shots/, made by scripts/cover_shots.py), the phone's at phone widths and the laptop's on a
laptop, in the visitor's light or dark.

Two kinds of scene: windows, where the 3D Tahoe world shows through behind a pinned card (the guidebook of the why, the lake their trip draws on,
the pier at sunset, the fork tree at the end), and paper scenes, opaque, with the words beside the screenshot. Each window says which stretch of
the world's own timeline it plays (`data-world="from,dwell,to"`: the world's chapter c at its rest is 2c), so the world itself (cover3d/src) is
unchanged. assets/js/cover.js is the conductor; only it ever fetches three.js, the world and the terrain, so reduced motion, no WebGL and weak
phones download none of it. home.py serves this to signed-out visitors only. Off production <main> carries data-debug="1", which turns on the
capture and measuring tools' URL switches and the world's window.__cover; production never renders it.
"""

import hashlib
from functools import lru_cache
from pathlib import Path

from fasthtml.common import A, Article, B, Canvas, Div, Em, Footer, H1, H2, Header, I, Img, Li, Link, Main, Meta, Nav, NotStr, P, Picture, Script, Section, Source, Span, Title, Ul

from gitaway import auth, session, showcase
from gitaway.icons import icon
from gitaway.layout import brand, preview, seo_meta, styles

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
TITLE = "Take a trip. Leave a trail."
SUBHEAD = "Share the whole trip, not just the photos, so the next family can follow it, make it theirs, and say thanks."
OG_IMAGE = "/assets/cover/og.jpg"
WORLD = "/assets/js/cover/world.js"
THREE = "/assets/vendor/three-0.187.0/three.cover.min.js"   # three.js r187, tree-shaken to what the world uses (cover3d/build.mjs); world.js imports it by this path and its hash
STILLS = "/assets/cover/stills"
SHOTS = "/assets/cover/shots"
# the world on top and the card in the thumb zone: phones, portrait tablets and short screens (a phone on its side has no room for a card beside
# the world); cover.js (from data-phone), every <picture> here and cover.css use this same query
PHONE_Q = "(max-width: 720px), (max-aspect-ratio: 85/100), (max-height: 520px)"
DARK = "(prefers-color-scheme: dark)"
THEME = (("#F2F2F5", "light"), ("#000000", "dark"))            # the browser bar: the cover's grey by day, black by night (cover.css --cv-bg)
DISCLOSURE = "This trip is an example: the families and bookings in this story are made up. The places are real."
# a screenshot's encoded widths (scripts/cover_shots.py WIDTHS) and what it is, for a screen reader
SHOT_W = {"phone": (600,), "wide": (960, 1440)}
SHOT_SIZE = {"phone": (390, 844), "wide": (1440, 900)}
ALT = {
    "plan": "GitAway's booking page for Lake Tahoe: flights into Reno, stays, a car and things to do for two adults and two kids, each a search on the partner's own site.",
    "cockpit": "The trip's cockpit: each day of the Tahoe trip as a ticket, today's open with the drive to Taylor Creek, the bookings and a paper map of the lake.",
    "day": "Monday at Tahoe in GitAway: pancakes at the cabin, snowshoeing at Taylor Creek, lunch in town and what is up next.",
    "ask": "Ask GitAway showing a change before it is applied: snowshoeing moved after lunch and hot chocolate at Taylor Creek added.",
    "family": "The family's chat on the trip: Sam booked the sled hill and the snow comes after six.",
    "trail": "Lena and Sam's published trip, Five snowy days at Lake Tahoe, with a button to fork it.",
    "creators": "GitAway for creators: paste a blog post, a YouTube link or an Instagram caption and it becomes a trip families can fork.",
}


@lru_cache(maxsize=1)
def _boot():
    return (ASSETS / "js" / "cover_boot.js").read_text(encoding="utf-8").strip()


def debug():
    """Off production the page turns on the tools' switches (?measure, ?capture, ?q, ?cam, ?shot) and the world's window.__cover; production never does."""
    return not auth.production()


def _world_files():
    return sorted([*(ASSETS / "js" / "cover").glob("*.js"), *(ASSETS / "vendor").glob("three-*/*.js")])


@lru_cache(maxsize=8)
def _hash(key):
    h = hashlib.sha256()
    for path in key[0]:
        h.update(path.read_bytes())
    return h.hexdigest()[:10]


def _version(paths):
    """A short hash of the files' bytes, worked out once per build: their sizes and times are the cache key, so a rebuild shows up without a restart."""
    return _hash((tuple(paths), tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in paths)))


def world_version():
    """The built world and the three.js it imports, so a new build is never mixed with a cached old one (the service worker keeps ?v= files for good)."""
    return _version(_world_files())


def three_url():
    """three.js by its content hash: the very specifier cover3d/build.mjs writes into world.js, so the page's preload is the module the world imports."""
    return f"{THREE}?v={_version([ASSETS / THREE.removeprefix('/assets/')])}"


def _ico(path, sw="1.8"):
    return NotStr(f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>')


ICONS = {"down": '<path d="m6 9 6 6 6-6"/>'}       # the cover's own icons, only the ones gitaway/icons.py lacks
# the why: what planning a trip looks like before GitAway (decoration: the lede says it in words)
TABS = ("Flights", "Hotels near Heavenly", "Weather in December", "Do we need chains?", "Ski school prices", "Car rental Reno", "Sled hills", "Restaurants",
        "Emerald Bay", "Packing list", "Road conditions", "Reviews", "Group chat", "Budget")


def shot_srcs(name, layout, mode):
    """The files of one screenshot for a layout and mode, smallest first (scripts/cover_shots.py names them)."""
    return [f"{SHOTS}/{name}-{layout}-{mode}-{w}.webp" for w in SHOT_W[layout]]


def _srcset(name, layout, mode):
    return ", ".join(f"{src} {w}w" for src, w in zip(shot_srcs(name, layout, mode), SHOT_W[layout]))


SIZES = "(min-width: 1600px) 900px, 58vw"


def _shot(name):
    """A real screenshot of the feature: the phone's on phone layouts and the laptop's elsewhere, light or dark by the system (cover.js follows the site's own switch
    too), loaded only as it nears the screen."""
    phone_dark = ", ".join(f"{DARK} and {q.strip()}" for q in PHONE_Q.split(","))
    w, h = SHOT_SIZE["wide"]
    return Picture(
        Source(media=phone_dark, srcset=_srcset(name, "phone", "dark"), sizes="300px"),
        Source(media=DARK, srcset=_srcset(name, "wide", "dark"), sizes=SIZES),
        Source(media=PHONE_Q, srcset=_srcset(name, "phone", "light"), sizes="300px"),
        Img(src=shot_srcs(name, "wide", "light")[0], srcset=_srcset(name, "wide", "light"), sizes=SIZES, alt=ALT[name], width=str(w), height=str(h),
            loading="lazy", decoding="async"),
        cls="cv-shot", data_shot=name,
    )


def _eyebrow(text):
    return P(I(), text, cls="cv-eyebrow")


def _window(i, name, h, world, *content, cls=""):
    """A scene where the world shows through: its card is pinned while the world plays `world` (from, dwell, to on the world's own timeline)."""
    return Section(*content, cls=f"cv-sc cv-win {cls}".strip(), data_scene=str(i), data_name=name, data_world=world, style=f"--h:{h}")


def _paper(i, name, act, h2, text, shot, *extra):
    """A scene on the page itself: the headline and a few plain words beside the feature's real screenshot."""
    return Section(
        Div(_eyebrow(act), H2(*h2), P(*text, cls="cv-say"), *extra, cls="cv-words"),
        Div(_shot(shot), cls=f"cv-frame {shot}"),
        cls="cv-sc cv-paper", data_scene=str(i), data_name=name,
    )


def _card(*content, cls="cv-card"):
    return Div(Article(*content, cls=cls), cls="cv-pin")


def scenes():
    chev = _ico(ICONS["down"], "2")
    return (
        # 1. Why GitAway exists
        _window(0, "Why", 1.6, "0,0,1",
                Div(Div(_eyebrow("Why GitAway"),
                        H1("Planning a trip shouldn’t feel like ", Em("homework.")),
                        Div(Ul(*[Li(t) for t in TABS], cls="cv-tabs", aria_hidden="true"),
                            P("Fourteen tabs, a guidebook and a group chat, and still no plan. Too much information, and none of it in one place.", cls="cv-lede"),
                            cls="cv-why"),
                        cls="cv-hero-copy"),
                    P("Scroll", chev, cls="cv-hint", aria_hidden="true"), cls="cv-pin"), cls="cv-hero"),
        _window(1, "Lena and Sam", 2.1, "1,2,3", _card(
            _eyebrow("One trip, start to finish"),
            H2("Lena and Sam are taking the kids to Lake Tahoe."),
            P("A week in December: a cabin near Heavenly, ski school, a sled hill. Here is how they plan it with GitAway, one screen at a time. ",
              Span(DISCLOSURE, cls="cv-disc")))),
        # 2. Booking with everything in view
        _paper(2, "Book", "1 · Book",
               ("Book with everything ", Em("in view.")),
               ("Flights into Reno, a cabin, a car with chains and things to do, side by side for their dates and both kids. "
                "Each one opens on the partner’s own site, so the price is today’s. ", B("GitAway never takes payment.")),
               "plan"),
        # 3. The planning tools
        _paper(3, "The trip", "2 · Plan together",
               ("The whole trip ", Em("on one line.")),
               ("Every day is a ticket: the drive, the weather, the bookings and a paper map of the real lake. Today’s sits open, with when to leave.",),
               "cockpit"),
        _paper(4, "The day", "2 · Plan together",
               ("Each day, ", Em("to the hour.")),
               ("Pancakes at the cabin, snowshoes at Taylor Creek, a hot tub at dusk: the day on one timeline, with what’s next and how far it is.",),
               "day"),
        _paper(5, "Ask", "2 · Plan together",
               ("Change it ", Em("by asking.")),
               ("Type or say “move snowshoeing after lunch”. GitAway shows the new day first; ", B("nothing changes until you tap Apply.")),
               "ask"),
        _paper(6, "Family", "2 · Plan together",
               ("The whole family, ", Em("on the same page.")),
               ("One chat for the trip. Sam books the sled hill and everyone sees it; every change to the plan tells the family.",),
               "family"),
        _window(7, "Go", 1.9, "7.4,8,9", _card(
            _eyebrow("And then"),
            H2("Then go. ", Em("Be there.")),
            P("A week, the four of them, and the lake doing that impossible blue. The plan keeps itself; they keep the moment."))),
        # 4. Leave a trail
        _paper(8, "Leave a trail", "3 · Leave a trail",
               ("Home again, ", Em("leave a trail.")),
               ("Publish the trip in a few taps. Bookings, dates, names and the chat stay private; the places, the days and the tips help the next family.",),
               "trail"),
        _paper(9, "Follow", "3 · Leave a trail",
               ("Someone follows it and ", Em("makes it theirs.")),
               ("Another family forks Lena and Sam’s trail, swaps the ski day for a sled hill and says thanks. Write about travel? "
                "Paste a post and it becomes a trip anyone can plan.",),
               "creators"),
        _window(10, "Your turn", 1.6, "11.4,12,13", _card(
            _eyebrow("Every trip here grew from another"),
            H2("Take a trip. ", Em("Leave a trail.")),
            P(SUBHEAD, cls="cv-sub"),
            Div(A("Start a trip", href="/start", cls="cv-btn fill"),
                A("Leave a trail", href="/for-creators", cls="cv-btn tonal"),
                *((A("See trips people shared", icon("arrow-right", stroke=2), href="/community", cls="cv-btn text"),) if showcase.community_open() else ()),
                cls="cv-ctas"),
            cls="cv-card cv-last"), cls="cv-end"),
    )


def _stage():
    """The poster (the world's first still, the right one for day or night and phone or laptop with no script), the stills the calm version swaps, and the canvas."""
    def still(layout, mode):
        return f"{STILLS}/a-0-{layout}-{mode}.webp"
    phone_dark = ", ".join(f"{DARK} and {q.strip()}" for q in PHONE_Q.split(","))
    return Div(
        Picture(Source(media=phone_dark, srcset=still("phone", "dark")), Source(media=DARK, srcset=still("wide", "dark")),
                Source(media=PHONE_Q, srcset=still("phone", "light")),
                Img(src=still("wide", "light"), alt="", fetchpriority="high", decoding="async"), cls="cv-poster"),
        Div(cls="cv-stills"),
        Canvas(cls="cv-canvas"),
        cls="cv-stage", aria_hidden="true",
    )


def _footer(links):
    return Footer(
        Span("GitAway", cls="ga-brand-name"),
        P("Plan a trip together, share it, and follow trips other families shared. Booking always happens on the partner’s site, under their terms, never here."),
        Nav(*[A(label, href=href) for label, href in [*links, ("Privacy", "/privacy"), ("Terms", "/terms")]], aria_label="More"),
        P("Early preview · the trip, the families and the bookings in this story are made up; the screens are GitAway’s own. Lake Tahoe is real: map data © ",
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
        _stage(),
        Header(brand(), Div(preview(), cls="cv-tag"), A("Sign in", href=session.signin_href(), cls="cv-btn tonal"), cls="cv-top"),
        Nav(cls="cv-rail", aria_label="Scenes"),
        Main(*scenes(), id="main", data_world=f"{WORLD}?v={world_version()}", data_three=three_url(), data_assets="/assets/cover/", data_stills=STILLS,
             data_shots=SHOTS, data_phone=PHONE_Q, data_debug="1" if debug() else None),
        Div(card, _footer(footer_links), cls="cv-close"),
        Div(cls="cv-anchors", aria_hidden="true"),
    )
