"""LiteAPI's flight booking answers as the sandbox really gave them (tests/fixtures/liteapi_flight, recorded 2026-11-18 by scripts/probe_liteapi_flights.py), as a TRANSPORT
that remembers every call. Nothing here reaches the network: `Fly` answers from the recordings, with the changes a test names (a moved price, a status, an error)."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "liteapi_flight"
API = "https://api.liteapi.travel/v3.0"
VERIFY, PREBOOK, BOOK = API + "/flights/verify", API + "/flights/prebooks", API + "/flights/bookings/"
BOOKING_ID = "01a1effe-73a6-7128-89a4-fc2295470c71"
BOOKING = API + "/flights/bookings/" + BOOKING_ID
CANCELS = BOOKING + "/cancellations"
PREBOOK_ID, TRANSACTION = "01a1effe-2d7f-78b4-9e13-1596fd089221", "tr_cts_HX7MNE9cTvRSWyWn_QAcm"
OFFER = "offer-flight-1"
AT = datetime(2026, 11, 18, 18, 50, tzinfo=timezone.utc)
FLIGHT_CENTS = 56_907      # the recording's total: $569.07 for 2 adults and a child, SFO to SAN and back


def rec(name) -> dict:
    return json.loads((FIX / f"{name}.json").read_text())


def body_of(name) -> dict:
    return rec(name)["body"]


def raw(name, edit=None) -> tuple:
    """(status, JSON bytes) of one recording, `edit(body)` changing a copy of its body first."""
    doc = rec(name)
    body = copy.deepcopy(doc["body"])
    if edit:
        edit(body)
    return doc["status"], json.dumps(body).encode()


class Fly:
    """A TRANSPORT for the flight calls. `answers` maps "verify", "prebook", "book", "booking", "quote", "cancel" to a recording name, or to a function(body) editing a copy of the
    default recording; `asked` is every call as (url, headers, body, method); `calls(url)` the bodies sent to one address."""

    DEFAULT = {"verify": "verify", "prebook": "prebook_sdk", "book": "book", "booking": "booking_get", "quote": "cancel_quote", "cancel": "cancel"}

    def __init__(self, other=None, **answers):
        self.asked, self.answers, self.other = [], {**self.DEFAULT, **answers}, other

    def which(self, url, body):
        if url == VERIFY:
            return "verify"
        if url == PREBOOK:
            return "prebook"
        if url == BOOK:
            return "book"
        if url.endswith("/cancellations"):
            return "cancel" if body is not None else "quote"
        if url.startswith(API + "/flights/bookings/"):
            return "booking"
        return None

    def __call__(self, url, headers, body, timeout, method=""):
        sent = json.loads(body) if body else (None if body is None else {})
        what = self.which(url, sent)
        if what is None:
            if self.other is None:
                raise AssertionError(f"an unexpected LiteAPI call: {url}")
            return self.other(url, headers, body, timeout) if not method else self.other(url, headers, body, timeout, method)
        self.asked.append((url, headers, sent, method))
        want = self.answers[what]
        if callable(want):
            status, payload = raw(self.DEFAULT[what], want)
        elif isinstance(want, tuple):      # (status, body dict) for an error
            status, payload = want[0], json.dumps(want[1]).encode()
        else:
            status, payload = raw(want)
        return status, "application/json", payload

    def calls(self, url) -> list:
        return [c[2] for c in self.asked if c[0] == url]


def price(cents_total):
    """An edit for the verify recording: the trip costs `cents_total` now, and LiteAPI says the price changed."""
    def edit(doc):
        j = doc["data"][0]["journey"]
        j["pricing"]["display"]["total"] = cents_total / 100
        doc["data"][0]["changes"]["priceChanged"] = True
    return edit


def status(name):
    """An edit for the booking recordings: the booking's status is `name`."""
    def edit(doc):
        doc["data"][0]["booking"]["status"] = name
    return edit


GUEST_NAMES = (("Maya", "Okafor"), ("Daniel", "Okafor"), ("Leo", "Okafor"))      # realistic made-up names: LiteAPI refuses placeholders such as "Test" (error 43002)
