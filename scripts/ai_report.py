"""What the AI did (F-079): `pixi run ai-report [--data-dir DIR] [--since YYYY-MM-DD]`.

Counts, time and tokens per job and per day, read from the usage log in the host database (GITAWAY_DATA_DIR, or --data-dir). Read only: it
never opens the app, never prints a prompt, an answer or a name (the log holds none).
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir")
    ap.add_argument("--since", help="only calls on or after this day (YYYY-MM-DD)")
    args = ap.parse_args(argv)
    folder = (ROOT / (args.data_dir or os.getenv("GITAWAY_DATA_DIR", "data/db"))).resolve()
    host = folder / f"{os.getenv('DB_NAME', 'app_host')}.db"
    if not host.exists():
        print(f"No host database at {host}")
        return 1
    from gitaway import ai
    conn = sqlite3.connect(f"file:{host}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM ga_ai_usage WHERE day >= ? ORDER BY id", (args.since or "",))]
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    print(ai.format_report(ai.report(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
