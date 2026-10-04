"""Talk to plan (F-024): a fully scripted voice demo. No audio is captured and nothing is understood; the page plays one
sentence word by word and this module turns it into draft plans on the traveler's own trip. Pure functions, plus two
thin session seams (preview and the apply/undo wrappers) over gitaway.tripcal so voice reuses the fork placement rules.

The mapping onto a trip's real days (trips have any dates and length, F-035):
  - "on Sunday" / "Monday" means the first Sunday / Monday inside the trip. A trip with none uses a fixed day instead
    (Sunday: day 3, Monday: day 2), and never a day past the trip's last.
  - "on our last day" is the trip's last day. "Tacos for dinner" is the one unclear bit: the question offers the first two
    evenings of the trip and the answer picks the night.
A plan the trip cannot hold (a day past the trip's end, or hours off the grid) is not dropped: the preview shows it as a clash
with the reason, and Apply skips it, exactly like a fork's plans. A plan that only overlaps a booking, a ride or another plan is
kept and ticked, with an "Overlaps" note (F-086).
"""

from dataclasses import dataclass

from gitaway import session as ses, tripcal as cal

SENTENCE = "Tacos for dinner, the observatory on Sunday at sunset, pool time Monday morning, and a beach walk on our last day."
SENTENCE_NO_STAY = "Tacos for dinner, the observatory on Sunday at sunset, and a beach walk on our last day."
NOTE_PREFIX = "Planned by voice: "
TACOS_START = 18 * 60 + 30
TACOS_LEN = 90
SUNDAY, MONDAY = 6, 0  # datetime.weekday()
KEYS = ("v0", "v1", "v2", "v3")


@dataclass(frozen=True)
class Option:
    day: int
    label: str


@dataclass(frozen=True)
class Question:
    text: str
    options: tuple

    def option(self, day):
        return next((o for o in self.options if o.day == day), None)


def sentence(has_stay=True):
    """The scripted sentence. With no stay booked there is no pool plan, so the pool clause is not said."""
    return SENTENCE if has_stay else SENTENCE_NO_STAY


def middle_days(dates):
    """Indexes of the full days between arrival and departure (not the arrival day, nor the check-out and flight-home day)."""
    return list(range(1, len(dates) - 1))


def day_for(dates, weekday, fallback):
    """Index of the first `weekday` in the trip, else the full middle day `fallback` ("first" or "last"); a trip of one or
    two days has no middle, so it uses day 3 / day 2 kept inside the trip."""
    found = next((i for i, d in enumerate(dates) if d.weekday() == weekday), None)
    if found is not None:
        return found
    mid = middle_days(dates)
    if mid:
        return mid[-1] if fallback == "last" else mid[0]
    return min(2 if fallback == "last" else 1, len(dates) - 1)


def sunday(dates):
    return day_for(dates, SUNDAY, "last")


def monday(dates):
    return day_for(dates, MONDAY, "first")


def question(dates):
    """The one quick question: which of the first two evenings of the trip is for tacos. The observatory's evening is not
    offered (tacos at 6:30 would sit inside sunset) unless it is the only evening there is."""
    nights = [i for i in range(min(2, len(dates))) if i != sunday(dates)] or [0]
    return Question("Tacos on which night?", tuple(Option(i, f"{dates[i].strftime('%a')} {dates[i].day}, {cal.fmt_time(TACOS_START)}") for i in nights))


def fallback_notes(dates):
    """{plan key: sentence} for each plan whose weekday the trip does not have, so a stand-in day is never a silent guess."""
    out = {}
    for key, weekday, name, pick in (("v1", SUNDAY, "Sunday", sunday), ("v2", MONDAY, "Monday", monday)):
        if not any(d.weekday() == weekday for d in dates):
            d = dates[pick(dates)]
            out[key] = f"No {name} on this trip, so {d.strftime('%a')} {d.day}"
    return out


def plans(dates, stay_name, night=None, home=True):
    """The draft plans the sentence asks for, on the days of `dates`. Without a valid `night` the tacos wait for the answer.
    `home` is whether the booking has a flight home (the beach walk says so only then)."""
    out = []
    if question(dates).option(night):
        out.append(cal.Plan("v0", night, TACOS_START, TACOS_START + TACOS_LEN, "Tacos at Mariscos La Ola", "food"))
    out.append(cal.Plan("v1", sunday(dates), 17 * 60, 19 * 60 + 30, "Griffith Observatory at sunset", "culture"))
    if stay_name:  # pool time needs a hotel: staying with friends (no stay booked) leaves it out
        out.append(cal.Plan("v2", monday(dates), 9 * 60, 11 * 60 + 30, cal._short(f"Pool time at {stay_name}"), "fun"))
    out += [
        cal.Plan("v3", len(dates) - 1, 9 * 60, 10 * 60 + 30, "Beach walk before the flight home" if home else "Beach walk", "outdoors"),
    ]
    return out


_SHORT = {"v0": "Tacos", "v1": "Observatory", "v2": "Pool time", "v3": "Beach walk"}


def note_text(chosen, dates):
    """The trip note that logs an apply, e.g. "Planned by voice: Tacos Fri, Observatory Sun". Always fits a note."""
    out = NOTE_PREFIX
    for i, p in enumerate(chosen):
        piece = f"{_SHORT.get(p.key, p.title)} {dates[min(p.day, len(dates) - 1)].strftime('%a')}"
        nxt = out + (", " if i else "") + piece
        if len(nxt) > cal.MAX_NOTE:
            break
        out = nxt
    return out


# ---- the session seams ---------------------------------------------------------------------------------------------

def setup(session, demo):
    """(dates, stay name or None with no stay) of the booked trip. Raises CalendarError when signed out or nothing is booked."""
    if not ses.current_traveler(session):
        raise cal.CalendarError("Sign in to use the trip calendar.")
    b = ses.booking(session)
    if not b:
        raise cal.CalendarError("Book a trip first, then plan the gaps.")
    return cal.days(cal.trip(demo, b)), (cal.stay_of(b).name if cal.stay_of(b) else None)


def plans_for(session, night=None, demo=""):
    dates, stay = setup(session, demo)
    b = ses.booking(session)
    home = any(x.id == "b-back" for x in cal.booked_blocks(b, cal.trip(demo, b)))
    return plans(dates, stay, night, home)


def preview(session, night=None, demo=""):
    """The Placements of the voice plans (those the answer so far allows) around the bookings and everyone's items."""
    return cal.preview_plans(session, plans_for(session, night, demo), demo)


def apply(session, night, picks, demo=""):
    """Add the picked voice plans and the trip note. Returns (activities, note). A full cookie raises CalendarError."""
    dates, _ = setup(session, demo)
    return cal.apply_plans(session, plans_for(session, night, demo), picks, note=lambda chosen: note_text(chosen, dates), demo=demo)


def undo(session, night, ids, note_id=None, demo=""):
    """Take back what one apply added (only plans this script makes, and its note). Returns how many plans were removed."""
    return cal.remove_plans(session, plans_for(session, night, demo), ids, note_id=note_id, note_prefix=NOTE_PREFIX, demo=demo)
