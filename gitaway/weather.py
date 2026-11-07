"""Real weather for a real trip (F-203): MET Norway's forecast for the days it covers, and NOAA's climate normals ("typical late December")
before it opens. Nothing here is invented: a day GitAway knows nothing about shows nothing.

    forecast(lat, lon, altitude=None) -> Forecast | None   MET Norway Locationforecast 2.0 compact for a place, cached
    forecast_days(fc, tz, now) -> {date: Day}               its local days: high and low (deg F), condition, words, inches, mph, hours
    station_near(lat, lon) / station_named(text)           the NOAA climate-normals station for a place (normals.json), or None
    normal_day(station, date) -> Day                        that station's typical weather for the date, labelled "Typical late December · not a forecast yet"
    trip_weather(trip, coords=None) -> TripWeather          one Day (or None) per day of a trip: the forecast where it reaches, else typical
    notes(tw) -> [(text, link)]                             the lines a page shows under a trip's weather: the credit, the label, the source
    sample(trip) -> bool                                    the showcase's own sample trip, the one trip whose weather is sample data

MET Norway's terms (https://api.met.no/doc/TermsOfService, the Locationforecast HowTo and FAQ) and how this module keeps them:
  - a person in charge must read and accept the terms before the service is used: nothing is asked until MET_NORWAY_TERMS_ACCEPTED=1;
  - an identifying User-Agent: "GitAway/1.0 <the site's address> <GITAWAY_CONTACT_EMAIL, when set>" (the site's /privacy page names the contact);
  - at most four decimals in a coordinate, https only, gzip accepted, redirects followed (urllib follows them);
  - never ask again before the Expires header, and not within three hours (outside the Nordic area the forecast changes every six hours, and
    the FAQ asks for at least half of that); then ask with If-Modified-Since set to exactly the Last-Modified we were given, and keep our copy on 304;
  - far under 20 requests a second for the whole site: one gate for the process (`GATE`); a 429 or a 403 shuts it for a while;
  - a 203 (the product is deprecated) is logged as a warning, so whoever reads the logs moves to the successor.
The data are MET Norway's (CC BY 4.0 and NLOD 2.0) and GitAway's days are worked out from them: show `CREDIT` (linked to `CREDIT_URL`) wherever a
forecast shows. Our server asks, never a browser, so MET Norway sees our server and a place, not a family.

`TRANSPORT` is the one function that touches the network, (url, headers, timeout) -> (status, headers, body bytes); tests replace it.
"""

import json
import logging
import math
import os
import re
import threading
import zlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from gitaway import auth, catalog, zones
from gitaway.geo import Gate

log = logging.getLogger("gitaway.weather")

API = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
TIMEOUT = 3.0                       # seconds a page waits for MET at most
MIN_REPEAT = timedelta(hours=3)     # Locationforecast FAQ: outside the Nordic area wait at least half of its six-hour update interval
FAIL_WAIT = timedelta(minutes=5)    # after a failed call, before anyone asks for that place again
KEEP = timedelta(hours=24)          # a forecast we hold is still shown, with its time, for this long when later calls fail
REFUSED = {429: 600, 403: 3600}     # seconds the gate stays shut after MET says too many requests, or refuses us
MAX_BYTES = 2 * 1024 * 1024
CACHE_MAX = 512                     # places
GATE = Gate(0.2)                    # at most five calls a second from the whole process

FORECAST, NORMAL = "forecast", "normal"
CREDIT = "Forecast based on data from MET Norway"
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
class Hour:
    at: int                      # local hour, 0 to 23
    temp_f: int | None
    condition: str               # sun | cloud | rain | snow
    precip_in: float


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
    hours: tuple = ()                # forecast: Hour per hour where MET gives hourly steps (the first two or three days)
    partial: bool = False            # forecast: part of the day had gone when it was read (today)
    label: str = ""                  # normals: "Typical late December · not a forecast yet"


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


def _http(url, headers, timeout):
    """GET from MET Norway. 304, 403, 429 and the rest come back as a status, not an exception."""
    try:
        with urlopen(Request(url, headers=headers), timeout=timeout) as r:    # noqa: S310 - the fixed https address above
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(MAX_BYTES + 1)
    except HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, b""


