"""Face ID sign-in (F-074): WebAuthn passkeys. The logic lives here; the routes are gitaway/pages/passkeys.py.

A passkey identifies a person, not a family, so it lives in the host database (table `ga_passkeys`, made like the invite tables in
gitaway.members). Only the public key is stored. Signing in with one ends in `auth.start_session`, the step Google sign-in uses too.

The relying party (site name and origin the browser checks) comes from settings in production: GITAWAY_PUBLIC_URL, else Railway's
RAILWAY_PUBLIC_DOMAIN, else passkeys are off. Behind the proxy the Host and X-Forwarded-* headers are never trusted for it. Locally it is
the address of the request (localhost works; browsers refuse an IP address).

A challenge is kept in the signed session cookie for CHALLENGE_SECONDS and is used up by the first answer, right or wrong.
Nothing here logs credential material.
"""

import json
import os
import time
from datetime import datetime, timezone

from fh_saas.db_host import HostDatabase, gen_id
from sqlalchemy import text
from webauthn import (
    base64url_to_bytes, generate_authentication_options, generate_registration_options, options_to_json,
    verify_authentication_response, verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorAttachment, AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor, ResidentKeyRequirement, UserVerificationRequirement,
)

from gitaway import auth, hostdb

CHALLENGE_SECONDS = 300
MAX_PER_PERSON = 10
MAX_CREDENTIAL = 12000          # bytes of JSON a browser's answer may be
SITE_NAME = "GitAway"
_READY = False


class PasskeyError(Exception):
    """A message that is safe to show the person."""


def now() -> float:
    return time.time()


def relying_party(request):
    """(rp_id, origin) the browser must be on, or None when passkeys cannot work here."""
    if auth.production():
        base = (os.getenv("GITAWAY_PUBLIC_URL") or "").strip().rstrip("/")
        if not base and (domain := (os.getenv("RAILWAY_PUBLIC_DOMAIN") or "").strip()):
            base = f"https://{domain}"
        if not base.startswith("https://") or len(base) <= 8:
            return None
        host = base[len("https://"):].split("/")[0]
        return host.split(":")[0], f"https://{host}"
    host = request.url.hostname or ""
    if not host or host.replace(".", "").isdigit() or ":" in host:   # an IP address is not a valid site for a passkey
        return None
    return host, f"{request.url.scheme}://{request.url.netloc}"


def configured() -> bool:
    """Whether this server can do passkeys at all, without a request: production needs its public address set; locally the request decides."""
    return not auth.production() or any((os.getenv(k) or "").strip() for k in ("GITAWAY_PUBLIC_URL", "RAILWAY_PUBLIC_DOMAIN"))


def available(request) -> bool:
    return relying_party(request) is not None


def _conn():
    """The host database's connection with the passkey table made. Call only inside `hostdb.locked()`."""
    global _READY
    conn = HostDatabase.from_env().db.conn
    conn.rollback()
    if not _READY:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS ga_passkeys (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, credential_id TEXT NOT NULL UNIQUE, public_key TEXT NOT NULL,
            sign_count INTEGER NOT NULL DEFAULT 0, transports TEXT NOT NULL DEFAULT '[]', name TEXT NOT NULL,
            verified INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, last_used TEXT)"""))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ga_passkeys_user ON ga_passkeys (user_id)"))
        conn.commit()
        _READY = True
    return conn


def forget_tables():
    global _READY
    with hostdb.locked():
        _READY = False


def _rows(conn, sql, **params) -> list:
    return [dict(r) for r in conn.execute(text(sql), params).mappings()]


def _stamp() -> str:
    return datetime.fromtimestamp(now(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def device_name(user_agent) -> str:
    ua = user_agent or ""
    for word, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android phone"), ("Macintosh", "Mac"), ("Windows", "Windows PC"), ("CrOS", "Chromebook"), ("Linux", "Linux computer")):
        if word in ua:
            return name
    return "This device"


def listing(user_id) -> list:
    """The person's passkeys for the page: id, name, created_at, last_used. No credential material."""
    with hostdb.locked():
        return _rows(_conn(), "SELECT id, name, created_at, last_used FROM ga_passkeys WHERE user_id = :u ORDER BY created_at, rowid", u=user_id)


def count(user_id) -> int:
    return len(listing(user_id))


def remove(user_id, passkey_id) -> bool:
    """Remove one of the person's own passkeys (someone else's id changes nothing)."""
    with hostdb.locked():
        conn = _conn()
        done = conn.execute(text("DELETE FROM ga_passkeys WHERE id = :i AND user_id = :u"), {"i": passkey_id, "u": user_id}).rowcount
        conn.commit()
    return bool(done)


# ---- challenges -----------------------------------------------------------------------------------------------------------------------

def _keep_challenge(session, kind, challenge, user_id=""):
    session["pk"] = {"k": kind, "c": bytes_to_base64url(challenge), "t": int(now()), "u": user_id}


def _take_challenge(session, kind, user_id=""):
    """The challenge bytes the session holds for `kind`, used up now; raises when there is none, it is the wrong kind, or it is too old."""
    held = session.pop("pk", None)
    if not isinstance(held, dict) or held.get("k") != kind or held.get("u", "") != user_id:
        raise PasskeyError("That took too long or was already used. Please try again.")
    if now() - int(held.get("t") or 0) > CHALLENGE_SECONDS:
        raise PasskeyError("That took too long. Please try again.")
    return base64url_to_bytes(held["c"])


