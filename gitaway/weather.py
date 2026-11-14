"""Real weather for a real trip (F-203): MET Norway's forecast for the days it covers, and NOAA's climate normals ("typical late December")
before it opens. Nothing here is invented: a day GitAway knows nothing about shows nothing.

    forecast(station) -> Forecast | None                   MET Norway Locationforecast 2.0 compact at one of the table's stations, cached
    forecast_days(fc, tz, now) -> {date: Day}               its local days: high and low (deg F), condition, words, inches, mph
    station_named(text) / station(id)                      the NOAA climate-normals station for a destination's name (normals.json), or None
    normal_day(station, date) -> Day                        that station's typical weather for the date, labelled "Typical late December · not a forecast yet"
    trip_weather(trip) -> TripWeather                       one Day (or None) per day of a trip: the forecast where it reaches, else typical
    notes(tw) -> [(text, link)]                             the lines a page shows under a trip's weather; a line with a link is a link as a whole
    sample(trip) -> bool                                    the showcase's own sample trip, the one trip whose weather is sample data

MET Norway's terms (https://api.met.no/doc/TermsOfService, the Locationforecast HowTo and FAQ) and how this module keeps them:
  - a person in charge must read and accept the terms before the service is used: nothing is asked until MET_NORWAY_TERMS_ACCEPTED=1;
  - an identifying User-Agent: "GitAway/1.0 <the site's address> <GITAWAY_CONTACT_EMAIL, when set>" (the site's /privacy page names the contact);
  - at most four decimals in a coordinate, https only, gzip accepted; GitAway never follows a redirect (MET's API does not send them; one is logged by host);
  - never ask again before the Expires header (held to 12 hours at most), and not within three hours (outside the Nordic area the forecast changes every
    six hours, and the FAQ asks for at least half of that); then ask with If-Modified-Since set to exactly the Last-Modified we were given, and keep
    our copy on 304;
  - far under 20 requests a second for the whole site: one gate for the process (`GATE`); a 429 shuts it for ten minutes, a 403 for an hour;
  - a 203 (the product is deprecated) is logged as a warning, so whoever reads the logs moves to the successor.
Only a NOAA station's or a catalog place's coordinates are ever sent, never a family's address. Everything MET answers is untrusted: an answer that
does not read cleanly (too big, too deep, absurd times) is a failed call, and the place is not asked again for FAIL_WAIT.
The data are MET Norway's (CC BY 4.0 and NLOD 2.0) and GitAway's days are worked out from them: show `credit(...)` (linked to `CREDIT_URL`) wherever a
forecast shows (`credit`, which names the station). Our server asks, never a browser, so MET Norway sees our server and a place, not a family.

`TRANSPORT` is the one function that touches the network, (url, headers, timeout) -> (status, headers, body bytes); tests replace it.
"""

import http.client
import json
import logging
import math
import os
import re
import socket
import threading
import time as clock
import zlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from gitaway import auth, catalog, geo, zones
from gitaway.deadline import REDIRECTS, get as get_by_deadline, handshake
from gitaway.geo import Gate

log = logging.getLogger("gitaway.weather")

HOST = "api.met.no"
API = f"https://{HOST}/weatherapi/locationforecast/2.0/compact"
TIMEOUT = 3.0                       # one deadline for all a page waits on MET: the place's lock, the gate, the lookup, the call and the answer
MIN_REPEAT = timedelta(hours=3)     # Locationforecast FAQ: outside the Nordic area wait at least half of its six-hour update interval
EXPIRES_MAX = timedelta(hours=12)   # an Expires further off than this is held to it: a far-off date must not freeze a place
FAIL_WAIT = timedelta(minutes=5)    # after a failed call, before anyone asks for that place again
KEEP = timedelta(hours=24)          # a forecast we hold is still shown, with its time, for this long when later calls fail
REFUSED = {429: 600, 403: 3600}     # seconds the gate stays shut after MET says too many requests, or refuses us
MAX_BYTES = 2 * 1024 * 1024
MAX_STEPS = 200                     # MET's compact forecast has about 90 steps; more are not read
STEPS_FROM, STEPS_TO = timedelta(days=1), timedelta(days=12)        # a step outside now - 1 day .. now + 12 days is dropped
MADE_FROM, MADE_TO = timedelta(days=2), timedelta(hours=1)          # a forecast "made" outside now - 2 days .. now + 1 hour is refused
GATE = Gate(0.2)                    # at most five calls a second from the whole process; a page waits for its turn only until its deadline
MIN_CALL = 1.0                      # a call is not started with less time than this left: it would only time out and keep the place waiting FAIL_WAIT

