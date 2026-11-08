"""A booking search becomes the family's trip (F-210): "Make this a trip" on /plan's lanes and on Where to?.

    read(params)              (Search or None, {field: problem}) from a request's words, strictly: a place must be named, the dates and party must be good and ahead
    start(session, search)    the family's trip for this search, made and opened for this person; returns its id (raises importer.SaveError)

The trip is the importer's own kind (like a trip made from a fork, gitaway/forks.py `start_trip`): the place, the dates and who is coming, and no flights, stay or car, since
nothing was booked through us. Trip details edits it like any other. Its id comes from the person and the search, so pressing the button twice makes one trip. The time zone is
the place's airport's, else the zone named after its town (Lisbon), else its state's, else Los Angeles (gitaway/zones.py).
"""

import hashlib

from gitaway import catalog, session as ses, zones
from gitaway.partners import places

PLACE_MISSING = "Type where you want to go, like Lisbon or Lake Tahoe."


def _kids(params) -> str:
    """The `k` words: as given, else from the kid count and one age picker per kid (Where to?'s and the lanes' forms)."""
    if params.get("k"):
        return params.get("k")
    if params.get("n"):
        from gitaway.pages import plan_search      # here: the pages import this module
        return plan_search.kids_from(params.get("n"), [params.get(f"k{i}", "") for i in range(1, plan_search.MAX_KIDS + 1)])
    return ""


def read(params):
    """(Search or None, {field: problem}). `params` is a request's form or query (Where to?'s fields `from`, `n`, `k1`.., or the lanes' `home`, `k`)."""
    from gitaway.pages import plan_search
    get = lambda name: str(params.get(name) or "").strip()       # noqa: E731
    place = plan_search.place_text(get("to"), get("focus"), get("place"))
    d, r, a, k, home = get("d"), get("r"), get("a"), _kids(params), (get("home") or get("from")).upper()
    errors = {}
    if not place.strip():
        errors["place"] = PLACE_MISSING
    if home and not catalog.clean_home(home):
        errors["home"] = catalog.BAD_HOME
    try:
        catalog.parse_trip("", "la", d, r, a, k, check_past=True)
    except catalog.TripError as e:
        for field, msg in e.errors:
            errors.setdefault(field, msg)
    if errors:
        return None, errors
    search, problems = plan_search.search_from(place, get("iata"), d, r, a, k, "", home, get("focus"))
    return search, problems


def words(search, iata="") -> dict:
    """The address words that carry `search` (to /trip/new, /plan and back)."""
    from gitaway.pages import plan_search
    return plan_search.query(search, iata=iata)


def destination(place) -> str:
    """"Lake Tahoe, California": the place and its region, unless the name already says it."""
    return f"{place.name}, {place.region}" if place.region and place.region.lower() not in place.name.lower() else place.name


def zone(place) -> str:
    if place.iata in zones.AIRPORTS:
        return zones.AIRPORTS[place.iata]
    return zones.from_state(destination(place)) or zones.from_city(place.city) or zones.from_city(place.name) or zones.resolve("", destination(place))[0]     # the state first: Paris, Texas is not Europe/Paris


def token(user_id, search) -> str:
    key = "|".join(map(str, ("search", user_id, search.place.name.casefold(), search.depart, search.return_, search.adults, search.kid_ages)))
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def plan_of(session, search):
    from gitaway import tripimport as ti
    me = ses.current_traveler(session)
    people = [ti.Traveler(((me.name if me else "") or "Traveler")[:40] if i == 0 else f"Adult {i + 1}") for i in range(search.adults)] + \
             [ti.Traveler(f"Kid {i + 1}", "", age) for i, age in enumerate(search.kid_ages)]
    return ti.Plan(title=f"Trip to {search.place.name}"[:60], destination=destination(search.place)[:60], start=search.depart, end=search.return_, booked_on="elsewhere",
                   itinerary="", travelers=tuple(people), timezone=zone(search.place))


def start(session, search) -> str:
    """Make (or reopen) the family's trip for `search` and open it for this person. Returns the trip id; raises importer.SaveError (signed out, too many trips)."""
    from gitaway import importer      # here: the importer reads the family through gitaway.session
    me = ses.current_traveler(session)
    if not me:
        raise importer.SaveError("Sign in to make this a trip.")
    return importer.save(session, plan_of(session, search), token(me.id, search))
