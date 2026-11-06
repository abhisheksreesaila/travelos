"""Ready-made drafts: the captain drafts a creator's post privately and sends them a claim link (F-188). Rules and storage; the screens are gitaway/pages/creatorclaim.py.

    draft(admin_id, link, name)        read the post (the same pipeline as a creator's own paste: safe fetch, Haiku, validation) into a draft owned by no one yet, and issue its claim link
    fresh_link(draft_id)               a new link for the draft (the old one stops working): links are stored hashed, so the one shown at drafting time cannot be looked up later
    revoke(draft_id)                   the link stops working
    state(token) / claim(token, user)  "ok", "claimed", "expired", "revoked" or "unknown"; the first signed-in person to claim becomes the owner, once
    outreach(...)                      the short, warm message the captain copies; GitAway never sends it
    candidates()                       the people in docs/research/creators.csv, A priority first
    counts()                           drafts made, claimed, published

A claim link is `secrets.token_urlsafe(32)` (256 bits), kept only as its SHA-256, valid for 30 days, single use. The draft is owned by UNCLAIMED until then, so the creator's editor and publish routes
(which match owner = the signed-in person) answer 404 to everyone, and nothing is public until the claimer publishes it. The claim is one UPDATE that only matches an unclaimed, unrevoked,
unexpired row, so two people racing for one link cannot both win.
"""

import csv
import json
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import text

from gitaway import affiliate, blogbutton, creatordraft as cd, importsource
from gitaway.hub import HubError

UNCLAIMED = "*unclaimed*"      # the owner of a draft nobody has claimed (no sign-in id looks like this)
DAYS = 30
ADMIN_DAILY = 200              # drafts the captain may ask for in a day (the site-wide ceiling still applies on top)
CSV = Path(__file__).resolve().parent.parent / "docs" / "research" / "creators.csv"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
_PERSON = re.compile(r"\(([^()]{2,60})\)\s*$")


