"""The guided trip builder (F-055): a few friendly questions build the same `Plan` the template does.

The builder keeps no state on the server and nothing in the cookie: the answers so far travel in one hidden `draft` field (JSON of plain
text), posted with every step. A step reads its own fields into the draft (`read`), checks them (`check`) and the end builds a
`tripimport.Plan` (`build`). From there it is the importer's path: the same preview, the same replace-existing check, the same save.
Everything is checked again when the plan is built, because a hidden field can be edited.

The steps (STEPS): where, dates, who, flights, hotel, car, notes. `check(step, draft)` returns {field name: friendly message}.
Field names are the form's input names: `title`, `leg0_airline`, `hotel1_check_in_time`, `car_company` ...
"""

import json
import re
from datetime import date, datetime, time, timedelta

from gitaway import catalog, tripimport as ti, zones

STEPS = ("where", "dates", "who", "flights", "hotel", "car", "notes")
MAX_ADULTS = ti.MAX_TRAVELERS  # anything the importer accepts opens intact (the total is checked in check_who)
MAX_KIDS = ti.MAX_TRAVELERS
MAX_DRAFT = 40_000
AIRPORTS = ("SFO", "OAK", "SJC", "LAX", "BUR", "SNA", "LGB")
DESTINATION_AIRPORT = {"los angeles": "LAX", "la": "LAX", "burbank": "BUR", "long beach": "LGB", "orange county": "SNA"}

LEG = ("airline", "number", "from", "to", "depart_date", "depart_time", "arrive_date", "arrive_time", "confirmation", "seats")
HOTEL = ("name", "address", "check_in_date", "check_in_time", "check_out_date", "check_out_time", "confirmation", "room", "phone", "rooms")  # `rooms` has no question: it rides along from an import
CAR = ("company", "pickup_place", "pickup_date", "pickup_time", "dropoff_place", "dropoff_date", "dropoff_time", "confirmation", "car", "phone")
SCALARS = ("title", "destination", "start", "end", "adults", "flying", "stay", "rent", "notes", "booked_on", "itinerary", "timezone")
CARRIED = ("knames", "aages")  # kids' names and adults' ages: no question for them, they ride along from an import


def blank(fields):
    return {f: "" for f in fields}


def new_draft() -> dict:
    return {"adults": "2", "kids": [], "names": [], "emails": [], "flying": "yes", "stay": "yes", "rent": "no"}


def _s(value, limit=200):
    return value[:limit] if isinstance(value, str) else ""


def _rows(value, fields, most):
    out = []
    for item in (value if isinstance(value, list) else [])[:most]:
        item = item if isinstance(item, dict) else {}
        out.append({f: _s(item.get(f)) for f in fields})
    return out


def load(text) -> dict:
    """The draft a posted `draft` field holds, cleaned: only the known keys, only text, bounded. Nonsense gives a fresh draft."""
    try:
        raw = json.loads(text) if isinstance(text, str) and 0 < len(text) <= MAX_DRAFT else None
    except ValueError:
        raw = None
    if not isinstance(raw, dict):
        return new_draft()
    d = new_draft()
    for key in SCALARS:
        if key in raw:
            d[key] = _s(raw[key], 2100 if key == "notes" else 200)
    for key in ("kids", "names", "emails", *CARRIED):
        d[key] = [_s(x, 100) for x in (raw.get(key) if isinstance(raw.get(key), list) else [])[:MAX_KIDS]]
    if isinstance(raw.get("legs"), list):
        d["legs"] = _rows(raw["legs"], LEG, ti.MAX_LEGS)
    if isinstance(raw.get("hotels"), list):
        d["hotels"] = _rows(raw["hotels"], HOTEL, ti.MAX_HOTELS)
    if isinstance(raw.get("car"), dict):
        d["car"] = _rows([raw["car"]], CAR, 1)[0]
    return d


def dump(draft) -> str:
    return json.dumps(draft, separators=(",", ":"), ensure_ascii=False)


# ---- reading a step's form into the draft ---------------------------------------------------------------------------

