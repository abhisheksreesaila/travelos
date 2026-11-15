"""A dev server for looking at the creator pages (F-253) with no network: the recorded Lisbon post (tests/fixtures/creator_import) is read through the app's own fetcher and drafted from the
recorded answer, the dev sign-in is on, the showcase on (F253_LIVE=1: off). `pixi run python scripts/f253_dev.py` serves on F253_PORT (default 5253), data in F253_DATA (default a folder
beside the checkout's .pixi, never the project's). F253_WAIT is how long the pretend model takes (seconds, default 3: long enough to look at the page waiting)."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("F253_DATA") or ROOT / ".pixi" / "f253-data")
DATA.mkdir(parents=True, exist_ok=True)
os.environ.update({"GITAWAY_DATA_DIR": str(DATA), "GITAWAY_DEV_LOGIN": "1", "DB_TYPE": "SQLITE", "DB_NAME": "app_host", "GITAWAY_SHOWCASE": "0" if os.getenv("F253_LIVE") else "1",
                   "ANTHROPIC_API_KEY": "sk-ant-not-a-real-key-0000", "PLAN_FOR_ME_REVIEW": "0"})
for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT"):
    os.environ[key] = ""
sys.path.insert(0, str(ROOT))
os.chdir(DATA)
from gitaway import ai, safefetch  # noqa: E402
from tests.creator_import_support import Model, recorded  # noqa: E402

_, web, answer = recorded()


class Slow(Model):
    def __call__(self, kwargs, timeout):
        time.sleep(float(os.getenv("F253_WAIT", "3")))
        return super().__call__(kwargs, timeout)


ai.ANTHROPIC_TRANSPORT = Slow(answer)
safefetch.TRANSPORT = web
safefetch.RESOLVER = lambda host: ["93.184.216.34"]
import uvicorn  # noqa: E402
import main  # noqa: E402

uvicorn.run(main.app, host="127.0.0.1", port=int(os.getenv("F253_PORT", "5253")), log_level="warning")
