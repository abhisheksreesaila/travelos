"""Real "speak" calls to the model, by hand (not part of the test suite): `pixi run python -m gitaway.speak_smoke ["request" ...]`.

Shows the model a canned Saturday (lunch, an observatory visit, a Disneyland block with Soarin' in it; it is 2:00 PM) with the real Azure deployment from the
environment (.env), asks the two default requests (or the ones given), checks each answer with the app's own validation, and prints only the kinds and counts of
the operations, how many were kept and dropped, and the time taken. It prints no text from the day or the answer, and never the key. The calls are logged to a
throwaway database in a temporary folder, not to the app's own.

The canned day is built by `speak.make_day`, the same builder the app uses, and tests/test_speak.py checks it has every key `validate` needs.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

REQUESTS = ("We're tired, block the next two hours and move lunch to 12:30",
            "Add Bhoomija and Hrishi to Soarin and move the observatory to tomorrow at 10")


def canned_day():
    """A day shaped like speak.read_day's, with no database behind it: Saturday of the sample trip, 2:00 PM."""
    from gitaway import speak, tripcal as cal

    def plan(id_, start, end, title, kind="fun"):
        return {"act_id": id_, "day": 1, "start_min": int(start * 60), "end_min": int(end * 60), "title": title, "kind": kind, "seq": int(id_[1:])}
    plans = {p["act_id"]: p for p in (plan("a1", 12, 13, "Lunch", "food"), plan("a2", 15, 17, "Griffith Observatory", "culture"), plan("a3", 9, 21, "Disneyland"))}
    parts = {"p1": {"id": "p1", "act_id": "a3", "name": "Morning"}, "p2": {"id": "p2", "act_id": "a3", "name": "Afternoon"}}

    def step(id_, part, pos, title, time_, who):
        return {"id": id_, "act_id": "a3", "part_id": part, "position": pos, "title": title, "time": time_, "who": json.dumps(who), "note": "", "done": 0, "aside": 0}
    steps = {x["id"]: x for x in (step("s1", "p1", 0, "Soarin' Around the World", "09:30", ["m:u1"]), step("s2", "p1", 1, "Space Mountain", "10:30", []), step("s3", "p2", 0, "Haunted Mansion", "", []))}
    people = [{"user_id": "u1", "name": "Abhi Rivera"}, {"user_id": "u2", "name": "Bhoomija Rao"}, {"user_id": "u3", "name": "Hrishi Rivera"}]
    t = cal.trip("")
    return speak.make_day(t, 1, "America/Los_Angeles", [], [], plans, parts, steps, {}, people, when=("during", 1, 14 * 60))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    os.environ.setdefault("DB_TYPE", "SQLITE")
    os.environ["DB_NAME"] = "smoke_host"
    folder = tempfile.mkdtemp(prefix="gitaway-smoke-")
    os.chdir(folder)
    try:
        from gitaway import ai, speak
        if not ai.configured("speak"):
            print("The assistant is not configured (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT).")
            return 1
        ctx = canned_day()
        failed = 0
        for request in argv or REQUESTS:
            user = json.dumps({"day": speak.context_for(ctx), "request": request}, ensure_ascii=False)
            start = time.monotonic()
            try:
                answer = ai.call_json("speak", "smoke", speak.SYSTEM, user, speak.SCHEMA, name="day_change")
            except ai.AIError as e:
                print(f"Speak failed after {time.monotonic() - start:.1f} s: {e}")
                failed = 2
                continue
            took = time.monotonic() - start
            ops, dropped = speak.validate(ctx, answer.get("ops"))
            row = (ai.usage_rows() or [{}])[-1]
            asked = Counter(o.get("op") for o in answer.get("ops") or [] if isinstance(o, dict))
            kept = Counter(o["op"] for o in ops)
            print(f"deployment={ai.deployment('speak')} took={took:.1f}s asked={dict(sorted(asked.items()))} kept={dict(sorted(kept.items()))} dropped={len(dropped)} "
                  f"tokens_in={row.get('tokens_in', '?')} tokens_out={row.get('tokens_out', '?')}")
        return failed
    finally:
        os.chdir(Path(__file__).resolve().parent)
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
