"""The signed-in person and the cookie-held trip state. Public helpers for every screen.

Sign-in is fh-saas's (see gitaway.auth): the session holds `user_id` and `email`, and `current_traveler` is the thin
adapter that maps that person to the "traveler" every screen speaks of (id = the fh-saas user id, name from the email).
The family's trips, bookings, friends and remembered picks live in the family's SQLite database (F-040, gitaway.familydb):
the functions below take the session only to learn who is signed in and which family that is. Forks, saves, the hub and the
creator draft are still cookie state until F-041.

Session shape: {"user_id": "<fh-saas user id>", "email": "<email>", "tenant_id": "<family>", ..., "forks": {"<id>": ["<trip slug>", ...]}}.

For the header, `bind` is a beforeware (see main.py) that records the current traveler in a ContextVar for the
request; layout.site_header reads it with `request_traveler()`. Outside a request it is None (signed out).
"""

import hashlib
import json
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date
from urllib.parse import quote, unquote, urlsplit

from fh_saas.utils_sql import insert_only

from gitaway import catalog, familydb


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
INTENTS = ("save", "pay", "invite", "fork", "publish", "ride")

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


# ---- the family's trips, bookings, friends and remembered picks (SQLite: see gitaway.familydb) ---------------------

@dataclass
class Family:
    """One person's open view of their family database. Get it with `family(session)`; it closes when the block ends."""
    db: object
    traveler: Traveler
    member: dict
    trip_id: str | None  # the trip this person has open: the one they chose, else the family's newest

    def booking(self):
        return familydb.booking_for_trip(self.db, self.trip_id)


@contextmanager
def family(session):
    """`with family(session) as fam:` the signed-in person's family, or None when signed out or not a member of one."""
    t = current_traveler(session)
    with familydb.using(session) as db:
        if t is None or db is None:
            yield None
            return
        member = familydb.ensure_member(db, t.id, session.get("email") or "", t.name)
        yield Family(db, t, member, familydb.current_trip_id(db, member))


def booking(session):
    """The booking of the trip the signed-in person has open (a dict), or None when signed out or nothing is booked."""
    with family(session) as fam:
        return fam.booking() if fam else None


@dataclass(frozen=True)
class TripInfo:
    id: str
    title: str
    dates: str      # "Oct 16 – 20"
    source: str     # "demo" or "imported"
    current: bool


def trips(session) -> list:
    """The family's trips, newest first, with the one this person has open marked `current`. Empty when signed out."""
    from gitaway import tripcal  # here, not at the top: tripcal imports this module
    with family(session) as fam:
        if not fam:
            return []
        return [TripInfo(r["id"], r["title"], tripcal.range_label(date.fromisoformat(r["depart"]), date.fromisoformat(r["return_on"])),
                         r["source"], r["id"] == fam.trip_id) for r in familydb.trips(fam.db)]


def switch_trip(session, trip_id) -> bool:
    """Open another of the family's trips for this person. False when signed out or the family has no such trip."""
    with family(session) as fam:
        if not fam or not familydb.trip(fam.db, trip_id):
            return False
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "UPDATE members SET trip_id = :t WHERE id = :u", t=trip_id, u=fam.traveler.id)
        return True


MAX_PLAN_QUERY = 400


def remembered_plan(session):
    """The workspace picks (a /plan query string) the signed-in traveler last looked at, or None."""
    with family(session) as fam:
        return (fam.member.get("plan") or None) if fam else None


def remember_plan(session, query):
    """Remember the picks `query` (e.g. "f=f2&h=h3&c=c1&d=..") for the signed-in traveler. Only writes when it changed."""
    with family(session) as fam:
        if not fam or len(query or "") > MAX_PLAN_QUERY or (fam.member.get("plan") or "") == query:
            return
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "UPDATE members SET plan = :q WHERE id = :u", q=query, u=fam.traveler.id)


def booking_id(traveler_id, flight, stay, car, rooms="", add="", trip="", fare="", bags=""):
    """A stable id for one traveler's picks, so paying the same trip twice is the same booking. Default rooms, no add-ons, the sample trip and a Basic fare with no bags hash as before."""
    digest = hashlib.sha256(f"{traveler_id}|{flight}|{stay}|{car}{'|' + rooms + '|' + add if rooms or add else ''}{'|' + trip if trip else ''}{'|F' + fare + '|' + bags if fare or bags else ''}".encode()).hexdigest()
    return "GA-" + digest[:8].upper()


class BookingError(ValueError):
    """A booking the demo refuses; the message is fit to show the traveler."""


