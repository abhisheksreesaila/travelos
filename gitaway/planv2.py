"""What the planning page knows (F-252, D-630..): plain functions, no framework. The page is docs/design/planning-v2/index.html on the app's own models.

    view(session, curl) -> View          the open trip as the calendar draws it: its days with their sky, the booked blocks (locked), the family's plans, who is in, what changed
    lanes(events) -> (shown, more) overlapping events side by side, at most two across; what does not fit is counted for a "+N" chip
    pick_slot(v, kind, minutes, indoor) -> (day, start) | None    a free slot for a suggestion dropped in with "+": a dry day first, the quietest day first, never over anything
    span(a, b)                     "8:05 to 9:40 AM" for two minutes-after-midnight

Nothing here is invented. Bookings and plans are tripcal's (the family's database); the days' sky is weather.py's (a forecast, or the place's typical weather, labelled), and only
the showcase's own sample trip wears sample weather (dayweather.is_sample); a rain nudge needs a real forecast day with rain or snow; the suggestions and the "went" lists are the showcase's
made-up samples (v2rail.SAMPLE), which off the showcase are simply not offered. Plans are written by gitaway/planedit.py (the calendar's rules, the family's thread cards).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from gitaway import catalog, dayweather, familythread, interests, members, placefacts, session as ses, showcase, tripcal as cal, tripday as td, v2rail, weather

BOOKED_KIND = {"plane": "flight", "bed": "stay", "car": "car", "ticket": "tix"}        # a booked block's icon -> its colour's name
PLAN_KINDS = (("food", "Food"), ("fun", "Fun"), ("outdoors", "Outdoors"), ("culture", "Culture"), ("travel", "Travel"))      # tripcal.KINDS, in the order the chips show them
LEGEND = (("flight", "Flight"), ("stay", "Stay"), *PLAN_KINDS)
DURATIONS = (30, 60, 90, 120, 180)
STEP = cal.SNAP
SHOWN_ACROSS = 2
WET = ("rain", "snow")
MAX_CHANGES = 6
FOOD_TIMES = (12 * 60, 18 * 60 + 30, 13 * 60, 19 * 60, 8 * 60 + 30)
OTHER_TIMES = (10 * 60, 14 * 60, 11 * 60, 15 * 60 + 30, 9 * 60, 16 * 60)


@dataclass(frozen=True)
class Wx:
    hi: int | None
    lo: int | None
    word: str
    cond: str            # sun | cloud | rain | snow | wind, or "" when nothing is known
    typical: bool        # typical weather, not a forecast yet: the page says so
    sample: bool         # the showcase's own sample trip's weather
    label: str = ""      # what the weather is, in words, for a title: "Forecast · Rain" / "Typical · not a forecast yet"

    @property
    def wet(self) -> bool:
        """A real forecast of rain or snow (typical days and sample days never nudge)."""
        return self.cond in WET and not self.typical and not self.sample


@dataclass(frozen=True)
class Ev:
    id: str
    day: int
    start: int
    end: int
    title: str
    kind: str            # flight | stay | car | tix | food | fun | outdoors | culture | travel
    locked: bool = False
    icon: str = ""
    at: int = 0          # the minute to say (a block drawn earlier keeps its true start)
    by: str = ""         # the first name of who added it
    href: str = ""       # a booked block opens its booking here
    tag: str = ""        # "From Maya's guide": a plan dropped in from a guide (F-263) carries the guide's name as its note

    @property
    def when(self) -> str:
        return span(self.at or self.start, self.end)


@dataclass(frozen=True)
class Person:
    id: str
    name: str
    initials: str
    role: str
    slot: int            # 0..4: which of the five fills the avatar wears
    me: bool = False


@dataclass(frozen=True)
class Change:
    who: str
    text: str
    at: str


@dataclass
class View:
    title: str
    place: str
    dates: str
    nights: int
    party: str
    big: str             # "31" of "31 days to go"
    small: str           # "days to go"
    days: list           # [(index, date)]
    sky: list            # a Wx per day
    sky_notes: list      # [(text, link)]: what the weather must say (MET's credit, the typical-weather line)
    booked: list         # [Ev], locked
    plans: list          # [Ev]
    gs: int              # the grid's first minute
    ge: int              # its last
    open_day: int        # the day to open on: today during the trip, else the first
    people: list
    pending: list        # an admin's waiting invites: [{"email", "role", "token"}]
    changes: list
    interests: tuple
    role: str
    windows: dict = field(default_factory=dict)       # day -> (lo, hi): where a plan may go (cal.day_window)

    @property
    def events(self) -> list:
        return [*self.booked, *self.plans]

    def on(self, day) -> list:
        return sorted((e for e in self.events if e.day == day), key=lambda e: (e.start, -(e.end - e.start), e.id))


def span(a, b) -> str:
    """"8:05 to 9:40 AM", or "11:30 AM to 1:00 PM" across noon."""
    x, y = cal.fmt_time(a), cal.fmt_time(b)
    if x[-2:] == y[-2:]:
        x = x[:-3]
    return f"{x}–{y}"


def _day_word(d) -> str:
    return f"{d.strftime('%a')} {d.day}"


def sky(t) -> tuple:
    """([Wx per trip day], [(text, link)]) for trip `t`: the sample trip's sample weather, else a forecast or typical weather (a day nothing is known about has no cond)."""
    n = (t.return_ - t.depart).days + 1
    none = Wx(None, None, "", "", False, False)
    if dayweather.is_sample(t):
        days = [Wx(d.hi, d.lo, d.word, {"sun": "sun", "wind": "wind"}.get(d.kind, "cloud"), False, True, "Sample weather") for d in dayweather.days(t)]
        return days, []
    tw = weather.trip_weather(t)
    out = []
    for d in tw.days:
        if d is None:
            out.append(none)
        elif d.kind == weather.NORMAL:
            out.append(Wx(d.high_f, d.low_f, "Typical", d.condition, True, False, d.label or "Typical · not a forecast yet"))
        else:
            out.append(Wx(d.high_f, d.low_f, d.word, d.condition, False, False, "Forecast · MET Norway"))
    out += [none] * (n - len(out))
    return out[:n], weather.notes(tw)


