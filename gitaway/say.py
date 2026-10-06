"""The one Ask box (F-087): talk, type or paste a change to a day, or a whole itinerary; GitAway asks only what it must, shows one preview, and Apply saves it.

    route(text)                          "change" (a short request: what to do to one day) or "plan" (a long paste or ramble: a plan with parks, parts and steps)
    start(session, text, day)            read it with the model (job "speak" for a change, job "convert" for a plan) -> a step
    answer(session, state, answers, text)   the follow-up answers ("a_<question id>": value) -> the next step; no model call for a plan, one for a change that was
                                         waiting for its day
    apply(session, state, token, trip)   save the previewed plan or change: one transaction, one thread card, the family told once

A step is {"state": {...}, "questions": [question]} while something is unclear, else {"state", "questions": [], "preview": preview}. A question is
{"id", "text", "options": [{"value", "label"}], "suggest": value}: ask one tap each with the suggestion already chosen. Ids: `day` (a change with no day),
`park:<n>` (which day a park is), `who:<initial>` (who an initial in a plan is), `time:<op>` (a new or moved plan with no time), `who:<op>:<k>` (a name on a step
nobody in the family has). A preview is {"kind", "groups": [{"day", "label", "chips"}], "summary", "dropped", "tidy", "token"} with the same chips Ask has always shown.

The state travels in a hidden field of the page's own form (like Convert's draft did) and is checked again at Apply: a plan goes through canvas.clean and
canvas.save, a change through speak.validate and speak.apply, so a doctored form can change nothing a request could not. The model is only reached through
gitaway.ai (jobs "speak" and "convert", docs/ai-usage.md). A long text is a plan, a short one a change: one rule, no second model call to decide.
"""

import json
from datetime import datetime, timedelta

from gitaway import canvas, familythread, session as ses, speak, tripcal as cal

LIMIT = canvas.MAX_TEXT
SLOTS = ("09:00", "12:00", "15:00", "18:00")
KEEP = "i:"


class SayError(ValueError):
    """Something to tell the person, in words fit to show. `step` (when set) is the questions page to show again, with the choices kept."""

    def __init__(self, text, step=None):
        super().__init__(text)
        self.step = step


def route(text) -> str:
    return "plan" if len(" ".join((text or "").split())) > speak.MAX_REQUEST else "change"


def _clean_text(text) -> str:
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        raise SayError("Say, type or paste what you want first.")
    if len(text) > LIMIT:
        raise SayError(f"That is {len(text) - LIMIT:,} characters over the {LIMIT:,} limit. Paste it in two parts.")
    return text


def _trip(session):
    return cal.trip("", ses.booking(session))


def _days(session):
    return cal.days(_trip(session))


def _day_label(d) -> str:
    return f"{d.strftime('%a %b')} {d.day}"


def _long_day(d) -> str:
    return f"{d.strftime('%A')}, {d.strftime('%b')} {d.day}"


def day_options(session) -> list:
    return [{"value": str(i), "label": _day_label(d)} for i, d in enumerate(_days(session))]


# ---- starting --------------------------------------------------------------------------------------------------------------------

def start(session, text, day) -> dict:
    """The first step for what was said, typed or pasted. `day` is the trip day it came from, or None. Raises SayError, speak.SpeakError, canvas.CanvasError or ai.AIError."""
    text = _clean_text(text)
    if route(text) == "plan":
        return _start_plan(session, text, day)
    if day is None and speak.today_index(session) is not None:
        day = speak.default_day(session)       # on the trip: a short change is about today; the preview names the day and "Change it" can fix a wrong guess
    if day is None:
        return {"state": {"kind": "need_day"}, "questions": [_day_question(session)]}
    return _start_change(session, text, day)


def _day_question(session) -> dict:
    return {"id": "day", "text": "Which day?", "options": day_options(session), "suggest": str(speak.default_day(session))}


# ---- a change --------------------------------------------------------------------------------------------------------------------

def _start_change(session, text, day) -> dict:
    ctx, answer = speak.ask_model(session, day, text)
    ops = [o for o in (answer.get("ops") if isinstance(answer.get("ops"), list) else [])[: speak.MAX_OPS * 4] if isinstance(o, dict)]
    return _settle_change(session, {"kind": "change", "day": day, "summary": str(answer.get("summary") or "")[:400], "ops": ops}, ctx)


