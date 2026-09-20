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

from models import CreatorSubmission, Trip, TripFork

DEMO_USER_ID = "travelos-demo-traveler"
DEMO_TENANT_ID = "travelos-weekend-club"
DEMO_TENANT_NAME = "Weekend Club"


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
        "route": ["Albaicín", "Centro", "Sacromonte"],
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
        "route": ["Gion", "Higashiyama", "Arashiyama"],
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
        "route": ["Centro", "Jalatlaco", "Tlacolula"],
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
        "route": ["City Bowl", "Camps Bay", "Cape Point"],
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
    tenant_db = get_or_create_tenant_db(DEMO_TENANT_ID, DEMO_TENANT_NAME)
    tables = register_tables(
        tenant_db,
        [
            (Trip, "trips", "id"),
            (TripFork, "trip_forks", "id"),
            (CreatorSubmission, "creator_submissions", "id"),
        ],
    )
    return tenant_db, tables


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