TRANSPORT = _http


@dataclass
class _Entry:
    forecast: Forecast | None
    fetched: datetime | None     # when we last knew that forecast to be MET's current one
    next_ask: datetime           # nobody asks MET for this place before then
    modified: str = ""           # its Last-Modified, sent back as If-Modified-Since


_CACHE: dict = {}
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


def forecast(lat, lon, altitude=None, *, timeout=TIMEOUT) -> Forecast | None:
    """MET's forecast for a place (altitude in metres, when known, makes the temperatures more exact), or None: not switched on, a bad place,
    or no answer. Answered from the cache until MET's Expires (and three hours) have passed."""
    q = _query(lat, lon, altitude)
    if q is None:
        return None
    url = f"{API}?{q}"
    entry = _cached(url)
    now = catalog.now_utc()
    if (entry and now < entry.next_ask) or not live():
        return _held(entry, now)
    with _LOCK:
        lock = _ASKING.setdefault(url, threading.Lock())
    if not lock.acquire(timeout=timeout):
        return _held(entry, now)
    try:
        entry, now = _cached(url), catalog.now_utc()      # another page may have asked while we waited
        if entry and now < entry.next_ask:
            return _held(entry, now)
        if not GATE.wait():
            return _held(entry, now)
        return _ask(url, entry, now, timeout)
    finally:
        lock.release()


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
    try:
        fc = parse(json.loads(_unzip(raw, h.get("content-encoding", ""))))
    except (ValueError, TypeError, KeyError, zlib.error) as e:
        log.warning("MET Norway forecast could not be read: %s", type(e).__name__)
        return _failed(url, entry, now)
    return _keep(url, fc, now, h, h.get("last-modified", ""))


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
    try:
        at = parsedate_to_datetime(h.get("expires", ""))
    except (TypeError, ValueError, IndexError):
        return now
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _keep(url, fc, now, h, modified):
    _store(url, _Entry(fc, now, max(_expires(h, now), now + MIN_REPEAT), modified if isinstance(modified, str) else ""))
    return fc


def _failed(url, entry, now):
    held = _held(entry, now)
    _store(url, _Entry(held, entry.fetched if held else None, now + FAIL_WAIT, entry.modified if held else ""))
    return held


def _store(url, entry):
    with _LOCK:
        if url not in _CACHE and len(_CACHE) >= CACHE_MAX:     # forget the places whose wait ran out first
            for old in sorted(_CACHE, key=lambda u: _CACHE[u].next_ask)[:CACHE_MAX // 8]:
                del _CACHE[old]
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


def parse(doc) -> Forecast:
    """A Forecast from MET's compact GeoJSON. Raises ValueError when it holds no usable step."""
    props = doc["properties"]
    points = []
    for step in props["timeseries"]:
        try:
            points.append(_point(step))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    if not points:
        raise ValueError("no forecast steps")
    return Forecast(_utc(props["meta"]["updated_at"]), tuple(sorted(points, key=lambda p: p.at)))


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


def _hour_condition(symbol: str) -> str:
    k = _kind(symbol)
    return "snow" if k in ("snow", "sleet") else "rain" if k == "rain" else "sun" if k == "clear" else "cloud" if k else ""


@dataclass
class _Acc:
    temps: list = field(default_factory=list)
    winds: list = field(default_factory=list)
    day_winds: list = field(default_factory=list)
    clouds: list = field(default_factory=list)
    hours: list = field(default_factory=list)
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
        if p.hours == 1 and p.temp_c is not None:
            a.hours.append(Hour(local.hour, _f(p.temp_c), _hour_condition(p.symbol), _inches(p.precip_mm)))
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
                     round(max(a.winds) * 2.23694) if a.winds else None, tuple(sorted(a.hours, key=lambda h: h.at)), a.covered < 23)
    return out


# ---- typical weather: NOAA's climate normals ------------------------------------------------------------------------------------
# gitaway/normals.json is made by scripts/build_normals.py from NOAA NCEI's U.S. Climate Normals 1991-2020 (public domain): per station, for the
# early, mid and late part of each month, the normal high and low (deg F), the chance of a wet day (at least 0.01 in) and, where the station
# measures it, of a snowy one (at least 0.1 in). Nothing is fetched while the app runs.

