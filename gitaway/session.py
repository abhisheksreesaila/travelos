"""The signed-in person and the cookie-held trip state. Public helpers for every screen.

Sign-in is fh-saas's (see gitaway.auth): the session holds `user_id` and `email`, and `current_traveler` is the thin
adapter that maps that person to the "traveler" every screen speaks of (id = the fh-saas user id, name from the email).
F-040 and F-041 move the rest of this state into SQLite.

Session shape: {"user_id": "<fh-saas user id>", "email": "<email>", "forks": {"<id>": ["<trip slug>", ...]}, "friends": {"<id>": ["<name>", ...]}}.
Pure functions over a session dict, so tests and later tickets (F-018 pay, F-021 forks list) can use them directly.

For the header, `bind` is a beforeware (see main.py) that records the current traveler in a ContextVar for the
request; layout.site_header reads it with `request_traveler()`. Outside a request it is None (signed out).
"""

import hashlib
import json
import re
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlsplit

from gitaway import catalog


@dataclass(frozen=True)
class Traveler:
    id: str
    name: str
    initials: str
    blurb: str
    color: str  # a fill-* class from base.css


_COLORS = ("sun", "sky", "grape", "mint", "bubble")
BUDGET = 2600  # bytes of session JSON; base64 adds a third plus a signature, keeping the whole cookie near 3.4 KB (limit 3.6 KB, browsers drop >4 KB)
MAX_FRIENDS = 6
MAX_FRIEND_NAME = 20
DEMO_FRIENDS = ("Mom", "Sam")
_FRIEND_COLORS = ("sun", "sky", "grape", "mint", "bubble")
INTENTS = ("save", "pay", "invite", "fork", "publish")

_BAD_CHARS = re.compile(r"[\x00-\x20\x7f\\]")


def safe_next(value, default="/"):
    """A local path or `default`. Refuses absolute URLs, //host, backslashes, control chars and encoded tricks."""
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        return default
    decoded = unquote(value)
    if _BAD_CHARS.search(value) or _BAD_CHARS.search(decoded) or decoded.startswith("//"):
        return default
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return default
    return value


def _display_name(email):
    """"ari.rivera@gmail.com" -> "Ari Rivera"; the part before the @, split on dots, dashes and underscores."""
    local = re.sub(r"[._\-+]+", " ", (email or "").split("@")[0]).strip()
    return local.title() if local else "Traveler"


def current_traveler(session):
    """The signed-in person as a Traveler, or None. Pure over the session dict (`user_id` and `email`)."""
    uid = (session or {}).get("user_id")
    if not uid:
        return None
    email = session.get("email") or ""
    name = _display_name(email)
    words = name.split()
    initials = (words[0][0] + words[1][0] if len(words) > 1 else name[:2]).upper()
    color = _COLORS[int(hashlib.sha256((email or str(uid)).encode()).hexdigest(), 16) % len(_COLORS)]
    return Traveler(str(uid), name, initials, email or "Signed in", color)


# Everything fh-saas keeps in the session for the sign-in; sign_out removes exactly these and leaves the rest.
AUTH_KEYS = ("user_id", "email", "tenant_id", "tenant_role", "is_sys_admin", "login_at", "session_started_at",
             "_auth_cache", "oauth_state", "login_next", "login_intent")


def sign_in(session, user_id, email=""):
    """Put a person in a plain session dict (what fh-saas's create_user_session does, minus the tenant). For tests and model code."""
    session["user_id"], session["email"] = user_id, email
    return current_traveler(session)


def sign_out(session):
    for key in AUTH_KEYS:
        session.pop(key, None)


def forks(session):
    """Trip slugs the signed-in traveler has forked, oldest first. Empty when signed out."""
    t = current_traveler(session)
    return list(session.get("forks", {}).get(t.id, [])) if t else []


def trip_slug(path):
    m = re.fullmatch(r"/trips/([A-Za-z0-9][A-Za-z0-9_-]*)/?", urlsplit(path or "").path)
    return m.group(1) if m else None


class KeepError(ValueError):
    """A fork or save the demo refuses because the session cookie has no room; the message is fit to show."""


def _keep(session, key, current, next_path):
    """Add the trip in a /trips/<slug> path to the traveler's `key` list (forks or saves).

    False when signed out, when the path is not a trip that exists, or when it is already there. Raises KeepError
    (and changes nothing) when the signed cookie would grow past BUDGET.
    """
    from gitaway import forks as forks_model  # here, not at the top: forks imports this module
    t, slug = current_traveler(session), trip_slug(next_path)
    if not t or not slug or slug in current or not forks_model.resolve(session, slug):
        return False
    old = session.get(key)
    # Reassign the whole dict so the cookie session notices the change.
    session[key] = {**(old or {}), t.id: [*current, slug]}
    if len(json.dumps(dict(session))) > BUDGET:
        if old is None:
            session.pop(key, None)
        else:
            session[key] = old
        raise KeepError("This demo is full. Delete something from your calendar to make room.")
    return True