def _slot_question(ctx, i, op) -> dict:
    title = speak._title(op.get("title")) or (ctx["plans"].get(op.get("id")) or {}).get("title") or "this"
    busy = [(a["start_min"], a["end_min"]) for a in ctx["plans"].values()] + [(b.start, b.end) for b in ctx["booked"]]
    floor = ctx["now"] or 0
    free = [s for s in SLOTS if speak._minutes(s) >= floor and not any(speak._minutes(s) < e and b < speak._minutes(s) + 60 for b, e in busy)]
    return {"id": f"time:{i}", "text": f"What time is {title}?", "options": [{"value": s, "label": cal.fmt_time(speak._minutes(s))} for s in SLOTS], "suggest": (free or SLOTS)[0]}


def _who_questions(ctx, i, op) -> list:
    people = ctx["people"]
    step = ctx["steps"].get(speak._s(op.get("id"), 40)) if op.get("op") == "set_step_who" else None
    out = []
    for k, name in enumerate(op.get("who") if isinstance(op.get("who"), list) else []):
        try:
            speak.resolve_who([name], people, step)
            continue
        except speak.SpeakError:
            pass
        token = speak._s(name, 30)
        found = canvas.suggest(token, people, "")
        first = canvas._first_name(found["member"], people) if found["member"] else ""
        options = [{"value": canvas._first(p["name"]), "label": canvas._first(p["name"])} for p in people] + [{"value": "", "label": "Leave them off"}]
        out.append({"id": f"who:{i}:{k}", "text": f"Who is {token}?", "options": options, "suggest": first})
    return out


def _change_questions(ctx, ops) -> list:
    out = []
    for i, op in enumerate(ops):
        if op.get("op") in ("add_plan", "move_plan") and not (speak._clock(op.get("start")) and speak._clock(op.get("end"))) and not (op.get("op") == "move_plan" and op.get("id") not in ctx["plans"]):
            out.append(_slot_question(ctx, i, op))
        if op.get("op") in ("add_step", "set_step_who"):
            out += _who_questions(ctx, i, op)
    return out


def _patch_change(ctx, ops, answers) -> list:
    """The model's operations with the follow-up answers put in (a copy)."""
    ops = [dict(o, who=list(o["who"]) if isinstance(o.get("who"), list) else []) for o in ops]
    drops = {}
    for key, value in answers.items():
        if key.startswith("time:") and key[5:].isdigit() and int(key[5:]) < len(ops) and speak._clock(value):
            op = ops[int(key[5:])]
            start = speak._minutes(speak._clock(value))
            end = speak._minutes(speak._clock(op.get("end"))) if speak._clock(op.get("end")) else 0
            op["start"] = speak._clock(value)
            op["end"] = speak._hhmm(end if end > start else min(start + 60, 23 * 60 + 59))
        elif key.startswith("who:") and key.count(":") == 2:
            _, i, k = key.split(":")
            if i.isdigit() and k.isdigit() and int(i) < len(ops) and int(k) < len(ops[int(i)]["who"]):
                drops[(int(i), int(k))] = speak._s(value, 40)
    for (i, k), value in sorted(drops.items(), reverse=True):
        if value:
            ops[i]["who"][k] = value
        else:
            del ops[i]["who"][k]
    return ops


def _hour_long(ops) -> list:
    """A plan Ask adds with a start and no length gets an hour (F-097): the model is not asked, and neither is the family. A late one ends at the calendar's
    10 PM instead (a 9:30 swim is 9:30–10:00); one starting after 9:30 PM can't have the 30-minute minimum and is left out with the calendar's reason."""
    out = []
    for o in ops:
        if o.get("op") == "add_plan" and speak._clock(o.get("start")) and not speak._clock(o.get("end")):
            o = dict(o, end=speak._hhmm(min(speak._minutes(speak._clock(o["start"])) + 60, 22 * 60)))
        out.append(o)
    return out


