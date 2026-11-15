"""Add to my plan (F-262): a guide's stops dropped into the family's calendar (/trip/plan), through the same two things the rail's "+" uses: `planv2.pick_slot` (a free hour that suits the stop,
never over a booking or another plan, inside the day's window) and `planedit.add` (the calendar's own rules and the family's card, with an Undo). The stop's own time in the post is not used: a
creator's morning is not the family's, and a stop with no time is most of them. What a stop is called is the creator's own title, cut to the calendar's 40 characters.

    add(session, guide, keys)   [{"title", "when", "undo"}] added, and the names skipped: one already in the plan, or no free time that fits (the page says so)
"""

from gitaway import planedit, planv2 as pv, tripcal as cal

KIND = {"food": "food", "walk": "outdoors", "ride": "travel", "show": "culture", "tix": "fun", "see": "culture"}      # a stop's kind -> the calendar's
MINUTES = {"food": 90, "ride": 60}
DEFAULT_MINUTES = 120
MAX_AT_ONCE = 14


def add(session, guide, keys) -> dict:
    """Put the stops `keys` ("d0s1"...) of `guide` into the plan, one by one: a plan added changes what is free for the next. Raises tripcal.CalendarError (a sentence fit to show) when the calendar
    refuses, for instance a family with no trip."""
    added, skipped = [], []
    for key in list(dict.fromkeys(keys))[:MAX_AT_ONCE]:
        stop = guide.find(key)
        if stop is None:
            continue
        title = stop.name[:40].strip()
        v = pv.view(session, lambda day=0, booked="": "")
        if any(p.title == title for p in v.plans):
            skipped.append(stop.name)
            continue
        minutes = MINUTES.get(stop.kind, DEFAULT_MINUTES)
        slot = pv.pick_slot(v, KIND[stop.kind], minutes, False)
        if slot is None:
            skipped.append(stop.name)
            continue
        day, start = slot
        got = planedit.add(session, day=day, start=start, end=start + minutes, title=title, kind=KIND[stop.kind])
        a = got["act"]
        date = dict(v.days)[a.day]
        added.append({"title": a.title, "when": f"{date.strftime('%a')} {date.day} · {cal.fmt_time(a.start)}", "undo": got["undo"]})
    return {"added": added, "skipped": skipped}
