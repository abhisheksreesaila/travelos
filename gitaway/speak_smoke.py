"""One real "speak" call to the model, by hand (not part of the test suite): `pixi run python -m gitaway.speak_smoke ["request"]`.

Shows the model a canned Saturday (lunch, an observatory visit, dinner; it is 2:00 PM) with the real Azure deployment from the environment (.env) and the request
"We're tired, block the next two hours and move lunch to 12:30" (or the one given), checks the answer with the app's own validation, and prints only the kinds
and counts of the operations, how many were kept, and the time taken. It prints no text from the day or the answer, and never the key. The call is logged to a
throwaway database in a temporary folder, not to the app's own.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

REQUEST = "We're tired, block the next two hours and move lunch to 12:30"


def _canned(speak, cal):
    """A day shaped like speak.read_day's, with no database behind it."""
    def plan(id_, start, end, title):
        return {"act_id": id_, "day": 1, "start_min": start * 60, "end_min": end * 60, "title": title, "kind": "fun", "seq": int(id_[1:])}
    plans = {p["act_id"]: p for p in (plan("a1", 12, 13, "Lunch"), plan("a2", 15, 17, "Griffith Observatory"), plan("a3", 18.5, 20, "Dinner at Green Leaf Kitchen"))}
    for p in plans.values():
        p["start_min"], p["end_min"] = int(p["start_min"]), int(p["end_min"])
    t = cal.trip("")
    from datetime import timedelta
    return {"t": t, "day": 1, "date": t.depart + timedelta(days=1), "zone": "America/Los_Angeles", "blocks": [], "booked": [], "past": False, "now": 14 * 60,
            "plans": plans, "parts": {}, "steps": {}, "notes": {}, "people": [{"user_id": "u1", "name": "Abhi Rivera"}, {"user_id": "u2", "name": "Bhoomija Rao"}], "n_days": 5}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    os.environ.setdefault("DB_TYPE", "SQLITE")
    os.environ["DB_NAME"] = "smoke_host"
    folder = tempfile.mkdtemp(prefix="gitaway-smoke-")
    os.chdir(folder)
    try:
        from gitaway import ai, speak, tripcal as cal
        if not ai.configured("speak"):
            print("The assistant is not configured (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT).")
            return 1
        ctx = _canned(speak, cal)
        user = json.dumps({"day": speak.context_for(ctx), "request": argv[0] if argv else REQUEST}, ensure_ascii=False)
        start = time.monotonic()
        try:
            answer = ai.call_json("speak", "smoke", speak.SYSTEM, user, speak.SCHEMA, name="day_change")
        except ai.AIError as e:
            print(f"Speak failed after {time.monotonic() - start:.1f} s: {e}")
            return 2
        took = time.monotonic() - start
        ops, dropped = speak.validate(ctx, answer.get("ops"))
        row = (ai.usage_rows() or [{}])[-1]
        asked = Counter(o.get("op") for o in answer.get("ops") or [] if isinstance(o, dict))
        kept = Counter(o["op"] for o in ops)
        print(f"deployment={ai.deployment('speak')} took={took:.1f}s asked={dict(sorted(asked.items()))} kept={dict(sorted(kept.items()))} dropped={len(dropped)} "
              f"tokens_in={row.get('tokens_in', '?')} tokens_out={row.get('tokens_out', '?')}")
        return 0
    finally:
        os.chdir(Path(__file__).resolve().parent)
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
