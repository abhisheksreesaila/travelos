"""Trips imported from elsewhere, stored per family (F-042).

One row per imported trip in `trip_imports`: the validated template as JSON (gitaway.tripimport.to_doc), including the
confirmation numbers, so it never leaves the family's own database. The trip itself is an ordinary `trips` row with
source "imported" (its real dates, so ordering and the switcher work), and `booking(db, trip)` reads the document back as the
booking dict every screen already understands (see gitaway.familydb.booking_for_trip), with the document under "imported".

The tables are part of the family database (gitaway.familydb appends IMPORT_TABLES to FAMILY_TABLES). A new table needs no
migration: it is made when a family is next opened. See docs/family-db.md.
"""

import json


class TripImport:
    """The document of one imported trip: the whole filled-in template, as JSON. Confirmation numbers live here and nowhere else."""
    trip_id: str
    doc: str
    created_by: str
    created_at: str


IMPORT_TABLES = [(TripImport, "trip_imports", "trip_id")]

OFFER = "imp-"   # the prefix of the ids an imported trip's flight, stay and car carry: "imp-<trip id>"


def offer_id(trip_id) -> str:
    return OFFER + trip_id


def is_offer(value) -> bool:
    return isinstance(value, str) and value.startswith(OFFER)


def booking(db, trip) -> dict | None:
    """The booking dict of an imported trip row (`trip`), or None when its document is missing."""
    from gitaway import familydb, tripimport  # here, not at the top: familydb loads this module
    found = familydb.row(db, "SELECT doc FROM trip_imports WHERE trip_id = :t", t=trip["id"])
    if not found:
        return None
    doc = json.loads(found["doc"])
    plan = tripimport.from_doc(doc)
    oid = offer_id(trip["id"])
    return {"id": "IM-" + trip["id"].upper(), "flight": oid if plan.legs else None, "stay": oid if plan.hotels else None, "car": oid if plan.rental else None,
            "rooms": "", "add": "", "total_cents": 0, "booked_at": trip["created_at"], "trip": trip["params"] or "", "booked_by": trip["created_by"] or "", "imported": doc}
