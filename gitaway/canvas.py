"""Paste & Convert and the plan steps inside a calendar block (F-080).

    convert(session, text)                 pasted messages -> a draft (the model reads them; nothing is saved)
    clean(raw)                             any draft, from the model or from a form -> a validated, size-capped draft (idempotent)
    summary(draft)                         the counts step 1 shows
    questions(draft, people, text)         who each initial or name is (suggestions from the family) and which tokens need no question
    save(session, draft, answers)          write the park days, parts, steps, set-aside steps and lists, one thread card, one notify
    block(session, act_id), block_ids(session), set_done(...), set_aside(...)   reading and ticking what was saved
    move_step(...), restore(...), add_step(...), set_note(...), same_step(...), list_hits(...)   moving, adding and annotating steps by touch (F-082)

A draft is: days[{label, place, date, parts[{name, time_of_day, steps[{title, time, who_raw[], note, kind}]}]}], set_aside[{title, reason, day}],
lists[{name, items[{title, note}]}], initials[], notes_kept[], merged_repeats. The model answers to SCHEMA (a strict JSON schema); `clean` then
checks every field and caps every size, so neither a confused model nor a doctored form can store more than the limits below.

Nothing is saved until `save`. The draft travels between the steps in the page's own form (a hidden field), never in the cookie or the database.
A converted park day becomes ONE calendar activity (9:00 AM to 9:00 PM) on the day the family picks, through the calendar's own validation
(gitaway.tripcal), so the calendar and Today show it. The model is reached only through gitaway.ai (job "convert"), which logs the call without its content.
"""

import json
import re
import uuid
from datetime import datetime, timezone

from fh_saas.utils_sql import insert_only

from gitaway import ai, familydb, familythread, members, session as ses, tripcal as cal

MAX_TEXT = 20000
MAX_DAYS, MAX_PARTS, MAX_STEPS, MAX_ASIDE, MAX_LISTS, MAX_ITEMS, MAX_INITIALS, MAX_WHO = 6, 12, 40, 30, 6, 40, 14, 6
MAX_STEP_PER_TRIP = 1500
DAY_START, DAY_END = 9 * 60, 21 * 60
KINDS = ("ride", "show", "meal", "meet", "other")
GROUPS = {"adults": "Adults", "kids": "Kids", "children": "Kids", "grown-ups": "Adults", "grownups": "Adults"}
EVERYONE = {"everyone", "all", "we", "us", "family", "everybody"}
_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")
_SPLIT = re.compile(r"\s*(?:&|/|\+|,|;|\band\b)\s*", re.I)


class CanvasError(ValueError):
    """A change the canvas refuses; the text is fit to show."""


# ---- what the model is asked ---------------------------------------------------------------------------------------------

def _obj(props, required=None):
    return {"type": "object", "additionalProperties": False, "required": required or list(props), "properties": props}


def _text(null=False):
    return {"type": ["string", "null"] if null else "string"}


SCHEMA = _obj({
    "days": {"type": "array", "items": _obj({
        "label": _text(), "park_or_place": _text(), "date": _text(True),
        "parts": {"type": "array", "items": _obj({
            "name": _text(), "time_of_day": _text(True),
            "steps": {"type": "array", "items": _obj({
                "title": _text(), "time": _text(True), "who_raw": {"type": "array", "items": _text()}, "note": _text(True),
                "kind": {"type": "string", "enum": list(KINDS)}})}})}})},
    "set_aside": {"type": "array", "items": _obj({"title": _text(), "reason": _text(), "day": {"type": ["integer", "null"]}})},
    "lists": {"type": "array", "items": _obj({"name": _text(), "items": {"type": "array", "items": _obj({"title": _text(), "note": _text(True)})}})},
    "initials_found": {"type": "array", "items": _text()},
    "notes_kept": {"type": "array", "items": _text()},
    "merged_repeats": {"type": "integer"}})

SYSTEM = """You turn a family's pasted text messages about their trip into a structured plan. Answer with JSON that matches the schema and nothing else.

Rules:
- One entry in days for each park or place (the text may mix two parks in one stream with no dates; start a new day when the park changes). label is the heading the family used; park_or_place is the park's proper name.
- date is the day's date as YYYY-MM-DD when the text says which day it is (a date or a weekday, using the trip days given at the top), else null. Never guess a date.
- Inside a day, parts are the areas or stretches in the order written (for example Lower Lot, Lunch, Upper Lot). A part for a meal may have no steps. time_of_day is Morning, Afternoon, Evening or a time the text gives, else null.
- Times the text gives (for example "Mario Kart at 10:30" or "lunch 12") go in the step's time as 24-hour HH:MM, exactly as written; a part's time_of_day may be a time too. Never invent a time.
- Each ride, show, meal or meet-up is a step. Keep the family's own words. Normalise ride names lightly (for example "Fast and furious" becomes "Fast & Furious - Supercharged") only when you are confident which ride it is; when you change a name, say what the family wrote in the note. Never invent a ride or a time that is not in the text.
- Words in brackets and comments after a ride ("roughest ride", "main!!!", "lamp side", "H and B walk") are the step's note; keep the wording.
- People appear as initials or names (H, B, R&A, Sam). Put them in who_raw of the steps they belong to, exactly as written, one entry per person (split "R&A" into "R" and "A"). Never guess who they are. List every one in initials_found.
- "Skip X" or "skip the X" means X is set aside: put it in set_aside with a short reason, not in a day. Set day to the index (0 is the first day in days) it belongs to.
- A list the family names (for example "Pregnancy safe rides") goes in lists, not in a day. Keep notes in brackets.
- If the same list or day was sent twice, keep it once and count how many repeats you merged in merged_repeats.
- notes_kept holds the short notes you kept from the text, in the family's words.
- kind is ride, show, meal, meet or other."""


