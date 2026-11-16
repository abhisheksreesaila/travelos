"""Talk on a plan (F-091; photos and voice notes retired in F-254): text messages that belong to a plan, or to one part of a park day (Lunch).

* They are family-thread items (gitaway/familythread.py, the `thread` table), labelled with their plan. The payload says where they belong: {"act": "<plan id>", "part": "<part id, or empty for the plan
  as a whole>"}. Photo and voice items written before F-254 are still read and shown by the thread; nothing writes new ones.
* A plan's chat holds what was said on the plan as a whole, and each part's chat only what was said on that part.
* Everyone in the family may post, viewers too (POST /trip/talk/message, gitaway/pages/chatwrites.py, is on gitaway.access.OPEN_POSTS): it changes no plan. The push is the thread's (names and plan
  titles only; the same quiet and two-minute rules).
"""

import json

from gitaway import canvas, familydb, familythread as ft, session as ses, tripcal as cal
from gitaway.familythread import StaleTrip, ThreadError

STALE = "This trip changed. Reload the page."
GONE = "That plan is not here any more."
GONE_PART = "That part of the plan is not here any more."


def url(act, part="", trip=None) -> str:
    """The address of a plan's (or a part's) chat."""
    from urllib.parse import urlencode
    q = {"act": act, **({"part": part} if part else {})}
    if trip:
        q["trip"] = trip
    return "/trip/plan"      # F-254: the chat opens from the plan's own drawer ("Talk about this")


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

def labels(session, acts=None) -> dict:
    """{(plan id, part id or ""): label} for every plan and part of the open trip, for the Family tab's "on <plan>" tags. `acts`: the trip's plans, when the caller has read them."""
    out = {}
    plan = canvas.plan(session)["blocks"]
    for a in acts if acts is not None else cal.activities(session):
        out[(a.id, "")] = a.title
        for p in (plan.get(a.id) or {}).get("parts", []):
            out[(a.id, p["id"])] = f"{p['name']} · {a.title}"
    return out


def items(session, act, part="", since=0, trip=None, before=0, limit=0) -> list:
    """The chat of a plan (or a part), oldest first, after rowid `since` and before `before` (0: no end); `limit` keeps only the newest that many (0: all). Raises StaleTrip when the page was drawn for another trip."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return []
        ft._check(fam, trip)
        found = familydb.rows(fam.db, "SELECT rowid AS n, * FROM thread WHERE trip_id = :t AND rowid > :s AND kind IN ('message', 'photo', 'voice') AND (:b = 0 OR rowid < :b) AND payload LIKE :p ORDER BY rowid",
                              t=fam.trip_id, s=int(since or 0), b=int(before or 0), p=f'%"act":{json.dumps(act)}%')
    its = [ft._item(r) for r in found]
    its = [it for it in its if it["payload"].get("act") == act and (it["payload"].get("part") or "") == (part or "")]
    return its[-limit:] if limit else its


# ---- writing ---------------------------------------------------------------------------------------------------------------

def _post(session, act, part, kind, text, extra, push_what, trip=None, label_="", cid=""):
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise StaleTrip(STALE)
        ft._check(fam, trip)
        name, trip_id, me = ft.first_name(fam.traveler), fam.trip_id, fam.traveler.id
        with familydb.transaction(fam.db):
            added = ft._insert(fam.db, trip_id, kind, me, name, text, _payload(act, part, **extra), cid=cid)
    if added:
        ft.announce(session, trip_id, name, ft._safe(f"on {label_}: {push_what}"), exclude=me)


def post_message(session, act, part, text, trip=None, cid=""):
    """A text message on a plan (or a part). Raises ThreadError."""
    text = " ".join((text or "").split())
    if not text:
        raise ThreadError("Write something first.")
    if len(text) > ft.MAX_MESSAGE:
        raise ThreadError(f"Keep messages to {ft.MAX_MESSAGE} characters.")
    a, p = target(session, act, part)
    _post(session, act, part, "message", text, {}, text, trip, label(a, p), cid=cid)

