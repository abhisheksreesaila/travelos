"""Record one real streamed LiteAPI flight search (F-229): `pixi run python scripts/probe_liteapi_stream.py [--env PATH] [--out PATH] [--seconds N]`.

Reads LITEAPI_KEY from the environment, or from the .env file given (never printed, scrubbed from any error). POSTs /flights/rates with
`Accept: text/event-stream` (SFO to SAN and back, about a month out, 2 adults and kids 7 and 10, only the cheapest offer per journey) and reads the
events for up to N seconds (default 30), printing when each arrived and how many journeys it held. With --out, writes the stream trimmed to a sane size
(the first TRIM journeys of each chunk, plus that chunk's cheapest) as an SSE file, and the arrival times beside it as <out>.times.json.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

TRIM = 3
API = "https://api.liteapi.travel/v3.0/flights/rates"


def load_key(env_path):
    if os.environ.get("LITEAPI_KEY"):
        return
    for line in Path(env_path).read_text().splitlines() if env_path else ():
        if line.startswith("LITEAPI_KEY="):
            os.environ["LITEAPI_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")


def trimmed(payload):
    """The chunk with only its first TRIM journeys and its cheapest one: the same shape, smaller."""
    try:
        doc = json.loads(payload)
    except ValueError:
        return payload
    for day in doc.get("data") or () if isinstance(doc, dict) else ():
        js = day.get("journeys") if isinstance(day, dict) else None
        if isinstance(js, list) and len(js) > TRIM:
            def total(j):
                try:
                    return j["cheapestOffer"]["pricing"]["display"]["total"]
                except (KeyError, TypeError):
                    return float("inf")
            cheapest = min(js, key=total)
            keep = js[:TRIM] + ([cheapest] if cheapest not in js[:TRIM] else [])
            for j in keep:
                if isinstance(j.get("offers"), list):
                    j["offers"] = j["offers"][:1]
            day["journeys"] = keep
    return json.dumps(doc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args()
    load_key(a.env)
    key = os.environ.get("LITEAPI_KEY", "").strip()
    if not key:
        print("LITEAPI_KEY is not set (give --env PATH to a .env that has it; it is never printed).")
        return 1
    out_day = date.today() + timedelta(days=a.days)
    body = {"legs": [{"origin": "SFO", "destination": "SAN", "date": out_day.isoformat(), "direction": "OUTBOUND"},
                     {"origin": "SAN", "destination": "SFO", "date": (out_day + timedelta(days=4)).isoformat(), "direction": "INBOUND"}],
            "adults": 2, "children": 2, "childrenAges": [7, 10], "infants": 0, "infantAges": [], "currency": "USD", "country": "US",
            "filters": {"showCheapestOfferOnly": True}}
    req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST",
                                 headers={"X-API-Key": key, "Accept": "text/event-stream", "Content-Type": "application/json"})
    t0 = time.monotonic()
    events, msg, size = [], [], 0
    try:
        with urllib.request.urlopen(req, timeout=a.seconds) as r:     # noqa: S310 (a fixed https URL)
            print(f"HTTP {r.status} {r.headers.get('Content-Type')} at {time.monotonic() - t0:.1f} s")
            while time.monotonic() - t0 < a.seconds:
                line = r.readline()
                if not line:
                    print(f"the stream ended at {time.monotonic() - t0:.1f} s")
                    break
                size += len(line)
                line = line.decode("utf-8", "replace").rstrip("\r\n")
                if line:
                    msg.append(line)
                    continue
                if not msg:
                    continue
                ev = next((x[6:].strip() for x in msg if x.startswith("event:")), "")
                data = "\n".join(x[5:].lstrip() for x in msg if x.startswith("data:"))
                others = [x[:40] for x in msg if not x.startswith(("event:", "data:"))]
                at = time.monotonic() - t0
                try:
                    doc = json.loads(data) if data else None
                    n = sum(len(d.get("journeys") or ()) for d in doc.get("data") or ()) if isinstance(doc, dict) else 0
                    keys = sorted(doc)[:8] if isinstance(doc, dict) else type(doc).__name__
                    low = min((j["cheapestOffer"]["pricing"]["display"]["total"] for d in doc["data"] for j in d.get("journeys") or ()), default=None)
                except (ValueError, AttributeError, TypeError, KeyError):
                    n, keys, low = 0, "not JSON", None
                print(f"{at:6.1f} s  event={ev or '-':16} journeys={n:4}  cheapest={low}  bytes={len(data):9}  keys={keys}  other={others}")
                events.append((at, ev, data, others))
                msg = []
                if ev == "rates-complete":
                    break
    except Exception as e:
        print(f"stopped: {type(e).__name__}: {str(e).replace(key, '[key]')}")
    print(f"{len(events)} events, {size} bytes in {time.monotonic() - t0:.1f} s")
    if a.out and events:
        out = Path(a.out)
        lines = []
        for _, ev, data, others in events:
            lines += [*others, *([f"event: {ev}"] if ev else []), *([f"data: {trimmed(data)}"] if data else []), ""]
        out.write_text("\n".join(lines) + "\n")
        out.with_suffix(out.suffix + ".times.json").write_text(json.dumps([{"at": round(at, 1), "event": ev} for at, ev, _, _ in events], indent=1) + "\n")
        print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
