"""Report a public trip or creator page (F-185, D-104 to D-106).

Anyone, signed in or not, may report a live trip or a creator who has one: a reason from a short list, an optional note and an optional email address for a reply.
A report hides nothing; it reaches the captain's admin page (gitaway/pages/admin.py), where one click takes the trip down. It also tells the captain it is there (F-196): one WARNING line in the
server log, a "N new" count in the captain's account menu and header and on /admin until the captain presses "Mark all as read", and an email through fh-saas to every admin when SMTP is set (`notify`).

Limits: 5 reports an hour from one network address (kept only as a salted hash) or one signed-in person, and 60 an hour in all from signed-out callers (a signed-in person is never held up by it, so a flood from many addresses cannot silence real reporters; reaching it logs a warning), counted from the reports table itself, so
a restart or a second worker does not reset them. A filled-in honeypot field is dropped without a trace in the answer (the page says "thanks" like any other).
"""

import hashlib
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import text

from gitaway import auth, community, session as ses
from gitaway.community import _now, connect

REASONS = {"copyright": "It uses someone else's words or photos", "misleading": "It is wrong or misleading", "private": "It shows private information",
           "offensive": "It is unsafe or offensive", "spam": "It is spam or an advertisement", "other": "Something else"}
log = logging.getLogger("gitaway.reports")
PER_WINDOW, ALL_PER_WINDOW, WINDOW = 5, 60, timedelta(hours=1)
NOTE_MAX = 500
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class ReportError(ValueError):
    """A report GitAway refuses; the message is fit to show. `status` is the HTTP status it answers with."""

    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def ip_hash(ip) -> str:
    """A salted one-way hash of the address (the cookie secret is the salt), enough to count reports from one place; the address itself is never stored."""
    return hashlib.sha256(ses.cache_secret() + str(ip or "").encode()).hexdigest()[:16]


def client_ip(request) -> str:
    """The caller's address: the last X-Forwarded-For entry (what Railway's proxy appended; earlier ones are the caller's to forge), else the socket's."""
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[-1].strip() if forwarded.strip() else (request.client.host if request.client else "")


def same_site(request) -> bool:
    """Did this POST come from one of our own pages? The session cookie is SameSite=Lax already; this also refuses a cross-site form that carries no cookie (a
    report) by the Origin header, and Sec-Fetch-Site where a browser sends it. Used by every form of F-185 (the report and the admin's two buttons)."""
    origin = request.headers.get("origin")
    if origin is not None and urlsplit(origin).netloc != request.headers.get("host", ""):
        return False
    return request.headers.get("sec-fetch-site", "same-origin") in ("same-origin", "none")


def target_exists(kind, target) -> bool:
    if kind == "trip":
        return community.is_real(target)
    return kind == "creator" and any(c["handle"] == target for c in community.real_creators())


def _recent(conn, column, value) -> int:
    since = (datetime.now(timezone.utc) - WINDOW).isoformat(timespec="microseconds")
    return conn.execute(text(f"SELECT COUNT(*) FROM reports WHERE {column} = :v AND created_at > :s"), {"v": value, "s": since}).scalar()


