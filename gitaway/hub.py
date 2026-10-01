"""The community hub's model (F-022, F-041): which trips it lists, how they filter, and how a trip gets added.

The hub lists the fake community itineraries in `gitaway.itineraries` plus every trip published to the community database
(`gitaway.community`): families' shared trips and creators' trips. Publishing is the one door in, through `gitaway.share`
and `gitaway.creators`, which freeze the page as a snapshot. Everything published is listed for everyone, signed in or out;
cards published by the signed-in traveler are marked `mine`.

Pure functions over a session dict (for the signed-in person) and the community database.
"""

from dataclasses import dataclass, replace

from gitaway import community, itineraries
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
    """Every trip in the hub: the fake community's first, then everything published (the signed-in person's marked `mine`)."""
    me = (session or {}).get("user_id")
    published = [(r, _from_itinerary(community.trip_of(r))) for r in community.rows()]
    return [*(_from_itinerary(t) for t in itineraries.ITINERARIES.values()),
            *(replace(c, mine=bool(me) and r["owner_user"] == str(me)) for r, c in published)]


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