def _settle_change(session, state, ctx=None) -> dict:
    ctx = ctx or speak.load_day(session, state["day"])
    state = dict(state, ops=_hour_long(state["ops"]))
    questions = _change_questions(ctx, state["ops"])
    if questions:
        return {"state": state, "questions": questions}
    prop = speak.proposal_from(ctx, state["summary"], state["ops"])
    tidy = []
    return {"state": state, "questions": [], "preview": {"kind": "change", "groups": [{"day": state["day"], "label": _long_day(ctx["date"]), "chips": prop["changes"]}],
                                                          "summary": prop["summary"], "dropped": prop["dropped"], "tidy": tidy, "token": prop["token"], "ops": prop["ops"]}}


# ---- a plan ----------------------------------------------------------------------------------------------------------------------

def _pin(draft, day):
    """Everything on one day: the draft's days become one (the first park's name, all the parts in order, capped; the set-aside items go with it).
    Returns (draft, the names of the parts that did not fit)."""
    days = draft["days"]
    if len(days) <= 1:
        return draft, []
    every = [p for d in days for p in d["parts"]]
    merged = {"label": days[0]["label"], "place": days[0]["place"], "date": "", "parts": every[: canvas.MAX_PARTS]}
    cut = [p["name"] for p in every[canvas.MAX_PARTS:]]
    return canvas.clean({**draft, "days": [merged], "set_aside": [dict(a, day=0) for a in draft["set_aside"]]}), cut


def _passed(session, days):
    """SayError when any of these trip days has already passed (today is fine)."""
    if any(isinstance(d, int) and speak.is_past(session, d) for d in days):
        raise SayError("That day has already passed. Pick today or a day to come.")


def _start_plan(session, text, day) -> dict:
    if day is not None:
        _passed(session, [day])
    t = _trip(session)
    shown = [f"{(t.depart + timedelta(days=i)).isoformat()} {(t.depart + timedelta(days=i)).strftime('%A')}" for i in range((t.return_ - t.depart).days + 1)]
    draft = canvas.convert(session, text, trip_days=shown)
    cut = []
    if day is not None:
        draft, cut = _pin(draft, day)
    days = [day] * len(draft["days"]) if day is not None else [None] * len(draft["days"])
    if day is None:
        dated = _dated(session, draft)
        if None not in dated and len(set(dated)) == len(dated) and not any(speak.is_past(session, i) for i in dated):
            days = dated        # every park's date was read from the text and is inside the trip: no question, the preview shows the days
    state = {"kind": "plan", "draft": draft, "days": days, "pinned": day is not None, "who": {}, "cut": cut}
    return _settle_plan(session, state, text)


def _dated(session, draft) -> list:
    """The trip day of each park's date as the model read it, None where there is no date or it is outside the trip."""
    t = _trip(session)
    n = (t.return_ - t.depart).days + 1
    out = []
    for d in draft["days"]:
        try:
            idx = (datetime.strptime(d.get("date") or "", "%Y-%m-%d").date() - t.depart).days
        except ValueError:
            idx = -1
        out.append(idx if 0 <= idx < n else None)
    return out


def _suggested_days(session, draft) -> list:
    """A day for each park: the date the model read (unless it has passed), else the next free day in order from today (or the trip's first day)."""
    n = len(_days(session))
    out = [None if i is not None and speak.is_past(session, i) else i for i in _dated(session, draft)]
    free = [i for i in list(range(speak.default_day(session), n)) + list(range(0, speak.default_day(session))) if i not in out]
    return [v if v is not None else (free.pop(0) if free else 0) for v in out]


def _plan_questions(session, state, text, again=False) -> list:
    draft = state["draft"]
    out = []
    if not state["pinned"] and (again or any(d is None for d in state["days"])):
        suggest = _suggested_days(session, draft)
        for i, d in enumerate(draft["days"]):
            picked = state["days"][i] if i < len(state["days"]) and state["days"][i] is not None else suggest[i]
            out.append({"id": f"park:{i}", "text": f"Which day is {d['place']}?", "options": day_options(session), "suggest": str(picked)})
    people = canvas.family_people(session)
    for entry in canvas.questions(draft, people, text)["who"] if not again else []:
        tok = entry["token"]
        if tok in state["who"]:
            continue
        keep = f"{KEEP}{tok}"
        options = [{"value": f"m:{p['user_id']}", "label": canvas._first(p["name"])} for p in people] + [{"value": keep, "label": f"Keep as {tok}"}]
        picked = state["who"].get(tok) or (f"m:{entry['member']}" if entry["member"] else keep)
        out.append({"id": f"who:{tok}", "text": f"Who is {tok}?", "options": options, "suggest": picked, "why": entry["why"]})
    return out


