"""Share the trip (F-234): the card the family posts to Instagram and the public page it links back to.

    snapshot(session, names=False, exact=False) -> dict    what the card and the page may say about the open trip, read once
    save(session, names, exact) -> Share                   keep that snapshot under one long random token per trip (the same link every time) and return it
    find(token) -> Share | None                            a share that is on; None for an unknown token or one turned off
    off(session) -> bool                                   turn the open trip's share off: its card and page answer 404 from then on
    Share.card() / Share.link()                            the picture's contents (sharecard.Card) and the address the card points at

Privacy (D-491..D-494): a snapshot is made of the trip's title, its place, where from and to, its month and length, and (only when the family chose) the exact
dates and the first names of the family's members (the people with an account, never the trip's traveller list, which can hold children). It is read from
fields chosen here; no booking, confirmation number, hotel, price, address, email or note is ever read, so none can reach the card or the page.
The link back is the published trip's page when the family has published it (/trips/<slug>), else the share-only page /s/<token>, which says the same as the card
minus the names and the exact dates. A share lives in the community database (the page is public), in its own table made on first use.
"""

import json
import re
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text

from gitaway import blogbutton, community, members, placeart, publish, session as ses, sharecard, tripcal as cal

_TABLE = """CREATE TABLE IF NOT EXISTS trip_shares (
    token TEXT PRIMARY KEY, family TEXT NOT NULL, trip TEXT NOT NULL, title TEXT NOT NULL, place TEXT NOT NULL, art TEXT NOT NULL DEFAULT '', route TEXT NOT NULL DEFAULT '[]',
    month TEXT NOT NULL DEFAULT '', exact TEXT NOT NULL DEFAULT '', days INTEGER NOT NULL DEFAULT 0, names TEXT NOT NULL DEFAULT '', slug TEXT NOT NULL DEFAULT '',
    on_ INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE (family, trip))"""
_made: set = set()
_CODE = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class Share:
    token: str
    title: str
    place: str
    art: str
    route: tuple
    month: str
    exact: str
    days: int
    names: str
    slug: str

    def link(self) -> str:
        """The page the card points at: the published trip when it is still up, else the share-only page. Absolute, on the site's public address."""
        base = blogbutton.base_url()
        if self.slug and community.get(self.slug):
            return f"{base}/trips/{self.slug}"
        return f"{base}/s/{self.token}"

    def card(self) -> sharecard.Card:
        when = self.exact or self.month
        return sharecard.Card(self.title, self.place, self.route, when, self.days, self.names, self.link().split("://", 1)[-1], self.art)


def art_for(*names) -> str:
    """placeart's key for the first of `names` that has art ("South Lake Tahoe" is "laketahoe"), else ""."""
    for name in names:
        key = placeart._slug(name)
        if key in placeart.SLUGS:
            return key
        for slug in placeart.SLUGS:
            if slug in key:
                return slug
    return ""


def _month(a, b) -> str:
    if (a.year, a.month) == (b.year, b.month):
        return a.strftime("%B %Y")
    return f"{a.strftime('%b %Y')} – {b.strftime('%b %Y')}"


def first_names(session) -> str:
    """"Ari and Maya": the first names of the family's members (people with an account), at most four."""
    tid = (session or {}).get("tenant_id")
    out = [m["name"].split()[0] for m in members.members(tid) if m["name"].split()] if tid else []
    return publish.join_names(out[:4])


def trip_id(session) -> str:
    with ses.family(session) as fam:
        return (fam.trip_id if fam else "") or ""


def snapshot(session, names=False, exact=False) -> dict:
    b = ses.booking(session)
    t = cal.trip("", b)
    days = cal.days(t)
    origin = t.origin if _CODE.match(str(t.origin or "")) else t.origin_name
    route = tuple(x for x in (origin, t.destination_name) if x)
    live = publish.live(session)
    return {"title": " ".join(str(t.title or "Our trip").split())[:80], "place": t.destination_name, "art": art_for(t.destination_name, t.title),
            "route": route if len(route) == 2 and route[0] != route[1] else (), "month": _month(days[0], days[-1]),
            "exact": f"{cal.range_label(days[0], days[-1])}, {days[-1].year}" if exact else "", "days": len(days), "names": first_names(session) if names else "",
            "slug": live["slug"] if live else ""}


@contextmanager
def _db():
    """The community database with this module's table made (once for each database file)."""
    with community.connect() as c:
        if community._url() not in _made:
            c.conn.execute(text(_TABLE))
            c.conn.commit()
            _made.add(community._url())
        yield c.conn


def _share(r) -> Share:
    return Share(r["token"], r["title"], r["place"], r["art"], tuple(json.loads(r["route"])), r["month"], r["exact"], r["days"], r["names"], r["slug"])


def save(session, names=False, exact=False) -> Share:
    snap = snapshot(session, names, exact)
    family, trip = session.get("tenant_id") or "", trip_id(session)
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    with _db() as conn:
        conn.execute(text("""INSERT INTO trip_shares (token, family, trip, title, place, art, route, month, exact, days, names, slug, on_, created_at, updated_at)
                             VALUES (:token, :f, :t, :title, :place, :art, :route, :month, :exact, :days, :names, :slug, 1, :now, :now)
                             ON CONFLICT (family, trip) DO UPDATE SET title = :title, place = :place, art = :art, route = :route, month = :month, exact = :exact,
                             days = :days, names = :names, slug = :slug, on_ = 1, updated_at = :now"""),
                     {**snap, "route": json.dumps(snap["route"]), "token": secrets.token_urlsafe(12), "f": family, "t": trip, "now": now})
        token = conn.execute(text("SELECT token FROM trip_shares WHERE family = :f AND trip = :t"), {"f": family, "t": trip}).scalar()      # the row's own token: two opens at once make one
        conn.commit()
    return Share(token, snap["title"], snap["place"], snap["art"], snap["route"], snap["month"], snap["exact"], snap["days"], snap["names"], snap["slug"])


def find_open(session) -> Share | None:
    """The open trip's share while it is on (the sheet keeps the choices the family made last time), else None."""
    with _db() as conn:
        r = conn.execute(text("SELECT * FROM trip_shares WHERE family = :f AND trip = :t AND on_ = 1"), {"f": session.get("tenant_id") or "", "t": trip_id(session)}).mappings().first()
    return _share(r) if r else None


def find(token) -> Share | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,40}", str(token or "")):
        return None
    with _db() as conn:
        r = conn.execute(text("SELECT * FROM trip_shares WHERE token = :t AND on_ = 1"), {"t": token}).mappings().first()
    return _share(r) if r else None


def off(session) -> bool:
    with _db() as conn:
        n = conn.execute(text("UPDATE trip_shares SET on_ = 0 WHERE family = :f AND trip = :t AND on_ = 1"),
                           {"f": session.get("tenant_id") or "", "t": trip_id(session)}).rowcount
        conn.commit()
    return bool(n)
