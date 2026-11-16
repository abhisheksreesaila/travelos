"""The v2 page chrome (F-250, D-610): the sky behind the page (a sun, clouds, the shore), the top bar (the mark, the sample label, the light/dark round button, the account)
and the stylesheets and script a v2 page loads. `layout.page(v2=True)` uses it; a page opts in by that one flag, which puts the class `v2` on its wrapper.
Reference: docs/design/booking-v2/index.html (type pairing C, Newsreader with Inter); the tokens are assets/css/v2-tokens.css."""

import logging

from fasthtml.common import A, Button, Div, Form, Link, Nav, NotStr, Script, Span

from gitaway import session as session_, showcase
from gitaway.icons import icon

log = logging.getLogger(__name__)

HEAD = (Link(rel="stylesheet", href="/assets/css/v2-tokens.css"), Link(rel="stylesheet", href="/assets/css/v2.css"), Link(rel="stylesheet", href="/assets/css/v2page.css"), Link(rel="stylesheet", href="/assets/css/v2-moods.css"),
        Link(rel="preload", href="/assets/fonts/inter-variable.woff2", **{"as": "font"}, type="font/woff2", crossorigin=""),
        Link(rel="preload", href="/assets/fonts/newsreader-variable.woff2", **{"as": "font"}, type="font/woff2", crossorigin=""),
        Script(src="/assets/js/v2.js", defer=True), Script(src="/assets/js/v2top.js", defer=True))

CLOUD = '<path d="M20 44a16 16 0 0 1 2-32 22 22 0 0 1 40-4 18 18 0 0 1 32 10 13 13 0 0 1 6 26z"/>'
MARK = ('<svg viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" rx="12" fill="#4338CA"/><circle cx="26" cy="15" r="6" fill="#FFD43B"/>'
        '<path d="M5 27c5-4 9-4 14 0s9 4 16 0v8a5 5 0 0 1-5 5H10a5 5 0 0 1-5-5z" fill="#fff"/><path d="M5 31c5-3 9-3 14 0s9 3 16 0" fill="none" stroke="#C92A5E" stroke-width="2.5"/></svg>')


def _palm(x, y, s=1.0, c="#1F8A5B", t="#7A4E26") -> str:
    return (f'<g transform="translate({x} {y}) scale({s})"><path d="M0 0 Q2 -14 6 -28" fill="none" stroke="{t}" stroke-width="2.4" stroke-linecap="round"/><g fill="{c}">'
            '<path d="M6 -28q-10-3-15 4 8-3 15-4z"/><path d="M6 -28q10-4 15 3-8-3-15-3z"/><path d="M6 -28q-5-9-13-8 8 2 13 8z"/><path d="M6 -28q4-10 12-9-8 2-12 9z"/></g></g>')


def _shore() -> str:
    """The landing's foot: hills, a sea, a pier, a sailboat, a beach and palms (the cover's scene, redrawn as the prototype draws it)."""
    piles = "".join(f'<rect x="{130 + i * 24}" y="134" width="4" height="40" fill="#2B3A4A"/>' for i in range(16))
    palms = "".join(_palm(x, y, s) for x, y, s in ((1180, 214, 2.1), (1240, 220, 1.6), (1320, 212, 2.4), (70, 222, 1.8)))
    return ('<path d="M0 120 Q160 70 330 110 T700 96 T1060 108 T1440 92 V260 H0Z" fill="#C9B9D9" opacity=".55"/>'
            '<path d="M0 150 Q240 132 480 146 T960 140 T1440 148 V260 H0Z" fill="#A7D3EE"/><path d="M0 176 Q240 160 480 172 T960 166 T1440 174 V260 H0Z" fill="#78B8E3"/>'
            f'<rect x="120" y="128" width="380" height="6" fill="#2B3A4A"/>{piles}<rect x="456" y="104" width="40" height="24" rx="2" fill="#E4572E"/><path d="M450 104h52l-26-14z" fill="#2B3A4A"/>'
            '<path d="M0 214 Q300 190 640 206 T1440 200 V260 H0Z" fill="#F4D9A0"/>' + palms +
            '<g transform="translate(860 150)"><path d="M0 0 h60 l-8 10 h-44z" fill="#C2410C"/><path d="M28 0 V-46 L56 -4z" fill="#FFD43B"/><path d="M26 -2 V-38 L6 -4z" fill="#fff"/></g>')