# ---- cleaning a draft ----------------------------------------------------------------------------------------------------

def _s(value, cap) -> str:
    return " ".join(str(value or "").split())[:cap].strip()


def _clock(value) -> str:
    m = _TIME.match(str(value or "").strip())
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m and int(m.group(1)) < 24 and int(m.group(2)) < 60 else ""


def _who_tokens(raw) -> list:
    """The people a step names: initials and names split apart ("R&A" -> R, A), "everyone" dropped, groups (adults, kids) kept as groups ("g:Adults")."""
    out = []
    for item in (raw if isinstance(raw, list) else [])[:MAX_WHO]:
        for part in _SPLIT.split(_s(item, 40)):
            part = part.strip(" ().")
            low = part.casefold()
            if not part or low in EVERYONE:
                continue
            token = f"g:{GROUPS[low]}" if low in GROUPS else part
            if token not in out:
                out.append(token)
    return out[:MAX_WHO]


def _iso(value) -> str:
    """A YYYY-MM-DD date or ""."""
    try:
        return datetime.strptime(_s(value, 10), "%Y-%m-%d").date().isoformat()
    except ValueError:
        return ""


def _list(value):
    return value if isinstance(value, list) else []


def clean(raw) -> dict:
    """A validated draft from whatever the model (or a form) gave. Never raises for odd content: it keeps what is usable and drops the rest."""
    raw = raw if isinstance(raw, dict) else {}
    removed, days = 0, []
    for d in _list(raw.get("days"))[:MAX_DAYS]:
        d = d if isinstance(d, dict) else {}
        seen, parts = set(), []
        for p in _list(d.get("parts"))[:MAX_PARTS]:
            p = p if isinstance(p, dict) else {}
            steps = []
            for s in _list(p.get("steps"))[:MAX_STEPS]:
                s = s if isinstance(s, dict) else {}
                title = _s(s.get("title"), 80)
                if not title:
                    continue
                if title.casefold() in seen:   # a ride sent twice in one day is one step
                    removed += 1
                    continue
                seen.add(title.casefold())
                kind = s.get("kind") if s.get("kind") in KINDS else "other"
                steps.append({"title": title, "time": _clock(s.get("time")), "who_raw": _who_tokens(s.get("who_raw")), "note": _s(s.get("note"), 200), "kind": kind})
            name = _s(p.get("name"), 60)
            if name or steps:
                parts.append({"name": name or "Plan", "time_of_day": _s(p.get("time_of_day"), 30), "steps": steps})
        place = _s(d.get("park_or_place") or d.get("place"), cal.MAX_TITLE) or _s(d.get("label"), cal.MAX_TITLE)
        if place and parts:
            days.append({"label": _s(d.get("label"), 60), "place": place, "date": _iso(d.get("date")), "parts": parts})
    aside = []
    for a in _list(raw.get("set_aside"))[:MAX_ASIDE]:
        a = a if isinstance(a, dict) else {}
        title = _s(a.get("title"), 80)
        day = a.get("day") if isinstance(a.get("day"), int) and not isinstance(a.get("day"), bool) and 0 <= a.get("day") < len(days) else 0
        if title and days:
            aside.append({"title": title, "reason": _s(a.get("reason"), 140), "day": day})
    lists = []
    for lst in _list(raw.get("lists"))[:MAX_LISTS]:
        lst = lst if isinstance(lst, dict) else {}
        items, seen = [], set()
        for it in _list(lst.get("items"))[:MAX_ITEMS]:
            it = it if isinstance(it, dict) else {}
            title = _s(it.get("title"), 80)
            if title and title.casefold() not in seen:
                seen.add(title.casefold())
                items.append({"title": title, "note": _s(it.get("note"), 200)})
        name = _s(lst.get("name"), 60)
        if name and items:
            lists.append({"name": name, "items": items})
    initials = []
    for token in [*(t for d in days for p in d["parts"] for s in p["steps"] for t in s["who_raw"]), *(t for i in _list(raw.get("initials")) + _list(raw.get("initials_found")) for t in _who_tokens([i]))]:
        if not token.startswith("g:") and token.casefold() not in {x.casefold() for x in initials} and len(initials) < MAX_INITIALS:
            initials.append(token)
    notes = [n for n in (_s(x, 80) for x in _list(raw.get("notes_kept"))[:20]) if n]
    merged = raw.get("merged_repeats")
    return {"days": days, "set_aside": aside, "lists": lists, "initials": initials, "notes_kept": notes,
            "merged_repeats": (merged if isinstance(merged, int) and not isinstance(merged, bool) and 0 <= merged <= 50 else 0) + removed}


def summary(draft) -> dict:
    """The counts step 1 shows: park days, areas (parts with something in them), rides and shows (steps)."""
    days = draft["days"]
    return {"days": len(days), "areas": sum(1 for d in days for p in d["parts"] if p["steps"]), "steps": sum(len(p["steps"]) for d in days for p in d["parts"]),
            "set_aside": len(draft["set_aside"]), "lists": len(draft["lists"]), "list_items": sum(len(x["items"]) for x in draft["lists"])}


def empty(draft) -> bool:
    return not draft["days"] and not draft["lists"]


# ---- converting ----------------------------------------------------------------------------------------------------------

def convert(session, text, trip_days=None) -> dict:
    """Read pasted messages with the model and return the cleaned draft. Raises CanvasError (nothing pasted, too long, nothing found) or ai.AIError
    (the model is off, slow or failed; its text is fit to show). Nothing is saved. `trip_days` (["2026-10-16 Friday", ...]) is shown to the model above the
    text so it can say which date a day is."""
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        raise CanvasError("Paste the messages first.")
    if len(text) > MAX_TEXT:
        raise CanvasError(f"That is a lot of text. Paste up to {MAX_TEXT:,} characters at a time.")
    shown = f"Trip days: {', '.join(trip_days)}\n\nMessages:\n{text}" if trip_days else text
    draft = clean(ai.call_json("convert", (session or {}).get("tenant_id", ""), SYSTEM, shown, SCHEMA, name="trip_plan"))
    if empty(draft):
        raise CanvasError("We could not find a park day or a list in that text. Check it, or add more of the messages.")
    return draft


