"""LiteAPI (Nuitée), the trip matrix's one source of stays and flights (F-220, D-424): the only module that talks to it.

    stays(city=, country= | lat=, lng=, radius_m=, checkin=, checkout=, adults=, kid_ages=, family=)   an Answer of Stays, cheapest first: each hotel's cheapest room
    flights(legs=((origin, destination, date), ...), adults=, kid_ages=, family=)                      an Answer of Flights, cheapest first: each journey's cheapest offer
    about(hotel_id)                                                                                    the hotel's own description as plain text, or ""
    mode()                                                                                             "sandbox" | "live" | "off", from LITEAPI_KEY's prefix
    searches_today()                                                                                   how many calls went out today, for /admin

The shapes are what the sandbox really answered (docs/research/liteapi-shapes.md; recorded in tests/fixtures/liteapi). Base https://api.liteapi.travel/v3.0, header X-API-Key.
Every total is for the whole stay or trip and the whole party, in integer cents, taxes included; a hotel's fees the total leaves out ("included": false, a resort fee) are
`due_at_stay_cents`. Offer ids are long opaque strings, kept verbatim for booking and never shown. An Answer says OK, OVER (a daily budget is spent), OFF (no key) or FAILED:
never a silent empty list. Answers are kept in the process (stays STAY_KEEP, flights FLIGHT_KEEP, failures FAIL_KEEP) and know when they were fetched; only an uncached call
counts against the daily budgets (PER_FAMILY_A_DAY, A_DAY), which are counted in the community database so a restart does not reset them. `TRANSPORT` is the one function
that touches the network; tests replace it. A failure is one WARNING line with no key in it.
"""

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urlencode

from sqlalchemy import text

from gitaway import community

API = "https://api.liteapi.travel/v3.0"
OK, OVER, OFF, FAILED = "ok", "over budget", "off", "failed"
STAY_KEEP = timedelta(minutes=20)        # hotel prices move with the rooms left
FLIGHT_KEEP = timedelta(minutes=60)      # a flight offer expires within minutes, but its price is a preview here; booking verifies it again
FAIL_KEEP = timedelta(minutes=5)
DATA_KEEP = timedelta(hours=24)          # a hotel's own words
PER_FAMILY_A_DAY = 150                   # uncached calls a family (or, together, everyone signed out) may make in a day
A_DAY = 2000                             # and the whole site
STAY_TIMEOUT, FLIGHT_TIMEOUT = 15, 40    # seconds: the sandbox took 2 s for stays and up to 16 s for flights
HOTEL_LIMIT = 30
MAX_BYTES = 32 * 1024 * 1024             # a round trip's answer was 9 MB (386 journeys, 1,647 offers)
MAX_CENTS = 10_000_000
_CACHE: dict = {}                        # key -> Answer (or about text), oldest first
_CACHE_MAX = 512
_LOCK = threading.Lock()
log = logging.getLogger(__name__)


class Unreadable(ValueError):
    """An answer that is not the shape the sandbox gave: an error, or no data list."""


@dataclass(frozen=True)
class Stay:
    id: str                  # the hotel's id ("lp1f5cb")
    name: str
    photo: str
    thumbnail: str
    lat: float | None
    lng: float | None
    stars: float | None
    rating: float | None     # 0 to 10
    reviews: int
    address: str
    room: str                # "Standard Room, 2 Queen Beds"
    board: str               # "room only" | "breakfast" | the board's own name, lower case
    refundable: bool
    cents: int               # the whole stay, the whole party, taxes included
    due_at_stay_cents: int   # fees the total leaves out, paid at the hotel
    offer_id: str            # verbatim, never shown
    fetched: datetime


@dataclass(frozen=True)
class Leg:
    direction: str           # OUTBOUND | INBOUND
    origin: str
    destination: str
    depart: datetime         # local to the airport, as LiteAPI gives it (no zone)
    arrive: datetime
    stops: int
    minutes: int             # door of the plane to door of the plane, layovers included
    flights: tuple           # ("F9 3382", ...)


@dataclass(frozen=True)
class Flight:
    id: str                  # the journey's key
    airline: str             # "Frontier Airlines", or "United Airlines + Alaska Airlines"
    legs: tuple
    cents: int               # the whole party, taxes included
    carry_on: bool
    checked: bool
    bags: tuple              # what is included, in LiteAPI's words
    refundable: bool
    offer_id: str            # verbatim, never shown
    expires: datetime | None
    fetched: datetime

    @property
    def stops(self) -> int:
        return self.legs[0].stops if self.legs else 0


@dataclass(frozen=True)
class Answer:
    status: str
    items: tuple = ()
    fetched: datetime | None = None

    @property
    def ok(self) -> bool:
        return self.status == OK

    def age(self) -> timedelta | None:
        return now() - self.fetched if self.fetched else None


