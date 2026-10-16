"""F-168 measuring server: the app as the browser tests run it (throwaway data folder, dev sign-in, canned model answer, maps off,
"today" before the sample trip), on PERF_PORT (default 5020), wrapped in a timing layer that is NOT part of the app:
every request's server time (to the first response byte) and body size go to $PERF_LOG as JSON lines, and to a Server-Timing header.

    PERF_LOG=/tmp/x/server.jsonl python scripts/perf/serve.py
"""
import json
import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

os.environ["GITAWAY_DATA_DIR"] = os.environ.get("PERF_DATA") or tempfile.mkdtemp(prefix="ga-perf-data-")
os.environ["GITAWAY_DEV_LOGIN"] = "1"
os.environ["DB_TYPE"] = "SQLITE"
os.environ["DB_NAME"] = "app_host"
for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_VERSION",
          "AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "SARVAM_API_KEY", "GITAWAY_AI_TRANSCRIBE_PROVIDER", "GITAWAY_SHOWCASE", "GITAWAY_VAPID_PUBLIC",
          "GITAWAY_VAPID_PRIVATE", "GITAWAY_VAPID_SUBJECT", "GITAWAY_ENV"):
    os.environ[k] = ""
for k in [k for k in os.environ if k.startswith("GITAWAY_AI_")]:
    os.environ[k] = ""

import uvicorn  # noqa: E402

from main import app  # noqa: E402
from gitaway import ai, catalog, geo  # noqa: E402
from tests import canvas_samples as samples  # noqa: E402

# the same canned world the browser tests use
os.environ["AZURE_OPENAI_API_KEY"] = "k"
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://example.openai.azure.com"
os.environ["AZURE_OPENAI_DEPLOYMENT"] = "gpt-test"
ai.TRANSPORT = samples.FakeAzure()


def _refuse(url, timeout=0):
    raise OSError("the network is off while measuring")


geo.fetch = _refuse
geo.ASYNC = False
catalog.today = lambda: date(2026, 9, 30)

LOG = open(os.environ.get("PERF_LOG", os.devnull), "a", buffering=1)


def timed(inner):
    async def wrap(scope, receive, send):
        if scope["type"] != "http":
            return await inner(scope, receive, send)
        t0 = time.perf_counter()
        st = {"ttfb": None, "bytes": 0, "status": 0}

        async def snd(msg):
            if msg["type"] == "http.response.start":
                st["ttfb"] = (time.perf_counter() - t0) * 1000
                st["status"] = msg["status"]
                msg = dict(msg)
                msg["headers"] = list(msg.get("headers", [])) + [(b"server-timing", f"app;dur={st['ttfb']:.1f}".encode())]
            elif msg["type"] == "http.response.body":
                st["bytes"] += len(msg.get("body", b""))
            await send(msg)

        await inner(scope, receive, snd)
        q = scope.get("query_string", b"").decode()
        LOG.write(json.dumps({"at": time.time(), "method": scope["method"], "path": scope["path"] + ("?" + q if q else ""), "status": st["status"],
                              "ms": round(st["ttfb"] or 0, 1), "total_ms": round((time.perf_counter() - t0) * 1000, 1), "bytes": st["bytes"]}) + "\n")
    return wrap


if __name__ == "__main__":
    uvicorn.run(timed(app), host="127.0.0.1", port=int(os.environ.get("PERF_PORT", "5020")), log_level="warning")