# ---- who is who ----------------------------------------------------------------------------------------------------------

def _first(name) -> str:
    words = (name or "").split()
    return words[0] if words else ""


def exact_member(token, people):
    """The one family member whose first or full name is `token` (any capitals), else None."""
    low = token.casefold()
    found = [p for p in people if low in (_first(p["name"]).casefold(), p["name"].casefold())]
    return found[0] if len(found) == 1 else None


def suggest(token, people, text="") -> dict:
    """{"member": id or None, "why": sentence}. A name that is a member's wins; a single letter matching exactly one member's first letter is suggested.
    Anything else is left to the person: Convert never guesses a person."""
    if (m := exact_member(token, people)):
        return {"member": m["user_id"], "why": "that is their name"}
    letters = re.sub(r"[^A-Za-z]", "", token)
    if len(letters) == 1:
        same = [p for p in people if _first(p["name"])[:1].casefold() == letters.casefold()]
        if len(same) == 1:
            m = same[0]
            named = re.search(rf"\b{re.escape(_first(m['name']))}\b", text or "", re.I)
            return {"member": m["user_id"], "why": f"you wrote \"{_first(m['name'])}\"" if named else f"the only {letters.upper()} in the family"}
    return {"member": None, "why": ""}


def questions(draft, people, text="") -> dict:
    """What step 2 asks: `who` the initials that need an answer (each with its suggestion), and `named` the tokens that are a member's exact name
    (no question: they are matched when saving)."""
    who, named = [], {}
    for token in draft["initials"]:
        if (m := exact_member(token, people)):
            named[token] = m["user_id"]
        else:
            who.append({"token": token, **suggest(token, people, text)})
    return {"who": who, "named": named}


def family_people(session) -> list:
    """The family's members as dicts (user_id, name, initials, color), oldest first."""
    tid = (session or {}).get("tenant_id")
    uid = (session or {}).get("user_id")
    if not tid or not uid or not members.role_in(uid, tid):
        return []
    return [{"user_id": m["user_id"], "name": m["name"], "initials": m["initials"], "color": m["color"]} for m in members.members(tid)]


# ---- saving --------------------------------------------------------------------------------------------------------------

def _resolve(token, who, people_ids, named) -> str:
    """The stored form of one person: "m:<id>", "n:<Name>", "i:<R>" (initials kept) or "g:<group>"."""
    if token.startswith("g:"):
        return token
    choice = who.get(token) or (f"m:{named[token]}" if token in named else f"i:{token}")
    if choice.startswith("m:"):
        if choice[2:] not in people_ids:
            raise CanvasError("Pick one of the people in your family.")
        return choice
    if choice.startswith("n:"):
        return "n:" + (_s(choice[2:], 30) or token)
    return f"i:{token}"


def _first_name(person_id, people) -> str:
    return next((_first(p["name"]) for p in people if p["user_id"] == person_id), "")