def _whole(text, default=0):
    text = (text or "").strip()
    return int(text) if text.isascii() and text.isdigit() else default


def adults_of(draft) -> int:
    return max(0, min(_whole(draft.get("adults"), 2), MAX_ADULTS))


def read(step, form, draft):
    """Copy the fields step `step` (1-based) owns from `form` (a mapping of strings) into `draft`."""
    get = lambda k: str(form.get(k, "") or "").strip()
    if step == 1:
        draft["title"], draft["destination"] = get("title"), get("destination")
    elif step == 2:
        draft["start"], draft["end"] = get("start"), get("end")
    elif step == 3:
        draft["adults"] = get("adults") or draft.get("adults", "2")
        draft["kids"] = [get(f"k{i}") for i in range(1, min(_whole(get("nkids")), MAX_KIDS) + 1)]
        n = adults_of(draft)
        draft["knames"], draft["aages"] = [get(f"kn{i}") for i in range(1, len(draft["kids"]) + 1)], draft.get("aages", [])[:n]
        draft["names"] = [get(f"an{i}") for i in range(1, n + 1)]
        draft["emails"] = [get(f"ae{i}") for i in range(1, n + 1)]
    elif step == 4:
        draft["flying"] = "no" if get("flying") == "no" else "yes"
        draft["legs"] = [{f: get(f"leg{i}_{f}") for f in LEG} for i in range(ti.MAX_LEGS) if f"leg{i}_airline" in form]
    elif step == 5:
        draft["stay"] = "no" if get("stay") == "no" else "yes"
        old = draft.get("hotels", [])
        draft["hotels"] = [{**{f: get(f"hotel{i}_{f}") for f in HOTEL if f != "rooms"}, "rooms": old[i]["rooms"] if i < len(old) else ""} for i in range(ti.MAX_HOTELS) if f"hotel{i}_name" in form]
    elif step == 6:
        draft["rent"] = "yes" if get("rent") == "yes" else "no"
        draft["car"] = {f: get(f"car_{f}") for f in CAR}
    elif step == 7:
        draft["notes"], draft["booked_on"], draft["itinerary"] = str(form.get("notes", "") or "").strip(), get("booked_on"), get("itinerary")
    return draft


# ---- smart defaults -------------------------------------------------------------------------------------------------

def arrival_airport(draft) -> str:
    return DESTINATION_AIRPORT.get((draft.get("destination") or "").strip().casefold(), "")


def seed(step, draft):
    """Fill the starting rows of a step the first time it is drawn: dates from the trip, the way home on the return date."""
    start, end = draft.get("start", ""), draft.get("end", "")
    if step == 4 and "legs" not in draft:
        to = arrival_airport(draft)
        draft["legs"] = [{**blank(LEG), "from": catalog.ORIGIN[0], "to": to, "depart_date": start, "arrive_date": start},
                         {**blank(LEG), "from": to, "to": catalog.ORIGIN[0], "depart_date": end, "arrive_date": end}]
    elif step == 5 and "hotels" not in draft:
        draft["hotels"] = [{**blank(HOTEL), "check_in_date": start, "check_in_time": "15:00", "check_out_date": end, "check_out_time": "11:00"}]
    elif step == 6 and "car" not in draft:
        place = arrival_airport(draft) or next((leg["to"] for leg in draft.get("legs", []) if leg.get("to")), "")
        draft["car"] = {**blank(CAR), "pickup_place": place, "pickup_date": start, "pickup_time": "10:00", "dropoff_place": place, "dropoff_date": end, "dropoff_time": "12:00"}
    return draft


def add_row(step, draft):
    """"Add another flight / hotel": a new row with sensible dates."""
    if step == 4:
        legs = draft.setdefault("legs", [])
        if len(legs) < ti.MAX_LEGS:
            last = legs[-1] if legs else {}
            day = last.get("arrive_date") or draft.get("start", "")
            legs.append({**blank(LEG), "from": last.get("to", ""), "depart_date": day, "arrive_date": day})
    elif step == 5:
        hotels = draft.setdefault("hotels", [])
        if len(hotels) < ti.MAX_HOTELS:
            prev = hotels[-1]["check_out_date"] if hotels else draft.get("start", "")
            hotels.append({**blank(HOTEL), "check_in_date": prev, "check_in_time": "15:00", "check_out_date": draft.get("end", ""), "check_out_time": "11:00"})
    return draft


