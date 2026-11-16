"""The landing's search box (F-257, D-660..): one soft box you type a place into, and an autocomplete that builds a sentence the reader can read.

    suggest(text, home)   {"items": [{"text", "label", "hint", "kind"}], "say": words}: what the list under the box shows. "place" items are the known places the text could be
                          (gitaway/partners/places.py `matching`, only those a search can price here); once a place is whole, "party" and "when" items complete the sentence
                          ("San Diego · a family of 4 · Dec 12–16"). `text` is what the box holds after taking the item, so choosing is just setting the box. Text that is
                          no place we know is never guessed into one: `say` is "We don't know that place yet."
    search(text, home)    (the matrix's address, "") or ("", the problem in words): the box's sentence read by gitaway/tripsentence.py (the one reader) and the place by
                          places.lead; the matrix's own `v2sentence.address` then checks it like any other search.

The box's sentence is the place, then parts joined with " · " (a comma works too): "San Diego · a family of 4 · Dec 12–16", or typed freely, "san diego, 2 adults, Dec 12 to 16".
"""

import re
from dataclasses import replace
from datetime import timedelta

from gitaway import catalog, tripsentence, v2sentence
from gitaway.partners import places

SEP = " · "
UNKNOWN = "We don't know that place yet."
MAX_TEXT = 80
MAX_ITEMS = 7
POPULAR = ("San Diego", "Los Angeles", "New York", "Honolulu", "Lake Tahoe", "Las Vegas", "Orlando")
PARTY = (("a family of 4", "Mom, dad and two kids"), ("2 adults", "The two of us"), ("just me", "Solo"))
LEAD_DAYS, NIGHTS, STARTS = 28, 4, 4      # the first start offered is the first Saturday this far ahead (the matrix's own default); each next one a week later
_FROM = re.compile(r"\bfrom\s+([A-Za-z]{3})\b", re.I)
_STAND_IN = "to Anywhere, "                # the reader needs a place to read the rest around; the place itself is never read from here


def _known() -> dict:
    return {p.name: p for p in v2sentence.known_places()}


def popular() -> list:
    """The places the page shows as examples: the ones in POPULAR a search can price here."""
    known = _known()
    return [n for n in POPULAR if n in known]


def _place_item(p) -> dict:
    return {"text": p.name, "label": p.name, "hint": p.region + (f" · {p.iata}" if p.iata else ""), "kind": "place"}


def _day_range(a, b) -> str:
    return f"{a:%b} {a.day}–{b.day}" if (a.year, a.month) == (b.year, b.month) else f"{a:%b} {a.day}–{b:%b} {b.day}"


def _starts():
    first = catalog.today() + timedelta(days=LEAD_DAYS)
    first += timedelta(days=(5 - first.weekday()) % 7)
    return [first + timedelta(days=7 * i) for i in range(STARTS)]


def default_window(today=None) -> tuple:
    """(start, nights, flex) for a wish that names a place and no dates (F-268): the Friday at least LEAD_DAYS after `today`, 3 nights, give or take 2 days."""
    first = (today or catalog.today()) + timedelta(days=LEAD_DAYS)
    return first + timedelta(days=(4 - first.weekday()) % 7), 3, 2


def first_start():
    """The start day the matrix offers first (the first Saturday four weeks ahead): where a guide's "Plan this trip" starts its dates, for the reader to change in the sentence."""
    return _starts()[0]


def _split(rest) -> list:
    return [s.strip() for s in re.split(r"[·,]", rest) if s.strip()]


def _read(rest):
    return tripsentence.read(_STAND_IN + rest.replace("·", ","))


def _done(segment) -> bool:
    """Is this part whole: a party or a range of days the reader reads on its own?"""
    if _FROM.fullmatch(segment):
        return True
    ask = _read(segment)
    return ask.party_given or bool(ask.depart and ask.return_)