def _areas(day) -> str:
    names = [p["name"].lower() if p["name"].casefold() in ("breakfast", "lunch", "dinner", "snack") else p["name"] for p in day["parts"]]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + ", then " + names[-1]


def _plural(n, one, many) -> str:
    return f"{n} {one if n == 1 else many}"


def _plan_preview(session, state) -> dict:
    draft, days = state["draft"], state["days"]
    dates = _days(session)
    groups, idle = {}, []
    for i, d in enumerate(draft["days"]):
        steps = sum(len(p["steps"]) for p in d["parts"])
        areas = sum(1 for p in d["parts"] if p["steps"])
        after = f"{cal.fmt_time(canvas.DAY_START)}–{cal.fmt_time(canvas.DAY_END)} · {_plural(areas, 'area', 'areas')}, {_plural(steps, 'ride or show', 'rides and shows')}"
        chip = {"kind": "new", "label": d["place"], "before": "", "after": after, "warn": "", "detail": _areas(d)}
        old = canvas.existing_park(session, days[i], d["place"]) if isinstance(days[i], int) else []
        if old:         # the park is already on that day: what is new is added to it
            added = canvas.merge_plan(old, d["parts"])
            new_steps = sum(len(m["steps"]) for m in added)
            more = canvas.new_aside(old[0]["titles"], [a for a in draft["set_aside"] if a["day"] == i])
            if not added and not more:
                chip.update(kind="changed", after="Nothing new", detail="", warn="Everything in this is already on that day. It is left as it is.")
                idle.append(chip)
            elif not added:
                chip.update(kind="changed", before="", after=f"Adds {_plural(len(more), 'set-aside item', 'set-aside items')} to what is already there", detail=", ".join(a["title"] for a in more))
            else:
                new_parts = [m["part"]["name"] for m in added if m["into"] is None]
                chip.update(kind="changed", after=f"Adds {_plural(len(new_parts), 'area', 'areas')} and {_plural(new_steps, 'ride or show', 'rides and shows')} to what is already there",
                            detail=", ".join(new_parts + [f"more in {m['part']['name']}" for m in added if m["into"] is not None]), before="")
        groups.setdefault(days[i], []).append(chip)
    if idle and len(idle) == len(draft["days"]) and all(x["name"].casefold() in {y["name"].casefold() for y in canvas.plan(session)["lists"]} for x in draft["lists"]):
        for c in idle:
            c["warn"] = "Everything in this is already on that day. Apply will add nothing."
    tidy = []
    if state.get("cut"):
        tidy.append(f"{_plural(len(state['cut']), 'part', 'parts')} did not fit on one day and {'was' if len(state['cut']) == 1 else 'were'} left out: " + ", ".join(state["cut"]) + ".")
    if draft["merged_repeats"]:
        tidy.append(f"Merged {_plural(draft['merged_repeats'], 'repeated item', 'repeated items')}. It was sent twice.")
    if draft["set_aside"]:
        tidy.append("Set aside: " + ", ".join(a["title"] for a in draft["set_aside"]) + ". Still in the trip, just not in a day.")
    known = {x["name"].casefold() for x in canvas.plan(session)["lists"]}
    for lst in draft["lists"]:
        if lst["name"].casefold() in known:
            tidy.append(f"The list {lst['name']} is already in the trip, so it is not made again.")
            continue
        tidy.append(f"Made a list: {lst['name']} ({len(lst['items'])}).")
    if draft["notes_kept"]:
        tidy.append("Kept your notes: " + " · ".join(draft["notes_kept"]))
    return {"kind": "plan", "groups": [{"day": n, "label": _long_day(dates[n]), "chips": groups[n]} for n in sorted(groups)], "summary": "", "dropped": [], "tidy": tidy, "token": "", "ops": []}


def _settle_plan(session, state, text="") -> dict:
    questions = _plan_questions(session, state, text)
    if questions:
        return {"state": state, "questions": questions}
    return {"state": state, "questions": [], "preview": _plan_preview(session, state)}