def remove_row(step, draft, i):
    key = {4: "legs", 5: "hotels"}.get(step)
    if key and 0 <= i < len(draft.get(key, [])):
        del draft[key][i]
    return draft


# ---- checking a step ------------------------------------------------------------------------------------------------

_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")


def _day(text):
    if _DAY.match(text or ""):
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
    return None


def _at(day_text, time_text):
    d, m = _day(day_text), _TIME.match(time_text or "")
    if d and m and int(m.group(1)) <= 23 and int(m.group(2)) <= 59:
        return datetime.combine(d, time(int(m.group(1)), int(m.group(2))))
    return None


def _limit(errors, name, value, label, limit, required=False):
    if not value:
        if required:
            errors[name] = f"{label} is needed."
    elif len(value) > limit:
        errors[name] = f"{label} is too long (at most {limit} characters)."


def _when(errors, prefix, row, key, label):
    """The datetime in `row[key + "_date"]` and `row[key + "_time"]`, or None with an error on the field that is wrong
    (the error names are `prefix + key + "_date"` / `"_time"`)."""
    if _day(row.get(f"{key}_date", "")) is None:
        errors[f"{prefix}{key}_date"] = f"Pick the {label} date."
        return None
    at = _at(row[f"{key}_date"], row.get(f"{key}_time", ""))
    if at is None:
        errors[f"{prefix}{key}_time"] = f"Pick the {label} time (like 08:05)."
    return at


def trip_days(draft):
    s, e = _day(draft.get("start")), _day(draft.get("end"))
    return (s, e) if s and e else (None, None)


def _outside(at, lo, hi):
    return not lo <= at.date() <= hi


def check_where(draft):
    errors = {}
    _limit(errors, "title", draft.get("title", ""), "The trip name", 60, True)
    _limit(errors, "destination", draft.get("destination", ""), "Where you are going", 60, True)
    return errors


def check_dates(draft):
    errors = {}
    s, e = _day(draft.get("start")), _day(draft.get("end"))
    if s is None:
        errors["start"] = "Pick the day you leave."
    if e is None:
        errors["end"] = "Pick the day you come home."
    if s and e:
        if e < s:
            errors["end"] = "You come home before you leave. Check the two days."
        elif (e - s).days + 1 > ti.MAX_DAYS:
            errors["end"] = f"A trip can be at most {ti.MAX_DAYS} days long."
    return errors


def check_who(draft):
    errors = {}
    adults = _whole(draft.get("adults"), -1)
    if not 1 <= adults <= MAX_ADULTS:
        errors["adults"] = f"Choose 1 to {MAX_ADULTS} adults."
        adults = 0
    for i, age in enumerate(draft.get("kids", []), 1):
        if not (age.isascii() and age.isdigit() and int(age) <= catalog.MAX_KID_AGE):
            errors[f"k{i}"] = f"Pick an age from 0 to {catalog.MAX_KID_AGE} for kid {i}."
    if adults and adults + len(draft.get("kids", [])) > ti.MAX_TRAVELERS:
        errors["nkids"] = f"That is more than {ti.MAX_TRAVELERS} travelers. Keep it to the people on the booking."
    for i, name in enumerate(draft.get("knames", []), 1):
        _limit(errors, f"kn{i}", name, f"Kid {i}’s name", 40)
    for i, name in enumerate(draft.get("names", [])[:adults], 1):
        _limit(errors, f"an{i}", name, f"Adult {i}’s name", 40)
    for i, mail in enumerate(draft.get("emails", [])[:adults], 1):
        if mail and not (ti._EMAIL.match(mail) and len(mail) <= 80):
            errors[f"ae{i}"] = f"“{mail}” does not look like an email address."
    return errors


def _span(start, end):
    return f"{start:%b} {start.day} – {end:%b} {end.day}"


