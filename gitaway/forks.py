"""The traveler's forks and saved trips as things a page can show (F-021).

The family's database keeps only slugs (see gitaway.familydb_social). This module turns a slug into the trip behind it,
whichever kind it is: a sample community itinerary, or a trip published to the community database (shared or creator).
A slug whose trip is gone (its owner unpublished it) is simply not listed.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date, timedelta

from gitaway import community, hub, itineraries, publish, session as ses, showcase
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
    return (itineraries.get(slug) if showcase.on() else None) or community.find(slug)  # off the showcase there are no samples to fork (F-064)


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
    slugs = ses.forks(session)  # one query on the family database
    samples = sum(1 for s in slugs if s in itineraries.ITINERARIES)
    return samples + community.existing([s for s in slugs if s not in itineraries.ITINERARIES])  # one query on the community database


# ---- a fork lands something (F-196) ----------------------------------------------------------------------------------------------------------

START_AHEAD = 30      # days from today that a trip made from a fork starts: a placeholder the family changes under Trip details


def _words(text) -> set:
    return set(re.findall(r"[^\W\d_]{4,}", str(text or "").casefold()))


def other_place(trip, my_place, airports=()) -> str:
    """The fork's place (as the fork names it) when it is not where the open trip goes, else "". Both are put on the catalog's places (Los Angeles, San Diego, Honolulu, New York) when they name one,
    so "Anaheim" and "Los Angeles" are the same; a place the catalog does not know is the same when the two names share a word. A fork applied to another place lands its days in the wrong city."""
    theirs, mine = trip.plan_to or publish.place_key(trip.place), publish.place_key(my_place, airports)
    if theirs and mine:
        return "" if theirs == mine else trip.place
    if not trip.place or not my_place:
        return ""
    return "" if _words(trip.place) & _words(my_place) else trip.place


def start_trip(session, trip) -> str:
    """Make the signed-in family a trip from a fork, for a family that has none: "Trip to <place>", the fork's place and as many days as it has (at most a trip can have), starting START_AHEAD days
    from today, one adult (the person), no flights or stay (they add those later). It is the importer's saved trip, so Trip details edits it. The id comes from the person and the fork, so
    applying twice makes one trip. Returns the trip's id; raises importer.SaveError (the family has too many trips)."""
    from gitaway import importer, tripimport as ti  # here, not at the top: the importer reads the family through gitaway.session
    me = ses.current_traveler(session)
    start = date.today() + timedelta(days=START_AHEAD)
    plan = ti.Plan(title=f"Trip to {trip.place}"[:60], destination=trip.place[:60], start=start, end=start + timedelta(days=min(max(len(trip.days), 1), ti.MAX_DAYS) - 1), booked_on="elsewhere", itinerary="",
                   travelers=(ti.Traveler(((me.name if me else "") or "Traveler")[:40]),))
    return importer.save(session, plan, hashlib.sha256(f"fork|{me.id}|{trip.slug}".encode()).hexdigest()[:12])
