"""A creator's stats (F-192, D-129): how many people read their trips, forked them, tapped "Plan this trip", and where the partner clicks went.

Readers are counted without a cookie and without keeping anything about a person. A view of a live published trip is one upsert into `trip_days` (slug, day, views, forks, plans):
a plain count per trip per day. To count a reader once a day, `view_seen` holds a short hash of (today's random salt, address, browser) for the current day only: the salt lives in
memory and is dropped at midnight (and on every restart), the hash cannot be turned back into an address, and the table is emptied of every other day on the first view of each day.
No address and no user-agent text is ever written. Known bots, empty user-agents and the creator's own visits are not counted.

Partner clicks come from `via_clicks` (gitaway.affiliate), which records the creator's handle, not a trip, so they are shown for the creator as a whole.
"""

import hashlib
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from sqlalchemy import text

from gitaway import community, reports

WINDOWS = ("7", "30", "all")
DAYS = {"7": 7, "30": 30}
SPARK_DAYS = 30
# Crawlers, link-preview fetchers, scripts and monitors: anything that says so in its user-agent. An empty one is a script too.
BOT = re.compile(r"bot|crawl|spider|slurp|scrape|fetch|preview|headless|lighthouse|monitor|uptime|curl|wget|httpie|python|java/|go-http|okhttp|libwww|axios|node-|whatsapp|telegram|"
                 r"discord|slack|skype|facebookexternalhit|twitter|linkedin|pinterest|embedly|quora|vkshare|yahoo|baidu|yandex|duckduck|ahrefs|semrush|mj12|petal|bytespider|gptbot|claude|anthropic|"
                 r"perplexity|ccbot|apple-?news|google-?(read|inspection|site)|mediapartners|adsbot|feedly", re.I)

_salt = {"day": "", "bytes": b""}
_purged = {"day": ""}


def _today() -> date:
    return datetime.now(timezone.utc).date()


def reset() -> None:
    """Forget today's salt and the purge mark (a restart does this; tests call it)."""
    _salt.update(day="", bytes=b"")
    _purged["day"] = ""


def _salt_of(day: str) -> bytes:
    if _salt["day"] != day:
        _salt.update(day=day, bytes=secrets.token_bytes(16))   # yesterday's salt is gone for good, so yesterday's hashes can never be matched to a new visit
    return _salt["bytes"]


def is_bot(user_agent) -> bool:
    ua = str(user_agent or "").strip()
    return not ua or bool(BOT.search(ua))


def _reader(request, day: str) -> str:
    """A short code for this reader today: a hash of today's salt, their address and browser. Not stored with either."""
    ip = reports.client_ip(request)
    return hashlib.sha256(_salt_of(day) + f"{ip}|{request.headers.get('user-agent', '')}".encode()).hexdigest()[:20]


def _once(db, request, slug: str, kind: str, day: str) -> bool:
    """Is this the first time today this reader did `kind` on `slug`? Notes it as seen (and drops every other day's notes first)."""
    if _purged["day"] != day:
        db.conn.execute(text("DELETE FROM view_seen WHERE day != :d"), {"d": day})
        _purged["day"] = day
    return db.conn.execute(text("INSERT OR IGNORE INTO view_seen (day, h, slug, kind) VALUES (:d, :h, :s, :k)"), {"d": day, "h": _reader(request, day), "s": slug, "k": kind}).rowcount == 1


def _count(request, session, slug, kind: str, column: str) -> bool:
    if is_bot(request.headers.get("user-agent")):
        return False
    row = community.get(slug)
    if not row or row["kind"] != "scrapbook" or str((session or {}).get("user_id") or "\0") == row["owner_user"]:
        return False
    day = _today().isoformat()
    with community.connect() as db:
        if not _once(db, request, slug, kind, day):
            db.conn.commit()
            return False
        db.conn.execute(text(f"INSERT INTO trip_days (slug, day, {column}) VALUES (:s, :d, 1) ON CONFLICT(slug, day) DO UPDATE SET {column} = {column} + 1"), {"s": slug, "d": day})
        db.conn.commit()
    return True


