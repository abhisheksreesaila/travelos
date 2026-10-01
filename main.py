"""GitAway app entry point. Run with `pixi run dev` (http://localhost:5002; set PORT to change it).

Each screen lives in its own module under gitaway/pages/ and registers its own routes,
so screens can be built independently. Sign-in, families and storage are fh-saas (gitaway/auth.py, docs/setup.md).
"""

import os
from pathlib import Path

from fasthtml.common import Beforeware, FastHTML, Response, serve
from fh_saas.utils_auth import create_auth_beforeware
from fh_saas.utils_log import configure_logging

from gitaway import access, auth, hostdb, session
from gitaway.layout import HEAD
from gitaway.pages import register_all
from gitaway.pages.family import PRIVATE

ROOT = Path(__file__).parent.resolve()

configure_logging()
auth.configure_storage()  # SQLite under GITAWAY_DATA_DIR; this also makes it the working directory, so nothing below may use relative paths

# fh-saas hydrates request.state.user only on the private paths; every other page is public and reads the session itself.
_private = "|".join(p.rstrip("/") for p in PRIVATE)
auth_before = create_auth_beforeware(redirect_path="/signin?next=%2Ffamily", setup_tenant_db=False, session_cache=False,
                                     skip=[rf"(?!(?:{_private})(?:/.*)?$).*"])

_check_auth = auth_before.f


def _locked_auth(req, sess):
    """fh-saas's membership check uses its one shared host connection: take the host lock around it (gitaway.hostdb)."""
    with hostdb.locked():
        return _check_auth(req, sess)


auth_before = Beforeware(_locked_auth, skip=auth_before.skip)

_OPEN = [r"/assets/.*", r"/healthz"]


def make_app():
    auth.check_production_settings()
    app = FastHTML(before=[Beforeware(access.guard, skip=_OPEN), auth_before, Beforeware(session.bind, skip=_OPEN)], hdrs=HEAD, title="GitAway",
                   htmlkw={"lang": "en"}, secret_key=os.getenv("GITAWAY_SECRET_KEY") or None, key_fname=str(ROOT / ".sesskey"),
                   **auth.session_options())
    app.static_route_exts(prefix="/assets/", static_path=str(ROOT / "assets"))

    @app.get("/healthz")
    def healthz():
        """Railway's health check: no session, no database."""
        return Response("ok", media_type="text/plain")

    register_all(app)
    return app


app = make_app()

if __name__ == "__main__":
    opts = auth.server_options()
    if opts["reload"]:
        opts["reload_dirs"] = [str(ROOT)]  # the working directory is the data folder, so say where the code is
    serve(port=int(os.getenv("PORT", "5002")), **opts)
