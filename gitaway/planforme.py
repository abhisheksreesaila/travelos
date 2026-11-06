"""Plan it for me (F-193): a family pays once and an agent builds their whole trip in their GitAway account. Rules and storage; the screens are gitaway/pages/planforme.py.

    price_cents()                          what it costs, read on the server (PLAN_FOR_ME_PRICE_CENTS, default 2900); the browser never says
    read_intake(form)                      (the intake, {field: message}) from the posted form; checked with the guided trip builder's own checks
    create_order(owner, tenant, email, intake)   an order awaiting payment, at today's price; get(order_id, owner) reads it back for its buyer only
    mark_paid(order_id, event_id, session_id, amount, currency)   what a verified Stripe event does: idempotent by event id, bound to the order's session and amount
    clear()                                tests: every order

An order is a short state machine, moved only by guarded UPDATEs (`WHERE status = ...`): awaiting_payment -> paid -> building -> ready | failed (STATUSES). It lives in the community database
(`plan_orders`, made on first use) so it survives a restart, the admin lists every family's orders and `forget-person` covers it (tests/test_forget_covers_every_table.py).
`plan_order_events` holds the Stripe event ids already handled: a repeated webhook finds its id there and does nothing.
"""

import json
import logging
import os
import re
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from gitaway import auth, catalog, community, showcase, tripbuild
from gitaway import tripimport as ti

log = logging.getLogger("gitaway.planforme")

DEFAULT_PRICE = 2900          # US cents: $29, one time
PRICE_RANGE = (100, 50_000)   # a setting outside this is a typo, and the default stands
MAX_DAYS = 14                 # the longest trip an agent plans (a 14-day answer is about 6,000 tokens)
MAX_MUST = 600                # characters of "must-dos"
MAX_UNPAID = 5                # unfinished orders one person can have at once; the oldest without a checkout goes when they start another
STATUSES = ("awaiting_payment", "paid", "building", "ready", "failed")
BUDGETS = {"easy": "Easy on the wallet", "comfortable": "Comfortable", "treat": "Treat ourselves"}
PACES = {"relaxed": "Relaxed", "balanced": "Balanced", "packed": "Packed"}
SUGGESTIONS = ("Disneyland, California",)       # beside the catalog's places
PROMISE = "Not useful? Reply within 7 days for a full refund."
_ID = re.compile(r"[0-9a-f]{16}")
_AIRPORT = re.compile(r"[A-Za-z]{3}")


# ---- settings ---------------------------------------------------------------------------------------------------------

def price_cents() -> int:
    """What Plan it for me costs, in US cents: PLAN_FOR_ME_PRICE_CENTS when it is whole digits inside PRICE_RANGE, else 2900. Read here on the server every time an order is made."""
    raw = os.getenv("PLAN_FOR_ME_PRICE_CENTS", "").strip()
    return int(raw) if raw.isascii() and raw.isdigit() and PRICE_RANGE[0] <= int(raw) <= PRICE_RANGE[1] else DEFAULT_PRICE


def stripe_key() -> str:
    return os.getenv("STRIPE_SECRET_KEY", "").strip()


def webhook_secret() -> str:
    return os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()


def standin() -> bool:
    """Is the local stand-in checkout in use? Only on a local copy (the showcase is on, never production) with no Stripe key."""
    return not stripe_key() and not auth.production() and showcase.on()


def offered() -> bool:
    """Is Plan it for me for sale here? With a Stripe key, or locally through the stand-in checkout. In production without the key it is not (no cards, 404s)."""
    return bool(stripe_key()) or standin()


# ---- the intake -------------------------------------------------------------------------------------------------------

def _line(value, limit) -> str:
    """One clean line of what a person typed: no control characters, spaces collapsed, cut to `limit`."""
    s = "".join(c for c in str(value if isinstance(value, (str, int)) else "") if c.isprintable() or c in " \t\n")
    return " ".join(s.split())[:limit].strip()