FORECAST, NORMAL = "forecast", "normal"
CREDIT_URL = "https://docs.api.met.no/doc/License"   # MET's licensing page: the source, CC BY 4.0 and NLOD 2.0

WET_MM = 0.5         # less precipitation than this in a part of the day does not make it wet
WINDY_MS = 9.0       # about 20 mph of sustained wind makes a dry day "Windy"
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+")
_SYMBOL = re.compile(r"[a-z_]{2,48}")


# ---- what a forecast holds --------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Point:
    """One step of MET's timeseries, kept small: only what GitAway reads."""
    at: datetime                 # UTC
    temp_c: float | None
    wind_ms: float | None
    cloud: float | None          # % of the sky
    hours: int                   # how long its period lasts: 1 (next_1_hours), 6 (next_6_hours) or 0 (the last step has none)
    symbol: str                  # the period's symbol_code, "" when none
    precip_mm: float             # the period's precipitation
    tmax_c: float | None = None  # six-hour periods only
    tmin_c: float | None = None


@dataclass(frozen=True)
class Forecast:
    updated: datetime            # when MET made it (UTC)
    points: tuple


@dataclass(frozen=True)
class Day:
    """One day of a trip as GitAway shows it: MET's forecast, or the place's climate normals (kind NORMAL, with `label` saying so)."""
    date: date
    kind: str                    # FORECAST or NORMAL
    high_f: int
    low_f: int
    condition: str               # sun | cloud | rain | snow | wind
    word: str                    # "Light snow", "Partly cloudy, snow late"; for normals what the days are usually like
    precip_in: float | None = None   # forecast: the day's rain or melted snow
    wind_mph: int | None = None      # forecast: the strongest wind of the day
    label: str = ""                  # normals: "Typical late December · not a forecast yet"
    wet_pct: int | None = None       # normals: the station's chance of a wet day, in percent (the matrix's day cells; a forecast day has none)


# ---- asking MET Norway --------------------------------------------------------------------------------------------------------

def live() -> bool:
    """May GitAway ask MET Norway at all? Only once a person in charge has read and accepted their terms and set MET_NORWAY_TERMS_ACCEPTED=1."""
    return os.getenv("MET_NORWAY_TERMS_ACCEPTED", "").strip() == "1"


def user_agent() -> str:
    """Who is asking, as MET's terms want it: the app and its version, the site (its /privacy page has our contact) and the contact address."""
    from gitaway.blogbutton import base_url      # GITAWAY_PUBLIC_URL when it is a plain https address, else https://gitaway.me
    mail = os.getenv("GITAWAY_CONTACT_EMAIL", "").strip()
    ua = f"GitAway/1.0{'' if auth.production() else ' (test)'} {base_url()}"
    return f"{ua} {mail}" if _EMAIL.fullmatch(mail) else ua


