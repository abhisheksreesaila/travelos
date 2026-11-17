"""The page shell every GitAway screen shares: fonts, tokens, header and footer, the mark, and the light/dark switch (F-200)."""

import hashlib
import hmac

from fasthtml.common import A, Button, Details, Div, Footer, Form, Link, Main, Meta, Nav, NotStr, P, Script, Span, Summary, Title

from gitaway import session, showcase, v2pages
from gitaway.icons import icon


def trip_field():
    """A hidden `trip` input naming the trip this page was drawn for, so a form posted later from a stale tab changes that trip only.

    It reads the trip the request resolved, which happens when the family is first opened (any `ses.booking`, `cal.activities` ...): call
    it only while rendering a page that has already done so. Before that it returns "", and tests/test_family_storage.py fails a page whose
    post forms lack it."""
    from fasthtml.common import Input
    t = session.open_trip_id()
    return Input(type="hidden", name="trip", value=t) if t else ""

PAPER = "#F2F2F5"  # --paper / --ground in light mode (Direction A's canvas, F-200): the manifest's colours
DARK = "#000000"   # the canvas in dark mode
THEME_COLORS = {"sunset": PAPER, "pacific": PAPER}  # each theme's --ground, for the browser chrome (Direction A gives both themes the same canvas)
CLEAR_SITE_DATA = '"storage"'  # not "cache": clearing the HTTP cache is the slow part of signing out (F-062); "storage" still drops the service worker and its caches


def clear_site_data(response):
    """Make the browser forget this site's caches and storage (saved pages, service worker). Call it on every sign-out.

    /logout and /signout (gitaway/pages/signin.py) both pass their response through this.
    """
    response.headers["Clear-Site-Data"] = CLEAR_SITE_DATA
    return response


def cache_key(traveler=None, tenant_id=None):
    """A short, non-secret key the service worker files saved pages under (None when signed out): per person AND per active family,
    so a family switch or a removal changes it and the other family's saved pages are dropped (F-043)."""
    traveler = traveler or session.request_traveler()
    tenant_id = tenant_id if tenant_id is not None else session.request_tenant()
    ident = f"{traveler.id}|{tenant_id}" if traveler and tenant_id else (traveler.id if traveler else "")
    return hmac.new(session.cache_secret(), ident.encode(), hashlib.sha256).hexdigest()[:10] if traveler else None


def join_note():
    """The dismissable sign-in notice ("You joined Ari's family", with Switch / Stay), or "" when there is none. Posts go to /family/switch and /family/stay."""
    note = session.request_note()
    if not note:
        return ""
    from fasthtml.common import Input
    here = Input(type="hidden", name="next", value=session.request_path() or "/family")
    if note.get("switch"):
        buttons = [Form(Input(type="hidden", name="tenant", value=note["tenant"]), here, Button("Switch", type="submit", cls="btn btn-sm"), action="/family/switch", method="post"),
                   Form(here, Button("Stay", type="submit", cls="btn btn-sm"), action="/family/stay", method="post")]
    else:
        buttons = [Form(here, Button("OK", type="submit", cls="btn btn-sm"), action="/family/stay", method="post")]
    return Div(Span(note["text"], cls="ga-note-text"), Div(*buttons, cls="ga-note-actions"), role="status", id="ga-note", cls="ga-note")

HEAD = (
    Script(src="/assets/js/page_moves.js"),  # F-099: forward/back tag for the page-change transition; not deferred (see the file)
    Script(src="/assets/js/mode.js"),        # F-200: the remembered light or dark choice is on <html> before the first paint; not deferred
    Link(rel="preload", href="/assets/fonts/geist-variable.woff2", **{"as": "font"}, type="font/woff2", crossorigin=""),
    # Install on iPhone (F-044): manifest, theme colour, Apple tags, service worker registration
    Link(rel="manifest", href="/manifest.webmanifest"),
    Link(rel="apple-touch-icon", href="/assets/icons/apple-touch-icon.png"),
    Meta(name="mobile-web-app-capable", content="yes"),
    Meta(name="apple-mobile-web-app-capable", content="yes"),
    Meta(name="apple-mobile-web-app-status-bar-style", content="default"),
    Meta(name="apple-mobile-web-app-title", content="GitAway"),
    Script(src="/assets/js/pwa.js", defer=True),
)

