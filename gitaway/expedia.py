"""Read an Expedia itinerary (pasted text, or the text of its PDF) and write it as the trip template (F-056).

`looks_like_expedia(text)` says whether text is an Expedia itinerary. `convert(text)` returns `Converted(yaml, warnings, ...)`: the YAML
of docs/trip-template.md (a `hotels:` list, `car:`, `travelers:`, `trip:` with `booked_on: Expedia`) and plain-English warnings for
the parts it could not read. The import page then runs the normal reader (gitaway.tripimport.parse) over that YAML, so nothing here
saves anything. `pdf_text(bytes)` pulls the text out of an uploaded PDF with pypdf.

THE LAYOUT. Every booking is a section that starts with "Stay in <city>" or "Car rental in <city>" and a range line ("Oct 4, 2026 -
Oct 10, 2026"), then the company or hotel, "Confirmation: #…", and the details. The same PDF comes out in three orders (pdftotext, its
-layout mode, pypdf), so nothing depends on line order beyond: a label comes before its value, and the dates and times of one block
stay in order (check in, then check out). The year of a day like "Sun, Oct 4" comes from the section's range line. Everything from
"Payment details" on, "Important information", check-in paragraphs and the support footer are skipped, so prices, card digits and
Expedia's phone numbers never reach the output. Only chosen fields are copied; nothing else is carried over.

THE PARTY. "Reserved for Name, 3 adults, 1 child" gives the largest party across bookings. The named person comes first, then
"Adult 2", "Adult 3", "Child 1": placeholders to rename. A car's "Reserved for" (another person) takes the next adult slot. Expedia gives
no child's age, so a child is written with age 10 and a warning says to change it (the party counts a traveler without an age as an adult).
"""

import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time

from gitaway import zones

MAX_PDF_BYTES = 5_000_000
MAX_PDF_PAGES = 30
MAX_TEXT = 400_000
CHILD_AGE = 10

_MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
_MON = "(" + "|".join(_MONTHS) + ")[a-z]*"
_RANGE = re.compile(rf"^{_MON}\.? (\d{{1,2}}), (\d{{4}}) ?[-–] ?{_MON}\.? (\d{{1,2}}), (\d{{4}})$")
_DAY = re.compile(rf"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?, {_MON}\.? (\d{{1,2}})$")
_TIME = re.compile(r"^(\d{1,2})(?::(\d{2}))?\s*([AaPp])\.?[Mm]\.?$")
_HEADER = re.compile(r"^(Stay in|Car rental in) (.+)$")
_FLIGHT = re.compile(r"^Flights?\b")
_LABEL = re.compile(r"^(Check in|Check out|Pick-up|Drop-off)$", re.I)
_COUNTRY = re.compile(r",?\s*(United States of America|United States|USA)\s*$", re.I)
_STATE_ZIP = re.compile(r",\s*([A-Z]{2}),?\s+\d{5}")
_PERK = re.compile(r"status got you|perk|^Mention your|Learn more about|^[•·•*-]+$|^(Blue|Silve ?r|Gold|Platinum|Diamond)$", re.I)
_STOP_ROOM = re.compile(r"^(Reserved for|Included amenities|Requests|Payment details|Amenities)$")
_SKIP_SECTION = ("Expedia support",)

# airport names that appear in a car rental's address -> IATA code (used only when the code is one gitaway/zones.py knows)
_AIRPORT_NAMES = (
    ("hollywood-burbank", "BUR"), ("hollywood burbank", "BUR"), ("bob hope", "BUR"), ("burbank", "BUR"),
    ("los angeles international", "LAX"), ("los angeles intl", "LAX"), ("san francisco international", "SFO"), ("san diego international", "SAN"),
    ("mineta", "SJC"), ("san jose international", "SJC"), ("oakland international", "OAK"), ("john wayne", "SNA"), ("ontario international", "ONT"),
    ("long beach", "LGB"), ("john f. kennedy", "JFK"), ("laguardia", "LGA"), ("newark liberty", "EWR"), ("o'hare", "ORD"), ("o’hare", "ORD"),
    ("hartsfield", "ATL"), ("dallas/fort worth", "DFW"), ("denver international", "DEN"), ("seattle-tacoma", "SEA"), ("portland international", "PDX"),
    ("harry reid", "LAS"), ("mccarran", "LAS"), ("sky harbor", "PHX"), ("orlando international", "MCO"), ("miami international", "MIA"),
    ("logan international", "BOS"), ("daniel k. inouye", "HNL"), ("honolulu international", "HNL"),
)


