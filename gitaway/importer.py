"""Save an imported trip into the signed-in person's family (F-042). The parsing is gitaway.tripimport; the storage is gitaway.familydb_import.

An imported trip is an ordinary family trip (a `trips` row, source "imported") plus its document (a `trip_imports` row), written in one short
transaction. Saving the same template again opens the trip it made and changes nothing else (the id comes from the document), like paying the
same picks twice in the demo flow.
"""

import hashlib
import json

from fh_saas.utils_sql import insert_only

from gitaway import catalog, familydb, session as ses, tripimport


class SaveError(ValueError):
    """A save the app refuses; the message is fit to show."""


def trip_id_of(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]


def save(session, plan) -> str:
    """Keep `plan` as a new trip of the family and open it for this person. Returns the trip id. Raises SaveError."""
    doc = tripimport.to_doc(plan)
    trip_id = trip_id_of(doc)
    with ses.family(session) as fam:
        if not fam:
            raise SaveError("Sign in to import a trip.")
        db = fam.db
        with familydb.transaction(db):
            familydb.lock(db)
            if not familydb.trip(db, trip_id):
                if familydb.row(db, "SELECT COUNT(*) AS n FROM trips")["n"] >= familydb.MAX_TRIPS:
                    raise SaveError(f"That is {familydb.MAX_TRIPS} trips already. This demo keeps it small.")
                at = familydb.now()
                insert_only(db, "trips", {"id": trip_id, "title": plan.title, "source": tripimport.SOURCE, "params": catalog.trip_query(tripimport.trip_search(plan)),
                                          "depart": plan.start.isoformat(), "return_on": plan.end.isoformat(), "created_by": fam.traveler.id, "created_at": at},
                            ["id"], auto_commit=False)
                insert_only(db, "trip_imports", {"trip_id": trip_id, "doc": json.dumps(doc, separators=(",", ":")), "created_by": fam.traveler.id, "created_at": at},
                            ["trip_id"], auto_commit=False)
            familydb.run(db, "UPDATE members SET trip_id = :t WHERE id = :u", t=trip_id, u=fam.traveler.id)
    return trip_id


def plan_of(session, trip_id=None):
    """The Plan of the imported trip `trip_id` (default: the one this person has open), or None when that is not an imported trip."""
    with ses.family(session) as fam:
        if not fam:
            return None
        b = familydb.booking_for_trip(fam.db, trip_id or fam.trip_id)
        return tripimport.from_doc(b["imported"]) if b and b.get("imported") else None
