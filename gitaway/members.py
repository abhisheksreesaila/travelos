"""Who is in a family, who is invited, and which family a person is working in (F-043).

A family is an fh-saas tenant (ADR-0004). fh-saas keeps a `Membership` row (person, family, role) in the host database and
nothing else: it cannot invite someone into an existing tenant, choose between two memberships, or revoke one cleanly (see
docs/fh-saas-proposals.md, rows 1 and 10). This module is the layer GitAway puts on top, without touching the package.

Storage. Two small app-owned tables live in the host database, next to fh-saas's own, made with CREATE TABLE IF NOT EXISTS:
  ga_invites       a pending (or used, revoked, expired) invitation: email, family, role, a random token, inviter, expiry
  ga_last_family   the family a person last worked in, so signing in again lands there
They are in the host database rather than a file of their own so that accepting an invite (a new `Membership` plus the
invite marked accepted) is one transaction. Memberships and roles stay fh-saas's: `core_memberships.role` is "owner" (the
person who made the family), "admin", "editor" or "viewer". "owner" counts as admin everywhere (`effective_role`).

Every use of the host database goes through `hostdb.locked()`. The cookie holds `tenant_id` and `tenant_role` (what fh-saas
reads), but they are never trusted: `role_in` reads the membership row on every request (gitaway.access), so a removed
member loses access, and a changed role takes effect, on their next request.

Joining. After any sign-in (the dev sign-in and the Google callback both call `auth.after_sign_in`) `after_sign_in` looks for
pending invites for the person's email, creates a Membership with the invited role for each (and a TenantUser row in the
family's own database, so fh-saas's `local_role` agrees), marks them accepted, and makes the last family joined the active
one. fh-saas has still made the person's own empty family on a first sign-in; that is fine and they can switch back to it.
The invite link (`/join/<token>`) goes through `accept_token`, which also needs the signed-in email to match.
"""

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from fh_saas.db_host import HostDatabase, gen_id
from fh_saas.db_tenant import TenantUser, get_or_create_tenant_db, init_tenant_core_schema
from fh_saas.utils_auth import invalidate_auth_cache
from sqlalchemy import text

from gitaway import hostdb

log = logging.getLogger("gitaway.members")

ROLES = ("admin", "editor", "viewer")      # what a person can be in a family
INVITE_ROLES = ("editor", "viewer")        # what an invite can offer; an admin promotes later
ROLE_WORDS = {"admin": "Admin", "editor": "Editor", "viewer": "Viewer"}
ROLE_HELP = {"admin": "Invites people, changes roles and removes members, and edits everything.",
             "editor": "Edits trips, the calendar, rides, forks and sharing.",
             "viewer": "Looks at everything; changes nothing."}
INVITE_DAYS = 14
MAX_MEMBERS = 12
MAX_PENDING = 20
GMAIL = ("gmail.com", "googlemail.com")


class MemberError(ValueError):
    """Something the family page refuses; the message is fit to show the person."""


