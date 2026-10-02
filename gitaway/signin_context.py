"""What the sign-in boarding pass says (F-052): derived from where the traveler came from, never from anything they typed raw.

`context(next_path, intent)` reads the already-safe `next` through the existing helpers (catalog.parse_trip, forks.resolve) and
returns a Pass: a search (from, to, dates, party), a fork (a trip's place and days, no creator) or the generic pass.
Anything unknown or bad is the generic pass. Every field is plain text; the page escapes it.
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from gitaway import catalog, forks

FALLBACK = ("SFO", "LAX")
_CODE = re.compile(r"\b[A-Z]{3}\b")


@dataclass(frozen=True)
class Pass:
    kind: str       # cold | search | fork
    origin: str     # airport code on the sky
    dest: str
    head: str       # the big line
    sub: str
    route: str      # the stub's ROUTE value
    k2: str         # the stub's second label and value
    v2: str
    s1: str         # the two floating stickers
    s2: str
    note: str       # the handwritten note on the sky


GENERIC = Pass("cold", *FALLBACK, "Your next trip starts here.", "Plan it with your family, see every booking in one calendar, and keep it in your pocket.",
               "Anywhere", "WHEN", "You pick", "Tacos Friday", "Beach at sunset", "Fri 8:05 → we're off!")


def _search(trip):
    code = trip.airports[0] if trip.airports else FALLBACK[1]
    return Pass("search", trip.origin, code, f"{trip.origin_name} to {trip.destination_name}.",
                "Sign in to save these dates and picks, and plan the days with your family.", f"{trip.origin} → {code}",
                "DATES", trip.date_label, trip.nights_text, trip.summary, trip.date_label)


def _fork(trip):
    codes = _CODE.findall(trip.route or "")
    origin, dest = (codes[0], codes[1]) if len(codes) >= 2 else FALLBACK
    place, days = (trip.place or "").split(",")[0].strip() or "this trip", len(trip.days)
    day_text = f"{days} day{'s' if days != 1 else ''}"
    tag = trip.tags[0].label if trip.tags else place
    return Pass("fork", origin, dest, f"{place} in {day_text}.", "Sign in to keep this trip in your forks and drop its days into your calendar.",
                f"{origin} → {dest}", "DAYS", day_text, day_text, tag, f"{day_text} of {place}")


def context(next_path, intent) -> Pass:
    parts = urlsplit(next_path or "")
    path = parts.path.rstrip("/")
    q = {k: v[0] for k, v in parse_qs(parts.query).items() if v}
    if path == "/plan/pay" or (path == "/plan" and any(q.get(k) for k in ("f", "h", "c", "d", "r", "a", "k"))):
        try:
            return _search(catalog.parse_trip(catalog.ORIGIN[0], "la", q.get("d", catalog.SAMPLE_TRIP.depart.isoformat()), q.get("r", catalog.SAMPLE_TRIP.return_.isoformat()),
                                              q.get("a", str(catalog.SAMPLE_TRIP.adults)), q.get("k", ",".join(map(str, catalog.SAMPLE_TRIP.kid_ages)))))
        except catalog.TripError:
            return GENERIC
    if intent in ("fork", "save", "publish") and path.startswith("/trips/") and path.count("/") == 2:
        trip = forks.resolve(path.split("/")[2])
        return _fork(trip) if trip else GENERIC
    return GENERIC
