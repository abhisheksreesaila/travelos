"""GitAway app entry point. Run with `pixi run dev` (http://localhost:5002; set PORT to change it).

Each screen lives in its own module under gitaway/pages/ and registers its own routes,
so screens can be built independently. Sign-in, families and storage are fh-saas (gitaway/auth.py, docs/setup.md).
"""

import os
from pathlib import Path

from starlette.middleware import Middleware
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


class NoStoreWhenSignedIn:
    """F-062: every signed-in HTML response is `Cache-Control: private, no-store`, so Back after sign-out cannot show the last person's
    pages from the browser's back/forward or HTTP cache. (The service worker's own Cache API copy for offline use ignores no-store and
    is cleared on sign-out.) Signed-out pages and static assets are untouched."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        async def send_with(message):
            if message["type"] == "http.response.start" and scope.get(session.PRIVATE_SCOPE_KEY):
                headers = list(message.get("headers", []))
                if any(k.lower() == b"content-type" and v.startswith(b"text/html") for k, v in headers):
                    headers = [(k, v) for k, v in headers if k.lower() != b"cache-control"] + [(b"cache-control", b"private, no-store")]
                    message = {**message, "headers": headers}
            await send(message)
        await self.app(scope, receive, send_with)


def make_app():
    auth.check_production_settings()
    app = FastHTML(before=[Beforeware(access.guard, skip=_OPEN), auth_before, Beforeware(session.bind, skip=_OPEN)], hdrs=HEAD, title="GitAway", middleware=[Middleware(NoStoreWhenSignedIn)],
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