NOTHING_PICKED = "Pick at least one thing to book: a flight, a stay or a car."


def book(session, quote):
    """Record `quote` (a catalog.Quote) as a new trip of the signed-in traveler's family, and open it. Idempotent.

    Returns the booking, or None when signed out. Raises BookingError when no lane is picked or the family has too many trips.
    Paying the same picks again opens the trip they made and changes nothing else. Different picks make another trip: a family
    can have several. The booking is a dict {"id", "flight", "stay", "car", "rooms", "add", "total_cents", "booked_at"; "fare", "bags"
    and "trip" only when set} (rooms and add are the stay's compact pick codes, "" for the default room and no add-ons; fare and
    bags are the flight's, "" for Basic and no bags). A skipped lane is None, and total_cents is what is charged: the rides
    estimate (no car, a flight) is never in it and is not stored.
    """
    t = current_traveler(session)
    if not t:
        return None
    if quote.empty:
        raise BookingError(NOTHING_PICKED)
    rooms, add = (quote.stay.rooms_code, quote.stay.add_code) if quote.stay else ("", "")
    fare, bags = (quote.flight.fare_code, quote.flight.bags_code) if quote.flight else ("", "")
    params = catalog.trip_query(quote.trip)  # "" for the sample trip
    bid = booking_id(t.id, quote.flight_id, quote.stay_id, quote.car_id, rooms, add, params, fare, bags)
    with family(session) as fam:
        if not fam:
            return None
        db = fam.db
        with familydb.transaction(db):
            familydb.lock(db)  # from here to the commit nobody else writes: the lookup and the insert cannot interleave
            found = familydb.row(db, "SELECT trip_id FROM bookings WHERE id = :id", id=bid)
            if found:
                trip_id = found["trip_id"]
            else:
                if familydb.row(db, "SELECT COUNT(*) AS n FROM trips")["n"] >= familydb.MAX_TRIPS:
                    raise BookingError(f"That is {familydb.MAX_TRIPS} trips already. This demo keeps it small.")
                trip_id, at = uuid.uuid4().hex[:12], familydb.now()
                insert_only(db, "trips", {"id": trip_id, "title": quote.trip.title, "source": "demo", "params": params,
                                          "depart": quote.trip.depart.isoformat(), "return_on": quote.trip.return_.isoformat(),
                                          "created_by": t.id, "created_at": at}, ["id"], auto_commit=False)
                insert_only(db, "bookings", {"id": bid, "trip_id": trip_id, "flight": quote.flight_id, "stay": quote.stay_id, "car": quote.car_id,
                                             "rooms": rooms, "add_ons": add, "fare": fare, "bags": bags, "total_cents": quote.paid_cents,
                                             "booked_by": t.id, "booked_at": at}, ["id"], auto_commit=False)
            familydb.run(db, "UPDATE members SET trip_id = :t WHERE id = :u", t=trip_id, u=t.id)
        return familydb.booking_for_trip(db, trip_id)


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
    """The friends invited to the trip this person has open, oldest first. Empty when signed out or nothing is booked."""
    with family(session) as fam:
        if not fam or not fam.trip_id:
            return []
        return [_friend(r["name"]) for r in familydb.rows(fam.db, "SELECT name FROM friends WHERE trip_id = :t ORDER BY rowid", t=fam.trip_id)]


def friend_named(session, name):
    return next((f for f in friends(session) if f.name.casefold() == (name or "").casefold()), None)


def add_friend(session, name):
    """Invite a friend by name to the open trip. The same friend (any capitals) is never added twice.

    Returns the Friend. Raises FriendError for a bad name or too many friends.
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
    with family(session) as fam:
        if not fam or not fam.trip_id:
            raise FriendError("Book a trip first, then invite friends.")
        db = fam.db
        with familydb.transaction(db):
            familydb.lock(db)
            mine = [r["name"] for r in familydb.rows(db, "SELECT name FROM friends WHERE trip_id = :t ORDER BY rowid", t=fam.trip_id)]
            if (found := next((n for n in mine if n.casefold() == name.casefold()), None)):
                return _friend(found)
            if len(mine) >= MAX_FRIENDS:
                raise FriendError(f"That is {MAX_FRIENDS} friends already. This demo keeps it small.")
            insert_only(db, "friends", {"pk": f"{fam.trip_id}~{name.casefold()}", "trip_id": fam.trip_id, "name": name, "created_at": familydb.now()},
                        ["pk"], auto_commit=False)
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