# ---- adding a passkey ------------------------------------------------------------------------------------------------------------------

def registration_options(session, request, user_id, email) -> str:
    rp = relying_party(request)
    if rp is None:
        raise PasskeyError("Face ID is not set up on this site.")
    with hostdb.locked():
        have = _rows(_conn(), "SELECT credential_id, transports FROM ga_passkeys WHERE user_id = :u", u=user_id)
    if len(have) >= MAX_PER_PERSON:
        raise PasskeyError("That is as many passkeys as one person can have. Remove one you no longer use.")
    opts = generate_registration_options(
        rp_id=rp[0], rp_name=SITE_NAME, user_id=user_id.encode(), user_name=email, user_display_name=email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM, resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UserVerificationRequirement.REQUIRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(h["credential_id"])) for h in have],
    )
    _keep_challenge(session, "reg", opts.challenge, user_id)
    return options_to_json(opts)


def register(session, request, user_id, credential, user_agent="") -> dict:
    """Check the browser's answer and keep the new passkey. Raises PasskeyError (nothing stored) when anything is off."""
    rp = relying_party(request)
    challenge = _take_challenge(session, "reg", user_id)
    if rp is None or len(json.dumps(credential)) > MAX_CREDENTIAL:
        raise PasskeyError("Face ID could not be added.")
    try:
        ok = verify_registration_response(credential=credential, expected_challenge=challenge, expected_rp_id=rp[0], expected_origin=rp[1], require_user_verification=True)
    except Exception:
        raise PasskeyError("Face ID could not be added. Please try again.") from None
    transports = [t for t in (credential.get("response", {}).get("transports") or []) if isinstance(t, str)][:6]
    row = {"id": gen_id(), "user_id": user_id, "credential_id": bytes_to_base64url(ok.credential_id), "public_key": bytes_to_base64url(ok.credential_public_key),
           "sign_count": ok.sign_count, "transports": json.dumps(transports), "name": device_name(user_agent), "verified": 1 if session.get("verified", 1) else 0, "created_at": _stamp()}
    with hostdb.locked():
        conn = _conn()
        if _rows(conn, "SELECT 1 FROM ga_passkeys WHERE credential_id = :c", c=row["credential_id"]):
            raise PasskeyError("That passkey is already added.")
        conn.execute(text("""INSERT INTO ga_passkeys (id, user_id, credential_id, public_key, sign_count, transports, name, verified, created_at)
                             VALUES (:id, :user_id, :credential_id, :public_key, :sign_count, :transports, :name, :verified, :created_at)"""), row)
        conn.commit()
    return {"id": row["id"], "name": row["name"]}


# ---- signing in ------------------------------------------------------------------------------------------------------------------------

def authentication_options(session, request) -> str:
    """Options for a sign-in with no person named: the phone offers its own passkeys for this site (discoverable credentials)."""
    rp = relying_party(request)
    if rp is None:
        raise PasskeyError("Face ID is not set up on this site.")
    opts = generate_authentication_options(rp_id=rp[0], user_verification=UserVerificationRequirement.REQUIRED)
    _keep_challenge(session, "auth", opts.challenge)
    return options_to_json(opts)


def authenticate(session, request, credential):
    """Check the browser's answer. Returns the stored passkey row (with `user_id`) and updates its counter; raises PasskeyError otherwise."""
    rp = relying_party(request)
    challenge = _take_challenge(session, "auth")
    if rp is None or not isinstance(credential, dict) or len(json.dumps(credential)) > MAX_CREDENTIAL:
        raise PasskeyError("Face ID did not work. Please try again.")
    refused = PasskeyError("Face ID did not work. Try again, or sign in another way.")
    cid = credential.get("id")
    if not isinstance(cid, str) or len(cid) > 1024:
        raise refused
    with hostdb.locked():
        found = _rows(_conn(), "SELECT * FROM ga_passkeys WHERE credential_id = :c", c=cid)
    if not found:
        raise refused
    row = found[0]
    try:
        ok = verify_authentication_response(
            credential=credential, expected_challenge=challenge, expected_rp_id=rp[0], expected_origin=rp[1],
            credential_public_key=base64url_to_bytes(row["public_key"]), credential_current_sign_count=row["sign_count"], require_user_verification=True)
    except Exception:   # a wrong origin, site, challenge or signature, or a counter that went backwards
        raise refused from None
    with hostdb.locked():
        conn = _conn()
        done = conn.execute(text("UPDATE ga_passkeys SET sign_count = :n, last_used = :t WHERE id = :i AND sign_count = :old"),
                            {"n": ok.new_sign_count, "t": _stamp(), "i": row["id"], "old": row["sign_count"]}).rowcount
        conn.commit()
    if not done and not (ok.new_sign_count == 0 == row["sign_count"]):   # another answer for this passkey got in first: the counter would go backwards
        raise refused
    return row


def sign_in(session, row):
    """Start the session for the passkey's owner exactly as Google sign-in does. Returns the person's email."""
    with hostdb.locked():
        host_db = HostDatabase.from_env()
        host_db.rollback()
        found = host_db.global_users(where="id = :id", where_args={"id": row["user_id"]}, limit=1)
        if not found:
            raise PasskeyError("Face ID did not work. Try again, or sign in another way.")
        user = found[0]
        auth.start_session(host_db, user, session, bool(row["verified"]))
    return user.email
