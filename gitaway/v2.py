"""The v2 page chrome (F-250, D-610): the flat stage behind the page (F-296: the Harbour ground and the moods are retired), the top bar (the mark, the sample label, the light/dark round button, the account)
and the stylesheets and script a v2 page loads. `layout.page(v2=True)` uses it; a page opts in by that one flag, which puts the class `v2` on its wrapper.
Reference: docs/design/palette-bo/index.html (look C, Stage; Inter); the tokens are assets/css/v2-tokens.css."""

import logging

from fasthtml.common import A, Button, Div, Form, Link, Nav, NotStr, Script, Span

from gitaway import session as session_, showcase
from gitaway.icons import icon

log = logging.getLogger(__name__)

HEAD = (Link(rel="stylesheet", href="/assets/css/v2-tokens.css"), Link(rel="stylesheet", href="/assets/css/v2.css"), Link(rel="stylesheet", href="/assets/css/v2page.css"),
        Link(rel="preload", href="/assets/fonts/inter-variable.woff2", **{"as": "font"}, type="font/woff2", crossorigin=""),
        Script(src="/assets/js/v2.js", defer=True), Script(src="/assets/js/v2top.js", defer=True))

MARK = ('<svg viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" rx="12" fill="#4338CA"/><circle cx="26" cy="15" r="6" fill="#FFD43B"/>'
        '<path d="M5 27c5-4 9-4 14 0s9 4 16 0v8a5 5 0 0 1-5 5H10a5 5 0 0 1-5-5z" fill="#fff"/><path d="M5 31c5-3 9-3 14 0s9 3 16 0" fill="none" stroke="#C92A5E" stroke-width="2.5"/></svg>')


def bg(quiet: bool = False) -> Div:
    """The stage (F-296, D-956; v2.css `.v2-bg`): a flat #F5F5F7 (light) or #000 (dark) behind everything, nothing drawn on it (the Harbour ground, its sun, moon, ridges, shore and the moods are retired).
    A reading page marks it `is-quiet` (F-261, D-701), which also gives the page its foot."""
    return Div(cls="v2-bg is-quiet" if quiet else "v2-bg", aria_hidden="true", **({"data_sky": "quiet"} if quiet else {}))


def section_of(current: str) -> str:
    """Which of the pill's sections a page's `current` names: "trip" is Plan, the planning ask and matrix are Book, the guides (and the old community and creator addresses) are Guides, anything else none."""
    c = (current or "").rstrip("/")
    return ("plan" if c in ("trip", "/trip/plan") else "book" if c == "book" or c.startswith("/plan") else "guides" if c.startswith(("/guides", "/community", "/creators", "/for-creators")) else "")


def admin_notice(session):
    """(reports not yet read, is the captain): the count shows to an admin only, and (0, False) for everyone else."""
    from gitaway.pages import admin  # here, not at the top: that module draws pages with the shell, which draws this bar
    return (admin.new_reports(session), True) if admin.is_admin(session) else (0, False)


def _state(traveler):
    """(has a trip, is the captain, reports not yet read) for the signed-in person; a family whose trips cannot be read is shown as having none."""
    session = session_.request_session()
    if traveler is None or session is None:
        return False, False, 0
    try:
        has_trip = bool(session_.trips(session)) and session_.booking(session) is not None
    except Exception:
        log.exception("could not read the family's trips for the v2 top bar")
        has_trip = False
    new, captain = admin_notice(session)
    return has_trip, captain, new


def items(signed_in: bool, has_trip: bool) -> list:
    """The section pill's items as (key, label, href): Book, My trip (the booked trip's itinerary, only with a trip) and Guides for a signed-in person; Find a trip (the one door, layout.plan_href) and Guides for a visitor (F-289), whose
    Sign in is the account button beside the pill (F-262: Family left the bar; the family lives in Planning's Together drawer and the avatar menu)."""
    if not signed_in:
        from gitaway.layout import plan_href      # here: layout imports this module
        return [("start", "Find a trip", plan_href()), ("guides", "Guides", "/guides")]      # F-289: "plan" means only the booked trip's days now
    return [("book", "Book", showcase.planning_path())] + ([("plan", "My trip", "/trip/plan")] if has_trip else []) + [("guides", "Guides", "/guides")]


