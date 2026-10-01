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


def dev_login_enabled() -> bool:
    return os.getenv("GITAWAY_DEV_LOGIN") == "1"


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
        after_sign_in(session)
    return user


def after_sign_in(session):
    """The one step every sign-in ends with (the dev sign-in above and the Google callback in pages/signin.py): families the person's
    email was invited to are joined and the active family is chosen (gitaway.members). Returns the memberships joined this time."""
    from gitaway import members  # here, not at the top: members imports this package's other modules
    with hostdb.locked():
        return members.after_sign_in(session)


def make_room(session):
    """After a sign-in, make sure the new auth keys left the cookie room for a creator draft, the only other thing it holds (session.BUDGET).

    Trips, the calendar, forks and the rest live in the family database; the draft is the one thing that may still be in the cookie from
    someone who signed out at this browser. If the cookie is now too big, the draft goes.
    """
    from gitaway import session as ses
    if len(json.dumps(dict(session))) > ses.BUDGET:
        session.pop("cr", None)
