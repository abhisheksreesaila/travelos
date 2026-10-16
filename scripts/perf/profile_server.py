"""F-168: where the server's time goes for the canvas's common requests, in process (no network): each route timed N times, then one cProfile of the day fragment.
Runs on a COPY of a seeded data folder (run_all.sh leaves $OUT/data-<tag>) with that run's signed-in cookie.

    python scripts/perf/profile_server.py /tmp/x/data-phone-cpu4-lat180 /tmp/x/state-phone-cpu4-lat180.json
"""
import cProfile
import io
import json
import os
import pstats
import re
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
src, state = sys.argv[1], sys.argv[2]
data = tempfile.mkdtemp(prefix="ga-perf-prof-")
shutil.copytree(src, data, dirs_exist_ok=True)
os.environ["GITAWAY_DATA_DIR"] = data
os.environ["GITAWAY_DEV_LOGIN"] = "1"
os.environ["DB_TYPE"] = "SQLITE"
os.environ["DB_NAME"] = "app_host"
for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "AZURE_OPENAI_API_KEY", "GITAWAY_SHOWCASE", "GITAWAY_ENV", "GITAWAY_VAPID_PUBLIC", "GITAWAY_VAPID_PRIVATE"):
    os.environ[k] = ""

from datetime import date  # noqa: E402

from starlette.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from gitaway import catalog, geo  # noqa: E402

catalog.today = lambda: date(2026, 9, 30)
geo.fetch = lambda url, timeout=0: (_ for _ in ()).throw(OSError("off"))
geo.ASYNC = False

from gitaway import familydb  # noqa: E402

COUNT = {"open": 0, "open_ms": 0.0}
_open = familydb.family_db


def counted_open(*a, **k):      # every opening of the family database (familydb.using and session.family come through here)
    COUNT["open"] += 1
    t = time.perf_counter()
    try:
        return _open(*a, **k)
    finally:
        COUNT["open_ms"] += (time.perf_counter() - t) * 1000


familydb.family_db = counted_open

c = TestClient(app, base_url="http://127.0.0.1:5020")
for ck in json.load(open(state))["cookies"]:
    c.cookies.set(ck["name"], ck["value"])
H = {"X-Canvas": "1"}
week = c.get("/trip/canvas?frag=1", headers=H).text
trip = re.search(r"trip=([0-9a-f]+)", week).group(1)
day = c.get(f"/trip/canvas?day=1&trip={trip}&frag=1", headers=H).text
act = re.search(r'card\?act=(a\d+)|data-act="(a\d+)"', day)
act = act.group(1) or act.group(2)
ROUTES = [("healthz (no session)", "/healthz", {}), ("week fragment", f"/trip/canvas?trip={trip}&frag=1", H), ("day fragment", f"/trip/canvas?day=1&trip={trip}&frag=1", H),
          ("day page (full document)", f"/trip/canvas?day=1&trip={trip}", {}), ("plan card", f"/trip/canvas/card?act={act}&trip={trip}", {}),
          ("plan in the panel (fragment)", f"/trip/canvas?day=1&plan={act}&trip={trip}&frag=1", H), ("Ask box fragment", "/trip/ask?day=1", {"X-Ask": "1"})]
print("| request | median ms | min ms | bytes | family db opened per request | ms spent opening it (median) |\n|---|---|---|---|---|---|")
for name, u, h in ROUTES:
    ts, n, opens, oms = [], 0, [], []
    for _ in range(15):
        COUNT.update(open=0, open_ms=0.0)
        t = time.perf_counter()
        r = c.get(u, headers=h)
        ts.append((time.perf_counter() - t) * 1000)
        n = len(r.content)
        opens.append(COUNT["open"])
        oms.append(COUNT["open_ms"])
    print(f"| {name} | {statistics.median(ts):.0f} | {min(ts):.0f} | {n} | {statistics.median(opens):.0f} | {statistics.median(oms):.0f} |")
for name, u, h in ROUTES[2:3] + ROUTES[4:5]:
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(10):
        c.get(u, headers=h)
    pr.disable()
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(12)
    print(f"\n--- profile: {name} x10 ---")
    print("\n".join(line for line in s.getvalue().splitlines() if line.strip())[:6000])
shutil.rmtree(data, ignore_errors=True)
