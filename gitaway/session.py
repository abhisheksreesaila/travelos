"""Demo sign-in state, kept in the FastHTML (signed cookie) session. Public helpers for every screen.

Session shape: {"traveler": "<id>", "forks": {"<id>": ["<trip slug>", ...]}, "friends": {"<id>": ["<name>", ...]}}.
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


@dataclass(frozen=True)
class Traveler:
    id: str
    name: str
    initials: str
    blurb: str
    color: str  # a fill-* class from base.css


TRAVELERS = {
    "ari": Traveler("ari", "Ari Rivera", "AR", "Demo traveler · family of four", "grape"),
    "sam": Traveler("sam", "Sam Kim", "SK", "Demo traveler · couple trip", "mint"),
}
BUDGET = 2600  # bytes of session JSON; base64 adds a third plus a signature, keeping the whole cookie near 3.4 KB (limit 3.6 KB, browsers drop >4 KB)
MAX_FRIENDS = 6
MAX_FRIEND_NAME = 20
DEMO_FRIENDS = ("Mom", "Sam")
_FRIEND_COLORS = ("sun", "sky", "grape", "mint", "bubble")
INTENTS = ("save", "pay", "invite", "fork")

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


def current_traveler(session):
    return TRAVELERS.get((session or {}).get("traveler"))


def sign_in(session, traveler_id):
    """Store the demo traveler; returns it, or None for an unknown id (session untouched)."""
    if traveler_id not in TRAVELERS:
        return None
    session["traveler"] = traveler_id
    return TRAVELERS[traveler_id]


def sign_out(session):
    session.pop("traveler", None)


def forks(session):
    """Trip slugs the signed-in traveler has forked, oldest first. Empty when signed out."""
    t = current_traveler(session)
    return list(session.get("forks", {}).get(t.id, [])) if t else []


def trip_slug(path):
    m = re.fullmatch(r"/trips/([A-Za-z0-9][A-Za-z0-9_-]*)/?", urlsplit(path or "").path)
    return m.group(1) if m else None


def add_fork(session, next_path):
    """Add the trip in a /trips/<slug> path to the current traveler's forks.

    False when signed out, when the path is not a trip, or when it is already there.
    """
    t, slug = current_traveler(session), trip_slug(next_path)
    if not t or not slug:
        return False
    mine = forks(session)
    if slug in mine:
        return False
    # Reassign the whole dict so the cookie session notices the change.
    session["forks"] = {**session.get("forks", {}), t.id: [*mine, slug]}
    return True


def booking(session):
    """The signed-in traveler's booked trip (a dict), or None when signed out or nothing is booked."""
    t = current_traveler(session)
    return (session.get("bookings") or {}).get(t.id) if t else None


def booking_id(traveler_id, flight, stay, car):
    """A stable id for one traveler's picks, so paying the same trip twice is the same booking."""
    digest = hashlib.sha256(f"{traveler_id}|{flight}|{stay}|{car}".encode()).hexdigest()
    return "GA-" + digest[:8].upper()


def book(session, quote):
    """Record `quote` (a catalog.Quote) as the current traveler's booked trip. Idempotent.

    Returns the booking, or None when signed out. Paying the same picks again keeps the original booking untouched.
    Session shape: "bookings": {"<traveler id>": {"id", "flight", "stay", "car", "total_cents", "booked_at"}}.
    """
    t = current_traveler(session)
    if not t:
        return None
    bid = booking_id(t.id, quote.flight_id, quote.stay_id, quote.car_id)
    existing = booking(session)
    if existing and existing["id"] == bid:
        return existing
    record = {"id": bid, "flight": quote.flight_id, "stay": quote.stay_id, "car": quote.car_id,
              "total_cents": quote.total_cents, "booked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    # Reassign the whole dict so the cookie session notices the change.
    session["bookings"] = {**session.get("bookings", {}), t.id: record}
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


async def bind(req, session):
    """Beforeware: make the signed-in traveler visible to page rendering for this request.

    Async on purpose: a sync beforeware runs in a threadpool copy of the context, so the ContextVar set would be lost.
    """
    _request_traveler.set(current_traveler(session))
    _request_path.set(req.url.path + (f"?{req.url.query}" if req.url.query else ""))


def request_traveler():
    return _request_traveler.get()


def signin_href(path=None):
    """The sign-in URL that comes back to `path` (default: the current request's page)."""
    path = _request_path.get() if path is None else path
    if not path or path == "/" or path.startswith("/signin"):
        return "/signin"
    return f"/signin?next={quote(path, safe='')}"
