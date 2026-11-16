"""LiteAPI (Nuitée), the trip matrix's one source of stays and flights (F-220, D-424): the only module that talks to it.

    stays(city=, country= | lat=, lng=, radius_m=, checkin=, checkout=, adults=, kid_ages=, family=)   an Answer of Stays, cheapest first: each hotel's cheapest room
    flights(legs=((origin, destination, date), ...), adults=, kid_ages=, family=)                      an Answer of Flights, cheapest first: each journey's cheapest offer
    prebook(offer_id, family=) / book(prebook_id, guest, reference, family=)                           F-233: an Answer of one Prebook / one Booking, sandbox key only, never kept
    about(hotel_id)                                                                                the hotel's own description as plain text, or ""
    hotel(hotel_id) / reviews(hotel_id)                                                            F-275: the hotel's photos, words, facilities, rooms / its reviews and sentiment, kept a day
    mode()                                                                                             "sandbox" | "live" | "off", from LITEAPI_KEY's prefix
    searches_today()                                                                                   how many calls went out today, for /admin

The shapes are what the sandbox really answered (docs/research/liteapi-shapes.md; recorded in tests/fixtures/liteapi). Base https://api.liteapi.travel/v3.0, header X-API-Key.
Every total is for the whole stay or trip and the whole party, in integer cents, taxes included; a hotel's fees the total leaves out ("included": false, a resort fee) are
`due_at_stay_cents`. Offer ids are long opaque strings, kept verbatim for booking and never shown. An Answer says OK, OVER (a daily budget is spent), OFF (no key) or FAILED:
never a silent empty list. Answers are kept in the process (stays STAY_KEEP, flights FLIGHT_KEEP, failures FAIL_KEEP) and know when they were fetched; only an uncached call
counts against the daily budgets (PER_FAMILY_A_DAY, A_DAY), which are counted in the community database so a restart does not reset them. `TRANSPORT` is the one function
that touches the network; tests replace it. A failure is one WARNING line with no key in it.

Every call goes through one gate (F-229, D-445): at most `at_once()` in flight (AT_ONCE = 3 for a sandbox key; AT_ONCE_LIVE = 32 for a live key, F-273) across the site (the sandbox answered 429 when a page sent more), and a search
already in flight is joined, never asked twice: the second asker waits for the first one's Answer, and no second search is counted. A call carries a
`rank` (its square's place in the page's order, 0 the asked square): when a place at the gate comes free the lowest rank waiting goes, and a joiner lends
its rank to the search it joined. A family over its budget is told OVER before it waits; a call waits at most `wait` seconds (TILE_WAIT for a request,
GATE_WAIT for the head start) and never joins a line longer than MAX_WAITING: either way it is BUSY, which is never kept, so asked again it searches. Flights are read from
the stream (`Accept: text/event-stream`, D-446): `rates-chunk` messages shaped like the plain answer, then `rates-complete`, which the sandbox does not
always send. The reader keeps each journey's cheapest offer seen and stops at `rates-complete`, STREAM_GRACE seconds after the first chunk of at least
BULK journeys, or at STREAM_CAP whatever happens (a watchdog cuts a line that hangs); an Answer cut short says `complete=False`, the cheapest found.
"""

import http.client
import json
import logging
import os
import queue
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import quote, urlencode

from sqlalchemy import text

from gitaway import community

API = "https://api.liteapi.travel/v3.0"
BOOK_API = "https://book.liteapi.travel/v3.0"      # prebook and book live on their own host (F-233)
GONE, DUPLICATE, BAD_CODE = "gone", "duplicate", "bad code"      # a prebook or book the room or rate is no longer there for; a book whose clientReference was already used; a voucher code LiteAPI refuses (F-274)
MARGIN = 16.0                            # percent put on the net rate of every live stay search (F-274, D-840): the sandbox showed the retail rate and `suggestedSellingPrice` equal to the cent at 16
PAYMENT_SDK = "https://payment-wrapper.liteapi.travel/dist/liteAPIPayment.js?v=a1"      # LiteAPI's payment form script, the one script of another site GitAway loads, from the booking sheet only (D-841)
PREBOOK_TIMEOUT, BOOK_TIMEOUT = 60, 90     # the docs say a prebook can take up to about 2 minutes; the sandbox answered in a few seconds
OK, OVER, OFF, FAILED, BUSY = "ok", "over budget", "off", "failed", "busy"    # BUSY: no turn at the gate in time; never kept
STAY_KEEP = timedelta(minutes=20)        # hotel prices move with the rooms left
FLIGHT_KEEP = timedelta(minutes=60)      # a flight offer expires within minutes, but its price is a preview here; booking verifies it again
FAIL_KEEP = timedelta(minutes=5)
DATA_KEEP = timedelta(hours=24)          # a hotel's own words
PER_FAMILY_A_DAY = 150                   # uncached calls a family (or, together, everyone signed out) may make in a day
PER_VISITOR_A_DAY = 60                   # uncached searches one signed-out visitor may make in a day (F-265, D-764): about three full matrices; a visitor is `stats.searcher`'s "v:" code
VISITOR = "v:"
A_DAY = 2000                             # and the whole site
PER_FAMILY_BOOK_A_DAY, BOOK_A_DAY = 20, 200      # booking calls (prebook, book, lookup) have their own daily budgets, so booking never spends a family's searches nor the reverse (F-233 review)
STAY_TIMEOUT, FLIGHT_TIMEOUT = 30, 40    # seconds: the sandbox took 2 to 17 s for stays and up to 16 s for flights; on 2026-11-12 evening stays took up to 33 s
STAY_ASK = 10                            # seconds LiteAPI is asked to answer a stay search in (its `timeout`; the sandbox does not always keep it)
HOTEL_LIMIT = 30
MAX_BYTES = 32 * 1024 * 1024             # a round trip's answer was 9 MB (386 journeys, 1,647 offers)
MAX_CENTS = 10_000_000
AT_ONCE = 3                              # calls in flight across the site (F-229): the sandbox (5 requests a second) answered 429 to a page's 6
AT_ONCE_LIVE = 32                        # F-273, D-830: a live key (250 requests a second) lets a whole matrix's searches start together (5x5: about 30)
GATE_WAIT = 60                           # seconds a background call (the head start's few workers) waits for its turn at the gate; then BUSY, never kept
TILE_WAIT = 12                           # and a request's call (a tile: a request thread), so the server's thread pool is never held long
MAX_WAITING = 12                         # calls waiting at the gate at most; one more is BUSY at once
STREAM_CAP = 14.0                        # seconds: the flight stream is read this long at most (complete answers came at 10.5 and 13.9 s; some never)
STREAM_GRACE = 4.0                       # and this long after the first chunk of BULK journeys (those came at 4.7 to 5.7 s; later chunks to 14.5 s)
BULK = 20                                # a chunk this big is the search answering; the lone first chunk is the sandbox's test airline
_CACHE: dict = {}                        # key -> Answer (or about text), oldest first
_CACHE_MAX = 128                         # a round-trip answer holds hundreds of journeys with long offer ids
_LOCK = threading.Lock()
_FLYING: dict = {}                       # cache key -> _Flight: a search in flight, for a second asker to join
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
    rooms: tuple = ()        # F-251: every room the answer gave for this hotel, cheapest first (at most MAX_ROOMS), each a Room; the cheapest is this stay's own


