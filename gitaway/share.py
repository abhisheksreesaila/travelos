"""Share the traveler's trip as a scrapbook itinerary (F-022).

One tap turns the booked trip and its calendar activities into a public itinerary page at `/trips/<slug>` and a card in
the community hub. Only the days, the plans, their times and places, and the traveler's tags are shared. Private notes,
friends and their names, invites, prices and the booking itself never reach the page: the page is rebuilt from the
bookings and activities each time and has no field for them.

The shared trip persists as a hub entry in the session (see gitaway.hub), per traveler, like forks. The page is rebuilt
from the traveler's current calendar, so it follows edits; there is no stored copy to leave stale.
"""

from gitaway import hub, session as ses, tripcal as cal
from gitaway.hub import HubError
from gitaway.itineraries import PIER, VENICE, Day, Itinerary, Polaroid, Stop, Tag

PLACE = "Los Angeles, California"
KIND_ICON = {"fun": "star", "food": "food", "outdoors": "tree", "culture": "sight", "travel": "car"}
_FILL = {"sun": "sun", "mint": "mint", "grape": "grape", "sky": "sky", "bubble": "bubble"}


def slug_for(booking) -> str:
    return "shared-" + booking["id"].lower()


def default_tags(session) -> tuple:
    """Kid friendly when the trip has kids on it, else nothing (the traveler picks)."""
    return ("kid",) if cal.trip().kid_ages else ()


def title_for(t) -> str:
    return "LA with the kids" if t.kid_ages else "LA trip"


def _stop(block) -> Stop:
    return Stop(cal.fmt_time(block.start), block.title, block.icon or "star", "sun", booked=True)


def _plan(act) -> Stop:
    _, tint = cal.KINDS.get(act.kind, ("", "sun"))
    return Stop(cal.fmt_time(act.start), act.title, KIND_ICON.get(act.kind, "star"), _FILL.get(tint, "sun"))


def _day_title(i, last, stops) -> str:
    return "Touch down" if i == 0 else "Fly home" if i == last else "Out and about" if stops else "Free day"


def build(session, tags=(), theme="sunset"):
    """The scrapbook Itinerary for the signed-in traveler's booked trip, or None when signed out or nothing is booked."""
    b = ses.booking(session)
    if not b:
        return None
    t = cal.trip()
    blocks, acts = cal.booked_blocks(b, t), cal.activities(session)
    last = (t.return_ - t.depart).days
    days = []
    for i, d in enumerate(cal.days(t)):
        items = sorted([*(( x.start, 0, _stop(x)) for x in blocks if x.day == i), *((a.start, 1, _plan(a)) for a in acts if a.day == i)],
                       key=lambda r: r[:2])
        stops = [r[2] for r in items]
        w = cal.weather_for(i)
        days.append(Day(i + 1, f"{d.strftime('%a, %b').upper()} {d.day}", _day_title(i, last, stops), f"{w.temp_f}°F, {w.sky}", stops, collapsed=i >= 3))
    plans = sum(len(d.stops) for d in days)
    name = title_for(t)
    keys = [k for k in hub.TAGS if k in tags]
    return Itinerary(
        slug=slug_for(b), title=name, headline=f"{name}:", accent="our scrapbook", place=PLACE,
        lede=f"{len(days)} days in Los Angeles, planned on GitAway: flights, the stay and everything we want to do, day by day.",
        days=days, tags=[Tag(hub.TAGS[k][0], hub.TAGS[k][1], hub.TAGS[k][2], (-3, 2, -1.5)[n % 3]) for n, k in enumerate(keys)],
        stats=[(f"{len(days)} days", cal.range_label(t.depart, t.return_)), (f"{plans} plans", "bookings and things to do"), ("0", "families forked it")],
        polaroids=[Polaroid(PIER, "Santa Monica Pier and beach", "the pier"), Polaroid(VENICE, "Venice Beach, Los Angeles", "Venice")],
        author="a traveler", theme=theme if theme in ("sunset", "pacific") else "sunset",
    )


def shared(session):
    """The hub entry of the traveler's shared trip for the trip they have booked now, or None."""
    b = ses.booking(session)
    return hub.entry(session, slug_for(b)) if b else None


def publish(session, tags=None, theme="sunset") -> hub.HubCard:
    """Share (or re-share, with new tags or theme) the traveler's trip. Raises HubError with a message fit to show."""
    if not ses.current_traveler(session):
        raise HubError("Sign in to share your trip.")
    if not ses.booking(session):
        raise HubError("Book a trip first, then share it.")
    tags = default_tags(session) if tags is None else tuple(tags)
    trip = build(session, tags, theme)
    for e in hub.entries(session):
        if e.get("m") and e["s"] != trip.slug:
            hub.remove(session, e["s"])  # an older booking's page can no longer be rebuilt
    return hub.publish(session, slug=trip.slug, title=trip.title, place="Los Angeles", days=len(trip.days), author=trip.author,
                       tags=tags, theme=trip.theme, mine=True)


def find(session, slug):
    """The Itinerary behind /trips/<slug> when it is the signed-in traveler's own shared trip, else None."""
    e = hub.entry(session, slug)
    return build(session, e.get("g", ()), e.get("c", "sunset")) if e and e.get("m") and (shared(session) or {}).get("s") == slug else None
