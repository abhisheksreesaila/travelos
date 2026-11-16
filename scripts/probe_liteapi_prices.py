"""One real LiteAPI hotel-rates search, to compare the prices we could show: `pixi run python scripts/probe_liteapi_prices.py [--env PATH] [--city NAME --country CC] [--days N] [--nights N]`.

Reads LITEAPI_KEY from the environment, or from the env file given (never printed, scrubbed from any error). Says whether the key is a sandbox or a live one
by its prefix. POSTs /hotels/rates (one room, 2 adults and kids 7 and 10, N days out, one rate a hotel) and prints, for the cheapest hotels, the retail
rate (what the matrix shows today, `offerRetailRate`), the suggested selling price (`suggestedSellingPrice`, the public price), taxes and fees not
included, and whether the rate is refundable: the numbers the live-prices brief (docs/briefs/live-liteapi.md) compares with the big sites.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://api.liteapi.travel/v3.0/hotels/rates"


def load_key(env_path):
    if os.environ.get("LITEAPI_KEY"):
        return
    for line in Path(env_path).read_text().splitlines() if env_path else ():
        if line.startswith("LITEAPI_KEY="):
            os.environ["LITEAPI_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")


def money(p):
    p = p[0] if isinstance(p, list) and p else p
    return f"{p.get('amount')} {p.get('currency')}" if isinstance(p, dict) else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env")
    ap.add_argument("--city", default="San Diego")
    ap.add_argument("--country", default="US")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--nights", type=int, default=3)
    ap.add_argument("--show", type=int, default=6)
    a = ap.parse_args()
    load_key(a.env)
    key = os.environ.get("LITEAPI_KEY", "").strip()
    if not key:
        sys.exit("no LITEAPI_KEY")
    print("key:", "sandbox" if key.startswith("sand_") else "live")
    checkin = date.today() + timedelta(days=a.days)
    body = {"cityName": a.city, "countryCode": a.country, "checkin": checkin.isoformat(), "checkout": (checkin + timedelta(days=a.nights)).isoformat(),
            "currency": "USD", "guestNationality": "US", "occupancies": [{"adults": 2, "children": [7, 10]}], "limit": 30, "timeout": 8, "maxRatesPerHotel": 1}
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"X-API-Key": key, "Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            answer = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read()[:300].decode(errors='replace').replace(key, '***')}")
    except Exception as e:      # noqa: BLE001
        sys.exit(str(e).replace(key, "***"))
    names = {h.get("id"): h.get("name") for h in answer.get("hotels") or () if isinstance(h, dict)}
    rows = []
    for h in answer.get("data") or ():
        for rt in h.get("roomTypes") or ():
            rate = next(iter(rt.get("rates") or ()), {}) or {}
            fees = [f for f in (rate.get("retailRate") or {}).get("taxesAndFees") or () if isinstance(f, dict)]
            retail = rt.get("offerRetailRate") or {}
            ssp = rt.get("suggestedSellingPrice") or (rate.get("retailRate") or {}).get("suggestedSellingPrice")
            rows.append((float((retail or {}).get("amount") or 0), names.get(h.get("hotelId"), h.get("hotelId")), money(retail), money(ssp),
                         ", ".join(f"{f.get('description') or 'fee'} {f.get('amount')} {'in' if f.get('included') else 'NOT in'}" for f in fees) or "-",
                         (rate.get("cancellationPolicies") or {}).get("refundableTag")))
            break
    rows.sort()
    print(f"{a.city}, {checkin} for {a.nights} nights, 2 adults + 2 kids: {len(rows)} hotels priced")
    for _, name, retail, ssp, fees, rfn in rows[:a.show]:
        print(f"- {name}\n    retail (shown today): {retail} | public (suggested selling): {ssp} | {rfn}\n    taxes and fees: {fees}")


if __name__ == "__main__":
    main()