@dataclass(frozen=True)
class Converted:
    yaml: str
    warnings: tuple
    stays: int = 0
    cars: int = 0
    travelers: int = 0


# ---- recognising and reading the text ------------------------------------------------------------------------------

def _lines(text):
    """The text as short stripped lines. A -layout line with columns ("Pick-up      Drop-off") is split at the gaps, so it reads like the other orders."""
    out = []
    for raw in (text or "").replace("\x0c", "\n").replace("\r", "\n").split("\n"):
        for part in re.split(r"\s{2,}|\t", raw.strip()):
            part = part.strip().replace(" ", " ")
            if part:
                out.append(part)
    return out


def _is_range(line):
    return bool(_RANGE.match(line))


def _headers(lines):
    """[(index, kind, city)]: a section starts at "Stay in X" / "Car rental in X" when the next line is its range."""
    found = []
    for i, line in enumerate(lines[:-1]):
        m = _HEADER.match(line)
        if m and _is_range(lines[i + 1]):
            found.append((i, "stay" if m.group(1) == "Stay in" else "car", m.group(2).strip()))
    return found


def looks_like_expedia(text) -> bool:
    """True for the text of an Expedia itinerary: at least one "Stay in …" or "Car rental in …" section with its dates, and Expedia's own labels."""
    if not isinstance(text, str) or not text.strip():
        return False
    lines = _lines(text[:MAX_TEXT])
    if not _headers(lines):
        return False
    low = text.lower()
    return "expedia itinerary" in low or "expedia support" in low or "reservation details" in low


def pdf_text(data: bytes) -> str:
    """The text of an uploaded PDF. Raises ValueError (a friendly sentence) when it is not a readable PDF."""
    if not data or not data.lstrip()[:5].startswith(b"%PDF"):
        raise ValueError("That file is not a PDF. Upload the itinerary PDF from Expedia, or paste its text.")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError(f"That PDF is too large (at most {MAX_PDF_BYTES // 1_000_000} MB). Paste the itinerary text instead.")
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("That PDF is locked with a password. Paste the itinerary text instead.")
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:MAX_PDF_PAGES])
    except ValueError:
        raise
    except Exception:
        raise ValueError("We couldn't read that PDF. Paste the itinerary text instead.") from None
    if not text.strip():
        raise ValueError("We couldn't find any text in that PDF (it may be a scan). Paste the itinerary text instead.")
    return text[:MAX_TEXT]


# ---- small readers -------------------------------------------------------------------------------------------------

def _clock(token):
    m = _TIME.match(token.strip())
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
    if not (1 <= h <= 12 and mi < 60):
        return None
    return time(h % 12 + (12 if ap == "p" else 0), mi)


def _month(token):
    return _MONTHS[token[:3].title()]


def _range(line):
    m = _RANGE.match(line)
    g = m.groups()
    return date(int(g[2]), _month(g[0]), int(g[1])), date(int(g[5]), _month(g[3]), int(g[4]))


def _day_in(token, lo, hi):
    """The date of "Sun, Oct 4" within the section's range (the range gives the year, so a range across New Year works)."""
    m = _DAY.match(token)
    if not m:
        return None
    mon, d = _month(m.group(1)), int(m.group(2))
    for year in sorted({lo.year, hi.year}):
        try:
            cand = date(year, mon, d)
        except ValueError:
            continue
        if lo <= cand <= hi:
            return cand
    return None


def _proper(name):
    return " ".join(w.capitalize() if (w.islower() or w.isupper()) else w for w in name.split())


def _between(lines, start, stops, begin=0):
    """The lines after the first line equal to `start`, up to the first line that matches `stops` (a regex)."""
    try:
        i = lines.index(start, begin) + 1
    except ValueError:
        return None
    out = []
    for line in lines[i:]:
        if re.search(stops, line):
            break
        out.append(line)
    return out