NORMALS = Path(__file__).with_name("normals.json")
NEAR_KM = 25         # a place farther than this from every station has no normals
NORMALS_CREDIT = "From NOAA climate normals, 1991–2020"
CATALOG = {"la": "USW00093134", "sd": "USW00023188", "hi": "USW00022521", "nyc": "USW00094728"}   # the catalog's four places
_THIRDS = ("early", "mid", "late")


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    lat: float
    lon: float
    elev: int            # metres
    tz: str
    aliases: tuple       # destination names that mean this station, lower case
    normals: tuple       # 36 x (high F, low F, wet-day %, snowy-day % or None)


_STATIONS: tuple = ()


def stations() -> tuple:
    global _STATIONS
    if not _STATIONS:
        table = json.loads(NORMALS.read_text(encoding="utf-8"))["stations"]
        _STATIONS = tuple(Station(sid, s["name"], s["lat"], s["lon"], s["elev"], s["tz"], tuple(s["aliases"]), tuple(tuple(n) for n in s["n"]))
                          for sid, s in table.items())
    return _STATIONS


def station(sid: str) -> Station | None:
    return next((s for s in stations() if s.id == sid), None)


def _km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def station_near(lat, lon, km=NEAR_KM) -> Station | None:
    """The closest station within `km` of a place, or None."""
    lat, lon = _number(lat, -90, 90), _number(lon, -180, 180)
    if lat is None or lon is None:
        return None
    best = min(stations(), key=lambda s: _km(lat, lon, s.lat, s.lon))
    return best if _km(lat, lon, best.lat, best.lon) <= km else None


def _words(text) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).split())


def station_named(text) -> Station | None:
    """The station a destination's name means ("Lake Tahoe, California" is South Lake Tahoe), matched as whole words, the longest name winning; else None."""
    words = f" {_words(text)} "
    found = [(len(a), s) for s in stations() for a in s.aliases if f" {a} " in words]
    return max(found, key=lambda f: f[0])[1] if found else None


def period(d: date) -> str:
    """"late December": the third of the month a date falls in."""
    return f"{_THIRDS[0 if d.day <= 10 else 1 if d.day <= 20 else 2]} {d:%B}"


def normals_label(d: date) -> str:
    return f"Typical {period(d)} · not a forecast yet"


def _typical(high, low, wet, snow):
    """(condition, words) for a typical day: how often a day is wet, and whether that is mostly snow (the station says so, or its days average
    below 35 F when it does not count snow)."""
    snowy = snow >= 5 and snow * 2 >= wet if snow is not None else (high + low) / 2 < 35
    if wet < 10:
        return "sun", "Usually dry"
    if snow is not None and snowy:
        words = f"Snow about 1 day in {round(100 / snow)}"
    else:
        words = f"{'Snow or rain' if snowy else 'Rain'} about 1 day in {round(100 / wet)}"
    return ("snow" if snowy else "sun" if wet < 20 else "cloud" if wet < 35 else "rain"), words


def normal_day(st: Station, d: date) -> Day:
    """The station's typical weather for a date, as a Day of kind NORMAL that says it is not a forecast."""
    high, low, wet, snow = st.normals[(d.month - 1) * 3 + (0 if d.day <= 10 else 1 if d.day <= 20 else 2)]
    condition, words = _typical(high, low, wet, snow)
    return Day(d, NORMAL, high, low, condition, words, label=normals_label(d))


# ---- a trip's weather -------------------------------------------------------------------------------------------------------------

REACH = timedelta(days=10)   # MET forecasts about nine days ahead: only a trip with a day this close makes it ask
OPENS = timedelta(days=9)    # what a page promises: "The forecast opens around <the first typical day less this>"


@dataclass(frozen=True)
class Where:
    """Where a trip's weather is read: a place's coordinates (MET), its time zone (the days) and its climate-normals station, if it has one."""
    name: str
    lat: float
    lon: float
    altitude: int | None
    tz: str
    station: Station | None


