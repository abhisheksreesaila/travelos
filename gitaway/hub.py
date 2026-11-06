"""The community hub's model (F-022, F-041): which trips it lists, how they filter, and how a trip gets added.

The hub lists the fake community itineraries in `gitaway.itineraries` plus every trip published to the community database
(`gitaway.community`): families' shared trips and creators' trips. Publishing is the one door in, through `gitaway.share`
and `gitaway.creators`, which freeze the page as a snapshot. Everything published is listed for everyone, signed in or out;
cards published by the signed-in traveler are marked `mine`.

Pure functions over a session dict (for the signed-in person) and the community database.
"""

import re
from dataclasses import dataclass, replace
from urllib.parse import urlencode

from gitaway import community, itineraries, showcase
from gitaway.community import HubError  # noqa: F401  (the error publishers raise, re-exported for them)

# tag key -> (label, tint token name, icon name)
TAGS = {"kid": ("Kid friendly", "sun", "kid"), "pet": ("Pet friendly", "mint", "paw"), "couple": ("Couple friendly", "bubble", "couple")}
MAX_TEXT = 60
DEFAULT_PHOTO = ("/assets/photos/santa-monica-beach-pier.jpg", "Santa Monica Pier")
COVERS = {"pier": DEFAULT_PHOTO, "venice": (itineraries.VENICE, "Venice Beach, Los Angeles")}  # cover photo keys a creator trip can use


@dataclass(frozen=True)
class HubCard:
    slug: str
    title: str
    place: str
    days: int
    author: str
    tags: tuple = ()          # keys of TAGS
    forks: int = 0
    source: str = ""          # "YouTube", "Instagram"... for creator itineraries
    photo: str = ""
    alt: str = ""
    theme: str = "sunset"
    mine: bool = False        # published by the signed-in traveler
    real: bool = False        # a real family's published trip (F-181): no sample fork count, no "from creators" source
    handle: str = ""          # a real trip's creator profile


def has_shared() -> bool:
    """True once anyone has published a trip; until then the hub holds only the samples."""
    return bool(community.rows())


def tag_keys(trip) -> tuple:
    """Which of kid, pet and couple an itinerary is friendly to, read from its sticker labels."""
    return tuple(k for k, (label, *_rest) in TAGS.items() if any(t.label.startswith(label) for t in trip.tags))


def _from_itinerary(trip) -> HubCard:
    photo = trip.polaroids[0] if trip.polaroids else None
    parts = trip.source.byline.split(" · ") if trip.source else []
    source = parts[1] if len(parts) > 1 else ""
    return HubCard(trip.slug, trip.title, trip.place.split(",")[0], len(trip.days), trip.author, tag_keys(trip), trip.forks,
                   source, photo.src if photo else "", photo.alt if photo else "", trip.theme)


def all_cards(session) -> list:
    """Every trip in the hub: the fake community's first, then everything published (the signed-in person's marked `mine`).
    Off the showcase only real published trips are here (F-181), newest first."""
    me = (session or {}).get("user_id")
    real = not showcase.on()
    # TODO: paginate; this loads and parses every published snapshot on each hub request.
    published = [(r, _from_itinerary(community.trip_of(r))) for r in community.rows(kind="scrapbook" if real else "")]
    if real:
        published.reverse()
    cards = (replace(c, mine=bool(me) and r["owner_user"] == str(me), real=r["kind"] == "scrapbook", handle=r["meta"].get("handle", "")) for r, c in published)
    return [*(() if real else (_from_itinerary(t) for t in itineraries.ITINERARIES.values())), *cards]


_DISNEY = re.compile(r"disney\s?land|anaheim", re.I)       # not "Walt Disney Concert Hall" or "Disney Hall", which are downtown Los Angeles
_NOT_CALIFORNIA = re.compile(r"world|paris|tokyo|hong kong|shanghai|orlando|florida", re.I)   # Disneyland Resort is the one in Anaheim, not these


def focus_of(trip) -> str:
    """"disney" when a trip in the Los Angeles place is about Disneyland in Anaheim: its place, title, headline or lede says so (F-195). The Los Angeles place is also where
    other Los Angeles trips go, so its links (stays in Anaheim, Disneyland tickets) only apply to a trip that is one. "" for anything else."""
    said = f"{trip.place} {trip.title} {trip.headline} {trip.lede}"
    return "disney" if trip.plan_to == "la" and _DISNEY.search(said) and not _NOT_CALIFORNIA.search(said) else ""


def _params(trip) -> dict | None:
    """The trip a link from this page names: the place, sensible dates ahead for two adults, the focus, and whose trip it is (F-184). None
    when the trip's place is not one the workspace plans."""
    from gitaway import publish
    if not trip.plan_to:
        return None
    depart, ret = publish.sample_dates(trip.plan_days)
    focus = focus_of(trip)
    return {"to": trip.plan_to, "d": depart.isoformat(), "r": ret.isoformat(), "a": 2, **({"focus": focus} if focus else {}), **({"via": trip.handle} if trip.handle else {})}


def plan_href(trip) -> str:
    """"Plan this trip" for a real published trip: the booking workspace at the trip's place with sensible dates ahead (gitaway.publish.sample_dates), "" when
    the trip's place is not one the workspace plans. The reader says their party and airport on the page it opens (F-195)."""
    params = _params(trip)
    return "/plan?" + urlencode(params) if params else ""


def todo_href(trip) -> str:
    """The Tickets and things to do card of a real published trip: /go/search-todo with the same trip as "Plan this trip" (via: the click is theirs, F-195), "" when the place is not planned."""
    params = _params(trip)
    return "/go/search-todo?" + urlencode(params) if params else ""


def cards(session, *, tags=(), creators=False, q="") -> list:
    """The hub's cards. `tags` (kid, pet, couple) must all match; `creators` keeps trips that came from a vlog or post; `q` matches place or title."""
    wanted = [k for k in tags if k in TAGS]
    q = " ".join((q or "").split()).casefold()
    out = []
    for c in all_cards(session):
        if any(k not in c.tags for k in wanted) or (creators and not c.source):
            continue
        if q and q not in f"{c.place} {c.title}".casefold():
            continue
        out.append(c)
    return out