def save(session, draft, answers) -> dict:
    """Write the draft. `answers`: {"who": {token: "m:<id>" | "n:<Name>" | "i:<token>"}, "days": [trip day index for each draft day],
    "list_for": [ "m:<id>" | "n:<Name>" | "" for each list ]}. One transaction: park days (calendar activities), parts, steps, set-aside steps, lists, the
    one thread card, and the family's push. Raises CanvasError and then saves nothing. Returns {"acts": [(act id, title, day)], "steps": n, "lists": n}."""
    draft = clean(draft)
    if empty(draft):
        raise CanvasError("There is nothing to add.")
    who = answers.get("who") or {}
    picked = answers.get("days") or []
    list_for = answers.get("list_for") or []
    if len(picked) < len(draft["days"]) or any(not isinstance(d, int) for d in picked):
        raise CanvasError("Pick a day for each park.")
    if len(set(picked[: len(draft["days"])])) != len(draft["days"]):
        raise CanvasError("Pick a different day for each park.")
    people = family_people(session)
    ids = {p["user_id"] for p in people}
    named = questions(draft, people)["named"]
    with ses.family(session) as fam:
        if fam is None or not fam.trip_id:
            raise CanvasError("Open a trip first.")
        try:
            b, t, blocks = cal._need(fam, "")
            blocks = blocks + cal.ride_blocks(session, b, t)
        except cal.CalendarError as e:
            raise CanvasError(str(e))
        db = fam.db
        for_who = []
        for i, lst in enumerate(draft["lists"]):
            choice = list_for[i] if i < len(list_for) else ""
            if choice.startswith("m:") and choice[2:] not in ids:
                raise CanvasError("Pick one of the people in your family.")
            for_who.append(choice if choice.startswith("m:") else f"n:{_s(choice[2:], 30)}" if choice.startswith("n:") and _s(choice[2:], 30) else "")
        resolved = {tok: _resolve(tok, who, ids, named) for tok in draft["initials"]}
        made, steps_made = [], 0
        try:
            with familydb.transaction(db):
                st = cal._begin(db, fam.trip_id, "", fam.traveler.id)
                have = familydb.row(db, "SELECT COUNT(*) AS n FROM block_steps WHERE trip_id = :t", t=fam.trip_id)["n"]
                if have + sum(len(p["steps"]) for d in draft["days"] for p in d["parts"]) + len(draft["set_aside"]) > MAX_STEP_PER_TRIP:
                    raise CanvasError(cal.FULL)
                q = st["q"]
                for i, d in enumerate(draft["days"]):
                    day, start, end, title = cal._clean(t, blocks, day=picked[i], start=DAY_START, end=DAY_END, title=d["place"], kind="fun")
                    twin = familydb.row(db, "SELECT act_id FROM activities WHERE trip_id = :t AND scope = '' AND gone = 0 AND day = :d AND title = :n", t=fam.trip_id, d=day, n=title)
                    old_parts = _stored_parts(db, fam.trip_id, twin["act_id"]) if twin else []
                    if old_parts:       # the park is already planned that day: its parts and steps are added to, nothing is duplicated
                        when = cal._when(t, day, start).split(" ")[0]
                        plan_in = merge_plan(old_parts, d["parts"])
                        if not plan_in:
                            raise CanvasError(f"{title} is already planned on {when} with all of this. Pick another day, or open it and change it there.")
                        if len(old_parts) + sum(1 for m in plan_in if m["into"] is None) > MAX_PARTS:
                            raise CanvasError(f"{title} on {when} would have more than {MAX_PARTS} parts. Open it and change it there.")
                        made.append((twin["act_id"], title, day))
                        pos = len(old_parts)
                        for m in plan_in:
                            if m["into"] is None:
                                part, first = uuid.uuid4().hex, 0
                                _put(db, "block_parts", {"id": part, "trip_id": fam.trip_id, "act_id": twin["act_id"], "position": pos, "name": m["part"]["name"], "time_of_day": m["part"]["time_of_day"]})
                                pos += 1
                            else:
                                part, first = old_parts[m["into"]]["id"], old_parts[m["into"]]["n"]
                            for n, s in enumerate(m["steps"]):
                                _step(db, fam.trip_id, twin["act_id"], part, first + n, s["title"], s["time"], [resolved[x] if not x.startswith("g:") else x for x in s["who_raw"]], s["note"], s["kind"], 0)
                                steps_made += 1
                        continue
                    if len(cal._live_acts(db, fam.trip_id, "")) + len(made) >= cal.MAX_ACTIVITIES:
                        raise CanvasError(cal.FULL)
                    q += 1
                    act = f"a{q}"
                    cal._insert_activity(db, fam, "", act, q, day, start, end, title, "fun")
                    made.append((act, title, day))
                    for pos, p in enumerate(d["parts"]):
                        part = uuid.uuid4().hex
                        _put(db, "block_parts", {"id": part, "trip_id": fam.trip_id, "act_id": act, "position": pos, "name": p["name"], "time_of_day": p["time_of_day"]})
                        for n, s in enumerate(p["steps"]):
                            _step(db, fam.trip_id, act, part, n, s["title"], s["time"], [resolved[x] if not x.startswith("g:") else x for x in s["who_raw"]], s["note"], s["kind"], 0)
                            steps_made += 1
                for n, a in enumerate(draft["set_aside"]):
                    _step(db, fam.trip_id, made[a["day"]][0], "", n, a["title"], "", [], a["reason"], "other", 1)
                cal._bump(db, fam.trip_id, "", q)
                base = familydb.row(db, "SELECT COALESCE(MAX(position), -1) + 1 AS n FROM trip_lists WHERE trip_id = :t", t=fam.trip_id)["n"]
                for k, lst in enumerate(draft["lists"]):
                    lid = uuid.uuid4().hex
                    _put(db, "trip_lists", {"id": lid, "trip_id": fam.trip_id, "name": lst["name"], "for_who": for_who[k], "position": base + k})
                    for n, it in enumerate(lst["items"]):
                        _put(db, "trip_list_items", {"id": uuid.uuid4().hex, "list_id": lid, "trip_id": fam.trip_id, "title": it["title"], "note": it["note"], "position": n})
                familythread.change(session, fam, _card(familythread.first_name(fam.traveler), t, made, steps_made, draft["lists"]), action="add")
        except cal.CalendarError as e:
            raise CanvasError(str(e))
    return {"acts": made, "steps": steps_made, "lists": len(draft["lists"])}


def _stored_parts(db, trip_id, act) -> list:
    """The parts a block already has, in order: [{"id", "name", "n": steps in the part, "titles": every step title in the block}]."""
    parts = familydb.rows(db, "SELECT id, name FROM block_parts WHERE trip_id = :t AND act_id = :a ORDER BY position, rowid", t=trip_id, a=act)
    steps = familydb.rows(db, "SELECT part_id, title FROM block_steps WHERE trip_id = :t AND act_id = :a AND aside = 0", t=trip_id, a=act)
    titles = [x["title"] for x in steps]
    return [{"id": p["id"], "name": p["name"], "n": sum(1 for x in steps if x["part_id"] == p["id"]), "titles": titles} for p in parts]


def merge_plan(old_parts, new_parts) -> list:
    """What pasting `new_parts` (a draft day's parts) onto a block that already has `old_parts` (dicts with "name" and "titles", every step title in the block)
    adds: [{"part": the draft part, "into": index of the same-named old part or None, "steps": the steps not already in the block}]. A part adding nothing is left out."""
    have = list(old_parts[0]["titles"]) if old_parts else []
    out = []
    for p in new_parts:
        into = next((i for i, o in enumerate(old_parts) if o["name"].casefold() == p["name"].casefold()), None)
        fresh = []
        for s in p["steps"]:
            if not any(same_step(s["title"], h) for h in have):
                fresh.append(s)
                have.append(s["title"])
        if into is None or fresh:
            out.append({"part": p, "into": into, "steps": fresh})
    return out


def existing_park(session, day, title):
    """The parts the trip already has for park `title` on trip day `day` (for merge_plan: [{"name", "titles"}]), or [] when there is none."""
    for a in cal.activities(session):
        if a.day == day and a.title == title:
            view = block(session, a.id)
            parts = view["parts"] if view else []
            titles = [s["title"] for p in parts for s in p["steps"]]
            return [{"name": p["name"], "titles": titles} for p in parts]
    return []