def read_intake(form) -> tuple:
    """(intake, errors) from a posted form (any mapping of strings). `errors` maps a form field (where, start, end, home, adults, nkids, k1.. ) to a sentence fit to show; the intake is
    only complete when it is empty. The checks are the guided trip builder's (`tripbuild.check_where`, `check_dates`, `check_who`), so a family hears the same words everywhere.
    Nothing about money is read: the form has no such field."""
    get = lambda k: str(form.get(k, "") or "").strip()
    where, start, end = _line(get("where"), 60), get("start"), get("end")
    nkids = tripbuild._whole(get("nkids"), 0)
    kids = [get(f"k{i}") for i in range(1, min(nkids, tripbuild.MAX_KIDS) + 1)]
    draft = {"title": where, "destination": where, "start": start, "end": end, "adults": get("adults") or "2", "kids": kids, "knames": [], "names": [], "emails": []}
    errors = {}
    for check in (tripbuild.check_where, tripbuild.check_dates, tripbuild.check_who):
        errors.update({("where" if k == "destination" else k): v for k, v in check(draft).items() if k != "title"})
    s, e = tripbuild._day(start), tripbuild._day(end)
    if s and "start" not in errors and s < catalog.today():
        errors["start"] = "Pick a day that has not happened yet."
    if s and e and "end" not in errors and (e - s).days + 1 > MAX_DAYS:
        errors["end"] = f"A planned trip can be at most {MAX_DAYS} days long."
    home = get("home")
    if home and not _AIRPORT.fullmatch(home):
        errors["home"] = "Use the three-letter code, like SFO, or leave it empty."
    slug = get("from")
    like = (community.get(slug) or {}).get("title", "")[:60] if slug and community.is_real(slug) else ""      # the title comes from our database, never from the form
    intake = {"where": where, "start": start, "end": end, "home": home.upper() if _AIRPORT.fullmatch(home) else "", "adults": tripbuild.adults_of(draft),
              "kids": [int(a) for a in kids if a.isascii() and a.isdigit()][:tripbuild.MAX_KIDS],
              "budget": get("budget") if get("budget") in BUDGETS else "comfortable", "must": _line(form.get("must", ""), MAX_MUST),
              "pace": get("pace") if get("pace") in PACES else "balanced", "like": like}
    return intake, errors


# ---- storage ----------------------------------------------------------------------------------------------------------

_ready: set = set()


@contextmanager
def _db():
    """The community database's connection with the order tables made (once per database file)."""
    with community.connect() as db:
        if community._url() not in _ready:
            db.conn.execute(text("""CREATE TABLE IF NOT EXISTS plan_orders (
                id TEXT PRIMARY KEY, owner_user TEXT NOT NULL, tenant_id TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'awaiting_payment',
                intake TEXT NOT NULL, amount_cents INTEGER NOT NULL, stripe_session TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '', trip_id TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0, ai_model TEXT NOT NULL DEFAULT '', ai_tokens_in INTEGER NOT NULL DEFAULT 0, ai_tokens_out INTEGER NOT NULL DEFAULT 0,
                ai_cost_micros INTEGER NOT NULL DEFAULT 0, sample INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, paid_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)"""))
            db.conn.execute(text("CREATE TABLE IF NOT EXISTS plan_order_events (event_id TEXT PRIMARY KEY, order_id TEXT NOT NULL DEFAULT '', outcome TEXT NOT NULL DEFAULT '', at TEXT NOT NULL)"))
            db.conn.commit()
            _ready.add(community._url())
        yield db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def clear() -> None:
    """Remove every order and event. For tests."""
    with _db() as db:
        for table in ("plan_orders", "plan_order_events"):
            db.conn.execute(text(f"DELETE FROM {table}"))
        db.conn.commit()


def _order(r) -> dict:
    out = dict(r)
    out["intake"] = json.loads(out["intake"])
    out["result"] = json.loads(out["result"]) if out["result"] else None
    return out


