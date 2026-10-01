"""The phone trip view's model (F-054): what is on today, what is next, and one line per day.

Everything here is pure. The page is gitaway/pages/trip.py, which reads the family's trip the way the calendar does (gitaway.tripcal)
and passes it in. "Today" is `catalog.today()` and the minute of the day is `now_minute()`, both Los Angeles time and both pinned in
tests. Nothing here reads a confirmation number: the cards carry titles, times and places only.
"""

import re
from dataclasses import dataclass, replace
from datetime import datetime
from urllib.parse import quote_plus

from gitaway import catalog, tripcal as cal

TZ = catalog.TZ
DAY_TINTS = ("sun", "mint", "grape", "sky", "bubble")  # the calendar's day colours, in order
_PHONE = re.compile(r"iPhone|iPod|Android.+Mobile|Windows Phone|Mobile Safari|Opera Mini|BlackBerry", re.I)
_APPLE = re.compile(r"iPhone|iPad|iPod|Macintosh", re.I)
_LEG = re.compile(r"\b([A-Z]{3}) → ([A-Z]{3})\b")


def is_phone(ua) -> bool:
    """A phone's browser (not a tablet's): a plain /calendar sends these to /trip."""
    return bool(_PHONE.search(ua or "")) and "iPad" not in (ua or "")


def now_minute() -> int:
    """Minutes since midnight in Los Angeles. Tests pin this, like catalog.today."""
    n = datetime.now(TZ)
    return n.hour * 60 + n.minute


def maps_url(place, ua="") -> str:
    """Apple Maps on Apple devices, Google Maps elsewhere. `place` is a name or address; nothing else goes in the link."""
    q = quote_plus(place)
    return f"https://maps.apple.com/?q={q}" if _APPLE.search(ua or "") else f"https://www.google.com/maps/search/?api=1&query={q}"


def until(minutes) -> str:
    """'in 40 min', 'in 2 h 10 min', 'now'."""
    if minutes <= 0:
        return "now"
    h, m = divmod(minutes, 60)
    return f"in {m} min" if not h else f"in {h} h" if not m else f"in {h} h {m} min"


def span_label(s, e) -> str:
    """'5:00 – 7:30 PM', or '11:30 AM – 1:00 PM' across noon."""
    a, b = cal.fmt_time(s), cal.fmt_time(e)
    return f"{a[:-3]} – {b}" if a[-2:] == b[-2:] else f"{a} – {b}"


@dataclass(frozen=True)
class Item:
    id: str
    start: int
    end: int
    title: str
    kind: str       # flight | hotel | car | ride | offer | plan
    label: str      # "Flight", "Hotel", "Food" ...
    tint: str       # a token name: sky, sun, mint ...
    icon: str
    sub: str
    state: str = "later"   # done | now | next | later
    href: str = ""         # where tapping it goes
    place: str = ""        # what Directions looks up ("" for none)
    by: str = ""


@dataclass(frozen=True)
class Stay:
    title: str      # "Your hotel tonight" | "Checking out today"
    name: str
    where: str
    href: str = ""  # the trip details page, for an imported trip


@dataclass(frozen=True)
class DaySummary:
    index: int
    num: int
    dow: str
    tint: str
    head: str
    line: str
    state: str      # done | today | later


# ---- the phase of the trip ---------------------------------------------------------------------------------------------

def phase(t, today):
    """('before', days until it starts) | ('during', today's day index) | ('after', days since it ended)."""
    if today < t.depart:
        return "before", (t.depart - today).days
    if today > t.return_:
        return "after", (today - t.return_).days
    return "during", (today - t.depart).days


def starts_in(n) -> str:
    return "Trip starts tomorrow" if n == 1 else f"Trip starts in {n} days"


# ---- one day's timeline ------------------------------------------------------------------------------------------------

_ICON_KIND = {"plane": ("flight", "Flight", "sky"), "bed": ("hotel", "Hotel", "sun"), "car": ("car", "Car", "mint")}


def _place_of(block, hotel_place):
    """What Directions looks up for a booked block: the airport you leave from, the hotel (name and address), the car desk."""
    if block.icon == "plane":
        m = _LEG.search(block.title)
        return f"{m.group(1)} airport" if m else ""
    if block.title.startswith("Check in") and hotel_place:
        return hotel_place
    if block.icon == "car" and " · " in block.title:
        return block.title.rsplit(" · ", 1)[1]
    return ""


