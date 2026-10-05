"""Talk on the block (F-091): messages, photos and voice notes that belong to a plan, or to one part of a park day (Lunch).

* They are family-thread items (gitaway/familythread.py, the `thread` table), so the Family tab shows them too, labelled with their plan. The
  payload says where they belong: {"act": "<plan id>", "part": "<part id, or empty for the plan as a whole>"}. A voice note is kind "voice"
  with {"file", "mime", "secs"} (the audio is under gitaway/voicenotes.py's folder); a photo is kind "photo" with {"url", "photo"} (the photo
  is also in the family's photos, pinned to the plan: gitaway/photos.py).
* A plan's chat holds what was said on the plan as a whole, and each part's chat only what was said on that part.
* Everyone in the family may post, viewers too (the routes are on gitaway.access.OPEN_POSTS): it changes no plan. The push is the thread's
  (names and plan titles only; the same quiet and two-minute rules).
"""

import json

from gitaway import canvas, familydb, familythread as ft, photos, session as ses, tripcal as cal, voicenotes
from gitaway.familythread import StaleTrip, ThreadError

KINDS = ("message", "photo", "voice")
STALE = "This trip changed. Reload the page."
GONE = "That plan is not here any more."
GONE_PART = "That part of the plan is not here any more."


def url(act, part="", trip=None) -> str:
    """The address of a plan's (or a part's) chat."""
    from urllib.parse import urlencode
    q = {"act": act, **({"part": part} if part else {})}
    if trip:
        q["trip"] = trip
    return "/trip/talk?" + urlencode(q)


def target(session, act, part=""):
    """(activity, part dict or None) of this plan and part in the open trip. Raises ThreadError when either is gone or not this trip's."""
    a = next((x for x in cal.activities(session) if x.id == act), None) if isinstance(act, str) and act else None
    if a is None:
        raise ThreadError(GONE)
    if not part:
        return a, None
    blk = canvas.plan(session)["blocks"].get(act)
    p = next((x for x in blk["parts"] if x["id"] == part), None) if blk else None
    if p is None:
        raise ThreadError(GONE_PART)
    return a, p


def label(a, p=None) -> str:
    """"Lunch · Universal Studios" for a part, the plan's title for the plan."""
    return f"{p['name']} · {a.title}" if p else a.title


def _payload(act, part, **more) -> dict:
    return {"act": act, "part": part or "", **more}


# ---- reading ---------------------------------------------------------------------------------------------------------------

def _talk_rows(session, like):
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return None, []
        found = familydb.rows(fam.db, "SELECT rowid AS n, * FROM thread WHERE trip_id = :t AND kind IN ('message', 'photo', 'voice') AND payload LIKE :p ORDER BY rowid",
                              t=fam.trip_id, p=like)
        return fam, found


def counts(session) -> dict:
    """What has been said on each plan and part of the open trip: {(plan id, part id or ""): {"n": messages, "voice": any voice note, "photo": any photo}}."""
    _, found = _talk_rows(session, '%"act":"%')
    out = {}
    for it in map(ft._item, found):
        act = it["payload"].get("act")
        if not act:
            continue
        c = out.setdefault((act, it["payload"].get("part") or ""), {"n": 0, "voice": False, "photo": False})
        c["n"] += 1
        c["voice"] = c["voice"] or it["kind"] == "voice"
        c["photo"] = c["photo"] or it["kind"] == "photo"
    return out


def labels(session) -> dict:
    """{(plan id, part id or ""): label} for every plan and part of the open trip, for the Family tab's "on <plan>" tags."""
    out = {}
    plan = canvas.plan(session)["blocks"]
    for a in cal.activities(session):
        out[(a.id, "")] = a.title
        for p in (plan.get(a.id) or {}).get("parts", []):
            out[(a.id, p["id"])] = f"{p['name']} · {a.title}"
    return out


def items(session, act, part="", since=0, trip=None) -> list:
    """The chat of a plan (or a part), oldest first, after rowid `since`. Raises StaleTrip when the page was drawn for another trip."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return []
        ft._check(fam, trip)
        found = familydb.rows(fam.db, "SELECT rowid AS n, * FROM thread WHERE trip_id = :t AND rowid > :s AND kind IN ('message', 'photo', 'voice') AND payload LIKE :p ORDER BY rowid",
                              t=fam.trip_id, s=int(since or 0), p=f'%"act":{json.dumps(act)}%')
    its = [ft._item(r) for r in found]
    return [it for it in its if it["payload"].get("act") == act and (it["payload"].get("part") or "") == (part or "")]


def voice_file(session, item_id):
    """(path, mime) of the voice note in the thread item `item_id` of the signed-in person's family, or None. Another family's item is never found."""
    if not isinstance(item_id, str) or not item_id.isalnum() or len(item_id) > 64:
        return None
    with ses.family(session) as fam:
        found = familydb.row(fam.db, "SELECT payload FROM thread WHERE id = :i AND kind = 'voice' AND trip_id IN (SELECT id FROM trips)", i=item_id) if fam else None
    if not found:
        return None
    try:
        payload = json.loads(found["payload"])
    except ValueError:
        return None
    path = voicenotes.path_of(payload.get("file"))
    return (path, payload.get("mime") or "audio/mp4") if path else None


# ---- writing ---------------------------------------------------------------------------------------------------------------

def _post(session, act, part, kind, text, extra, push_what, trip=None, label_=""):
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise StaleTrip(STALE)
        ft._check(fam, trip)
        name, trip_id, me = ft.first_name(fam.traveler), fam.trip_id, fam.traveler.id
        with familydb.transaction(fam.db):
            ft._insert(fam.db, trip_id, kind, me, name, text, _payload(act, part, **extra))
    ft.announce(session, trip_id, name, ft._safe(f"on {label_}: {push_what}"), exclude=me)


def post_message(session, act, part, text, trip=None):
    """A text message on a plan (or a part). Raises ThreadError."""
    text = " ".join((text or "").split())
    if not text:
        raise ThreadError("Write something first.")
    if len(text) > ft.MAX_MESSAGE:
        raise ThreadError(f"Keep messages to {ft.MAX_MESSAGE} characters.")
    a, p = target(session, act, part)
    _post(session, act, part, "message", text, {}, text, trip, label(a, p))


def post_voice(session, act, part, data, secs, trip=None):
    """A voice note on a plan (or a part): checks and stores the audio, then writes the item. Raises ThreadError or voicenotes.VoiceError."""
    a, p = target(session, act, part)
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise StaleTrip(STALE)
        ft._check(fam, trip)
        trip_id = fam.trip_id
    saved = voicenotes.save(session.get("tenant_id"), trip_id, data, secs)
    try:
        _post(session, act, part, "voice", "", {"file": saved["file"], "mime": saved["mime"], "secs": saved["secs"]}, "voice note", trip, label(a, p))
    except Exception:
        voicenotes.remove(saved["file"])
        raise


def post_photo(session, act, part, data, caption="", trip=None):
    """A photo on a plan (or a part): the family's photo store checks and keeps it (pinned to the plan) and the thread item names plan and part.
    Raises ThreadError or photos.PhotoError."""
    a, p = target(session, act, part)
    lab = label(a, p)
    talk = {"act": act, "title": a.title, "extra": _payload(act, part), "push": ft._safe(f"on {lab}: photo")}
    return photos.add(session, data, caption, None, trip, talk=talk)
