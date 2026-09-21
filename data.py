"""Local fixture storage for the TravelOS demo.

Public discovery content lives in code so it remains deterministic. Workspace actions
use fh-saas' host/tenant SQLite boundary: the demo traveler belongs to one tenant and
forks/submissions are stored only in that tenant database.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fh_saas import db_host as fh_host
from fh_saas import db_tenant as fh_tenant
from fh_saas.db_host import GlobalUser, HostDatabase, Membership, gen_id, timestamp
from fh_saas.db_tenant import get_or_create_tenant_db
from fh_saas.utils_db import register_tables
from sqlalchemy import text

from models import CreatorSubmission, Trip, TripFork, TripPreferences

DEMO_USER_ID = "travelos-demo-traveler"
DEMO_TENANT_ID = "travelos-weekend-club"
DEMO_TENANT_NAME = "Weekend Club"

# fh-saas creates a SQLAlchemy connection for each tenant database object. The
# demo has one fixed tenant per process, so retain its table registry instead
# of opening a new pool checkout for every workspace render or save.
_TENANT_TABLES: tuple[Any, dict[str, Any]] | None = None


def _normalize_fh_saas_model_fields() -> None:
    """Keep fh-saas 0.9.14's annotation-only models usable on Python 3.14.

    ``fastsql`` turns these models into dataclasses at first table creation.
    Some fh-saas models declare a required timestamp after optional fields, which
    Python 3.14 correctly rejects. Reordering the annotations before fastsql
    sees them preserves every field and default while making the host/tenant
    schemas portable. This compatibility shim can be deleted once fh-saas
    ships models with required fields first.
    """
    models = (
        fh_host.GlobalUser,
        fh_host.TenantCatalog,
        fh_host.Membership,
        fh_host.Subscription,
        fh_host.HostAuditLog,
        fh_host.SystemJob,
        fh_host.PricingPlan,
        fh_host.StripeWebhookEvent,
        fh_tenant.TenantUser,
        fh_tenant.TenantPermission,
        fh_tenant.TenantSettings,
    )
    for model in models:
        fields = model.__annotations__
        required = {name: annotation for name, annotation in fields.items() if not hasattr(model, name)}
        optional = {name: annotation for name, annotation in fields.items() if hasattr(model, name)}
        model.__annotations__ = required | optional


_normalize_fh_saas_model_fields()

PUBLIC_TRIPS: list[dict[str, Any]] = [
    {
        "slug": "granada-after-dark",
        "title": "Granada after dark",
        "destination": "Granada, Spain",
        "region": "Europe",
        "days": 4,
        "price": "$624",
        "hero": "granada",
        "creator": "Lina Morales",
        "creator_role": "City filmmaker · 42.8K on YouTube",
        "avatar": "LM",
        "saves": "1.8k",
        "summary": "Courtyards, late tapas, an Alhambra sunrise, and the room to wander.",
        "tags": ["Food-forward", "Walkable", "Spring"],
        "weather": "22° / clear",
        "dates": "Apr 12–16",
        "start_date": "2025-04-12",
        "route": ["Albaicín", "Centro", "Sacromonte"],
        "creator_bio": "Granada city filmmaker who plans around first light, tiled courtyards, and the last useful bus home.",
        "creator_location": "Granada-based · filming local food and street life",
        "creator_channels": [("YouTube", "Lina Morales", "42.8K fixture subscribers"), ("Instagram", "@linaafterdark", "18.4K fixture followers")],
        "creator_note": "Start with one booked anchor, then protect the blank space around it. Granada gets better after you stop trying to win it in a day.",
        "best_for": "First-time visitors who like a late dinner and a walkable base",
        "planning_notes": ["Book the Alhambra anchor before choosing the rest of the day.", "Stay near Plaza Nueva so the first and last walks stay easy.", "Carry a light layer—the hillside changes character after sunset."],
    },
    {
        "slug": "kyoto-rainy-season",
        "title": "Kyoto in the rain",
        "destination": "Kyoto, Japan",
        "region": "Asia",
        "days": 5,
        "price": "$918",
        "hero": "kyoto",
        "creator": "Hana & Kenji",
        "creator_role": "Slow travel notes · 116K on Instagram",
        "avatar": "HK",
        "saves": "3.2k",
        "summary": "Mossy temple paths, tiny coffee bars, and the best hours to be outside.",
        "tags": ["Culture", "Rain plan", "Couples"],
        "weather": "19° / misty",
        "dates": "Jun 03–08",
        "start_date": "2025-06-03",
        "route": ["Gion", "Higashiyama", "Arashiyama"],
        "creator_bio": "A two-person slow-travel notebook for rain-softened lanes, tiny coffee counters, and patient mornings.",
        "creator_location": "Kyoto field notes · slow travel duo",
        "creator_channels": [("Instagram", "@hanaandkenji", "116K fixture followers"), ("YouTube", "Hana & Kenji", "24K fixture subscribers")],
        "creator_note": "Rain is not a backup plan here. Move slowly, keep one dry-room pause nearby, and let the temples empty out.",
        "best_for": "Couples and solo travelers who prefer a soft-weather rhythm",
        "planning_notes": ["Keep a covered coffee stop between outdoor anchors.", "Start temple walks early, then let the rain choose the smaller lanes.", "Pack shoes that stay comfortable on damp stone."],
    },
    {
        "slug": "oaxaca-color-weekend",
        "title": "A color-filled Oaxaca weekend",
        "destination": "Oaxaca, Mexico",
        "region": "Americas",
        "days": 3,
        "price": "$441",
        "hero": "oaxaca",
        "creator": "Maya Sol",
        "creator_role": "Food & design storyteller · 78K on YouTube",
        "avatar": "MS",
        "saves": "987",
        "summary": "Market breakfasts, studio visits, mezcal notes, and one brilliant blue hotel.",
        "tags": ["Food-forward", "Design", "Weekend"],
        "weather": "27° / warm",
        "dates": "May 24–27",
        "start_date": "2025-05-24",
        "route": ["Centro", "Jalatlaco", "Tlacolula"],
        "creator_bio": "Food and design storyteller with a notebook full of market counters, studio doors, and bright blue facades.",
        "creator_location": "Oaxaca regular · food + design field notes",
        "creator_channels": [("YouTube", "Maya Sol", "78K fixture subscribers"), ("Instagram", "@mayasolgoes", "31K fixture followers")],
        "creator_note": "Eat your first meal in the market, make room for a studio conversation, and never schedule mezcal before the color of the sky changes.",
        "best_for": "A long weekend with appetite, curiosity, and room for detours",
        "planning_notes": ["Use the market breakfast to set the day’s direction.", "Ask before photographing a working studio.", "Leave a late-afternoon gap before your mezcal stop."],
    },
    {
        "slug": "cape-town-blue-hour",
        "title": "Cape Town, blue hour to blue hour",
        "destination": "Cape Town, South Africa",
        "region": "Africa",
        "days": 6,
        "price": "$1,104",
        "hero": "capetown",
        "creator": "Nico Bell",
        "creator_role": "Adventure editor · 54K on Instagram",
        "avatar": "NB",
        "saves": "2.1k",
        "summary": "A peninsula loop, cliffside coffee, and a city itinerary that stays breathable.",
        "tags": ["Outdoors", "Road trip", "Friends"],
        "weather": "20° / breezy",
        "dates": "Nov 09–15",
        "start_date": "2025-11-09",
        "route": ["City Bowl", "Camps Bay", "Cape Point"],
        "creator_bio": "Adventure editor balancing an open-road instinct with useful city timing and weather-aware turnarounds.",
        "creator_location": "Cape Town editor · road and coast routes",
        "creator_channels": [("Instagram", "@nicobelloutside", "54K fixture followers"), ("YouTube", "Nico Bell", "19K fixture subscribers")],
        "creator_note": "The coast rewards an early start and a flexible finish. Keep the dramatic bit optional so the good weather can lead.",
        "best_for": "Friends who want a road-trip feeling without a frantic schedule",
        "planning_notes": ["Use the peninsula loop only when the weather window is clear.", "Keep a city alternative for windy afternoons.", "Bring layers even when the morning starts warm."],
    },
]


def public_trip(slug: str) -> dict[str, Any] | None:
    return next((trip for trip in PUBLIC_TRIPS if trip["slug"] == slug), None)


def discovery_trips(query: str = "", region: str = "") -> list[dict[str, Any]]:
    """Filter deterministic public fixtures without calling a travel provider."""
    query = query.strip().lower()
    region = region.strip().lower()
    results = PUBLIC_TRIPS
    if query:
        results = [
            trip
            for trip in results
            if query in " ".join((trip["title"], trip["destination"], trip["creator"], *trip["tags"])).lower()
        ]
    if region and region != "all":
        results = [trip for trip in results if trip["region"].lower() == region]
    return results


def _data_directory() -> Path:
    location = Path(os.getenv("TRAVELOS_DATA_DIR", Path(__file__).parent / "data")).resolve()
    location.mkdir(parents=True, exist_ok=True)
    return location


def _configure_local_sqlite() -> None:
    """Point fh-saas at local SQLite files and keep its tenant files out of source."""
    data_dir = _data_directory()
    os.environ["DB_TYPE"] = "SQLITE"
    os.environ["DB_NAME"] = "travelos_host"
    # fh-saas derives a tenant SQLite filename from the process working directory.
    # The demo keeps that process-local storage under data/ rather than requiring Postgres.
    if Path.cwd() != data_dir:
        os.chdir(data_dir)


def _first(table, where: str, where_args: dict[str, str]):
    matches = table(where=where, where_args=where_args, limit=1)
    return matches[0] if matches else None


def _tenant_tables():
    global _TENANT_TABLES
    if _TENANT_TABLES:
        return _TENANT_TABLES
    tenant_db = get_or_create_tenant_db(DEMO_TENANT_ID, DEMO_TENANT_NAME)
    tables = register_tables(
        tenant_db,
        [
            (Trip, "trips", "id"),
            (TripFork, "trip_forks", "id"),
            (TripPreferences, "trip_preferences", "id"),
            (CreatorSubmission, "creator_submissions", "id"),
        ],
    )
    _TENANT_TABLES = tenant_db, tables
    return _TENANT_TABLES


def bootstrap_store() -> None:
    """Provision the one local demo identity and its isolated workspace once."""
    _configure_local_sqlite()
    host_db = HostDatabase.from_env()
    if not _first(host_db.global_users, "id = :id", {"id": DEMO_USER_ID}):
        host_db.global_users.insert(
            GlobalUser(
                id=DEMO_USER_ID,
                email="traveler@travelos.local",
                oauth_id="local-demo",
                created_at=timestamp(),
            )
        )
        host_db.commit()

    # get_or_create_tenant_db registers the tenant in the host catalog.
    _tenant_tables()
    if not _first(
        host_db.memberships,
        "user_id = :user_id AND tenant_id = :tenant_id",
        {"user_id": DEMO_USER_ID, "tenant_id": DEMO_TENANT_ID},
    ):
        host_db.memberships.insert(
            Membership(
                id=gen_id(),
                user_id=DEMO_USER_ID,
                tenant_id=DEMO_TENANT_ID,
                profile_id="travelos-demo-profile",
                role="owner",
                created_at=timestamp(),
            )
        )
        host_db.commit()


PACE_OPTIONS = ("slow", "balanced", "full")
INTEREST_OPTIONS = ("Food-forward", "Culture", "Outdoors", "Nightlife", "Design")


def _default_preferences(trip: Trip) -> TripPreferences:
    plan = public_trip(trip.slug) or {}
    return TripPreferences(
        id=gen_id(),
        trip_id=trip.id,
        start_date=str(plan.get("start_date", "2025-04-12")),
        group_size=2,
        budget=1300,
        pace="balanced",
        interests="Food-forward,Culture",
        updated_at=timestamp(),
    )


def trip_preferences(trip: Trip) -> TripPreferences:
    """Return one persisted planning profile, creating the useful local defaults once."""
    tenant_db, tables = _tenant_tables()
    preferences = _first(tables["trip_preferences"], "trip_id = :trip_id", {"trip_id": trip.id})
    if preferences:
        return preferences
    preferences = _default_preferences(trip)
    tables["trip_preferences"].insert(preferences)
    tenant_db.conn.commit()
    return preferences


def update_trip_preferences(
    trip: Trip,
    *,
    start_date: str,
    group_size: int,
    budget: int,
    pace: str,
    interests: list[str],
) -> TripPreferences:
    """Persist validated local planning inputs for a forked trip.

    The values intentionally tune only fixture-derived workspace views. No price,
    itinerary, booking, or creator provider is contacted.
    """
    from datetime import date

    try:
        date.fromisoformat(start_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("Choose a valid trip start date.") from exc
    if not 1 <= group_size <= 12:
        raise ValueError("Choose between 1 and 12 travelers.")
    if not 300 <= budget <= 25000:
        raise ValueError("Choose a total comfort budget between $300 and $25,000.")
    if pace not in PACE_OPTIONS:
        raise ValueError("Choose a supported trip pace.")
    selected_interests = [interest for interest in INTEREST_OPTIONS if interest in interests]
    if not selected_interests:
        raise ValueError("Choose at least one trip interest.")

    tenant_db, tables = _tenant_tables()
    preferences = _first(tables["trip_preferences"], "trip_id = :trip_id", {"trip_id": trip.id})
    if not preferences:
        preferences = _default_preferences(trip)
        tables["trip_preferences"].insert(preferences)

    # fh-saas gives this demo a SQLite tenant connection; using a parameterized
    # update keeps the small planning record durable without a provider adapter.
    tenant_db.conn.execute(
        text(
            """UPDATE trip_preferences
               SET start_date = :start_date, group_size = :group_size, budget = :budget,
                   pace = :pace, interests = :interests, updated_at = :updated_at
               WHERE trip_id = :trip_id"""
        ),
        {
            "start_date": start_date,
            "group_size": group_size,
            "budget": budget,
            "pace": pace,
            "interests": ",".join(selected_interests),
            "updated_at": timestamp(),
            "trip_id": trip.id,
        },
    )
    tenant_db.conn.commit()
    return _first(tables["trip_preferences"], "trip_id = :trip_id", {"trip_id": trip.id})


def fork_plan(source_slug: str, user_id: str = DEMO_USER_ID) -> Trip:
    """Copy a public fixture into the signed-in tenant's workspace.

    This is the intended provider boundary: an adapter can later hydrate prices,
    reservations, and identity without changing the public plan contract.
    """
    plan = public_trip(source_slug)
    if not plan:
        raise KeyError(source_slug)

    tenant_db, tables = _tenant_tables()
    existing = _first(
        tables["trip_forks"],
        "source_slug = :source_slug AND user_id = :user_id",
        {"source_slug": source_slug, "user_id": user_id},
    )
    if existing:
        trip = _first(tables["trips"], "id = :id", {"id": existing.trip_id})
        if trip:
            trip_preferences(trip)
            return trip

    trip = Trip(
        id=gen_id(),
        slug=source_slug,
        title=plan["title"],
        destination=plan["destination"],
        days=plan["days"],
        traveler_name="Ari",
        created_at=timestamp(),
    )
    tables["trips"].insert(trip)
    tables["trip_forks"].insert(
        TripFork(
            id=gen_id(),
            source_slug=source_slug,
            trip_id=trip.id,
            user_id=user_id,
            created_at=timestamp(),
        )
    )
    tenant_db.conn.commit()
    trip_preferences(trip)
    return trip


def latest_workspace_trip(user_id: str = DEMO_USER_ID) -> Trip | None:
    tenant_db, tables = _tenant_tables()
    forks = tables["trip_forks"](where="user_id = :user_id", where_args={"user_id": user_id})
    if not forks:
        return None
    latest = sorted(forks, key=lambda item: item.created_at, reverse=True)[0]
    return _first(tables["trips"], "id = :id", {"id": latest.trip_id})


def save_creator_submission(payload: dict[str, str]) -> CreatorSubmission:
    """Persist a local creator pitch in the tenant workspace; no social APIs are called."""
    tenant_db, tables = _tenant_tables()
    submission = CreatorSubmission(
        id=gen_id(),
        creator_name=payload["creator_name"].strip(),
        email=payload["email"].strip(),
        destination=payload["destination"].strip(),
        story_title=payload["story_title"].strip(),
        youtube=payload.get("youtube", "").strip(),
        instagram=payload.get("instagram", "").strip(),
        note=payload.get("note", "").strip(),
        created_at=timestamp(),
    )
    tables["creator_submissions"].insert(submission)
    tenant_db.conn.commit()
    return submission