def now() -> datetime:
    return datetime.now(timezone.utc)


def key() -> str:
    return os.environ.get("LITEAPI_KEY", "").strip()


def mode() -> str:
    k = key()
    return "off" if not k else ("sandbox" if k.startswith("sand_") else "live")


def _send(url: str, headers: dict, body: bytes | None, timeout: float):
    """(status, content type, the body, at most MAX_BYTES + 1 of it). An HTTP error is an answer, not an exception; a redirect is refused (it would carry the key)."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    try:
        with _opener.open(req, timeout=timeout) as r:      # noqa: S310 (a fixed https URL)
            return r.status, r.headers.get("Content-Type", ""), r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", e.read(MAX_BYTES + 1)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)
TRANSPORT = _send


def clear() -> None:
    with _LOCK:
        _CACHE.clear()


# --- reading

def _cents(amount) -> int | None:
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
        return None
    c = int(round(amount * 100))
    return c if c <= MAX_CENTS else None


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _data(answer) -> list:
    if not isinstance(answer, dict) or "error" in answer or not isinstance(answer.get("data"), list):
        raise Unreadable("no data")
    return answer["data"]


def _usd(prices) -> int | None:
    """The amount of a [{amount, currency}] or {amount, currency}, in cents, when it is in dollars."""
    p = prices[0] if isinstance(prices, list) and prices else prices
    return _cents(p.get("amount")) if isinstance(p, dict) and p.get("currency") == "USD" else None


def _board(rate) -> str:
    kind = rate.get("boardType") or ""
    return "room only" if kind == "RO" else ("breakfast" if kind == "BI" else str(rate.get("boardName") or kind).lower())


def read_stays(answer, fetched: datetime) -> tuple:
    """Each hotel's cheapest room from a /hotels/rates answer, cheapest first."""
    data = _data(answer)
    hotels = {h.get("id"): h for h in answer.get("hotels") or () if isinstance(h, dict)}
    found = []
    for h in data:
        hotel = hotels.get(h.get("hotelId") if isinstance(h, dict) else None)
        best = None
        for rt in (h.get("roomTypes") or ()) if hotel else ():
            rates = rt.get("rates") or ()
            cents = _usd(rt.get("offerRetailRate"))
            if not rates or cents is None or not rt.get("offerId") or (best and best[0] <= cents):
                continue
            best = (cents, rt, rates[0])
        if not best:
            continue
        cents, rt, rate = best
        fees = (rate.get("retailRate") or {}).get("taxesAndFees") or ()
        due = sum(_cents(f.get("amount")) or 0 for f in fees if isinstance(f, dict) and f.get("included") is False and f.get("currency") == "USD")
        found.append(Stay(hotel["id"], str(hotel.get("name") or ""), str(hotel.get("main_photo") or ""), str(hotel.get("thumbnail") or ""), _num(hotel.get("latitude")),
                          _num(hotel.get("longitude")), _num(hotel.get("stars")), _num(hotel.get("rating")), int(_num(hotel.get("review_count")) or 0),
                          str(hotel.get("address") or ""), str(rate.get("name") or ""), _board(rate),
                          (rate.get("cancellationPolicies") or {}).get("refundableTag") == "RFN", cents, due, rt["offerId"], fetched))
    return tuple(sorted(found, key=lambda s: (s.cents, s.id)))


def _when(text_) -> datetime | None:
    try:
        return datetime.fromisoformat(text_) if isinstance(text_, str) else None
    except ValueError:
        return None