def _put(db, table, row):
    insert_only(db, table, row, ["id"], auto_commit=False)


def _step(db, trip_id, act, part, pos, title, time_, who, note, kind, aside):
    _put(db, "block_steps", {"id": uuid.uuid4().hex, "trip_id": trip_id, "act_id": act, "part_id": part, "position": pos, "title": title, "time": time_,
                             "who": json.dumps(who, separators=(",", ":")), "note": note, "kind": kind, "done": 0, "aside": aside, "created_at": familydb.now()})


def _card(who, t, made, steps, lists) -> str:
    """The thread card: "Abhi added Universal Studios Hollywood on Tue and Disney California Adventure on Fri (23 steps)"."""
    places = [f"{title} on {cal._when(t, day, DAY_START).split(' ')[0]}" for _, title, day in made]
    parts = [cal.oxford(places)] if places else []
    if lists:
        parts.append(f"{len(lists)} list{'s' if len(lists) != 1 else ''}: {cal.oxford([x['name'] for x in lists])}")
    return f"{who} added {' and '.join(parts)}" + (f" ({steps} steps)" if steps else "")


# ---- reading and ticking -------------------------------------------------------------------------------------------------

def _who_names(tokens, people) -> list:
    out = []
    for tok in tokens:
        if tok.startswith("m:"):
            out.append(_first_name(tok[2:], people) or "Someone")
        else:
            out.append(tok[2:])
    return out


def _step_view(r, people) -> dict:
    try:
        tokens = [x for x in json.loads(r["who"] or "[]") if isinstance(x, str)]
    except ValueError:
        tokens = []
    return {"id": r["id"], "title": r["title"], "time": r["time"], "who": _who_names(tokens, people), "note": r["note"], "kind": r["kind"], "done": bool(r["done"]), "aside": bool(r["aside"]),
            "act": r["act_id"], "part": r["part_id"], "people": [_person(t, people) for t in tokens], "who_key": tuple(sorted(tokens))}


def _initials(name) -> str:
    words = [w for w in re.split(r"[\s.]+", name or "") if w]
    return "".join(w[0] for w in words[:2]).upper() or "?"


def _person(tok, people) -> dict:
    """One who-token as a person to draw. kind: member (a family member), named (a name nobody matched to a member), initials (letters nobody matched) or group (Adults, Kids)."""
    if tok.startswith("m:"):
        p = next((p for p in people if p["user_id"] == tok[2:]), None)
        return {"kind": "member", "name": _first(p["name"]) if p else "Someone", "initials": p["initials"] if p else "?", "color": p["color"] if p else ""}
    if tok.startswith("g:"):
        return {"kind": "group", "name": tok[2:], "initials": tok[2:], "color": ""}
    if tok.startswith("i:"):
        return {"kind": "initials", "name": tok[2:], "initials": tok[2:] if len(tok[2:]) <= 2 else _initials(tok[2:]), "color": ""}
    return {"kind": "named", "name": tok[2:], "initials": _initials(tok[2:]), "color": ""}


def plan(session) -> dict:
    """Everything the trip canvas draws, in one read: {"blocks": {act id: {"parts": [{id, name, time_of_day, steps[]}], "aside": [steps]}}, "lists": [...]}.
    A step is the dict `_step_view` makes; a block's aside steps carry the name of the part they came from as `part_name`."""
    people = family_people(session)
    out = {"blocks": {}, "lists": []}
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return out
        parts = familydb.rows(fam.db, "SELECT * FROM block_parts WHERE trip_id = :t ORDER BY position, rowid", t=fam.trip_id)
        steps = familydb.rows(fam.db, "SELECT * FROM block_steps WHERE trip_id = :t ORDER BY position, rowid", t=fam.trip_id)
        names = {p["id"]: p["name"] for p in parts}
        for p in parts:
            out["blocks"].setdefault(p["act_id"], {"parts": [], "aside": []})["parts"].append({"id": p["id"], "name": p["name"], "time_of_day": p["time_of_day"], "steps": []})
        for r in steps:
            block = out["blocks"].get(r["act_id"])
            if block is None:
                continue
            v = _step_view(r, people)
            if r["aside"]:
                block["aside"].append({**v, "part_name": names.get(r["part_id"], "")})
            elif (part := next((p for p in block["parts"] if p["id"] == r["part_id"]), None)):
                part["steps"].append(v)
        lists = familydb.rows(fam.db, "SELECT * FROM trip_lists WHERE trip_id = :t ORDER BY position, rowid", t=fam.trip_id)
        items = familydb.rows(fam.db, "SELECT * FROM trip_list_items WHERE trip_id = :t ORDER BY position, rowid", t=fam.trip_id)
        for lst in lists:
            owner = lst["for_who"]
            out["lists"].append({"id": lst["id"], "name": lst["name"], "for": (_who_names([owner], people)[0] if owner else ""), "items": [{"title": i["title"], "note": i["note"]} for i in items if i["list_id"] == lst["id"]]})
    return out


