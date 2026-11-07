"""The cover (F-206): what a signed-out visitor sees at /. A scroll story through Lake Tahoe in December, opening on "Don't read about it. Go."
and closing on the line "Take a trip. Leave a trail." (docs/briefs/free-and-polished.md "The line"; design: docs/design/cover3d/, concept A with B's fork tree).

Every word is real DOM text in seven chapters. Behind them a fixed stage shows a poster at once (chapter 0's still), then either the live 3D world
or the calm stills: assets/js/cover.js decides, and only it ever fetches three.js, the world (assets/js/cover/world.js, built from cover3d/src)
and the terrain, so reduced motion, no WebGL and weak phones download none of it. home.py serves this to signed-out visitors only.
"""

import hashlib
from functools import lru_cache
from pathlib import Path

from fasthtml.common import A, Article, B, Canvas, Div, Em, Footer, H1, H2, Header, I, Img, Li, Link, Main, Nav, NotStr, P, Picture, Script, Section, Source, Span, Title, Ul

from gitaway import session, showcase
from gitaway.layout import brand, seo_meta, styles

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
TITLE = "Take a trip. Leave a trail."
SUBHEAD = "Share the whole trip, not just the photos, so the next family can follow it, make it theirs, and say thanks."
OG_IMAGE = "/assets/cover/og.jpg"
WORLD = "/assets/js/cover/world.js"
THREE = "/assets/vendor/three-0.187.0/three.cover.min.js"   # three.js r187, tree-shaken to what the world uses (cover3d/build.mjs); world.js imports it by this path
STILLS = "/assets/cover/stills"
PHONE_Q = "(max-width: 720px), (max-aspect-ratio: 85/100)"     # the world on top and the card in the thumb zone; cover.js and cover.css use the same query
# the trip's five days (chapter 1): name, kind colour (cover.css --cv-k-*)
DAYS = (("Cabin", "stay"), ("Emerald Bay", "see"), ("Tahoe City", "food"), ("Sand Harbor", "see"), ("Heavenly", "tix"))


@lru_cache(maxsize=1)
def _boot():
    return (ASSETS / "js" / "cover_boot.js").read_text(encoding="utf-8").strip()


def _world_files():
    return sorted([*(ASSETS / "js" / "cover").glob("*.js"), *(ASSETS / "vendor").glob("three-*/*.js")])


@lru_cache(maxsize=4)
def _hash(stamp):
    h = hashlib.sha256()
    for path in _world_files():
        h.update(path.read_bytes())
    return h.hexdigest()[:10]


def world_version():
    """A short hash of the built world and the three.js it imports, so a new build is never mixed with a cached old one (the service worker keeps ?v= files for good).
    Hashed once per build: the files' sizes and times are the cache key, so a rebuild shows up without a restart."""
    return _hash(tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in _world_files()))