def add_fork(session, next_path):
    """Fork the trip in a /trips/<slug> path for the current traveler (see _keep for the False and KeepError cases)."""
    return _keep(session, "forks", forks(session), next_path)


def saved(session):
    """Trip slugs the signed-in traveler has saved with the heart, oldest first. Empty when signed out.

    Session shape: "saves": {"<traveler id>": ["<trip slug>", ...]}, like forks.
    """
    t = current_traveler(session)
    return list((session.get("saves") or {}).get(t.id, [])) if t else []


def add_save(session, next_path):
    """Save the trip in a /trips/<slug> path for the current traveler (see _keep for the False and KeepError cases)."""
    return _keep(session, "saves", saved(session), next_path)


def remove_save(session, next_path):
    """Un-save the trip in a /trips/<slug> path. False when it was not saved."""
    t, slug = current_traveler(session), trip_slug(next_path)
    if not t or not slug or slug not in saved(session):
        return False
    session["saves"] = {**session["saves"], t.id: [s for s in saved(session) if s != slug]}
    return True


def booking(session):
    """The signed-in traveler's booked trip (a dict), or None when signed out or nothing is booked."""
    t = current_traveler(session)
    return (session.get("bookings") or {}).get(t.id) if t else None


def remembered_plan(session):
    """The workspace picks (a /plan query string) the signed-in traveler last looked at, or None."""
    t = current_traveler(session)
    return (session.get("plan") or {}).get(t.id) if t else None


def remember_plan(session, query):
    """Remember the picks `query` (e.g. "f=f2&h=h3&c=c1&d=..") for the signed-in traveler. Only writes when it changed."""
    t = current_traveler(session)
    if not t or remembered_plan(session) == query:
        return
    old = session.get("plan")
    # Reassign the whole dict so the cookie session notices the change.
    session["plan"] = {**(old or {}), t.id: query}
    if len(json.dumps(dict(session))) > BUDGET:  # same cookie budget as the calendar: skip remembering rather than overflow
        if old is None:
            session.pop("plan", None)
        else:
            session["plan"] = old


def booking_id(traveler_id, flight, stay, car, rooms="", add="", trip="", fare="", bags=""):
    """A stable id for one traveler's picks, so paying the same trip twice is the same booking. Default rooms, no add-ons, the sample trip and a Basic fare with no bags hash as before."""
    digest = hashlib.sha256(f"{traveler_id}|{flight}|{stay}|{car}{'|' + rooms + '|' + add if rooms or add else ''}{'|' + trip if trip else ''}{'|F' + fare + '|' + bags if fare or bags else ''}".encode()).hexdigest()
    return "GA-" + digest[:8].upper()


class BookingError(ValueError):
    """A booking the demo refuses; the message is fit to show the traveler."""


NOTHING_PICKED = "Pick at least one thing to book: a flight, a stay or a car."