def create_order(owner, tenant, email, intake) -> dict:
    """An order awaiting payment for `owner`'s family `tenant`, at today's price (`amount_cents` is fixed here and is what the webhook must carry). At most MAX_UNPAID unfinished orders per
    person: starting another drops the oldest unpaid ones that have no checkout open (or one older than two hours: Stripe's session has expired by then)."""
    oid, now = secrets.token_hex(8), _now()
    stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="microseconds")
    with _db() as db:
        db.conn.execute(text("""DELETE FROM plan_orders WHERE owner_user = :o AND status = 'awaiting_payment' AND (stripe_session = '' OR created_at < :stale) AND id NOT IN (
                SELECT id FROM plan_orders WHERE owner_user = :o AND status = 'awaiting_payment' ORDER BY created_at DESC, id DESC LIMIT :keep)"""),
                        {"o": str(owner), "stale": stale, "keep": MAX_UNPAID - 1})
        db.conn.execute(text("INSERT INTO plan_orders (id, owner_user, tenant_id, email, intake, amount_cents, created_at, updated_at) VALUES (:i, :o, :t, :e, :n, :a, :c, :c)"),
                        {"i": oid, "o": str(owner), "t": str(tenant), "e": str(email)[:120], "n": json.dumps(intake, separators=(",", ":")), "a": price_cents(), "c": now})
        db.conn.commit()
    return get(oid, owner)


def get(order_id, owner) -> dict | None:
    """The order, but only for its buyer: anyone else (or a made-up id) gets None."""
    if not isinstance(order_id, str) or not _ID.fullmatch(order_id) or not owner:
        return None
    with _db() as db:
        r = db.conn.execute(text("SELECT * FROM plan_orders WHERE id = :i AND owner_user = :o"), {"i": order_id, "o": str(owner)}).mappings().fetchone()
    return _order(r) if r else None


def _row(order_id) -> dict | None:
    """The order whoever it belongs to (the worker, the webhook and the admin; never a request that names an id)."""
    with _db() as db:
        r = db.conn.execute(text("SELECT * FROM plan_orders WHERE id = :i"), {"i": str(order_id)}).mappings().fetchone()
    return _order(r) if r else None


def set_session(order_id, session_id) -> None:
    """Remember the Stripe Checkout session made for this order, so the webhook can be matched to it."""
    with _db() as db:
        db.conn.execute(text("UPDATE plan_orders SET stripe_session = :s, updated_at = :u WHERE id = :i AND status = 'awaiting_payment'"), {"s": str(session_id), "u": _now(), "i": order_id})
        db.conn.commit()


def mark_paid(order_id, event_id, session_id, amount, currency) -> str:
    """What a verified Stripe event for a completed payment does. Returns "paid" (the order is now paid and the worker will build it), "duplicate" (this event id, or a second event for an
    order already paid), "mismatch" (the amount or currency is not the order's: the order is marked failed, a refund is due) or "unknown" (no such order, or another session's).
    The event id is recorded first, in the same transaction, so a repeat of it does nothing at all."""
    with _db() as db:
        if not db.conn.execute(text("INSERT OR IGNORE INTO plan_order_events (event_id, order_id, at) VALUES (:e, :o, :a)"), {"e": str(event_id), "o": str(order_id), "a": _now()}).rowcount:
            return "duplicate"
        o = db.conn.execute(text("SELECT status, amount_cents, stripe_session FROM plan_orders WHERE id = :i"), {"i": str(order_id)}).mappings().fetchone() if _ID.fullmatch(str(order_id)) else None
        if o is None or o["stripe_session"] not in ("", session_id):
            outcome = "unknown"
        elif o["status"] != "awaiting_payment":
            outcome = "duplicate"
        elif int(amount or 0) != o["amount_cents"] or str(currency or "").lower() != "usd":
            db.conn.execute(text("UPDATE plan_orders SET status = 'failed', error = 'amount_mismatch', stripe_session = :s, paid_at = :u, updated_at = :u WHERE id = :i AND status = 'awaiting_payment'"),
                            {"s": session_id, "u": _now(), "i": order_id})
            outcome = "mismatch"
        else:
            db.conn.execute(text("UPDATE plan_orders SET status = 'paid', stripe_session = :s, paid_at = :u, updated_at = :u WHERE id = :i AND status = 'awaiting_payment'"), {"s": session_id, "u": _now(), "i": order_id})
            outcome = "paid"
        db.conn.execute(text("UPDATE plan_order_events SET outcome = :x WHERE event_id = :e"), {"x": outcome, "e": str(event_id)})
        db.conn.commit()
    return outcome
