"""The fine print, up front (F-282, D-895..D-899): what a hotel's page usually tucks away, said first, from what LiteAPI gave and nothing else. Plain functions on liteapi.HotelDetails and
liteapi.HotelReviews, no framework, no network; gitaway/pages/fineprint.py draws them.

    build(h, rv)              FinePrint: the costs not in the price, the policies that bite, what fits a family, what guests complain about and "The usual: ..." line
    newest_first(items)       the review drawer's order, every fetched review, newest first (a complaint's `ids` index this list)

Rules: a fact is shown only when the source gave it, in the source's own words where it wrote words; anything absent says "not listed" (never "none", never a guess). An item wears "Heads up"
(`flag`) when it is a cost the price leaves out or something the hotel itself says is a condition; ordinary amenities are not items, they go in one "The usual" line. What depends on the
room or flight the person chose (fees paid at the hotel, refundability, the landing against check-in) is filled by assets/js/hotelfine.js from the offers the server drew, never here.
"""

import re
from dataclasses import dataclass

from gitaway import reviewtrend

MONEY = re.compile(r"\b(fees?|charged?|charges|deposit|surcharge|taxes|tax|extra)\b|[$€£]\s?\d|\b(usd|eur|gbp)\s?\d|\b\d[\d,.]*\s?(usd|eur|gbp|dollars|euros|pounds)\b", re.I)
FAMILY_TYPE = "family_with_children"
NOT_LISTED = "not listed"
ASK_FIRST = "Ask the hotel before you go"
# what a family looks for, in the hotel's facility words: (what we call it, a word in the facility); the first two lines are asked about even when absent
FAMILY_ASKS = (("Cribs", ("crib", "cot", "baby")), ("Kids’ club", ("kids", "children", "child", "playground")), ("Connecting rooms", ("connecting",)))
FAMILY_HAS = ("family room", "swimming pool", "pool", "babysitting", "water park", "playground", "kids", "children", "crib", "connecting")
STOP = {"some", "guests", "guest", "reported", "reports", "report", "mentioned", "mention", "expected", "better", "hotel", "property", "several", "many", "with", "that", "this", "from",
        "have", "were", "very", "long", "other", "occasional", "inconsistent", "star", "room", "rooms", "quality", "value", "money"}


@dataclass(frozen=True)
class Item:
    title: str
    note: str = ""
    flag: bool = False         # "Heads up"
    state: str = "plain"       # "ok" (a tick), "unknown" (not listed), "plain"


@dataclass(frozen=True)
class Complaint:
    text: str
    ids: tuple                 # positions in `newest_first(items)` of the reviews whose cons say it
    count: int


@dataclass(frozen=True)
class FinePrint:
    costs: tuple
    policies: tuple
    family: tuple
    complaints: tuple
    usual: str                 # "The usual: WiFi available, ..." or ""
    checkin_minutes: int | None      # the hotel's check-in as minutes after midnight, for assets/js/hotelfine.js (the flight's landing is set against it)


def _minutes(clock: str) -> int | None:
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*([AP]M)?\s*$", clock or "", re.I)
    if not m:
        return None
    h, mi = int(m[1]) % 12 if m[3] else int(m[1]), int(m[2])
    return (h + (12 if m[3] and m[3].upper() == "PM" else 0)) * 60 + mi if h < 24 and mi < 60 else None


def newest_first(items) -> list:
    """Every review LiteAPI gave, newest first; a day keeps LiteAPI's own order (the sort is stable)."""
    return sorted(items, key=lambda r: r.date or "", reverse=True)


def _has(facilities, *words) -> str:
    return next((f for f in facilities if any(w in f.lower() for w in words)), "")


def _costs(h, taken: set) -> tuple:
    out = [Item(line, flag=True) for line in h.important if MONEY.search(line)]
    parking = _has(h.facilities, "parking")
    if parking:
        taken.add(parking)
    if not any("parking" in i.title.lower() for i in out):      # the hotel's own line about parking is the answer; else say what is and is not known
        out.append(Item("Parking", "Listed by the hotel; the price is not listed", state="unknown") if parking else Item(f"Parking: {NOT_LISTED}", state="unknown"))
    return tuple(out)


def _policies(h) -> tuple:
    return (Item(f"Check-in from {h.checkin}", state="ok") if h.checkin else Item(f"Check-in: {NOT_LISTED}", state="unknown"),
            Item(f"Check-out by {h.checkout}", state="ok") if h.checkout else Item(f"Check-out: {NOT_LISTED}", state="unknown"),
            *[Item(line) for line in h.important if not MONEY.search(line)])


def _family(h, rv, taken: set) -> tuple:
    out = []
    for f in h.facilities:
        if any(w in f.lower() for w in FAMILY_HAS):
            out.append(Item(f, state="ok"))
            taken.add(f)
    for name, words in FAMILY_ASKS:
        if not _has(h.facilities, *words):
            out.append(Item(f"{name}: {NOT_LISTED}", ASK_FIRST, state="unknown"))
    sleeps = max((r.sleeps for r in h.rooms if r.sleeps), default=0)
    if sleeps:
        out.append(Item(f"Largest room sleeps {sleeps}", state="ok"))
    t = reviewtrend.trend(rv.items, h.rating, FAMILY_TYPE) if rv and rv.items else None
    if t and t.like_you:
        out.append(Item(t.like_you, state="ok"))
    return tuple(out)


def _tokens(text: str) -> set:
    return {w.rstrip("s") for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in STOP}


def _complaints(rv, drawer) -> tuple:
    out = []
    for text in (rv.cons if rv else ()):
        words = _tokens(text)
        ids = tuple(i for i, r in enumerate(drawer) if words & _tokens(r.cons))
        out.append(Complaint(text, ids, len(ids)))
    return tuple(out)


def build(h, rv) -> FinePrint:
    taken: set = set()
    costs = _costs(h, taken)
    family = _family(h, rv, taken)
    usual = [f for f in h.facilities if f not in taken]
    return FinePrint(costs, _policies(h), family, _complaints(rv, newest_first(rv.items) if rv else []), f"The usual: {', '.join(usual)}." if usual else "", _minutes(h.checkin))
