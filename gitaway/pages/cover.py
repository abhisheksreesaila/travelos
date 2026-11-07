"""The cover (F-206): what a signed-out visitor sees at /. A scroll story through Lake Tahoe in December, opening on "Don't read about it. Go."
and closing on the line "Take a trip. Leave a trail." (docs/briefs/free-and-polished.md "The line"; design: docs/design/cover3d/, concept A with B's fork tree).

Every word is real DOM text in seven chapters. Behind them a fixed stage shows a poster at once (chapter 0's still), then either the live 3D world
or the calm stills: assets/js/cover.js decides, and only it ever fetches three.js, the world (assets/js/cover/world.js, built from cover3d/src)
and the terrain, so reduced motion, no WebGL and weak phones download none of it. home.py serves this to signed-out visitors only.

The family, their bookings and their thanks are an illustration shown in production too, and the story says so where the family first appears
(docs/decisions.md D-270, the exception to the showcase rule). Off production <main> carries data-debug="1", which turns on the capture and measuring
tools' URL switches and the world's window.__cover; production never renders it.
"""

import hashlib
from functools import lru_cache
from pathlib import Path

from fasthtml.common import A, Article, B, Canvas, Div, Em, Footer, H1, H2, Header, I, Img, Li, Link, Main, Meta, Nav, NotStr, P, Picture, Script, Section, Source, Span, Title, Ul

from gitaway import auth, session, showcase
from gitaway.icons import icon
from gitaway.layout import brand, seo_meta, styles

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
TITLE = "Take a trip. Leave a trail."
SUBHEAD = "Share the whole trip, not just the photos, so the next family can follow it, make it theirs, and say thanks."
OG_IMAGE = "/assets/cover/og.jpg"
WORLD = "/assets/js/cover/world.js"
THREE = "/assets/vendor/three-0.187.0/three.cover.min.js"   # three.js r187, tree-shaken to what the world uses (cover3d/build.mjs); world.js imports it by this path and its hash
STILLS = "/assets/cover/stills"
# the world on top and the card in the thumb zone: phones, portrait tablets and short screens (a phone on its side has no room for a card beside
# the world); cover.js (from data-phone), the poster's <picture> and cover.css use this same query
PHONE_Q = "(max-width: 720px), (max-aspect-ratio: 85/100), (max-height: 520px)"
THEME = (("#F2F2F5", "light"), ("#000000", "dark"))            # the browser bar: the cover's grey by day, black by night (cover.css --cv-bg)
# the trip's five days (chapter 1): name, kind colour (cover.css --cv-k-*)
DAYS = (("Cabin", "stay"), ("Emerald Bay", "see"), ("Tahoe City", "food"), ("Sand Harbor", "see"), ("Heavenly", "tix"))


@lru_cache(maxsize=1)
def _boot():
    return (ASSETS / "js" / "cover_boot.js").read_text(encoding="utf-8").strip()


def debug():
    """Off production the page turns on the tools' switches (?measure, ?capture, ?q, ?cam) and the world's window.__cover; production never does."""
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


# the cover's own icons, only the ones gitaway/icons.py lacks: snow, a route, a chevron down
ICONS = {
    "wx": '<path d="M12 2v20M4.9 7l14.2 10M4.9 17 19.1 7M9 4l3 3 3-3M9 20l3-3 3 3"/>',
    "up": '<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
    "down": '<path d="m6 9 6 6 6-6"/>',
}
SITE_ICON = {"flight": "plane", "stay": "bed", "car": "car", "tix": "ticket"}      # gitaway/icons.py names for the bookings' kinds


def _widget(kind, label, title, line, by="", extra=""):
    """One of the plan's widgets (chapter 3). Booked ones say on whose site, as every booking in GitAway does (links out, never a checkout)."""
    stub = kind in SITE_ICON
    return Div(
        Span(label, icon(SITE_ICON[kind], stroke=1.8) if stub else _ico(ICONS[kind]), cls="k"),
        NotStr(title) if kind == "wx" else B(title),
        Span(line),
        *((Span(f"Booked on {by}", icon("ext", stroke=2), cls="by"), I("BOOKED", cls="stamp", aria_hidden="true")) if by else ()),
        cls=f"cv-wd {kind}{' stub' if stub else ''}{' wide' if kind in ('wx', 'up') else ''}{extra}",
    )


def _card(*content, cls="cv-card"):
    return Div(Article(*content, cls=cls), cls="cv-pin")


def _chapter(i, name, h, *content, cls=""):
    return Section(*content, cls=f"cv-ch {cls}".strip(), data_chapter=str(i), data_name=name, style=f"--h:{h}")


