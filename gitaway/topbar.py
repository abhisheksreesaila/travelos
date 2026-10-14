"""The one top bar of the signed-in web (F-139): brand, Trip | Family | Ask, the trip picker, SOS and the avatar menu.

    bar()    the bar for this request's signed-in person ("" when signed out), drawn on every signed-in page; topbar.css shows it from 1020px up
    STYLE    the stylesheet link, which layout.styles() adds to every page (the old header and the phone's tabs are unchanged below that width)
    SCRIPT   topbar.js: the two menus and the "/" key

The section marked is worked out from the request's path (`section`). Trip goes to /trip, which opens the open trip's day (today during the
trip, else day 1); a family with no trip gets Start in its place. Ask and Family open what exists today (F-142 and F-143 dock them in a panel):
Ask is the Ask box page (/trip/ask) and Family the family chat (/trip/family); "People and invites" in the avatar menu is the /family page.
"""

import logging

from fasthtml.common import A, Button, Details, Div, Form, Header, Input, Kbd, Li, Nav, P, Script, Span, Summary, Ul

from gitaway import session as ses, showcase
from gitaway.icons import icon

log = logging.getLogger(__name__)

STYLE_HREF = "/assets/css/topbar.css"
SCRIPT_SRC = "/assets/js/topbar.js"


def section(path: str) -> str:
    """Which of Trip, Family and Ask a path belongs to: "ask", "family", "trip", or "" (the community and the like)."""
    p = (path or "").split("?")[0].rstrip("/") or "/"
    if p == "/trip/ask":
        return "ask"
    if p == "/family" or p.startswith("/family/") or p == "/trip/family" or p.startswith("/trip/family/"):
        return "family"
    if p in ("/trip", "/calendar", "/start", "/plan", "/rides") or p.startswith(("/trip/", "/calendar/", "/trips/build", "/trips/import", "/plan/", "/start/")):
        return "trip"
    return ""


def _link(label, href, key, current, ico=None, **extra):
    return A(icon(ico, 15, 2.2) if ico else "", label, href=href, cls=f"ga-tb-link ga-tb-{key}", aria_current="page" if key == current else None, **extra)


def _trip_pick(trips, b):
    """The trip picker: the open trip's name and dates; its menu switches trips (POST /trips/switch, as the calendar's did) and plans or imports another."""
    from gitaway import tripcal as cal
    t = cal.trip("", b) if b else None
    dates = cal.range_label(t.depart, t.return_) if t else ""
    mine = [Li(Form(Input(type="hidden", name="trip", value=x.id), Input(type="hidden", name="next", value="/trip"),
                    Button(Span(x.title, cls="ga-tb-sw-name"), Span(x.detail, cls="ga-tb-sw-dates"), type="submit", aria_current="true" if x.current else None, cls="ga-tb-sw"),
                    action="/trips/switch", method="post")) for x in trips]
    name = t.title if t else (trips[0].title if trips else "")
    return Details(
        Summary(Span(icon("sun", 15, 2.2), cls="ga-tb-tdot"), Span(name, cls="ga-tb-pickname"), Span(dates, cls="ga-tb-pickdates") if dates else "", icon("chev-right", 14, 2.6, "ga-tb-chev"),
                cls="ga-tb-sum", aria_label=f"Trip: {name}. Switch trips"),
        Div(Span("Your trips", cls="ga-tb-k") if len(trips) > 1 else P("This is your only trip so far. Add another and switch between them here.", cls="ga-tb-solo"),
            Ul(*mine, cls="ga-tb-list") if len(trips) > 1 else "",
            A(icon("plus", 16, 2.4), "Plan another trip", href="/start", cls="ga-tb-item"),
            A(icon("ledger", 16, 2.4), "Import a trip you booked", href="/trips/import", cls="ga-tb-item"),
            cls="ga-tb-pop ga-tb-pop-trip"),
        cls="ga-tb-menu ga-tb-picker")


def _me(who):
    """The avatar and its menu: who is signed in, People and invites, (the community, only with the showcase on) and Sign out."""
    extra = [A(icon("star", 16, 2.2), "Community trips", href="/community", cls="ga-tb-item"), A(icon("pencil", 16, 2.2), "For creators", href="/creators", cls="ga-tb-item")] if showcase.on() else []
    return Details(
        Summary(Span(who.initials, cls=f"ga-tb-av fill-{who.color}"), cls="ga-tb-sum ga-tb-sum-me", aria_label=f"{who.name}: account menu"),
        Div(Span(who.name, cls="ga-tb-who"), Span(who.blurb, cls="ga-tb-mail"),
            A(icon("users", 16, 2.2), "People and invites", href="/family", cls="ga-tb-item"),
            *extra,
            Form(Button(icon("lock", 16, 2.2), "Sign out", type="submit", cls="ga-tb-item ga-tb-out"), action="/signout", method="post"),
            cls="ga-tb-pop ga-tb-pop-me"),
        cls="ga-tb-menu ga-tb-account")


def bar(path=None):
    """The top bar, or "" when nobody is signed in. `path` defaults to the request's own (to mark the section)."""
    who = ses.request_traveler()
    session = ses.request_session()
    if who is None or session is None:
        return ""
    try:
        trips = ses.trips(session)
        b = ses.booking(session) if trips else None
    except Exception:  # the bar must never take a page down: without the family's trips it shows the trip-less bar
        log.exception("could not read the family's trips for the top bar")
        trips, b = [], None
    from gitaway.pages import tripcanvas  # here, not at the top: that module draws pages with the shell, which draws this bar
    current = section(path if path is not None else ses.request_path())
    has_trip = bool(trips) and b is not None
    return Header(
        A("Skip to content", href="#main", cls="ga-skip"),
        A(Span(icon("fork", 18, 2.5), cls="ga-brand-mark"), Span("GitAway", cls="ga-brand-name"), href="/", cls="ga-brand", aria_label="GitAway home"),
        Nav(_link("Trip", "/trip", "trip", current, "calendar") if has_trip else _link("Start", "/start", "trip", current, "plus"),
            _link("Family", "/trip/family" if has_trip else "/family", "family", current, "users"),
            A(Span(icon("mic", 12, 2.6), cls="ga-tb-dot"), "Ask", Kbd("/", cls="ga-tb-kbd"), href="/trip/ask", cls="ga-tb-link ga-tb-ask", id="ga-tb-ask", aria_current="page" if current == "ask" else None,
              aria_keyshortcuts="/"),
            cls="ga-tb-nav", aria_label="Sections"),
        Span(cls="ga-tb-sp"),
        _trip_pick(trips, b) if has_trip else "",
        A(icon("life", 15, 2.4), Span("SOS"), href=tripcanvas.curl(sos=True), cls="ga-tb-sos", aria_label="Emergency: call 911 and your people") if has_trip else "",
        _me(who),
        cls="ga-topbar", data_topbar="1")
