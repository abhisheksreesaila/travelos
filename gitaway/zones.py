"""Which time zone a trip lives in (F-057).

A small built-in table of IATA airport codes -> IANA zone names (US majors and the common international hubs), then the destination's US
state where it is obvious, then Los Angeles. `resolve` never raises; `valid` checks a zone name a person typed (with zoneinfo).
"""

import re
from zoneinfo import ZoneInfo

DEFAULT = "America/Los_Angeles"

_ET, _CT, _MT, _PT = "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"

_BY_ZONE = {
    _PT: "LAX SFO SJC OAK SAN SEA PDX LAS SMF SNA BUR ONT PSP SBA MRY FAT RNO GEG BOI LGB",
    _MT: "DEN SLC ABQ COS JAC ASE BZN MSO",
    "America/Phoenix": "PHX TUS",
    _CT: "ORD MDW DFW DAL IAH HOU AUS SAT MSP STL MCI MSY BNA MEM MKE OMA OKC TUL",
    _ET: "JFK LGA EWR BOS DCA IAD BWI PHL ATL MIA FLL MCO TPA CLT DTW CLE PIT RDU CMH IND CVG JAX RSW PBI SAV CHS BUF SYR ALB PVD BDL",
    "America/Anchorage": "ANC FAI JNU",
    "Pacific/Honolulu": "HNL OGG KOA LIH ITO",
    "America/Toronto": "YYZ YUL YOW",
    "America/Vancouver": "YVR",
    "America/Edmonton": "YYC YEG",
    "America/Mexico_City": "MEX GDL",
    "America/Cancun": "CUN",
    "Europe/London": "LHR LGW STN LTN MAN EDI GLA",
    "Europe/Dublin": "DUB",
    "Europe/Paris": "CDG ORY NCE LYS MRS",
    "Europe/Amsterdam": "AMS",
    "Europe/Brussels": "BRU",
    "Europe/Berlin": "FRA MUC BER HAM DUS",
    "Europe/Zurich": "ZRH GVA",
    "Europe/Madrid": "MAD BCN AGP PMI",
    "Europe/Lisbon": "LIS OPO",
    "Europe/Rome": "FCO MXP VCE NAP FLR",
    "Europe/Vienna": "VIE",
    "Europe/Copenhagen": "CPH",
    "Europe/Stockholm": "ARN",
    "Europe/Oslo": "OSL",
    "Europe/Helsinki": "HEL",
    "Europe/Athens": "ATH",
    "Europe/Istanbul": "IST SAW",
    "Atlantic/Reykjavik": "KEF",
    "Asia/Dubai": "DXB AUH",
    "Asia/Tokyo": "NRT HND KIX",
    "Asia/Seoul": "ICN",
    "Asia/Shanghai": "PVG PEK PKX CAN",
    "Asia/Hong_Kong": "HKG",
    "Asia/Singapore": "SIN",
    "Asia/Bangkok": "BKK",
    "Asia/Kolkata": "DEL BOM BLR MAA HYD",
    "Australia/Sydney": "SYD MEL CBR",
    "Pacific/Auckland": "AKL",
    "America/Sao_Paulo": "GRU GIG",
    "America/Bogota": "BOG",
    "America/Lima": "LIM",
    "America/Santiago": "SCL",
    "America/Argentina/Buenos_Aires": "EZE",
    "Africa/Johannesburg": "JNB CPT",
    "Africa/Cairo": "CAI",
    "Africa/Casablanca": "CMN",
}
AIRPORTS = {code: zone for zone, codes in _BY_ZONE.items() for code in codes.split()}

_STATES = {
    "CA": _PT, "WA": _PT, "OR": _PT, "NV": _PT, "AZ": "America/Phoenix", "UT": _MT, "CO": _MT, "NM": _MT, "ID": _MT, "MT": _MT, "WY": _MT,
    "TX": _CT, "IL": _CT, "MN": _CT, "MO": _CT, "LA": _CT, "TN": _CT, "WI": _CT, "OK": _CT, "AL": _CT, "IA": _CT, "KS": _CT, "NE": _CT, "AR": _CT, "MS": _CT,
    "NY": _ET, "FL": _ET, "MA": _ET, "DC": _ET, "GA": _ET, "NC": _ET, "SC": _ET, "VA": _ET, "PA": _ET, "NJ": _ET, "OH": _ET, "MI": _ET, "MD": _ET, "CT": _ET,
    "RI": _ET, "VT": _ET, "NH": _ET, "ME": _ET, "DE": _ET, "KY": _ET, "IN": _ET, "WV": _ET, "AK": "America/Anchorage", "HI": "Pacific/Honolulu",
}
_STATE_NAMES = {
    "california": "CA", "washington": "WA", "oregon": "OR", "nevada": "NV", "arizona": "AZ", "utah": "UT", "colorado": "CO", "new mexico": "NM",
    "texas": "TX", "illinois": "IL", "minnesota": "MN", "tennessee": "TN", "louisiana": "LA", "new york": "NY", "florida": "FL", "massachusetts": "MA",
    "georgia": "GA", "north carolina": "NC", "south carolina": "SC", "virginia": "VA", "pennsylvania": "PA", "new jersey": "NJ", "michigan": "MI",
    "ohio": "OH", "alaska": "AK", "hawaii": "HI",
}
_ABBR = re.compile(r",\s*([A-Z]{2})\b\.?\s*$")


def valid(name) -> str | None:
    """The IANA zone name if `name` is one zoneinfo knows, else None."""
    if not isinstance(name, str) or not name.strip():
        return None
    try:
        return ZoneInfo(name.strip()).key
    except Exception:  # unknown, malformed, or a path-like string
        return None


def from_state(destination) -> str | None:
    """The zone of a destination that ends in a US state ("Austin, TX") or names one ("Honolulu, Hawaii")."""
    text = (destination or "").strip()
    m = _ABBR.search(text)
    if m and m.group(1) in _STATES:
        return _STATES[m.group(1)]
    low = text.lower()
    for name, abbr in _STATE_NAMES.items():
        if re.search(rf"\b{name}\b", low):
            return _STATES[abbr]
    return None


def resolve(airport="", destination="") -> tuple:
    """(zone name, note): the zone of the arrival airport, else of the destination's state, else Los Angeles. `note` is "" when the zone was
    found, and says what was assumed when it was not."""
    code = (airport or "").strip().upper()
    if code in AIRPORTS:
        return AIRPORTS[code], ""
    found = from_state(destination)
    if found:
        return found, ""
    what = f"the airport {code}" if code else "this trip"
    return DEFAULT, (f"We do not know the time zone of {what}, so “today” and “up next” use Los Angeles time. "
                     "Add a line like “timezone: Europe/Paris” under “trip:” to set it.")
