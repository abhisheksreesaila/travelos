"""Record LiteAPI's flight booking path against the sandbox (F-276): `pixi run python scripts/probe_liteapi_flights.py --out DIR [--env PATH]`.

Reads LITEAPI_KEY from the environment (or the .env file given); it is never printed, and it and every `secretKey` are scrubbed from what is written. Refuses a key that does not
start with `sand_`. Polite calls only (2 s apart), all with made-up passengers (example.com): a round-trip search SFO ⇄ SAN (trimmed to a few journeys when written, the full
answer is megabytes), verify of the cheapest Nuitée Air offer (the sandbox's end-to-end airline, else the cheapest), a prebook with `usePaymentSdk: true` and its lookup, a
TRANSACTION_ID book of that unpaid transaction (the refusal), then a prebook without the SDK booked with the sandbox's own card (`ACC_CREDIT_CARD`, simulated, no charge), its
lookup, its cancel quote and its cancel, and the lookup of a booking that does not exist.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

HOSTS = ("https://api.liteapi.travel/v3.0", "https://book.liteapi.travel/v3.0")
SECRETS: list = []


def load_key(env_path):
    if os.environ.get("LITEAPI_KEY"):
        return os.environ["LITEAPI_KEY"]
    for line in Path(env_path).read_text().splitlines() if env_path and Path(env_path).exists() else ():
        if line.startswith("LITEAPI_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def scrub(text):
    for s in SECRETS:
        if s:
            text = text.replace(s, "[secret]")
    return text


def scrub_doc(v):
    if isinstance(v, dict):
        return {k: ("[secretKey]" if k in ("secretKey", "clientSecret") and isinstance(x, str) else scrub_doc(x)) for k, x in v.items()}
    if isinstance(v, list):
        return [scrub_doc(x) for x in v]
    return v


def call(key, method, url, body, name, out, keep=None):
    time.sleep(2)
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"X-API-Key": key, "Accept": "application/json", **({"Content-Type": "application/json"} if body is not None else {})})
    started = time.monotonic()
    try:
        r = urllib.request.urlopen(req, timeout=130)      # noqa: S310
        status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
        if status in (301, 302, 307, 308) and e.headers.get("Location"):
            where = urllib.parse.urljoin(url, e.headers["Location"])
            print("  ", name, "redirects to", where.split("?")[0])
            return call(key, method, where, body, name + "_followed", out, keep)
    except (urllib.error.URLError, TimeoutError) as e:
        print(name, "failed:", type(e).__name__)
        return 0, {}
    text = scrub(raw.decode("utf-8", "replace"))
    try:
        doc = json.loads(text)
    except ValueError:
        doc = {"raw": text[:800]}
    written = keep(doc) if keep else doc
    (out / f"{name}.json").write_text(json.dumps({"status": status, "seconds": round(time.monotonic() - started, 1), "body": scrub_doc(written)}, indent=1))
    print(name, status, len(raw), "bytes", f"{time.monotonic() - started:.1f}s")
    return status, doc


def trim(chosen_keys):
    def keep(doc):
        data = doc.get("data") if isinstance(doc, dict) else None
        if not isinstance(data, list):
            return doc
        out = []
        for chunk in data:
            js = [j for j in chunk.get("journeys") or [] if j.get("journeyKey") in chosen_keys] or (chunk.get("journeys") or [])[:3]
            out.append({**{k: v for k, v in chunk.items() if k != "journeys"}, "journeys": js, "journeysTotal": len(chunk.get("journeys") or [])})
        return {**doc, "data": out}
    return keep


def first_ok(key, method, path, body, name, out):
    """The docs give api.liteapi.travel; hotels book on book.liteapi.travel. Try each host until one is not 404."""
    for host in HOSTS:
        status, doc = call(key, method, host + path, body, f"{name}__{host.split('//')[1].split('.')[0]}", out)
        if status not in (0, 404):
            return host, status, doc
    return HOSTS[0], status, doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--env", default=".env")
    a = ap.parse_args()
    key = load_key(a.env)
    if not key.startswith("sand_"):
        sys.exit("a sandbox key (sand_...) is required")
    SECRETS.append(key)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    go, back = date.today() + timedelta(days=30), date.today() + timedelta(days=34)
    search = {"legs": [{"origin": "SFO", "destination": "SAN", "date": go.isoformat(), "direction": "OUTBOUND"},
                       {"origin": "SAN", "destination": "SFO", "date": back.isoformat(), "direction": "INBOUND"}],
              "adults": 2, "children": 1, "childrenAges": [7], "infants": 0, "infantAges": [], "currency": "USD", "country": "US",
              "filters": {"showCheapestOfferOnly": True}}
    status, found = call(key, "POST", HOSTS[0] + "/flights/rates", search, "rates_full_unwritten", out, keep=lambda d: {"trimmed": True})
    journeys = [j for c in (found.get("data") or []) for j in c.get("journeys") or []]
    print("  journeys", len(journeys))
    if not journeys:
        sys.exit("no journeys")

    def airline(j):
        return " / ".join(sorted({(s.get("carrier") or {}).get("marketingName", "") for s in j.get("segments") or []}))

    def price(j):
        o = j.get("cheapestOffer") or (j.get("offers") or [{}])[0]
        p = o.get("price") or o.get("totalPrice") or {}
        return p if not isinstance(p, dict) else p.get("total", p.get("amount", p))

    nuitee = [j for j in journeys if "nuit" in airline(j).lower()]
    pick = (nuitee or journeys)[0]
    print("  picked", airline(pick), "price", json.dumps(price(pick))[:120], "nuitee journeys", len(nuitee))
    call(key, "POST", HOSTS[0] + "/flights/rates", search, "rates", out, keep=trim({pick.get("journeyKey")}))
    offer = (pick.get("cheapestOffer") or {}).get("offerId") or ((pick.get("offers") or [{}])[0]).get("offerId")
    session = next((c.get("sessionId") for c in found.get("data") or [] if c.get("sessionId")), None)
    host, st, ver = first_ok(key, "POST", "/flights/verify", {"offerId": offer}, "verify", out)
    print("  verify host", host, "status", st)
    contact = {"firstName": "Maya", "lastName": "Okafor", "email": "maya.okafor@example.com", "phoneCountryCode": "1", "phoneNumber": "4155550100"}
    pax = [{"passengerType": 0, "title": "MS", "firstName": "Maya", "lastName": "Okafor", "birthday": "1985-04-12", "gender": "F", "nationality": "US"},
           {"passengerType": 0, "title": "MR", "firstName": "Daniel", "lastName": "Okafor", "birthday": "1983-09-03", "gender": "M", "nationality": "US"},
           {"passengerType": 1, "firstName": "Leo", "lastName": "Okafor", "birthday": (date.today() - timedelta(days=7 * 365 + 40)).isoformat(), "gender": "M", "nationality": "US"}]
    body = {"offerId": offer, "usePaymentSdk": True, "contact": contact, "passengers": pax, **({"sessionId": session} if session else {})}
    phost, st, pre = first_ok(key, "POST", "/flights/prebooks", body, "prebook_sdk", out)
    d = (pre.get("data") or [{}])
    d = d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else {})
    if d.get("secretKey"):
        SECRETS.append(d["secretKey"])
    print("  prebook host", phost, "status", st, "keys", sorted(d.keys())[:30])
    pid = d.get("prebookId")
    if pid:
        call(key, "GET", f"{phost}/flights/prebooks/{pid}", None, "prebook_get", out)
        call(key, "POST", phost + "/flights/bookings", {"prebookId": pid, "payment": {"method": "TRANSACTION_ID", "transactionId": d.get("transactionId")}}, "book_unpaid", out)
    # the sandbox's own card: a simulated booking, then its cancel
    _, pre2 = call(key, "POST", phost + "/flights/prebooks", {**body, "usePaymentSdk": False}, "prebook_nosdk", out)
    d2 = (pre2.get("data") or [{}])
    d2 = d2[0] if isinstance(d2, list) and d2 else (d2 if isinstance(d2, dict) else {})
    if d2.get("prebookId"):
        _, bk = call(key, "POST", phost + "/flights/bookings", {"prebookId": d2["prebookId"], "payment": {"method": "ACC_CREDIT_CARD"}}, "book_acc", out)
        b = (bk.get("data") or [{}])
        b = b[0] if isinstance(b, list) and b else (b if isinstance(b, dict) else {})
        bid = (b.get("booking") or b).get("bookingId")
        print("  booking", bool(bid), "status", (b.get("booking") or b).get("status"))
        if bid:
            call(key, "GET", f"{phost}/flights/bookings/{bid}", None, "booking_get", out)
            call(key, "GET", f"{phost}/flights/bookings/{bid}/cancellations", None, "cancel_quote", out)
            call(key, "POST", f"{phost}/flights/bookings/{bid}/cancellations", {}, "cancel", out)
            call(key, "GET", f"{phost}/flights/bookings/{bid}", None, "booking_after_cancel", out)
    call(key, "GET", f"{phost}/flights/bookings/not-a-booking", None, "booking_unknown", out)


if __name__ == "__main__":
    main()