@dataclass(frozen=True)
class Room:
    name: str                # "Deluxe King Corner"
    board: str               # as Stay.board
    refundable: bool
    cents: int               # the whole stay in this room, the whole party, taxes included, fees paid at the hotel not
    due_at_stay_cents: int
    offer_id: str            # verbatim, never shown


MAX_ROOMS = 4


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
    complete: bool = True    # False: a stream stopped at its deadline, so the items are the cheapest found by then

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


def at_once() -> int:
    """The gate's places for the key in use, read at each call (F-273): a live key's rate allows a whole matrix at once, a sandbox key (or none) keeps 3."""
    return AT_ONCE_LIVE if mode() == "live" else AT_ONCE


def margin() -> float | None:
    """The percentage a live stay search carries (`margin`), so the price charged is the public price shown (F-274, D-840): LITEAPI_MARGIN, else MARGIN. A sandbox key sends none."""
    if mode() != "live":
        return None
    try:
        m = float(os.environ.get("LITEAPI_MARGIN", "").strip() or MARGIN)
    except ValueError:
        return MARGIN
    return m if 0 <= m <= 40 else MARGIN


def real_booking() -> bool:
    """May a live key book (and so charge a real card)? In production unless GITAWAY_LIVE_BOOKING=0; anywhere else only with GITAWAY_LIVE_BOOKING=1 (D-841), so a dev box with the
    live key reads prices and plays the sample booking by default."""
    from gitaway import auth
    flag = os.environ.get("GITAWAY_LIVE_BOOKING", "").strip()
    return mode() == "live" and (flag != "0" if auth.production() else flag == "1")


class _Lines:
    """A streamed answer's lines as they arrive. `cut()` shuts the socket down from another thread (the reader closes it), so a line that hangs ends."""

    def __init__(self, resp):
        self.resp = resp

    def __iter__(self):
        try:
            while True:
                line = self.resp.readline(MAX_BYTES + 1)
                if not line:
                    return
                yield line
        finally:
            self.resp.close()

    def cut(self):
        try:
            self.resp.fp.raw._sock.shutdown(socket.SHUT_RDWR)
        except (AttributeError, OSError):
            pass

    def close(self):
        try:
            self.resp.close()
        except OSError:
            pass


def _send(url: str, headers: dict, body: bytes | None, timeout: float, method: str = ""):
    """(status, content type, the body, at most MAX_BYTES + 1 of it; or a stream's lines, `_Lines`). An HTTP error is an answer, not an exception; a redirect
    is refused (it would carry the key)."""
    req = urllib.request.Request(url, data=body, headers=headers, method=method or ("POST" if body is not None else "GET"))
    try:
        r = _opener.open(req, timeout=timeout)      # noqa: S310 (a fixed https URL)
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", e.read(MAX_BYTES + 1)
    ctype = r.headers.get("Content-Type", "")
    if "event-stream" in ctype:
        return r.status, ctype, _Lines(r)
    with r:
        return r.status, ctype, r.read(MAX_BYTES + 1)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)
TRANSPORT = _send


def clear() -> None:
    global _TURNS
    with _LOCK:
        _CACHE.clear()
        _FLYING.clear()
    _TURNS = _Turns(at_once)


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


def _room_of(rt, rate) -> Room:
    fees = (rate.get("retailRate") or {}).get("taxesAndFees") or ()
    due = sum(_cents(f.get("amount")) or 0 for f in fees if isinstance(f, dict) and f.get("included") is False and f.get("currency") == "USD")
    return Room(str(rate.get("name") or ""), _board(rate), (rate.get("cancellationPolicies") or {}).get("refundableTag") == "RFN", _shown(rt), due, rt["offerId"])


def _shown(rt) -> int | None:
    """The price a room shows (F-267, D-767). With a live key, LiteAPI's public selling price (`suggestedSellingPrice`: about 15% over the retail rate, the price the big sites
    show, so never under the hotel's own); when a rate has none, or none we can read, the retail rate (`offerRetailRate`), and nothing more said. A sandbox key shows the retail rate."""
    public = _usd(rt.get("suggestedSellingPrice")) if mode() == "live" else None
    return public if public is not None else _usd(rt.get("offerRetailRate"))