def _reserved(lines):
    """(name, adults, children) from the line after "Reserved for"."""
    if "Reserved for" not in lines:
        return "", 0, 0
    i = lines.index("Reserved for") + 1
    line = lines[i] if i < len(lines) else ""
    adults = children = 0
    names = []
    for part in line.split(","):
        part = part.strip()
        a, c = re.match(r"^(\d+)\s+adults?$", part, re.I), re.match(r"^(\d+)\s+(?:child|children|kids?)$", part, re.I)
        if a:
            adults = int(a.group(1))
        elif c:
            children = int(c.group(1))
        elif part:
            names.append(part)
    return _proper(" ".join(names)), adults, children


def _confirmation(lines):
    for line in lines:
        m = re.match(r"^Confirmation(?: number)?:?\s*#?\s*(\S+)", line, re.I)
        if m:
            return m.group(1).strip()
    return ""


def _title_lines(lines):
    """The hotel or company name: the lines between the range line and "Confirmation:"."""
    out = []
    for line in lines[2:]:
        if re.match(r"^Confirmation", line, re.I) or re.match(r"^\+?\d[\d\s().-]{6,}$", line) or len(out) >= 2:
            break
        out.append(line)
    return " ".join(out)


def _schedule(head, lo, hi):
    """((first day, first time), (second day, second time)) from the block of labels, days and times between "Reservation details" and the next heading.
    Either may be None (not found). The days fall back to the range line, which always has them."""
    tokens = []
    for line in head:
        if _LABEL.match(line):
            tokens.append(("label", line.lower()))
        elif _DAY.match(line):
            tokens.append(("day", _day_in(line, lo, hi)))
        elif _clock(line):
            tokens.append(("time", _clock(line)))
    days = [v for k, v in tokens if k == "day"]
    times = [v for k, v in tokens if k == "time"]
    first_value = next((i for i, (k, _) in enumerate(tokens) if k != "label"), len(tokens))
    labels_before = sum(1 for k, _ in tokens[:first_value] if k == "label")
    grouped = labels_before != 1  # both labels first (plain, -layout): values follow in block order; one label then its values (pypdf): interleaved
    d1 = days[0] if days and days[0] else lo
    d2 = days[1] if len(days) > 1 and days[1] else hi
    if len(times) >= 2:
        t1, t2 = times[0], times[1]
    elif len(times) == 1:
        if grouped:  # labels first, then days, then times: one time is the first block's
            t1, t2 = times[0], None
        else:        # label, day, time per block: the one time belongs to the block it follows
            idx = next(i for i, (k, _) in enumerate(tokens) if k == "time")
            later_label = any(k == "label" for k, _ in tokens[first_value:idx])
            t1, t2 = (None, times[0]) if later_label else (times[0], None)
    else:
        t1 = t2 = None
    return (d1, t1), (d2, t2)


def _airport_code(parts):
    """An IATA code for a car rental's place when its address names an airport gitaway/zones.py knows."""
    blob = " ".join(parts).lower()
    for code in re.findall(r"\(([A-Z]{3})\)", " ".join(parts)):
        if code in zones.AIRPORTS:
            return code
    if "airport" in blob or "international" in blob:
        for needle, code in _AIRPORT_NAMES:
            if needle in blob and code in zones.AIRPORTS:
                return code
    return ""


def _place(block, company):
    """A car place from the lines after "Pick-up location" / "Drop-off location": the company line dropped; a known airport as its code, else the address."""
    if not block:
        return ""
    block = list(block)
    if block and (block[0].lower() == company.lower() or (company and block[0].lower().startswith(company.lower()) and len(block) > 1)):
        block = block[1:]
    code = _airport_code(block)
    if code:
        return code
    return _COUNTRY.sub("", ", ".join(block)).strip(", ")[:80]


# ---- the sections --------------------------------------------------------------------------------------------------