def block_ids(session) -> set:
    """The ids of this trip's calendar activities that have parts and steps."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return set()
        return {r["act_id"] for r in familydb.rows(fam.db, "SELECT DISTINCT act_id FROM block_parts WHERE trip_id = :t", t=fam.trip_id)}


def block(session, act_id):
    """One block with its parts, steps and Set aside tray, and the trip's lists; None when the activity is gone or has no parts."""
    people = family_people(session)
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return None
        act = familydb.row(fam.db, "SELECT * FROM activities WHERE trip_id = :t AND scope = '' AND act_id = :a AND gone = 0", t=fam.trip_id, a=act_id)
        parts = familydb.rows(fam.db, "SELECT * FROM block_parts WHERE trip_id = :t AND act_id = :a ORDER BY position, rowid", t=fam.trip_id, a=act_id)
        if not act or not parts:
            return None
        steps = familydb.rows(fam.db, "SELECT * FROM block_steps WHERE trip_id = :t AND act_id = :a ORDER BY position, rowid", t=fam.trip_id, a=act_id)
        lists = familydb.rows(fam.db, "SELECT * FROM trip_lists WHERE trip_id = :t ORDER BY position, rowid", t=fam.trip_id)
        items = familydb.rows(fam.db, "SELECT * FROM trip_list_items WHERE trip_id = :t ORDER BY position, rowid", t=fam.trip_id)
        views = [_step_view(r, people) for r in steps]
        by_part = {}
        for r, v in zip(steps, views):
            if not r["aside"]:
                by_part.setdefault(r["part_id"], []).append(v)
        out_lists = []
        for lst in lists:
            owner = lst["for_who"]
            out_lists.append({"id": lst["id"], "name": lst["name"], "for": (_who_names([owner], people)[0] if owner else ""), "items": [{"title": i["title"], "note": i["note"]} for i in items if i["list_id"] == lst["id"]]})
        return {"act": cal._act(act), "parts": [{"id": p["id"], "name": p["name"], "time_of_day": p["time_of_day"], "steps": by_part.get(p["id"], [])} for p in parts],
                "aside": [v for r, v in zip(steps, views) if r["aside"]], "lists": out_lists}


CARD_WINDOW = 15 * 60   # seconds: ticks by one person on one block inside this window share a single thread card


def _tick(session, step_id, column, value):
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise CanvasError("Open a trip first.")
        with familydb.transaction(fam.db):
            found = familydb.row(fam.db, "SELECT act_id, kind, title, done, aside FROM block_steps WHERE id = :i AND trip_id = :t", i=step_id, t=fam.trip_id)
            if not found:
                raise CanvasError("That step is gone.")
            familydb.run(fam.db, f"UPDATE block_steps SET {column} = :v WHERE id = :i", v=1 if value else 0, i=step_id)   # column is one of two fixed names
            if bool(found[column]) != bool(value):
                _tell(session, fam, found, column, bool(value))
        return found["act_id"]


def _tell(session, fam, step, column, value):
    """The family's thread card for a tick, coalesced: three rides marked done in a row are one card, "Abhi finished 3 rides at Universal Studios Hollywood",
    changed in place (no second push) while the same person keeps ticking that block. Undoing a tick takes one off the card that counts it; with no such card
    there is nothing to say."""
    act = familydb.row(fam.db, "SELECT title FROM activities WHERE trip_id = :t AND scope = '' AND act_id = :a", t=fam.trip_id, a=step["act_id"])
    where = act["title"] if act else "the trip"
    key = f"{column}:{step['act_id']}"
    verb = {"done": "finished", "aside": "set aside", "moved": "moved", "added": "added"}[column]
    who = familythread.first_name(fam.traveler)
    last = familydb.row(fam.db, "SELECT rowid AS n, * FROM thread WHERE trip_id = :t ORDER BY rowid DESC LIMIT 1", t=fam.trip_id)
    card, payload = None, {}
    if last and last["kind"] == "change" and last["author"] == fam.traveler.id:
        try:
            payload = json.loads(last["payload"] or "{}")
        except ValueError:
            payload = {}
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last["created_at"])).total_seconds()
        if payload.get("key") == key and age <= CARD_WINDOW:
            card = last
    if card is None:
        if value:
            familythread.change(session, fam, f"{who} {verb} {step['title']} at {where}", action="change")
            made = familydb.row(fam.db, "SELECT rowid AS n FROM thread WHERE trip_id = :t ORDER BY rowid DESC LIMIT 1", t=fam.trip_id)
            familydb.run(fam.db, "UPDATE thread SET payload = :p WHERE rowid = :n", p=json.dumps({"action": "change", "key": key, "n": 1, "kinds": [step["kind"]]}, separators=(",", ":")), n=made["n"])
        return
    n = payload.get("n", 1) + (1 if value else -1)
    kinds = (payload.get("kinds") or []) + ([step["kind"]] if value else [])
    if n <= 0:
        familydb.run(fam.db, "DELETE FROM thread WHERE rowid = :n", n=card["n"])
        return
    noun = ("ride" if n == 1 else "rides") if set(kinds) == {"ride"} else ("step" if n == 1 else "steps")
    familydb.run(fam.db, "UPDATE thread SET text = :x, payload = :p WHERE rowid = :n", x=f"{who} {verb} {n} {noun} at {where}",
                 p=json.dumps({"action": "change", "key": key, "n": n, "kinds": kinds[-n:]}, separators=(",", ":")), n=card["n"])


def set_done(session, step_id, done=True) -> str:
    """Mark a step done (or not). The id of its block. CanvasError when the step is gone."""
    return _tick(session, step_id, "done", done)


def set_aside(session, step_id, aside=True) -> str:
    """Move a step to the block's Set aside tray (or back). The id of its block."""
    return _tick(session, step_id, "aside", aside)


# ---- moving, adding and annotating by touch (F-082) -----------------------------------------------------------------------

MAX_NOTE = 200
MAX_UNDO = 120


def _norm(title) -> str:
    """A ride's name for comparing: lower case, no punctuation, no leading "the"."""
    words = re.sub(r"[^a-z0-9 ]+", " ", str(title or "").casefold().replace("'", "").replace("’", "")).split()
    return " ".join(words[1:] if words[:1] == ["the"] and len(words) > 1 else words)


def same_step(step_title, item_title) -> bool:
    """Is a step the list item? Equal names, or one name starts (whole words) with the other: "Soarin'" is "Soarin' Around the World"."""
    a, b = _norm(step_title), _norm(item_title)
    return bool(a and b) and (a == b or a.startswith(b + " ") or b.startswith(a + " "))


