"""Creators keep their affiliate links (F-184, D-100 to D-103).

A creator may save their own Travelpayouts marker (digits only). A family that plans from the creator's published trip ("Plan this trip") gets a
30-day `ga_via` cookie holding the creator's handle and nothing else; the Book links of /plan then go to /go, which asks `marker_for(via)`:

- flights (Aviasales) carry `marker=<the creator's marker>.<SubID>`;
- stays and cars (Klook) carry GitAway's: the partner-links API is called with our token and project id, and whether it accepts another account's marker
  is not verified (no token to probe with), so a Klook click never claims to pay the creator.

No marker, or no cookie: GitAway's marker, as before. Every click that came from a creator's trip is one row in `via_clicks`, so the admin page can count them.
The page of a published trip says who earns what (`earning_line`), in the same words the For creators page uses.
"""

import re

from sqlalchemy import text

from gitaway import community
from gitaway.community import HubError, _now, connect

COOKIE = "ga_via"
COOKIE_DAYS = 30
_MARKER = re.compile(r"[0-9]{3,10}")
_HANDLE = re.compile(r"[a-z0-9-]{1,40}")
BAD_MARKER = "A marker is digits only, 3 to 10 of them, like 801445. Find yours in Travelpayouts under Profile."


def clean_marker(value) -> str:
    """The marker as saved: "" (none) or 3 to 10 ASCII digits. Raises HubError for anything else (spaces at the ends are forgiven)."""
    v = str(value or "").strip()
    if v and not _MARKER.fullmatch(v):
        raise HubError(BAD_MARKER)
    return v


def set_marker(owner_user, value) -> str:
    """Save (or, with "", forget) a person's marker. Returns what is saved."""
    v = clean_marker(value)
    with connect() as db:
        if v:
            db.conn.execute(text("INSERT INTO creator_markers (owner_user, marker, updated_at) VALUES (:o, :m, :t) "
                                 "ON CONFLICT(owner_user) DO UPDATE SET marker = :m, updated_at = :t"), {"o": str(owner_user), "m": v, "t": _now()})
        else:
            db.conn.execute(text("DELETE FROM creator_markers WHERE owner_user = :o"), {"o": str(owner_user)})
        db.conn.commit()
    return v


def marker_of(owner_user) -> str:
    with connect() as db:
        r = db.conn.execute(text("SELECT marker FROM creator_markers WHERE owner_user = :o"), {"o": str(owner_user)}).fetchone()
    return r[0] if r else ""


def marker_for(handle) -> str:
    """The marker of the creator with this handle, or "" (an unknown handle, a creator without one, anything that is not a handle)."""
    if not _HANDLE.fullmatch(str(handle or "")):
        return ""
    with connect() as db:
        r = db.conn.execute(text("SELECT m.marker FROM creators c JOIN creator_markers m ON m.owner_user = c.owner_user WHERE c.handle = :h"), {"h": handle}).fetchone()
    return r[0] if r else ""


def log_click(handle, partner, lane, own_marker) -> None:
    """One row for a /go click that came from a creator's trip: which partner and lane, and whether the creator's own marker was on the link."""
    with connect() as db:
        db.conn.execute(text("INSERT INTO via_clicks (handle, partner, lane, own_marker, clicked_at) VALUES (:h, :p, :l, :o, :t)"),
                        {"h": handle, "p": partner, "l": lane, "o": int(bool(own_marker)), "t": _now()})
        db.conn.commit()


def clicks_by_creator() -> dict:
    """{handle: (all clicks, clicks that carried the creator's own marker)}."""
    with connect() as db:
        return {r[0]: (r[1], r[2] or 0) for r in db.conn.execute(text("SELECT handle, COUNT(*), SUM(own_marker) FROM via_clicks GROUP BY handle")).fetchall()}


def valid_via(handle) -> str:
    """The handle when it is a real creator's, else "". What the `via` link parameter and the cookie are checked with."""
    return handle if _HANDLE.fullmatch(str(handle or "")) and community.creator(handle) else ""


def earning_line(name, has_marker) -> str:
    """Who earns when someone books from a creator's trip, in plain words."""
    if has_marker:
        return f"Flights booked from this trip support {name}. Stays and things to do support GitAway."
    return "Bookings from this trip support GitAway."
