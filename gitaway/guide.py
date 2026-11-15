"""A guide's data (F-262, D-710..): what the guide page draws, from any `Itinerary` (a published creator trip, a sample, an owner's draft preview). Pure functions, no framework.

A guide is the prototype's run sheet (docs/design/guides-v2/index.html): at-a-glance tiles, a day strip, and for each day a time rail of stop cards. Honest by construction: every word is the
creator's own (a stop's one-line why is the post's own sentence that names it, else the creator's note), a tile exists only where the guide knows the fact, a cost is only ever a price the
creator's own sentence says, a tip badge only where one of the creator's tips names the stop, and travel time between stops is never drawn (a stop has no coordinates, so there is no router
answer to give: gitaway/airportdrive.py answers only airport to town, and no time is ever guessed).
"""

import re
from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import quote, urlsplit

from gitaway import asksuggest, creatorbook as cb, hub
from gitaway.itineraries import Itinerary, safe_href
from gitaway.partners import places

_COST = re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d{1,2})?(?:\s+(?:per|a|each|for)\s+\w+)?")
SUITS = (("kid", "Families"), ("couple", "Couples"), ("pet", "Travelling with a pet"))
MIN_NIGHTS, MAX_NIGHTS = 2, 7      # the matrix's own nights slider


@dataclass(frozen=True)
class GStop:
    key: str                 # "d0s1": the day and the stop among the day's named stops, the address of the inline edit (creatordraft.word) and of Add to my plan
    day: int
    n: int                   # 1-based among the day's stops
    of: int                  # how many stops the day has
    name: str
    kind: str                # see | food | tix | ride | show | walk (what the name says it is)
    label: str               # "Sight", "Food"...
    time: str = ""           # as the post says it, "" when it does not
    why: str = ""            # the creator's own sentence about it
    cost: str = ""           # a price written in that sentence
    tip: str = ""            # one of the creator's tips that names the stop
    link: str = ""           # the creator's own link for this stop (allow-listed upstream, stoplinks.py)
    link_host: str = ""


@dataclass(frozen=True)
class GDay:
    n: int
    title: str
    stops: list
    note: str = ""

    @property
    def kinds(self) -> list:
        return [s.kind for s in self.stops]


@dataclass(frozen=True)
class Tile:
    icon: str
    label: str
    value: str
    sub: str = ""


@dataclass(frozen=True)
class Guide:
    slug: str
    title: str
    place: str
    by: str
    first: str               # the creator's first name, for "Maya's link"
    days: list
    tiles: list
    tips: list
    scene: tuple
    host: str = ""           # the post's site, "" when there is none
    url: str = ""
    photo: tuple | None = None        # (address, description): a picture the creator picked from their own post; never a drawing
    sample: bool = False
    real: bool = True
    stamped: str = ""
    private: list = field(default_factory=list)      # [(kind, title)] of an owner's booked flights and stays: kept out of the guide, said to its owner only

    @property
    def stops(self) -> int:
        return sum(len(d.stops) for d in self.days)

    @property
    def nights(self) -> int:
        return max(MIN_NIGHTS, min(MAX_NIGHTS, len(self.days) - 1))

    def find(self, key: str):
        return next((s for d in self.days for s in d.stops if s.key == key), None)


def cost_of(text: str) -> str:
    """A price written in the creator's own sentence ("$25 for 4"), exactly as written; "" when it names none."""
    m = _COST.search(text or "")
    return m.group(0).strip() if m else ""


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.") if url else ""


def _stops(day, i, trip, first, tips, used) -> list:
    out = []
    for j, s in enumerate(day.stops):
        why = (s.said or s.note or "").strip()
        link = safe_href(s.link) if s.link else ""
        tip = cb.said(tips, [s.title], used)[0]
        out.append(GStop(f"d{i}s{j}", i, j + 1, len(day.stops), s.title, cb.kind_of(s.title), cb.KINDS[cb.kind_of(s.title)], s.time or "", why, cost_of(why), tip, link, _host(link)))
    return out


def tiles(trip: Itinerary, days: list, tips: list, host: str) -> list:
    """The at-a-glance tiles: only for what the guide knows (days always; who it suits when the creator marked it; tips when it has any; the post when it came from one)."""
    n, stops = len(days), sum(len(d.stops) for d in days)
    out = [Tile("plan", "Days", f"{n} day{'s' if n != 1 else ''}", f"{stops} stop{'s' if stops != 1 else ''}")]
    kinds = hub.tag_keys(trip)
    suits = [word for key, word in SUITS if key in kinds]
    if suits:
        out.append(Tile("users", "Suits", " and ".join(suits[:2]), "As the creator marks it"))
    if tips:
        out.append(Tile("bulb", "Tips", f"{len(tips)} tip{'s' if len(tips) != 1 else ''}", "In the creator's words"))
    if host:
        out.append(Tile("link", "From", host, "Their original post"))
    return out


def from_trip(trip: Itinerary, *, stamped: str = "", private: list | None = None) -> Guide:
    """The guide of an itinerary. The byline is the source card's (a trip nobody has vouched for yet names its site, not the person: D-189)."""
    src = trip.source
    by = (src.byline.split(" · ")[0] if src and src.byline else "") or trip.author
    place = (trip.place or "").split(",")[0].strip() or trip.title
    first = (by.split() or ["The creator"])[0]
    tips, used = list(trip.tips), set()
    days = [GDay(i + 1, d.title, _stops(d, i, trip, first, tips, used), d.note) for i, d in enumerate(trip.days)]
    url = safe_href(src.url) if src and src.url else ""
    host = _host(url)
    shot = trip.polaroids[0] if trip.polaroids else None
    return Guide(trip.slug, trip.title, place, by, first, days, tiles(trip, days, tips, host), tips, cb.scene_of(place, trip.title), host, url, (shot.src, shot.alt) if shot else None,
                 not trip.real, trip.real, stamped, list(private or []))


def plan_href(place: str, nights: int = 0) -> str:
    """"Plan this trip": booking's sentence (/plan/ask) with the guide's place as its Where to, and the guide's length as its dates (the matrix's own default first start day, so the reader
    changes them in the sentence); the place alone when GitAway does not know how to find it."""
    p = places.resolve(place)
    if not (p and p.known):
        return "/plan/ask"
    out = f"/plan/ask?to={quote(p.name)}"
    if nights:
        start = asksuggest.first_start()
        out += f"&d={start.isoformat()}&r={(start + timedelta(days=nights)).isoformat()}"
    return out
