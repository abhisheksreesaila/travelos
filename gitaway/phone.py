"""The phone shell (F-067): every trip screen sits in one frame with a bottom tab bar (Today, Ask, Family: three, so Ask is the true centre; Map is a button in the day heading (F-096); Help left the bar in F-093 and is opened from a booking or the SOS button).

    shell(active, *content, title="", head=(), scripts=(), **attrs)   the whole document: styles, the screen's content, the tab bar
    tabbar(active)                                                     the bar alone (`active` is one of TAB_KEYS)
    header(kicker, title, faces=())                                    the screen heading the tabs share
    coming(name, line, ico)                                            the short "coming" card a tab shows until it is built
    guard(session, path)                                               a redirect when the traveler is not signed in or has no trip yet, else None

Today is gitaway/pages/trip.py. Each other tab is a module in gitaway/pages/ (tab_map, tab_ask, tab_family, tab_help) exposing
`content(request, session)` (what goes between the heading and the bar) and, optionally, `HEAD` and `SCRIPTS` tuples for its own
stylesheet and script; gitaway/pages/phone_tabs.py registers the routes and builds the shell around them. Replacing a tab means
editing only its module. On a laptop the bar is hidden and the existing header and layout stay; the bar shows at phone width (720px
and under) and in the installed Home Screen app.
"""

from urllib.parse import quote

from fasthtml.common import A, Div, H1, H2, Header, Link, Nav, P, Script, Span, Title
from starlette.responses import RedirectResponse

from gitaway import session as ses
from gitaway.icons import icon
from gitaway.layout import styles

TABS = (("today", "Today", "calendar", "/trip"), ("ask", "Ask", "mic", "/trip/ask"),
        ("family", "Family", "users", "/trip/family"))   # F-093: Help left the bar; /trip/help still works for old links, passes and phone numbers
TAB_KEYS = tuple(t[0] for t in TABS)
HEAD = (Link(rel="stylesheet", href="/assets/css/trip.css"), Link(rel="stylesheet", href="/assets/css/phone.css"))  # the shared phone look, then the shell


def tabbar(active):
    links = [A(Span(icon(ico, 22, 2.2), cls="ph-ti"), name, href=href, id=f"ph-tab-{key}", cls=f"ph-tab{' ph-ask' if key == 'ask' else ''}",
               aria_current="page" if key == active else None) for key, name, ico, href in TABS]
    return Nav(*links, cls="ph-tabs", aria_label="Trip")


def header(kicker, title, faces=(), sos=False):
    """`sos`: a small SOS button (F-093) that opens the emergency sheet on the trip canvas; the Ask and Family tabs have it, the canvas has its own."""
    button = A(icon("life", 18, 2.4), Span("SOS"), href="/trip/canvas?sos=1", id="ph-sos", cls="ph-sos", aria_label="Emergency: call 911 and your people") if sos else ""
    return Header(Div(Span(kicker, cls="tp-head-k"), H1(title, id="tp-title-h"), cls="tp-head-text"), button, Div(*faces, cls="tp-faces") if faces else "", cls="tp-head")


def coming(name, line, ico):
    """The card a tab shows until it is built."""
    return Div(Span(icon(ico, 30, 2.2), cls="ph-coming-ico"), H2(f"{name} is coming"), P(line), A("Back to Today", href="/trip", cls="tp-btn tp-btn-ink"), cls="ph-coming", id="ph-coming", role="status")


def shell(active, *content, title="", head=(), scripts=(), **attrs):
    attrs.setdefault("id", "ph-app")
    return (
        Title(f"GitAway · {title}" if title else "GitAway"),
        *styles(*head, *HEAD),
        Div(A("Skip to content", href="#main", cls="ga-skip"), *content, A("Back to Today", href="/trip", cls="ph-back") if active != "today" else "", tabbar(active),
            data_theme="sunset", data_screen=active, cls="tp ph", **attrs),
        *[Script(src=s, defer=True) for s in scripts],
    )


def guard(session, path):
    if not ses.current_traveler(session):
        return RedirectResponse(f"/signin?next={quote(path, safe='')}", status_code=303)
    if not ses.booking(session):
        return RedirectResponse("/start", status_code=303)
    return None
