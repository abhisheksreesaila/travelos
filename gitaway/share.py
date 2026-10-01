"""Share the traveler's trip as a scrapbook itinerary (F-022).

One tap turns the booked trip and its calendar activities into a public itinerary page at `/trips/<slug>` and a card in
the community hub. Only the days, the plans, their times and places, and the traveler's tags are shared. Private notes,
friends and their names, invites, prices and the booking reference never reach the page: it is rebuilt from the
bookings and activities each time and has no field for them. Flight and stay names do show; they help the next traveler.

The shared trip is stored as a snapshot in the community database (see gitaway.community): the page is built from the
traveler's calendar when they publish, frozen, and served to anyone from the stored copy. Sharing again updates it.
"""

import hashlib
import hmac
import re

from gitaway import community, hub, session as ses, tripcal as cal
from gitaway.hub import HubError
from gitaway.itineraries import PIER, VENICE, Day, Itinerary, Polaroid, Stop, Tag

PLACE = "Los Angeles, California"
KIND_ICON = {"fun": "star", "food": "food", "outdoors": "tree", "culture": "sight", "travel": "car"}
_FILL = {"sun": "sun", "mint": "mint", "grape": "grape", "sky": "sky", "bubble": "bubble"}


def _lede_lanes(b) -> str:
    """"flights, the stay and " for the lanes the booking really has ("" when it has neither)."""
    parts = (["flights"] if cal.flight_of(b) else []) + (["the stay"] if cal.stay_of(b) else [])
    return (", ".join(parts) + " and ") if len(parts) == 2 else (parts[0] + " and " if parts else "")


def slug_for(traveler_id, booking) -> str:
    """A stable public slug per traveler and booking that does not contain the booking reference (an HMAC keyed with the server secret)."""
    return "shared-" + hmac.new(ses.cache_secret(), f"gitaway-share|{traveler_id}|{booking['id']}".encode(), hashlib.sha256).hexdigest()[:10]


def default_tags(session) -> tuple:
    """Kid friendly when the trip has kids on it, else nothing (the traveler picks)."""
    return ("kid",) if cal.trip("", ses.booking(session)).kid_ages else ()


def title_for(t) -> str:
    """The shared trip's title: the family's own for an imported trip, else the sample's."""
    return getattr(t, "name", "") or ("LA with the kids" if t.kid_ages else "LA trip")


def _la(t) -> bool:
    """The sample trip and any trip to Los Angeles: the only places the scrapbook has photos of."""
    return t.destination_name.casefold() in ("los angeles", "la")


_REGIONS = {x.strip() for x in (
    "alabama,alaska,arizona,arkansas,california,colorado,connecticut,delaware,florida,georgia,hawaii,idaho,illinois,indiana,iowa,kansas,kentucky,"
    "louisiana,maine,maryland,massachusetts,michigan,minnesota,mississippi,missouri,montana,nebraska,nevada,new hampshire,new jersey,new mexico,"
    "new york,north carolina,north dakota,ohio,oklahoma,oregon,pennsylvania,rhode island,south carolina,south dakota,tennessee,texas,utah,vermont,"
    "virginia,washington,west virginia,wisconsin,wyoming,district of columbia,usa,us,u.s.,u.s.a.,united states").split(",")}
_ZIP = re.compile(r"^(.*\s)?\d{4,5}(-\d{4})?$")


def _is_not_area(part) -> bool:
    """A trailing piece of an address that is not the city: a state (name or two letters), a zip, or the country."""
    low = part.casefold()
    return low in _REGIONS or bool(_ZIP.match(part)) or bool(re.fullmatch(r"[A-Za-z]{2}", part))


def area_of(address, fallback) -> str:
    """The city or area in a street address ("123 Ocean Ave, Santa Monica, CA 90401" -> "Santa Monica"), else `fallback`. Never the street."""
    parts = [p.strip() for p in (address or "").split(",") if p.strip()]
    while parts and _is_not_area(parts[-1]):  # drop a trailing zip, state or country
        parts.pop()
    return parts[-1] if len(parts) > 1 or (parts and not re.match(r"\d", parts[0])) else fallback


def _hotel_phrase(block, b, t) -> str:
    """"a hotel in Santa Monica": a shared page names the area, never the hotel. An imported trip's area is the city in the hotel's address
    (each of several hotels has its own); a demo trip's is the catalog stay's area."""
    if cal.is_imported(b):
        hotels = cal.plan_of(b).hotels
        n = int(m.group(1)) if (m := re.match(r"b-h(?:in|out)(\d+)$", block.id)) else 1
        area = area_of(hotels[min(n, len(hotels)) - 1].address if hotels else "", t.destination_name)
    else:
        stay = cal.stay_of(b)
        area = stay.headline if stay and stay.headline else t.destination_name
    return "a hotel downtown" if area.casefold() == "downtown" else f"a hotel in {area}"