def count_view(request, session, slug) -> bool:
    """A reader opened the published trip `slug`. True when it was counted."""
    return _count(request, session, slug, "view", "views")


def count_plan(request, session, handle) -> bool:
    """A reader tapped "Plan this trip" on one of `handle`'s trips (the Referer names the trip). True when it was counted; a tap from the profile names no trip and is not."""
    try:
        path = urlsplit(request.headers.get("referer", "")).path.rstrip("/")
    except ValueError:
        return False
    m = re.fullmatch(r"/trips/([a-z0-9-]{1,80})", path)
    row = community.get(m.group(1)) if m else None
    if not row or (row["meta"] or {}).get("handle") != handle:
        return False
    return _count(request, session, row["slug"], "plan", "plans")


# ---- reading them ---------------------------------------------------------------------------------------------------------

def _since(window: str):
    return (_today() - timedelta(days=DAYS[window] - 1)).isoformat() if window in DAYS else ""


def _sums(conn, slugs, window):
    if not slugs:
        return {"views": 0, "forks": 0, "plans": 0}
    marks = ", ".join(f":s{i}" for i in range(len(slugs)))
    args = {f"s{i}": s for i, s in enumerate(slugs)} | {"d": _since(window)}
    r = conn.execute(text(f"SELECT COALESCE(SUM(views), 0), COALESCE(SUM(forks), 0), COALESCE(SUM(plans), 0) FROM trip_days WHERE slug IN ({marks}) AND day >= :d"), args).fetchone()
    return {"views": r[0], "forks": r[1], "plans": r[2]}


def _group(conn, slugs) -> dict:
    out = {w: _sums(conn, slugs, w) for w in WINDOWS}
    if slugs:   # all-time forks also count the ones made before the daily numbers existed
        marks = ", ".join(f":s{i}" for i in range(len(slugs)))
        out["all"]["forks"] = max(out["all"]["forks"], conn.execute(text(f"SELECT COALESCE(SUM(n), 0) FROM fork_counts WHERE slug IN ({marks})"), {f"s{i}": s for i, s in enumerate(slugs)}).scalar())
    return out


def _spark(conn, slug) -> list:
    first = _today() - timedelta(days=SPARK_DAYS - 1)
    got = {r[0]: r[1] for r in conn.execute(text("SELECT day, views FROM trip_days WHERE slug = :s AND day >= :d"), {"s": slug, "d": first.isoformat()})}
    return [got.get((first + timedelta(days=i)).isoformat(), 0) for i in range(SPARK_DAYS)]


def clicks(handle) -> dict:
    """Partner clicks from the creator's trips: {"7": n, "30": n, "all": n, "own": n clicks that carried their marker, "gitaway": n that went through ours}, each window's own and GitAway's too."""
    out = {}
    with community.connect() as db:
        for w in WINDOWS:
            since = _since(w)
            r = db.conn.execute(text("SELECT COUNT(*), COALESCE(SUM(own_marker), 0) FROM via_clicks WHERE handle = :h AND clicked_at >= :t"), {"h": handle, "t": since}).fetchone()
            out[w], out[f"own_{w}"] = r[0], r[1]
    out["own"], out["gitaway"] = out["own_all"], out["all"] - out["own_all"]
    return out


def report(owner) -> dict:
    """{"trips": [{slug, title, 7, 30, all (each {views, forks, plans}), spark}], "total": {7, 30, all}, "clicks": clicks(handle) or None} for the person's live trips."""
    creator = community.creator_of(owner)
    trips = community.rows(kind="scrapbook", owner=owner, pending=True)      # their own, the waiting ones too (F-194)
    with community.connect() as db:
        per = [{"slug": t["slug"], "title": t["title"], **_group(db.conn, [t["slug"]]), "spark": _spark(db.conn, t["slug"])} for t in trips]
        total = _group(db.conn, [t["slug"] for t in trips])
    return {"trips": per, "total": total, "clicks": clicks(creator["handle"]) if creator else None}


def readers_all_time(slugs) -> int:
    """How many readers these trips have had in all (the admin page's number per creator)."""
    with community.connect() as db:
        return _sums(db.conn, list(slugs), "all")["views"]
