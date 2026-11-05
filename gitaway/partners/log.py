"""The family's partner clicks and sandbox bookings (autopilot M2/M3): the only code that touches the `partner_clicks` table.

A click is logged for a signed-in person (a signed-out click still redirects and is not logged, D-23). `book` records the simulated
conversion on a click and adds what was booked to the family's trip as an ordinary imported trip, "Booked elsewhere · <partner>" (the way a
pasted Expedia booking is shown): one trip per place and dates, so a flight, a stay and a car booked on three partners land together.
"""

import hashlib
import uuid
from dataclasses import replace
from datetime import datetime, timedelta

from fh_saas.utils_sql import insert_only

from gitaway import catalog, familydb, importer, session as ses, tripimport as ti
from gitaway.partners import for_offer

MAX_ORIGIN = 30   # how long the "Booked elsewhere" label may be (the trip builder's limit)


def new_click_id() -> str:
    return uuid.uuid4().hex[:10]


def sub_id(session, trip, offer) -> str:
    """The Travelpayouts SubID of a click: a short family hash, the place, the first day and the lane. No name, email or address (D-24)."""
    family = hashlib.sha256(str((session or {}).get("tenant_id") or "").encode()).hexdigest()[:6] if (session or {}).get("tenant_id") else "anon"
    return f"{family}-{trip.key}-{trip.depart:%y%m%d}-{offer.kind}"


def record_click(session, click_id, offer, trip, partner) -> str:
    """Log a click for the signed-in person's family. Returns its SubID (a signed-out click is not logged but has one)."""
    sub = sub_id(session, trip, offer)
    with ses.family(session) as fam:
        if fam:
            with familydb.transaction(fam.db):
                if not familydb.row(fam.db, "SELECT id FROM partner_clicks WHERE id = :i", i=click_id):
                    insert_only(fam.db, "partner_clicks", {"id": click_id, "user_id": fam.traveler.id, "offer_id": offer.id, "partner": partner.key, "lane": offer.kind,
                                                           "offer_name": offer.name, "place": trip.key, "query": catalog.trip_query(trip), "sub_id": sub,
                                                           "price_cents": offer.price_cents, "state": "clicked", "clicked_at": familydb.now()}, ["id"], auto_commit=False)
    return sub


def clicks(session) -> list:
    """The family's clicks and bookings, newest first. Empty when signed out."""
    with ses.family(session) as fam:
        return familydb.rows(fam.db, "SELECT * FROM partner_clicks ORDER BY clicked_at DESC, rowid DESC") if fam else []


def get(session, click_id):
    with ses.family(session) as fam:
        return familydb.row(fam.db, "SELECT * FROM partner_clicks WHERE id = :i", i=click_id) if fam else None


def _origin(old, new) -> str:
    names = [n for n in old.split(", ") if n and n != "elsewhere"]
    if new not in names:
        names.append(new)
    text = ", ".join(names)
    return text if len(text) <= MAX_ORIGIN else f"{len(names)} partners"


def plan_for(session, offer, trip, partner, confirmation) -> ti.Plan:
    """What booking `offer` on `partner` adds to the family's trip: the trip's party, and the one lane the offer is for."""
    adults = [ti.Traveler(ses.current_traveler(session).name if i == 0 else f"Adult {i + 1}") for i in range(trip.adults)]
    people = tuple(adults) + tuple(ti.Traveler(f"Kid {i + 1}", "", age) for i, age in enumerate(trip.kid_ages))
    at = lambda day, minutes: datetime.combine(day, datetime.min.time()) + timedelta(minutes=minutes)
    legs = hotels = ()
    rental = None
    if offer.kind == "flight":
        airline, _, number = offer.name.rpartition(" ")
        back_arrive = at(trip.return_, offer.back_arrive_min)
        back_depart = at(trip.return_, offer.back_depart_min)
        legs = (ti.Leg(airline, number, trip.origin, offer.airport, at(trip.depart, offer.depart_min), at(trip.depart, offer.arrive_min), confirmation),
                ti.Leg(airline, number, offer.airport, trip.origin, back_depart, back_arrive if back_arrive > back_depart else back_arrive + timedelta(days=1), confirmation))
    elif offer.kind == "stay":
        hotels = (ti.Lodging(offer.name, f"{offer.headline}, {trip.destination_name}", at(trip.depart, 15 * 60), at(trip.return_, 11 * 60), confirmation),)
    else:
        rental = ti.Rental(offer.name, f"{trip.airports[0]} airport", at(trip.depart, 12 * 60), f"{trip.airports[0]} airport", at(trip.return_, 12 * 60), confirmation, offer.headline)
    return ti.Plan(trip.title, trip.destination_name, trip.depart, trip.return_, partner.name, "", people, legs, hotels, rental)


def _merged(old: ti.Plan, new: ti.Plan) -> ti.Plan:
    """`old` with the lane `new` books swapped in (a second flight replaces the first), and the partner added to its label."""
    return replace(old, legs=new.legs or old.legs, hotels=new.hotels or old.hotels, rental=new.rental or old.rental, booked_on=_origin(old.booked_on, new.booked_on))


def book(session, click_id, offer, trip, partner):
    """Record the simulated conversion for a click and put the booking in the family's trip. Returns the click row, or None when signed out.

    Pressing it again changes nothing. Raises importer.SaveError when the family cannot take another trip.
    """
    done = get(session, click_id)
    if done and done["state"] == "booked":
        return done
    if not ses.current_traveler(session):
        return None
    confirmation = "GA-" + click_id.upper()
    plan = plan_for(session, offer, trip, partner, confirmation)
    match = importer.find_match(session, plan)
    if match:
        trip_id = importer.save(session, _merged(importer.plan_of(session, match[0]), plan), replace=match[0])
    else:
        trip_id = importer.save(session, plan)
    sub = record_click(session, click_id, offer, trip, partner)
    with ses.family(session) as fam:
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "UPDATE partner_clicks SET state = 'booked', booked_at = :at, commission_cents = :c, confirmation = :n, trip_id = :t WHERE id = :i AND sub_id = :s",
                         at=familydb.now(), c=partner.estimate_cents(offer.price_cents), n=confirmation, t=trip_id, i=click_id, s=sub)
    return get(session, click_id)