def check_flights(draft):
    errors = {}
    if draft.get("flying") == "no":
        return errors
    legs = draft.get("legs", [])
    if not legs:
        return {"flying": "Add a flight, or choose “I’m not flying”."}
    start, end = trip_days(draft)
    for i, leg in enumerate(legs):
        p, n = f"leg{i}_", i + 1
        _limit(errors, p + "airline", leg["airline"], f"Flight {n}’s airline", 40, True)
        _limit(errors, p + "number", leg["number"], f"Flight {n}’s flight number", 12, True)
        for key, label in (("from", "leaves from"), ("to", "lands at")):
            if not (leg[key].isalpha() and leg[key].isascii() and len(leg[key]) == 3):
                errors[p + key] = f"Flight {n}: where it {label} should be a three-letter airport code like SFO."
        _limit(errors, p + "confirmation", leg["confirmation"], f"Flight {n}’s confirmation", 20)
        _limit(errors, p + "seats", leg["seats"], f"Flight {n}’s seats", 60)
        out = _when(errors, p, leg, "depart", f"flight {n} leaves")
        land = _when(errors, p, leg, "arrive", f"flight {n} lands")
        if out and land and not -1 <= (land.date() - out.date()).days <= 2:
            errors[p + "arrive_date"] = f"Flight {n} lands {abs((land.date() - out.date()).days)} days from when it leaves. Check the dates."
        if leg["from"] and leg["from"].casefold() == leg["to"].casefold() and p + "from" not in errors and p + "to" not in errors:
            errors[p + "to"] = f"Flight {n} leaves from and lands at {leg['from'].upper()}. Check the airports."
        if start and end:
            if out and _outside(out, start - timedelta(days=1), end):
                errors[p + "depart_date"] = f"Flight {n} leaves on {out:%b} {out.day}, outside your trip dates ({_span(start, end)}). Change the flight, or go back and change the dates."
            if land and p + "arrive_date" not in errors and _outside(land, start, end + timedelta(days=1)):
                errors[p + "arrive_date"] = f"Flight {n} lands on {land:%b} {land.day}, outside your trip dates ({_span(start, end)}). Change the flight, or go back and change the dates."
    return errors


def check_hotel(draft):
    errors = {}
    if draft.get("stay") == "no":
        return errors
    hotels = draft.get("hotels", [])
    if not hotels:
        return {"stay": "Add a hotel, or choose “No hotel”."}
    start, end = trip_days(draft)
    stays = []
    for i, h in enumerate(hotels):
        p = f"hotel{i}_"
        who = f"Hotel {i + 1}" if len(hotels) > 1 else "The hotel"
        _limit(errors, p + "name", h["name"], f"{who}’s name", 80, True)
        _limit(errors, p + "address", h["address"], f"{who}’s address", 120, True)
        _limit(errors, p + "confirmation", h["confirmation"], f"{who}’s confirmation", 30)
        _limit(errors, p + "room", h["room"], f"{who}’s room", 80)
        _limit(errors, p + "phone", h["phone"], f"{who}’s phone", 30)
        cin, cout = _when(errors, p, h, "check_in", "check-in"), _when(errors, p, h, "check_out", "check-out")
        if cin and cout and cout <= cin:
            errors[p + "check_out_date"] = "Check-out has to be after check-in."
        for key, at in (("check_in", cin), ("check_out", cout)):
            if at and start and end and _outside(at, start, end) and f"{p}{key}_date" not in errors:
                errors[f"{p}{key}_date"] = f"{who}’s {key.replace('_', '-')} is on {at:%b} {at.day}, outside your trip dates ({_span(start, end)}). Change the hotel, or go back and change the dates."
        if cin and cout and cout > cin:
            stays.append((cin, cout, i, h["name"]))
    stays.sort()
    for a, b in zip(stays, stays[1:]):
        if b[0] < a[1]:
            errors.setdefault(f"hotel{b[2]}_check_in_date", f"{b[3]} starts before {a[3]} ends. Two stays cannot overlap.")
    return errors


