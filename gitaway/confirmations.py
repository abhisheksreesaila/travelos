"""Paste-back (F-198): read a pasted booking confirmation from Booking.com, Airbnb, Vrbo, GetYourGuide, Klook or a car-rental company, and put it in the trip.

    read(text)              the Booking one confirmation holds (partner, a stay / car / ticket, where, who), or None when the text is not one we read
    plan_for(booking, base) the trip Plan it makes: `base` (the open imported trip) with this booking added when its dates fall inside it, else a new trip of its own
    convert(text, base)     Converted(yaml, warnings, partner): the trip template text the import page reads with the normal reader, or None

An Expedia itinerary keeps its own reader (gitaway/expedia.py). Like it, nothing here saves anything, and only chosen fields are copied: a name, an address or meeting place,
the dates and times, the confirmation number, the car type, the party. Prices, PINs, card digits and the partner's own phone numbers are never read. Each booking records its
partner (`booked_on`), so the trip shows "Booked on Airbnb" and the button to change or cancel it there. The layouts read are labels followed by values, on the same line after
a colon or on the next line, which is how these emails come out when their text is copied; the samples are in tests/confirmation_samples.py.
"""

import re
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta

from gitaway import expedia, tripimport as ti

MAX_TEXT = 60_000
CHILD_AGE = expedia.CHILD_AGE
CAR_BRANDS = ("Enterprise", "Hertz", "Avis", "Budget", "National", "Alamo", "Sixt", "Thrifty", "Dollar")
_MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_US_DATE = re.compile(rf"(?:\b(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+)?\b{_MON}\s+(\d{{1,2}}),?\s+(\d{{4}})", re.I)
_EU_DATE = re.compile(rf"\b(\d{{1,2}})\s+{_MON}\s+(\d{{4}})", re.I)
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s?m\b\.?", re.I)
_ADDRESS = re.compile(r",\s*([A-Z]{2}),?\s+\d{5}")
_COUNTRY = re.compile(r",?\s*(United States of America|United States|USA)\s*$", re.I)
_AIRPORT = re.compile(r"\(([A-Z]{3})\)")


@dataclass(frozen=True)
class Booking:
    partner: str          # what the trip says it was booked on: "Booking.com"
    kind: str             # stay | car | ticket
    item: object          # tripimport.Lodging | Rental | Ticket, with `booked_on` set
    destination: str      # "South Lake Tahoe, CA"
    adults: int = 0       # 0: the confirmation does not say
    kids: tuple = ()      # each child's age, or None where it is not given
    warnings: tuple = ()

    @property
    def start(self) -> date:
        return (self.item.check_in if self.kind == "stay" else self.item.pickup if self.kind == "car" else self.item.start).date()

    @property
    def end(self) -> date:
        return (self.item.check_out if self.kind == "stay" else self.item.dropoff if self.kind == "car" else self.item.end).date()


@dataclass(frozen=True)
class Converted:
    yaml: str
    warnings: tuple
    partner: str
    merged: bool          # added to the open trip, rather than a trip of its own


# ---- small readers ------------------------------------------------------------------------------------------------------

def _lines(text):
    return [" ".join(line.split()) for line in (text or "")[:MAX_TEXT].replace("\r", "\n").split("\n") if line.strip()]


def _date(line):
    for pattern, order in ((_US_DATE, "mdy"), (_EU_DATE, "dmy"), (_ISO_DATE, "ymd")):
        m = pattern.search(line or "")
        if not m:
            continue
        a, b, c = m.groups()
        try:
            if order == "mdy":
                return date(int(c), _MONTHS[a[:3].lower()], int(b))
            if order == "dmy":
                return date(int(c), _MONTHS[b[:3].lower()], int(a))
            return date(int(a), int(b), int(c))
        except ValueError:
            return None
    return None