def _check_plan(state):
    draft = canvas.clean(state.get("draft")) if isinstance(state.get("draft"), dict) else None
    days = state.get("days")
    if not draft or canvas.empty(draft) or not isinstance(days, list) or len(days) != len(draft["days"]):
        raise SayError("That plan was lost. Ask again.")
    who = state.get("who") if isinstance(state.get("who"), dict) else {}
    cut = state.get("cut") if isinstance(state.get("cut"), list) else []
    return {"kind": "plan", "draft": draft, "days": [d if isinstance(d, int) and not isinstance(d, bool) else None for d in days], "pinned": bool(state.get("pinned")),
            "who": {str(k)[:40]: str(v)[:60] for k, v in who.items()}, "cut": [str(x)[:60] for x in cut][:60]}


# ---- answering -------------------------------------------------------------------------------------------------------------------

def answer(session, state, answers, text="") -> dict:
    """The next step after the follow-up answers (`answers`: {"a_<id>": value}). Raises SayError (with `step`, to show the questions again), or what `start` raises."""
    if not isinstance(state, dict):
        raise SayError("That was lost. Ask again.")
    given = {k[2:]: str(v) for k, v in answers.items() if k.startswith("a_")}
    kind = state.get("kind")
    if kind == "need_day":
        n = len(_days(session))
        if not given.get("day", "").isdigit() or not 0 <= int(given["day"]) < n:
            raise SayError("Pick a day.", {"state": state, "questions": [_day_question(session)]})
        return _start_change(session, _clean_text(text), int(given["day"]))
    if kind == "change":
        day = state.get("day")
        ops = state.get("ops") if isinstance(state.get("ops"), list) else []
        if not isinstance(day, int) or not ops:
            raise SayError("That change was lost. Ask again.")
        ctx = speak.load_day(session, day)
        new = {"kind": "change", "day": day, "summary": str(state.get("summary") or "")[:400], "ops": _patch_change(ctx, [o for o in ops if isinstance(o, dict)], given)}
        return _settle_change(session, new, ctx)
    if kind == "plan":
        state = _check_plan(state)
        for key, value in given.items():
            if key.startswith("park:") and key[5:].isdigit() and int(key[5:]) < len(state["days"]) and not state["pinned"]:
                state["days"][int(key[5:])] = int(value) if value.isdigit() and int(value) < len(_days(session)) else None
            elif key.startswith("who:"):
                state["who"][key[4:]] = value
        if not state["pinned"] and (any(d is None for d in state["days"]) or len(set(state["days"])) != len(state["days"])):
            raise SayError("Pick a different day for each park.", {"state": state, "questions": _plan_questions(session, state, text, again=True)})
        try:
            _passed(session, state["days"])
        except SayError as e:
            raise SayError(str(e), {"state": state, "questions": _plan_questions(session, state, text, again=True)})
        return _settle_plan(session, state, text)
    raise SayError("That was lost. Ask again.")



# ---- applying --------------------------------------------------------------------------------------------------------------------

def apply(session, state, token, trip) -> dict:
    """Save what the preview showed. A plan: {"days": [trip day of each park], "steps": n, "count": n}. A change: speak.apply's {"count", "text"} plus "days": [day]."""
    if not isinstance(state, dict):
        raise SayError("That was lost. Ask again.")
    if state.get("kind") == "plan":
        state = _check_plan(state)
        if any(d is None for d in state["days"]):
            raise SayError("Pick a day for each park.")
        _passed(session, state["days"])
        with ses.family(session) as fam:
            try:
                if fam is not None:
                    familythread._check(fam, trip)
            except familythread.ThreadError as e:
                raise SayError(str(e))
        try:
            done = canvas.save(session, state["draft"], {"who": state["who"], "days": state["days"], "list_for": []})
        except canvas.CanvasError as e:
            raise SayError(str(e))
        return {"days": [a[2] for a in done["acts"]] or state["days"], "steps": done["steps"], "count": len(done["acts"]), "lists": done["lists"], "merged": done["merged"]}
    if state.get("kind") == "change" and isinstance(state.get("day"), int):
        ctx = speak.load_day(session, state["day"])
        ops, _ = speak.validate(ctx, state.get("ops"))
        done = speak.apply(session, state["day"], ops, token, trip)
        return {**done, "days": [state["day"]]}
    raise SayError("That was lost. Ask again.")