def _ev(a, people, tags) -> Ev:
    who = people.get(a.by_id)
    return Ev(a.id, a.day, a.start, a.end, a.title, a.kind, by=(who.name.split() or [""])[0] if who else (a.by or ""), tag=tags.get(a.id, ""))


def _ago(iso) -> str:
    """"Just now", "5 min ago", "2 h ago", "3 days ago" for a stored moment."""
    try:
        then = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    secs = (datetime.now(timezone.utc) - (then if then.tzinfo else then.replace(tzinfo=timezone.utc))).total_seconds()
    if secs < 90:
        return "Just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} h ago"
    return f"{int(secs // 86400)} days ago"


def _countdown(t, session) -> tuple:
    today = catalog.today_in(ses.trip_zone(session))
    ph, n = td.phase(t, today)
    total = (t.return_ - t.depart).days + 1
    if ph == "before":
        return str(n), "day to go" if n == 1 else "days to go"
    if ph == "during":
        return str(n + 1), f"day of {total}"
    return "", "back home"


def view(session, curl) -> View:
    """Everything the page draws for the open trip. `curl(day=, booked=)` is the booking sheet's address (a locked block opens its booking there)."""
    b = ses.booking(session)
    t = cal.trip("", b)
    dates = cal.days(t)
    blocks = [x for x in cal.booked_blocks(b, t) if x.kind != "ride"]
    acts = cal.activities(session)
    tid = session.get("tenant_id")
    me = (session.get("user_id") or "")
    crew = members.members(tid) if tid else []
    who = {m["user_id"]: ses.Friend(m["name"], m["initials"], m["color"]) for m in crew}
    people = [Person(m["user_id"], m["name"], m["initials"], m["role"], i % 5, m["user_id"] == me) for i, m in enumerate(crew)]
    role = next((p.role for p in people if p.me), "viewer")
    days_sky, notes = sky(t)
    gs, ge = cal.grid_start(blocks), cal.grid_end(blocks)
    booked = [Ev(x.id, x.day, x.start, x.end, x.title, BOOKED_KIND.get(x.icon, "tix"), True, x.icon, x.at, href=curl(day=x.day, booked=x.id)) for x in blocks]
    tags = {n.act: n.text for n in cal.notes(session) if n.act and n.guide}
    plans = [_ev(a, who, tags) for a in acts]
    gs = min([gs, *(e.start // 60 * 60 for e in plans)])
    ge = max([ge, *(-(-e.end // 60) * 60 for e in plans)])
    start, end = dates[0], dates[-1]
    nights = (end - start).days
    big, small = _countdown(t, session)
    pending = []
    if role == "admin" and tid:
        pending = [{"email": i["email"], "role": i["role"], "token": i["token"]} for i in members.pending_invites(tid)]
    changes = [Change(c["name"], c["text"], _ago(c["at"])) for c in reversed(familythread.items(session, limit=40)) if c["kind"] == "change"][:MAX_CHANGES]
    today = catalog.today_in(ses.trip_zone(session))
    ph, n = td.phase(t, today)
    return View(t.title, t.destination_name, f"{start.strftime('%a, %b')} {start.day} → {end.strftime('%a, %b')} {end.day}", nights,
                _party(t), big, small, list(enumerate(dates)), days_sky, notes, booked, plans, gs, ge, n if ph == "during" else 0, people, pending, changes, interests.get(session), role,
                {i: cal.day_window(blocks, i) for i in range(len(dates))})


def _party(t) -> str:
    from gitaway import cockpit
    return cockpit.party_text(t)


# ---- overlaps -----------------------------------------------------------------------------------------------------------------

def lanes(events) -> tuple:
    """Events of one day side by side. -> (shown, more): `shown` is [(event, lane, across)] for what is drawn (at most SHOWN_ACROSS across in a run of overlapping events; `across` is the
    run's widest point, capped), `more` is [(first hidden event's start, [hidden events])], one "+N" chip for each run that has any. Booked blocks take a lane before plans do."""
    runs, cur, reach = [], [], -1
    for e in sorted(events, key=lambda e: (e.start, -(e.end - e.start), e.id)):
        if cur and e.start >= reach:
            runs.append(cur)
            cur, reach = [], -1
        cur.append(e)
        reach = max(reach, e.end)
    if cur:
        runs.append(cur)
    shown, more = [], []
    for run in runs:
        lane_of = {}
        for e in sorted(run, key=lambda e: (not e.locked, e.start, -(e.end - e.start), e.id)):
            taken = {lane_of[o] for o in lane_of if o.start < e.end and e.start < o.end}
            lane_of[e] = next(i for i in range(len(run)) if i not in taken)
        across = min(max(lane_of.values()) + 1, SHOWN_ACROSS)
        hidden = sorted((e for e in run if lane_of[e] >= SHOWN_ACROSS), key=lambda e: (e.start, e.id))
        shown += [(e, lane_of[e], across) for e in run if lane_of[e] < SHOWN_ACROSS]
        if hidden:
            more.append((hidden[0].start, hidden))
    return shown, more


# ---- a suggestion dropped in ---------------------------------------------------------------------------------------------------

def _busy(v, day) -> list:
    return [(e.start, e.end) for e in v.events if e.day == day]


def pick_slot(v, kind, minutes, indoor=False) -> tuple | None:
    """Where the "+" puts a suggestion of `minutes`: a day with no rain or snow in a real forecast (any day when it is indoors, or when every day is wet), the day with the fewest plans
    first, at the hour that suits it (meals at noon or half past six, the rest mid morning or mid afternoon), in the day's window (nothing before the flight lands or too close to
    the one home), and never over a booking or another plan. None when nothing is free."""
    n = len(v.days)
    count = {i: sum(1 for e in v.plans if e.day == i) for i in range(n)}
    order = sorted(range(n), key=lambda i: (count[i], i))
    dry = [i for i in order if not v.sky[i].wet]
    wet = [i for i in order if v.sky[i].wet]
    tried = (order,) if indoor else (dry, wet)
    prefer = FOOD_TIMES if kind == "food" else OTHER_TIMES
    for days in tried:
        for i in days:
            lo, hi = v.windows[i]
            busy = _busy(v, i)
            for s in (*prefer, *range(lo // STEP * STEP, hi, 30)):
                if lo <= s and s + minutes <= hi and s % STEP == 0 and not any(s < e2 and b < s + minutes for b, e2 in busy):
                    return i, s
    return None


def slot_in(v, day, minutes, after=0) -> int | None:
    """The first start on `day` at or after minute `after` where `minutes` fit in the day's window, on the grid's step and over nothing (F-263: a guide's morning dropped in one stop after the
    other). None when the day has no room."""
    lo, hi = v.windows[day]
    busy = _busy(v, day)
    for s in range(max(lo, after) // STEP * STEP + (STEP if max(lo, after) % STEP else 0), hi, STEP):
        if s + minutes <= hi and not any(s < e2 and b < s + minutes for b, e2 in busy):
            return s
    return None


# ---- what the rail offers --------------------------------------------------------------------------------------------------------

def suggestions(v) -> list:
    """The places the quick add and the rail's "Fits you" offer: [{"id", "title", "sub", "kind", "minutes", "indoor", "fit": [interest keys]}]. Only the showcase has any (the made-up places of
    v2rail.SAMPLE, labelled Sample where they show); off the showcase there is no sourced list of places, so there are none."""
    got = v2rail.sample(v.place) if showcase.on() else None
    if not got:
        return []
    out = []
    for i, (name, what, mins, fit) in enumerate(got["food"]):
        out.append({"id": f"f{i}", "title": name, "sub": f"{what} · {mins} min away", "kind": "food", "minutes": 90, "indoor": True, "fit": list(fit)})
    for i, (name, when) in enumerate(got["trend"]):
        out.append({"id": f"t{i}", "title": name, "sub": when, "kind": "outdoors", "minutes": 120, "indoor": False, "fit": []})
    return out


def fits(v, sugg) -> list:
    """The suggestions that fit what the family said it likes (the first few when it said nothing or nothing fits)."""
    food = [s for s in sugg if s["kind"] == "food"]
    want = set(v.interests)
    match = [s for s in food if want & set(s["fit"])]
    return (match or food)[:3]


def facts(v) -> tuple:
    return placefacts.facts(v.place)


def rain(v) -> tuple | None:
    """(day index, Wx) of the first real forecast of rain or snow, else None."""
    return next(((i, w) for i, w in enumerate(v.sky) if w.wet), None)


def day_words(d) -> str:
    return _day_word(d)