def hash_token(token) -> str:
    return hashlib.sha256(str(token).encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def link_for(token) -> str:
    return f"{blogbutton.base_url()}/claim/{token}"


def creator_name(csv_name) -> str:
    """The person's name from a CSV row's name, "Site name (Person Name)" -> "Person Name"; the whole name when there are no brackets. At most the 40 characters a trip's name takes."""
    m = _PERSON.search(csv_name or "")
    return " ".join((m.group(1) if m else csv_name or "").split())[:cd.MAX_NAME]


def first_name(name) -> str:
    return (name or "").split(" ")[0] if (name or "").strip() else "there"


# ---- the people to invite -----------------------------------------------------------------------------------------------------

def candidates() -> list:
    """Rows of docs/research/creators.csv as dicts with a `person` (the name to show on the trip) and `drafted` (the post already has a draft), A priority first, then the file's order."""
    try:
        with CSV.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return []
    done = {r["post_url"] for r in listing()}
    out = [{**r, "person": creator_name(r["name"]), "drafted": (r.get("example_post_url") or "").strip() in done} for r in rows if (r.get("example_post_url") or "").strip()]
    return sorted(out, key=lambda r: (r.get("priority") or "Z").strip() != "A")


# ---- storage ------------------------------------------------------------------------------------------------------------------

def listing() -> list:
    """Every claim, newest first: draft_id, name, post_url, state ("waiting", "claimed", "revoked", "expired"), `published` (the creator published it), `title`, `slug` and `email` (the address the claimer was signed in with, "" until claimed)."""
    with cd._db() as db:
        rows = db.conn.execute(text("""SELECT c.draft_id, c.name, c.post_url, c.expires_at, c.revoked_at, c.claimed_by, d.data, d.slug, d.published_by, c.claimed_email FROM creator_claims c
                                       LEFT JOIN creator_drafts d ON d.id = c.draft_id ORDER BY c.created_at DESC, c.rowid DESC""")).fetchall()
    now, out = _iso(_now()), []
    for r in rows:
        st = "claimed" if r[5] else "revoked" if r[4] else "expired" if r[3] <= now else "waiting"
        title = ""
        if r[6]:
            title = json.loads(r[6]).get("title", "")
        out.append({"draft_id": r[0], "name": r[1], "post_url": r[2], "state": st, "title": title, "slug": r[7] or "", "published": bool(r[8]), "email": r[9]})
    return out


def counts() -> dict:
    rows = listing()
    return {"made": len(rows), "claimed": sum(1 for r in rows if r["state"] == "claimed"), "published": sum(1 for r in rows if r["published"])}


def _issue(db, draft_id, name="", post_url="") -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    db.conn.execute(text("""INSERT INTO creator_claims (draft_id, token_hash, expires_at, name, post_url, created_at) VALUES (:d, :h, :e, :n, :u, :c)
                            ON CONFLICT (draft_id) DO UPDATE SET token_hash = :h, expires_at = :e, revoked_at = '', created_at = :c WHERE claimed_by = ''"""),
                    {"d": draft_id, "h": hash_token(token), "e": _iso(now + timedelta(days=DAYS)), "n": name, "u": post_url, "c": _iso(now)})
    db.conn.commit()
    return token


def fresh_link(draft_id) -> str:
    """A new claim link for an unclaimed draft (the old one stops working), or "" when the draft is not one that waits."""
    with cd._db() as db:
        row = db.conn.execute(text("SELECT 1 FROM creator_claims WHERE draft_id = :d AND claimed_by = ''"), {"d": str(draft_id)}).fetchone()
        return link_for(_issue(db, str(draft_id))) if row else ""


def revoke(draft_id) -> bool:
    with cd._db() as db:
        r = db.conn.execute(text("UPDATE creator_claims SET revoked_at = :n WHERE draft_id = :d AND claimed_by = '' AND revoked_at = ''"), {"n": _iso(_now()), "d": str(draft_id)})
        db.conn.commit()
        return r.rowcount == 1


def _row(token):
    if not _TOKEN.fullmatch(str(token or "")):
        return None
    with cd._db() as db:
        return db.conn.execute(text("SELECT draft_id, expires_at, revoked_at, claimed_by, name FROM creator_claims WHERE token_hash = :h"), {"h": hash_token(token)}).fetchone()


def state(token, user_id="") -> str:
    """"ok" (can be claimed), "mine" (the signed-in person already claimed it), "claimed" (someone else did), "revoked", "expired" or "unknown". A claimed link says "claimed" before it says anything else."""
    r = _row(token)
    if not r:
        return "unknown"
    if r[3]:
        return "mine" if user_id and r[3] == str(user_id) else "claimed"
    return "revoked" if r[2] else "expired" if r[1] <= _iso(_now()) else "ok"


def domain_of(d) -> str:
    """The website a draft's post is on ("blog.example.com"), for the claimer to confirm it is theirs."""
    try:
        return (urlsplit((d.get("source") or {}).get("url", "")).hostname or "").lower()
    except ValueError:
        return ""


def draft_id_of(token) -> str:
    r = _row(token)
    return r[0] if r else ""


def claim(token, user_id, email="") -> str:
    """Make `user_id` the owner of the draft behind `token` (and note the `email` they were signed in with, for the captain's list): its id. "" when the link cannot be claimed (used, revoked, expired, unknown). Claiming again as the same person gives the id again."""
    r = _row(token)
    if not r or not user_id:
        return ""
    if r[3]:
        return r[0] if r[3] == str(user_id) else ""
    now = _iso(_now())
    with cd._db() as db:
        won = db.conn.execute(text("""UPDATE creator_claims SET claimed_by = :u, claimed_at = :n, claimed_email = :e WHERE token_hash = :h AND claimed_by = '' AND revoked_at = '' AND expires_at > :n"""),
                              {"u": str(user_id), "n": now, "e": str(email or "")[:200], "h": hash_token(token)})
        if won.rowcount != 1:
            db.conn.rollback()
            return ""
        db.conn.execute(text("UPDATE creator_drafts SET owner_user = :u, updated_at = :n WHERE id = :d AND owner_user = :x"), {"u": str(user_id), "n": now, "d": r[0], "x": UNCLAIMED})
        db.conn.commit()
    return r[0]


# ---- drafting for a creator ---------------------------------------------------------------------------------------------------

def _allow() -> str:
    """Count one try for the captain today, and one for the whole site. "" when it may go ahead, else "person" or "site" (nothing counted)."""
    day = cd._today()
    with cd._db() as db:
        if not cd._take(db, "*captain*", day, ADMIN_DAILY):
            db.conn.rollback()
            return "person"
        if not cd._take(db, cd.SITE_KEY, day, cd.site_limit()):
            db.conn.rollback()
            return "site"
        db.conn.commit()
        return ""


def drafted(link) -> dict | None:
    """The existing claim for this post address, if the post was drafted before (a revoked one does not count: draft it again)."""
    try:
        link = importsource.clean_link(link)
    except importsource.SourceError:
        return None
    return next((r for r in listing() if r["post_url"] == link and r["state"] != "revoked"), None)


def draft(admin_id, link, name="", text="") -> tuple:
    """Draft one post privately for a creator: (draft dict, claim link). Raises importsource.SourceError, ai.AIError or HubError (a sentence fit to show) when it cannot.
    Blocking (a page fetch and a model call): call it from run_in_threadpool, never on the event loop. With no AI key it is the simulated draft where the showcase is on, else an error."""
    link = importsource.clean_link(link)
    name = " ".join(str(name or "").split())[:cd.MAX_NAME]
    mode = cd.mode()
    if mode == "manual":
        raise HubError("Drafting needs ANTHROPIC_API_KEY. Set it, or run on the local showcase to try the flow with made-up drafts.")
    if (hit := _allow()):
        raise HubError(cd.SITE_LIMIT_HIT if hit == "site" else f"You have drafted {ADMIN_DAILY} posts today, which is the most for one day.")
    if mode == "sample":
        d = cd.sample(UNCLAIMED, importsource.offline(link, ""), name)
    else:
        d = cd.make(UNCLAIMED, str(admin_id), importsource.gather(link, ""), name)
    with cd._db() as db:
        token = _issue(db, d["id"], name, link)
    return d, link_for(token)


# ---- the message ---------------------------------------------------------------------------------------------------------------

def outreach(person, title, link, captain) -> str:
    """The message to copy: short, warm, personal. GitAway never sends it."""
    who = first_name(person)
    return (f"Hi {who},\n\n"
            f"I loved your post \"{title}\". I'm {captain}, and I'm building GitAway, an app where families fork a trip and plan it together. "
            f"I turned your post into a trip so you can see how it looks. Nothing is public until you say so:\n\n{link}\n\n"
            "Three promises:\n"
            "1. It takes under a minute: one tap to publish, or edit first.\n"
            f"2. Flights pay you: {affiliate.pays_you()}\n"
            "3. Every trip links back to your post.\n\n"
            "It is free, and you can take it down any time.\n\n"
            f"{captain}")