def check_car(draft):
    errors = {}
    if draft.get("rent") != "yes":
        return errors
    c = draft.get("car") or blank(CAR)
    _limit(errors, "car_company", c["company"], "The car company", 40, True)
    _limit(errors, "car_pickup_place", c["pickup_place"], "Where you pick it up", 80, True)
    _limit(errors, "car_dropoff_place", c["dropoff_place"], "Where you drop it off", 80, True)
    _limit(errors, "car_confirmation", c["confirmation"], "The car’s confirmation", 30)
    _limit(errors, "car_car", c["car"], "The car type", 40)
    _limit(errors, "car_phone", c["phone"], "The car’s phone", 30)
    pick, drop = _when(errors, "car_", c, "pickup", "pick-up"), _when(errors, "car_", c, "dropoff", "drop-off")
    if pick and drop and drop <= pick:
        errors["car_dropoff_date"] = "The car has to be dropped off after it is picked up."
    start, end = trip_days(draft)
    for key, label, at in (("pickup", "pick-up", pick), ("dropoff", "drop-off", drop)):
        if at and start and end and _outside(at, start, end) and f"car_{key}_date" not in errors:
            errors[f"car_{key}_date"] = f"The car {label} is on {at:%b} {at.day}, outside your trip dates ({_span(start, end)}). Change it, or go back and change the dates."
    return errors


def check_notes(draft):
    errors = {}
    _limit(errors, "booked_on", draft.get("booked_on", ""), "Where you booked", 30)
    _limit(errors, "itinerary", draft.get("itinerary", ""), "The itinerary number", 30)
    if len(draft.get("notes", "")) > ti.MAX_NOTES:
        errors["notes"] = f"The notes are too long (at most {ti.MAX_NOTES} characters)."
    return errors


CHECKS = (check_where, check_dates, check_who, check_flights, check_hotel, check_car, check_notes)


def _anything(draft) -> bool:
    return (draft.get("flying") != "no" and bool(draft.get("legs"))) or (draft.get("stay") != "no" and bool(draft.get("hotels"))) or draft.get("rent") == "yes"


def check(step, draft) -> dict:
    """{field name: friendly message} for step `step` (1-based); empty when it is fine."""
    errors = CHECKS[step - 1](draft)
    if step == 6 and not errors and not _anything(draft):
        errors["rent"] = "You said no to flights, a hotel and a car, so there is nothing to put on the calendar. Go back and add at least one."
    return errors


def first_problem(draft):
    """(step, errors) of the first step that does not pass, or None."""
    for step in range(1, len(STEPS) + 1):
        errors = check(step, draft)
        if errors:
            return step, errors
    return None


# ---- the plan -------------------------------------------------------------------------------------------------------

def _adult_age(text):
    """An adult's age that rode along from an import: 18 to 120, else none (a hidden field can be edited)."""
    n = _whole(text, -1)
    return n if 18 <= n <= 120 else None


def _rooms(text):
    """Rooms that rode along: 1 to 8 like the importer, else 1."""
    n = _whole(text, 1)
    return n if 1 <= n <= 8 else 1


def _stamp(at):
    return at.date().isoformat(), f"{at:%H:%M}"


