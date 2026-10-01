"""The page shell every GitAway screen shares: fonts, tokens, header and footer."""

import hashlib
import hmac

from fasthtml.common import A, Button, Div, Footer, Form, Header, Link, Main, Meta, Nav, Script, Span, Title

from gitaway import session
from gitaway.icons import icon


def trip_field():
    """A hidden `trip` input naming the trip this page was drawn for, so a form posted later from a stale tab changes that trip only.

    It reads the trip the request resolved, which happens when the family is first opened (any `ses.booking`, `cal.activities` ...): call
    it only while rendering a page that has already done so. Before that it returns "", and tests/test_family_storage.py fails a page whose
    post forms lack it."""
    from fasthtml.common import Input
    t = session.open_trip_id()
    return Input(type="hidden", name="trip", value=t) if t else ""

FONTS = (
    "https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800"
    "&family=Figtree:wght@400;500;600;700;800&family=Caveat:wght@600;700&display=swap"
)

PAPER = "#FFF8EE"  # --paper / --ground: the manifest's colours
THEME_COLORS = {"sunset": PAPER, "pacific": "#F4F9FF"}  # each theme's --ground, for the browser chrome
CLEAR_SITE_DATA = '"cache", "storage"'


def clear_site_data(response):
    """Make the browser forget this site's caches and storage (saved pages, service worker). Call it on every sign-out.

    /logout and /signout (gitaway/pages/signin.py) both pass their response through this.
    """
    response.headers["Clear-Site-Data"] = CLEAR_SITE_DATA
    return response


def cache_key(traveler=None):
    """A short, non-secret per-person key the service worker files saved pages under (None when signed out)."""
    traveler = traveler or session.request_traveler()
    return hmac.new(session.cache_secret(), traveler.id.encode(), hashlib.sha256).hexdigest()[:10] if traveler else None

HEAD = (
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
        Meta(name="theme-color", content=THEME_COLORS.get(theme, PAPER)),
        *((Meta(name="ga-user", content=key),) if key else ()),
        Link(rel="stylesheet", href="/assets/css/tokens.css"),
        Link(rel="stylesheet", href="/assets/css/base.css"),
        *extra,
    )

NAV = [("Discover", "/discover"), ("Plan a trip", "/start"), ("For creators", "/creators")]


def brand(href: str = "/"):
    return A(
        Span(icon("fork", 22, 2.4), cls="ga-brand-mark"),
        Span("GitAway", cls="ga-brand-name"),
        href=href, cls="ga-brand", aria_label="GitAway home",
    )


def avatar(traveler, cls="ga-avatar"):
    return Span(traveler.initials, cls=f"{cls} fill-{traveler.color}", title=traveler.name, aria_label=traveler.name)


def account(traveler=None):
    """Sign in link, or the traveler's avatar plus Sign out. Defaults to the request's traveler (see gitaway.session)."""
    traveler = traveler or session.request_traveler()
    if not traveler:
        return A("Sign in", href=session.signin_href(), cls="btn btn-sm")
    return Div(
        avatar(traveler),
        Form(Button("Sign out", type="submit", cls="ga-signout"), action="/signout", method="post"),
        cls="ga-account",
    )


def site_header(current: str = "", traveler=None):
    links = [A(label, href=href, aria_current="page" if href == current else None) for label, href in NAV]
    return Header(
        A("Skip to content", href="#main", cls="ga-skip"),
        brand(),
        Nav(*links, cls="ga-nav", aria_label="Main"),
        account(traveler),
        cls="ga-header ga-wrap",
    )


def site_footer():
    return Footer(
        Span("GitAway", cls="ga-brand-name"),
        Span("Trips shared by travelers and creators. Sample data only: no real bookings or payments."),
        cls="ga-footer ga-wrap",
    )


def page(title: str, *content, current: str = "", theme: str = "sunset", head=()):
    """A full GitAway page. `current` marks the active nav link; `theme` is sunset or pacific."""
    return (
        Title(f"GitAway · {title}" if title else "GitAway"),
        *styles(*head, theme=theme),
        Div(site_header(current), Main(*content, id="main"), site_footer(), data_theme=theme, cls="ga-page"),
    )