def book(session, quote):
    """Record `quote` (a catalog.Quote) as the current traveler's booked trip. Idempotent.

    Returns the booking, or None when signed out. Raises BookingError when the session cookie has no room for it. Paying the same picks again keeps the original booking untouched.
    Session shape: "bookings": {"<traveler id>": {"id", "flight", "stay", "car", "rooms", "add", "total_cents", "booked_at"; "fare", "bags" and "trip" only when set}}
    (rooms and add are the stay's compact pick codes, "" for the default room and no add-ons; fare and bags are the flight's, "" for Basic and no bags).
    A skipped lane is stored as null, and total_cents is what is charged: the rides estimate (no car, a flight) is never in it and is not stored.
    Raises BookingError when no lane is picked.
    """
    t = current_traveler(session)
    if not t:
        return None
    if quote.empty:
        raise BookingError(NOTHING_PICKED)
    rooms, add = (quote.stay.rooms_code, quote.stay.add_code) if quote.stay else ("", "")
    fare, bags = (quote.flight.fare_code, quote.flight.bags_code) if quote.flight else ("", "")
    trip = catalog.trip_query(quote.trip)  # "" for the sample trip
    bid = booking_id(t.id, quote.flight_id, quote.stay_id, quote.car_id, rooms, add, trip, fare, bags)
    existing = booking(session)
    if existing and existing["id"] == bid:
        return existing
    record = {"id": bid, "flight": quote.flight_id, "stay": quote.stay_id, "car": quote.car_id, "rooms": rooms, "add": add,
              "total_cents": quote.paid_cents, "booked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    for key, value in (("fare", fare), ("bags", bags), ("trip", trip)):
        if value:
            record[key] = value
    old = session.get("bookings")
    # Reassign the whole dict so the cookie session notices the change.
    session["bookings"] = {**(old or {}), t.id: record}
    if len(json.dumps(dict(session))) > BUDGET:  # same cookie budget as the calendar: refuse rather than overflow the cookie
        if old is None:
            session.pop("bookings", None)
        else:
            session["bookings"] = old
        raise BookingError("This demo can't hold another booking right now. Delete some calendar items to make room, then try again.")
    return record


class FriendError(ValueError):
    """An invite the demo refuses; the message is fit to show the traveler."""


@dataclass(frozen=True)
class Friend:
    name: str
    initials: str
    color: str  # a fill-* class from base.css


def _friend(name):
    words = name.split()
    initials = (words[0][0] + words[1][0] if len(words) > 1 else name[:2]).upper()
    color = "bubble" if name.casefold() == "mom" else _FRIEND_COLORS[int(hashlib.sha256(name.casefold().encode()).hexdigest(), 16) % len(_FRIEND_COLORS)]
    return Friend(name, initials, color)


def friends(session):
    """The signed-in traveler's invited friends, oldest first. Empty when signed out."""
    t = current_traveler(session)
    return [_friend(n) for n in (session.get("friends") or {}).get(t.id, [])] if t else []


def friend_named(session, name):
    return next((f for f in friends(session) if f.name.casefold() == (name or "").casefold()), None)


def add_friend(session, name):
    """Invite a friend by name for the current traveler. The same friend (any capitals) is never added twice.

    Returns the Friend. Raises FriendError for a bad name, too many friends or a full session cookie.
    """
    t = current_traveler(session)
    if not t:
        raise FriendError("Sign in to invite friends.")
    name = " ".join((name or "").split())
    if not name:
        raise FriendError("Type a name first.")
    if len(name) > MAX_FRIEND_NAME:
        raise FriendError(f"Keep the name to {MAX_FRIEND_NAME} characters.")
    if name.casefold() == "you":
        raise FriendError("That one is you. Pick another name.")
    if (found := friend_named(session, name)):
        return found
    mine = (session.get("friends") or {}).get(t.id, [])
    if len(mine) >= MAX_FRIENDS:
        raise FriendError(f"That is {MAX_FRIENDS} friends already. This demo keeps it small.")
    old = session.get("friends")
    # Reassign the whole dict so the cookie session notices the change.
    session["friends"] = {**(old or {}), t.id: [*mine, name]}
    if len(json.dumps(dict(session))) > BUDGET:
        if old is None:
            session.pop("friends", None)
        else:
            session["friends"] = old
        raise FriendError("This demo trip is full. Delete something to make room.")
    return _friend(name)


def invite_link(booking_id):
    """A fake, stable invite link for a booking."""
    return f"https://gitaway.example/join/{booking_id}"


_request_traveler = ContextVar("gitaway_traveler", default=None)
_request_path = ContextVar("gitaway_path", default="/")
_request_forks = ContextVar("gitaway_forks", default=0)


async def bind(req, session):
    """Beforeware: make the signed-in traveler visible to page rendering for this request.

    Async on purpose: a sync beforeware runs in a threadpool copy of the context, so the ContextVar set would be lost.
    """
    _request_traveler.set(current_traveler(session))
    from gitaway import forks  # here, not at the top: forks imports this module
    _request_forks.set(forks.count(session))
    _request_path.set(req.url.path + (f"?{req.url.query}" if req.url.query else ""))


def cache_secret() -> bytes:
    """The server's session secret, for keys that must not be guessable: GITAWAY_SECRET_KEY, else the .sesskey file
    (the same two places main.py takes FastHTML's session secret from)."""
    import os
    from pathlib import Path
    if (env := os.getenv("GITAWAY_SECRET_KEY")):
        return env.encode()
    try:
        return (Path(__file__).resolve().parent.parent / ".sesskey").read_bytes().strip() or b"gitaway"
    except OSError:
        return b"gitaway"


def as_signed_out():
    """Render the rest of this request as a signed-out visitor (for pages that are cached and shared, like /offline)."""
    _request_traveler.set(None)


def request_traveler():
    return _request_traveler.get()


def request_fork_count():
    """How many forks the current request's traveler has (0 when signed out), for panes that have no session at hand."""
    return _request_forks.get()


def signin_href(path=None):
    """The sign-in URL that comes back to `path` (default: the current request's page)."""
    path = _request_path.get() if path is None else path
    if not path or path == "/" or path.startswith("/signin"):
        return "/signin"
    return f"/signin?next={quote(path, safe='')}"
