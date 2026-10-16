"""F-172: how long N day fragments take when they arrive together, against one alone (in process, no network).
The host-lock pile-up showed here: two prefetches at once took 150-230 ms each where one alone took 30-50.

    python scripts/perf/concurrent_server.py /tmp/x/data-phone-cpu4-lat180 /tmp/x/state-phone-cpu4-lat180.json [N=2]
"""
import json
import os
import re
import shutil
import statistics
import sys
import tempfile
import threading
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
src, state = sys.argv[1], sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 2
data = tempfile.mkdtemp(prefix="ga-perf-conc-")
shutil.copytree(src, data, dirs_exist_ok=True)
os.environ.update(GITAWAY_DATA_DIR=data, GITAWAY_DEV_LOGIN="1", DB_TYPE="SQLITE", DB_NAME="app_host")
for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "AZURE_OPENAI_API_KEY", "GITAWAY_SHOWCASE", "GITAWAY_ENV", "GITAWAY_VAPID_PUBLIC", "GITAWAY_VAPID_PRIVATE"):
    os.environ[k] = ""

from starlette.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from gitaway import catalog, geo  # noqa: E402

catalog.today = lambda: date(2026, 9, 30)
geo.fetch = lambda url, timeout=0: (_ for _ in ()).throw(OSError("off"))
geo.ASYNC = False

cookies = json.load(open(state))["cookies"]


def client():
    c = TestClient(app, base_url="http://127.0.0.1:5020")
    for ck in cookies:
        c.cookies.set(ck["name"], ck["value"])
    return c


H = {"X-Canvas": "1"}
clients = [client() for _ in range(N)]
week = clients[0].get("/trip/canvas?frag=1", headers=H).text
trip = re.search(r"trip=([0-9a-f]+)", week).group(1)
urls = [f"/trip/canvas?day={d}&trip={trip}&frag=1" for d in range(N)]


def timed(c, u, out, i):
    t = time.perf_counter()
    c.get(u, headers=H)
    out[i] = (time.perf_counter() - t) * 1000


alone, together = [], []
for _ in range(10):
    out = [0]
    timed(clients[0], urls[0], out, 0)
    alone.append(out[0])
    out = [0] * N
    ts = [threading.Thread(target=timed, args=(clients[i], urls[i], out, i)) for i in range(N)]
    t0 = time.perf_counter()
    [t.start() for t in ts]
    [t.join() for t in ts]
    together.append((time.perf_counter() - t0) * 1000)
a, b = statistics.median(alone), statistics.median(together)
print(f"one alone: {a:.0f} ms median; {N} together (wall time until all are done): {b:.0f} ms median; ratio {b / a:.2f}")
shutil.rmtree(data, ignore_errors=True)
