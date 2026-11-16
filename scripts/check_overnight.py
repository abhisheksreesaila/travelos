"""The overnight run's checker (docs/overnight-goal.md): prints PASS or FAIL per milestone. `pixi run python scripts/check_overnight.py [M1 M2 ...]`."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = {**os.environ, "TMPDIR": os.environ.get("TMPDIR") or str(Path.home() / ".cache" / "check-tmp")}
Path(ENV["TMPDIR"]).mkdir(parents=True, exist_ok=True)


def run(*cmd):
    return subprocess.run(cmd, cwd=ROOT, env=ENV, capture_output=True, text=True).returncode == 0


def pytest_k(path, k):
    return run("pytest", "-q", "-p", "no:randomly", path, "-k", k)


CHECKS = {
    "M1": lambda: pytest_k("tests", "place_only or F268 or f268"),
    "M2": lambda: pytest_k("tests", "plan_this_trip_after_save or F269 or f269"),
    "M3": lambda: pytest_k("tests", "no_google_fonts or F270 or f270"),
    "M4": lambda: run("pytest", "-q", "--collect-only", "tests_browser"),
    "M5": lambda: run("pytest", "-q", "-x", "tests"),
    "M6": lambda: (ROOT / "docs/ship/live-prices.md").exists() and (ROOT / "scripts/railway_set_liteapi_key.sh").exists(),
}

if __name__ == "__main__":
    want = sys.argv[1:] or list(CHECKS)
    bad = 0
    for m in want:
        ok = CHECKS[m]()
        bad += not ok
        print(f"{m}: {'PASS' if ok else 'FAIL'}", flush=True)
    sys.exit(1 if bad else 0)