def list_hits(step_title, lists) -> list:
    """The ids of the trip's lists that name this step."""
    return [lst["id"] for lst in lists if any(same_step(step_title, i["title"]) for i in lst["items"])]


def _live(db, trip_id, act_id) -> bool:
    """Is that block a live calendar activity of this trip (not deleted)?"""
    return bool(familydb.row(db, "SELECT 1 AS x FROM activities WHERE trip_id = :t AND scope = '' AND act_id = :a AND gone = 0", t=trip_id, a=act_id))


def _ordered(db, trip_id, part_id, skip=""):
    return [r for r in familydb.rows(db, "SELECT * FROM block_steps WHERE trip_id = :t AND part_id = :p AND aside = 0 ORDER BY position, rowid", t=trip_id, p=part_id) if r["id"] != skip]


def _state(r) -> dict:
    return {"id": r["id"], "act": r["act_id"], "part": r["part_id"], "position": r["position"], "time": r["time"], "aside": r["aside"]}


def _clock12(value) -> str:
    h, m = (int(x) for x in value.split(":"))
    return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def move_step(session, step_id, *, part="", before="", act="", aside=False) -> dict:
    """Move one step, in one transaction. Where it goes: `aside` (the block's Set aside tray), `part` (a part of any block, placed before the step `before`, else at
    the end), or `act` (another block, in its same-named part or its first). A step dropped before a timed step takes that step's time; at the end of a part it
    keeps its own. The family's thread card is changed in place (moves coalesce like ticks). -> {"title", "where", "act" (the block it is in now), "changed",
    "undo" (a snapshot `restore` puts back exactly)}. CanvasError when the step or the place is not in this trip."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise CanvasError("Open a trip first.")
        db, trip = fam.db, fam.trip_id
        try:
            days = cal.days(cal._need(fam, "")[1])
        except cal.CalendarError:
            days = []
        with familydb.transaction(db):
            s = familydb.row(db, "SELECT * FROM block_steps WHERE id = :i AND trip_id = :t", i=step_id, t=trip)
            if not s:
                raise CanvasError("That step is gone.")
            src_act = s["act_id"]
            if aside:
                undo = {"kind": "aside", "act": src_act, "steps": [_state(s)]}
                if s["aside"]:
                    return {"title": s["title"], "where": "the Set aside tray", "act": src_act, "changed": False, "undo": undo}
                familydb.run(db, "UPDATE block_steps SET aside = 1 WHERE id = :i", i=s["id"])
                _tell(session, fam, s, "aside", True)
                return {"title": s["title"], "where": "the Set aside tray", "act": src_act, "changed": True, "undo": undo}
            if part:
                target = familydb.row(db, "SELECT * FROM block_parts WHERE id = :p AND trip_id = :t", p=part, t=trip)
            elif act:
                options = familydb.rows(db, "SELECT * FROM block_parts WHERE trip_id = :t AND act_id = :a ORDER BY position, rowid", t=trip, a=act)
                mine = familydb.row(db, "SELECT name FROM block_parts WHERE id = :p AND trip_id = :t", p=s["part_id"], t=trip)
                target = next((p for p in options if mine and p["name"] == mine["name"]), options[0] if options else None)
            else:
                raise CanvasError("Pick where to put it.")
            if not target or not _live(db, trip, target["act_id"]):
                raise CanvasError("That place is not in this trip.")
            tgt = _ordered(db, trip, target["id"], skip=s["id"])
            src = _ordered(db, trip, s["part_id"], skip=s["id"]) if s["part_id"] and s["part_id"] != target["id"] else []
            idx = next((i for i, r in enumerate(tgt) if r["id"] == before), len(tgt))
            anchor = tgt[idx] if idx < len(tgt) else None
            time_ = anchor["time"] if anchor and anchor["time"] else s["time"]
            undo = {"kind": "moved", "act": src_act, "steps": [_state(s)] + [_state(r) for r in tgt + src][: MAX_UNDO - 1]}
            order = tgt[:idx] + [s] + tgt[idx:]
            if (not s["aside"] and s["part_id"] == target["id"] and time_ == s["time"]
                    and [r["id"] for r in order] == [r["id"] for r in _ordered(db, trip, target["id"])]):
                return {"title": s["title"], "where": target["name"], "act": src_act, "changed": False, "undo": undo}
            for n, r in enumerate(order):
                if r["id"] == s["id"]:
                    familydb.run(db, "UPDATE block_steps SET act_id = :a, part_id = :p, position = :n, time = :tm, aside = 0 WHERE id = :i", a=target["act_id"], p=target["id"], n=n, tm=time_, i=s["id"])
                else:
                    familydb.run(db, "UPDATE block_steps SET position = :n WHERE id = :i", n=n, i=r["id"])
            for n, r in enumerate(src):
                familydb.run(db, "UPDATE block_steps SET position = :n WHERE id = :i", n=n, i=r["id"])
            if target["act_id"] != src_act:
                day = familydb.row(db, "SELECT day, title FROM activities WHERE trip_id = :t AND scope = '' AND act_id = :a AND gone = 0", t=trip, a=target["act_id"])
                where = days[day["day"]].strftime("%A") if day and 0 <= day["day"] < len(days) else (day["title"] if day else target["name"])
            elif s["part_id"] != target["id"] or s["aside"]:
                where = target["name"]
            elif time_ != s["time"]:
                where = _clock12(time_)
            else:
                where = "a new spot in " + target["name"]
            _tell(session, fam, s, "moved", True)
            return {"title": s["title"], "where": where, "act": target["act_id"], "changed": True, "undo": undo}


def restore(session, snapshot) -> str:
    """Put steps back exactly as a snapshot from `move_step` recorded them (their block, part, place in the part, time and tray), and take the move off the
    family's card. The snapshot comes from the page, so every id, part, time and number in it is checked against this trip. -> the block the moved step is back in."""
    if (not isinstance(snapshot, dict) or snapshot.get("kind") not in ("moved", "aside") or not isinstance(snapshot.get("steps"), list)
            or not 0 < len(snapshot["steps"]) <= MAX_UNDO):
        raise CanvasError("There is nothing to undo.")
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise CanvasError("Open a trip first.")
        db, trip = fam.db, fam.trip_id
        with familydb.transaction(db):
            ok = []
            for x in snapshot["steps"]:
                x = x if isinstance(x, dict) else {}
                row = familydb.row(db, "SELECT * FROM block_steps WHERE id = :i AND trip_id = :t", i=str(x.get("id") or "")[:40], t=trip)
                part, act, pos, tm, aside = str(x.get("part") or "")[:40], str(x.get("act") or "")[:20], x.get("position"), str(x.get("time") or ""), x.get("aside")
                if (not row or not isinstance(pos, int) or isinstance(pos, bool) or not 0 <= pos < 10000 or aside not in (0, 1) or isinstance(aside, bool)
                        or (tm and _clock(tm) != tm)):
                    raise CanvasError("There is nothing to undo.")
                if part:
                    owner = familydb.row(db, "SELECT act_id FROM block_parts WHERE id = :p AND trip_id = :t", p=part, t=trip)
                    valid = bool(owner) and owner["act_id"] == act
                else:
                    valid = aside == 1 and bool(familydb.row(db, "SELECT 1 AS x FROM block_parts WHERE act_id = :a AND trip_id = :t", a=act, t=trip))
                if not valid:
                    raise CanvasError("There is nothing to undo.")
                ok.append((row, act, part, pos, tm, aside))
            for row, act, part, pos, tm, aside in ok:
                familydb.run(db, "UPDATE block_steps SET act_id = :a, part_id = :p, position = :n, time = :tm, aside = :s WHERE id = :i", a=act, p=part, n=pos, tm=tm, s=aside, i=row["id"])
            first = ok[0][0]
            source = str(snapshot.get("act") or "")[:20]
            if not familydb.row(db, "SELECT 1 AS x FROM block_parts WHERE act_id = :a AND trip_id = :t", a=source, t=trip):
                raise CanvasError("There is nothing to undo.")
            _tell(session, fam, {"act_id": source, "kind": first["kind"], "title": first["title"]}, "aside" if snapshot["kind"] == "aside" else "moved", False)
            return ok[0][1]


