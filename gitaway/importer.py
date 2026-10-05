"""Save an imported trip into the signed-in person's family (F-042). The parsing is gitaway.tripimport; the storage is gitaway.familydb_import.

An imported trip is an ordinary family trip (a `trips` row, source "imported") plus its document (a `trip_imports` row), written in one short
transaction. Its id is random; the preview hands out one (`new_token`) and the save uses it, so pressing Save twice makes one trip.

Correcting an import. A template with the same itinerary number (or the same title and start date) as a trip the family already imported
is a correction: `find_match` says which trip, and `save(..., replace=<id>)` swaps the trip's document and dates in place, keeping its
calendar plans, notes, friends and rides. `delete` removes an imported trip and everything that belongs to it, its shared page too.
"""

import json
import re
from dataclasses import replace
import uuid

from fh_saas.utils_sql import insert_only

from gitaway import catalog, community, familydb, familydb_import, session as ses, share, tripimport

_TOKEN = re.compile(r"^[0-9a-f]{12}$")


class SaveError(ValueError):
    """A save the app refuses; the message is fit to show."""


def new_token() -> str:
    """A random trip id (12 hex characters), made when a preview is drawn."""
    return uuid.uuid4().hex[:12]


def _params(plan) -> str:
    return catalog.trip_query(tripimport.trip_search(plan))


def find_match(session, plan):
    """(trip id, title) of the family's imported trip this plan corrects, or None: the same itinerary number, else the same title and start date."""
    with ses.family(session) as fam:
        if not fam:
            return None
        for r in familydb.rows(fam.db, "SELECT t.id, t.title, i.doc FROM trips t JOIN trip_imports i ON i.trip_id = t.id WHERE t.source = 'imported' ORDER BY t.created_at DESC"):
            old = tripimport.from_doc(json.loads(r["doc"]))
            if (plan.itinerary and old.itinerary == plan.itinerary) or (old.title.casefold() == plan.title.casefold() and old.start == plan.start):
                return r["id"], r["title"]
    return None


def _ride_key(trip_id, plan):
    from gitaway import rides
    oid = familydb_import.offer_id(trip_id)
    return rides.context_key(oid if plan.legs else None, oid if plan.hotels else None, _params(plan))


def save(session, plan, token=None, replace=None) -> str:
    """Keep `plan` as a trip of the family and open it for this person. Returns the trip id. Raises SaveError.

    `token` is the trip id the preview made (a random one is made when there is none); saving the same token again opens that trip and changes
    nothing. With `replace` (an imported trip's id) that trip is corrected in place instead of a new one being made.
    """
    doc = tripimport.to_doc(plan)
    if token is not None and not _TOKEN.match(token):
        raise SaveError("That form is out of date. Preview your trip again.")
    with ses.family(session) as fam:
        if not fam:
            raise SaveError("Sign in to import a trip.")
        db = fam.db
        with familydb.transaction(db):
            familydb.lock(db)
            if replace:
                was = _stored(db, replace)
                trip_id = _replace(db, replace, plan, doc)
                if _stored(db, trip_id) != was:   # a save that changed nothing says nothing to the family
                    from gitaway import familythread  # here: familythread -> morning -> tripcal
                    familythread.change(session, fam, f"{familythread.first_name(fam.traveler)} updated the trip details: {plan.title}", trip_id=trip_id, action="change")
            else:
                trip_id = token or new_token()
                if not familydb.trip(db, trip_id):
                    if familydb.row(db, "SELECT COUNT(*) AS n FROM trips")["n"] >= familydb.MAX_TRIPS:
                        raise SaveError(f"That is {familydb.MAX_TRIPS} trips already. This demo keeps it small.")
                    at = familydb.now()
                    insert_only(db, "trips", {"id": trip_id, "title": plan.title, "source": tripimport.SOURCE, "params": _params(plan),
                                              "depart": plan.start.isoformat(), "return_on": plan.end.isoformat(), "created_by": fam.traveler.id, "created_at": at,
                                              "timezone": plan.timezone},
                                ["id"], auto_commit=False)
                    insert_only(db, "trip_imports", {"trip_id": trip_id, "doc": json.dumps(doc, separators=(",", ":")), "created_by": fam.traveler.id, "created_at": at},
                                ["trip_id"], auto_commit=False)
            familydb.run(db, "UPDATE members SET trip_id = :t WHERE id = :u", t=trip_id, u=fam.traveler.id)
    from gitaway import tripgeo  # here: tripgeo reads the trip back through gitaway.session
    try:
        tripgeo.warm(session, force=True)  # find the trip's places in the background (F-068); a failure here never undoes the save
    except Exception:
        pass
    return trip_id


def _retimes(db, trip_id, old_key, plan) -> list:
    """[(ride row id, the ride moved to the corrected trip)] for the scheduled Uber rides whose time or place the correction changes."""
    from gitaway import rides
    if plan.rental or not plan.legs:
        return []
    oid = familydb_import.offer_id(trip_id)
    flight, trip = tripimport.flight_offer(plan, oid), tripimport.trip_search(plan)
    out = []
    for r in familydb.rows(db, "SELECT id, data FROM rides WHERE key = :k", k=old_key):
        moved = rides.retime(rides.from_dict(json.loads(r["data"])), flight, tripimport.stay_offer(plan, oid, rides.from_dict(json.loads(r["data"])).leg), trip)
        if moved:
            out.append((r["id"], moved))
    return out


