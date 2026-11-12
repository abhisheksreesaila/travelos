"""The drive from a trip's airport to where it stays (F-210), for the booking lanes' side panel: the router's own time, or nothing.

    drive(iata, town) -> Drive | None    minutes by car from the airport to the town, as OSRM's public router answers it, or None

The airport is only one of AIRPORTS, gitaway/airport_coords.py's and the booking lanes' own (never looked up by its code: a wrong match would be a
wrong time; the lanes' are kept here so the trip maps, which look an unlisted airport up by name, do not change); the town is found with
OpenStreetMap's Nominatim, and the drive asked of OSRM, both through gitaway/geo.py (its gates keep each service at one request a second for the whole
process; tests refuse `geo.fetch`). The booking page has no family database, so the answers are kept here, in the process: a drive for KEEP, a failure
for FAIL_WAIT, the oldest dropped past MAX_KEPT. At most BUDGET_PER_MINUTE uncached lookups go out in any minute for the whole site, and a page waits
at most DEADLINE seconds. A drive longer than MAX_MINUTES is not an airport run (the town matched somewhere else): it is not shown.
No time is ever guessed: no router answer, no widget.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import timedelta

from gitaway import geo
from gitaway.airport_coords import AIRPORT_COORDS

# the airports of the booking lanes' places (gitaway/partners/places.py) that airport_coords.py lacks, from OpenStreetMap's Nominatim on 2026-11-08 (each an aerodrome)
LANE_AIRPORTS = {
    "RNO": (39.4983, -119.7688), "ASE": (39.2224, -106.8678), "BZN": (45.7835, -111.1570), "EGE": (39.6423, -106.9172), "FAT": (36.7760, -119.7197),
    "FLG": (35.1404, -111.6702), "HDN": (40.4816, -107.2204), "JAC": (43.6088, -110.7380), "KOA": (19.7439, -156.0423), "LIH": (21.9722, -159.3500),
    "MRY": (36.5871, -121.8419), "MTJ": (38.5118, -107.8925), "SUN": (43.5066, -114.3006),
}
AIRPORTS = {**AIRPORT_COORDS, **LANE_AIRPORTS}

DEADLINE = 2.5
KEEP = timedelta(days=7).total_seconds()
FAIL_WAIT = timedelta(minutes=10).total_seconds()
MAX_KEPT = 512
BUDGET_PER_MINUTE = 10
MAX_MINUTES = 8 * 60
CREDIT_URL = "https://www.openstreetmap.org/copyright"

_KEPT: dict = {}          # (iata, town) -> (Drive | None, monotonic time asked), oldest first
_ASKED: deque = deque()   # monotonic times of the uncached lookups in the last minute
_LOCK = threading.Lock()
_clock = time.monotonic


@dataclass(frozen=True)
class Drive:
    iata: str
    town: str
    minutes: int

    def label(self) -> str:
        """"1 h 5 min", "45 min"."""
        h, m = divmod(self.minutes, 60)
        return f"{h} h {m} min" if h and m else f"{h} h" if h else f"{m} min"


def clear() -> None:
    with _LOCK:
        _KEPT.clear()
        _ASKED.clear()


def _spend() -> bool:
    now = _clock()
    with _LOCK:
        while _ASKED and now - _ASKED[0] > 60:
            _ASKED.popleft()
        if len(_ASKED) >= BUDGET_PER_MINUTE:
            return False
        _ASKED.append(now)
        return True


def _keep(key, value) -> None:
    with _LOCK:
        _KEPT.pop(key, None)
        while len(_KEPT) >= MAX_KEPT:
            _KEPT.pop(next(iter(_KEPT)))
        _KEPT[key] = (value, _clock())


def kept(iata, town) -> Drive | None:
    """The drive already known for this airport and town, without asking anyone (F-222: a page drawn before its answers land)."""
    found = _KEPT.get((str(iata or "").strip().upper(), " ".join(str(town or "").split()).lower()))
    return found[0] if found and _clock() - found[1] < KEEP else None


def drive(iata, town) -> Drive | None:
    """The drive from airport `iata` to `town` ("South Lake Tahoe, California"), or None. Can wait on the network up to DEADLINE seconds:
    call it from a plain `def` handler or run_in_threadpool."""
    iata, town = str(iata or "").strip().upper(), " ".join(str(town or "").split())
    a = AIRPORTS.get(iata)
    if not a or not town:
        return None
    key = (iata, town.lower())
    kept = _KEPT.get(key)
    if kept and _clock() - kept[1] < (KEEP if kept[0] else FAIL_WAIT):
        return kept[0]
    if not _spend():
        return None
    deadline = _clock() + DEADLINE
    try:
        b = geo.find(town, None, deadline=deadline)[0]
        minutes = geo.drive_minutes(a, b, None, deadline=deadline) if isinstance(b, tuple) else None
    except Exception:      # a drive is never worth failing the page
        b, minutes = None, None
    found = Drive(iata, town, int(minutes)) if isinstance(minutes, int) and 0 < minutes <= MAX_MINUTES else None
    if found or b == geo.MISSING or isinstance(minutes, int):      # keep only what a service answered; a busy gate or a spent deadline is asked again next time
        _keep(key, found)
    return found
