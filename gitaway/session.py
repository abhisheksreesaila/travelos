"""Demo sign-in state, kept in the FastHTML (signed cookie) session. Public helpers for every screen.

Session shape: {"traveler": "<id>", "forks": {"<id>": ["<trip slug>", ...]}}.
Pure functions over a session dict, so tests and later tickets (F-018 pay, F-021 forks list) can use them directly.

For the header, `bind` is a beforeware (see main.py) that records the current traveler in a ContextVar for the
request; layout.site_header reads it with `request_traveler()`. Outside a request it is None (signed out).
"""

import re
from contextvars import ContextVar
from dataclasses import dataclass
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