def _time(line):
    m = _TIME.search(line or "")
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    if not (1 <= hour <= 12 and minute < 60):
        return None
    return time((hour % 12) + (12 if m.group(3).lower() == "p" else 0), minute)


def _find(lines, *labels):
    """(index, the text after the label) of the first line that starts with one of `labels` (any case), or (None, "")."""
    for i, line in enumerate(lines):
        low = line.lower()
        for label in labels:
            if low.startswith(label.lower()) and (len(low) == len(label) or not low[len(label)].isalpha()):
                return i, line[len(label):].lstrip(" :#-–").strip()
    return None, ""


def _value(lines, *labels, limit=80):
    """The value of a label: the rest of its line, else the next line."""
    i, rest = _find(lines, *labels)
    if i is None:
        return ""
    return (rest or (lines[i + 1] if i + 1 < len(lines) else ""))[:limit].strip()


def _when(lines, labels, default):
    """The date and time a label gives, read from its own line and the two after it; the time is `default` when none is given."""
    i, rest = _find(lines, *labels)
    if i is None:
        return None
    near = [rest] + lines[i + 1:i + 3]
    day = next((d for d in map(_date, near) if d), None)
    if not day:
        return None
    clock = next((t for t in map(_time, near) if t), None)
    return datetime.combine(day, clock or default)


def _address(text):
    return _COUNTRY.sub("", text).strip(" ,")[:120]


def _town(address):
    """"South Lake Tahoe, CA" from "45 Pine Ridge Rd, South Lake Tahoe, CA 96150"."""
    m = _ADDRESS.search(address or "")
    if not m:
        return ""
    head = address[:m.start()].split(",")
    return f"{head[-1].strip()}, {m.group(1)}" if head and head[-1].strip() else ""


def _party(text):
    """(adults, kids' ages with None where not given) from "2 adults, 2 children (8 and 11 years old)" or "2 x Adult, 2 x Child"."""
    a = re.search(r"(\d+)\s*(?:x\s*)?adults?\b", text, re.I)
    k = re.search(r"(\d+)\s*(?:x\s*)?(?:child(?:ren)?|kids?)\b(?:\s*\(([^)]*)\))?", text, re.I)
    adults = int(a.group(1)) if a else 0
    n = int(k.group(1)) if k else 0
    ages = [int(x) for x in re.findall(r"\b(\d{1,2})\b", k.group(2) or "")] if k and k.group(2) and "year" in (k.group(2) or "").lower() else []
    ages = ages if len(ages) == n and all(a <= 17 for a in ages) else [None] * n
    return min(adults, 12), tuple(ages[:8])


def _conf(text):
    return re.sub(r"[^A-Za-z0-9.\-]", "", text or "")[:30]


# ---- one reader per partner ----------------------------------------------------------------------------------------------

def _stay(partner, lines, name, address, conf, party, cin_labels, cout_labels):
    warnings = []
    cin, cout = _when(lines, cin_labels, time(15)), _when(lines, cout_labels, time(11))
    if not (name and cin and cout and cout > cin):
        return None
    if not address:
        warnings.append(f"{partner} gave no street address; add it under the stay.")
    adults, kids = _party(party)
    item = ti.Lodging(name[:80], address or name[:120], cin, cout, conf, "", 1, "", partner)
    return Booking(partner, "stay", item, _town(address), adults, kids, tuple(warnings))


def _booking_com(lines):
    ai = next((i for i, l in enumerate(lines) if _ADDRESS.search(l)), None)
    name = lines[ai - 1] if ai else ""
    return _stay("Booking.com", lines, name, _address(lines[ai]) if ai is not None else "", _conf(_value(lines, "Booking number", "Confirmation number")),
                 _value(lines, "Guests", limit=120), ("Check-in",), ("Check-out",))


def _airbnb(lines):
    i, rest = _find(lines, "You're going to", "You’re going to")
    name = lines[i + 1] if i is not None and i + 1 < len(lines) else ""
    return _stay("Airbnb", lines, name, _address(_value(lines, "Address", limit=160)), _conf(_value(lines, "Confirmation code")), _value(lines, "Guests", limit=120),
                 ("Check-in",), ("Checkout", "Check-out"))