def _ico(path, sw="1.8"):
    return NotStr(f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>')


ARROW_OUT = '<path d="M7 17 17 7M7 7h10v10"/>'
ICONS = {
    "wx": '<path d="M12 2v20M4.9 7l14.2 10M4.9 17 19.1 7M9 4l3 3 3-3M9 20l3-3 3 3"/>',
    "up": '<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
    "flight": '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
    "stay": '<path d="M2 4v16M2 8h18a2 2 0 0 1 2 2v10M2 17h20M6 8v9"/>',
    "car": '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
    "tix": '<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M13 5v2M13 17v2M13 11v2"/>',
}


def _widget(kind, label, title, line, by="", extra=""):
    """One of the plan's widgets (chapter 3). Booked ones say on whose site, as every booking in GitAway does (links out, never a checkout)."""
    stub = kind in ("flight", "stay", "car", "tix")
    return Div(
        Span(label, _ico(ICONS[kind]), cls="k"),
        NotStr(title) if kind == "wx" else B(title),
        Span(line),
        *((Span(f"Booked on {by}", _ico(ARROW_OUT, "2"), cls="by"), I("BOOKED", cls="stamp", aria_hidden="true")) if by else ()),
        cls=f"cv-wd {kind}{' stub' if stub else ''}{' wide' if kind in ('wx', 'up') else ''}{extra}",
    )


def _card(*content, cls="cv-card"):
    return Div(Article(*content, cls=cls), cls="cv-pin")


def _chapter(i, name, h, *content, cls=""):
    return Section(*content, cls=f"cv-ch {cls}".strip(), data_chapter=str(i), data_name=name, style=f"--h:{h}")


def _eyebrow(text):
    return P(I(), text, cls="cv-eyebrow")


def _chapters():
    chev = _ico('<path d="m6 9 6 6 6-6"/>', "2")
    return (
        _chapter(0, "The book", 1.5,
                 Div(Div(H1("Don’t read about it. ", Em("Go.")),
                         P("Forget the guidebook. Start from a trip a real family took, ", B("make it yours"), ", and go.", cls="cv-lede"), cls="cv-hero-copy"),
                     P("Scroll", chev, cls="cv-hint", aria_hidden="true"), cls="cv-pin"), cls="cv-hero"),
        Div(cls="cv-gap", style="--h:0.8", aria_hidden="true"),
        _chapter(1, "Arrive", 2.2, _card(
            _eyebrow("Lake Tahoe · December"),
            H2("A family shared their five days here."),
            P("Lena and Sam posted the whole trip: the cabin, the drives, where they ate, the ski day. Every pin is a place on their trip."),
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
                cls="cv-wds", aria_label="The trip, planned"),
            P("Every booking opens on the partner’s site. GitAway never takes payment.", cls="cv-note"))),
        _chapter(4, "Go", 2, _card(
            _eyebrow("Go"),
            H2("Then go. ", Em("Be there.")),
            P("Five days, the four of you, and the lake doing that impossible blue. The plan keeps itself; you keep the moment."))),
        _chapter(5, "Share it back", 2.2, _card(
            _eyebrow("Share it back"),
            H2("Someone’s next trip starts with yours."),
            P("Post your photos and your plan when you’re home. The next family follows your trail, and their thank-you finds its way back to you."),
            P(_ico('<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>', "1.6"), "Thanks from Ana & Luis", cls="cv-thanks"))),
        _chapter(6, "Leave a trail", 1.6, _card(
            _eyebrow("Every trip here grew from another"),
            H2("Take a trip. ", Em("Leave a trail.")),
            P(SUBHEAD, cls="cv-sub"),
            Div(A("Start a trip", href="/start", cls="cv-btn fill"),
                A("Leave a trail", href="/for-creators", cls="cv-btn tonal"),
                *((A("See trips people shared", _ico('<path d="M5 12h14M13 6l6 6-6 6"/>', "2"), href="/community", cls="cv-btn text"),) if showcase.community_open() else ()),
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
        P("Early preview · the trip, the families and the bookings in this story are made up. Lake Tahoe is real: map data © OpenStreetMap contributors, "
          "elevation from USGS 3DEP via AWS Terrain Tiles.", cls="cv-fine"),
        cls="cv-foot",
    )


def page(footer_links, drive=()):
    """The whole cover document. `footer_links` are the landing's (home.footer_links); `drive` the Travelpayouts Drive tag when it is switched on (home._drive)."""
    from gitaway.itinerary_view import plan_for_me_card
    card = plan_for_me_card("Rather not plan it yourself?", "/plan-for-me", "pf-card cv-pf")
    return (
        Title(f"GitAway · {TITLE}"),
        *styles(Link(rel="stylesheet", href="/assets/css/cover.css"), *((Link(rel="stylesheet", href="/assets/css/planforme.css"),) if card else ()),
                *seo_meta(f"GitAway · {TITLE}", SUBHEAD, OG_IMAGE), *drive,
                Script(NotStr(_boot())), Script(src="/assets/js/cover.js", defer=True)),
        A("Skip to the story", href="#main", cls="ga-skip"),
        _stage(),
        Header(brand(), Span("Early preview", cls="cv-tag"), Span(cls="cv-sp"), A("Sign in", href=session.signin_href(), cls="cv-btn tonal"), cls="cv-top"),
        Nav(cls="cv-rail", aria_label="Chapters"),
        Main(*_chapters(), id="main", data_world=f"{WORLD}?v={world_version()}", data_three=THREE, data_assets="/assets/cover/", data_stills=STILLS, data_phone=PHONE_Q),
        Div(card, _footer(footer_links), cls="cv-close"),
        Div(cls="cv-anchors", aria_hidden="true"),
    )