def styles(*extra, theme="sunset"):
    """The shared stylesheets in cascade order (tokens, base), then any page-specific head items.

    page() uses this; a page that builds its own document should too, so page CSS always wins over base.css.
    """
    key = cache_key()
    return (
        Meta(name="theme-color", content=THEME_COLORS.get(theme, PAPER), media="(prefers-color-scheme: light)"),
        Meta(name="theme-color", content=DARK, media="(prefers-color-scheme: dark)"),     # F-200: the browser bar follows the mode (mode.js follows a manual choice)
        *((Meta(name="ga-user", content=key),) if key else ()),
        *((Meta(name="ga-until", content=str(session.expires_at())),) if key and session.expires_at() else ()),      # when this sign-in runs out: sw.js serves no saved page past it
        Link(rel="stylesheet", href="/assets/css/tokens.css"),
        Link(rel="stylesheet", href="/assets/css/base.css"),
        Link(rel="stylesheet", href="/assets/css/toast.css"),         # F-108: the one toast, on every page
        Script(src="/assets/js/motion.js", defer=True),               # F-109: the one liquid motion (GA.motion); before every script that opens something
        Script(src="/assets/js/motion_fallback.js", defer=True),     # F-110: the one stand-in when motion.js did not load, so no script carries a copy
        Script(src="/assets/js/toast.js", defer=True),
        Script(src="/assets/js/preview.js", defer=True),              # F-200: the "Early preview" label opens and closes
        *extra,
    )



MARK = ('<svg class="ga-mark" viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" aria-hidden="true" focusable="false">'
        '<path class="mk-l" d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9M12 12v3"/><circle class="mk-a" cx="6" cy="6" r="2.6"/>'
        '<circle class="mk-b" cx="18" cy="6" r="2.6"/><circle class="mk-c" cx="12" cy="18" r="2.6"/></svg>')


def mark(cls="ga-brand-mark"):
    """The mark (Direction A, F-200): an ink tile (white in dark mode) with the fork's three nodes in kind colours. base.css sizes and colours it; `cls` is the tile's class."""
    return Span(NotStr(MARK), cls=cls)


def brand(href: str = "/"):
    return A(
        mark(),
        Span("GitAway", cls="ga-brand-name"),
        href=href, cls="ga-brand", aria_label="GitAway home",
    )


PREVIEW_LINE = ("GitAway is new. Things will change; ", "tell us what breaks", ".")


def preview(cls="ga-preview"):
    """The honest "Early preview" label (F-200, the brief's "What" 1): a small calm pill in the shell, beside the brand (the site header, the top bar, sign-in, the
    booking workspace) and at the top of a phone's trip screens. It opens one line; "tell us what breaks" is a link to GITAWAY_CONTACT_EMAIL when that is set.
    assets/js/preview.js opens and closes it with the one motion (GA.motion), like the top bar's menus."""
    from gitaway import planforme  # here, not at the top: it reads the Stripe and AI settings
    addr = planforme.contact_email()
    ask = A(PREVIEW_LINE[1], href=f"mailto:{addr}?subject=GitAway%20early%20preview") if addr else PREVIEW_LINE[1]
    return Details(Summary(Span("Early preview", cls="ga-preview-pill"), cls="ga-preview-sum"), Div(P(PREVIEW_LINE[0], ask, PREVIEW_LINE[2]), cls="ga-preview-pop", role="note"), cls=cls)




def mode_switch(where="foot"):
    """One button for dark (D-460, founder 2026-11-13: "a simple button to switch between light and dark … light by default"): pressed when
    dark; assets/js/mode.js keeps the choice on this device. The moon shows in light, the sun in dark. `where` names this copy (the footer, the
    avatar menu)."""
    return Button(Span(icon("moon", 18), "Dark", cls="ga-mode-moon"), Span(icon("sun", 18), "Light", cls="ga-mode-sun"),
                  type="button", cls="ga-mode", id=f"ga-mode-{where}", data_mode_toggle="1", aria_pressed="false", aria_label="Dark mode", title="Dark mode")


def avatar(traveler, cls="ga-avatar"):
    return Span(traveler.initials, cls=f"{cls} fill-{traveler.color}", title=traveler.name, aria_label=traveler.name)


def plan_href() -> str:
    """Where "Plan a trip" and "Start a trip" go (D-461, D-761): the ask and the trip matrix where it exists, else the import of a trip already booked, for
    everyone. A visitor searches and compares without an account; sign-in comes only where something is kept: Save, Book and Plan this trip."""
    return showcase.planning_path()


APP_MARK = "/assets/icons/icon-512.png"   # the picture a shared link shows when the page has none of its own


def seo_meta(title: str, description: str = "", image: str = "", og_type: str = "website", noindex: bool = False):
    """The <meta> tags of a page that is found or shared (F-196): a description and Open Graph (title, description, image, type, address, site name), and `robots noindex` for a page that
    must not appear in search. Addresses are absolute, on GITAWAY_PUBLIC_URL (a preview card cannot read a relative one). No description means no tags except noindex."""
    from gitaway import blogbutton  # here, not at the top: it reads the passkey settings
    tags = [Meta(name="robots", content="noindex")] if noindex else []
    if not description:
        return tuple(tags)
    base = blogbutton.base_url()
    picture = image or APP_MARK
    return (*tags, Meta(name="description", content=description), Meta(property="og:title", content=title), Meta(property="og:description", content=description),
            Meta(property="og:type", content=og_type), Meta(property="og:image", content=picture if picture.startswith("http") else base + picture),
            Meta(property="og:url", content=base + (session.request_path() or "/").split("?")[0]), Meta(property="og:site_name", content="GitAway"))