def bg(mood: str = "", quiet: bool = False) -> Div:
    """The sky: a gradient, a sun that becomes a moon in the dark, clouds and the mood's one object at the foot (beach: the shore; F-260, gitaway/moods.py). A `?mood=` preview wins on the showcase."""
    if quiet:      # a reading page (F-261, D-701): no sun, moon, clouds, shore or mood object, only a soft gradient framing the content column (v2.css `.v2-bg.is-quiet`)
        return Div(cls="v2-bg is-quiet", aria_hidden="true", data_sky="quiet")
    from gitaway import moodart, moods
    mood = moods.preview(session_.request_path()) or (mood if mood in moods.MOODS else moods.DEFAULT)
    cloud = lambda style: NotStr(f'<svg class="cloud" style="{style}" viewBox="0 0 120 50">{CLOUD}</svg>')      # noqa: E731
    foot = moodart.FEET.get(mood) or _shore()
    return Div(Div(cls="sunball"), NotStr(moodart.MOON), NotStr(moodart.STARS), cloud("left:6%;top:9%;width:170px"), cloud("left:58%;top:22%;width:120px;animation-duration:80s"), cloud("left:28%;top:44%;width:200px;animation-duration:95s"),
               NotStr(f'<svg class="shore" viewBox="0 0 1440 260" preserveAspectRatio="xMidYMax slice">{foot}</svg>'), cls="v2-bg", aria_hidden="true", data_mood=mood)


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
    """The section pill's items as (key, label, href): Book, Plan (only with a trip) and Guides for a signed-in person; Plan a trip (the one door, layout.plan_href) and Guides for a visitor, whose
    Sign in is the account button beside the pill (F-262: Family left the bar; the family lives in Planning's Together drawer and the avatar menu)."""
    if not signed_in:
        from gitaway.layout import plan_href      # here: layout imports this module
        return [("start", "Plan a trip", plan_href()), ("guides", "Guides", "/guides")]
    return [("book", "Book", showcase.planning_path())] + ([("plan", "Plan", "/trip/plan")] if has_trip else []) + [("guides", "Guides", "/guides")]


def menu_items(captain: bool, new: int = 0, has_trip: bool = False) -> list:
    """The avatar menu's links as (key, label, href): the family's members page (it left the bar, so it stays reachable here) Help · who to call (SOS, F-254: with a trip; /trip/booking?sos=1) and Admin (the captain only); Sign out is its own form."""
    return [("family", "Family members", "/family")] + ([("help", "Help · who to call", "/trip/booking?sos=1")] if has_trip else []) + ([("admin", f"Admin ({new} new)" if new else "Admin", "/admin")] if captain else [])


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
                             aria_controls="v2-menu", aria_label=f"{traveler.name}: account menu{news}", title=traveler.name), menu, cls="v2-account")
    else:
        account = A("Sign in", href=session_.signin_href(), cls="v2-signin")
    mode = Button(Span(icon("moon", 20), cls="ga-mode-moon"), Span(icon("sun", 20), cls="ga-mode-sun"), type="button", cls="v2-round", id="ga-mode-v2", data_mode_toggle="1",
                  aria_pressed="false", aria_label="Dark mode", title="Dark mode")
    from gitaway.layout import preview      # here: layout imports this module
    return Div(A(NotStr(MARK), "GitAway", href="/", cls="v2-brand", aria_label="GitAway"), preview(), Span(cls="sp"),
               pill, Span(cls="sp"), Span(sample, cls="v2-pill") if showcase.on() else "", mode, account, cls="v2-top")