def read_stays(answer, fetched: datetime) -> tuple:
    """Each hotel's cheapest room from a /hotels/rates answer, cheapest first, with the hotel's other rooms (F-251: at most MAX_ROOMS, the cheapest first)."""
    data = _data(answer)
    hotels = {h.get("id"): h for h in answer.get("hotels") or () if isinstance(h, dict)}
    found = []
    for h in data:
        hotel = hotels.get(h.get("hotelId") if isinstance(h, dict) else None)
        rooms = []
        for rt in (h.get("roomTypes") or ()) if hotel else ():
            rates = rt.get("rates") or ()
            if rates and _usd(rt.get("offerRetailRate")) is not None and rt.get("offerId"):
                rooms.append(_room_of(rt, rates[0]))
        if not rooms:
            continue
        rooms = tuple(sorted(rooms, key=lambda r: r.cents)[:MAX_ROOMS])      # a stable sort: of two rooms at one price the first the answer gave is the cheapest
        best = rooms[0]
        found.append(Stay(hotel["id"], str(hotel.get("name") or ""), _https(hotel.get("main_photo")), str(hotel.get("thumbnail") or ""), _num(hotel.get("latitude")),
                          _num(hotel.get("longitude")), _num(hotel.get("stars")), _num(hotel.get("rating")), int(_num(hotel.get("review_count")) or 0),
                          str(hotel.get("address") or ""), best.name, best.board, best.refundable, best.cents, best.due_at_stay_cents, best.offer_id, fetched, rooms))
    return tuple(sorted(found, key=lambda s: (s.cents, s.id)))


def _https(url) -> str:
    """A photo address only when it is https with a host: a `javascript:` or plain http value from an answer never reaches a page."""
    u = urlsplit(url) if isinstance(url, str) else None
    return url if u and u.scheme == "https" and u.netloc else ""


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
    return tuple(sorted(cheapest(found), key=lambda f: (f.cents, f.id)))


def cheapest(flights) -> list:
    """One flight per journey, at its cheapest (a stream sends a journey in several chunks, at prices a few cents apart)."""
    best = {}
    for f in flights:
        if f.id not in best or f.cents < best[f.id].cents:
            best[f.id] = f
    return list(best.values())


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


def _per(family: str, per: int, book: bool) -> int:
    """A visitor's own allowance, else the family's budget (a booking call is a signed-in family's, never a visitor's)."""
    return PER_VISITOR_A_DAY if family.startswith(VISITOR) and not book else per


def visitor_over(family: str) -> bool:
    """Is `family` a visitor whose own allowance for today is spent (not the site's total)?"""
    if not family.startswith(VISITOR):
        return False
    with community.connect() as db:
        return db.conn.execute(text("SELECT COALESCE(SUM(n), 0) FROM liteapi_searches WHERE day = :d AND family = :f"), {"d": _day(), "f": family}).scalar() >= PER_VISITOR_A_DAY


def _spend(family: str, book: bool = False) -> bool:
    """Count one uncached call for `family` today, if neither its budget nor the site's is spent. `book`: a booking call, counted in its own table against its own budgets."""
    day, who = _day(), family or "guest"
    table, per, total = ("liteapi_bookings", PER_FAMILY_BOOK_A_DAY, BOOK_A_DAY) if book else ("liteapi_searches", PER_FAMILY_A_DAY, A_DAY)
    with _LOCK, community.connect() as db:
        mine = db.conn.execute(text(f"SELECT COALESCE(SUM(n), 0) FROM {table} WHERE day = :d AND family = :f"), {"d": day, "f": who}).scalar()
        everyone = db.conn.execute(text(f"SELECT COALESCE(SUM(n), 0) FROM {table} WHERE day = :d"), {"d": day}).scalar()
        if mine >= _per(who, per, book) or everyone >= total:
            return False
        if who.startswith(VISITOR) and not book:      # a visitor's code is good for the day it was made: yesterday's are gone
            db.conn.execute(text("DELETE FROM liteapi_searches WHERE family LIKE 'v:%' AND day != :d"), {"d": day})
        db.conn.execute(text(f"INSERT INTO {table} (day, family, n) VALUES (:d, :f, 1) ON CONFLICT(day, family) DO UPDATE SET n = n + 1"), {"d": day, "f": who})
        db.conn.commit()
    return True


def can_search(family: str, book: bool = False) -> bool:
    """Whether `family` (and the site) still has calls left today: background work asks before it starts (F-229). `book`: the booking budgets."""
    day, who = _day(), family or "guest"
    table, per, total = ("liteapi_bookings", PER_FAMILY_BOOK_A_DAY, BOOK_A_DAY) if book else ("liteapi_searches", PER_FAMILY_A_DAY, A_DAY)
    with community.connect() as db:
        mine = db.conn.execute(text(f"SELECT COALESCE(SUM(n), 0) FROM {table} WHERE day = :d AND family = :f"), {"d": day, "f": who}).scalar()
        everyone = db.conn.execute(text(f"SELECT COALESCE(SUM(n), 0) FROM {table} WHERE day = :d"), {"d": day}).scalar()
    return mine < _per(who, per, book) and everyone < total


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


def _say(what, e) -> None:
    k = key()
    log.warning("LiteAPI %s not read (%s)", what, str(e).replace(k, "[key]") if k else e)


def _headers(body, accept="application/json") -> dict:
    return {"X-API-Key": key(), "Accept": accept, **({"Content-Type": "application/json"} if body is not None else {})}


def _ask(what: str, path: str, body: dict | None, timeout: float):
    """The parsed JSON answer, or None after saying once what went wrong (never the key). The caller holds the gate."""
    try:
        try:
            status, ctype, raw = TRANSPORT(API + path, _headers(body), json.dumps(body).encode() if body is not None else None, timeout)
        except (http.client.RemoteDisconnected, ConnectionResetError):      # the sandbox sometimes drops a line before answering: asked once more (never after a timeout)
            status, ctype, raw = TRANSPORT(API + path, _headers(body), json.dumps(body).encode() if body is not None else None, timeout)
        if len(raw) > MAX_BYTES:
            raise Unreadable(f"over {MAX_BYTES} bytes")
        if status != 200:
            raise Unreadable(f"HTTP {status}")
        return read_body(ctype, raw)
    except Exception as e:      # a timeout, a 401, an error body: say so once
        _say(what, e)
        return None