def _footer_line() -> str:
    """The production footer's one sentence: booking is on the partners' sites, and GitAway takes payment only while Plan it for me is sold (F-199)."""
    from gitaway import planforme  # here: planforme reads the community database and imports much of the app
    taken = "GitAway takes payment only for Plan it for me." if planforme.paid() else "GitAway never takes payment."
    return f"Plan a trip together: flights, stays and days on one calendar. You book on the partners' own sites; {taken}"


def page(title: str, *content, current: str = "", theme: str = "sunset", head=(), description: str = "", image: str = "", og_type: str = "website", noindex: bool = False, footer: bool = True, v2: bool | str = True, mood: str = "", quiet: bool = False):
    """A full GitAway page. `current` marks the active nav link; `theme` is sunset or pacific.

    `description` (with `image` and `og_type`) adds the description and Open Graph tags a search result or a shared link shows; `noindex` keeps the page out of search (see `seo_meta`). `footer=False` leaves the site footer out (the trip matrix, F-238: its Privacy and Terms sit in its own ⓘ).
    `v2=True` (F-250, D-610; a string adds its classes, "is-results" for the results look) opts the page into design language v2 with one class: the sky, the v2 top bar, Newsreader and Inter (gitaway/v2.py); there is no site header, top bar or footer. `mood` is the sky's (gitaway/moods.py; none is beach). `quiet=True` (F-261) is a reading page's sky: no objects, a soft gradient framing the content. A quiet page also ends with `pg_foot()` (Privacy and Terms, F-272) unless `footer=False` (the page has its own, as the matrix's "About these prices") or it is a creator page (`cv`, whose foot is studio.foot)."""
    from gitaway import v2 as v2_
    return (
        Title(f"GitAway · {title}" if title else "GitAway"),
        *styles(*v2_.HEAD, *head, *seo_meta(title, description, image, og_type, noindex), theme=theme),
        Div(v2_.bg(mood, quiet), v2_.top(current, *(("Sample guides",) if "cv" in str(v2).split() else ())), join_note(), Main(*content, id="main"),
            *((pg_foot(),) if quiet and footer and "cv" not in str(v2).split() else ()), data_theme=theme, cls="ga-page v2" + (f" {v2}" if isinstance(v2, str) else "")),
    )


def pg_foot():
    """The foot of a v2 reading page (F-272, D-800): Privacy and Terms, which the v2 top bar does not carry. The sentence under it is the site footer's, as it was."""
    return Footer(Nav(A("Privacy", href="/privacy"), A("Terms", href="/terms"), A("How GitAway keeps you safe", href="/trust"), cls="pg-foot-nav", aria_label="Legal"),
                  Span("Sample data only: no real bookings or payments." if showcase.on() else _footer_line(), cls="pg-fine"), cls="pg-foot")


def reading(title: str, *content, wide: bool = False, current: str = "", **kw):
    """A reading or form page in design language v2 (F-272, D-800): the quiet sky, the v2 top bar, one column (`.pg`, 46rem; `wide` 90rem for a page with two columns) and, as every quiet page, the foot with
    Privacy and Terms (`page()` adds it). Its stylesheet is assets/css/v2page.css (in v2.HEAD): near-opaque cards, v2 buttons and fields for the Direction A classes `.btn`, `.tag` and plain inputs inside it."""
    return page(title, Div(*content, cls="pg is-wide" if wide else "pg"), current=current, v2="pgs", quiet=True, **{**kw, "head": (*v2pages.HEAD, *kw.get("head", ()))})


def notice(title: str, *body, status: int = 200, current: str = "", head=(), **kw):
    """A short page with one message and a way on (a 404, a refusal, the offline page, a stand-in): the title, the words and the buttons in one card. `status` makes it the response's code."""
    from fasthtml.core import FtResponse
    out = reading(title, Div(*body, cls="pg-card pg-notice"), current=current, head=head, **kw)
    return out if status == 200 else FtResponse(out, status_code=status)


# The cover's way in (founder, 2026-11-13, D-458; F-262): Plan a trip is drawn as `plan_href()`. Guides is always there: off the showcase, before anyone has shared a guide, its page says so.
NAV = [("Guides", "/guides"), ("Find a trip", "/plan/matrix")]      # F-289: the search is "Find a trip"; "My trip" is the booked trip's days
