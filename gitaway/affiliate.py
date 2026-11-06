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
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from sqlalchemy import text

from gitaway import community
from gitaway.community import HubError, _now, connect

COOKIE = "ga_via"
COOKIE_DAYS = 30
VIA_PER_WINDOW = 30      # counted /go clicks an hour from one person or address (F-182)
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


def log_click(handle, partner, lane, own_marker, who="") -> bool:
    """One row for a /go click that came from a creator's trip: which partner and lane, and whether the creator's own marker was on the link. `who` is the signed-in person ("u:<id>")
    or the caller's salted address hash: at most VIA_PER_WINDOW rows an hour per `who` (F-182), so one script cannot inflate a creator's count. True when it was counted."""
    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="microseconds")
    with connect() as db:
        if who and db.conn.execute(text("SELECT COUNT(*) FROM via_clicks WHERE who = :w AND clicked_at > :s"), {"w": who, "s": since}).scalar() >= VIA_PER_WINDOW:
            return False
        db.conn.execute(text("INSERT INTO via_clicks (handle, partner, lane, own_marker, clicked_at, who) VALUES (:h, :p, :l, :o, :t, :w)"),
                        {"h": handle, "p": partner, "l": lane, "o": int(bool(own_marker)), "t": _now(), "w": who})
        db.conn.commit()
        return True


def clicks_by_creator() -> dict:
    """{handle: (all clicks, clicks that carried the creator's own marker)}."""
    with connect() as db:
        return {r[0]: (r[1], r[2] or 0) for r in db.conn.execute(text("SELECT handle, COUNT(*), SUM(own_marker) FROM via_clicks GROUP BY handle")).fetchall()}


def valid_via(handle) -> str:
    """The handle when it is a real creator's, else "". What the `via` link parameter and the cookie are checked with."""
    return handle if _HANDLE.fullmatch(str(handle or "")) and community.creator(handle) else ""


# What is true about the money, in one place (F-194): the For creators page, the claim page, the outreach message, the settings page and the trip page all say it with these words.
# A creator's own links on a stop are a different thing (F-196); if they come back, say so here and every place follows.
STAYS = "Stays and things to do support GitAway for now."


def pays_you(has_marker=False) -> str:
    """What a creator is told about the money, in plain words: their marker rides on flights booked from their trips, nothing else."""
    lead = "Flights booked from your trips carry your Travelpayouts marker, so Aviasales pays you." if has_marker else "Add your Travelpayouts marker and flights booked from your trips carry it, so Aviasales pays you."
    return f"{lead} {STAYS}"


def earning_line(name, has_marker, plannable=True) -> str:
    """Who earns when someone books from a creator's trip, in plain words. A trip at a place GitAway cannot plan has no booking, so nobody earns from it (F-194)."""
    if not plannable:
        return "Nothing on this page can be booked, so nobody earns from it."
    if has_marker:
        return f"Flights booked from this trip support {name}. {STAYS}"
    return "Bookings from this trip support GitAway."


def seen_on_own_page(request, handle) -> bool:
    """Did this request come from the creator's own profile (/creators/<handle>) or one of their published trips (/trips/<slug>) on this site? By the Referer, which the browser
    sends on a same-site click. The `ga_via` cookie is only set then (F-182): a link anywhere else to /plan?via=<handle> must not decide who a stranger's bookings pay."""
    try:
        ref = urlsplit(request.headers.get("referer", ""))
    except ValueError:
        return False
    if ref.scheme not in ("http", "https") or ref.netloc != request.headers.get("host", "") or not ref.netloc:
        return False
    path = ref.path.rstrip("/")
    if path == f"/creators/{handle}":
        return True
    m = re.fullmatch(r"/trips/([a-z0-9-]{1,80})", path)
    row = community.get(m.group(1)) if m else None
    return bool(row and (row["meta"] or {}).get("handle") == handle)