def _who_options(db, trip_id, people) -> set:
    """The who tokens a new step may name: the family's members, Adults and Kids, and names or initials already used on this trip."""
    seen = set()
    for r in familydb.rows(db, "SELECT who FROM block_steps WHERE trip_id = :t", t=trip_id):
        try:
            seen |= {x for x in json.loads(r["who"] or "[]") if isinstance(x, str) and x[:2] in ("n:", "i:")}
        except ValueError:
            pass
    return {f"m:{p['user_id']}" for p in people} | seen | {"g:Adults", "g:Kids"}


def add_step(session, act_id, part_id, title, time="", who=(), note="") -> str:
    """A new step at the end of a part. `who`: tokens ("m:<id>", "g:Adults", "g:Kids", or a name or initials already on this trip); none means everyone. The new
    step's id. The family's card says it was added (coalesced). CanvasError for an empty title, a part that is not in that block, a bad time or too many steps."""
    title, note, time = _s(title, 80), _s(note, MAX_NOTE), str(time or "").strip()
    if not title:
        raise CanvasError("Give the step a name.")
    if time and not _clock(time):
        raise CanvasError("That time is not one we can read.")
    people = family_people(session)
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise CanvasError("Open a trip first.")
        db, trip = fam.db, fam.trip_id
        allowed, tokens = _who_options(db, trip, people), []
        for w in list(who)[: MAX_WHO + 1]:
            if w not in allowed:
                raise CanvasError("Pick people from the family.")
            if w not in tokens:
                tokens.append(w)
        if len(tokens) > MAX_WHO:
            raise CanvasError("Pick up to six people, or leave it for everyone.")
        with familydb.transaction(db):
            if not _live(db, trip, act_id) or not familydb.row(db, "SELECT 1 AS x FROM block_parts WHERE id = :p AND trip_id = :t AND act_id = :a", p=part_id, t=trip, a=act_id):
                raise CanvasError("Pick a part of this day.")
            if familydb.row(db, "SELECT COUNT(*) AS n FROM block_steps WHERE trip_id = :t", t=trip)["n"] >= MAX_STEP_PER_TRIP:
                raise CanvasError(cal.FULL)
            last = familydb.row(db, "SELECT COALESCE(MAX(position), -1) + 1 AS n FROM block_steps WHERE trip_id = :t AND part_id = :p AND aside = 0", t=trip, p=part_id)["n"]
            sid = uuid.uuid4().hex
            _put(db, "block_steps", {"id": sid, "trip_id": trip, "act_id": act_id, "part_id": part_id, "position": last, "title": title, "time": _clock(time),
                                     "who": json.dumps(tokens, separators=(",", ":")), "note": note, "kind": "other", "done": 0, "aside": 0, "created_at": familydb.now()})
            _tell(session, fam, {"act_id": act_id, "kind": "other", "title": title}, "added", True)
            return sid


def set_note(session, step_id, note) -> str:
    """Write (or clear) a step's note. The id of its block. No card: a note is not a change to the plan."""
    note = _s(note, MAX_NOTE)
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise CanvasError("Open a trip first.")
        with familydb.transaction(fam.db):
            found = familydb.row(fam.db, "SELECT act_id FROM block_steps WHERE id = :i AND trip_id = :t", i=step_id, t=fam.trip_id)
            if not found:
                raise CanvasError("That step is gone.")
            familydb.run(fam.db, "UPDATE block_steps SET note = :n WHERE id = :i", n=note, i=step_id)
            return found["act_id"]
