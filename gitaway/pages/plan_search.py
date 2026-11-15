"""What a search is, in words (F-195, F-198; trimmed by F-254 when the booking lanes page at /plan retired): the place, dates and party a request names, read the one way for the partner links
(/book/<lane>, gitaway/pages/partners.py), the trip matrix's old addresses (`matrix_href`) and the booking sheet's flight link. No page is drawn here."""

from dataclasses import replace
from urllib.parse import urlencode

from gitaway import catalog, showcase
from gitaway.partners import links, places

BAD_IATA = "Use a three-letter airport code, like RNO, or leave it empty."


def ahead(trip):
    """`trip` with its dates moved to the next ones worth searching, the same length, when they have passed (a stale link, or a bare /plan with the sample's old dates): a search for the past books nothing."""
    if trip.depart >= catalog.today():
        return trip
    from gitaway import publish  # here, not at the top: publish reads the community database
    depart, ret = publish.sample_dates(trip.nights + 1)
    return replace(trip, depart=depart, return_=ret)


def place_text(to="", focus="", place=""):
    """The place a request names: `place` as typed, else the catalog destination of a `to=` key (Disneyland for its focus), else ""."""
    if (place or "").strip():
        return place
    dest = next((x for x in catalog.DESTINATIONS if x.key == (to or "").strip().lower()), None)
    if not dest:
        return ""
    return "Disneyland" if focus == "disney" and dest.key == "la" else dest.name


def search_from(place="", iata="", d="", r="", a="", k="", to="", home="", focus=""):
    """(Search or None, {field: problem}) from a request's words. Dates and party as catalog.trip_from_url reads them (anything bad is the sample's, moved ahead); a bad airport
    code is a problem said on the page and kept out of every link."""
    errors = {}
    if (home or "").strip() and not catalog.clean_home(home):
        errors["home"] = catalog.BAD_HOME
    if (iata or "").strip() and not places.clean_iata(iata):
        errors["iata"] = BAD_IATA
    if (place or "").strip() and any((d, r, a, k)):      # typed in the form: a mistake is said, never silently swapped for the sample's dates and party
        try:
            catalog.parse_trip("", "la", d or "", r or "", a or "", k or "")
        except catalog.TripError as e:
            errors["trip"] = " ".join(dict.fromkeys(m for _, m in e.errors))
    trip = ahead(catalog.trip_from_url(d, r, a, k, to or "la", home, focus))
    if not (k or "").strip() and not showcase.on():      # F-210: off the showcase the sample family's kids never fill in a party nobody typed
        trip = replace(trip, kid_ages=())
    spot = places.resolve(place_text(to, focus, place), iata)
    return (links.Search(spot, trip.depart, trip.return_, trip.adults, trip.kid_ages, trip.home) if spot else None), errors


def query(search, via="", iata=""):
    """The address words that carry a search to /book and back to /plan."""
    q = {"place": search.place.name, "d": search.depart.isoformat(), "r": search.return_.isoformat(), "a": search.adults}
    if search.kid_ages:
        q["k"] = ",".join(map(str, search.kid_ages))
    if search.home:
        q["home"] = search.home
    if iata:
        q["iata"] = iata
    if via:
        q["via"] = via
    return q


def _href(link, q):
    return f"/book/{link.lane}?" + urlencode({"site": link.site, **q})


MAX_KIDS = catalog.MAX_TRAVELERS - 1


def matrix_href(q) -> str:
    """The trip matrix for the words of a search or of an old Where to? address (F-231: `/start` is gone): the place (`place`, or a sample city's `to`), `home` or `from`, `d`, `r`, `a`,
    and the kids as `k` or as a count `n` with one age `k1`.. each. The matrix checks them; what is not said it asks for. Where the matrix does not exist, the way in that does."""
    if not showcase.matrix_open():
        return showcase.planning_path()
    get = lambda name: str(q.get(name) or "").strip()       # noqa: E731
    k = get("k") or (kids_from(get("n"), [get(f"k{i}") for i in range(1, MAX_KIDS + 1)]) if get("n") else "")
    words = {"to": place_text(get("to"), get("focus"), get("place")), "home": (get("home") or get("from")).upper(), "d": get("d"), "r": get("r"), "a": get("a"), "k": k}
    return "/plan/matrix" + ("?" + urlencode({n: v for n, v in words.items() if v}) if any(words.values()) else "")


def kids_from(n, ages) -> str:
    """The `k` words for a trip from the form's kid count and one age picker per kid (F-198 review: a phone's number pad has no comma). An age not picked is "?", which the trip's
    own check refuses with its sentence; nothing typed, nothing given."""
    count = int(n) if str(n).isascii() and str(n).isdigit() else 0
    picked = [str(a).strip() for a in ages[:min(count, MAX_KIDS)]]
    return ",".join(a if a else "?" for a in picked)