def _stay(lines, city, warnings):
    label = f"Stay in {city}"
    lo, hi = _range(lines[1])
    name = _title_lines(lines) or ""
    if not name:
        warnings.append(f"We couldn't read the hotel name for {label}.")
        name = label
    head = _between(lines, "Reservation details", r"^Check in and special instructions$|^Location$|^Room details$") or []
    (d_in, t_in), (d_out, t_out) = _schedule(head, lo, hi)
    if t_in is None:
        m = next((re.match(r"^Check-in time starts at (.+)$", l) for l in lines if re.match(r"^Check-in time starts at (.+)$", l)), None)
        t_in = _clock(m.group(1)) if m else None
    if t_in is None:
        warnings.append(f"We couldn't read the check-in time for {label}; 15:00 was used.")
        t_in = time(15, 0)
    if t_out is None:
        warnings.append(f"We couldn't read the check-out time for {label}; 11:00 was used.")
        t_out = time(11, 0)
    address = _between(lines, "Location", r"^(Room details|Reserved for|Included amenities|Requests|Payment details)$")
    address = _COUNTRY.sub("", ", ".join(address or [])).strip(", ")[:120]
    if not address:
        warnings.append(f"We couldn't read the address for {label}; the city was used.")
        address = city
    room_lines = _between(lines, "Room details", _STOP_ROOM.pattern) or []
    room = " ".join(l for l in room_lines if not _PERK.search(l))[:80].strip()
    conf = _confirmation(lines)
    if not conf:
        warnings.append(f"We couldn't read the confirmation number for {label}.")
    name_, adults, kids = _reserved(lines)
    return dict(kind="stay", city=city, name=name[:80], conf=conf[:30], address=address, room=room, check_in=datetime.combine(d_in, t_in), check_out=datetime.combine(d_out, t_out),
                person=name_, adults=adults, kids=kids, state=(_STATE_ZIP.search(address).group(1) if _STATE_ZIP.search(address) else ""), start=lo, end=hi)


def _car(lines, city, warnings):
    label = f"Car rental in {city}"
    lo, hi = _range(lines[1])
    company = _title_lines(lines)
    if not company:
        warnings.append(f"We couldn't read the car company for {label}.")
        company = "Car rental"
    head = _between(lines, "Reservation details", r"^Pick-up location$") or []
    (d_p, t_p), (d_d, t_d) = _schedule(head, lo, hi)
    if t_p is None:
        warnings.append(f"We couldn't read the pick-up time for {label}; 12:00 was used.")
        t_p = time(12, 0)
    if t_d is None:
        warnings.append(f"We couldn't read the drop-off time for {label}; 12:00 was used.")
        t_d = time(12, 0)
    stop = r"^(Hours of operation|Rental counter phone number|Drop-off location|Rental information|Reserved for|Amenities|Important information|Payment details)$"
    pickup = _place(_between(lines, "Pick-up location", stop), company)
    drop = _place(_between(lines, "Drop-off location", stop), company) or pickup
    if not pickup:
        warnings.append(f"We couldn't read the pick-up place for {label}; the city was used.")
        pickup = drop = city
    info = _between(lines, "Rental information", r"^(Reserved for|Amenities|Important information|Payment details)$") or []
    kind = info[0] if info else ""
    if len(info) > 1 and re.search(r"or similar$", info[1], re.I):
        kind = f"{kind}, {info[1]}"
    if len(kind) > 40:
        kind = info[0][:40]
    conf = _confirmation(lines)
    if not conf:
        warnings.append(f"We couldn't read the confirmation number for {label}.")
    person, _, _ = _reserved(lines)
    return dict(kind="car", city=city, company=company[:40], conf=conf[:30], pickup=pickup, dropoff=drop, pick_at=datetime.combine(d_p, t_p), drop_at=datetime.combine(d_d, t_d),
                car=kind, person=person, start=lo, end=hi)


# ---- the template --------------------------------------------------------------------------------------------------

def _q(value):
    """A YAML string scalar, always quoted (so a confirmation number like 0012 or 1e5 stays exactly as written)."""
    return json.dumps(str(value), ensure_ascii=False)


def _stamp(at):
    return _q(at.strftime("%Y-%m-%d %H:%M"))


