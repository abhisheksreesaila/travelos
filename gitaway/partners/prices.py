"""Real flight prices where they are free (F-198): the Aviasales Data API's cached prices, the only free price source left for a US trip (docs/research/booking-any-trip.md section 2).

    flight_from(origin, dest, depart, return_)   Price(cents a person, when we checked) for the round trip on those dates, or None: no token, nothing seen, or any failure
    Price.label()                                "from $187 a person, checked Nov 6, 2:05 PM"

The API (GET https://api.travelpayouts.com/aviasales/v3/prices_for_dates, header X-Access-Token: TRAVELPAYOUTS_TOKEN, market=us and currency=usd; its defaults are the ru market
and roubles) returns the cheapest price Aviasales users saw for those dates in the last few days. It is a hint, never a quote, and is never invented: no answer is no price.
Travelpayouts recommends caching for 24 hours; a price is kept that long, a failure FAIL_MINUTES so a slow API is not asked on every page. In-process (one server process).
`TRANSPORT` is the one function that touches the network; tests replace it. A failure is one WARNING line with no token in it.
"""

import json
import logging
import re
import threading
import time
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

from gitaway import catalog
from gitaway.partners import travelpayouts

API = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
TIMEOUT = 2
KEEP = timedelta(hours=24)
FAIL_MINUTES = 30
MAX_CENTS = 5_000_000         # a fare above $50,000 a person is a bad answer
_CACHE: dict = {}             # (origin, dest, depart, return) -> (Price | None, when it was asked), oldest first: the oldest goes when it is full
_CACHE_MAX = 2048
BUDGET_PER_MINUTE = 20        # uncached calls in any minute, for the whole site (F-198 review: anonymous pages must not spend our token); past it, no price
_ASKED: deque = deque()       # monotonic times of the uncached calls in the last minute
_LOCK = threading.Lock()
_IATA = re.compile(r"[A-Z]{3}")
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Price:
    cents: int                # per person, US cents
    checked: datetime         # when GitAway asked (UTC)

    def label(self) -> str:
        return f"from {catalog.money(self.cents)} a person, checked {when(self.checked)}"


def when(at: datetime) -> str:
    local = at.astimezone(catalog.TZ)
    return f"{local:%b} {local.day}, {local.hour % 12 or 12}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"


def _get(url: str, headers: dict, timeout: float):
    """GET with our token; a redirect is refused (it would carry the token elsewhere)."""
    req = urllib.request.Request(url, headers=headers)
    with travelpayouts._opener.open(req, timeout=timeout) as r:     # noqa: S310 (a fixed https URL)
        return json.load(r)


TRANSPORT = _get


def clear() -> None:
    with _LOCK:
        _CACHE.clear()
        _ASKED.clear()


def _spend() -> bool:
    """May one more uncached call go out now? At most BUDGET_PER_MINUTE in any minute."""
    now = time.monotonic()
    with _LOCK:
        while _ASKED and now - _ASKED[0] > 60:
            _ASKED.popleft()
        if len(_ASKED) >= BUDGET_PER_MINUTE:
            return False
        _ASKED.append(now)
        return True


def _keep(key, value) -> None:
    with _LOCK:
        _CACHE.pop(key, None)
        while len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = value


def _read(answer) -> int | None:
    """The cheapest price in an answer, in cents, or None when there is nothing believable in it."""
    if not isinstance(answer, dict) or answer.get("success") is False or not isinstance(answer.get("data"), list) or not answer["data"]:
        return None
    first = answer["data"][0]
    price = first.get("price") if isinstance(first, dict) else None
    if isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
        return None
    cents = int(round(price * 100))
    return cents if cents <= MAX_CENTS else None


def flight_from(origin, dest, depart: date, return_: date) -> Price | None:
    origin, dest = str(origin or "").strip().upper(), str(dest or "").strip().upper()
    token = travelpayouts.token()
    if not token or not (_IATA.fullmatch(origin) and _IATA.fullmatch(dest)) or origin == dest or depart < catalog.today() or return_ <= depart:
        return None
    key, now = (origin, dest, depart, return_), datetime.now(timezone.utc)
    kept = _CACHE.get(key)
    if kept:
        found, asked = kept
        if now - asked < (KEEP if found else timedelta(minutes=FAIL_MINUTES)):
            return found
    if not _spend():
        return None
    query = {"origin": origin, "destination": dest, "departure_at": depart.isoformat(), "return_at": return_.isoformat(), "currency": "usd", "market": "us",
             "sorting": "price", "direct": "false", "one_way": "false", "limit": 1}
    try:
        cents = _read(TRANSPORT(f"{API}?{urlencode(query)}", {"X-Access-Token": token, "Accept": "application/json"}, TIMEOUT))
    except Exception as e:      # a timeout, a 401, a bad body: no price, and say so once
        log.warning("flight price %s-%s not read (%s)", origin, dest, travelpayouts.redacted(e))
        cents = None
    found = Price(cents, now) if cents else None
    _keep(key, (found, now))
    return found