def _eyebrow(text):
    return P(I(), text, cls="cv-eyebrow")


def _chapters():
    chev = _ico(ICONS["down"], "2")
    return (
        _chapter(0, "The book", 1.5,
                 Div(Div(H1("Don’t read about it. ", Em("Go.")),
                         P("Forget the guidebook. Start from a trip a real family took, ", B("make it yours"), ", and go.", cls="cv-lede"), cls="cv-hero-copy"),
                     P("Scroll", chev, cls="cv-hint", aria_hidden="true"), cls="cv-pin"), cls="cv-hero"),
        Div(cls="cv-gap", style="--h:0.8", aria_hidden="true"),
        _chapter(1, "Arrive", 2.2, _card(
            _eyebrow("Lake Tahoe · December"),
            H2("A family shared their five days here."),
            P("Lena and Sam posted the whole trip: the cabin, the drives, where they ate, the ski day. ",
              Span("The places are real; the families and bookings in this story are made up.", cls="cv-disc")),
            Ul(*[Li(I(style=f"background:var(--cv-k-{kind})"), name) for name, kind in DAYS], cls="cv-days", aria_label="Their five days"))),
        _chapter(2, "Follow", 2, _card(
            _eyebrow("Follow this trail"),
            H2("Make it yours."),
            P("Follow their trail and it’s yours to change. Keep the cabin, swap the ski day for a sled hill. ", B("Lena and Sam get the thanks;"), " you get a head start."))),
        _chapter(3, "Plan together", 2.6, _card(
            _eyebrow("Plan together"),
            H2("The whole trip on one screen."),
            P("The weather, your route, the drive time and every booking, wherever you made it. Your family plans it together.", cls="cv-plan-lede"),
            Div(_widget("wx", "South Lake Tahoe", '<div class="cv-wx"><span class="big">28°</span><span>Snow · 6 in tonight</span></div>', ""),
                _widget("up", "Drive · 18 min", "Cabin → Taylor Creek sled hill", "8 mi · chains advised"),
                _widget("flight", "Flight", "SFO → RNO", "Fri 8:05 · nonstop", "Aviasales"),
                _widget("stay", "Stay", "Cabin on Ski Run Blvd", "4 nights · Fri to Tue", "Vrbo"),
                _widget("car", "Car", "AWD SUV, chains", "Reno airport", "Expedia"),
                _widget("tix", "Tickets", "Sled hill passes", "4 passes · Sat", "Klook"),
                cls="cv-wds", role="group", aria_label="The trip, planned"),
            P("Every booking opens on the partner’s site. GitAway never takes payment.", cls="cv-note"))),
        _chapter(4, "Go", 2, _card(
            _eyebrow("Go"),
            H2("Then go. ", Em("Be there.")),
            P("Five days, the four of you, and the lake doing that impossible blue. The plan keeps itself; you keep the moment."))),
        _chapter(5, "Share it back", 2.2, _card(
            _eyebrow("Share it back"),
            H2("Someone’s next trip starts with yours."),
            P("Post your photos and your plan when you’re home. The next family follows your trail, and their thank-you finds its way back to you."),
            P(icon("star", stroke=1.6), "Thanks from Ana & Luis", cls="cv-thanks"))),
        _chapter(6, "Leave a trail", 1.6, _card(
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
    """The poster (chapter 0's still, the right one for day or night and phone or laptop with no script), the stills the calm version swaps, and the canvas."""
    def still(layout, mode):
        return f"{STILLS}/a-0-{layout}-{mode}.webp"
    dark = "(prefers-color-scheme: dark)"
    phone_dark = ", ".join(f"{dark} and {q.strip()}" for q in PHONE_Q.split(","))
    return Div(
        Picture(Source(media=phone_dark, srcset=still("phone", "dark")), Source(media=dark, srcset=still("wide", "dark")),
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
        P("Early preview · the trip, the families and the bookings in this story are made up. Lake Tahoe is real: map data © ",
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
        Header(brand(), Span("Early preview", cls="cv-tag"), A("Sign in", href=session.signin_href(), cls="cv-btn tonal"), cls="cv-top"),
        Nav(cls="cv-rail", aria_label="Chapters"),
        Main(*_chapters(), id="main", data_world=f"{WORLD}?v={world_version()}", data_three=three_url(), data_assets="/assets/cover/", data_stills=STILLS,
             data_phone=PHONE_Q, data_debug="1" if debug() else None),
        Div(card, _footer(footer_links), cls="cv-close"),
        Div(cls="cv-anchors", aria_hidden="true"),
    )
