"""The traveler's forks and saved trips as things a page can show (F-021).

The family's database keeps only slugs (see gitaway.familydb_social). This module turns a slug into the trip behind it,
whichever kind it is: a sample community itinerary, or a trip published to the community database (shared or creator).
A slug whose trip is gone (its owner unpublished it) is simply not listed.
"""

from dataclasses import dataclass

from gitaway import community, hub, itineraries, session as ses
from gitaway.itineraries import PIER


@dataclass(frozen=True)
class Entry:
    slug: str
    title: str
    days: int
    author: str
    tags: tuple     # hub tag keys
    photo: str
    alt: str
    trip: object    # the gitaway.itineraries.Itinerary


def resolve(slug):
    """The Itinerary behind a trip slug (a sample or a published trip), or None when it does not exist (any more)."""
    return itineraries.get(slug) or community.find(slug)


def entry(session, slug):
    """The Entry for a trip slug, or None when the trip does not exist (any more)."""
    trip = resolve(slug)
    return _entry(trip) if trip else None


def _entry(trip) -> Entry:
    shot = trip.polaroids[0] if trip.polaroids else None
    return Entry(trip.slug, trip.title, len(trip.days), trip.author, hub.tag_keys(trip),
                 shot.src if shot else PIER, shot.alt if shot else "Santa Monica Pier", trip)


def _entries(session, slugs) -> list:
    trips = (resolve(s) for s in slugs)
    return [_entry(t) for t in trips if t]


def forked(session) -> list:
    """The signed-in traveler's forks, oldest first, skipping trips that no longer exist."""
    return _entries(session, ses.forks(session))


def saved(session) -> list:
    """The trips saved with the heart that are not also forked (a fork is already in the list), oldest first."""
    mine = set(ses.forks(session))
    return _entries(session, [s for s in ses.saved(session) if s not in mine])


def count(session) -> int:
    """How many forks the traveler has (the number on the calendar's Your forks button)."""
    return len(forked(session))
