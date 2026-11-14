"""Record one real LiteAPI sandbox booking (F-233): `pixi run python scripts/probe_liteapi_book.py --out DIR [--env PATH]`.

Reads LITEAPI_KEY from the environment or the .env file given (never printed; scrubbed from any answer). Refuses a key that does not start with `sand_`.
Makes six polite calls: a stay search (San Diego, about a month out, 3 nights, 2 adults and kids 7 and 10, 5 hotels), a prebook, a book with the sandbox's
`ACC_CREDIT_CARD` and a made-up guest, the same book again (the idempotency answer), a prebook of a made-up offer id, and a book with a bad email.
Writes each answer as <out>/<name>.json ({status, body}). The guest is made up (example.com): no real person's data is ever sent.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

SEARCH = "https://api.liteapi.travel/v3.0/hotels/rates"
BOOK = "https://book.liteapi.travel/v3.0"


def load_key(env_path):
    if os.environ.get("LITEAPI_KEY"):
        return os.environ["LITEAPI_KEY"]
    for line in Path(env_path).read_text().splitlines() if env_path else ():
        if line.startswith("LITEAPI_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def call(key, url, body, name, out):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"X-API-Key": key, "Accept": "application/json", "Content-Type": "application/json"}, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=130)      # noqa: S310
        status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    text = raw.decode("utf-8", "replace").replace(key, "[key]")
    try:
        doc = json.loads(text)
    except ValueError:
        doc = {"raw": text[:500]}
    (out / f"{name}.json").write_text(json.dumps({"status": status, "body": doc}, indent=1))
    print(name, status, len(raw), "bytes")
    return status, doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--env", default=".env")
    a = ap.parse_args()
    key = load_key(a.env)
    if not key.startswith("sand_"):
        sys.exit("a sandbox key (sand_...) is required")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    start = date.today() + timedelta(days=30)
    search = {"cityName": "San Diego", "countryCode": "US", "checkin": start.isoformat(), "checkout": (start + timedelta(days=3)).isoformat(), "currency": "USD",
              "guestNationality": "US", "occupancies": [{"adults": 2, "children": [7, 10]}], "limit": 5, "timeout": 10, "maxRatesPerHotel": 1}
    _, found = call(key, SEARCH, search, "hotel_rates", out)
    offer = found["data"][0]["roomTypes"][0]["offerId"]
    _, pre = call(key, BOOK + "/rates/prebook", {"offerId": offer, "usePaymentSdk": False}, "prebook", out)
    guest = {"firstName": "Test", "lastName": "Traveler", "email": "test.traveler@example.com"}
    book = {"prebookId": pre["data"]["prebookId"], "clientReference": "gitaway-probe-f233", "holder": guest, "payment": {"method": "ACC_CREDIT_CARD"},
            "guests": [{"occupancyNumber": 1, **guest}]}
    call(key, BOOK + "/rates/book", book, "book", out)
    call(key, BOOK + "/rates/book", book, "book_again", out)
    call(key, BOOK + "/rates/prebook", {"offerId": "not-an-offer", "usePaymentSdk": False}, "prebook_bad_offer", out)
    call(key, BOOK + "/rates/book", {**book, "clientReference": "gitaway-probe-f233-b", "holder": {**guest, "email": "nope"}}, "book_bad_email", out)


if __name__ == "__main__":
    main()
