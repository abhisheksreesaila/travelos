"""Changing a plan with a finger (F-097, F-098): move it, change its length, rename it, delete it, and take each of those back.

    change(session, act_id, start=, end=, title=, day=)   one edit of a plan; -> {"act", "undo", "changed"}; CalendarError says why not
    restore(session, snapshot)                          Undo: put a plan back as `change` recorded it in "undo", through the same rules
    delete(session, act_id) / undelete(session, act_id)  remove a plan (its parts and steps wait for the Undo) and put it back

Every edit goes through the calendar's own rules (`tripcal.update_in`, `delete_in`, `undo_delete`): the plan must be live, the title 1 to 40 characters, the
time inside the day's grid and the end after the start; overlapping other plans or bookings is allowed (F-086). The touch grid's grain is finer than the forms':
times snap to 5 minutes and a plan may be 15 minutes long (`fine`). Booked blocks are not plans and are refused. Writes are one short transaction on the
plan's own row. The family is told once: a move, then a nudge or two more of the same plan by the same person inside `canvas.CARD_WINDOW`, are one card,
changed in place (no second push), and an Undo that brings the plan back to where it began takes the card away.
"""

import json
from datetime import datetime, timezone

from gitaway import canvas, familydb, familythread, session as ses, tripcal as cal


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _payload(card):
    try:
        return json.loads(card["payload"] or "{}")
    except ValueError:
        return {}


def _last_card(fam, key):
    """The family thread's newest card when it is this person's own card for plan `key` (see `_tell`) and still inside the window, else None."""
    last = familydb.row(fam.db, "SELECT rowid AS n, * FROM thread WHERE trip_id = :t ORDER BY rowid DESC LIMIT 1", t=fam.trip_id)
    if not last or last["kind"] != "change" or last["author"] != fam.traveler.id:
        return None
    payload = _payload(last)
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(last["created_at"])).total_seconds()
    return last if payload.get("key") == key and age <= canvas.CARD_WINDOW and isinstance(payload.get("orig"), list) else None


def _tell(session, fam, t, act_id, was, now):
    """The family's card for this plan's change, coalesced. `was` and `now` are (day, start, end, title)."""
    key = f"plan:{act_id}"
    who = familythread.first_name(fam.traveler)
    card, orig = _last_card(fam, key), list(was)
    adding = bool(card) and _payload(card).get("action") == "add"
    if card:
        orig = _payload(card)["orig"]
    if adding:
        # F-101: a plan just made, then moved, resized or renamed inside the window: the one card keeps saying it was added, with the plan as it now is.
        text = f"{who} added {now[3]} on {cal._when(t, now[0], now[1])}"
        payload = json.dumps({"action": "add", "key": key, "orig": orig}, separators=(",", ":"))
        familydb.run(fam.db, "UPDATE thread SET text = :x, payload = :p WHERE rowid = :n", x=text, p=payload, n=card["n"])
        return
    if tuple(orig) == tuple(now):
        if card:
            familydb.run(fam.db, "DELETE FROM thread WHERE rowid = :n", n=card["n"])      # back where it began: nothing happened
        return
    text = cal.update_card(who, t, tuple(orig), *now)
    if not text:
        return
    payload = json.dumps({"action": text[1], "key": key, "orig": orig}, separators=(",", ":"))
    if card:
        familydb.run(fam.db, "UPDATE thread SET text = :x, payload = :p WHERE rowid = :n", x=text[0], p=payload, n=card["n"])
        return
    familythread.change(session, fam, text[0], action=text[1])
    made = familydb.row(fam.db, "SELECT rowid AS n FROM thread WHERE trip_id = :t ORDER BY rowid DESC LIMIT 1", t=fam.trip_id)
    familydb.run(fam.db, "UPDATE thread SET payload = :p WHERE rowid = :n", p=payload, n=made["n"])


def add(session, *, day, start, end, title):
    """Make a plan (F-101: the touch grid's hold on empty time), through the calendar's own add rules with the grid's grain. The family is told once, and the card
    is tagged like `change`'s so a move, resize or rename of the new plan right after (inside `canvas.CARD_WINDOW`) changes that card and sends nothing more.
    -> {"act": the plan, "undo": {"added": its id}}"""
    a = cal.add_activity(session, day=day, start=start, end=end, title=title, kind="fun", fine=True)
    if a is None:
        raise cal.CalendarError("That did not work.")
    with ses.family(session) as fam, familydb.transaction(fam.db):
        last = familydb.row(fam.db, "SELECT rowid AS n, * FROM thread WHERE trip_id = :t ORDER BY rowid DESC LIMIT 1", t=fam.trip_id)
        if last and last["kind"] == "change" and last["author"] == fam.traveler.id and f" added {a.title} on " in last["text"]:
            payload = json.dumps({"action": "add", "key": f"plan:{a.id}", "orig": [a.day, a.start, a.end, a.title]}, separators=(",", ":"))
            familydb.run(fam.db, "UPDATE thread SET payload = :p WHERE rowid = :n", p=payload, n=last["n"])
    return {"act": a, "undo": {"added": a.id}}