def _completions(base, have_party, have_dates, tail) -> list:
    """The parts that could come next after `base`, for what the person has begun to type (`tail`)."""
    cands = []
    if tail and _read(f"{tail} for {NIGHTS} nights").depart:        # a single day, "Dec 12": its ranges and its nights
        start = _read(f"{tail} for {NIGHTS} nights").depart
        cands = [("when", _day_range(start, start + timedelta(days=n)), f"{n} nights") for n in (3, 4, 5)] + [("when", f"{tail} for {n} nights", "") for n in (3, 4, 5)]
    else:
        if not have_party:
            cands += [("party", w, hint) for w, hint in PARTY]
        if not have_dates:
            cands += [("when", _day_range(s, s + timedelta(days=NIGHTS)), f"{NIGHTS} nights") for s in _starts()]
    if tail:
        low = tail.lower()
        cands = [c for c in cands if c[1].lower().startswith(low) or any(w.startswith(low) for w in c[1].lower().split())]
    return [{"text": f"{base}{SEP}{w}", "label": w, "hint": hint, "kind": kind} for kind, w, hint in cands]


def suggest(text, home) -> dict:
    text = " ".join(str(text or "").split())[:MAX_TEXT]
    text = re.sub(r"^(?:to|in)\s+", "", text, flags=re.I)
    known = _known()
    if not text:
        return {"items": [_place_item(known[n]) for n in popular()], "say": ""}
    hit = places.lead(text)
    options = [p for p in places.matching(text) if p.name in known]
    if hit is None or hit[0].name not in known or (not hit[1] and len(options) > 1):      # the place is not whole yet (or not one we can price): what it could be
        if options:
            exact = [p for p in options if p.name.lower() == text.lower()]
            return {"items": [_place_item(p) for p in [*exact, *(p for p in options if p not in exact)]][:MAX_ITEMS], "say": ""}
        return {"items": [], "say": UNKNOWN}
    place, rest = hit
    parts = _split(rest)
    tail = ""
    if parts and not _done(parts[-1]):      # the last part is still being typed
        tail = parts.pop()
    done = _read(", ".join(parts))
    base = SEP.join([place.name, *parts])
    items = _completions(base, done.party_given, bool(done.depart and done.return_), tail)
    if not home and not _FROM.search(rest):      # nobody has said where they fly from (off the showcase there is no default)
        items += [{"text": f"{base}{SEP}from {code}", "label": f"from {code}", "hint": city, "kind": "from"} for code, city in v2sentence.AIRPORTS[:3] if f"from {code}".lower().startswith(tail.lower())]
    return {"items": items[:MAX_ITEMS], "say": ""}


def search(text, home) -> tuple:
    """(the matrix's address, "") for the box's sentence, or ("", the problem in words)."""
    text = " ".join(str(text or "").split())[:MAX_TEXT]
    text = re.sub(r"^(?:to|in)\s+", "", text, flags=re.I)
    hit = places.lead(text)
    if hit is None or hit[0].name not in _known():
        return "", UNKNOWN if text else "Say where you would like to go."
    place, rest = hit
    said = _FROM.search(rest)
    rest = _FROM.sub("", rest)
    ask = _read(rest)
    no_dates = ask.depart is None and ask.return_ is None
    if no_dates and ask.unread == ("dates",):      # a place and nothing about when: a window to start from, shown in the results' sentence for the reader to change
        start, nights, flex = default_window()
        ask = replace(ask, depart=start, return_=start + timedelta(days=nights), flex=ask.flex if ask.flex is not None else flex)
    if ask.unread:
        from gitaway.pages.tripmatrix import MISSING      # here, not at the top: the page imports this module's neighbours
        return "", " ".join(MISSING[x] for x in ask.unread)
    form = {"to": place.name, "home": catalog.clean_home(said.group(1)) if said else home, "d": ask.depart.isoformat(), "n": (ask.return_ - ask.depart).days, "a": ask.adults,
            "k": ",".join(map(str, ask.kid_ages)), "b": ask.budget_cents // 100 if ask.budget_cents else "", "x": "" if ask.flex is None else str(ask.flex)}      # a string: "exactly" is 0, which v2sentence.address would read as absent
    return v2sentence.address(form)


def box_text(place="", depart=None, return_=None, adults=None, kids=0) -> str:
    """The sentence a link into the landing fills the box with (a creator's "Plan this trip": a place; a link back: the place, who and when)."""
    party = None if adults is None else (f"a family of {adults + kids}" if kids else ("just me" if adults == 1 else f"{adults} adults"))
    return SEP.join(x for x in (place, party, _day_range(depart, return_) if depart and return_ else "") if x)
