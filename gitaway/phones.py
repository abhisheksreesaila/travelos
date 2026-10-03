"""Phone numbers and tonight's hotel (F-069), the model behind the Help tab (gitaway/pages/tab_help.py).

    clean(value)                      (number to keep, "") or ("", message): a phone number typed loosely, or nothing to clear it
    tel(number)                       the `tel:` link target ("+13105550100"), or "" when the text holds no dialable number
    tonight(hotels, today)            the index of the stay that covers tonight in `hotels`, or None when there are none
    member_phones(session)            {user id: number} for the signed-in person's family
    set_member_phone(session, number) keep my own number (any member); raises PhoneError
    set_stay_phone(session, kind, index, number)   fix a hotel's or the rental car's number on the open imported trip; raises PhoneError

Member numbers live in the family database (`members.phone`, migration 003). A hotel's and the car's live in the trip's document
(`trip_imports.doc`), the same place the confirmation numbers are, so Edit trip and Help show one number.
"""

import json
import re
from dataclasses import replace

from gitaway import familydb, session as ses, tripimport

MAX_PHONE = 30
_ALLOWED = re.compile(r"^[0-9 ()+\-.#*,xX]+$")
_EXT = re.compile(r"\s*(?:x|ext\.?|#)\s*\d+\s*$", re.I)


class PhoneError(ValueError):
    """A number the app refuses; the message is fit to show."""


def clean(value) -> tuple:
    """(number, message). Loose on purpose: digits with spaces, dashes, dots, brackets, a leading + and an extension. Empty clears it."""
    v = value.strip() if isinstance(value, str) else ""
    if not v:
        return "", ""
    if len(v) > MAX_PHONE:
        return "", f"That number is longer than {MAX_PHONE} characters."
    if not _ALLOWED.match(v) or sum(c.isdigit() for c in v) < 7:
        return "", "Enter a phone number like +1 310 555 0100."
    return v, ""


def tel(number) -> str:
    """The number to dial: digits, a leading + kept, any extension left off. '' when fewer than 7 digits are there."""
    v = _EXT.sub("", (number or "").strip())
    digits = re.sub(r"\D", "", v)
    if len(digits) < 7:
        return ""
    return ("+" if v.startswith("+") else "") + digits


def tonight(hotels, today):
    """Index of the stay that covers tonight (check in on or before today, check out after it); with none, the next stay still to come, else the last."""
    if not hotels:
        return None
    for i, h in enumerate(hotels):
        if h.check_in.date() <= today < h.check_out.date():
            return i
    for i, h in enumerate(hotels):
        if h.check_in.date() > today:
            return i
    return len(hotels) - 1


# ---- the family's own numbers --------------------------------------------------------------------------------------

def member_phones(session) -> dict:
    with ses.family(session) as fam:
        if not fam:
            return {}
        return {r["id"]: r["phone"] for r in familydb.rows(fam.db, "SELECT id, phone FROM members WHERE phone != ''")}


def set_member_phone(session, number):
    keep, message = clean(number)
    if message:
        raise PhoneError(message)
    with ses.family(session) as fam:
        if not fam:
            raise PhoneError("Sign in to add your number.")
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "UPDATE members SET phone = :p WHERE id = :u", p=keep, u=fam.traveler.id)


# ---- a hotel's or the car's number ---------------------------------------------------------------------------------

def set_stay_phone(session, kind, index, number):
    """Set the number of hotel `index` or of the rental car on the imported trip this person has open. Only that one number changes."""
    keep, message = clean(number)
    if message:
        raise PhoneError(message)
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise PhoneError("Open a trip first.")
        db = fam.db
        with familydb.transaction(db):
            familydb.lock(db)
            old = familydb.row(db, "SELECT i.doc FROM trips t JOIN trip_imports i ON i.trip_id = t.id WHERE t.id = :t AND t.source = 'imported'", t=fam.trip_id)
            if not old:
                raise PhoneError("Only a trip you imported or built has numbers to fix.")
            plan = tripimport.from_doc(json.loads(old["doc"]))
            if kind == "hotel" and str(index).isdigit() and int(index) < len(plan.hotels):
                hotels = list(plan.hotels)
                hotels[int(index)] = replace(hotels[int(index)], phone=keep)
                plan = replace(plan, hotels=tuple(hotels))
            elif kind == "car" and plan.rental:
                plan = replace(plan, rental=replace(plan.rental, phone=keep))
            else:
                raise PhoneError("That booking is not on this trip.")
            familydb.run(db, "UPDATE trip_imports SET doc = :doc WHERE trip_id = :t", doc=json.dumps(tripimport.to_doc(plan), separators=(",", ":")), t=fam.trip_id)
