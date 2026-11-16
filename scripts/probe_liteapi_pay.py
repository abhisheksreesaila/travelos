"""Record LiteAPI's payment-SDK booking path against the sandbox (F-274): `pixi run python scripts/probe_liteapi_pay.py --out DIR [--env PATH]`.

Reads LITEAPI_KEY from the environment (or the .env file given); it is never printed, and it and every `secretKey` are scrubbed from what is written. Refuses a key that does not
start with `sand_`. Polite calls only, all with a made-up guest (example.com): the `margin` experiment (one stay search at margins none/0/10/15, 3 hotels, printed as numbers
only), a prebook with `usePaymentSdk: true`, a sandbox voucher (created, applied at prebook, then set inactive), a TRANSACTION_ID book of an unpaid transaction (the refusal),
a book with the sandbox's test card and its cancel (a refundable rate if one is found), and the cancel of a booking that does not exist.
"""

import argparse
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

SEARCH = "https://api.liteapi.travel/v3.0/hotels/rates"
BOOK = "https://book.liteapi.travel/v3.0"
VOUCHERS = "https://da.liteapi.travel/vouchers"
CODE = "F274SANDBOX"
SECRETS: list = []


def load_key(env_path):
    if os.environ.get("LITEAPI_KEY"):
        return os.environ["LITEAPI_KEY"]
    for line in Path(env_path).read_text().splitlines() if env_path else ():
        if line.startswith("LITEAPI_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def scrub(text):
    for s in SECRETS:
        if s:
            text = text.replace(s, "[secret]")
    return text


def scrub_doc(v):
    """A secretKey is replaced by a placeholder of the same shape (the SDK key's prefix is kept: it is not secret, the rest is)."""
    if isinstance(v, dict):
        return {k: ("[secretKey]" if k == "secretKey" and isinstance(x, str) else scrub_doc(x)) for k, x in v.items()}
    if isinstance(v, list):
        return [scrub_doc(x) for x in v]
    return v


def call(key, method, url, body, name, out):
    time.sleep(2)      # the sandbox answers 429 to a burst
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"X-API-Key": key, "Accept": "application/json", **({"Content-Type": "application/json"} if body is not None else {})})
    try:
        r = urllib.request.urlopen(req, timeout=130)      # noqa: S310
        status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    text = scrub(raw.decode("utf-8", "replace"))
    try:
        doc = json.loads(text)
    except ValueError:
        doc = {"raw": text[:500]}
    (out / f"{name}.json").write_text(json.dumps({"status": status, "body": scrub_doc(doc)}, indent=1))
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
    SECRETS.append(key)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    start = date.today() + timedelta(days=30)
    search = {"cityName": "San Diego", "countryCode": "US", "checkin": start.isoformat(), "checkout": (start + timedelta(days=3)).isoformat(), "currency": "USD",
              "guestNationality": "US", "occupancies": [{"adults": 2, "children": [7, 10]}], "limit": 3, "timeout": 10, "maxRatesPerHotel": 1}
    # the margin experiment: the same search at several margins; only numbers are printed
    for m in (None, 0, 10, 15):
        _, found = call(key, "POST", SEARCH, {**search, **({} if m is None else {"margin": m})}, f"hotel_rates_margin_{m}", out)
        for h in (found.get("data") or [])[:3]:
            rt = h["roomTypes"][0]
            rate = rt["rates"][0]
            print("  margin", m, h["hotelId"], "retail", rate["retailRate"]["total"][0]["amount"], "ssp", (rt.get("suggestedSellingPrice") or {}).get("amount"),
                  "rate-ssp", [x.get("amount") for x in rate["retailRate"].get("suggestedSellingPrice") or []], "commission", [c.get("amount") for c in rate.get("commission") or []],
                  "initial", rate["retailRate"].get("initialPrice"), "refundable", (rate.get("cancellationPolicies") or {}).get("refundableTag"))
    _, found = call(key, "POST", SEARCH, search, "hotel_rates", out)
    offers = [(rt["offerId"], rt["rates"][0]["cancellationPolicies"].get("refundableTag")) for h in found["data"] for rt in h["roomTypes"]]
    refundable = next((o for o, tag in offers if tag == "RFN"), offers[0][0])
    # a prebook that returns the payment SDK's keys
    _, pre = call(key, "POST", BOOK + "/rates/prebook", {"offerId": offers[0][0], "usePaymentSdk": True}, "prebook_sdk", out)
    for field in ("secretKey", "transactionId"):
        if isinstance(pre.get("data"), dict) and pre["data"].get(field):
            SECRETS.append(pre["data"][field]) if field == "secretKey" else None
    # a sandbox voucher, applied at prebook (created, or switched on again when an earlier run left it off)
    _, lst = call(key, "GET", VOUCHERS, None, "voucher_list_before", out)
    have = next((i for i in (lst.get("vouchers") or []) if i.get("voucher_code") == CODE), None)
    window = {"validity_start": date.today().isoformat(), "validity_end": (date.today() + timedelta(days=60)).isoformat()}
    body = {"voucher_code": CODE, "discount_type": "percentage", "discount_value": 10, "minimum_spend": 1, "maximum_discount_amount": 100, **window, "usages_limit": 5, "currency": "USD",
            "status": "active", "terms_and_conditions": "GitAway sandbox test code"}
    if have:
        call(key, "PUT", f"{VOUCHERS}/{have['id']}", body, "voucher_on", out)
    else:
        call(key, "POST", VOUCHERS, body, "voucher_create", out)
    _, vpre = call(key, "POST", BOOK + "/rates/prebook", {"offerId": offers[0][0], "usePaymentSdk": True, "voucherCode": CODE}, "prebook_voucher", out)
    d, v = pre.get("data") or {}, vpre.get("data") or {}
    print("  prebook price", d.get("price"), "pays", d.get("sellingPriceToUser"), "| with voucher: price", v.get("price"), "pays", v.get("sellingPriceToUser"), "discount", v.get("voucherTotalAmount"))
    call(key, "POST", BOOK + "/rates/prebook", {"offerId": offers[0][0], "usePaymentSdk": True, "voucherCode": "NOSUCHCODE"}, "prebook_bad_voucher", out)
    guest = {"firstName": "Test", "lastName": "Traveler", "email": "test.traveler@example.com"}
    # TRANSACTION_ID for a payment never made: refused
    call(key, "POST", BOOK + "/rates/book", {"prebookId": d.get("prebookId"), "clientReference": "gitaway-probe-f274-" + uuid.uuid4().hex[:10], "holder": guest, "guests": [{"occupancyNumber": 1, **guest}],
                                              "payment": {"method": "TRANSACTION_ID", "transactionId": d.get("transactionId")}}, "book_unpaid", out)
    # a booking made with the sandbox's own test card, then cancelled
    _, pre2 = call(key, "POST", BOOK + "/rates/prebook", {"offerId": refundable, "usePaymentSdk": False}, "prebook_refundable", out)
    _, bk = call(key, "POST", BOOK + "/rates/book", {"prebookId": pre2["data"]["prebookId"], "clientReference": "gitaway-probe-f274-" + uuid.uuid4().hex[:10], "holder": guest,
                                                      "guests": [{"occupancyNumber": 1, **guest}], "payment": {"method": "ACC_CREDIT_CARD"}}, "book_for_cancel", out)
    booking_id = (bk.get("data") or {}).get("bookingId")
    if booking_id:
        call(key, "PUT", f"{BOOK}/bookings/{booking_id}", None, "cancel", out)
        call(key, "PUT", f"{BOOK}/bookings/{booking_id}", None, "cancel_again", out)
    call(key, "PUT", f"{BOOK}/bookings/not-a-booking", None, "cancel_unknown", out)
    # tidy: the test voucher is switched off
    _, lst = call(key, "GET", VOUCHERS, None, "voucher_list", out)
    for item in (lst.get("vouchers") or []) if isinstance(lst, dict) else []:
        if isinstance(item, dict) and item.get("voucher_code") == CODE and item.get("id"):
            keep = ("voucher_code", "discount_type", "discount_value", "minimum_spend", "maximum_discount_amount", "usages_limit", "currency")
            call(key, "PUT", f"{VOUCHERS}/{item['id']}", {**{k: item[k] for k in keep}, "validity_start": item["validity_start"][:10], "validity_end": item["validity_end"][:10],
                                                          "status": "inactive"}, "voucher_off", out)


if __name__ == "__main__":
    main()
