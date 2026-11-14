"""The page shell every GitAway screen shares: fonts, tokens, header and footer, the mark, and the light/dark switch (F-200)."""

import hashlib
import hmac

from fasthtml.common import A, Button, Details, Div, Footer, Form, Header, Link, Main, Meta, Nav, NotStr, P, Script, Span, Summary, Title

from gitaway import session, showcase
from gitaway.icons import icon


def trip_field():
    """A hidden `trip` input naming the trip this page was drawn for, so a form posted later from a stale tab changes that trip only.

    It reads the trip the request resolved, which happens when the family is first opened (any `ses.booking`, `cal.activities` ...): call
    it only while rendering a page that has already done so. Before that it returns "", and tests/test_family_storage.py fails a page whose
    post forms lack it."""
    from fasthtml.common import Input
    t = session.open_trip_id()
    return Input(type="hidden", name="trip", value=t) if t else ""

FONTS = "https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&display=swap"   # the hand (traveler notes); Geist, the face of everything else, is served from /assets/fonts (tokens.css)

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
    Link(rel="preconnect", href="https://fonts.googleapis.com"),
    Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
    Link(rel="stylesheet", href=FONTS),
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
        Link(rel="stylesheet", href="/assets/css/tokens.css"),
        Link(rel="stylesheet", href="/assets/css/base.css"),
        Link(rel="stylesheet", href="/assets/css/toast.css"),         # F-108: the one toast, on every page
        Link(rel="stylesheet", href="/assets/css/topbar.css"),        # F-139: the signed-in desktop's one top bar (shown from 1020px up)
        Script(src="/assets/js/motion.js", defer=True),               # F-109: the one liquid motion (GA.motion); before every script that opens something
        Script(src="/assets/js/motion_fallback.js", defer=True),     # F-110: the one stand-in when motion.js did not load, so no script carries a copy
        Script(src="/assets/js/toast.js", defer=True),
        Script(src="/assets/js/topbar.js", defer=True),               # F-139: the top bar's two menus and the "/" key
        Script(src="/assets/js/preview.js", defer=True),              # F-200: the "Early preview" label opens and closes
        *extra,
        Link(rel="stylesheet", href="/assets/css/desk_skin.css"),     # F-158: the calm laptop skin, last so it wins over every page's own CSS; every rule in it sits under the desktop query and a signed-in page's top bar, so the phone, the tablet, the installed app and the landing never see it
    )

# The site's way in, the same everywhere (founder, 2026-11-13, D-458): "/start" is drawn as `plan_href()`. Community trips is always there: off the
# showcase, before anyone has shared a trip, its page says so.
NAV = [("For creators", "/for-creators"), ("Community trips", "/community"), ("Plan a trip", "/start")]


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


MODES = (("auto", "Auto"), ("light", "Light"), ("dark", "Dark"))


def mode_switch(where="foot"):
    """Auto, Light, Dark (F-200): assets/js/mode.js keeps the choice on this device and marks the pressed one. Auto follows the phone's or computer's own setting.
    `where` names this copy (the footer, the avatar menu), so two on one page have their own label ids."""
    return Div(Span("Appearance", cls="ga-mode-k", id=f"ga-mode-{where}"),
               *[Button(label, type="button", data_mode_pick=key, aria_pressed="false") for key, label in MODES],      # mode.js marks the one in use as soon as the page loads
               role="group", aria_labelledby=f"ga-mode-{where}", cls="ga-mode")


def avatar(traveler, cls="ga-avatar"):
    return Span(traveler.initials, cls=f"{cls} fill-{traveler.color}", title=traveler.name, aria_label=traveler.name)


def account(traveler=None):
    """Sign in link, or the traveler's avatar plus Sign out. Defaults to the request's traveler (see gitaway.session)."""
    traveler = traveler or session.request_traveler()
    if not traveler:
        return A("Sign in", href=session.signin_href(), cls="btn btn-sm")
    from gitaway import topbar  # here, not at the top: topbar reads the family through gitaway.session
    new, captain = topbar._admin_notice(session.request_session())
    return Div(
        A(f"Admin ({new} new)" if new else "Admin", href="/admin", cls="ga-admin-link", id="ga-admin-link") if captain else "",     # F-196: the captain's way in, with the reports not yet read
        A(avatar(traveler), href="/family", cls="ga-me", aria_label="Your family and who is in it", title=traveler.name),  # F-043: the family page
        Form(Button("Sign out", type="submit", cls="ga-signout"), action="/signout", method="post"),
        cls="ga-account",
    )


def site_header(current: str = "", traveler=None, nav: bool = True):
    """The header. `nav=False` is the landing's: the brand and the account only.

    A signed-in person's page (nav=True) also carries the one top bar (F-139, gitaway.topbar) before it: topbar.css shows the bar from 1020px up and
    hides this header there; below that width this header is what shows, as before."""
    from gitaway import topbar  # here, not at the top: topbar reads the family through gitaway.session
    links = [A(label, href=plan_href() if href == "/start" else href, aria_current="page" if (plan_href() if href == "/start" else href) == current else None)
             for label, href in NAV]
    top = topbar.bar() if nav and traveler is None else ""
    return (top, Header(
        A("Skip to content", href="#main", cls="ga-skip"),
        Div(brand(), preview(), cls="ga-brand-row"),
        *((Nav(*links, cls="ga-nav", aria_label="Main"),) if nav else ()),
        account(traveler),
        cls="ga-header ga-wrap", **({"data_has_topbar": "1"} if top else {}),
    ))


def plan_href() -> str:
    """Where "Plan a trip" and "Start a trip" go (D-458): Where to? (/start), where a family starts a trip or brings in one already booked; signed
    out, through sign-in first. The trip matrix is reached from a trip, not from the front door, until booking opens."""
    return "/start" if session.request_traveler() else session.signin_href("/start")


def site_footer(links=()):
    """The footer. `links` is a list of (label, href) shown as a small nav; the landing puts the header's old links here."""
    return Footer(
        Span("GitAway", cls="ga-brand-name"),
        Span("Trips shared by travelers and creators. Sample data only: no real bookings or payments." if showcase.on() else _footer_line(), cls="ga-fine"),      # F-200: fine print
        *((Nav(*[A(label, href=href) for label, href in links], cls="ga-footer-nav", aria_label="More"),) if links else ()),
        Nav(A("Privacy", href="/privacy"), A("Terms", href="/terms"), cls="ga-footer-nav", aria_label="Legal"),
        mode_switch(),
        cls="ga-footer ga-wrap",
    )


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


def page(title: str, *content, current: str = "", theme: str = "sunset", head=(), nav: bool = True, footer_links=(), description: str = "", image: str = "", og_type: str = "website", noindex: bool = False):
    """A full GitAway page. `current` marks the active nav link; `theme` is sunset or pacific.

    `nav=False` drops the header's links (brand and account stay) and `footer_links` adds a footer nav: the landing's pair of options.
    `description` (with `image` and `og_type`) adds the description and Open Graph tags a search result or a shared link shows; `noindex` keeps the page out of search (see `seo_meta`)."""
    return (
        Title(f"GitAway · {title}" if title else "GitAway"),
        *styles(*head, *seo_meta(title, description, image, og_type, noindex), theme=theme),
        Div(site_header(current, nav=nav), join_note(), Main(*content, id="main"), site_footer(footer_links), data_theme=theme, cls="ga-page"),
    )
