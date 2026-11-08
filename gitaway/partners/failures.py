"""Klook links that could not be made (F-195): one count per day per reason in the community database, read by /admin.

The partner-links API is what turns a Klook page into a tracked link. When it fails, the click still lands on the plain Klook link (`travelpayouts.klook_link`), so nothing breaks
for the family but every such click loses its tracking: a wrong TRAVELPAYOUTS_TRS or a token that was revoked looks exactly like this. The reason is a short text with no secret in it.
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from gitaway import community


def record(reason: str) -> None:
    """Count one failure today for this reason."""
    now = datetime.now(timezone.utc)
    with community.connect() as db:
        db.conn.execute(text("INSERT INTO klook_failures (day, reason, n, last_at) VALUES (:d, :r, 1, :t) "
                             "ON CONFLICT(day, reason) DO UPDATE SET n = n + 1, last_at = :t"), {"d": now.date().isoformat(), "r": reason, "t": now.isoformat(timespec="microseconds")})
        db.conn.commit()


def recent(days: int = 7) -> tuple:
    """(how many failures in the last `days` days, the latest reason or "")."""
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with community.connect() as db:
        n = db.conn.execute(text("SELECT COALESCE(SUM(n), 0) FROM klook_failures WHERE day >= :s"), {"s": since}).scalar()
        last = db.conn.execute(text("SELECT reason FROM klook_failures WHERE day >= :s ORDER BY last_at DESC LIMIT 1"), {"s": since}).fetchone()
    return int(n), last[0] if last else ""