def _stream(path: str, body: dict, at: datetime, gate=None):
    """Flights read from the stream: (each journey's cheapest offer, whether the stream said it was complete). Raises on a failure or a shape we never saw.
    The transport and its lines run on their own thread, so the deadlines hold even while a read hangs; at the end the line is cut. If that thread is still
    connecting when the reader is done, it takes over `gate`'s place and gives it back when the transport returns (its socket timeout bounds that), so a
    line LiteAPI still has open always counts against AT_ONCE."""
    started = time.monotonic()
    got: queue.Queue = queue.Queue()
    stop = threading.Event()
    held, hand = {}, {"done": False, "gate": None, "lock": threading.Lock()}

    def pump():
        try:
            _pump()
        finally:
            with hand["lock"]:
                hand["done"] = True
                gate_ = hand["gate"]
            if gate_ is not None:
                gate_.turns.give()

    def _pump():
        try:
            status, ctype, lines = TRANSPORT(API + path, _headers(body, "text/event-stream"), json.dumps(body).encode(), STREAM_CAP)
            held["lines"] = lines
            if stop.is_set():      # the reader gave up before the answer came: close it at once, read nothing
                _shut(lines)
                return
            got.put(("head", status, ctype))
            if isinstance(lines, (bytes, bytearray)):
                got.put(("body", ctype, bytes(lines)))
                return
            for line in lines:
                if stop.is_set():
                    break
                got.put(("line", line))
            got.put(("end",))
        except Exception as e:      # noqa: BLE001 (said by the reader)
            got.put(("error", e))

    pumping = threading.Thread(target=pump, daemon=True, name="liteapi-stream")
    pumping.start()
    flights, size, msg, bulk_at, complete = {}, 0, [], None, False

    def take(event, payload):
        nonlocal complete
        if event == "error":
            raise Unreadable("the stream said error")
        if event == "rates-complete" and payload.strip() in ("", "{}"):      # complete, with nothing new: what came in the chunks is the answer
            complete = True
            return 0
        if event not in ("rates-chunk", "rates-complete") or not payload:
            return 0
        try:
            doc = json.loads(payload)
        except ValueError as e:
            raise Unreadable("a message that is not JSON") from e
        found = read_flights(doc, at)
        for f in found:
            if f.id not in flights or f.cents < flights[f.id].cents:
                flights[f.id] = f
        complete = complete or event == "rates-complete"
        return sum(len(d.get("journeys") or ()) for d in _data(doc) if isinstance(d, dict))

    try:
        while not complete:
            now_ = time.monotonic()
            until = started + STREAM_CAP if bulk_at is None else min(started + STREAM_CAP, bulk_at + STREAM_GRACE)
            if now_ >= until:
                break
            try:
                item = got.get(timeout=until - now_)
            except queue.Empty:
                break
            if item[0] == "error":
                raise item[1]
            if item[0] == "head":
                if item[1] != 200:
                    raise Unreadable(f"HTTP {item[1]}")
                continue
            if item[0] == "body":      # a plain answer after all (JSON, or a whole stream at once)
                if len(item[2]) > MAX_BYTES:
                    raise Unreadable(f"over {MAX_BYTES} bytes")
                return read_flights(read_body(item[1], item[2]), at), True
            if item[0] == "end":
                break
            line = item[1]
            size += len(line)
            if size > MAX_BYTES:
                raise Unreadable(f"over {MAX_BYTES} bytes")
            text_ = line.decode("utf-8", "replace").rstrip("\r\n")
            if text_:
                msg.append(text_)
                continue
            if not msg:
                continue
            event = next((ln[6:].strip() for ln in msg if ln.startswith("event:")), "")
            payload = "\n".join(ln[5:].lstrip() for ln in msg if ln.startswith("data:"))
            msg = []
            if take(event, payload) >= BULK and bulk_at is None:
                bulk_at = time.monotonic()
    finally:
        stop.set()
        cut = getattr(held.get("lines"), "cut", None)
        if cut:
            cut()
        pumping.join(0.25)
        with hand["lock"]:
            if not hand["done"] and gate is not None and gate.ok:      # still connecting: its place at the gate goes with it
                hand["gate"], gate.ok = gate, False
    if not flights:
        raise Unreadable(f"no flights in the stream after {time.monotonic() - started:.1f} s")
    return tuple(sorted(flights.values(), key=lambda f: (f.cents, f.id))), complete


def _shut(lines) -> None:
    for name in ("cut", "close"):
        fn = getattr(lines, name, None)
        if fn:
            fn()


class _Flight:
    """A search in flight: the first asker sets `answer`, then `done`. `rank` is the most wanted asker's (a joiner can lower it while it waits at the gate)."""

    def __init__(self, rank=0):
        self.done, self.answer, self.rank = threading.Event(), None, rank


class _Turns:
    """The gate's places (`places()` is read each time: it depends on the key, F-273). A waiting call goes in rank order (lowest first), then by arrival; its rank is read each time a place comes free."""

    def __init__(self, places):
        self.places, self.used, self.waiting, self.cond, self.seq = places, 0, [], threading.Condition(), 0

    @property
    def free(self) -> int:
        return self.places() - self.used

    def take(self, rank_of, timeout) -> bool:
        with self.cond:
            if self.free <= 0 and len(self.waiting) >= MAX_WAITING:
                return False
            self.seq += 1
            me = (self.seq, rank_of)
            self.waiting.append(me)
            end = time.monotonic() + timeout
            try:
                while True:
                    if self.free > 0 and min(self.waiting, key=lambda w: (w[1](), w[0])) is me:
                        self.used += 1
                        return True
                    left = end - time.monotonic()
                    if left <= 0:
                        return False
                    self.cond.wait(left)
            finally:
                self.waiting.remove(me)
                self.cond.notify_all()

    def give(self) -> None:
        with self.cond:
            self.used -= 1
            self.cond.notify_all()

    def nudge(self) -> None:
        with self.cond:
            self.cond.notify_all()


_TURNS = _Turns(at_once)


class _Gate:
    """One of the AT_ONCE places in flight, in rank order; False when none came free within GATE_WAIT."""

    def __init__(self, rank_of=lambda: 0, wait=None):
        self.rank_of, self.wait = rank_of, GATE_WAIT if wait is None else wait

    def __enter__(self):
        self.turns = _TURNS
        self.ok = self.turns.take(self.rank_of, self.wait)
        return self

    def __exit__(self, *exc):
        if self.ok:
            self.turns.give()


