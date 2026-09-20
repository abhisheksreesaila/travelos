"""Tenant-scoped TravelOS records.

The dataclass models are intentionally compatible with ``fh_saas.utils_db``.
Production can extend these records without changing the public fixture routes.
"""

from dataclasses import dataclass


@dataclass
class Trip:
    id: str
    slug: str
    title: str
    destination: str
    days: int
    traveler_name: str
    status: str = "planned"
    created_at: str = ""


@dataclass
class TripFork:
    id: str
    source_slug: str
    trip_id: str
    user_id: str
    created_at: str


@dataclass
class CreatorSubmission:
    id: str
    creator_name: str
    email: str
    destination: str
    story_title: str
    youtube: str = ""
    instagram: str = ""
    note: str = ""
    status: str = "received"
    created_at: str = ""