def convert(text) -> Converted:
    """The template YAML for an Expedia itinerary, and warnings for what could not be read."""
    lines = _lines((text or "")[:MAX_TEXT])
    heads = _headers(lines)
    warnings = []
    for i, line in enumerate(lines[:-1]):
        if _FLIGHT.match(line) and _is_range(lines[i + 1]):
            warnings.append("We found a flight but couldn't read it yet; add it under flights:")
            break
    bounds = [h[0] for h in heads] + [len(lines)]
    for j, (i, _, _) in enumerate(heads):  # a section ends at the support footer too
        for k in range(i + 1, bounds[j + 1]):
            if lines[k] in _SKIP_SECTION:
                bounds[j + 1] = k
                break
    stays, cars = [], []
    for j, (i, kind, city) in enumerate(heads):
        block = lines[i:bounds[j + 1]]
        block = block[:block.index("Payment details")] if "Payment details" in block else block
        (stays if kind == "stay" else cars).append((_stay if kind == "stay" else _car)(block, city, warnings))

    everything = stays + cars
    start = min([s["check_in"].date() for s in stays] + [c["pick_at"].date() for c in cars])
    end = max([s["check_out"].date() for s in stays] + [c["drop_at"].date() for c in cars])
    first = sorted(stays, key=lambda s: s["check_in"])[0] if stays else sorted(cars, key=lambda c: c["pick_at"])[0]
    city = first["city"]
    destination = f"{city}, {first['state']}" if first.get("state") else city

    travelers = _party(stays, cars, warnings)
    out = ["# Read from an Expedia itinerary. Rename the travelers, then check each line.", "trip:", f"  title: {_q(f'{city} trip')}", f"  destination: {_q(destination)}",
           f"  start: {_q(start.isoformat())}", f"  end: {_q(end.isoformat())}", "  booked_on: \"Expedia\"", "", "travelers:"]
    for name, age in travelers:
        out.append(f"  - name: {_q(name)}" + (f"\n    age: {age}" if age is not None else ""))
    if stays:
        out += ["", "hotels:"]
        for s in sorted(stays, key=lambda s: s["check_in"]):
            out += [f"  - name: {_q(s['name'])}", f"    address: {_q(s['address'])}", f"    check_in: {_stamp(s['check_in'])}", f"    check_out: {_stamp(s['check_out'])}"]
            out += ([f"    confirmation: {_q(s['conf'])}"] if s["conf"] else []) + ([f"    room: {_q(s['room'])}"] if s["room"] else [])
    if cars:
        c = sorted(cars, key=lambda c: c["pick_at"])[0]
        if len(cars) > 1:
            warnings.append("We found more than one car rental but a trip holds one; the first was used.")
        out += ["", "car:", f"  company: {_q(c['company'])}", f"  pickup: {_q(c['pickup'] + ', ' + c['pick_at'].strftime('%Y-%m-%d %H:%M'))}",
                f"  dropoff: {_q(c['dropoff'] + ', ' + c['drop_at'].strftime('%Y-%m-%d %H:%M'))}"]
        out += ([f"  confirmation: {_q(c['conf'])}"] if c["conf"] else []) + ([f"  car: {_q(c['car'])}"] if c["car"] else [])
    return Converted("\n".join(out) + "\n", tuple(warnings), len(stays), len(cars), len(travelers))


def _party(stays, cars, warnings):
    """[(name, age or None)]: the named person, other named adults, then placeholders. Adults first, then children."""
    adults = max([s["adults"] for s in stays] + [0])
    kids = max([s["kids"] for s in stays] + [0])
    named = []
    for who in [s["person"] for s in stays] + [c["person"] for c in cars]:
        if who and who.lower() not in (n.lower() for n in named):
            named.append(who)
    named = named[:2]  # the booker, and the car's driver if it is someone else
    adults = max(adults, len(named), 1)
    people = []
    for i in range(adults):
        people.append((named[i] if i < len(named) else f"Adult {i + 1}", None))
    for i in range(kids):
        people.append((f"Child {i + 1}", CHILD_AGE))
    if kids:
        warnings.append(f"Expedia doesn't give children's ages, so each child is set to {CHILD_AGE}; change the ages.")
    return people
