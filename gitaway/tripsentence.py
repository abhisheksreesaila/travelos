"""The search as one sentence (F-217): "A family of 4 with Grandma and the dog, SFO to Orlando, Dec 12 to 16, within 20 miles of Disney, under $3,000."

    read(text, today)   an Ask: what the sentence says, part by part. Nothing is guessed: a part it could not read is left empty and named in `Ask.unread`
    write(ask)          the same Ask as one tidy sentence, so a retyped search comes back in the app's words
    parts(ask)          [(key, words)] the page draws, each key a control: party, with, route, dates, near, budget

Plain rules, no model: the same words always give the same search, a test can pin every form, and a search costs nothing. A model may rewrite a loose
sentence into these words later (D-417); what it writes is still read here, so this stays the only reader.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from gitaway import catalog
from gitaway.partners import places

MAX_TEXT = 300
MIN_BUDGET_CENTS, MAX_BUDGET_CENTS = 50_000, 2_000_000      # $500 to $20,000: the ends of the page's budget slider; outside them it is not read as a budget
MAX_MILES = 200
KID_AGE = 8                            # the age a kid counts as when the sentence gives none: a child fare, a seat of their own
_MONTHS = {m: i for i, names in enumerate((("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
                                           ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"), ("dec", "december")), 1) for m in names}
_MON = "(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
_NUMS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "a": 1, "an": 1}
_TO = r"\s*(?:to|through|thru|until|till|-|–|—)\s*"
_DAY = r"(\d{1,2})(?:st|nd|rd|th)?"
_SENIOR = re.compile(r"\b(grandma|grandpa|grandmother|grandfather|grandparents|granny|nana|seniors?|my (?:mom|mum|mother|dad|father))\b", re.I)
_PET = re.compile(r"\b(?:(?:the|our|my|a) )?(dogs?|pupp(?:y|ies)|pets?|cats?)\b", re.I)
_STOP = re.compile(r"\s+(?:in|on|for|under|below|with|near|within|next|this|leaving|around|and|budget|from)\b.*$", re.I)


@dataclass(frozen=True)
class Ask:
    place: str = ""                # where to, as typed ("Orlando")
    origin: str = ""               # the airport they leave from, a three-letter code, or ""
    depart: date | None = None
    return_: date | None = None
    adults: int = 2
    kid_ages: tuple = ()
    ages_given: bool = False       # False: `kid_ages` are KID_AGE stand-ins for kids the sentence only counted
    senior: str = ""               # the word they used for an older traveler ("Grandma"), or ""
    pet: str = ""                  # "dog", "cat" or "pet", or ""
    near: str = ""                 # what the stay should be near ("Disney")
    miles: int | None = None       # how near, when they said
    budget_cents: int | None = None
    party_given: bool = False      # False: nobody said who is going, so `adults` is the usual two
    too_many: bool = False         # they named more travelers than a booking takes (catalog.MAX_TRAVELERS)

    @property
    def unread(self) -> tuple:
        """What stops a search: the parts it cannot run without that the sentence did not give, and a party too big to book, in the order to say them."""
        return tuple(name for name, have in (("place", self.place), ("dates", self.depart and self.return_), ("party", not self.too_many)) if not have)

    @property
    def travelers(self) -> int:
        return self.adults + len(self.kid_ages)


def _num(word) -> int | None:
    word = (word or "").lower()
    if word.isdigit():
        return int(word)
    return _NUMS.get(word)


def _on(month, day, today, after=None, year=None) -> date | None:
    """The next `month day` on or after `today` (and after `after`, a trip's first day), or None for a day that month never has. A typed `year` is taken at its
    word: the day in that year, or None when that is in the past or not after `after`."""
    floor = after or today
    for y in ((year,) if year else (floor.year, floor.year + 1)):
        try:
            found = date(y, month, day)
        except ValueError:
            continue
        if found >= today and (after is None or found > after):
            return found
    return None


def _year(text) -> int | None:
    """A typed year: four digits, or two ("27" is 2027)."""
    return (int(text) if len(text) == 4 else 2000 + int(text)) if text else None


def _first_year(y1, y2, month1, month2) -> int | None:
    """The year of a trip's first day when a year was typed: its own, else the return's (the one before it when the trip crosses New Year)."""
    if y1 or not y2:
        return _year(y1)
    return _year(y2) - (1 if month2 < month1 else 0)


_YEAR = r"(?:,?\s*(\d{4}))?"
_ISO = re.compile(rf"(\d{{4}})-(\d{{2}})-(\d{{2}}){_TO}(\d{{4}})-(\d{{2}})-(\d{{2}})", re.I)
_WORDS = re.compile(rf"\b{_MON}\s+{_DAY}{_YEAR}{_TO}(?:{_MON}\s+)?{_DAY}\b{_YEAR}", re.I)
_SLASH = re.compile(rf"\b(\d{{1,2}})/(\d{{1,2}})(?:/(\d{{4}}|\d{{2}}))?{_TO}(\d{{1,2}})/(\d{{1,2}})(?:/(\d{{4}}|\d{{2}}))?(?![\d/])", re.I)
_ONE = re.compile(rf"\b{_MON}\s+{_DAY}\b{_YEAR}", re.I)
_NIGHTS = re.compile(r"\bfor (\w+) nights?\b", re.I)


def _dates(raw, today):
    """((depart, return) or (None, None), the text with the dates cut out). Cut out, so "Dec 12 to 16" is never read as a trip to a place called 16, and
    the days of "12/20 to 12/24" are never read as kids' ages."""
    def cut(*found):
        out = raw
        for m in sorted(found, key=lambda m: m.start(), reverse=True):
            out = out[:m.start()] + " , " + out[m.end():]
        return out

    m = _ISO.search(raw)
    if m:
        try:
            a, b = date(*map(int, m.groups()[:3])), date(*map(int, m.groups()[3:]))
        except ValueError:
            return (None, None), cut(m)
        return ((a, b) if today <= a < b else (None, None)), cut(m)
    m = _WORDS.search(raw)
    if m:
        m1, d1, y1, m2, d2, y2 = m.groups()
        mon1, mon2 = _MONTHS[m1.lower()], _MONTHS[(m2 or m1).lower()]
        a = _on(mon1, int(d1), today, year=_first_year(y1, y2, mon1, mon2))
        b = _on(mon2, int(d2), today, a, _year(y2)) if a else None
        return ((a, b) if a and b else (None, None)), cut(m)
    m = _SLASH.search(raw)
    if m:
        m1, d1, y1, m2, d2, y2 = m.groups()
        a = _on(int(m1), int(d1), today, year=_first_year(y1, y2, int(m1), int(m2))) if 1 <= int(m1) <= 12 else None
        b = _on(int(m2), int(d2), today, a, _year(y2)) if a and 1 <= int(m2) <= 12 else None
        return ((a, b) if a and b else (None, None)), cut(m)
    m, nights = _ONE.search(raw), _NIGHTS.search(raw)
    if m and nights and _num(nights.group(1)):
        a, n = _on(_MONTHS[m.group(1).lower()], int(m.group(2)), today, year=_year(m.group(3))), _num(nights.group(1))
        return ((a, a + timedelta(days=n)) if a and 1 <= n <= catalog.MAX_NIGHTS else (None, None)), cut(m, nights)
    return (None, None), raw


def _party(low):
    """(adults, kid ages, were the ages given, did they say who is going, are they more than a booking takes). Read from the text with the dates cut out."""
    adults = kids = None
    m = re.search(r"\bfamily of (\w+)", low)
    if m and _num(m.group(1)):
        n = _num(m.group(1))
        adults, kids = min(2, n), max(0, n - 2)
    m = re.search(r"\b(\w+) (?:adults?|grown-?ups?)\b", low)
    if m and _num(m.group(1)):
        adults = _num(m.group(1))
    m = re.search(r"\b(\w+) (?:kids?|children|child)\b", low)
    if m and _num(m.group(1)) is not None:
        kids = _num(m.group(1))
    if adults is None and re.search(r"\b(couple|the two of us|us two)\b", low):
        adults = 2
    if adults is None and re.search(r"\b(solo|just me|by myself|on my own)\b", low):
        adults = 1
    ages = ()
    m = re.search(r"\b(?:ages?|aged)\s+((?:\d{1,2}\s*(?:,|and|&)?\s*)+)", low) or re.search(r"\bkids?\s*\(([\d,\s]+)\)", low)
    if m:
        ages = tuple(int(x) for x in re.findall(r"\d{1,2}", m.group(1)) if int(x) <= catalog.MAX_KID_AGE)
    said = adults is not None or kids is not None or bool(ages)
    adults = 2 if adults is None else adults
    if ages and (kids is None or kids == len(ages)):
        kid_ages, given = ages, True
    else:
        kid_ages, given = (KID_AGE,) * (kids or 0), False
    if not 1 <= adults <= catalog.MAX_TRAVELERS or adults + len(kid_ages) > catalog.MAX_TRAVELERS:
        return 2, (), False, False, True
    return adults, kid_ages, given, said, False


def _budget(low) -> int | None:
    # a number with a unit after it is not money: "less than 600 miles from home", "up to 5 nights"
    m = (re.search(r"\b(?:under|below|budget(?: of| is)?|max(?:imum)?(?: of)?|up to|less than|no more than)\s*\$?\s*(\d[\d,]*(?:\.\d+)?)(?![\d,.])\s*(k\b)?(?!\s*(?:miles?|mi|nights?|hours?|hrs?|days?|minutes?|min|kids?|adults?)\b)", low)
         or re.search(r"\$\s*(\d[\d,]*(?:\.\d+)?)\s*(k\b)?", low))
    if not m:
        return None
    cents = int(round(float(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1) * 100))
    return cents if MIN_BUDGET_CENTS <= cents <= MAX_BUDGET_CENTS else None


def _near(raw):
    m = re.search(r"\bwithin (\d{1,3}) (?:miles?|mi) (?:of|from) (?:the )?([^,.;]+)", raw, re.I)
    if m:
        miles = int(m.group(1))
        return _tidy(m.group(2)), miles if 1 <= miles <= MAX_MILES else None
    m = re.search(r"\b(?:near|close to) (?:the )?([^,.;]+)", raw, re.I)
    return (_tidy(m.group(1)), None) if m else ("", None)


def _tidy(words) -> str:
    words = _STOP.sub("", " " + " ".join(words.split())).strip(" ,.;")
    return words[:places.MAX_NAME]


def _route(raw):
    """(origin code or "", place as typed or "") from the text with the dates already cut out."""
    m = re.search(r"\bfrom ([A-Za-z][A-Za-z .'-]*?) to ([A-Za-z][^,.;]*)", raw, re.I) or re.search(r"\b([A-Z]{3}) to ([A-Za-z][^,.;]*)", raw)
    if m:
        origin = places.clean_iata(m.group(1)) if len(m.group(1).strip()) == 3 else ""
        if not origin:
            known = places.resolve(m.group(1))
            origin = known.iata if known and known.known else ""
        return origin, _tidy(m.group(2))
    m = re.search(r"\b(?:to|in|visit(?:ing)?) ([A-Z][^,.;]*)", raw)
    origin = re.search(r"\bfrom ([A-Z]{3})\b", raw)
    return (origin.group(1) if origin else ""), (_tidy(m.group(1)) if m else "")


def read(text, today=None) -> Ask:
    raw = " ".join(str(text or "").split())[:MAX_TEXT]
    today = today or catalog.today()
    (depart, return_), rest = _dates(raw, today)
    origin, place = _route(rest)
    adults, kid_ages, given, said, too_many = _party(rest.lower())
    senior, pet = _SENIOR.search(raw), _PET.search(raw)
    near, miles = _near(rest)
    if depart and return_ and (return_ - depart).days > catalog.MAX_NIGHTS:
        depart = return_ = None
    return Ask(place=place, origin=origin, depart=depart, return_=return_, adults=adults, kid_ages=kid_ages, ages_given=given,
               senior=_senior_word(senior.group(1)) if senior else "", pet=_pet_word(pet.group(1)) if pet else "",
               near=near, miles=miles, budget_cents=_budget(rest.lower()), party_given=said, too_many=too_many)


def _senior_word(word) -> str:
    word = word.lower()
    return {"seniors": "a senior", "senior": "a senior", "grandparents": "the grandparents"}.get(word, word if word.startswith("my ") else word.capitalize())


def _pet_word(word) -> str:
    word = word.lower()
    return "dog" if word.startswith(("dog", "pup")) else ("cat" if word.startswith("cat") else "pet")


def party_words(ask) -> str:
    kids = len(ask.kid_ages)
    if kids:
        return f"A family of {ask.travelers}"
    return "One adult" if ask.adults == 1 else f"{ask.adults} adults"


def with_words(ask) -> str:
    extra = [w for w in (ask.senior, f"the {ask.pet}" if ask.pet else "") if w]
    return "with " + " and ".join(extra) if extra else ""


def dates_words(ask) -> str:
    a, b = ask.depart, ask.return_
    if not (a and b):
        return ""
    return f"{a:%b} {a.day} to " + (f"{b.day}" if (a.year, a.month) == (b.year, b.month) else f"{b:%b} {b.day}")


def parts(ask) -> list:
    """[(key, words)] in reading order; a part with nothing to say is left out."""
    route = (f"{ask.origin} to {ask.place}" if ask.origin else f"to {ask.place}") if ask.place else ""
    near = (f"within {ask.miles} miles of {ask.near}" if ask.miles else f"near {ask.near}") if ask.near else ""
    budget = f"under {catalog.money(ask.budget_cents)}" if ask.budget_cents else ""
    found = (("party", party_words(ask)), ("with", with_words(ask)), ("route", route), ("dates", dates_words(ask)), ("near", near), ("budget", budget))
    return [(k, w) for k, w in found if w]


def write(ask) -> str:
    found = dict(parts(ask))
    head = " ".join(w for w in (found.get("party"), found.get("with")) if w)
    return ", ".join(w for w in (head, found.get("route"), found.get("dates"), found.get("near"), found.get("budget")) if w) + "."