def _leg(direction, segments, durations) -> Leg | None:
    segs = [s for s in segments if s.get("direction") == direction]
    if not segs:
        return None
    depart, arrive = _when(segs[0].get("departureTime")), _when(segs[-1].get("arrivalTime"))
    if not depart or not arrive:
        return None
    minutes = next((d["duration"].get("minutes") for d in durations if d.get("direction") == direction and isinstance(d.get("duration"), dict)), None)
    if not isinstance(minutes, int):
        minutes = int((arrive - depart).total_seconds() // 60)
    stops = len(segs) - 1 + sum(s.get("stopCount") or 0 for s in segs)
    names = tuple(f"{(s.get('carrier') or {}).get('marketingCode', '')} {(s.get('flight') or {}).get('marketingNumber', '')}".strip() for s in segs)
    return Leg(direction, str(segs[0].get("originCode") or ""), str(segs[-1].get("destinationCode") or ""), depart, arrive, stops, minutes, names)


def read_flights(answer, fetched: datetime) -> tuple:
    """Each journey's cheapest offer from a /flights/rates answer, cheapest first."""
    found = []
    for day in _data(answer):
        for j in (day.get("journeys") or ()) if isinstance(day, dict) else ():
            segments = [s for s in j.get("segments") or () if isinstance(s, dict)]
            directions = list(dict.fromkeys(s.get("direction") for s in segments))
            legs = tuple(_leg(d, segments, j.get("legDurations") or ()) for d in directions)
            offer = j.get("cheapestOffer") or min(j.get("offers") or (), key=lambda o: o["pricing"]["display"]["total"], default=None)
            display = ((offer or {}).get("pricing") or {}).get("display") or {}
            cents = _cents(display.get("total")) if display.get("currency") == "USD" else None
            if not segments or None in legs or cents is None or not offer.get("offerId"):
                continue
            airlines = dict.fromkeys(str((s.get("carrier") or {}).get("marketingName") or "") for s in segments)
            bags = offer.get("baggage") or {}
            found.append(Flight(str(j.get("journeyKey") or offer["offerId"][:16]), " + ".join(a for a in airlines if a), legs, cents,
                                bags.get("hasCarryOnBag") is True, bags.get("hasCheckedBag") is True,
                                tuple(str(b.get("description")) for b in bags.get("included") or () if isinstance(b, dict) and b.get("description")),
                                (offer.get("terms") or {}).get("refundable") is True, offer["offerId"], _when(offer.get("expiration")), fetched))
    return tuple(sorted(found, key=lambda f: (f.cents, f.id)))


def read_body(content_type: str, body: bytes):
    """The answer as one JSON object. A streamed answer (text/event-stream: `event:` and `data:` lines, a blank line between messages) is merged: its journeys in order."""
    if "event-stream" not in (content_type or ""):
        try:
            return json.loads(body)
        except ValueError as e:
            raise Unreadable("not JSON") from e
    days = []
    for message in body.decode("utf-8", "replace").replace("\r\n", "\n").split("\n\n"):
        lines = message.split("\n")
        event = next((ln[6:].strip() for ln in lines if ln.startswith("event:")), "")
        payload = "\n".join(ln[5:].lstrip() for ln in lines if ln.startswith("data:"))
        if event == "error":
            raise Unreadable("the stream said error")
        if not payload or payload == "{}":
            continue
        try:
            days.extend(_data(json.loads(payload)))
        except ValueError as e:
            raise Unreadable("a message that is not JSON") from e
    if not days:
        raise Unreadable("an empty stream")
    return {"data": days}


class _Text(HTMLParser):
    BLOCK = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "table", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "br":
            self.out.append("\n")
        elif tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def strip_html(html: str) -> str:
    """Plain text from LiteAPI's HTML descriptions: paragraphs kept as blank lines, tags, scripts and entities gone."""
    p = _Text()
    p.feed(str(html or ""))
    p.close()
    paras = ("".join(p.out)).split("\n\n")
    lines = ("\n".join(" ".join(ln.split()) for ln in para.split("\n")).strip("\n") for para in paras)
    return "\n\n".join(x for x in lines if x.strip())


# --- asking

def _day() -> str:
    return now().date().isoformat()


def _spend(family: str) -> bool:
    """Count one uncached call for `family` today, if neither its budget nor the site's is spent."""
    day, who = _day(), family or "guest"
    with _LOCK, community.connect() as db:
        mine = db.conn.execute(text("SELECT COALESCE(SUM(n), 0) FROM liteapi_searches WHERE day = :d AND family = :f"), {"d": day, "f": who}).scalar()
        everyone = db.conn.execute(text("SELECT COALESCE(SUM(n), 0) FROM liteapi_searches WHERE day = :d"), {"d": day}).scalar()
        if mine >= PER_FAMILY_A_DAY or everyone >= A_DAY:
            return False
        db.conn.execute(text("INSERT INTO liteapi_searches (day, family, n) VALUES (:d, :f, 1) ON CONFLICT(day, family) DO UPDATE SET n = n + 1"), {"d": day, "f": who})
        db.conn.commit()
    return True


def searches_today() -> int:
    with community.connect() as db:
        return int(db.conn.execute(text("SELECT COALESCE(SUM(n), 0) FROM liteapi_searches WHERE day = :d"), {"d": _day()}).scalar())


def _kept(cache_key, keep_ok):
    with _LOCK:
        kept = _CACHE.get(cache_key)
    if kept is None:
        return None
    value, at = kept
    fresh = keep_ok if (not isinstance(value, Answer) or value.ok) else FAIL_KEEP
    return value if now() - at < fresh else None


def _keep(cache_key, value) -> None:
    with _LOCK:
        _CACHE.pop(cache_key, None)
        while len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[cache_key] = (value, now())


def _ask(what: str, path: str, body: dict | None, timeout: float):
    """The parsed JSON answer, or None after saying once what went wrong (never the key)."""
    k = key()
    headers = {"X-API-Key": k, "Accept": "application/json", **({"Content-Type": "application/json"} if body is not None else {})}
    try:
        status, ctype, raw = TRANSPORT(API + path, headers, json.dumps(body).encode() if body is not None else None, timeout)
        if len(raw) > MAX_BYTES:
            raise Unreadable(f"over {MAX_BYTES} bytes")
        if status != 200:
            raise Unreadable(f"HTTP {status}")
        return read_body(ctype, raw)
    except Exception as e:      # a timeout, a 401, an error body: say so once
        log.warning("LiteAPI %s not read (%s)", what, str(e).replace(k, "[key]") if k else e)
        return None


def _search(what: str, path: str, body: dict, keep: timedelta, timeout: float, family: str, read) -> Answer:
    if not key():
        return Answer(OFF)
    cache_key = (path, mode(), json.dumps(body, sort_keys=True))
    kept = _kept(cache_key, keep)
    if kept is not None:
        return kept
    if not _spend(family):
        return Answer(OVER)
    at = now()
    answer = _ask(what, path, body, timeout)
    try:
        found = Answer(OK, read(answer, at), at) if answer is not None else Answer(FAILED, (), at)
    except Unreadable as e:
        log.warning("LiteAPI %s not read (%s)", what, e)
        found = Answer(FAILED, (), at)
    _keep(cache_key, found)
    return found


def _party(adults: int, kid_ages) -> tuple:
    ages = [int(a) for a in kid_ages or ()]
    if not 1 <= int(adults) <= 9 or any(not 0 <= a <= 17 for a in ages):
        raise ValueError("a party is 1 to 9 adults and kids 0 to 17")
    return int(adults), ages


def stays(*, checkin: date, checkout: date, adults: int, kid_ages=(), city: str = "", country: str = "", lat: float | None = None, lng: float | None = None,
          radius_m: int | None = None, family: str = "") -> Answer:
    """Hotel rates for one room for the party, by a city and its country code or by a point and a radius in metres."""
    adults, ages = _party(adults, kid_ages)
    if checkout <= checkin:
        raise ValueError("checkout is after checkin")
    if city and country:
        where = {"cityName": city, "countryCode": country.upper()}
    elif lat is not None and lng is not None and radius_m:
        where = {"latitude": float(lat), "longitude": float(lng), "radius": int(radius_m)}
    else:
        raise ValueError("a city and country, or a point and a radius")
    body = {**where, "checkin": checkin.isoformat(), "checkout": checkout.isoformat(), "currency": "USD", "guestNationality": "US",
            "occupancies": [{"adults": adults, "children": ages}], "limit": HOTEL_LIMIT, "timeout": STAY_TIMEOUT - 5}
    return _search("stays", "/hotels/rates", body, STAY_KEEP, STAY_TIMEOUT, family, read_stays)


def flights(*, legs, adults: int, kid_ages=(), family: str = "") -> Answer:
    """Flight offers for the legs in order (one: one way; two back and forth: a round trip), for the party. Kids under 2 fly as infants."""
    adults, ages = _party(adults, kid_ages)
    legs = tuple(legs)
    if not legs:
        raise ValueError("at least one leg")
    round_trip = len(legs) == 2 and legs[0][0] == legs[1][1] and legs[0][1] == legs[1][0]
    body = {"legs": [{"origin": o.upper(), "destination": d.upper(), "date": day.isoformat(), **({"direction": ("OUTBOUND", "INBOUND")[i]} if round_trip else {})}
                     for i, (o, d, day) in enumerate(legs)],
            "adults": adults, "children": len([a for a in ages if a >= 2]), "childrenAges": [a for a in ages if a >= 2],
            "infants": len([a for a in ages if a < 2]), "infantAges": [a for a in ages if a < 2], "currency": "USD", "country": "US"}
    return _search("flights", "/flights/rates", body, FLIGHT_KEEP, FLIGHT_TIMEOUT, family, read_flights)


def about(hotel_id: str, family: str = "") -> str:
    """The hotel's own description, HTML stripped; "" when there is no key, the budget is spent, or it could not be read."""
    hotel_id = str(hotel_id or "").strip()
    if not key() or not hotel_id.isalnum():
        return ""
    cache_key = ("about", mode(), hotel_id)
    kept = _kept(cache_key, DATA_KEEP)
    if kept is not None:
        return kept
    if not _spend(family):
        return ""
    answer = _ask("hotel", "/data/hotel?" + urlencode({"hotelId": hotel_id}), None, STAY_TIMEOUT)
    words = strip_html(answer["data"].get("hotelDescription")) if isinstance(answer, dict) and isinstance(answer.get("data"), dict) else ""
    if words:
        _keep(cache_key, words)
    return words
