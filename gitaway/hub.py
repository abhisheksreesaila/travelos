"""The community hub's model (F-022): which trips it lists, how they filter, and how a trip gets added.

The hub lists the fake community itineraries in `gitaway.itineraries` plus whatever the signed-in traveler has published
in this browser session (their shared trip, and later a creator import). Publishing is the one door in:

    hub.publish(session, slug=..., title=..., place=..., days=..., author=..., tags=("kid",), source="YouTube")

F-023 calls this to put a creator itinerary in the hub. The entry is only the card (compact, because the signed cookie
is small); the page behind `/trips/<slug>` is the caller's to serve. Publishing the same slug again replaces the entry.

Everything published in this browser session, by any demo traveler, is listed for everyone using it: that is the demo's
community. Cards published by the signed-in traveler are marked `mine`.

Session shape: {"hub": {"<traveler id>": [{"s": slug, "t": title, "p": place, "n": days, "a": author, "g": [tag keys],
                                           "k": source label or absent, "c": theme, "m": 1 when it is the traveler's own shared trip}]}}
Pure functions over a session dict, like gitaway.session.
"""

import json
from dataclasses import dataclass

from gitaway import itineraries, session as ses

# tag key -> (label, tint token name, icon name)
TAGS = {"kid": ("Kid friendly", "sun", "kid"), "pet": ("Pet friendly", "mint", "paw"), "couple": ("Couple friendly", "bubble", "couple")}
MAX_ENTRIES = 6
MAX_TEXT = 60
DEFAULT_PHOTO = ("/assets/photos/santa-monica-beach-pier.jpg", "Santa Monica Pier")


class HubError(ValueError):
    """A publish the demo refuses; the message is fit to show the traveler."""


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


def entries(session) -> list:
    """The signed-in traveler's published entries (raw rows), oldest first. Empty when signed out."""
    t = ses.current_traveler(session)
    return [dict(e) for e in (session.get("hub") or {}).get(t.id, [])] if t else []


def entry(session, slug):
    return next((e for e in entries(session) if e["s"] == slug), None)


def all_entries(session) -> list:
    """(traveler id, entry) for every traveler's published trip held in this browser session. The demo's community."""
    return [(tid, dict(e)) for tid, rows in (session.get("hub") or {}).items() if tid in ses.TRAVELERS for e in rows]


def _card(e, mine=False) -> HubCard:
    photo = DEFAULT_PHOTO if e.get("m") else ("", "")
    return HubCard(e["s"], e["t"], e["p"], e["n"], e["a"], tuple(e.get("g", ())), 0, e.get("k", ""), photo[0], photo[1],
                   e.get("c", "sunset"), mine)


def all_cards(session) -> list:
    """Every trip in the hub: the fake community's first, then everything published in this browser (yours marked `mine`)."""
    from gitaway import share  # here, not at the top: share imports this module
    me = ses.current_traveler(session)
    live = [(tid, e) for tid, e in all_entries(session) if not e.get("m") or share.is_live(session, tid, e["s"])]
    return [*(_from_itinerary(t) for t in itineraries.ITINERARIES.values()),
            *(_card(e, bool(me) and tid == me.id) for tid, e in live)]


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


def remove(session, slug) -> bool:
    """Take the signed-in traveler's entry out of the hub. False when there was none."""
    t = ses.current_traveler(session)
    have = entries(session)
    if not t or all(e["s"] != slug for e in have):
        return False
    session["hub"] = {**session["hub"], t.id: [e for e in have if e["s"] != slug]}
    return True


def publish(session, *, slug, title, place, days, author, tags=(), source="", theme="sunset", mine=False) -> HubCard:
    """Add a trip to the signed-in traveler's hub, or replace the entry with the same slug.

    Raises HubError when signed out, when a field is missing, or when the session cookie has no room left.
    """
    t = ses.current_traveler(session)
    if not t:
        raise HubError("Sign in to share a trip.")
    if not ses.trip_slug(f"/trips/{slug}") or not str(title).strip() or not str(place).strip():
        raise HubError("A shared trip needs a title and a place.")
    row = {"s": slug, "t": str(title)[:MAX_TEXT], "p": str(place)[:MAX_TEXT], "n": int(days), "a": str(author)[:MAX_TEXT],
           "g": [k for k in TAGS if k in tags], "c": theme if theme in ("sunset", "pacific") else "sunset"}
    if source:
        row["k"] = str(source)[:MAX_TEXT]
    if mine:
        row["m"] = 1
    have = entries(session)
    rows = [row if e["s"] == slug else e for e in have]
    if all(e["s"] != slug for e in have):
        if len(have) >= MAX_ENTRIES:
            raise HubError(f"That is {MAX_ENTRIES} shared trips already. This demo keeps it small.")
        rows.append(row)
    old = session.get("hub")
    # Reassign the whole dict so the cookie session notices the change.
    session["hub"] = {**(old or {}), t.id: rows}
    if len(json.dumps(dict(session))) > ses.BUDGET:
        if old is None:
            session.pop("hub", None)
        else:
            session["hub"] = old
        raise HubError("This demo is full. Delete something from your calendar to make room.")
    return _card(row)