def _search(what: str, path: str, body: dict, keep: timedelta, timeout: float, family: str, read, cached_only: bool = False, stream: bool = False,
            rank: int = 0, wait: float | None = None) -> Answer | None:
    if not key():
        return Answer(OFF)
    cache_key = (path, mode(), json.dumps(body, sort_keys=True))
    while True:
        kept = _kept(cache_key, keep)
        if kept is not None or cached_only:      # cached_only (F-222): what is kept, or None; never a call and never a search counted
            return kept
        with _LOCK:
            flying = _FLYING.get(cache_key)
            first = flying is None
            if first:
                flying = _FLYING[cache_key] = _Flight(rank)
            elif rank < flying.rank:
                flying.rank = rank
        if first:
            break
        _TURNS.nudge()      # a lower rank lent to a search still waiting at the gate
        flying.done.wait((GATE_WAIT if wait is None else wait) + max(timeout, STREAM_CAP) + 1)      # the same search is on its way: its answer is ours, and no second search counted
        if flying.answer is None:
            return Answer(BUSY)
        if flying.answer.status != OVER:
            return flying.answer
        # the first asker's budget was spent, not ours: ask on our own
    found = Answer(FAILED, (), now())
    try:
        found = _call(what, path, body, timeout, family, read, stream, flying, wait)
        if found.status not in (OVER, BUSY):      # no turn at the gate, or a spent budget, is not the answer: asked again, it searches
            _keep(cache_key, found)
    finally:
        flying.answer = found
        with _LOCK:
            if _FLYING.get(cache_key) is flying:
                del _FLYING[cache_key]
        flying.done.set()
    return found


def _call(what, path, body, timeout, family, read, stream, flying, wait) -> Answer:
    if not can_search(family):      # told at once, never after a wait at the gate
        return Answer(OVER)
    with _Gate(lambda: flying.rank, wait) as gate:
        through = gate.ok
        if not through:
            _say(what, "no turn at the gate")
            return Answer(BUSY)
        if not _spend(family):
            return Answer(OVER)
        at = now()
        try:
            if stream:
                items, complete = _stream(path, body, at, gate)
                return Answer(OK, items, at, complete)
            answer = _ask(what, path, body, timeout)
            return Answer(OK, read(answer, at), at) if answer is not None else Answer(FAILED, (), at)
        except Exception as e:      # a shape we never saw (a missing field, a string for a number), a stream with nothing: a failure, never a crash
            _say(what, f"{type(e).__name__}: {e}")
            return Answer(FAILED, (), at)


def _party(adults: int, kid_ages) -> tuple:
    ages = [int(a) for a in kid_ages or ()]
    if not 1 <= int(adults) <= 9 or any(not 0 <= a <= 17 for a in ages):
        raise ValueError("a party is 1 to 9 adults and kids 0 to 17")
    return int(adults), ages


def stays(*, checkin: date, checkout: date, adults: int, kid_ages=(), city: str = "", country: str = "", lat: float | None = None, lng: float | None = None,
          radius_m: int | None = None, family: str = "", cached_only: bool = False, rank: int = 0, wait: float | None = None) -> Answer | None:
    """Hotel rates for one room for the party, by a city and its country code or by a point and a radius in metres. `cached_only`: the kept answer or None, no call."""
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
            "occupancies": [{"adults": adults, "children": ages}], "limit": HOTEL_LIMIT, "timeout": STAY_ASK,
            "maxRatesPerHotel": 1}      # one rate a hotel: 104 KB instead of 7.8 MB at the same price (measured 2026-11-13, none of 27 hotels dearer)
    if margin() is not None:
        body["margin"] = margin()
    return _search("stays", "/hotels/rates", body, STAY_KEEP, STAY_TIMEOUT, family, read_stays, cached_only, rank=rank, wait=wait)


def flights(*, legs, adults: int, kid_ages=(), family: str = "", cached_only: bool = False, rank: int = 0, wait: float | None = None) -> Answer | None:
    """Flight offers for the legs in order (one: one way; two back and forth: a round trip), for the party. Kids under 2 fly as infants. `cached_only` as for stays."""
    adults, ages = _party(adults, kid_ages)
    legs = tuple(legs)
    if not legs:
        raise ValueError("at least one leg")
    round_trip = len(legs) == 2 and legs[0][0] == legs[1][1] and legs[0][1] == legs[1][0]
    body = {"legs": [{"origin": o.upper(), "destination": d.upper(), "date": day.isoformat(), **({"direction": ("OUTBOUND", "INBOUND")[i]} if round_trip else {})}
                     for i, (o, d, day) in enumerate(legs)],
            "adults": adults, "children": len([a for a in ages if a >= 2]), "childrenAges": [a for a in ages if a >= 2],
            "infants": len([a for a in ages if a < 2]), "infantAges": [a for a in ages if a < 2], "currency": "USD", "country": "US",
            "filters": {"showCheapestOfferOnly": True}}      # 11.6 MB down to 4.4 MB; the time is LiteAPI's either way
    return _search("flights", "/flights/rates", body, FLIGHT_KEEP, FLIGHT_TIMEOUT, family, read_flights, cached_only, stream=True, rank=rank, wait=wait)


def forget_stays() -> None:
    """Drop the kept stay searches (a prebook found a room gone): the next search asks LiteAPI again for today's rooms."""
    with _LOCK:
        for k in [k for k in _CACHE if k[0] == "/hotels/rates"]:
            del _CACHE[k]


@dataclass(frozen=True)
class Photo:
    url: str
    caption: str = ""


@dataclass(frozen=True)
class Para:
    lead: str      # the bold first words of a description paragraph ("Convenient Airport Shuttle Service"), or ""
    text: str


@dataclass(frozen=True)
class HotelRoom:
    name: str
    size_m2: float | None
    beds: tuple      # "Double bed", "King bed" ...
    sleeps: int | None
    photos: tuple    # https addresses of this room's own photos


@dataclass(frozen=True)
class HotelDetails:
    """What the hotel says about itself (F-275, D-860): LiteAPI's /data/hotel."""
    id: str
    name: str
    address: str
    stars: float | None
    rating: float | None
    review_count: int
    paragraphs: tuple
    photos: tuple          # Photo, the hotel's own, https only
    facilities: tuple
    rooms: tuple
    checkin: str
    checkout: str

    @property
    def description(self) -> str:
        return "\n\n".join((f"{p.lead}\n{p.text}" if p.lead and p.text else p.lead or p.text) for p in self.paragraphs)


