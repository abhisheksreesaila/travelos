"""A real Around you search, by hand (not part of the test suite): `pixi run python -m gitaway.around_smoke [lat lon]`.

Asks the real Overpass API for vegetarian food and restrooms near a point (default: Disneyland, 33.8121, -117.9190), then, when the Azure deployment in the
environment (.env) is set, asks the model to rank the vegetarian candidates. Prints only counts and times: how many places came back, how many were inside the radius,
how many the model picked, how many of its picks were on the list, and the seconds each step took. It prints no place name, no answer text and never the key.
The model call is logged to a throwaway database in a temporary folder, not to the app's own.
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

DISNEYLAND = (33.8121, -117.9190)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    lat, lon = (float(argv[0]), float(argv[1])) if len(argv) >= 2 else DISNEYLAND
    os.environ.setdefault("DB_TYPE", "SQLITE")
    os.environ["DB_NAME"] = "smoke_host"
    folder = tempfile.mkdtemp(prefix="gitaway-smoke-")
    os.chdir(folder)
    try:
        from gitaway import ai, around

        failed = 0
        for cat in ("veg", "wc"):
            start = time.monotonic()
            try:
                found = around.places_near(cat, lat, lon, around.WALK_M, pref=True)
            except around.AroundError as e:
                print(f"{cat}: Overpass failed after {time.monotonic() - start:.1f} s: {e}")
                failed = 2
                continue
            took = time.monotonic() - start
            inside = sum(1 for p in found if around.metres(lat, lon, p["lat"], p["lon"]) <= around.WALK_M * 1.05)
            with_hours = sum(1 for p in found if p["hours"])
            with_phone = sum(1 for p in found if p["phone"])
            print(f"{cat}: overpass took={took:.1f}s places={len(found)} inside_radius={inside} with_hours={with_hours} with_phone={with_phone}")
            if cat == "veg":
                veg = found
        if failed or not veg:
            return failed or 1
        if not ai.configured("around-you"):
            print("The assistant is not configured (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT); skipping the ranking.")
            return 0
        now = around.now_in("America/Los_Angeles")
        cands = around.by_distance([dict(p, m=around.metres(lat, lon, p["lat"], p["lon"]), open=around.open_now(p["hours"], now)) for p in veg])[: around.CANDIDATES]
        start = time.monotonic()
        try:
            picks = around.ask_ai("veg", True, cands, "smoke")
        except ai.AIError as e:
            print(f"ranking failed after {time.monotonic() - start:.1f} s: {e}")
            return 2
        took = time.monotonic() - start
        row = (ai.usage_rows() or [{}])[-1]
        print(f"ranking: deployment={ai.deployment('around-you')} took={took:.1f}s candidates={len(cands)} picks={len(picks)} on_the_list={sum(1 for i, _ in picks if 0 <= i < len(cands))} "
              f"with_a_reason={sum(1 for _, why in picks if why)} tokens_in={row.get('tokens_in', '?')} tokens_out={row.get('tokens_out', '?')}")
        return 0
    finally:
        os.chdir(Path(__file__).resolve().parent)
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