def timeline(day, blocks, acts, offers, destination, *, hotel_place="", ride_href=None, detail_href=None, now=None, past=False):
    """The items of day `day`, in time order, each marked done, now, next or later.

    `now` is the minute of the day when `day` is today, else None. `past` marks a whole day done (an earlier day, or after the trip).
    A ride offer is an invitation, not an event: it is never 'next'."""
    items = []
    for b in blocks:
        if b.day != day:
            continue
        if b.kind == "ride":
            items.append(Item(b.id, b.start, b.end, b.title, "ride", "Uber", "mint", "car", f"{span_label(b.start, b.end)} · simulated", href=ride_href(b) if ride_href else ""))
            continue
        kind, label, tint = _ICON_KIND.get(b.icon, ("hotel", "Booked", "sun"))
        where = b.tag.split(" · ")[-1] if b.tag else ""
        items.append(Item(b.id, b.at, b.end, b.title, kind, label, tint, b.icon or "calendar", f"{cal.fmt_time(b.at)} · booked" + (f" on {where}" if where else ""),
                          href=detail_href(b) if (b.tag and detail_href) else "", place=_place_of(b, hotel_place)))
    for o in offers:
        if o.day == day:
            items.append(Item(o.id, o.start, o.end, o.title, "offer", "Uber", "mint", "car", f"{cal.fmt_time(o.start)} · tap to schedule, simulated", href=ride_href(o) if ride_href else ""))
    for a in acts:
        if a.day == day:
            label, tint = cal.KINDS[a.kind]
            items.append(Item(a.id, a.start, a.end, a.title, "plan", label, tint, "", span_label(a.start, a.end) + (f" · added by {a.by}" if a.by else ""),
                              place=f"{a.title}, {destination}", by=a.by))
    items.sort(key=lambda x: (x.start, x.end, x.id))
    return _mark(items, now, past)


def _mark(items, now, past):
    out, claimed = [], False
    for x in items:
        if past:
            state = "done"
        elif now is None:
            state = "later"
        elif x.end <= now:
            state = "done"
        elif x.start <= now:
            state = "now"
        elif not claimed and x.kind != "offer":
            state, claimed = "next", True
        else:
            state = "later"
        out.append(replace(x, state=state))
    return out


@dataclass(frozen=True)
class Up:
    kicker: str                # "UP NEXT · IN 40 MIN"
    item: Item | None
    detail: str = ""
    uber: Item | None = None   # a ride still to schedule, else the one already set


def up_next(items, now, tomorrow_first=None) -> Up:
    """The dark card for today: what is happening now, else what is next, else 'all done' (with tomorrow's first item if there is one)."""
    here = next((x for x in items if x.state == "now" and x.kind not in ("ride", "offer")), None)
    nxt = next((x for x in items if x.state == "next"), None)
    pending = [x for x in items if x.state != "done"]
    uber = next((x for x in pending if x.kind == "offer"), None) or next((x for x in pending if x.kind == "ride"), None)
    if here:
        return Up(f"HAPPENING NOW · ENDS {until(here.end - now).upper()}", here, span_label(here.start, here.end), uber)
    if nxt:
        return Up(f"UP NEXT · {until(nxt.start - now).upper()}", nxt, span_label(nxt.start, nxt.end), uber)
    if tomorrow_first:
        return Up("ALL DONE TODAY", None, f"Tomorrow starts with {tomorrow_first.title} at {cal.fmt_time(tomorrow_first.start)}.")
    return Up("ALL DONE TODAY", None, "Nothing else is planned. Add something fun?")


# ---- one line per day, and the hotel card ----------------------------------------------------------------------------------

def day_summaries(dates, blocks, acts, today_index):
    last = len(dates) - 1
    out = []
    for i, d in enumerate(dates):
        planned = sorted([x for x in acts if x.day == i], key=lambda x: (x.start, x.id))
        booked = [b for b in blocks if b.day == i and b.kind != "ride"]
        flies_in = i == 0 and any(b.id.startswith("b-out") and b.icon == "plane" for b in booked)
        flies_home = i == last and any(b.id.startswith("b-back") and b.icon == "plane" for b in booked)
        checks_in = any(b.title.startswith("Check in") for b in booked)
        head = "Fly in · check in" if flies_in and checks_in else "Fly in" if flies_in else "Fly home" if flies_home else (planned[0].title if planned else "Wide open")
        titles = [b.title.split(" · ")[0] if b.icon == "plane" else b.title for b in booked] + [x.title for x in planned]
        line = " · ".join(titles[:4]) + (f" · and {len(titles) - 4} more" if len(titles) > 4 else "") if titles else "Nothing planned yet"
        state = "today" if i == today_index else "done" if today_index is not None and i < today_index else "later"
        out.append(DaySummary(i, d.day, d.strftime("%a").upper(), DAY_TINTS[i % 5], head, line, state))
    return out


def stay_card(b, dates, day) -> Stay | None:
    """The hotel for the night of `day`, or the one you check out of that day, else None."""
    last = len(dates) - 1
    if cal.is_imported(b):
        d = dates[day]
        plan = cal.plan_of(b)
        tonight = next((h for h in plan.hotels if h.check_in.date() <= d < h.check_out.date()), None)
        leaving = next((h for h in plan.hotels if h.check_out.date() == d), None)
        h = tonight or leaving
        return Stay("Your hotel tonight" if tonight else "Checking out today", h.name, h.address or "", "/trip/details") if h else None
    stay = cal.stay_of(b)
    return Stay("Checking out today" if day == last else "Your hotel tonight", stay.name, stay.headline) if stay else None


def hotel_place(b, dates, day) -> str:
    """The hotel's name and address, for Directions to the check in on `day`."""
    if cal.is_imported(b):
        d = dates[day]
        plan = cal.plan_of(b)
        h = next((h for h in plan.hotels if h.check_in.date() == d), None) or next((h for h in plan.hotels if h.check_in.date() <= d < h.check_out.date()), None)
        return (f"{h.name}, {h.address}" if h.address else h.name) if h else ""
    stay = cal.stay_of(b)
    return f"{stay.name}, {cal.trip_of(b).destination_name}" if stay else ""