def add(kind, target, reason, note="", email="", reporter="", ip="") -> None:
    """Store one report. Raises ReportError (422 for a bad one, 429 over a limit)."""
    if reason not in REASONS:
        raise ReportError("Pick the reason that fits best.")
    if not target_exists(kind, target):
        raise ReportError("That page is not on GitAway any more.", 404)
    note = " ".join(_CONTROL.sub(" ", str(note or "")).split())[:NOTE_MAX]
    email = str(email or "").strip()
    if email and not auth.clean_email(email):
        raise ReportError("That email address does not look right. Leave it empty if you would rather not be answered.")
    who, where = str(reporter or ""), ip_hash(ip)
    with connect() as db:
        since = (datetime.now(timezone.utc) - WINDOW).isoformat(timespec="microseconds")
        if _recent(db.conn, "ip_hash", where) >= PER_WINDOW or (who and _recent(db.conn, "reporter", who) >= PER_WINDOW):
            raise ReportError("That is a lot of reports in an hour. Please try again later.", 429)
        if not who and db.conn.execute(text("SELECT COUNT(*) FROM reports WHERE reporter = '' AND created_at > :s"), {"s": since}).scalar() >= ALL_PER_WINDOW:
            log.warning("signed-out report ceiling reached (%s an hour): signed-out reports are refused until it passes", ALL_PER_WINDOW)
            raise ReportError("That is a lot of reports in an hour. Please try again later.", 429)
        db.conn.execute(text("INSERT INTO reports (kind, target, reason, note, email, reporter, ip_hash, created_at) VALUES (:k, :t, :r, :n, :e, :p, :i, :c)"),
                        {"k": kind, "t": target, "r": reason, "n": note, "e": auth.clean_email(email) or "", "p": who, "i": where, "c": _now()})
        db.conn.commit()
    notify(kind, target, reason)


# ---- telling the captain (F-196) ---------------------------------------------------------------------------------------------------

EMAIL_TEMPLATE = Path(__file__).parent / "emails" / "report.md"


def _run(fn, *args):
    """Run `fn` on its own thread: SMTP can be slow, and a report is posted from an async handler that must not wait for a mail server. Tests call it directly instead."""
    threading.Thread(target=fn, args=args, daemon=True, name="report-mail").start()


def notify(kind, target, reason) -> None:
    """Tell the captain a report arrived: one WARNING line (the kind, the page and the reason: never the reporter's note or address), and an email when SMTP is set.
    The badges need nothing here: they count the reports not yet marked read. Never raises, so a mail problem cannot lose a report."""
    log.warning("new report: %s %s, reason %s (read it at /admin)", kind, target, reason)
    _run(_email, kind, target, reason)


def _email(kind, target, reason) -> None:
    """One email to each admin (GITAWAY_ADMIN_EMAILS) through fh-saas's `send_email`, when its SMTP settings are all set. It names the page and the reason from our own list and links /admin:
    the reporter's note and address are a stranger's text and stay on the admin page. A failure is a WARNING, nothing more."""
    try:
        from fh_saas import utils_email
        from gitaway import blogbutton
        from gitaway.pages.admin import admin_emails
        try:
            utils_email.get_smtp_config()
        except ValueError:
            return      # no mail server set: the log line and the badge are the notice
        what, why = f"the {kind} {target}", REASONS.get(reason, reason)
        for addr in sorted(admin_emails()):
            got = utils_email.send_email(addr, "GitAway admin", f"GitAway: new report: {why}", "report", {"what": what, "reason": why, "admin_url": blogbutton.base_url() + "/admin"},
                                         custom_template_path=EMAIL_TEMPLATE)
            if got.get("status") == "error":
                log.warning("report email was not sent: %s", got.get("error"))
    except Exception as e:  # noqa: BLE001 - mail must never lose a report
        log.warning("report email was not sent: %s", e)


def all_reports() -> list:
    """Every report, newest first (the admin page); the address hash stays in the database. `seen` is whether the captain has opened /admin since it came in."""
    with connect() as db:
        return [dict(r._mapping) for r in db.conn.execute(text("SELECT id, kind, target, reason, note, email, created_at, seen FROM reports ORDER BY id DESC")).fetchall()]


def unseen() -> int:
    """How many reports the captain has not marked read (the number on /admin, the account menu and the header)."""
    with connect() as db:
        return db.conn.execute(text("SELECT COUNT(*) FROM reports WHERE seen = 0")).scalar()


def mark_seen(upto) -> None:
    """The reports up to id `upto` (the newest the captain was shown when they pressed "Mark all as read") are read; one that came in meanwhile is not."""
    with connect() as db:
        db.conn.execute(text("UPDATE reports SET seen = 1 WHERE seen = 0 AND id <= :m"), {"m": upto})
        db.conn.commit()