def unadd(session, snapshot):
    """Undo of `add`: the plan goes (its parts and steps too, as for a delete). While the family's card for it is still the newest, it goes too, as if nothing happened;
    after other news, they are told it was removed."""
    act = snapshot.get("added") if isinstance(snapshot, dict) else None
    if not isinstance(act, str) or act.startswith("b-") or not act:
        raise cal.CalendarError("There is nothing to undo.")
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise cal.CalendarError("There is nothing to undo.")
        with familydb.transaction(fam.db):
            card = _last_card(fam, f"plan:{act}")
            gone = cal.delete_in(session, fam, act[:20], say=not card)
            if gone is None:
                raise cal.CalendarError("That plan is gone.")
            if card:
                familydb.run(fam.db, "DELETE FROM thread WHERE rowid = :n", n=card["n"])
    return gone


def change(session, act_id, *, start=None, end=None, title=None, day=None, expect=None):
    """Edit one plan: any of its start, end, title or day. -> {"act": the plan now, "undo": the snapshot `restore` takes, "changed": whether anything differs}."""
    if not isinstance(act_id, str) or act_id.startswith("b-"):
        raise cal.CalendarError("Booked items are locked. Change your booking to move them.")
    with ses.family(session) as fam:
        b, t, blocks = cal._need(fam, "")
        blocks = blocks + cal.ride_blocks(session, b, t)
        db = fam.db
        with familydb.transaction(db):
            cal._begin(db, fam.trip_id, "", fam.traveler.id)
            row = familydb.row(db, "SELECT * FROM activities WHERE trip_id = :t AND scope = '' AND act_id = :i AND gone = 0", t=fam.trip_id, i=act_id)
            if row is None:
                raise cal.CalendarError("That plan is gone.")
            was = (row["day"], row["start_min"], row["end_min"], row["title"])
            if expect is not None and tuple(expect) != was:
                raise cal.CalendarError("Someone changed it since. Nothing was undone.")      # an Undo must not overwrite another member's later change
            a =cal.update_in(session, fam, t, blocks, act_id, day=day, start=start, end=end, title=title, scope="", say=False, fine=True)
            now = (a.day, a.start, a.end, a.title)
            _tell(session, fam, t, act_id, was, now)
    return {"act": a, "changed": was != now, "undo": {"act": act_id, "day": was[0], "start": was[1], "end": was[2], "title": was[3],
                                                      "after": {"day": now[0], "start": now[1], "end": now[2], "title": now[3]}}}


def restore(session, snapshot):
    """Undo: put a plan back as the snapshot `change` gave says. The snapshot comes from the page, so every field is checked."""
    s = snapshot if isinstance(snapshot, dict) else {}
    after = s.get("after") if isinstance(s.get("after"), dict) else {}
    if not (isinstance(s.get("act"), str) and _int(s.get("day")) and _int(s.get("start")) and _int(s.get("end")) and isinstance(s.get("title"), str)
            and _int(after.get("day")) and _int(after.get("start")) and _int(after.get("end")) and isinstance(after.get("title"), str)):
        raise cal.CalendarError("There is nothing to undo.")
    return change(session, s["act"][:20], day=s["day"], start=s["start"], end=s["end"], title=s["title"],
                  expect=(after["day"], after["start"], after["end"], after["title"]))["act"]


def delete(session, act_id):
    """Delete a plan, keeping it for one Undo. -> {"title", "steps": how many steps went with it}."""
    if not isinstance(act_id, str) or act_id.startswith("b-"):
        raise cal.CalendarError("Booked items are locked. Change your booking to move them.")
    with ses.family(session) as fam:
        steps = familydb.row(fam.db, "SELECT COUNT(*) AS n FROM block_steps WHERE trip_id = :t AND act_id = :a", t=fam.trip_id, a=act_id)["n"] if fam and fam.trip_id else 0
    gone = cal.delete_activity(session, act_id)
    if gone is None:
        raise cal.CalendarError("That plan is gone.")
    return {"title": gone.title, "steps": steps}


def undelete(session, act_id):
    """Put the plan last deleted back."""
    back = cal.undo_delete(session, act_id) if isinstance(act_id, str) else None
    if back is None:
        raise cal.CalendarError("There is nothing to undo.")
    return back
