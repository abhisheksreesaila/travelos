"""The scrapbook book (F-253, D-640..): the data behind a creator's trip drawn as a book, from any `Itinerary` (a draft's preview, a published creator trip, a sample). Pure functions, no
framework; the pages are gitaway/pages/bookview.py. Nothing here invents a word: a quote is a sentence of the post itself (creatordraft keeps them, `importsource.own_words`), a time only where the
draft has one, and a picture only where the creator picked one; everything else is a drawing, labelled as one.
"""

import json
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

from gitaway import placeart
from gitaway.itineraries import Itinerary, safe_href
from gitaway.partners import places

KINDS = {"see": "Sight", "food": "Food", "tix": "Tickets", "ride": "Ride", "show": "Show", "walk": "Walk"}
_WORDS = (("show", r"\bshows?\b|concert|fado|theat|opera|musical|festival|lucha|performance|nightlife"),
          ("food", r"restaurant|caf[eé]|bakery|market|lunch|dinner|breakfast|brunch|past[eé]is|pastel|tacos?|pizza|bistro|\bbar\b|coffee|snack|ice cream|churros|supper|picnic|food|factory"),
          ("ride", r"tuk|tram|ferry|train|\bbus\b|taxi|\buber\b|\bride\b|cruise|gondola|boat|drive|metro|trajinera"),
          ("tix", r"ticket|castel|castle|ch[aâ]teau|palace|palacio|palazzo|admission|aquarium|\bzoo\b|quinta|theme park|\btour\b|cathedral"),
          ("walk", r"walk|hike|stroll|trail|lanes?\b|district|neighbou?rhood|alfama|street|loop|beach|promenade|boardwalk|\bsquare\b"))
CLOTHS = ("#1E4E79", "#7A1F2B", "#0E5E5A", "#1C3F8C", "#2F5233", "#8A1F55", "#33415C", "#5B3A29")
SOURCE_STICKER = {"blog": "From the post", "youtube": "From the video", "instagram": "From Instagram"}
ART = json.loads((Path(__file__).with_name("bookart.json")).read_text(encoding="utf-8"))
# a drawing for a day's plate or a cover, by the place or stop it is about: (words that name it) -> a scene of bookart.json
_SCENES = (("belem", r"bel[eé]m"), ("sintra", r"sintra|pena palace"), ("alfama", r"alfama"), ("lisbon", r"lisbon|lisboa"), ("kyoto", r"kyoto"), ("bigsur", r"big sur"), ("amalfi", r"amalfi|positano"),
           ("cdmx", r"mexico city|ciudad de m"), ("iceland", r"iceland"))


def kind_of(name: str) -> str:
    """The colour a stop gets: what the name says it is, "see" when it does not say."""
    low = (name or "").casefold()
    return next((k for k, pat in _WORDS if re.search(pat, low)), "see")


def cloth_of(slug: str) -> str:
    return CLOTHS[zlib.crc32(str(slug).encode()) % len(CLOTHS)]


def scene_of(*texts):
    """("bookart", key) for a drawn scene that names this place, ("placeart", place) for GitAway's own place art, else ("generic", "")."""
    said = " ".join(t for t in texts if t).casefold()
    for key, pat in _SCENES:
        if re.search(pat, said):
            return "bookart", key
    for t in texts:
        if t and placeart.art(t) is not None:
            return "placeart", t
    return "generic", ""


@dataclass(frozen=True)
class BStop:
    name: str
    kind: str
    time: str = ""
    note: str = ""


@dataclass(frozen=True)
class BDay:
    head: str
    stops: list
    quote: str = ""
    scene: tuple = ("generic", "")
    caption: str = ""


@dataclass(frozen=True)
class Book:
    slug: str
    title: str
    by: str
    place: str
    days: list
    tips: list
    cloth: str
    scene: tuple
    quote: str = ""
    photo: tuple | None = None        # (address, description): a picture the creator picked from their own post; never a drawing
    host: str = ""                    # the post's site, "" when there is none
    url: str = ""
    sticker: str = ""                 # the cover's round sticker ("From the post", "Sample book")
    sample: bool = False
    stamped: str = ""                 # "Nov 15, 2026" once it is published

    @property
    def stops(self) -> int:
        return sum(len(d.stops) for d in self.days)


def plan_href(place: str) -> str:
    """"Plan this trip": booking's sentence (/plan/ask) with the book's place as its Where to, when that is a place GitAway knows how to find; else the sentence as it is."""
    p = places.resolve(place)
    return "/plan/ask" + (f"?to={quote(p.name)}" if p and p.known else "")


def from_trip(trip: Itinerary, *, sample: bool = False, stamped: str = "") -> Book:
    """The book of an itinerary. The byline is the source card's (a trip nobody has vouched for yet names its site, not the person: D-189)."""
    src = trip.source
    by = (src.byline.split(" · ")[0] if src and src.byline else "") or trip.author
    place = (trip.place or "").split(",")[0].strip() or trip.title
    days = []
    for d in trip.days:
        names = [s.title for s in d.stops]
        days.append(BDay(d.title, [BStop(s.title, kind_of(s.title), s.time, s.note) for s in d.stops], getattr(d, "quote", ""), scene_of(*names, place), ""))
    host = (urlsplit(src.url).hostname or "").removeprefix("www.") if src and src.url else ""
    kind = next((k for k, label in {"blog": "Blog", "youtube": "YouTube", "instagram": "Instagram"}.items() if src and src.byline.endswith(label)), "") if src else ""
    shot = trip.polaroids[0] if trip.polaroids else None
    return Book(trip.slug, trip.title, by, place, days, list(trip.tips), cloth_of(trip.slug), scene_of(place, trip.title), getattr(trip, "quote", ""), (shot.src, shot.alt) if shot else None, host,
                safe_href(src.url) if src else "", "Sample book" if sample else SOURCE_STICKER.get(kind, ""), sample, stamped)


# ---- the post's own sentences, laid against the stops they name -------------------------------------------------------------------------

def _fold(text: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (text or "").casefold()) if not unicodedata.combining(c))


def _names(sentence: str, name: str) -> bool:
    n = _fold(name).strip()
    return len(n) >= 4 and n != _fold("Unnamed stop") and n in _fold(sentence)


def said(words: list, names: list, used: set | None = None) -> list:
    """For each stop name, the post's own sentence that names it (the first one not already used), else "". `words` are sentences exactly as the post wrote them."""
    used = set() if used is None else used
    out = []
    for name in names:
        hit = next((s for s in words if s not in used and _names(s, name)), "")
        if hit:
            used.add(hit)
        out.append(hit)
    return out


def day_quote(words: list, names: list, used: set) -> str:
    """The sentence a day page quotes: the post's first sentence naming one of the day's stops (never one already quoted), "" when the post names none."""
    for name in names:
        for sentence in words:
            if sentence not in used and _names(sentence, name):
                used.add(sentence)
                return sentence
    return ""
