"""Record one real Overpass answer per hotel for the aerial view's tests and the showcase (F-284): `pixi run python scripts/record_aerial_fixture.py`.

Asks the two hotels of gitaway/aerial.py SAMPLES (Hilton Los Angeles Airport, Hyatt Regency Lake Tahoe) through the app's own `aerial.ask` (the same query, the fixed hosts, a generic
User-Agent: no person's address) and keeps the answer in tests/fixtures/aerial/<file> with the date it was read. Overpass is keyless; two polite calls, one hotel after the other.
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gitaway import aerial  # noqa: E402


def main():
    aerial.HOST_TIMEOUT = 45.0      # the page gives a host 8 s; a recording may wait for a busy one
    out = aerial.FIXTURES
    out.mkdir(parents=True, exist_ok=True)
    for name, lat, lon, file in aerial.SAMPLES.values():
        got = aerial.ask(lat, lon)
        if not got:
            print(f"{name}: no host gave a whole answer; nothing kept")
            continue
        data, host = got
        (out / file).write_text(json.dumps({"name": name, "lat": lat, "lon": lon, "recorded": date.today().isoformat(), "host": host, "data": data}, separators=(",", ":")))
        print(f"{name}: {len(data['elements'])} elements from {host} -> {out / file}")
        time.sleep(2)


if __name__ == "__main__":
    main()