@dataclass(frozen=True)
class Review:
    name: str
    date: str          # "2026-11-14"
    score: float | None
    type: str          # LiteAPI's traveller type: "couple", "extended_group" ...
    country: str
    headline: str
    pros: str
    cons: str


@dataclass(frozen=True)
class Category:
    name: str
    rating: float | None
    description: str


@dataclass(frozen=True)
class HotelReviews:
    """The newest reviews and LiteAPI's AI summary of all of them (F-275): the summary is a machine's reading of the guests' words and is labelled so."""
    items: tuple
    categories: tuple
    pros: tuple
    cons: tuple
    total: int


_LEAD = re.compile(r"^\s*(?:<p[^>]*>)?\s*<(?:strong|b)>(.*?)</(?:strong|b)>\s*(?:<br\s*/?>|:)?", re.S | re.I)


def _paragraphs(html) -> tuple:
    out = []
    for chunk in re.split(r"</p>|\n\n", str(html or "")):
        m = _LEAD.match(chunk)
        lead = strip_html(m.group(1)) if m else ""
        text_ = strip_html(chunk[m.end():] if m else chunk)
        if lead or text_:
            out.append(Para(lead.rstrip(":"), text_.lstrip(": ")))
    return tuple(out)


def _str(v) -> str:
    return " ".join(str(v).split()) if isinstance(v, (str, int, float)) else ""


def _bed(b) -> str:
    kind = _str(b.get("bedType"))
    return kind if "bed" in kind.lower() else f"{kind} bed"


def read_hotel(answer) -> HotelDetails | None:
    d = answer.get("data") if isinstance(answer, dict) else None
    if not isinstance(d, dict) or not d.get("name"):
        return None
    photos = tuple(Photo(u, _str(i.get("caption")).capitalize()) for i in d.get("hotelImages") or () if isinstance(i, dict) and (u := _https(i.get("urlHd")) or _https(i.get("url"))))
    rooms = []
    for r in d.get("rooms") or ():
        if not isinstance(r, dict) or not r.get("roomName"):
            continue
        beds = tuple(_bed(b) for b in r.get("bedTypes") or () if isinstance(b, dict) and b.get("bedType"))
        size = _num(r.get("roomSizeSquare")) if r.get("roomSizeUnit") == "m2" else None
        rooms.append(HotelRoom(_str(r["roomName"]), size, beds, int(_num(r.get("maxOccupancy")) or 0) or None,
                               tuple(u for p in r.get("photos") or () if isinstance(p, dict) and (u := _https(p.get("hd_url")) or _https(p.get("url"))))))
    times = d.get("checkinCheckoutTimes") if isinstance(d.get("checkinCheckoutTimes"), dict) else {}
    return HotelDetails(_str(d.get("id")), _str(d["name"]), _str(d.get("address")), _num(d.get("starRating")), _num(d.get("rating")), int(_num(d.get("reviewCount")) or 0),
                        _paragraphs(d.get("hotelDescription")), photos, tuple(_str(f) for f in d.get("hotelFacilities") or () if _str(f)), tuple(rooms),
                        _str(times.get("checkinStart") or times.get("checkin")), _str(times.get("checkout")))


def read_reviews(answer) -> HotelReviews | None:
    if not isinstance(answer, dict):
        return None
    items = tuple(Review(_str(r.get("name")), _str(r.get("date"))[:10], _num(r.get("averageScore")), _str(r.get("type")), _str(r.get("country")), _str(r.get("headline")),
                         _str(r.get("pros")), _str(r.get("cons"))) for r in answer.get("data") or () if isinstance(r, dict))
    sa = answer.get("sentimentAnalysis") if isinstance(answer.get("sentimentAnalysis"), dict) else {}
    cats = tuple(Category(_str(c.get("name")), _num(c.get("rating")), _str(c.get("description"))) for c in sa.get("categories") or () if isinstance(c, dict) and c.get("name"))
    return HotelReviews(items, cats, tuple(_str(x) for x in sa.get("pros") or () if _str(x)), tuple(_str(x) for x in sa.get("cons") or () if _str(x)), int(_num(answer.get("total")) or 0))


def _data_call(what: str, path: str, hotel_id: str, family: str, read):
    """A hotel's data (not a price): through the gate, counted against the budget, kept DATA_KEEP; None when there is no key, no id, no budget or no answer."""
    hotel_id = str(hotel_id or "").strip()
    if not key() or not hotel_id.isalnum():
        return None
    cache_key = (what, mode(), hotel_id)
    kept = _kept(cache_key, DATA_KEEP)
    if kept is not None:
        return kept
    with _Gate() as gate:
        if not gate.ok or not _spend(family):
            return None
        answer = _ask(what, path.format(id=quote(hotel_id)), None, STAY_TIMEOUT)
    got = read(answer) if answer is not None else None
    if got is not None:
        _keep(cache_key, got)
    return got


def hotel(hotel_id: str, family: str = "") -> HotelDetails | None:
    """The hotel's own photos, words, facilities and rooms (F-275), asked when a square is opened, not for every square."""
    return _data_call("hotel", "/data/hotel?hotelId={id}", hotel_id, family, read_hotel)


REVIEWS_SHOWN = 8


def reviews(hotel_id: str, family: str = "") -> HotelReviews | None:
    """The newest reviews and LiteAPI's sentiment summary (F-275)."""
    return _data_call("reviews", f"/data/reviews?hotelId={{id}}&limit={REVIEWS_SHOWN}&getSentiment=true", hotel_id, family, read_reviews)


def about(hotel_id: str, family: str = "") -> str:
    """The hotel's own description, HTML stripped; "" when there is no key, the budget is spent, or it could not be read."""
    h = hotel(hotel_id, family)
    return h.description if h else ""


# --- booking (F-233, D-480): prebook a stay's offer, then book it with the sandbox's own test card; never with a live key

