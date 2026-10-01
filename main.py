"""GitAway app entry point. Run with `pixi run dev` (http://localhost:5002; set PORT to change it).

Each screen lives in its own module under gitaway/pages/ and registers its own routes,
so screens can be built independently. Sign-in, families and storage are fh-saas (gitaway/auth.py, docs/setup.md).
"""

import os
from pathlib import Path

from fasthtml.common import Beforeware, FastHTML, serve
from fh_saas.utils_auth import create_auth_beforeware
from fh_saas.utils_log import configure_logging

from gitaway import auth, session
from gitaway.layout import HEAD
from gitaway.pages import register_all
from gitaway.pages.family import PRIVATE

ROOT = Path(__file__).parent.resolve()

configure_logging()
auth.configure_storage()  # SQLite under GITAWAY_DATA_DIR; this also makes it the working directory, so nothing below may use relative paths

# fh-saas hydrates request.state.user only on the private paths; every other page is public and reads the session itself.
_private = "|".join(p.rstrip("/") for p in PRIVATE)
auth_before = create_auth_beforeware(redirect_path="/signin?next=%2Ffamily", setup_tenant_db=False, session_cache=True,
                                     skip=[rf"(?!(?:{_private})(?:/.*)?$).*"])

app = FastHTML(before=[auth_before, Beforeware(session.bind, skip=[r"/assets/.*"])], hdrs=HEAD, title="GitAway", htmlkw={"lang": "en"},
               secret_key=os.getenv("GITAWAY_SECRET_KEY") or None, key_fname=str(ROOT / ".sesskey"))
app.static_route_exts(prefix="/assets/", static_path=str(ROOT / "assets"))
register_all(app)

if __name__ == "__main__":
    serve(port=int(os.getenv("PORT", "5002")), reload_dirs=[str(ROOT)])  # the working directory is the data folder, so say where the code is