def rides_to_retime(session, trip_id, plan) -> int:
    """How many scheduled rides replacing trip `trip_id` with `plan` would move (for the preview)."""
    with ses.family(session) as fam:
        old = familydb.row(fam.db, "SELECT i.doc FROM trip_imports i WHERE i.trip_id = :t", t=trip_id) if fam else None
        return len(_retimes(fam.db, trip_id, _ride_key(trip_id, tripimport.from_doc(json.loads(old["doc"]))), plan)) if old else 0


def _stored(db, trip_id):
    """What is saved for an imported trip (its row and document), to tell whether a correction changed anything."""
    return familydb.row(db, "SELECT t.title, t.params, t.depart, t.return_on, t.timezone, i.doc FROM trips t JOIN trip_imports i ON i.trip_id = t.id WHERE t.id = :t", t=trip_id)


def _replace(db, trip_id, plan, doc) -> str:
    """Swap the document and dates of the imported trip `trip_id`; its plans, notes, friends and rides stay (the rides follow the new picks' key)."""
    old = familydb.row(db, "SELECT t.params, i.doc FROM trips t JOIN trip_imports i ON i.trip_id = t.id WHERE t.id = :t AND t.source = 'imported'", t=trip_id)
    if not old:
        raise SaveError("That trip is not there any more. Save it as a new trip instead.")
    before = tripimport.from_doc(json.loads(old["doc"]))
    old_key, new_key = _ride_key(trip_id, before), _ride_key(trip_id, plan)
    moved = dict(_retimes(db, trip_id, old_key, plan))  # a scheduled ride follows the corrected flight times; one with a driver on the way stays
    familydb.run(db, "UPDATE trips SET title = :ti, params = :p, depart = :d, return_on = :r, timezone = :z WHERE id = :t", ti=plan.title, p=_params(plan), d=plan.start.isoformat(),
                 r=plan.end.isoformat(), z=plan.timezone, t=trip_id)
    familydb.run(db, "UPDATE trip_imports SET doc = :doc WHERE trip_id = :t", doc=json.dumps(doc, separators=(",", ":")), t=trip_id)
    if old_key != new_key or moved:
        for r in familydb.rows(db, "SELECT id, data FROM rides WHERE key = :k", k=old_key):
            from gitaway import rides
            data = rides.to_dict(replace(moved[r["id"]], key=new_key)) if r["id"] in moved else json.loads(r["data"])
            data["k"] = new_key
            familydb.run(db, "UPDATE rides SET key = :k, data = :d WHERE id = :i", k=new_key, d=json.dumps(data, separators=(",", ":")), i=r["id"])
    return trip_id


def delete(session, trip_id) -> bool:
    """Remove an imported trip and everything that belongs to it (its document, calendar plans, notes, friends and rides). False when it is not one."""
    with ses.family(session) as fam:
        if not fam:
            return False
        db = fam.db
        with familydb.transaction(db):
            familydb.lock(db)
            old = familydb.row(db, "SELECT i.doc FROM trips t JOIN trip_imports i ON i.trip_id = t.id WHERE t.id = :t AND t.source = 'imported'", t=trip_id)
            if not old:
                return False
            key = _ride_key(trip_id, tripimport.from_doc(json.loads(old["doc"])))
            booking = familydb.booking_for_trip(db, trip_id)
            for table in ("activities", "notes", "cal_state", "friends", "thread", "photos", "passes", "pass_flights", "block_parts", "block_steps", "trip_lists", "trip_list_items"):   # the thread (F-070), passes (F-083) and the canvas parts, steps and lists (F-080) go too
                familydb.run(db, f"DELETE FROM {table} WHERE trip_id = :t", t=trip_id)
            familydb.run(db, "DELETE FROM rides WHERE trip_id = :t OR key = :k", t=trip_id, k=key)
            familydb.run(db, "DELETE FROM trip_imports WHERE trip_id = :t", t=trip_id)
            familydb.run(db, "DELETE FROM trips WHERE id = :t", t=trip_id)
            familydb.run(db, "UPDATE members SET trip_id = NULL WHERE trip_id = :t", t=trip_id)
        from gitaway import photos
        photos.purge_trip(session.get("tenant_id"), trip_id)   # the picture files, once the rows are gone (F-071)
        from gitaway import passes, voicenotes
        passes.purge_trip(session.get("tenant_id"), trip_id)   # and the boarding pass files (F-083)
        voicenotes.purge_trip(session.get("tenant_id"), trip_id)   # and the voice notes (F-091)
        for row in community.rows(kind="shared"):  # a shared page of this trip (by whoever shared it) comes down with it
            if booking and share.slug_for(row["owner_user"], booking) == row["slug"]:
                community.unpublish({"user_id": row["owner_user"]}, row["slug"])
        return True


def plan_of(session, trip_id=None):
    """The Plan of the imported trip `trip_id` (default: the one this person has open), or None when that is not an imported trip."""
    with ses.family(session) as fam:
        if not fam:
            return None
        b = familydb.booking_for_trip(fam.db, trip_id or fam.trip_id)
        return tripimport.from_doc(b["imported"]) if b and b.get("imported") else None
