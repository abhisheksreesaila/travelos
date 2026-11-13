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

Every call goes through one gate (F-229, D-445): at most AT_ONCE in flight across the site (the sandbox answered 429 when a page sent more), and a search
already in flight is joined, never asked twice: the second asker waits for the first one's Answer, and no second search is counted. A call carries a
`rank` (its square's place in the page's order, 0 the asked square): when a place at the gate comes free the lowest rank waiting goes, and a joiner lends
its rank to the search it joined. Flights are read from
the stream (`Accept: text/event-stream`, D-446): `rates-chunk` messages shaped like the plain answer, then `rates-complete`, which the sandbox does not
always send. The reader keeps each journey's cheapest offer seen and stops at `rates-complete`, STREAM_GRACE seconds after the first chunk of at least
BULK journeys, or at STREAM_CAP whatever happens (a watchdog cuts a line that hangs); an Answer cut short says `complete=False`, the cheapest found.
"""

import json
import logging
import os
import queue
import socket
import threading
import time
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
STAY_TIMEOUT, FLIGHT_TIMEOUT = 30, 40    # seconds: the sandbox took 2 to 17 s for stays and up to 16 s for flights; on 2026-11-12 evening stays took up to 33 s
STAY_ASK = 10                            # seconds LiteAPI is asked to answer a stay search in (its `timeout`; the sandbox does not always keep it)
HOTEL_LIMIT = 30
MAX_BYTES = 32 * 1024 * 1024             # a round trip's answer was 9 MB (386 journeys, 1,647 offers)
MAX_CENTS = 10_000_000
AT_ONCE = 3                              # calls in flight across the site (F-229): the sandbox answered 429 to a page's 6
GATE_WAIT = 60                           # seconds a call waits for its turn at the gate before it fails (not kept: asked again, it searches)
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


def _send(url: str, headers: dict, body: bytes | None, timeout: float):
    """(status, content type, the body, at most MAX_BYTES + 1 of it; or a stream's lines, `_Lines`). An HTTP error is an answer, not an exception; a redirect
    is refused (it would carry the key)."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
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
    _TURNS = _Turns(AT_ONCE)


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


def can_search(family: str) -> bool:
    """Whether `family` (and the site) still has searches left today: background work asks before it starts (F-229)."""
    day, who = _day(), family or "guest"
    with community.connect() as db:
        mine = db.conn.execute(text("SELECT COALESCE(SUM(n), 0) FROM liteapi_searches WHERE day = :d AND family = :f"), {"d": day, "f": who}).scalar()
        everyone = db.conn.execute(text("SELECT COALESCE(SUM(n), 0) FROM liteapi_searches WHERE day = :d"), {"d": day}).scalar()
    return mine < PER_FAMILY_A_DAY and everyone < A_DAY


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
        status, ctype, raw = TRANSPORT(API + path, _headers(body), json.dumps(body).encode() if body is not None else None, timeout)
        if len(raw) > MAX_BYTES:
            raise Unreadable(f"over {MAX_BYTES} bytes")
        if status != 200:
            raise Unreadable(f"HTTP {status}")
        return read_body(ctype, raw)
    except Exception as e:      # a timeout, a 401, an error body: say so once
        _say(what, e)
        return None


def _stream(path: str, body: dict, at: datetime):
    """Flights read from the stream: (each journey's cheapest offer, whether the stream said it was complete). Raises on a failure or a shape we never saw.
    The transport and its lines run on their own thread, so the deadlines hold even while a read hangs; at the end the line is cut."""
    started = time.monotonic()
    got: queue.Queue = queue.Queue()
    stop = threading.Event()
    held = {}

    def pump():
        try:
            status, ctype, lines = TRANSPORT(API + path, _headers(body, "text/event-stream"), json.dumps(body).encode(), STREAM_CAP)
            held["lines"] = lines
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

    threading.Thread(target=pump, daemon=True, name="liteapi-stream").start()
    flights, size, msg, bulk_at, complete = {}, 0, [], None, False

    def take(event, payload):
        nonlocal complete
        if event == "error":
            raise Unreadable("the stream said error")
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
    if not flights:
        raise Unreadable(f"no flights in the stream after {time.monotonic() - started:.1f} s")
    return tuple(sorted(flights.values(), key=lambda f: (f.cents, f.id))), complete


class _Flight:
    """A search in flight: the first asker sets `answer`, then `done`. `rank` is the most wanted asker's (a joiner can lower it while it waits at the gate)."""

    def __init__(self, rank=0):
        self.done, self.answer, self.rank = threading.Event(), None, rank


class _Turns:
    """The gate's AT_ONCE places. A waiting call goes in rank order (lowest first), then by arrival; its rank is read each time a place comes free."""

    def __init__(self, places):
        self.free, self.waiting, self.cond, self.seq = places, [], threading.Condition(), 0

    def take(self, rank_of, timeout) -> bool:
        with self.cond:
            self.seq += 1
            me = (self.seq, rank_of)
            self.waiting.append(me)
            end = time.monotonic() + timeout
            try:
                while True:
                    if self.free > 0 and min(self.waiting, key=lambda w: (w[1](), w[0])) is me:
                        self.free -= 1
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
            self.free += 1
            self.cond.notify_all()

    def nudge(self) -> None:
        with self.cond:
            self.cond.notify_all()


_TURNS = _Turns(AT_ONCE)


class _Gate:
    """One of the AT_ONCE places in flight, in rank order; False when none came free within GATE_WAIT."""

    def __init__(self, rank_of=lambda: 0):
        self.rank_of = rank_of

    def __enter__(self):
        self.turns = _TURNS
        self.ok = self.turns.take(self.rank_of, GATE_WAIT)
        return self.ok

    def __exit__(self, *exc):
        if self.ok:
            self.turns.give()


def _search(what: str, path: str, body: dict, keep: timedelta, timeout: float, family: str, read, cached_only: bool = False, stream: bool = False,
            rank: int = 0) -> Answer | None:
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
        flying.done.wait(GATE_WAIT + max(timeout, STREAM_CAP) + 5)      # the same search is on its way: its answer is ours, and no second search is counted
        if flying.answer is None:
            return Answer(FAILED, (), now())
        if flying.answer.status != OVER:
            return flying.answer
        # the first asker's budget was spent, not ours: ask on our own
    found = Answer(FAILED, (), now())
    try:
        called = _call(what, path, body, timeout, family, read, stream, flying)
        if called is not None and called.status != OVER:      # no turn at the gate, or a spent budget, is not the answer: asked again, it searches
            _keep(cache_key, called)
        found = called or found
    finally:
        flying.answer = found
        with _LOCK:
            if _FLYING.get(cache_key) is flying:
                del _FLYING[cache_key]
        flying.done.set()
    return found


def _call(what, path, body, timeout, family, read, stream, flying) -> Answer | None:
    """The Answer, or None when no place at the gate came free in time."""
    with _Gate(lambda: flying.rank) as through:
        if not through:
            _say(what, "no turn at the gate")
            return None
        if not _spend(family):
            return Answer(OVER)
        at = now()
        try:
            if stream:
                items, complete = _stream(path, body, at)
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
          radius_m: int | None = None, family: str = "", cached_only: bool = False, rank: int = 0) -> Answer | None:
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
            "occupancies": [{"adults": adults, "children": ages}], "limit": HOTEL_LIMIT, "timeout": STAY_ASK}
    return _search("stays", "/hotels/rates", body, STAY_KEEP, STAY_TIMEOUT, family, read_stays, cached_only, rank=rank)


def flights(*, legs, adults: int, kid_ages=(), family: str = "", cached_only: bool = False, rank: int = 0) -> Answer | None:
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
    return _search("flights", "/flights/rates", body, FLIGHT_KEEP, FLIGHT_TIMEOUT, family, read_flights, cached_only, stream=True, rank=rank)


def about(hotel_id: str, family: str = "") -> str:
    """The hotel's own description, HTML stripped; "" when there is no key, the budget is spent, or it could not be read."""
    hotel_id = str(hotel_id or "").strip()
    if not key() or not hotel_id.isalnum():
        return ""
    cache_key = ("about", mode(), hotel_id)
    kept = _kept(cache_key, DATA_KEEP)
    if kept is not None:
        return kept
    with _Gate() as through:
        if not through or not _spend(family):
            return ""
        answer = _ask("hotel", "/data/hotel?" + urlencode({"hotelId": hotel_id}), None, STAY_TIMEOUT)
    words = strip_html(answer["data"].get("hotelDescription")) if isinstance(answer, dict) and isinstance(answer.get("data"), dict) else ""
    if words:
        _keep(cache_key, words)
    return words