def from_plan(plan) -> dict:
    """The draft that builds `plan` back (the way from an import preview into the builder: "Change something"). Nothing the preview shows is lost."""
    adults = [t for t in plan.travelers if not t.is_kid][:MAX_ADULTS]
    kids = [t for t in plan.travelers if t.is_kid][:MAX_KIDS]
    d = {"title": plan.title, "destination": plan.destination, "start": plan.start.isoformat(), "end": plan.end.isoformat(),
         "adults": str(len(adults)), "names": [t.name for t in adults], "emails": [t.email for t in adults], "aages": [str(t.age) if t.age is not None else "" for t in adults],
         "kids": [str(t.age) for t in kids], "knames": [t.name for t in kids],
         "flying": "yes" if plan.legs else "no", "stay": "yes" if plan.hotels else "no", "rent": "yes" if plan.rental else "no",
         "notes": plan.notes, "booked_on": plan.booked_on, "itinerary": plan.itinerary,
         # the zone rides along only when the text set it; otherwise the builder derives it again from the flights and destination after edits
         "timezone": plan.timezone if plan.timezone != ti.zone_for(plan.legs, plan.destination)[0] else ""}
    if plan.legs:
        d["legs"] = [{"airline": l.airline, "number": l.number, "from": l.origin, "to": l.dest, "depart_date": _stamp(l.depart)[0], "depart_time": _stamp(l.depart)[1],
                      "arrive_date": _stamp(l.arrive)[0], "arrive_time": _stamp(l.arrive)[1], "confirmation": l.confirmation, "seats": l.seats} for l in plan.legs]
    if plan.hotels:
        d["hotels"] = [{"name": h.name, "address": h.address, "check_in_date": _stamp(h.check_in)[0], "check_in_time": _stamp(h.check_in)[1],
                        "check_out_date": _stamp(h.check_out)[0], "check_out_time": _stamp(h.check_out)[1], "confirmation": h.confirmation, "room": h.room, "phone": h.phone,
                        "rooms": str(h.rooms)} for h in plan.hotels]
    if plan.rental:
        c = plan.rental
        d["car"] = {"company": c.company, "pickup_place": c.pickup_place, "pickup_date": _stamp(c.pickup)[0], "pickup_time": _stamp(c.pickup)[1],
                    "dropoff_place": c.dropoff_place, "dropoff_date": _stamp(c.dropoff)[0], "dropoff_time": _stamp(c.dropoff)[1], "confirmation": c.confirmation, "car": c.car, "phone": c.phone}
    return d


def build(draft) -> ti.Plan:
    """The `Plan` this draft describes. Raises BuildProblem with the step to go back to when a step does not pass."""
    problem = first_problem(draft)
    if problem:
        raise BuildProblem(*problem)
    n, names, emails = adults_of(draft), draft.get("names", []), draft.get("emails", [])
    aages, knames = draft.get("aages", []), draft.get("knames", [])
    people = [ti.Traveler(((names[i] if i < len(names) else "") or f"Adult {i + 1}"), (emails[i] if i < len(emails) else "").lower(),
                          _adult_age(aages[i] if i < len(aages) else "")) for i in range(n)]
    people += [ti.Traveler((knames[i] if i < len(knames) else "") or f"Kid {i + 1}", "", int(age)) for i, age in enumerate(draft.get("kids", []))]
    legs = hotels = ()
    if draft.get("flying") != "no":
        legs = tuple(sorted((ti.Leg(l["airline"], l["number"], l["from"].upper(), l["to"].upper(), _at(l["depart_date"], l["depart_time"]), _at(l["arrive_date"], l["arrive_time"]), l["confirmation"], l["seats"])
                             for l in draft["legs"]), key=lambda leg: leg.depart))
    if draft.get("stay") != "no":
        hotels = tuple(sorted((ti.Lodging(h["name"], h["address"], _at(h["check_in_date"], h["check_in_time"]), _at(h["check_out_date"], h["check_out_time"]), h["confirmation"], h["room"], _rooms(h["rooms"]), h["phone"])
                               for h in draft["hotels"]), key=lambda h: h.check_in))
    rental = None
    if draft.get("rent") == "yes":
        c = draft["car"]
        rental = ti.Rental(c["company"], c["pickup_place"], _at(c["pickup_date"], c["pickup_time"]), c["dropoff_place"], _at(c["dropoff_date"], c["dropoff_time"]), c["confirmation"], c["car"], c["phone"])
    return ti.Plan(title=draft["title"], destination=draft["destination"], start=_day(draft["start"]), end=_day(draft["end"]), booked_on=draft.get("booked_on") or "elsewhere",
                   itinerary=draft.get("itinerary", ""), travelers=tuple(people), legs=legs, hotels=hotels, rental=rental, notes=draft.get("notes", "").strip(), timezone=zones.valid(draft.get("timezone", "")) or "")


class BuildProblem(ValueError):
    """A draft that does not pass: `step` (1-based) is the first step to fix and `errors` its messages."""

    def __init__(self, step, errors):
        self.step, self.errors = step, errors
        super().__init__(next(iter(errors.values())))