class InviteProblem(MemberError):
    """An invite link that cannot be used. `kind` is "unknown", "expired", "revoked", "accepted" or "mismatch"."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


# ---- small helpers -------------------------------------------------------------------------------------------------

def now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def match_key(email: str) -> str:
    """The key two emails are compared by: lowercase, and for Gmail the dots and +tag in the name are ignored (Google treats them as one mailbox)."""
    email = (email or "").strip().lower()
    local, _, domain = email.partition("@")
    if domain in GMAIL:
        local = local.split("+")[0].replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def effective_role(raw) -> str | None:
    """fh-saas's membership role as GitAway's: "owner" is an admin; anything unknown has no access."""
    return "admin" if raw == "owner" else raw if raw in ROLES else None


def mask_email(email: str) -> str:
    local, _, domain = (email or "").partition("@")
    return f"{local[:1]}{'*' * max(1, min(len(local) - 1, 5))}@{domain}"


_READY = False


def _conn():
    """The host database's connection, with GitAway's own tables made. Call only inside `hostdb.locked()`."""
    global _READY
    host = HostDatabase.from_env()
    conn = host.db.conn
    conn.rollback()
    if not _READY:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS ga_invites (
            id TEXT PRIMARY KEY, token TEXT NOT NULL UNIQUE, email TEXT NOT NULL, email_key TEXT NOT NULL, tenant_id TEXT NOT NULL,
            role TEXT NOT NULL, invited_by TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', accepted_by TEXT, accepted_at TEXT)"""))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ga_invites_key ON ga_invites (email_key, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ga_invites_tenant ON ga_invites (tenant_id, status)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS ga_last_family (user_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL)"))
        conn.commit()
        _READY = True
    return conn


def forget_tables():
    """Make the next use re-check that the invite tables exist (tests that swap the host database)."""
    global _READY
    with hostdb.locked():
        _READY = False


def _rows(conn, sql, **params) -> list:
    return [dict(r) for r in conn.execute(text(sql), params).mappings()]


def _row(conn, sql, **params):
    found = _rows(conn, sql, **params)
    return found[0] if found else None


def _traveler(user_id, email):
    from gitaway import session as ses
    return ses.current_traveler({"user_id": user_id, "email": email})


# ---- who is in a family --------------------------------------------------------------------------------------------

_MEMBER_SQL = """SELECT m.user_id, m.role, m.created_at AS joined, u.email FROM core_memberships m
                 JOIN core_users u ON u.id = m.user_id WHERE m.tenant_id = :t AND m.is_active = 1 ORDER BY m.created_at, m.rowid"""


def membership_row(user_id, tenant_id) -> dict | None:
    """The person's active membership of that family (user_id, tenant_id, role, created_at), or None. Read fresh every time."""
    if not user_id or not tenant_id:
        return None
    with hostdb.locked():
        return _row(_conn(), "SELECT user_id, tenant_id, role, created_at FROM core_memberships WHERE user_id = :u AND tenant_id = :t AND is_active = 1",
                    u=user_id, t=tenant_id)


def role_in(user_id, tenant_id) -> str | None:
    """"admin", "editor" or "viewer" for an active member of the family, else None (not a member, or removed)."""
    found = membership_row(user_id, tenant_id)
    return effective_role(found["role"]) if found else None


def members(tenant_id) -> list:
    """The family's active members, oldest first: dicts with user_id, email, name, initials, color, role (effective), raw (fh-saas's), joined."""
    with hostdb.locked():
        rows = _rows(_conn(), _MEMBER_SQL, t=tenant_id)
    out = []
    for r in rows:
        t = _traveler(r["user_id"], r["email"])
        out.append({"user_id": r["user_id"], "email": r["email"], "name": t.name, "initials": t.initials, "color": t.color,
                    "role": effective_role(r["role"]) or "viewer", "raw": r["role"], "joined": r["joined"]})
    return out


def admin_count(tenant_id) -> int:
    return sum(1 for m in members(tenant_id) if m["role"] == "admin")


def family_label(tenant_id) -> str:
    """"Ari Rivera's family": named after the person who made it (fh-saas names every tenant "<name>'s Workspace" and cannot be told otherwise)."""
    with hostdb.locked():
        owner = _row(_conn(), """SELECT u.email FROM core_memberships m JOIN core_users u ON u.id = m.user_id
                                 WHERE m.tenant_id = :t ORDER BY (m.role = 'owner') DESC, m.created_at, m.rowid LIMIT 1""", t=tenant_id)
    if not owner:
        return "A family"
    name = _traveler("x", owner["email"]).name
    return f"{name}'s family"


def families_of(user_id) -> list:
    """The person's active families, in the order they joined them: dicts with tenant_id, role (effective), label, joined."""
    with hostdb.locked():
        rows = _rows(_conn(), "SELECT tenant_id, role, created_at AS joined FROM core_memberships WHERE user_id = :u AND is_active = 1 ORDER BY created_at, rowid", u=user_id)
    return [{"tenant_id": r["tenant_id"], "role": effective_role(r["role"]) or "viewer", "joined": r["joined"], "label": family_label(r["tenant_id"])} for r in rows]


def crew(session) -> list:
    """The other members of the signed-in person's family as Friend-like objects (name, initials, color), newest member last. For the calendar's avatars."""
    from gitaway import session as ses
    uid, tid = (session or {}).get("user_id"), (session or {}).get("tenant_id")
    if not uid or not tid or not role_in(uid, tid):
        return []
    return [ses.Friend(m["name"], m["initials"], m["color"]) for m in members(tid) if m["user_id"] != uid]


# ---- the person's active family ------------------------------------------------------------------------------------

def apply_active(session, tenant_id, raw_role):
    """Put a family in the session as fh-saas's create_user_session does (`tenant_id`, `tenant_role`), and drop the cached auth."""
    session["tenant_id"], session["tenant_role"] = tenant_id, raw_role
    invalidate_auth_cache(session)


def _remember(conn, user_id, tenant_id):
    conn.execute(text("INSERT OR REPLACE INTO ga_last_family (user_id, tenant_id) VALUES (:u, :t)"), {"u": user_id, "t": tenant_id})
    conn.commit()


def set_active(session, tenant_id) -> bool:
    """Work in another of the person's families. The membership is checked here, never trusted from the form. False when they are not a member."""
    uid = (session or {}).get("user_id")
    found = membership_row(uid, tenant_id)
    if not found:
        return False
    with hostdb.locked():
        _remember(_conn(), uid, tenant_id)
    apply_active(session, tenant_id, found["role"])
    return True


def preferred_family(user_id) -> dict | None:
    """The membership to work in after signing in: the family last used if they still belong to it, else the first they joined."""
    with hostdb.locked():
        conn = _conn()
        last = _row(conn, """SELECT m.user_id, m.tenant_id, m.role FROM core_memberships m JOIN ga_last_family l ON l.user_id = m.user_id AND l.tenant_id = m.tenant_id
                             WHERE m.user_id = :u AND m.is_active = 1""", u=user_id)
        return last or _row(conn, "SELECT user_id, tenant_id, role FROM core_memberships WHERE user_id = :u AND is_active = 1 ORDER BY created_at, rowid LIMIT 1", u=user_id)


# ---- invites -------------------------------------------------------------------------------------------------------

def _invite_state(inv) -> str:
    if inv["status"] == "pending" and inv["expires_at"] <= _iso(now()):
        return "expired"
    return inv["status"]


def _with_state(inv):
    return {**inv, "state": _invite_state(inv)} if inv else None


def _require_admin(conn, tenant_id, actor_id):
    found = _row(conn, "SELECT role FROM core_memberships WHERE user_id = :u AND tenant_id = :t AND is_active = 1", u=actor_id, t=tenant_id)
    if not found or effective_role(found["role"]) != "admin":
        raise MemberError("Only a family admin can do that.")


def clean_email(value):
    from gitaway import auth
    return auth.clean_email(value)


def invite(tenant_id, actor_id, email, role) -> dict:
    """An admin invites `email` into the family as `role` (editor or viewer). Returns the invite (it carries the token for the link).

    Inviting the same address again refreshes the pending invite (new role, new expiry, same link). Refuses an address that is
    already a member, a bad address, an unknown role and a family that is full.
    """
    email = clean_email(email)
    if not email:
        raise MemberError("Type a full email address, like sam@gmail.com.")
    if role not in INVITE_ROLES:
        raise MemberError("Choose Editor or Viewer.")
    key = match_key(email)
    with hostdb.locked():
        conn = _conn()
        _require_admin(conn, tenant_id, actor_id)
        if any(match_key(m["email"]) == key for m in _rows(conn, _MEMBER_SQL, t=tenant_id)):
            raise MemberError(f"{email} is already in your family.")
        if len(_rows(conn, _MEMBER_SQL, t=tenant_id)) >= MAX_MEMBERS:
            raise MemberError(f"That is {MAX_MEMBERS} people already. A family stays small.")
        expires = _iso(now() + timedelta(days=INVITE_DAYS))
        pending = [i for i in _rows(conn, "SELECT * FROM ga_invites WHERE tenant_id = :t AND status = 'pending' AND expires_at > :n", t=tenant_id, n=_iso(now()))]
        same = next((i for i in pending if i["email_key"] == key), None)
        if same:
            conn.execute(text("UPDATE ga_invites SET role = :r, expires_at = :e, email = :m WHERE id = :id"), {"r": role, "e": expires, "m": email, "id": same["id"]})
            conn.commit()
            return _with_state(_row(conn, "SELECT * FROM ga_invites WHERE id = :id", id=same["id"]))
        if len(pending) >= MAX_PENDING:
            raise MemberError(f"{MAX_PENDING} invites are waiting already. Revoke one you do not need first.")
        row = {"id": gen_id(), "token": secrets.token_urlsafe(24), "email": email, "email_key": key, "tenant_id": tenant_id, "role": role,
               "invited_by": actor_id, "created_at": _iso(now()), "expires_at": expires}
        conn.execute(text("""INSERT INTO ga_invites (id, token, email, email_key, tenant_id, role, invited_by, created_at, expires_at)
                             VALUES (:id, :token, :email, :email_key, :tenant_id, :role, :invited_by, :created_at, :expires_at)"""), row)
        conn.commit()
        return _with_state(_row(conn, "SELECT * FROM ga_invites WHERE id = :id", id=row["id"]))


def pending_invites(tenant_id) -> list:
    """The invites still waiting to be used, newest first."""
    with hostdb.locked():
        rows = _rows(_conn(), "SELECT * FROM ga_invites WHERE tenant_id = :t AND status = 'pending' AND expires_at > :n ORDER BY created_at DESC, rowid DESC", t=tenant_id, n=_iso(now()))
    return [_with_state(r) for r in rows]


def revoke(tenant_id, actor_id, invite_id) -> bool:
    """An admin takes back a pending invite: its link stops working. False when there was nothing pending by that id in this family."""
    with hostdb.locked():
        conn = _conn()
        _require_admin(conn, tenant_id, actor_id)
        n = conn.execute(text("UPDATE ga_invites SET status = 'revoked' WHERE id = :id AND tenant_id = :t AND status = 'pending'"), {"id": invite_id, "t": tenant_id}).rowcount
        conn.commit()
        return n > 0


def find_invite(token) -> dict | None:
    """The invite behind a link token (with `state`: pending, expired, revoked or accepted), or None."""
    if not isinstance(token, str) or not token or len(token) > 80:
        return None
    with hostdb.locked():
        return _with_state(_row(_conn(), "SELECT * FROM ga_invites WHERE token = :k", k=token))


def _join(conn, inv, user_id, email):
    """Make the person a member with the invited role and mark the invite accepted: one commit. Call inside `hostdb.locked()`.

    Returns the membership row. A person who is already in the family keeps the role they have; one who was removed is let back in.
    """
    found = _row(conn, "SELECT id, role, is_active FROM core_memberships WHERE user_id = :u AND tenant_id = :t", u=user_id, t=inv["tenant_id"])
    if found and found["is_active"]:
        role = found["role"]
    elif found:
        conn.execute(text("UPDATE core_memberships SET is_active = 1, role = :r WHERE id = :id"), {"r": inv["role"], "id": found["id"]})
        role = inv["role"]
    else:
        conn.execute(text("""INSERT INTO core_memberships (id, user_id, tenant_id, profile_id, role, is_active, created_at)
                             VALUES (:id, :u, :t, :u, :r, 1, :at)"""), {"id": gen_id(), "u": user_id, "t": inv["tenant_id"], "r": inv["role"], "at": _iso(now())})
        role = inv["role"]
    conn.execute(text("UPDATE ga_invites SET status = 'accepted', accepted_by = :u, accepted_at = :at WHERE id = :id"), {"u": user_id, "at": _iso(now()), "id": inv["id"]})
    conn.commit()
    return {"user_id": user_id, "tenant_id": inv["tenant_id"], "role": role}


def _sync_tenant_user(tenant_id, user_id, email, role):
    """Keep fh-saas's own per-family record (TenantUser.local_role) in step with the membership. Best effort: the host membership is the truth."""
    db = None
    try:
        db = get_or_create_tenant_db(tenant_id)
        users = init_tenant_core_schema(db)["tenant_users"]
        if db.conn.execute(text("SELECT 1 FROM core_tenant_users WHERE id = :u"), {"u": user_id}).first():
            db.conn.execute(text("UPDATE core_tenant_users SET local_role = :r WHERE id = :u"), {"r": role, "u": user_id})
        else:
            from fh_saas.db_host import timestamp
            users.insert(TenantUser(id=user_id, display_name=_traveler(user_id, email).name, local_role=role, created_at=timestamp()))
        db.conn.commit()
    except Exception:
        log.warning("could not write the TenantUser row of %s in family %s", user_id, tenant_id, exc_info=True)
    finally:
        if db is not None:
            try:
                db.conn.close()
            except Exception:
                pass


def accept_pending(user_id, email) -> list:
    """Join every family with a live invite for this email. Returns the memberships joined, oldest invite first. Nothing to do: []."""
    key = match_key(email)
    joined = []
    with hostdb.locked():
        conn = _conn()
        for inv in _rows(conn, "SELECT * FROM ga_invites WHERE email_key = :k AND status = 'pending' AND expires_at > :n ORDER BY created_at, rowid", k=key, n=_iso(now())):
            m = _join(conn, inv, user_id, email)
            joined.append(m)
            log.info("invite %s accepted by %s into family %s as %s", inv["id"], user_id, inv["tenant_id"], m["role"])
    for m in joined:
        _sync_tenant_user(m["tenant_id"], user_id, email, effective_role(m["role"]))
    return joined


def accept_token(user_id, email, token) -> dict:
    """The signed-in person uses an invite link. The email must match the invite: a token alone gets nobody in.

    Returns the membership joined. Raises InviteProblem (unknown, expired, revoked, accepted, mismatch).
    """
    with hostdb.locked():  # looked at and used under one lock: a revoke or another use cannot slip in between
        inv = find_invite(token)
        if not inv:
            raise InviteProblem("unknown", "That invite link is not one we know. Ask for a new one.")
        if inv["state"] == "expired":
            raise InviteProblem("expired", "That invite has expired. Ask the family admin for a new one.")
        if inv["state"] == "revoked":
            raise InviteProblem("revoked", "That invite was taken back. Ask the family admin for a new one.")
        if inv["state"] == "accepted":
            raise InviteProblem("accepted", "That invite was already used.")
        if match_key(email) != inv["email_key"]:
            log.warning("invite %s (for %s) was opened by user %s signed in as %s: the email does not match, nobody joined",
                        inv["id"], mask_email(inv["email"]), user_id, mask_email(email))
            raise InviteProblem("mismatch", "This invite is for a different email address.")
        m = _join(_conn(), inv, user_id, email)
    _sync_tenant_user(m["tenant_id"], user_id, email, effective_role(m["role"]))
    log.info("invite %s accepted by %s into family %s as %s (link)", inv["id"], user_id, inv["tenant_id"], m["role"])
    return m


# ---- changing the family -------------------------------------------------------------------------------------------

def _admins(conn, tenant_id):
    return [r["user_id"] for r in _rows(conn, _MEMBER_SQL, t=tenant_id) if effective_role(r["role"]) == "admin"]


def change_role(tenant_id, actor_id, user_id, role):
    """An admin changes a member's role (admin, editor or viewer). The last admin cannot be demoted; only the owner can change the owner."""
    if role not in ROLES:
        raise MemberError("Choose Admin, Editor or Viewer.")
    with hostdb.locked():
        conn = _conn()
        _require_admin(conn, tenant_id, actor_id)
        target = _row(conn, "SELECT id, role FROM core_memberships WHERE user_id = :u AND tenant_id = :t AND is_active = 1", u=user_id, t=tenant_id)
        if not target:
            raise MemberError("That person is not in your family.")
        if target["role"] == "owner" and actor_id != user_id:
            raise MemberError("Only the person who made the family can change their own role.")
        if effective_role(target["role"]) == role:
            return
        if effective_role(target["role"]) == "admin" and role != "admin" and _admins(conn, tenant_id) == [user_id]:
            raise MemberError("A family needs at least one admin. Make someone else an admin first.")
        conn.execute(text("UPDATE core_memberships SET role = :r WHERE id = :id"), {"r": role, "id": target["id"]})
        conn.commit()
        email = _row(conn, "SELECT email FROM core_users WHERE id = :u", u=user_id)["email"]
    _sync_tenant_user(tenant_id, user_id, email, role)


def remove(tenant_id, actor_id, user_id):
    """An admin removes a member: their membership is switched off and they lose access on their next request.

    Refuses the last admin (even if it is the admin removing themselves) and anyone but the owner removing the owner.
    """
    with hostdb.locked():
        conn = _conn()
        _require_admin(conn, tenant_id, actor_id)
        target = _row(conn, "SELECT id, role FROM core_memberships WHERE user_id = :u AND tenant_id = :t AND is_active = 1", u=user_id, t=tenant_id)
        if not target:
            raise MemberError("That person is not in your family.")
        if target["role"] == "owner" and actor_id != user_id:
            raise MemberError("Only the person who made the family can leave it.")
        if effective_role(target["role"]) == "admin" and _admins(conn, tenant_id) == [user_id]:
            raise MemberError("You are the only admin. Make someone else an admin before you leave.")
        conn.execute(text("UPDATE core_memberships SET is_active = 0 WHERE id = :id"), {"id": target["id"]})
        conn.execute(text("DELETE FROM ga_last_family WHERE user_id = :u AND tenant_id = :t"), {"u": user_id, "t": tenant_id})
        conn.commit()
    log.info("user %s removed from family %s by %s", user_id, tenant_id, actor_id)


# ---- sign-in -------------------------------------------------------------------------------------------------------

def after_sign_in(session) -> list:
    """The one hook every sign-in runs (auth.after_sign_in): join the families the person's email was invited to, then choose the active one.

    A person who just joined a family works in it. Otherwise they work in the family they used last, else the first. Returns the
    memberships joined this time.
    """
    uid, email = session.get("user_id"), session.get("email") or ""
    if not uid:
        return []
    joined = accept_pending(uid, email)
    target = ({"tenant_id": joined[-1]["tenant_id"], "role": joined[-1]["role"]} if joined else preferred_family(uid))
    if target:
        with hostdb.locked():
            _remember(_conn(), uid, target["tenant_id"])
        apply_active(session, target["tenant_id"], target["role"])
    invalidate_auth_cache(session)
    return joined