@dataclass(frozen=True)
class Guest:
    first: str
    last: str
    email: str
    phone: str = ""          # a real booking sends the lead guest's mobile number too (LiteAPI's book marks the holder's phone required); the sandbox's card booking sends none
    remarks: str = ""        # what was asked of the hotel ("Quiet room. Arriving in the evening."), the guest's own picks from a fixed list


@dataclass(frozen=True)
class Prebook:
    prebook_id: str          # verbatim, never shown
    hotel_id: str
    room: str
    checkin: date
    checkout: date
    cents: int               # the final price, the whole stay, taxes included
    due_at_stay_cents: int   # fees the price leaves out, paid at the hotel
    refundable: bool
    changed: bool            # the price, the cancellation terms or the board moved since the search: the person is told before booking
    fetched: datetime
    secret_key: str = ""     # the payment form's key (usePaymentSdk), never saved, never logged, only given to the form on the page (F-274)
    transaction_id: str = ""  # what book pays with (TRANSACTION_ID); LiteAPI cannot give it back later, so it is saved at once
    pays_cents: int | None = None   # what the guest's card is charged: `sellingPriceToUser`, the price less a voucher's discount
    voucher_code: str = ""
    discount_cents: int = 0  # a voucher's discount (`voucherTotalAmount`), 0 without one
    tiers: tuple = ()        # LiteAPI's cancellation steps, in order: (the time, GMT, as it gave it, what cancelling after it costs in cents); () when it gives none
    remarks: str = ""        # the hotel's cancellation remarks and the offer's terms, LiteAPI's own words

    @property
    def charge_cents(self) -> int:
        """What is charged for the stay itself (the fees paid at the hotel are on top): the card's amount, else the price."""
        return self.cents if self.pays_cents is None else self.pays_cents


@dataclass(frozen=True)
class Booking:
    booking_id: str          # LiteAPI's, shown on the confirmation
    status: str              # "CONFIRMED"
    hotel: str
    hotel_id: str
    checkin: date
    checkout: date
    cents: int
    confirmation: str        # the hotel's confirmation code ("test" in the sandbox), "" when it has none yet
    refundable: bool
    sandbox: bool
    fetched: datetime


def _day_of(v) -> date:
    return date.fromisoformat(str(v)[:10])


def read_prebook(answer, fetched: datetime) -> Prebook:
    d = answer.get("data") if isinstance(answer, dict) and "error" not in answer else None
    if not isinstance(d, dict) or not d.get("prebookId") or d.get("currency") != "USD":
        raise Unreadable("no prebook")
    cents = _cents(d.get("price"))
    if cents is None:
        raise Unreadable("no price")
    rate = next((r for rt in d.get("roomTypes") or () for r in rt.get("rates") or ()), None) or {}
    fees = sum(_cents(f.get("amount")) or 0 for f in (rate.get("retailRate") or {}).get("taxesAndFees") or () if isinstance(f, dict) and f.get("included") is False)
    policy = rate.get("cancellationPolicies") or {}
    infos = [i for i in policy.get("cancelPolicyInfos") or () if isinstance(i, dict)]
    remarks = " ".join(str(x).strip() for x in [*(policy.get("hotelRemarks") or ()), d.get("termsAndConditions") or ""] if str(x).strip())
    pays = _cents(d.get("sellingPriceToUser"))
    return Prebook(str(d["prebookId"]), str(d.get("hotelId") or ""), str(rate.get("name") or ""), _day_of(d.get("checkin")), _day_of(d.get("checkout")), cents, fees,
                   policy.get("refundableTag") == "RFN", bool(d.get("priceDifferencePercent")) or bool(d.get("cancellationChanged")) or bool(d.get("boardChanged")), fetched,
                   str(d.get("secretKey") or ""), str(d.get("transactionId") or ""), pays, str(d.get("voucherCode") or ""), _cents(d.get("voucherTotalAmount")) or 0,
                   tuple((str(i.get("cancelTime") or ""), _cents(i.get("amount")) or 0) for i in infos if i.get("cancelTime")), remarks[:1200])


def read_booking(answer, fetched: datetime) -> Booking:
    d = answer.get("data") if isinstance(answer, dict) and "error" not in answer else None
    if not isinstance(d, dict) or not d.get("bookingId") or d.get("status") != "CONFIRMED" or d.get("currency") != "USD":
        raise Unreadable("no confirmed booking")
    cents = _cents(d.get("price"))
    if cents is None:
        raise Unreadable("no price")
    hotel = d.get("hotel") if isinstance(d.get("hotel"), dict) else {}
    return Booking(str(d["bookingId"]), "CONFIRMED", str(hotel.get("name") or d.get("hotelName") or ""), str(hotel.get("hotelId") or d.get("hotelId") or ""),
                   _day_of(d.get("checkin")), _day_of(d.get("checkout")), cents, str(d.get("hotelConfirmationCode") or ""), d.get("tag") == "RFN",
                   answer.get("sandbox") is True, fetched)


@dataclass(frozen=True)
class Cancelled:
    booking_id: str
    status: str              # "CANCELLED" (nothing charged) or "CANCELLED_WITH_CHARGES"
    refund_cents: int        # what comes back to the guest's card
    fee_cents: int           # what the cancellation cost
    fetched: datetime


def read_cancel(answer, fetched: datetime) -> Cancelled:
    d = answer.get("data") if isinstance(answer, dict) and "error" not in answer else None
    if not isinstance(d, dict) or not d.get("bookingId") or d.get("status") not in ("CANCELLED", "CANCELLED_WITH_CHARGES") or d.get("currency") != "USD":
        raise Unreadable("no cancellation")
    refund, fee = _cents(d.get("refund_amount")), _cents(d.get("cancellation_fee"))
    if refund is None or fee is None:
        raise Unreadable("no amounts")
    return Cancelled(str(d["bookingId"]), d["status"], refund, fee, fetched)


_BOOK_TURN = threading.BoundedSemaphore(1)      # one booking call in flight on the whole site: it holds one of the AT_ONCE gate places, never two (F-233 review)


