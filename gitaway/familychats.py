"""The trip's chats and what is unread in them (F-143): the Family panel on the laptop lists them, whole trip first, then each plan's and part's.

* A chat is named by a key: "trip" (the whole trip: messages, photos, voice notes and plan-change cards that belong to no plan), "<plan id>" or "<plan id>:<part id>"
  (what was said on a plan or a part: gitaway/plantalk.py).
* Read marks are per person and per chat (the `thread_reads` table): a message is unread when someone else wrote it and it is newer than that chat's mark and than the
  mark "*" (everything read: the phone's Family tab shows all chats at once). Plan-change cards never count. Nothing here sends or changes a plan.
"""

import json

from gitaway import familydb, plantalk, session as ses

TRIP = "trip"
EVERYTHING = "*"
_SAYS = {"photo": "Photo", "voice": "Voice note"}


def key_of(act="", part="") -> str:
    return TRIP if not act else f"{act}:{part}" if part else act


def split(key) -> tuple:
    """(plan id, part id) of a chat key; ("", "") for the whole trip. Anything that is not a plain key is the whole trip."""
    key = key if isinstance(key, str) and len(key) <= 60 else ""
    act, _, part = key.partition(":")
    return ("", "") if not key or key == TRIP or not act.isalnum() or (part and not part.isalnum()) else (act, part)


def _of(payload) -> str:
    try:
        d = json.loads(payload) if payload else {}
    except ValueError:
        d = {}
    d = d if isinstance(d, dict) else {}
    return key_of(d.get("act") or "", d.get("part") or "") if d.get("act") else TRIP


def _read(fam):
    rows = familydb.rows(fam.db, "SELECT rowid AS n, kind, author, author_name, text, payload FROM thread WHERE trip_id = :t AND kind IN ('message', 'photo', 'voice') ORDER BY rowid", t=fam.trip_id)
    marks = {r["key"]: r["last_n"] for r in familydb.rows(fam.db, "SELECT key, last_n FROM thread_reads WHERE user_id = :u", u=fam.traveler.id)}
    return rows, marks


def _unread(rows, marks, me) -> dict:
    out = {}
    everything = marks.get(EVERYTHING, 0)
    for r in rows:
        k = _of(r["payload"])
        if r["author"] != me and r["n"] > max(everything, marks.get(k, 0)):
            out[k] = out.get(k, 0) + 1
    return out


def unread_total(session) -> int:
    """How many messages in the open trip's chats someone else wrote that this person has not read."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return 0
        rows, marks = _read(fam)
        return sum(_unread(rows, marks, fam.traveler.id).values())


def threads(session, open_key="") -> list:
    """The chats of the open trip: the whole trip first, then each plan's and part's that has something said (newest first), and `open_key`'s even when it is empty. Each is
    {"key", "act", "part", "title", "last" (the newest line), "who" (its author's first name), "unread", "n" (how many items), "newest" (its rowid)}."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return []
        rows, marks = _read(fam)
        me = fam.traveler.id
    unread, labels = _unread(rows, marks, me), plantalk.labels(session)
    found = {}
    for r in rows:
        k = _of(r["payload"])
        found[k] = {"last": r["text"] if r["kind"] == "message" else _SAYS.get(r["kind"], ""), "who": "You" if r["author"] == me else r["author_name"], "n": found.get(k, {}).get("n", 0) + 1, "newest": r["n"]}
    want = [TRIP, *sorted((k for k in found if k != TRIP), key=lambda k: -found[k]["newest"])]
    if open_key and open_key not in want:
        want.append(open_key)
    out = []
    for k in want:
        act, part = split(k)
        title = "Whole trip" if k == TRIP else labels.get((act, part))
        if title is None:
            continue
        out.append({"key": k, "act": act, "part": part, "title": title, "unread": unread.get(k, 0), **{"last": "", "who": "", "n": 0, "newest": 0, **found.get(k, {})}})
    return out


def mark_read(session, key, upto) -> None:
    """This person has read the chat `key` up to the item with rowid `upto` (never moves a mark back)."""
    try:
        upto = int(upto)
    except (TypeError, ValueError):
        return
    if upto <= 0 or not (key == EVERYTHING or key == TRIP or split(key) != ("", "")):
        return
    with ses.family(session) as fam:
        if not fam:
            return
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "INSERT INTO thread_reads (pk, user_id, key, last_n) VALUES (:p, :u, :k, :n) ON CONFLICT(pk) DO UPDATE SET last_n = MAX(thread_reads.last_n, :n)",
                         p=f"{fam.traveler.id}|{key}", u=fam.traveler.id, k=key, n=upto)


def newest(session) -> int:
    """The rowid of the newest item of the open trip's thread (0 for none)."""
    with ses.family(session) as fam:
        found = familydb.row(fam.db, "SELECT MAX(rowid) AS n FROM thread WHERE trip_id = :t", t=fam.trip_id) if fam and fam.trip_id else None
    return int(found["n"] or 0) if found else 0
