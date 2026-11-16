"""The top bar of the signed-in web on the pages that are not v2 (the family page, the admin, the legal pages, the import of a trip already booked, sign-in's neighbours): the brand island, the nav pill
Book | Plan | Guides in the middle and the avatar menu on the right. It says what the v2 bar (gitaway/v2.py, F-255) says, in Direction A's chrome; F-254 took out the old Trip, Family and Ask sections,
the trip picker and SOS with the pages they opened.

    bar()    the bar for this request's signed-in person ("" when signed out); topbar.css shows it from 1020px up (the tablet and the phone keep the site header)
    STYLE    the stylesheet link, which layout.styles() adds to every page
    SCRIPT   topbar.js: the avatar menu

Book goes to the way in (`showcase.planning_path`), Plan to the trip's calendar (only with a trip), Guides to /guides; the avatar's menu holds Family members, Admin (the captain, with the count of
reports not yet read), the light and dark switch and Sign out.
"""

import logging

from fasthtml.common import A, Button, Details, Div, Form, Header, Nav, Span, Summary

from gitaway import session as ses, showcase
from gitaway.icons import icon
from gitaway.layout import mark, mode_switch, preview

log = logging.getLogger(__name__)

STYLE_HREF = "/assets/css/topbar.css"
SCRIPT_SRC = "/assets/js/topbar.js"


def section(path: str) -> str:
    """Which of Book, Plan and Guides a path belongs to: "book", "plan", "guides", or "" (the family page and the like)."""
    p = (path or "").split("?")[0].rstrip("/") or "/"
    if p.startswith("/guides") or p.startswith("/creators"):
        return "guides"
    if p == "/trip/plan" or p.startswith("/trip/"):
        return "plan"
    if p.startswith(("/plan", "/trips/import", "/trips/build")):
        return "book"
    return ""


def _link(label, href, key, current, ico=None, **extra):
    return A(icon(ico, 15, 2.2) if ico else "", label, href=href, cls=f"ga-tb-link ga-tb-{key}", aria_current="page" if key == current else None, **extra)


def _me(who, new=0, admin=False):
    """The avatar and its menu: who is signed in, Family members, for the captain Admin with the count of reports not yet read (F-196: a dot on the avatar says there is one) and Sign out."""
    return Details(
        Summary(Span(who.initials, cls=f"ga-tb-av fill-{who.color}"), Span(cls="ga-tb-dot-new") if new else "", cls="ga-tb-sum ga-tb-sum-me",
                aria_label=f"{who.name}: account menu" + (f", {new} new report{'s' if new != 1 else ''}" if new else "")),
        Div(Span(who.name, cls="ga-tb-who"), Span(who.blurb, cls="ga-tb-mail"),
            A(icon("users", 16, 2.2), "Family members", href="/family", cls="ga-tb-item"),
            A(icon("shield", 16, 2.2), "Admin", Span(f"{new} new", cls="ga-tb-new") if new else "", href="/admin", cls="ga-tb-item", id="ga-tb-admin") if admin else "",
            mode_switch("menu"),      # F-200: light, dark or the system's, remembered on this device
            Form(Button(icon("lock", 16, 2.2), "Sign out", type="submit", cls="ga-tb-item ga-tb-out"), action="/signout", method="post"),
            cls="ga-tb-pop ga-tb-pop-me"),
        cls="ga-tb-menu ga-tb-account")


def _admin_notice(session):
    """(reports not yet read, is the captain): the count shows to an admin only, and (0, False) for everyone else."""
    from gitaway.pages import admin  # here, not at the top: that module draws pages with the shell, which draws this bar
    return (admin.new_reports(session), True) if admin.is_admin(session) else (0, False)


def bar(path=None):
    """The top bar, or "" when nobody is signed in. `path` defaults to the request's own (to mark the section)."""
    who = ses.request_traveler()
    session = ses.request_session()
    if who is None or session is None:
        return ""
    try:
        has_trip = bool(ses.trips(session)) and ses.booking(session) is not None
    except Exception:  # the bar must never take a page down: without the family's trips it shows the trip-less bar
        log.exception("could not read the family's trips for the top bar")
        has_trip = False
    current = section(path if path is not None else ses.request_path())
    return Header(       # F-200: three islands: the brand on the left, the nav pill in the middle, you on the right
        A("Skip to content", href="#main", cls="ga-skip"),
        Div(A(mark(), Span("GitAway", cls="ga-brand-name"), href="/", cls="ga-brand", aria_label="GitAway home"),
            preview(), cls="ga-tb-l"),       # the honest "Early preview" label, beside the brand
        Nav(_link("Book", showcase.planning_path(), "book", current, "ticket"),
            _link("Plan", "/trip/plan", "plan", current, "calendar") if has_trip else "",
            _link("Guides", "/guides", "guides", current, "star"),
            cls="ga-tb-nav", aria_label="Sections"),
        Div(_me(who, *_admin_notice(session)), cls="ga-tb-r"),
        cls="ga-topbar", data_topbar="1")