def _vrbo(lines):
    ai, address = _find(lines, "Property address", "Address")
    name = lines[ai - 1] if ai else ""
    if name.lower().startswith(("reservation id", "your booking")):
        name = ""
    return _stay("Vrbo", lines, name, _address(address), _conf(_value(lines, "Reservation ID", "Confirmation number")), _value(lines, "Guests", limit=120),
                 ("Check-in",), ("Checkout", "Check-out"))


def _ticket(partner, lines, name, day_labels, place, conf, party):
    day = _date(_value(lines, *day_labels))
    if not (name and day):
        return None
    start = datetime.combine(day, _time(_value(lines, "Time", "Start time", "Starting time")) or time(9))
    hours = re.search(r"(\d+(?:\.\d+)?)\s*hours?", _value(lines, "Duration"), re.I)
    end = start + (timedelta(hours=float(hours.group(1))) if hours and 0 < float(hours.group(1)) <= 12 else ti.TICKET_LEN)
    adults, kids = _party(party)
    item = ti.Ticket(name[:80], _address(place), start, end if end.date() == start.date() else datetime.combine(start.date(), time(23, 59)), conf, partner)
    return Booking(partner, "ticket", item, _town(place) or _address(place), adults, kids)


def _getyourguide(lines):
    i, _ = _find(lines, "Your booking is confirmed", "Booking confirmed")
    name = lines[i + 1] if i is not None and i + 1 < len(lines) else ""
    return _ticket("GetYourGuide", lines, name, ("Date",), _value(lines, "Meeting point", "Location", "Address", limit=160), _conf(_value(lines, "Booking reference", "Reference number")),
                   _value(lines, "Participants", limit=120))


def _klook(lines):
    i, _ = _find(lines, "Booking reference ID", "Booking reference", "Booking ID")
    name = lines[i + 1] if i is not None and i + 1 < len(lines) else ""
    return _ticket("Klook", lines, name, ("Participation date", "Date"), _value(lines, "Location", "Address", "Meeting point", limit=160),
                   _conf(_value(lines, "Booking reference ID", "Booking reference", "Booking ID")), _value(lines, "Units", "Participants", "Quantity", limit=120))


def _car(lines, brand):
    pick_i, pick_place = _find(lines, "Pick-up", "Pickup", "Pick up")
    drop_i, drop_place = _find(lines, "Return", "Drop-off", "Dropoff", "Drop off")
    pick, drop = _when(lines, ("Pick-up", "Pickup", "Pick up"), time(12)), _when(lines, ("Return", "Drop-off", "Dropoff", "Drop off"), time(12))
    if not (pick and drop and drop > pick):
        return None
    where = lambda text: (m.group(1) if (m := _AIRPORT.search(text)) else re.split(r"\s+(?:on\s+)?(?:mon|tue|wed|thu|fri|sat|sun)", text, flags=re.I)[0])[:60].strip(" ,@")
    pp, dp = where(pick_place) or "Pick-up", where(drop_place) or where(pick_place) or "Drop-off"
    vehicle = re.split(r"\s+(?:-|–)\s+|\s+or similar", _value(lines, "Vehicle", "Car type", "Car"), maxsplit=1)[0][:40]
    item = ti.Rental(brand, pp, pick, dp, drop, _conf(_value(lines, "Confirmation Number", "Confirmation", "Reservation Number")), vehicle, "", brand)
    dest = re.sub(r"\s*\([A-Z]{3}\)", "", pick_place).strip()[:60]
    return Booking(brand, "car", item, dest, warnings=("Check the trip's destination: a car confirmation names only where you pick it up.",))