def _lookup(host, deadline) -> tuple:
    """Every address of the host, in the resolver's order, looked up in a thread of its own so that a slow resolver cannot hold a page past its
    deadline (a clock.monotonic time)."""
    found = {}

    def look():
        try:
            found["ips"] = tuple(dict.fromkeys(info[4][0] for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
        except (OSError, IndexError) as e:
            found["error"] = e

    t = threading.Thread(target=look, daemon=True, name="met-lookup")
    t.start()
    t.join(max(0.0, deadline - clock.monotonic()))
    if not found.get("ips"):
        raise TimeoutError("looking up api.met.no took too long") if t.is_alive() else OSError("api.met.no could not be found")
    return found["ips"]


class _MetTLS(http.client.HTTPSConnection):
    """A TLS connection to api.met.no's looked-up addresses, each tried in turn within the deadline, a dead one listed first getting only its share of
    the time; the certificate must be api.met.no's (`deadline.handshake`)."""
    ips, deadline = (), 0.0

    def connect(self):
        raw, failed = None, None
        for i, ip in enumerate(self.ips):
            left = self.deadline - clock.monotonic()
            if left <= 0:
                break
            try:
                raw = socket.create_connection((ip, self.port), left / (len(self.ips) - i))
                break
            except OSError as e:
                failed = e
        if raw is None:
            raise failed or TimeoutError("no address of api.met.no answered in time")
        handshake(self, raw, self._context, self.deadline)


def _connection(ips, deadline, port=443, context=None):
    """The connection `_http` uses. Tests point `port` and `context` (a trusted test CA) at a local TLS server."""
    conn = _MetTLS(HOST, port, timeout=max(0.05, deadline - clock.monotonic()), context=context)
    conn.ips, conn.deadline = tuple(ips), deadline
    return conn


CONNECTION = _connection        # tests: (ips, deadline) -> a connection to a local stand-in


def _host(url) -> str:
    try:
        return urlsplit(str(url)).hostname or "nowhere"
    except ValueError:
        return "nowhere"


def _http(url, headers, timeout):
    """One GET from https://api.met.no and nowhere else, all of it (lookup, connect, handshake, answer) within `timeout` seconds: (status, headers, body).
    Any other address raises ValueError before anything is sent; a redirect is never followed (only its host is logged). The deadline is kept by
    gitaway/deadline.py's watchdog, because a socket timeout bounds only one wait and a server dripping a byte at a time would hold the page."""
    try:
        parts = urlsplit(url)
        bad = parts.scheme != "https" or parts.hostname != HOST or parts.port is not None or parts.username is not None or parts.password is not None
    except ValueError:
        bad = True
    if bad:
        raise ValueError("GitAway asks only https://api.met.no")
    deadline = clock.monotonic() + timeout
    conn = CONNECTION(_lookup(HOST, deadline), deadline)
    status, got, body = get_by_deadline(conn, (parts.path or "/") + (f"?{parts.query}" if parts.query else ""), headers, deadline, MAX_BYTES + 1)
    if status in REDIRECTS:          # a 304 is an answer (nothing changed), not one of these
        log.warning("MET Norway answered %s towards %s; GitAway does not follow redirects", status, _host(got.get("location", "")))
    return status, got, body


TRANSPORT = _http


@dataclass
class _Entry:
    forecast: Forecast | None
    fetched: datetime | None     # when we last knew that forecast to be MET's current one
    next_ask: datetime           # nobody asks MET for this place before then
    modified: str = ""           # its Last-Modified, sent back as If-Modified-Since


_CACHE: dict = {}                # url -> _Entry; a url is a station's or a catalog place's, so there are at most a few dozen
_LOCK = threading.Lock()
_ASKING: dict = {}               # url -> the lock one asker holds, so two pages never ask for the same place at once


def clear():
    with _LOCK:
        _CACHE.clear()
        _ASKING.clear()


def _number(v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        return None
    return float(v)


def _query(lat, lon, altitude=None) -> str | None:
    lat, lon = _number(lat, -90, 90), _number(lon, -180, 180)
    if lat is None or lon is None:
        return None
    q = f"lat={round(lat, 4) + 0.0:.4f}&lon={round(lon, 4) + 0.0:.4f}"     # at most four decimals (MET's terms; + 0.0 turns -0.0 into 0.0)
    alt = _number(altitude, -500, 9000)
    return q + (f"&altitude={int(alt)}" if alt is not None else "")


def forecast(st, *, timeout=TIMEOUT) -> Forecast | None:
    """MET's forecast at one of the table's NOAA stations (at its altitude, which makes the temperatures more exact), or None: not switched on, not a
    station of the table (so no caller can make the cache grow or send other coordinates), or no answer within `timeout` seconds in all. Answered
    from the cache until MET's Expires (and three hours) have passed."""
    q = _query(st.lat, st.lon, st.elev) if isinstance(st, Station) and station(st.id) == st else None
    if q is None:
        return None
    url = f"{API}?{q}"
    entry, now = _cached(url), catalog.now_utc()
    if (entry and now < entry.next_ask) or not live():
        return _held(entry, now)
    deadline = geo._clock() + timeout            # the gate's own clock, so its wait and ours are counted the same way
    with _LOCK:
        lock = _ASKING.setdefault(url, threading.Lock())
    if not lock.acquire(timeout=max(0.0, deadline - geo._clock())):
        return _held(entry, now)
    try:
        entry, now = _cached(url), catalog.now_utc()      # another page may have asked while we waited
        if entry and now < entry.next_ask:
            return _held(entry, now)
        if not GATE.wait(deadline):
            return _held(entry, now)
        left = deadline - geo._clock()
        if left < MIN_CALL:       # too late to finish: show what we hold and let the next page ask, rather than fail and block the place
            return _held(entry, now)
        return _ask(url, entry, now, left)
    finally:
        lock.release()
        with _LOCK:
            if url not in _CACHE:
                _ASKING.pop(url, None)       # nothing was asked or kept: leave no lock behind


def _cached(url):
    with _LOCK:
        return _CACHE.get(url)


def _held(entry, now):
    """The forecast we hold for a place, unless it is more than a day old."""
    if entry is None or entry.forecast is None or entry.fetched is None or now - entry.fetched > KEEP:
        return None
    return entry.forecast


def _ask(url, entry, now, timeout):
    headers = {"User-Agent": user_agent(), "Accept-Encoding": "gzip"}
    if entry and entry.forecast and entry.modified:
        headers["If-Modified-Since"] = entry.modified
    try:
        status, h, raw = TRANSPORT(url, headers, timeout)
        h = {str(k).lower(): v for k, v in (h or {}).items()}
    except Exception as e:  # offline, slow or refused: try again in a few minutes
        log.warning("MET Norway forecast failed: %s", type(e).__name__)
        return _failed(url, entry, now)
    try:
        if status == 304 and entry and entry.forecast:
            return _keep(url, entry.forecast, now, h, entry.modified)
        if status in REFUSED:
            GATE.back_off(REFUSED[status])
            log.warning("MET Norway refused the forecast (%s): %s", status,
                        "too many requests" if status == 429 else "check the User-Agent and that the terms are kept")
            return _failed(url, entry, now)
        if status not in (200, 203):
            log.warning("MET Norway forecast answered %s", status)
            return _failed(url, entry, now)
        if status == 203:
            log.warning("MET Norway answered 203: Locationforecast 2.0 is deprecated and will be switched off; move to its successor")
        return _keep(url, parse(json.loads(_unzip(raw, str(h.get("content-encoding", "")))), now), now, h, h.get("last-modified", ""))
    except Exception as e:  # everything MET sends is untrusted: an answer that does not read cleanly (too deep, absurd numbers or times) is a failed call
        log.warning("MET Norway forecast could not be read: %s", type(e).__name__)
        return _failed(url, entry, now)


def _unzip(raw: bytes, encoding: str) -> bytes:
    if len(raw) > MAX_BYTES:
        raise ValueError("too large")
    if "gzip" not in encoding.lower():
        return raw
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = d.decompress(raw, MAX_BYTES + 1)
    if len(out) > MAX_BYTES or d.unconsumed_tail:
        raise ValueError("too large")
    return out


def _expires(h, now) -> datetime:
    """MET's Expires, held between now and now + 12 hours whatever it says; unreadable means now."""
    try:
        at = parsedate_to_datetime(h.get("expires", ""))
        at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
        return min(max(at, now), now + EXPIRES_MAX)
    except Exception:  # absurd dates overflow in several ways
        return now


def _keep(url, fc, now, h, modified):
    _store(url, _Entry(fc, now, max(_expires(h, now), now + MIN_REPEAT), modified if isinstance(modified, str) else ""))
    return fc


def _failed(url, entry, now):
    held = _held(entry, now)
    _store(url, _Entry(held, entry.fetched if held else None, now + FAIL_WAIT, entry.modified if held else ""))
    return held


def _store(url, entry):
    with _LOCK:
        _CACHE[url] = entry


# ---- reading MET's answer -------------------------------------------------------------------------------------------------------

def _utc(text) -> datetime:
    at = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    if at.tzinfo is None:
        raise ValueError("a time without a zone")
    return at.astimezone(timezone.utc)


def _point(step) -> Point:
    at, data = _utc(step["time"]), step["data"]
    now = data["instant"]["details"]
    n1, n6 = data.get("next_1_hours"), data.get("next_6_hours")
    period, hours = (n1, 1) if isinstance(n1, dict) else (n6, 6) if isinstance(n6, dict) else ({}, 0)
    details = period.get("details") if isinstance(period.get("details"), dict) else {}
    symbol = (period.get("summary") or {}).get("symbol_code") if isinstance(period.get("summary"), dict) else ""
    six = hours == 6
    return Point(at, _number(now.get("air_temperature"), -90, 60), _number(now.get("wind_speed"), 0, 120), _number(now.get("cloud_area_fraction"), 0, 100),
                 hours, symbol if isinstance(symbol, str) and _SYMBOL.fullmatch(symbol) else "", _number(details.get("precipitation_amount"), 0, 500) or 0.0,
                 _number(details.get("air_temperature_max"), -90, 60) if six else None, _number(details.get("air_temperature_min"), -90, 60) if six else None)


def parse(doc, now: datetime) -> Forecast:
    """A Forecast from MET's compact GeoJSON, read as untrusted: at most MAX_STEPS steps, only those between a day before `now` and twelve days after,
    and the forecast must have been made between two days before `now` and an hour after. Raises ValueError when nothing usable is left."""
    props = doc["properties"]
    made = _utc(props["meta"]["updated_at"])
    if not now - MADE_FROM <= made <= now + MADE_TO:
        raise ValueError("a forecast made far from now")
    points = []
    for step in props["timeseries"][:MAX_STEPS]:
        try:
            p = _point(step)
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            continue
        if now - STEPS_FROM <= p.at <= now + STEPS_TO:
            points.append(p)
    if not points:
        raise ValueError("no forecast steps")
    return Forecast(made, tuple(sorted(points, key=lambda p: p.at)))


def updated_text(fc: Forecast, tz) -> str:
    """When MET made the forecast, in the place's own time: "6:10 AM"."""
    at = fc.updated.astimezone(_zone(tz))
    return f"{at.hour % 12 or 12}:{at.minute:02d} {'AM' if at.hour < 12 else 'PM'}"


# ---- the days of a forecast -----------------------------------------------------------------------------------------------------

def _zone(tz):
    try:
        return ZoneInfo(str(tz or zones.DEFAULT))
    except (ValueError, KeyError, OSError):
        return ZoneInfo(zones.DEFAULT)


def _f(c) -> int:
    return round(c * 9 / 5 + 32)


def _inches(mm) -> float:
    return round(mm / 25.4, 2)


def _kind(symbol: str) -> str:
    """The family a MET symbol code belongs to: snow, sleet, rain, fog, cloudy, partly, clear, or "" (unknown)."""
    s = symbol.split("_")[0]
    for word, kind in (("snow", "snow"), ("sleet", "sleet"), ("rain", "rain")):
        if word in s:
            return kind
    return {"fog": "fog", "cloudy": "cloudy", "partlycloudy": "partly", "fair": "clear", "clearsky": "clear"}.get(s, "")


@dataclass
class _Acc:
    temps: list = field(default_factory=list)
    winds: list = field(default_factory=list)
    day_winds: list = field(default_factory=list)
    clouds: list = field(default_factory=list)
    covered: int = 0
    mm: dict = field(default_factory=lambda: defaultdict(float))                                 # part of the day -> mm
    kinds: dict = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))          # part -> symbol family -> hours
    thunder: dict = field(default_factory=lambda: defaultdict(int))


def _slices(points):
    """Every hour the forecast's periods cover, once each: (UTC start, symbol, mm). In the hourly part each step's next_1_hours, after it each six-hour
    period, with its precipitation spread over its hours. (A step has periods of several lengths; only the shortest is counted.)"""
    out, until = [], None
    for p in points:
        if not p.hours or (until is not None and p.at < until):
            continue
        out += [(p.at + timedelta(hours=k), p.symbol, p.precip_mm / p.hours) for k in range(p.hours)]
        until = p.at + timedelta(hours=p.hours)
    return out


def _part(hour: int) -> str:
    return "early" if hour < 7 else "day" if hour < 19 else "late"


def _wet_kind(kinds, temps) -> str:
    snow, rain = kinds["snow"] + kinds["sleet"], kinds["rain"]
    if snow or rain:
        return "snow" if snow >= rain else "rain"
    return "snow" if temps and sum(temps) / len(temps) <= 1 else "rain"


def _sky(kinds, clouds):
    """(condition, word) of a dry daytime from its symbols (or, with none, its cloud cover)."""
    total = sum(kinds.values())
    if not total:
        avg = sum(clouds) / len(clouds) if clouds else 0
        return ("cloud", "Cloudy") if avg >= 70 else ("cloud", "Partly cloudy") if avg >= 30 else ("sun", "Sunny")
    clear = kinds["clear"]
    if clear * 2 >= total:
        return "sun", "Sunny" if clear == total else "Mostly sunny"
    grey = {"Partly cloudy": kinds["partly"], "Cloudy": kinds["cloudy"] + kinds["snow"] + kinds["sleet"] + kinds["rain"], "Fog": kinds["fog"]}
    return "cloud", max(grey, key=grey.get)


def _condition(a: _Acc):
    day = a.kinds["day"]
    if a.mm["day"] >= WET_MM:
        kind = _wet_kind(day, a.temps)
        noun = "sleet" if kind == "snow" and day["sleet"] > day["snow"] else kind
        size = "Light " if a.mm["day"] < 2.5 else "Heavy " if a.mm["day"] >= 10 else ""
        word = (size + noun) if size else noun.capitalize()
        return kind, word + (" and thunder" if a.thunder["day"] else "")
    condition, word = _sky(day, a.clouds)
    if a.day_winds and max(a.day_winds) >= WINDY_MS:
        condition, word = "wind", "Windy"
    wet = [(_wet_kind(a.kinds[p], a.temps), p) for p in ("early", "late") if a.mm[p] >= WET_MM]
    if len(wet) == 2 and wet[0][0] == wet[1][0]:
        word += f", {wet[0][0]} early and late"
    elif wet:
        word += ", " + ", ".join(f"{k} {p}" for k, p in wet)
    return condition, word


def forecast_days(fc: Forecast | None, tz, now: datetime) -> dict:
    """{local date: Day} for every day of the forecast that is covered well enough to call: most of a future day, most of what is left of today."""
    if fc is None:
        return {}
    zone, acc = _zone(tz), {}

    def day(d):
        return acc.setdefault(d, _Acc())

    for p in fc.points:
        local = p.at.astimezone(zone)
        a = day(local.date())
        if p.temp_c is not None:
            a.temps.append(p.temp_c)
        if p.wind_ms is not None:
            a.winds.append(p.wind_ms)
            if _part(local.hour) == "day":
                a.day_winds.append(p.wind_ms)
        if p.cloud is not None and _part(local.hour) == "day":
            a.clouds.append(p.cloud)
        if p.hours == 6:      # a six-hour period's high and low belong to the day its middle falls on
            middle = day((p.at + timedelta(hours=3)).astimezone(zone).date())
            middle.temps += [v for v in (p.tmax_c, p.tmin_c) if v is not None]
    for start, symbol, mm in _slices(fc.points):
        local = start.astimezone(zone)
        a, part = day(local.date()), _part(local.hour)
        a.covered += 1
        a.mm[part] += mm
        if kind := _kind(symbol):
            a.kinds[part][kind] += 1
        if "thunder" in symbol:
            a.thunder[part] += 1
    out = {}
    for d, a in sorted(acc.items()):
        start = datetime.combine(d, time(0), zone).astimezone(timezone.utc)
        end = datetime.combine(d + timedelta(days=1), time(0), zone).astimezone(timezone.utc)
        left = (end - max(start, now)).total_seconds() / 3600
        if left < 1 or not a.temps or a.covered < 0.75 * left:
            continue
        condition, word = _condition(a)
        out[d] = Day(d, FORECAST, _f(max(a.temps)), _f(min(a.temps)), condition, word, _inches(sum(a.mm.values())),
                     round(max(a.winds) * 2.23694) if a.winds else None)
    return out


# ---- typical weather: NOAA's climate normals ------------------------------------------------------------------------------------
# gitaway/normals.json is made by scripts/build_normals.py from NOAA NCEI's U.S. Climate Normals 1991-2020 (public domain): per station, for the
# early, mid and late part of each month, the normal high and low (deg F), the chance of a wet day (at least 0.01 in) and, where the station
# measures it, of a snowy one (at least 0.1 in). Nothing is fetched while the app runs.

NORMALS = Path(__file__).with_name("normals.json")
CATALOG_STATIONS = {"la": "USW00093134", "sd": "USW00023188", "hi": "USW00022521", "nyc": "USW00094728"}   # the stations of the catalog's four places
_THIRDS = ("early", "mid", "late")
_STATES = {   # US state names and their postal codes, to read a destination's ", Florida" or ", FL"
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY"}
_CODES = set(_STATES.values())
_COUNTRY = ("usa", "us", "u s", "u s a", "united states", "united states of america")


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    lat: float
    lon: float
    elev: int            # metres
    tz: str
    states: tuple        # the postal codes of the states it stands for ("CA", "NV" for South Lake Tahoe)
    aliases: tuple       # destination names that mean this station, lower case
    normals: tuple       # 36 x (high F, low F, wet-day %, snowy-day % or None)


_STATIONS: tuple = ()


def stations() -> tuple:
    global _STATIONS
    if not _STATIONS:
        table = json.loads(NORMALS.read_text(encoding="utf-8"))["stations"]
        _STATIONS = tuple(Station(sid, s["name"], s["lat"], s["lon"], s["elev"], s["tz"], tuple(s["states"]), tuple(s["aliases"]),
                                  tuple(tuple(n) for n in s["n"])) for sid, s in table.items())
    return _STATIONS


def station(sid: str) -> Station | None:
    return next((s for s in stations() if s.id == sid), None)


def third(day: int) -> int:
    """Which third of its month a day of the month falls in: 0 (days 1-10, "early"), 1 (11-20, "mid") or 2 (21 to the end, "late"). The one rule for
    the table's 36 periods; scripts/build_normals.py builds them with it."""
    return 0 if day <= 10 else 1 if day <= 20 else 2


def _tokens(text) -> list:
    """A destination's words, in their own case, and its commas: "Disneyland, Anaheim, CA" -> ["Disneyland", ",", "Anaheim", ",", "CA"]."""
    return re.findall(r"[A-Za-z0-9]+|,", str(text or ""))


def _starts(tokens, alias) -> int:
    """How many tokens a station's name takes from the start of a destination (commas between its words are allowed: "Washington, D.C."), or 0."""
    i = 0
    for want in alias.split():
        while i < len(tokens) and tokens[i] == ",":
            i += 1
        if i == len(tokens) or tokens[i].lower() != want:
            return 0
        i += 1
    return i


def _part_ok(part, st) -> bool:
    """Does a trailing part of a destination keep it at this station? Only a US state it stands for (a name, or a code: in capitals, or in lower case when
    it is one of the station's own; maybe with a ZIP code), the United States, or one of the station's own names: "CA 96150", "ca", "Nevada", "USA",
    "Lake Tahoe". "France", "Ibiza" or "Florida" (for Los Angeles) do not."""
    words = [t.lower() for t in part]
    if " ".join(words) in st.aliases:
        return True
    taken = next((n for n in (3, 2, 1) if n <= len(words) and " ".join(words[:n]) in _STATES), 0)
    if taken:
        state = _STATES[" ".join(words[:taken])]
    elif part and len(part[0]) == 2 and part[0].upper() in _CODES and (part[0].isupper() or part[0].upper() in st.states):
        state, taken = part[0].upper(), 1       # a code in capitals; or in lower case, only as one of the station's own states ("ca" for South Lake Tahoe)
    else:
        state = None
    if state is not None:
        if state not in st.states:
            return False
        if taken < len(words) and re.fullmatch(r"\d{5}", words[taken]):
            taken += 1
            if taken < len(words) and re.fullmatch(r"\d{4}", words[taken]):      # ZIP+4
                taken += 1
    return " ".join(words[taken:]) in ("", *_COUNTRY)


def station_named(text) -> Station | None:
    """The station a destination's name means. One of its names must start the destination, as whole words, the longest winning ("Lake Tahoe,
    California" is South Lake Tahoe; "Lake Placid, New York" is nobody); and every part after it must keep it there (`_part_ok`), so a place
    abroad or in another state never borrows a US station's weather ("Disneyland Paris, France", "Hollywood Florida", "San Antonio, Ibiza, Spain")."""
    tokens = _tokens(text)
    found = [(n, s) for s in stations() for a in s.aliases if (n := _starts(tokens, a))]
    if not found:
        return None
    n, st = max(found, key=lambda f: f[0])
    parts, part = [], []
    for t in tokens[n:]:
        if t == ",":
            parts.append(part)
            part = []
        else:
            part.append(t)
    parts.append(part)
    return st if all(_part_ok(p, st) for p in parts if p) else None


def period(d: date) -> str:
    """"late December": the third of the month a date falls in."""
    return f"{_THIRDS[third(d.day)]} {d:%B}"


def normals_label(d: date) -> str:
    return f"Typical {period(d)} · not a forecast yet"


def _every(count: int) -> str:
    """"about 1 day in 3"; "most days" when that would be 1 in 1."""
    return "most days" if count < 2 else f"about 1 day in {count}"


def _typical(high, low, wet, snow):
    """(condition, words) for a typical day: how often a day is wet, and whether that is mostly snow (the station says so, or its days average
    below 35 F when it does not count snow)."""
    snowy = snow >= 5 and snow * 2 >= wet if snow is not None else (high + low) / 2 < 35
    if wet < 10:
        return "sun", "Usually dry"
    if snow is not None and snowy:
        words = f"Snow {_every(round(100 / snow))}"
    else:
        words = f"{'Snow or rain' if snowy else 'Rain'} {_every(round(100 / wet))}"
    return ("snow" if snowy else "sun" if wet < 20 else "cloud" if wet < 35 else "rain"), words


def normal_day(st: Station, d: date) -> Day:
    """The station's typical weather for a date, as a Day of kind NORMAL that says it is not a forecast."""
    high, low, wet, snow = st.normals[(d.month - 1) * 3 + third(d.day)]
    condition, words = _typical(high, low, wet, snow)
    return Day(d, NORMAL, high, low, condition, words, label=normals_label(d), wet_pct=int(wet))


# ---- a trip's weather -------------------------------------------------------------------------------------------------------------

REACH = timedelta(days=10)   # MET forecasts about nine days ahead: only a trip with a day this close makes it ask
OPENS = timedelta(days=9)    # what a page promises: "The forecast opens around <the first typical day less this>"


@dataclass(frozen=True)
class Where:
    """Where a trip's weather is read: its NOAA station (MET is asked at the station; its time zone gives the days; its climate normals)."""
    name: str
    tz: str
    station: Station


@dataclass(frozen=True)
class TripWeather:
    days: tuple                  # a Day or None for each day of the trip, first to last
    place: str = ""              # the station's name: "South Lake Tahoe"
    updated: str = ""            # when MET made the forecast its forecast days come from, in the place's time ("6:10 AM")
    opens: date | None = None    # roughly when the forecast reaches the first day that is still typical (only while MET is switched on)
    gone: bool = False           # every day of the trip has passed, in the place's own time


def where(trip) -> Where | None:
    """Where a trip's weather is: the station of one of the catalog's places (Anaheim for a Disneyland trip), or the station its destination's name
    means. None when GitAway has nothing real for the place. Only a station's coordinates are ever sent to MET, never an address."""
    if getattr(trip, "focus", "") == "disney":
        st = station_named("anaheim")
    elif any(d.name == trip.destination_name for d in catalog.DESTINATIONS) and trip.key in CATALOG_STATIONS:
        st = station(CATALOG_STATIONS[trip.key])
    else:
        st = station_named(trip.destination_name)
    return Where(st.name, st.tz, st) if st else None


def trip_weather(trip) -> TripWeather:
    """One entry per day of the trip: MET's forecast where it covers the day; else, for a day still to come, the place's typical weather (a NORMAL
    Day, labelled so); else None (a day gone by, or a place with nothing real). Days are the place's own: "today" is today where the trip is.
    MET is asked only when a day of the trip is within its reach. This can wait on the network for up to TIMEOUT seconds: call it from a plain
    `def` handler or through run_in_threadpool."""
    dates = [trip.depart + timedelta(days=i) for i in range((trip.return_ - trip.depart).days + 1)]
    w = where(trip)
    today = catalog.today_in(w.tz if w else getattr(trip, "tz", "") or zones.DEFAULT)
    if w is None:
        return TripWeather((None,) * len(dates), gone=trip.return_ < today)
    fc = forecast(w.station) if any(today <= d <= today + REACH for d in dates) else None
    try:
        known = forecast_days(fc, w.tz, catalog.now_utc())
    except Exception as e:  # a forecast that read cleanly but cannot be laid out in days: show typical weather rather than fail the page
        log.warning("MET Norway forecast could not be laid out in days: %s", type(e).__name__)
        fc, known = None, {}
    days = tuple(None if d < today else known.get(d) or normal_day(w.station, d) for d in dates)
    typical = [d for d in days if d and d.kind == NORMAL]
    opens = typical[0].date - OPENS if typical and live() and typical[0].date - OPENS > today else None
    shown = fc is not None and any(d and d.kind == FORECAST for d in days)
    return TripWeather(days, w.name, updated_text(fc, w.tz) if shown else "", opens, trip.return_ < today)


def _span(typical) -> str:
    """The thirds of a month a trip's typical days fall in: "late December", "mid to late December", "late December to early January"."""
    first, last = period(typical[0].date), period(typical[-1].date)
    if first == last:
        return first
    (a, month_a), (b, month_b) = first.split(" ", 1), last.split(" ", 1)
    return f"{a} to {b} {month_a}" if month_a == month_b else f"{first} to {last}"


def credit(place: str, updated: str) -> str:
    """MET Norway's credit, naming the station the forecast is for: "Forecast for South Lake Tahoe, based on data from MET Norway · updated 6:10 AM"."""
    return f"Forecast for {place}, based on data from MET Norway · updated {updated}"


def notes(tw: TripWeather) -> list:
    """[(text, link or "")]: what a page says under a trip's weather, a line with a link being a link as a whole. The forecast's credit to MET Norway
    (with when it was made) when a day is a forecast; when a day is typical weather, the span it covers, what those days are usually like, the
    station's normals they come from, and when the forecast opens while MET is switched on."""
    out = []
    if tw.updated:
        out.append((credit(tw.place, tw.updated), CREDIT_URL))
    typical = [d for d in tw.days if d and d.kind == NORMAL]
    if typical:
        periods = [period(d.date) for d in typical]
        most = max(periods, key=periods.count)
        usually = next(d.word for d in typical if period(d.date) == most)
        opens = f" The forecast opens around {tw.opens:%b} {tw.opens.day}." if tw.opens else ""
        out.append((f"Typical {_span(typical)} · not a forecast yet", ""))
        out.append((f"{usually}. From NOAA climate normals for {tw.place}, 1991–2020.{opens}", ""))
    return out


def sample(trip) -> bool:
    """Is this the showcase's own sample trip (Los Angeles, Oct 16-20 2026), the one trip whose weather is sample data? Never on the live site and never
    a family's imported trip, whatever its dates."""
    from gitaway import context, showcase, tripimport
    return (showcase.on() and not isinstance(trip, tripimport.ImportedTrip) and trip.destination_name == "Los Angeles"
            and (trip.depart, trip.return_) == (context.SAMPLE_DEPART, context.SAMPLE_RETURN))
