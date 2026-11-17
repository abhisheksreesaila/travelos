"""The 2026-11-17 overnight checker (docs/overnight-goal-2026-11-17.md): PASS or FAIL per milestone. `pixi run python scripts/check_overnight2.py [M1 ...]`."""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = {**os.environ, "TMPDIR": os.environ.get("TMPDIR") or str(Path.home() / ".cache" / "check2-tmp")}
Path(ENV["TMPDIR"]).mkdir(parents=True, exist_ok=True)
PLAN = (ROOT / "docs/plan.md").read_text()
WALK = ROOT / "docs/report/journey-2026-11-17.md"
BROWSER = ["test_harbour.py", "test_aerial.py", "test_tripmatrix.py", "test_tripview.py", "test_matrix_v3.py", "test_rail_extra.py"]


def done(ticket):
    return bool(re.search(rf"^## {ticket} .*\[done\]", PLAN, re.M))


def run(*cmd):
    return subprocess.run(cmd, cwd=ROOT, env=ENV, capture_output=True, text=True).returncode == 0


def browser_green():
    extra = [ln.strip() for ln in (ROOT / "docs/report/touched-browser-2026-11-17.txt").read_text().splitlines() if ln.strip()] if (ROOT / "docs/report/touched-browser-2026-11-17.txt").exists() else []
    files = [f for f in dict.fromkeys(BROWSER + extra) if (ROOT / "tests_browser" / f).exists()]
    return all(run("python", "-m", "pytest", "-q", "-p", "no:randomly", f"tests_browser/{f}") for f in files)


CHECKS = {
    "M1": lambda: done("F-286"),
    "M2": lambda: done("F-282"),
    "M3": lambda: done("F-283"),
    "M4": lambda: WALK.exists() and len(list((ROOT / "docs/report/journey-2026-11-17").glob("*.png"))) >= 16,
    "M5": lambda: WALK.exists() and WALK.read_text().count("[x] fixed") >= 6,
    "M6": lambda: run("pytest", "-q", "-p", "no:randomly", "tests") and browser_green(),
    "M7": lambda: (ROOT / "docs/report/overnight-2026-11-17.md").exists(),
}

if __name__ == "__main__":
    bad = 0
    for m in sys.argv[1:] or list(CHECKS):
        ok = CHECKS[m]()
        bad += not ok
        print(f"{m}: {'PASS' if ok else 'FAIL'}", flush=True)
    sys.exit(1 if bad else 0)
