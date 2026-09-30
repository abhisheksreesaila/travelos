"""GitAway app entry point. Run with `pixi run dev` (http://localhost:5002).

Each screen lives in its own module under gitaway/pages/ and registers its own routes,
so screens can be built independently.
"""

from pathlib import Path

from fasthtml.common import Beforeware, FastHTML, serve

from gitaway import session
from gitaway.layout import HEAD
from gitaway.pages import register_all

ROOT = Path(__file__).parent

app = FastHTML(before=Beforeware(session.bind, skip=[r"/assets/.*"]), hdrs=HEAD, title="GitAway", htmlkw={"lang": "en"}, key_fname=str(ROOT / ".sesskey"))
app.static_route_exts(prefix="/assets/", static_path=str(ROOT / "assets"))
register_all(app)

if __name__ == "__main__":
    serve(port=5002)