def menu_items(captain: bool, new: int = 0, has_trip: bool = False) -> list:
    """The avatar menu's links as (key, label, href): the family's members page (it left the bar, so it stays reachable here) Help · who to call (SOS, F-254: with a trip; /trip/booking?sos=1) and Admin (the captain only); Sign out is its own form."""
    return [("family", "Family members", "/family")] + ([("help", "Help · who to call", "/trip/booking?sos=1")] if has_trip else []) + ([("admin", f"Admin ({new} new)" if new else "Admin", "/admin")] if captain else [])


ITEM = {"role": "menuitem", "tabindex": "-1"}       # what every row of a More menu carries (assets/js/v2top.js moves through them)


def more(*items, ident: str = "more", label: str = "More", dot: bool = False, cls: str = "", compact: bool = False) -> Div:
    """The one quiet button that holds what most people do not need on a screen (F-293, D-946): a small "More" that opens a menu growing out of it (assets/js/v2top.js, the account menu's
    script; Escape closes it and focus returns here). `items` are links or buttons made with `**ITEM`; `dot` marks that something inside is waiting (an unread chat); `compact` is a round button of three dots whose word is only for readers (a card's corner). No items, no button."""
    items = [i for i in items if i != ""]
    if not items:
        return ""
    return Div(Button(icon("more", 20, 2.4), Span(label, cls="sr-only" if compact else ""), Span(cls="v2-dot", id=f"{ident}-dot", hidden=not dot), Span(" (something new inside)", cls="sr-only") if dot else "", type="button", cls="v2-more-btn" + (" is-round" if compact else ""), id=ident, aria_haspopup="menu", aria_expanded="false", aria_controls=f"{ident}-menu"),
               Div(*items, id=f"{ident}-menu", cls="v2-menu v2-glass", role="menu", aria_label=label, hidden=True), cls=("v2-account " + cls).strip(), data_more="1")


def top(current: str = "", sample: str = "Sample prices") -> Div:
    """The brand, a label saying the prices are samples (on the showcase), the sections pill (Book, Plan, Guides; on a phone it floats at the bottom), the light/dark button and
    the account: the avatar and its menu for a signed-in person, Sign in for a visitor."""
    traveler = session_.request_traveler()
    has_trip, captain, new = _state(traveler)
    here = section_of(current)
    pill = Nav(*[A(label, href=href, aria_current="page" if key == here else None) for key, label, href in items(traveler is not None, has_trip)],
               cls="v2-sections v2-glass", aria_label="Sections")
    if traveler:
        menu = Div(*[A(label, href=href, role="menuitem", tabindex="-1") for _, label, href in menu_items(captain, new, has_trip)],
                   Form(Button("Sign out", type="submit", role="menuitem", tabindex="-1"), action="/signout", method="post"),
                   id="v2-menu", cls="v2-menu v2-glass", role="menu", aria_label="Account", hidden=True)
        news = f", {new} new report{'s' if new != 1 else ''}" if new and captain else ""
        account = Div(Button(Span(traveler.initials), Span(cls="v2-dot") if news else "", type="button", cls="v2-round", id="v2-me", aria_haspopup="menu", aria_expanded="false",
                             aria_controls="v2-menu", aria_label=f"{traveler.name}: account menu{news}", title=traveler.name), menu, cls="v2-account", data_more="1")
    else:
        account = A("Sign in", href=session_.signin_href(), cls="v2-signin")
    mode = Button(Span(icon("moon", 20), cls="ga-mode-moon"), Span(icon("sun", 20), cls="ga-mode-sun"), type="button", cls="v2-round", id="ga-mode-v2", data_mode_toggle="1",
                  aria_pressed="false", aria_label="Dark mode", title="Dark mode")
    from gitaway.layout import preview      # here: layout imports this module
    return Div(A(NotStr(MARK), "GitAway", href="/", cls="v2-brand", aria_label="GitAway"), preview(), Span(cls="sp"),
               pill, Span(cls="sp"), Span(sample, cls="v2-pill") if showcase.on() else "", mode, account, cls="v2-top")