def _stop(block, b, t) -> Stop:
    """A booked block as the public page shows it: no flight numbers and no hotel names (the times and the days stay)."""
    title = block.title
    if block.icon == "plane":
        dest = m.group(1) if (m := re.search(r"→\s*([A-Z]{3})", title)) else ""
        title = "Flight home" if block.id.startswith("b-back") else f"Flight to {dest}" if dest and block.id.startswith("b-out") else "Connecting flight"
    elif block.icon == "bed":
        title = f"{'Check in' if title.startswith('Check in') else 'Check out'} · {_hotel_phrase(block, b, t)}"
    return Stop(cal.fmt_time(block.at), title, block.icon or "star", "sun", booked=True)


def _plan(act) -> Stop:
    _, tint = cal.KINDS.get(act.kind, ("", "sun"))
    return Stop(cal.fmt_time(act.start), act.title, KIND_ICON.get(act.kind, "star"), _FILL.get(tint, "sun"))


def _day_title(i, last, stops) -> str:
    return "Touch down" if i == 0 else "Fly home" if i == last else "Out and about" if stops else "Free day"


def build(session, tags=(), theme="sunset"):
    """The scrapbook Itinerary for the signed-in traveler's booked trip, or None when there is none."""
    b = ses.booking(session)
    if not b:
        return None
    t = cal.trip("", b)  # the booked trip's own dates and length (an imported trip's real ones too), not the sample's
    blocks, acts = cal.booked_blocks(b, t), cal.activities(session)
    last = (t.return_ - t.depart).days
    days = []
    for i, d in enumerate(cal.days(t)):
        items = sorted([*((x.start, 0, _stop(x, b, t)) for x in blocks if x.day == i), *((a.start, 1, _plan(a)) for a in acts if a.day == i)],
                       key=lambda r: r[:2])
        stops = [r[2] for r in items]
        w = cal.weather_for(i)
        days.append(Day(i + 1, f"DAY {i + 1}", _day_title(i, last, stops), f"{w.temp_f}°F, {w.sky}", stops, collapsed=i >= 3))
    plans = sum(len(d.stops) for d in days)
    name = title_for(t)
    keys = [k for k in hub.TAGS if k in tags]
    la = _la(t)
    place = PLACE if la else t.destination_name
    return Itinerary(
        slug=slug_for(ses.current_traveler(session).id, b), title=name, headline=f"{name}:", accent="our scrapbook", place=place,
        lede=f"{len(days)} days in {'Los Angeles' if la else t.destination_name}, planned on GitAway: {_lede_lanes(b)}everything we want to do, day by day.",
        days=days, tags=[Tag(hub.TAGS[k][0], hub.TAGS[k][1], hub.TAGS[k][2], (-3, 2, -1.5)[n % 3]) for n, k in enumerate(keys)],
        stats=[(f"{len(days)} days", "from landing to flight home"), (f"{plans} plans", "bookings and things to do"), ("0", "families forked it")],
        polaroids=[Polaroid(PIER, "Santa Monica Pier and beach", "the pier"), Polaroid(VENICE, "Venice Beach, Los Angeles", "Venice")] if la else [],
        author="a traveler", theme=theme if theme in ("sunset", "pacific") else "sunset",
        **({} if la else {"route": place}),
    )


def shared(session):
    """The community row of the signed-in traveler's shared trip for the trip they have booked now, or None."""
    t, b = ses.current_traveler(session), ses.booking(session)
    row = community.get(slug_for(t.id, b)) if b else None
    return row if row and row["owner_user"] == t.id else None


def publish(session, tags=None, theme=None) -> hub.HubCard:
    """Share (or re-share) the traveler's trip: freeze it as a snapshot in the community database. Raises HubError with a message fit to show.

    With no `tags` or `theme` an existing share keeps its choices; a first share gets the defaults.
    The traveler has one shared trip at a time: sharing a newly booked trip takes the older one down.
    """
    t = ses.current_traveler(session)
    if not t:
        raise HubError("Sign in to share your trip.")
    if not ses.booking(session):
        raise HubError("Book a trip first, then share it.")
    before = shared(session)
    tags = (tuple(before["tags"]) if before else default_tags(session)) if tags is None else tuple(tags)
    theme = (before["theme"] if before else "sunset") if theme is None else theme
    trip = build(session, tags, theme)
    row = community.publish(session, trip, kind="shared", tags=[k for k in hub.TAGS if k in tags], theme=trip.theme)
    for old in community.rows(kind="shared", owner=t.id):
        if old["slug"] != trip.slug:
            community.unpublish(session, old["slug"])
    return hub._from_itinerary(community.trip_of(row))


def find(slug):
    """The Itinerary behind /trips/<slug> when it is a published shared trip, else None. Anyone can ask."""
    return community.find(slug, "shared")
