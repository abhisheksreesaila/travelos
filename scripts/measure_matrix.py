"""How fast the trip matrix fills against LiteAPI's sandbox (F-229): `pixi run python scripts/measure_matrix.py --env PATH [--days 45] [--runs 1]`.

Starts this checkout's app on a free local port off the showcase (a throwaway data folder, LITEAPI_KEY read from the .env given and never printed), opens
/plan/matrix in headless Chromium at 1440x900 for SFO to San Diego, 2 adults and kids 7 and 10, `--days` from today (each run a day later, so LiteAPI's
own cache does not flatter it), and prints the seconds from navigation to: the asked square's total, the asked day's column (every place on that start
day), and every other square in view, each with its status. The targets (F-229): the asked square within 10 s, the column within 20 s.
"""
import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
WATCH = """() => {
  window.__landed = {};
  const t0 = performance.timeOrigin;
  const look = () => document.querySelectorAll('.mx-lane .mx-sq[data-sq]').forEach(e => {
    const k = e.dataset.sq;
    if (!window.__landed[k] && !e.classList.contains('is-wait')) window.__landed[k] = [performance.now() / 1000, e.classList.contains('is-ok') ? 'ok' : e.textContent.trim()];
  });
  new MutationObserver(look).observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'] });
  look();
}"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def key_from(env_path):
    for line in Path(env_path).read_text().splitlines():
        if line.startswith("LITEAPI_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--days", type=int, default=45)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--wait", type=float, default=60)
    a = ap.parse_args()
    k = key_from(a.env)
    if not k:
        print("no LITEAPI_KEY in that file")
        return 1
    port, data = free_port(), tempfile.mkdtemp(prefix="gitaway-measure-", dir=os.environ.get("TMPDIR"))
    env = {**os.environ, "LITEAPI_KEY": k, "GITAWAY_SHOWCASE": "0", "GITAWAY_DATA_DIR": data, "MET_NORWAY_TERMS_ACCEPTED": ""}
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
                              cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(100):
            try:
                urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for run in range(a.runs):
                d = date.today() + timedelta(days=a.days + run)
                url = f"http://127.0.0.1:{port}/plan/matrix?to=San+Diego&home=SFO&d={d}&r={d + timedelta(days=4)}&a=2&k=7,10&x=2"
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.add_init_script(f"document.addEventListener('DOMContentLoaded', {WATCH})")
                page.goto(url)
                asked = f"sandiego|{d}"
                column = [f"{lane}|{d}" for lane in ("sandiego", "losangeles", "orangecounty", "losangeles+sandiego", "orangecounty+sandiego")]
                end = time.monotonic() + a.wait
                while time.monotonic() < end:
                    landed = page.evaluate("window.__landed || {}")
                    if all(c in landed for c in column) and page.evaluate("document.getElementById('mx').dataset.busy") == "0":
                        break
                    time.sleep(0.25)
                landed = page.evaluate("window.__landed || {}")
                print(f"run {run + 1}: start {d}")
                at = landed.get(asked)
                print(f"  asked square: {at[0]:.1f} s ({at[1]})" if at else "  asked square: not landed")
                col = [landed[c][0] for c in column if c in landed]
                print(f"  asked day's column: {max(col):.1f} s, {len(col)} of {len(column)} landed" if col else "  asked day's column: none landed")
                for sq, (t, how) in sorted(landed.items(), key=lambda x: x[1][0]):
                    print(f"    {t:5.1f} s  {sq:36} {how}")
                page.close()
            browser.close()
    finally:
        server.terminate()
        try:
            out = server.communicate(timeout=10)[0]
        except subprocess.TimeoutExpired:
            server.kill()
            out = server.communicate()[0]
        warnings = [ln.replace(k, "[key]") for ln in (out or "").splitlines() if "LiteAPI" in ln or "429" in ln]
        if warnings:
            print("server said:\n  " + "\n  ".join(warnings[-20:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
