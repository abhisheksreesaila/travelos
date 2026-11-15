"""Add to my plan (F-262, F-263): a guide's stops dropped into the family's calendar (/trip/plan), through the same two things the rail's "+" uses: `planv2.pick_slot` (a free hour that suits the
stop, avoiding a real forecast of rain, never over a booking or another plan, inside the day's window) and `planedit.add` (the calendar's own rules and the family's card, with an Undo). The stop's own
time in the post is not used: a creator's morning is not the family's, and a stop with no time is most of them. What a stop is called is the creator's own title, cut to the calendar's 40
characters, and each plan carries a note, "From Maya's guide", which the calendar draws on it.

    add(session, guide, keys, day=None)   {"added": [{"title", "when", "undo", "start", "end"}], "skipped": [names]}: one already in the plan, or no free time that fits (the page says so). With
                                          `day`, the stops go one after the other into that day (a free morning), not wherever suits each best
    free_time(v)                          the first free morning, afternoon or evening of the trip that is long enough for a few stops and not under a real forecast of rain: a Free, or None
    fit_day(guide, free)                  the guide's day whose opening stops fit that free time best: (day number, [stop keys]), or None when not even two fit
"""

from dataclasses import dataclass

from gitaway import planedit, planv2 as pv, tripcal as cal

KIND = {"food": "food", "walk": "outdoors", "ride": "travel", "show": "culture", "tix": "fun", "see": "culture"}      # a stop's kind -> the calendar's
MINUTES = {"food": 90, "ride": 60}
DEFAULT_MINUTES = 120
MAX_AT_ONCE = 14
PARTS = (("morning", 8 * 60, 13 * 60), ("afternoon", 13 * 60, 18 * 60), ("evening", 18 * 60, 22 * 60))
MIN_FREE = 150      # a gap shorter than this is not "free time" for a guide's stops
MIN_STOPS = 2       # a "morning" of one stop is only a stop: the + does that


@dataclass(frozen=True)
class Free:
    day: int         # the trip's day index
    name: str        # "Saturday"
    short: str       # "Sat"
    part: str        # morning | afternoon | evening
    start: int       # minutes after midnight
    end: int

    @property
    def minutes(self) -> int:
        return self.end - self.start

    @property
    def said(self) -> str:
        return f"Your {self.name} {self.part} is free."


def free_time(v) -> Free | None:
    """Day by day, part by part (a morning, an afternoon, an evening cut by the day's own window and by every booking and plan), the first gap of MIN_FREE minutes or more. A day whose real
    forecast says rain or snow is not offered (typical weather and the sample's never rule a day out)."""
    for i, date in v.days:
        if v.sky[i].wet:
            continue
        lo, hi = v.windows[i]
        busy = sorted(pv._busy(v, i))
        for part, ps, pe in PARTS:
            a, z = max(lo, ps), min(hi, pe)
            cursor, best = a, None
            for b0, b1 in [*busy, (z, z)]:
                if b1 <= cursor:
                    continue
                gap = (cursor, min(b0, z))
                if gap[1] - gap[0] >= MIN_FREE and (best is None or gap[1] - gap[0] > best[1] - best[0]):
                    best = gap
                cursor = max(cursor, b1)
                if cursor >= z:
                    break
            if best is not None:
                return Free(i, date.strftime("%A"), date.strftime("%a"), part, *best)
    return None


def minutes_of(stop) -> int:
    return MINUTES.get(stop.kind, DEFAULT_MINUTES)


def fit_day(guide, free) -> tuple | None:
    """The guide's day whose first stops, one after the other, fill the free time with the most stops (the earlier day on a tie): (day number, their keys). Fewer than MIN_STOPS: None."""
    best = None
    for d in guide.days:
        cursor, keys = free.start, []
        for s in d.stops:
            if cursor + minutes_of(s) > free.end:
                break
            keys.append(s.key)
            cursor += minutes_of(s)
        if len(keys) >= MIN_STOPS and (best is None or len(keys) > len(best[1])):
            best = (d.n, keys)
    return best


def add(session, guide, keys, day=None, after=0) -> dict:
    """Put the stops `keys` ("d0s1"...) of `guide` into the plan, one by one: a plan added changes what is free for the next. With `day` (a trip day index) they go one after the other from the
    day's first free minute at or after `after`. Raises tripcal.CalendarError (a sentence fit to show) when the calendar refuses, for instance a family with no trip or a day it has no room on."""
    added, skipped, cursor = [], [], after
    for key in list(dict.fromkeys(keys))[:MAX_AT_ONCE]:
        stop = guide.find(key)
        if stop is None:
            continue
        title = stop.name[:40].strip()
        v = pv.view(session, lambda day=0, booked="": "")
        if day is not None and not 0 <= day < len(v.days):
            raise cal.CalendarError("That day is not in your trip.")
        if any(p.title == title for p in v.plans):
            skipped.append(stop.name)
            continue
        minutes = minutes_of(stop)
        if day is None:
            slot = pv.pick_slot(v, KIND[stop.kind], minutes, False)
        else:
            if v.sky[day].wet:
                raise cal.CalendarError(f"Rain is forecast for {dict(v.days)[day].strftime('%A')}, so nothing was added there.")
            start = pv.slot_in(v, day, minutes, cursor)
            slot = (day, start) if start is not None else None
        if slot is None:
            skipped.append(stop.name)
            continue
        d, start = slot
        got = planedit.add(session, day=d, start=start, end=start + minutes, title=title, kind=KIND[stop.kind])
        a = got["act"]
        try:
            cal.add_note(session, f"From {guide.poss} guide", act=a.id, guide=True)
        except cal.CalendarError:
            pass      # the plan is in; only its tag is missing
        cursor = a.end
        date = dict(v.days)[a.day]
        added.append({"key": key, "act": a.id, "day": a.day, "title": a.title, "when": f"{date.strftime('%a')} {date.day} · {cal.fmt_time(a.start)}", "undo": got["undo"], "start": a.start, "end": a.end})
    return {"added": added, "skipped": skipped}
