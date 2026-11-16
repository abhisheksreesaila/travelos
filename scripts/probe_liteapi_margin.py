"""Prove the margin end to end on the sandbox (F-274 review): `pixi run python scripts/probe_liteapi_margin.py --out FILE [--env PATH]`.

One stay search with `margin: 16` (what a live search carries), then a prebook (`usePaymentSdk: true`) of the cheapest offer of each of the first hotels. For each it records the price the
square shows (`suggestedSellingPrice`), the retail rate the search gave, and the prebook's `price` and `sellingPriceToUser`: the price charged is the price shown if they are equal.
Only numbers and hotel ids are written (no key, no `secretKey`, no offer id). The key is read from the environment (or the .env file given), never printed; a non-sandbox key is refused.
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

SEARCH = "https://api.liteapi.travel/v3.0/hotels/rates"
PREBOOK = "https://book.liteapi.travel/v3.0/rates/prebook"
MARGIN = 16


def post(key, url, body):
    time.sleep(2)      # the sandbox answers 429 to a burst
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={"X-API-Key": key, "Accept": "application/json", "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=130)      # noqa: S310
        return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--env", default=".env")
    a = ap.parse_args()
    key = os.environ.get("LITEAPI_KEY", "")
    if not key and Path(a.env).exists():
        key = next((line.split("=", 1)[1].strip().strip("\"'") for line in Path(a.env).read_text().splitlines() if line.startswith("LITEAPI_KEY=")), "")
    if not key.startswith("sand_"):
        sys.exit("a sandbox key (sand_...) is required")
    start = date.today() + timedelta(days=30)
    search = {"cityName": "San Diego", "countryCode": "US", "checkin": start.isoformat(), "checkout": (start + timedelta(days=3)).isoformat(), "currency": "USD",
              "guestNationality": "US", "occupancies": [{"adults": 2, "children": [7, 10]}], "limit": 8, "timeout": 10, "maxRatesPerHotel": 1, "margin": MARGIN}
    status, found = post(key, SEARCH, search)
    rows = []
    for h in (found.get("data") or [])[:6]:
        rt = h["roomTypes"][0]
        rate = rt["rates"][0]
        shown = (rt.get("suggestedSellingPrice") or {}).get("amount")
        status, pre = post(key, PREBOOK, {"offerId": rt["offerId"], "usePaymentSdk": True})
        d = pre.get("data") or {}
        row = {"hotelId": h["hotelId"], "shown": shown, "retail": rate["retailRate"]["total"][0]["amount"], "prebook_price": d.get("price"), "pays": d.get("sellingPriceToUser"), "prebook_status": status}
        rows.append(row)
        print(row)
    Path(a.out).write_text(json.dumps({"margin": MARGIN, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
