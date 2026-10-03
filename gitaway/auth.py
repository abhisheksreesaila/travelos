"""Sign-in on fh-saas: storage location, Google keys, the local dev sign-in and the family tenant. See docs/setup.md.

Everything here is a thin layer over fh_saas.utils_auth. The dev sign-in runs the same steps as fh-saas's OAuth callback
(create_or_get_global_user, provision_new_user, create_user_session), so later code cannot tell the two apart. Both then run
`after_sign_in`, which joins the families the person's email was invited to (F-043).
"""

import json
import os
import re
from pathlib import Path

from gitaway import hostdb
from fh_saas.db_host import HostDatabase  # importing fh_saas also loads .env into the environment
from fh_saas.utils_auth import (
    create_or_get_global_user, create_user_session, get_user_membership, provision_new_user,
)

ROOT = Path(__file__).resolve().parent.parent
LOCAL_HOSTS = ("127.0.0.1", "::1")
PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "x-forwarded-server", "x-real-ip", "forwarded",
                 "cf-connecting-ip", "true-client-ip")
MAX_NEXT = 200  # longest `next` kept in the cookie across the Google round trip
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def data_dir() -> Path:
    """GITAWAY_DATA_DIR (default ./data/db under the project); a relative value is read from the project folder."""
    return (ROOT / os.getenv("GITAWAY_DATA_DIR", "data/db")).resolve()


def configure_storage() -> Path:
    """Point fh-saas at SQLite files inside the data folder and make that folder the working directory.

    fh-saas builds tenant database paths relative to the working directory and has no setting for it, so the process
    works from the data folder; the host database is DB_NAME (default app_host) there. Code must not rely on relative
    paths: assets and templates resolve from this package's folder.
    """
    os.environ["DB_TYPE"] = "SQLITE"
    os.environ.setdefault("DB_NAME", "app_host")
    folder = data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    os.chdir(folder)
    return folder


def google_enabled() -> bool:
    return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))


SESSION_DAYS = 30


def production() -> bool:
    """True on Railway (RAILWAY_ENVIRONMENT is set there) or when GITAWAY_ENV=production."""
    return os.getenv("GITAWAY_ENV", "").lower() == "production" or bool(os.getenv("RAILWAY_ENVIRONMENT"))


def check_production_settings():
    """Production needs its own cookie-signing key: a key made on the fly would sign everyone out on every redeploy."""
    if production() and not (os.getenv("GITAWAY_SECRET_KEY") or "").strip():
        raise RuntimeError("GITAWAY_SECRET_KEY must be set in production (it signs the session cookie); refusing to start.")


def session_options() -> dict:
    """FastHTML's session cookie settings: about 30 days. Starlette re-issues the cookie only when the session changes,
    so the sliding comes from session.slide, not from here; https-only in production (browsers still accept it on localhost over http in development)."""
    return {"max_age": SESSION_DAYS * 24 * 3600, "sess_https_only": production()}


def server_options() -> dict:
    """uvicorn settings for `serve`. Production: no reload, and the proxy's X-Forwarded-* headers are trusted (the app only listens
    behind Railway's proxy), so request.url.scheme is https. Locally proxy headers are ignored, so dev_login_allowed's rule holds."""
    if production():
        return {"host": "0.0.0.0", "reload": False, "proxy_headers": True, "forwarded_allow_ips": "*"}
    return {"host": "0.0.0.0", "reload": True, "proxy_headers": False}


def dev_login_enabled() -> bool:
    """The flag, but never in production, even when set."""
    return os.getenv("GITAWAY_DEV_LOGIN") == "1" and not production()


def dev_login_allowed(request) -> bool:
    """The dev sign-in needs GITAWAY_DEV_LOGIN=1 and a request straight from this machine.

    The peer address is the socket's, never a forwarded header; and a request that carries any proxy header is
    refused, because behind a proxy the "local" peer would be the proxy, not the person.
    """
    if not dev_login_enabled():
        return False
    host = request.client.host if request.client else None
    if host not in LOCAL_HOSTS:
        return False
    return not any(h in request.headers for h in PROXY_HEADERS)


def clean_email(value) -> str | None:
    email = " ".join((value or "").split()).lower()
    return email if len(email) <= 120 and _EMAIL.fullmatch(email) else None


def sign_in_dev(session, email):
    """Sign `email` in exactly as the Google callback would, creating the person and their family tenant on first use."""
    with hostdb.locked():
        host_db = HostDatabase.from_env()
        user = create_or_get_global_user(host_db, f"dev:{email}", email, {"email": email})
        membership = get_user_membership(host_db, user.id)
        if not membership:
            provision_new_user(host_db, user)
            membership = get_user_membership(host_db, user.id)
        create_user_session(session, user, membership)
        after_sign_in(session, verified=True)  # the dev sign-in is local only: its email counts as verified
    return user


def after_sign_in(session, verified):
    """The one step every sign-in ends with (the dev sign-in above and Google below): when the email is verified, families it was invited to
    are joined; the active family is chosen (gitaway.members). Returns the memberships joined this time."""
    from gitaway import members  # here, not at the top: members imports this package's other modules
    with hostdb.locked():
        return members.after_sign_in(session, verified)


def start_session(host_db, user, session, verified):
    """The steps after a person is known, shared by Google sign-in and passkey sign-in (F-074): their family (made on first use, also for a person
    who has lost every membership), the session, then `after_sign_in`. Call inside `hostdb.locked()`."""
    from fh_saas import utils_auth as ua
    membership = ua.get_user_membership(host_db, user.id)
    if not membership and not user.is_sys_admin:
        ua.provision_new_user(host_db, user)
        membership = ua.get_user_membership(host_db, user.id)
    if membership:
        ua.create_user_session(session, user, membership)
    else:  # a system admin has no family: the minimal session fh-saas gives them (gitaway.access does not support these yet)
        session["user_id"], session["email"], session["is_sys_admin"] = user.id, user.email, True
    after_sign_in(session, verified)


def sign_in_google(code, state, request, session) -> bool:
    """The Google callback, composed from fh-saas's public steps so Google's `email_verified` is kept (handle_oauth_callback discards the
    user info: docs/fh-saas-proposals.md #17). Same steps as fh_saas.utils_auth.handle_oauth_callback. Returns whether the email is verified.

    Raises when the state, the code or the user info is bad. Only a verified email may join an invited family (gitaway.members).
    """
    from fh_saas import utils_auth as ua  # looked up on the module each time: tests swap get_google_oauth_client
    ua.verify_oauth_state(session, state)
    client = ua.get_google_oauth_client()
    info = client.retr_info(code, ua.redir_url(request, "/auth/callback"))
    email = info.get("email") or ""
    verified = info.get("email_verified") in (True, "true", "True")
    with hostdb.locked():
        host_db = HostDatabase.from_env()
        user = ua.create_or_get_global_user(host_db, info[client.id_key], email, info)
        start_session(host_db, user, session, verified)
    return verified


def make_room(session):
    """After a sign-in, make sure the new auth keys left the cookie room for a creator draft, the only other thing it holds (session.BUDGET).

    Trips, the calendar, forks and the rest live in the family database; the draft is the one thing that may still be in the cookie from
    someone who signed out at this browser. If the cookie is now too big, the draft goes.
    """
    from gitaway import session as ses
    if len(json.dumps(dict(session))) > ses.BUDGET:
        session.pop("cr", None)