@dataclass(frozen=True)
class TripWeather:
    days: tuple                  # a Day or None for each day of the trip, first to last
    place: str = ""
    updated: str = ""            # when MET made the forecast its forecast days come from, in the place's time ("6:10 AM")
    opens: date | None = None    # roughly when the forecast reaches the first day that is still typical (only while MET is switched on)


def _at(st: Station, name=None) -> Where:
    return Where(name or st.name, st.lat, st.lon, st.elev, st.tz, st)


def where(trip, coords=None) -> Where | None:
    """Where a trip's weather is: one of the catalog's places (Anaheim for a Disneyland trip), the station its destination names, or the coordinates a
    caller knows (with the station near them, if any). None when GitAway has nothing real for the place."""
    if getattr(trip, "focus", "") == "disney":
        return _at(station_named("anaheim"))
    if any(d.name == trip.destination_name for d in catalog.DESTINATIONS) and trip.key in CATALOG:
        return _at(station(CATALOG[trip.key]))
    if coords is not None and _query(*coords) is not None:
        lat, lon = coords
        st = station_near(lat, lon)
        return Where(trip.destination_name, lat, lon, None, st.tz if st else getattr(trip, "tz", "") or zones.DEFAULT, st)
    st = station_named(trip.destination_name)
    return _at(st) if st else None


def trip_weather(trip, coords=None) -> TripWeather:
    """One entry per day of the trip: MET's forecast where it covers the day; else, for a day still to come, the place's typical weather (a NORMAL
    Day, labelled so); else None (a day gone by, or a place with nothing real). MET is asked only when a day of the trip is within its reach.
    This can wait on the network for up to TIMEOUT seconds: call it from a plain `def` handler or through run_in_threadpool."""
    dates = [trip.depart + timedelta(days=i) for i in range((trip.return_ - trip.depart).days + 1)]
    w = where(trip, coords)
    if w is None:
        return TripWeather((None,) * len(dates))
    today, now = catalog.today(), catalog.now_utc()
    fc = forecast(w.lat, w.lon, w.altitude) if any(today <= d <= today + REACH for d in dates) else None
    known = forecast_days(fc, w.tz, now)
    days = tuple(None if d < today else known.get(d) or (normal_day(w.station, d) if w.station else None) for d in dates)
    waiting = [d for d, day in zip(dates, days) if d >= today and (day is None or day.kind == NORMAL)]
    opens = waiting[0] - OPENS if waiting and live() and waiting[0] - OPENS > today else None
    shown = fc is not None and any(d and d.kind == FORECAST for d in days)
    return TripWeather(days, w.name, updated_text(fc, w.tz) if shown else "", opens)


def notes(tw: TripWeather) -> list:
    """[(text, link or "")]: what a page says under a trip's weather. The forecast's credit to MET Norway (with when it was made) when a day is a forecast;
    when a day is typical weather, the label most of those days carry, what those days are usually like and where that comes from; and when the
    forecast opens, while MET is switched on."""
    out = []
    if tw.updated:
        out.append((f"{CREDIT} · updated {tw.updated}", CREDIT_URL))
    opens = f"The forecast opens around {tw.opens:%b} {tw.opens.day}." if tw.opens else ""
    typical = [d for d in tw.days if d and d.kind == NORMAL]
    if typical:
        periods = [period(d.date) for d in typical]
        most = max(periods, key=periods.count)
        usually = next(d.word for d in typical if period(d.date) == most)
        out.append((f"Typical {most} · not a forecast yet", ""))
        out.append((" ".join(filter(None, (f"{usually}. {NORMALS_CREDIT}.", opens))), ""))
    elif opens:
        out.append((opens, ""))
    return out


def sample(trip) -> bool:
    """Is this the showcase's own sample trip (Los Angeles, Oct 16-20 2026), the one trip whose weather is sample data? Never on the live site and never
    a family's imported trip, whatever its dates."""
    from gitaway import context, showcase, tripimport
    return (showcase.on() and not isinstance(trip, tripimport.ImportedTrip) and trip.destination_name == "Los Angeles"
            and (trip.depart, trip.return_) == (context.SAMPLE_DEPART, context.SAMPLE_RETURN))
