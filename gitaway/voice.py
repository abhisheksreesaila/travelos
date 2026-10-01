"""Talk to plan (F-024): a fully scripted voice demo. No audio is captured and nothing is understood; the page plays one
sentence word by word and this module turns it into draft plans on the traveler's own trip. Pure functions, plus two
thin session seams (preview and the apply/undo wrappers) over gitaway.tripcal so voice reuses the fork placement rules.

The mapping onto a trip's real days (trips have any dates and length, F-035):
  - "on Sunday" / "Monday" means the first Sunday / Monday inside the trip. A trip with none uses a fixed day instead
    (Sunday: day 3, Monday: day 2), and never a day past the trip's last.
  - "on our last day" is the trip's last day. "Tacos for dinner" is the one unclear bit: the question offers the first two
    evenings of the trip and the answer picks the night.
A plan the trip cannot hold (it would start before you land, or end too close to your flight home) is not dropped: the
preview shows it as a clash with the reason, and Apply skips it, exactly like a fork's plans.
"""

from dataclasses import dataclass

from gitaway import catalog, session as ses, tripcal as cal

SENTENCE = "Tacos for dinner, the observatory on Sunday at sunset, pool time Monday morning, and a beach walk on our last day."
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


def question(dates):
    """The one quick question: which of the first two evenings of the trip is for tacos."""
    return Question("Tacos on which night?", tuple(Option(i, f"{d.strftime('%a')} {d.day}, {cal.fmt_time(TACOS_START)}") for i, d in enumerate(dates[:2])))


def day_for(dates, weekday, fallback):
    """Index of the first `weekday` in the trip, else day `fallback` (0 based) kept inside the trip."""
    found = next((i for i, d in enumerate(dates) if d.weekday() == weekday), None)
    return found if found is not None else min(fallback, len(dates) - 1)


def plans(dates, stay_name, night=None):
    """The draft plans the sentence asks for, on the days of `dates`. Without a valid `night` the tacos wait for the answer."""
    out = []
    if question(dates).option(night):
        out.append(cal.Plan("v0", night, TACOS_START, TACOS_START + TACOS_LEN, "Tacos at Mariscos La Ola", "food"))
    out += [
        cal.Plan("v1", day_for(dates, SUNDAY, 2), 17 * 60, 19 * 60 + 30, "Griffith Observatory at sunset", "culture"),
        cal.Plan("v2", day_for(dates, MONDAY, 1), 9 * 60, 11 * 60 + 30, cal._short(f"Pool time at {stay_name}"), "fun"),
        cal.Plan("v3", len(dates) - 1, 9 * 60, 10 * 60 + 30, "Beach walk before the flight home", "outdoors"),
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
    """(dates, stay name) of the booked trip. Raises CalendarError when signed out or nothing is booked."""
    if not ses.current_traveler(session):
        raise cal.CalendarError("Sign in to use the trip calendar.")
    b = ses.booking(session)
    if not b:
        raise cal.CalendarError("Book a trip first, then plan the gaps.")
    return cal.days(cal.trip(demo, b)), catalog.offer(b["stay"]).name


def plans_for(session, night=None, demo=""):
    dates, stay = setup(session, demo)
    return plans(dates, stay, night)


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
