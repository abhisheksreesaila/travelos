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

from gitaway import asksuggest, creatorbook as cb, forks, hub, seo
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
    note: str = ""           # what the creator wrote about it in the editor, when the line above is the post's own sentence and this is something more
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
    href: str = ""           # the creator's own post, for the tile that links back to it (itinerary_view._from_gitaway adds utm_source)
    by: str = ""             # the source card's byline, said in that tile ("Maya Chen · Blog")


@dataclass(frozen=True)
class Guide:
    slug: str
    title: str
    place: str
    by: str
    first: str               # the creator's first name, for "Maya's link" (a site's name when nobody has vouched for the creator yet)
    days: list
    tiles: list
    tips: list
    scene: tuple
    host: str = ""           # the post's site, "" when there is none
    url: str = ""
    photo: tuple | None = None        # (address, description): a picture the creator picked from their own post; never a drawing
    sample: bool = False
    source_by: str = ""      # the source card's byline as the trip says it ("Maya Chen · Blog", or the site's name until the creator is vouched for, D-189)
    author: str = ""         # who the trip says made it ("By Maya Chen"): the page's own byline, as the trip page has always said it
    handle: str = ""         # the creator's profile page (/creators/<handle>), "" while the trip waits for the captain's yes or has none
    real: bool = True
    stamped: str = ""
    private: list = field(default_factory=list)      # [(kind, title)] of an owner's booked flights and stays: kept out of the guide, said to its owner only

    @property
    def stops(self) -> int:
        return sum(len(d.stops) for d in self.days)

    @property
    def poss(self) -> str:
        """"Maya's" (the creator's first name), or "the creator's" when the byline is a site that nobody has vouched for yet (D-189) or there is none."""
        return f"{self.first}'s" if self.first and "." not in self.first else "the creator's"

    @property
    def Poss(self) -> str:      # noqa: N802 - the same, to start a sentence or a label
        return self.poss[0].upper() + self.poss[1:]

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
        note = s.note.strip() if s.said and s.note.strip() and s.note.strip() != s.said.strip() else ""
        link = safe_href(s.link) if s.link else ""
        tip = cb.said(tips, [s.title], used)[0]
        out.append(GStop(f"d{i}s{j}", i + 1, j + 1, len(day.stops), s.title, cb.kind_of(s.title), cb.KINDS[cb.kind_of(s.title)], s.time or "", why, note, cost_of(why) or cost_of(note), tip, link, _host(link)))
    return out


def tiles(trip: Itinerary, days: list, tips: list, host: str, url: str = "") -> list:
    """The at-a-glance tiles: only for what the guide knows (the post first when there is one, days always; who it suits when the creator marked it; tips when it has any; the post when it came from one)."""
    n, stops = len(days), sum(len(d.stops) for d in days)
    out = [Tile("calendar", "Days", f"{n} day{'s' if n != 1 else ''}", f"{stops} stop{'s' if stops != 1 else ''}")]
    kinds = hub.tag_keys(trip)
    suits = [word for key, word in SUITS if key in kinds]
    if suits:
        out.append(Tile("users", "Suits", " and ".join(suits[:2]), "As the creator marks it"))
    season = next((m.group(1) for t in trip.tags if (m := re.fullmatch(r"Best in (\w+)", t.label))), "")      # the creator's own answer, drawn as a tag
    if season:
        out.append(Tile("sun", "Best season", season.capitalize(), "As the creator says"))
    if tips:
        out.append(Tile("spark", "Tips", f"{len(tips)} tip{'s' if len(tips) != 1 else ''}", "In the creator's words"))
    if host:      # the creator's credit leads: whose post this is, and the link back to it (F-295, D-952)
        out.insert(0, Tile("link", (trip.source.kicker if trip.source else "") or "From", host, (trip.source.link_label if trip.source else "") or "Read the original post", url, trip.source.byline if trip.source else ""))
    return out


def from_trip(trip: Itinerary, *, stamped: str = "", private: list | None = None, handle: str = "") -> Guide:
    """The guide of an itinerary. The byline is the source card's (a trip nobody has vouched for yet names its site, not the person: D-189)."""
    src = trip.source
    by = (src.byline.split(" · ")[0] if src and src.byline else "") or trip.author
    place = (trip.place or "").split(",")[0].strip() or trip.title
    first = (by.split() or [""])[0]
    tips, used = list(trip.tips), set()
    days = [GDay(i + 1, d.title, _stops(d, i, trip, first, tips, used), d.note) for i, d in enumerate(trip.days)]
    url = safe_href(src.url) if src and src.url else ""
    host = _host(url)
    shot = trip.polaroids[0] if trip.polaroids else None
    return Guide(trip.slug, trip.title, place, by, first, days, tiles(trip, days, tips, host, url), tips, cb.scene_of(place, trip.title), host, url, (shot.src, shot.alt) if shot else None,
                 not trip.real, src.byline if src else "", trip.author, handle if first and "." not in first else "", trip.real, stamped, list(private or []))      # no profile link while the byline is only the site (D-189)


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


def is_guide(found) -> bool:
    """Does this trip read as a guide? One a creator made (it has a source card, or came through the creator import or "from my trip") or a creator's sample; a family's own published trip and the
    other samples keep the trip page."""
    return found is not None and (found.source is not None or (found.real and seo.imported(found.slug)))


def for_place(session, place: str, limit: int = 3) -> tuple:
    """The guides the booking and planning rails offer for `place` (F-263, D-730): (the first `limit` cards, how many in all). Only what the hub lists: published guides (not a trip waiting for the
    captain's yes, nor one taken down) and, on the showcase, the labelled sample guides; a family's own published trip is not a guide. The place is the guide's own place, matched by name. Off the
    showcase with none published this is ((), 0) and the rails draw nothing."""
    want = (place or "").split(",")[0].strip().casefold()
    if not want:
        return (), 0
    found = [c for c in hub.cards(session, q=want) if c.place.casefold() == want and is_guide(forks.resolve(c.slug))]
    found.sort(key=lambda c: (c.real, -c.days))      # the samples read first on the showcase; the sort is stable among real ones (newest first)
    return tuple(found[:limit]), len(found)