def _allowed(body: dict | None) -> bool:
    """Which calls this key may make (D-480, reopened in D-840): a sandbox key all of them; a live key only where real booking is on (`real_booking`), and then never with the
    sandbox's own card: a book pays with TRANSACTION_ID alone and a prebook asks for the payment form (an ACC_CREDIT_CARD book would charge the LiteAPI account's own card)."""
    m = mode()
    if m == "sandbox":
        return True
    if m != "live" or not real_booking():
        return False
    body = body or {}
    pay = body.get("payment")
    return (pay is None or (isinstance(pay, dict) and pay.get("method") == "TRANSACTION_ID" and bool(pay.get("transactionId")))) and body.get("usePaymentSdk", True) is True


def _order(what: str, path: str, body: dict | None, timeout: float, family: str, read, gone=(), wait: float | None = None, base: str = BOOK_API, method: str = "") -> Answer:
    """One booking call: sandbox key only, one at a time across the site, through the gate and the booking budgets, never cached, never asked again by itself (the first may
    have gone through), and a failure logs the call and its HTTP status, never the body (it can hold a guest's email). `gone`: the HTTP statuses that mean the room or rate is
    no longer there. No `body`: a GET, or `method` (a PUT)."""
    if not _allowed(body):
        return Answer(OFF)
    if not can_search(family, True):
        return Answer(OVER)
    wait = TILE_WAIT if wait is None else wait
    if not _BOOK_TURN.acquire(timeout=wait):
        return Answer(BUSY)
    try:
        with _Gate(wait=wait) as gate:
            if not gate.ok:
                return Answer(BUSY)
            if not _spend(family, True):
                return Answer(OVER)
            at = now()
            try:
                status, ctype, raw = TRANSPORT(base + path, _headers(body), json.dumps(body).encode() if body is not None else None, timeout, *((method,) if method else ()))
                if len(raw) > MAX_BYTES:
                    raise Unreadable("too big")
                doc = read_body(ctype, raw)
            except Exception as e:      # a timeout, a dropped line, a body that is not JSON
                log.warning("LiteAPI %s not read (%s)", what, type(e).__name__)
                return Answer(FAILED, (), at)
            if status == 200:
                try:
                    return Answer(OK, (read(doc, at),), at)
                except Exception as e:      # a shape we never saw
                    log.warning("LiteAPI %s not read (%s)", what, type(e).__name__)
                    return Answer(FAILED, (), at)
            err = doc.get("error") if isinstance(doc, dict) else None
            code = err.get("code") if isinstance(err, dict) else None
            log.warning("LiteAPI %s not done (HTTP %s, code %s)", what, status, code)
            if code == 4002 and (body or {}).get("voucherCode"):      # LiteAPI's 4002 for a voucher it does not accept: said as that, not as a room taken
                return Answer(BAD_CODE, (), at)
            return Answer(GONE if status in gone or code in (2001, 4002) else DUPLICATE if code == 4005 else FAILED, (), at)
    finally:
        _BOOK_TURN.release()


def _the_booking(reference: str):
    """A reader for the lookup: exactly one booking whose clientReference is `reference`, else Unreadable (never another family's booking)."""
    def read(doc, fetched: datetime) -> Booking:
        items = doc.get("data") if isinstance(doc, dict) else None
        mine = [i for i in items if isinstance(i, dict) and i.get("clientReference") == reference] if isinstance(items, list) else []
        if len(mine) != 1:
            raise Unreadable("not exactly one booking for the reference")
        return read_booking({"data": mine[0], "sandbox": True}, fetched)
    return read


def booking_for(reference: str, family: str = "") -> Answer:
    """The booking LiteAPI made for our `clientReference` (GET /bookings?clientReference=): an Answer of one Booking, FAILED when it has none. For a book LiteAPI called a
    duplicate that we hold no row for: it may have been made by an answer we lost. Only a booking carrying exactly that reference counts."""
    return _order("booking lookup", "/bookings?" + urlencode({"clientReference": str(reference)}), None, STAY_TIMEOUT, family, _the_booking(str(reference)), base=API)


def prebook(offer_id: str, family: str = "", *, sdk: bool = False, voucher: str = "") -> Answer:
    """The stay's offer confirmed before anyone books: an Answer of one Prebook, GONE when the room sold out or the offer expired (search again, never retry the offer). `sdk`:
    ask for the payment form's `secretKey` and `transactionId` (what a live key always needs); `voucher`: a LiteAPI voucher code, BAD_CODE when LiteAPI does not accept it."""
    body = {"offerId": str(offer_id), "usePaymentSdk": bool(sdk), **({"voucherCode": str(voucher)} if voucher else {})}
    return _order("prebook", "/rates/prebook", body, PREBOOK_TIMEOUT, family, read_prebook, gone=(409,))


def book(prebook_id: str, guest: Guest, reference: str, family: str = "", transaction_id: str = "") -> Answer:
    """Book the prebooked room for `guest`. With a `transaction_id` (the payment form's, paid) the payment is `TRANSACTION_ID`; without one, and only with a sandbox key, it is the
    sandbox key's own test card (`ACC_CREDIT_CARD`: nothing is charged). A live key never sends the card method. `reference` is the idempotency key: the same one twice is
    DUPLICATE, never a second booking. An Answer of one Booking."""
    person = {"firstName": guest.first, "lastName": guest.last, "email": guest.email, **({"phone": guest.phone} if guest.phone else {})}
    pay = {"method": "TRANSACTION_ID", "transactionId": str(transaction_id)} if transaction_id else {"method": "ACC_CREDIT_CARD"}
    body = {"prebookId": str(prebook_id), "clientReference": str(reference), "holder": person, "guests": [{"occupancyNumber": 1, **person, **({"remarks": guest.remarks} if guest.remarks else {})}], "payment": pay}
    return _order("book", "/rates/book", body, BOOK_TIMEOUT, family, read_booking, gone=(410,))


def cancel(booking_id: str, family: str = "") -> Answer:
    """Cancel a booking (PUT /bookings/{id}): an Answer of one Cancelled saying what came back. Asking again answers the same; an unknown booking is FAILED."""
    return _order("cancel", "/bookings/" + quote(str(booking_id), safe=""), None, BOOK_TIMEOUT, family, read_cancel, method="PUT")
