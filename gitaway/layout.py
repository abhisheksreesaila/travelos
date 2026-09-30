"""The page shell every GitAway screen shares: fonts, tokens, header and footer."""

from fasthtml.common import A, Div, Footer, Header, Link, Main, Nav, Span, Title

from gitaway.icons import icon

FONTS = (
    "https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800"
    "&family=Figtree:wght@400;500;600;700;800&family=Caveat:wght@600;700&display=swap"
)

HEAD = (
    Link(rel="preconnect", href="https://fonts.googleapis.com"),
    Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
    Link(rel="stylesheet", href=FONTS),
)

def styles(*extra):
    """The shared stylesheets in cascade order (tokens, base), then any page-specific head items.

    page() uses this; a page that builds its own document should too, so page CSS always wins over base.css.
    """
    return (
        Link(rel="stylesheet", href="/assets/css/tokens.css"),
        Link(rel="stylesheet", href="/assets/css/base.css"),
        *extra,
    )

NAV = [("Discover", "/discover"), ("Plan a trip", "/plan"), ("For creators", "/creators")]


def brand(href: str = "/"):
    return A(
        Span(icon("fork", 22, 2.4), cls="ga-brand-mark"),
        Span("GitAway", cls="ga-brand-name"),
        href=href, cls="ga-brand", aria_label="GitAway home",
    )


def site_header(current: str = ""):
    links = [A(label, href=href, aria_current="page" if href == current else None) for label, href in NAV]
    return Header(
        A("Skip to content", href="#main", cls="ga-skip"),
        brand(),
        Nav(*links, cls="ga-nav", aria_label="Main"),
        A("Sign in", href="/signin", cls="btn btn-sm"),
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
        *styles(*head),
        Div(site_header(current), Main(*content, id="main"), site_footer(), data_theme=theme, cls="ga-page"),
    )