def read(text) -> Booking | None:
    """The one booking a pasted confirmation holds, or None. Expedia itineraries are not read here (gitaway/expedia.py)."""
    if not isinstance(text, str) or not text.strip() or expedia.looks_like_expedia(text):
        return None
    lines = _lines(text)
    head = " ".join(lines[:4]).lower()
    body = " ".join(lines).lower()
    if "booking.com" in head:
        return _booking_com(lines)
    if "airbnb" in head:
        return _airbnb(lines)
    if "vrbo" in head or "homeaway" in head:
        return _vrbo(lines)
    if "getyourguide" in head:
        return _getyourguide(lines)
    if "klook" in head:
        return _klook(lines)
    brand = next((b for b in CAR_BRANDS if re.search(rf"\b{b.lower()}\b", head)), None)
    if brand and ("pick-up" in body or "pickup" in body or "pick up" in body):
        return _car(lines, brand)
    return None


def partner_of(text) -> str:
    """"Expedia", "Airbnb", ... for a pasted confirmation GitAway can read, else ""."""
    if isinstance(text, str) and expedia.looks_like_expedia(text):
        return "Expedia"
    b = read(text)
    return b.partner if b else ""


# ---- into a trip -----------------------------------------------------------------------------------------------------------

def _overlaps(a, b) -> bool:
    return a.check_in < b.check_out and b.check_in < a.check_out


def _merged(base, b):
    """`base` with booking `b` in it, and what that changed, in words."""
    notes = []
    if b.kind == "stay":
        gone = [h for h in base.hotels if h.name.casefold() == b.item.name.casefold() or _overlaps(h, b.item)]
        notes += [f"It replaces {h.name} on the same nights." for h in gone if h.name.casefold() != b.item.name.casefold()]
        return replace(base, hotels=tuple(sorted([h for h in base.hotels if h not in gone] + [b.item], key=lambda h: h.check_in))), notes
    if b.kind == "car":
        if base.rental and base.rental.company != b.item.company:
            notes.append(f"It replaces the {base.rental.company} car.")
        return replace(base, rental=b.item), notes
    same = [t for t in base.tickets if t.name.casefold() == b.item.name.casefold() and t.start == b.item.start]
    return replace(base, tickets=tuple(sorted([t for t in base.tickets if t not in same] + [b.item], key=lambda t: t.start))), notes


def _travelers(b):
    adults = max(b.adults, 1)
    people = [ti.Traveler(f"Adult {i + 1}") for i in range(adults)]
    people += [ti.Traveler(f"Child {i + 1}", "", age if age is not None else CHILD_AGE) for i, age in enumerate(b.kids)]
    return tuple(people)


def plan_for(b: Booking, base=None) -> tuple:
    """(Plan, warnings, merged). The booking goes into `base` when its dates fall inside it (the family pasted a confirmation for the trip they have open), else it is a trip of its own."""
    warnings = list(b.warnings)
    if base and base.start <= b.start and b.end <= base.end:
        plan, notes = _merged(base, b)
        return plan, warnings + [f"Added to {base.title}."] + notes, True
    if any(age is None for age in b.kids):
        warnings.append(f"{b.partner} doesn't give children's ages, so each child is set to {CHILD_AGE}; change the ages.")
    where = b.destination or b.item.name
    city = where.split(",")[0].strip() or "My"
    plan = ti.Plan(f"{city} trip"[:60], where[:60], b.start, b.end, b.partner, "", _travelers(b),
                   hotels=(b.item,) if b.kind == "stay" else (), rental=b.item if b.kind == "car" else None, tickets=(b.item,) if b.kind == "ticket" else ())
    return plan, warnings + ["Rename the travelers, then check each line."], False


def convert(text, base=None) -> Converted | None:
    b = read(text)
    if b is None:
        return None
    plan, warnings, merged = plan_for(b, base)
    return Converted(ti.to_yaml(plan, f"Read from your {b.partner} confirmation."), (f"Read from your {b.partner} confirmation.", *warnings), b.partner, merged)
