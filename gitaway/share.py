"""Share the traveler's trip as a scrapbook itinerary (F-022).

One tap turns the booked trip and its calendar activities into a public itinerary page at `/trips/<slug>` and a card in
the community hub. Only the days, the plans, their times and places, and the traveler's tags are shared. Private notes,
friends and their names, invites, prices and the booking reference never reach the page: it is rebuilt from the
bookings and activities each time and has no field for them. Flight and stay names do show; they help the next traveler.

The shared trip persists as a hub entry in the session (see gitaway.hub), per traveler, like forks. The page is rebuilt
from that traveler's current calendar, so it follows edits; there is no stored copy to leave stale. For the demo, every
traveler's shared trip held in this browser is listed and viewable by anyone using it.
"""

import hashlib

from gitaway import hub, session as ses, tripcal as cal
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
    """A stable public slug per traveler and booking that does not contain the booking reference (a salted hash)."""
    return "shared-" + hashlib.sha256(f"gitaway-share|{traveler_id}|{booking['id']}".encode()).hexdigest()[:10]


def _as(session, traveler_id):
    """A read-only view of the session as another demo traveler, so their booking and calendar can be read."""
    return {**{k: v for k, v in dict(session).items() if k not in ("user_id", "email")}, "user_id": traveler_id}


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


def build(session, tags=(), theme="sunset", traveler=None):
    """The scrapbook Itinerary for a traveler's booked trip (default: the signed-in one), or None when there is none."""
    if traveler:
        session = _as(session, traveler)
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
        slug=slug_for(ses.current_traveler(session).id, b), title=name, headline=f"{name}:", accent="our scrapbook", place=PLACE,
        lede=f"{len(days)} days in Los Angeles, planned on GitAway: {_lede_lanes(b)}everything we want to do, day by day.",
        days=days, tags=[Tag(hub.TAGS[k][0], hub.TAGS[k][1], hub.TAGS[k][2], (-3, 2, -1.5)[n % 3]) for n, k in enumerate(keys)],
        stats=[(f"{len(days)} days", cal.range_label(t.depart, t.return_)), (f"{plans} plans", "bookings and things to do"), ("0", "families forked it")],
        polaroids=[Polaroid(PIER, "Santa Monica Pier and beach", "the pier"), Polaroid(VENICE, "Venice Beach, Los Angeles", "Venice")],
        author="a traveler", theme=theme if theme in ("sunset", "pacific") else "sunset",
    )


def shared(session):
    """The hub entry of the signed-in traveler's shared trip for the trip they have booked now, or None."""
    t, b = ses.current_traveler(session), ses.booking(session)
    return hub.entry(session, slug_for(t.id, b)) if b else None


def publish(session, tags=None, theme=None) -> hub.HubCard:
    """Share (or re-share) the traveler's trip. Raises HubError with a message fit to show.

    With no `tags` or `theme` an existing share keeps its choices; a first share gets the defaults.
    A failure leaves the hub exactly as it was.
    """
    if not ses.current_traveler(session):
        raise HubError("Sign in to share your trip.")
    if not ses.booking(session):
        raise HubError("Book a trip first, then share it.")
    before = shared(session)
    tags = (tuple(before["g"]) if before else default_tags(session)) if tags is None else tuple(tags)
    theme = (before["c"] if before else "sunset") if theme is None else theme
    trip = build(session, tags, theme)
    old = session.get("hub")
    try:
        for e in hub.entries(session):
            if e.get("m") and e["s"] != trip.slug:
                hub.remove(session, e["s"])  # an older booking's page can no longer be rebuilt
        return hub.publish(session, slug=trip.slug, title=trip.title, place="Los Angeles", days=len(trip.days), author=trip.author,
                           tags=tags, theme=trip.theme, mine=True)
    except HubError:
        if old is None:
            session.pop("hub", None)
        else:
            session["hub"] = old
        raise


def is_live(session, traveler_id, slug) -> bool:
    """True while `slug` is still the page of that traveler's current booking (a rebooking makes the old page unbuildable)."""
    b = ses.booking(_as(session, traveler_id))
    return bool(b) and slug_for(traveler_id, b) == slug


def find(session, slug):
    """The Itinerary behind /trips/<slug> when it is a trip shared in this browser, else None. Built from its owner's booking."""
    for tid, e in hub.all_entries(session):
        if e["s"] == slug and e.get("m"):
            return build(session, e.get("g", ()), e.get("c", "sunset"), traveler=tid) if is_live(session, tid, slug) else None
    return None
