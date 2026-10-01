"""Creator link import (F-023): a pasted YouTube or Instagram link becomes a scrapbook itinerary the creator edits and publishes.

Nothing is fetched and no AI runs. The "transcript" is one of a few fixtures picked by a hash of the link, so the same link
always gives the same draft. The draft is never trusted: the creator answers a few questions (which days, who it suits, best
season), edits five spots and ticks two boxes before Submit.

The five editable spots are FIELDS: the title, the highlight of the first and of the second day, a tip, and the cover photo.
Everything else (days, stops, times, the source card) is laid out for them, and the server reads no other field.

The draft lives in the signed cookie session, kept tiny because the cookie is small (`session.BUDGET`). It stores only the
link, the answers and the creator's edits; the rest is rebuilt from the fixture each time.

    session["cr"]  = {"u": link, "a": {"d": "012", "w": "kp", "s": "summer"}, "e": {"t": ..., "h1": ..., "h2": ..., "p": ..., "c": ...}, "k": "12"}
                     (a = answers, e = edits that differ from the draft, k = both boxes ticked)

Drafts stay per device. Publishing (F-041) freezes the page as a snapshot in the community database (gitaway.community,
kind "creator", the record kept beside it as `meta`), so the trip shows in the hub and at /trips/<slug> for everyone.
"""

import hashlib
from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from gitaway import community, hub, session as ses
from gitaway.hub import HubError
from gitaway.itineraries import PIER, VENICE, Day, Itinerary, Polaroid, Source, Stop, Tag, safe_href

FIELDS = ("title", "hl1", "hl2", "tip", "cover")     # the only spots a creator can edit; the server reads nothing else
MAX = {"title": 60, "hl1": 70, "hl2": 70, "tip": 140}
KEYS = {"title": "t", "hl1": "h1", "hl2": "h2", "tip": "p", "cover": "c"}
MAX_LINK = 300
MAX_TRIPS = 2                                          # creator trips per traveler in this browser
FULL = "This demo is full. Delete something from your calendar to make room."
SEASONS = {"spring": ("68°F", "mild and bright", "Spring"), "summer": ("78°F", "sunny and warm", "Summer"),
           "fall": ("74°F", "warm and clear", "Fall"), "winter": ("64°F", "cool, a little rain", "Winter")}
COVERS = {"pier": (PIER, "Santa Monica Pier and beach"), "venice": (VENICE, "Venice Beach, Los Angeles"), "none": ("", "")}
COVER_LABELS = {"pier": "The pier", "venice": "Venice", "none": "No photo"}
HOSTS = {"youtube.com": "YouTube", "www.youtube.com": "YouTube", "m.youtube.com": "YouTube", "youtu.be": "YouTube",
         "instagram.com": "Instagram", "www.instagram.com": "Instagram"}
_WHO = {k[0]: k for k in hub.TAGS}                     # "k" -> "kid", "p" -> "pet", "c" -> "couple"
_FILL = ("sun", "mint", "grape")


class LinkError(ValueError):
    """A link the demo will not take; the message is fit to show the creator."""


@dataclass(frozen=True)
class Link:
    url: str
    platform: str


def parse_link(raw) -> Link:
    """The link when it is an http(s) YouTube or Instagram address to one video or post, else LinkError with a friendly message."""
    url = raw.strip() if isinstance(raw, str) else ""
    if not url:
        raise LinkError("Paste the link to your video or post first.")
    if len(url) > MAX_LINK or any(c in url for c in "\x00\r\n\t ") or any(ord(c) < 32 for c in url):
        raise LinkError("That link doesn't look right. Copy it straight from the share button.")
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = parts.port
    except ValueError:
        raise LinkError("That link doesn't look right. Copy it straight from the share button.") from None
    if port is not None:
        raise LinkError("Paste the plain link, without a port number.")
    if parts.scheme not in ("http", "https") or "@" in parts.netloc:
        raise LinkError("Paste a web link that starts with https://, from YouTube or Instagram.")
    platform = HOSTS.get(host.lower())
    if not platform:
        raise LinkError("GitAway can read YouTube and Instagram links for now. Paste one of those.")
    if parts.path in ("", "/"):
        raise LinkError("That link goes to the home page. Paste the link to one video or post.")
    return Link(url, platform)


# ---------- the simulated transcript ----------

@dataclass(frozen=True)
class DayFx:
    title: str
    highlight: str
    stops: tuple          # (time, minutes:seconds into the video, title, icon, bubble tint)


@dataclass(frozen=True)
class Fixture:
    key: str
    creator: str
    handle: str
    video: str
    mins: int
    title: str
    lede: str
    tip: str
    thumb: str
    cover: str
    guess: dict           # what the "transcript" suggested: days, who, season
    days: tuple


FIXTURES = (
    Fixture("family", "Joy & Mateo Travel", "joyandmateo", "LA with two little ones: what we'd do again", 14, "Sandcastles & Ferris wheels",
            "Three easy beach days for a family with little ones: a pier, a boardwalk and a park with steam trains.",
            "Book the Pacific Park wristbands online and go before 11, while the lines are short.", VENICE, "pier",
            {"d": "012", "w": "k", "s": "summer"}, (
                DayFx("Pier day", "The carousel, three times.", (
                    ("10:00 AM", "1:12", "Santa Monica Pier and the Ferris wheel", "star", "bubble"),
                    ("1:30 PM", "3:48", "Fish tacos by the water", "food", "mint"))),
                DayFx("Venice, slowly", "Watch the skaters from the rail.", (
                    ("9:30 AM", "5:20", "Venice Canals stroll", "waves", "mint"),
                    ("1:00 PM", "7:55", "Boardwalk and the skate park", "sun", "sun"))),
                DayFx("Park and stars", "The little steam train is free to walk up to.", (
                    ("10:30 AM", "10:40", "Travel Town steam trains", "train", "grape"),
                    ("5:00 PM", "12:30", "Observatory at sunset", "sight", "grape"))))),
    Fixture("dog", "Carmen on the Go", "carmenonthego", "A dog's guide to Los Angeles", 11, "Paws on the Pacific",
            "Three days with a dog who has strong opinions about beaches, patios and trails.",
            "Pack a collapsible bowl. Patios say dog friendly but rarely put the water out.", PIER, "venice",
            {"d": "012", "w": "p", "s": "spring"}, (
                DayFx("Beach walk", "Leash on, tail wagging.", (
                    ("8:00 AM", "0:55", "Early walk on Venice Beach", "waves", "mint"),
                    ("12:00 PM", "2:40", "Patio lunch in Venice", "food", "sun"))),
                DayFx("Hike day", "Go early. It gets hot fast.", (
                    ("9:00 AM", "4:10", "Runyon Canyon loop", "tree", "mint"),
                    ("2:00 PM", "6:05", "Dog park break in Silver Lake", "sun", "sun"))),
                DayFx("Slow Sunday", "Everyone at the market wanted to say hi.", (
                    ("10:00 AM", "8:30", "Farmers market with the pup", "food", "bubble"),
                    ("3:00 PM", "9:50", "Sunset at the pier", "pin", "sky"))))),
    Fixture("couple", "Dee & Jo", "deeandjo", "LA for two on a shoestring", 22, "Golden hours, just us two",
            "Three unhurried days for a couple: late breakfasts, golden hours and one very good sunset.",
            "Sunset spots fill an hour early. Bring a blanket and arrive with snacks.", PIER, "pier",
            {"d": "012", "w": "c", "s": "fall"}, (
                DayFx("Arrive and wander", "Share the lemon ricotta pancakes.", (
                    ("11:00 AM", "1:40", "Brunch in Silver Lake", "food", "sun"),
                    ("4:30 PM", "5:15", "Golden hour at Griffith Park", "sight", "grape"))),
                DayFx("Beach, no alarm", "We had nowhere to be and it showed.", (
                    ("10:30 AM", "9:05", "Coffee and the Venice Canals", "waves", "mint"),
                    ("5:30 PM", "12:20", "Sunset on Santa Monica Pier", "pin", "bubble"))),
                DayFx("Museums and a long dinner", "Gardens first, then the view.", (
                    ("11:00 AM", "16:45", "The Getty Center gardens", "sight", "grape"),
                    ("7:00 PM", "19:10", "Dinner in Los Feliz", "food", "bubble"))))),
)


def channel_url(fx, platform) -> str:
    """The creator's channel on the platform the link came from. Always an https address."""
    return f"https://www.youtube.com/@{fx.handle}" if platform == "YouTube" else f"https://www.instagram.com/{fx.handle}"


def fixture_for(url) -> Fixture:
    """The same link always picks the same fixture: a hash of the link, not a random choice."""
    return FIXTURES[int(hashlib.sha256(url.strip().encode()).hexdigest(), 16) % len(FIXTURES)]


# ---------- a draft ----------

@dataclass(frozen=True)
class Draft:
    url: str
    platform: str
    fx: Fixture
    kept: tuple           # indexes of the fixture days that stay
    who: tuple            # keys of hub.TAGS
    season: str
    title: str
    hl: tuple             # highlights of the first and second kept day (up to two)
    tip: str
    cover: str
    answered: bool        # the creator has saved answers or edits
    confirmed: bool       # both boxes ticked
    ticks: str = ""       # which boxes are ticked: "1", "2" or "12"

    @property
    def tags(self):
        return self.who

    @property
    def days(self):
        return [self.fx.days[i] for i in self.kept]


def _default_hl(fx, kept, slot):
    return fx.days[kept[slot]].highlight


def resolve(rec) -> Draft:
    """The draft for a stored record (or just {"u": link}). Pure; everything not edited comes from the fixture."""
    link = parse_link(rec["u"])
    fx = fixture_for(link.url)
    a, e = rec.get("a") or {}, rec.get("e") or {}
    n = len(fx.days)
    kept = tuple(int(c) for c in a.get("d", fx.guess["d"]) if c.isdigit() and int(c) < n) or tuple(range(n))
    who = tuple(_WHO[c] for c in a.get("w", fx.guess["w"]) if c in _WHO)
    season = a.get("s") if a.get("s") in SEASONS else fx.guess["s"]
    hl = tuple(e.get(f"h{i + 1}") or _default_hl(fx, kept, i) for i in range(min(2, len(kept))))
    cover = e.get("c") if e.get("c") in COVERS else fx.cover
    return Draft(link.url, link.platform, fx, kept, who, season, e.get("t") or fx.title, hl, e.get("p") or fx.tip, cover,
                 bool(a or e), rec.get("k", "") == "12", rec.get("k", ""))


def draft_for(url) -> Draft:
    return resolve({"u": url})


def get_rec(session):
    rec = session.get("cr")
    return dict(rec) if isinstance(rec, dict) and rec.get("u") else None


def minutes_left(rec) -> int:
    """The gentle progress line: 5 minutes before a link, then 3, 2 once they have answered or edited, 1 when both boxes are ticked."""
    if not rec:
        return 5
    if rec.get("k") == "12":
        return 1
    return 2 if (rec.get("a") or rec.get("e")) else 3


# ---------- the session ----------

def start(session, url):
    """Begin a draft from an already validated link (replaces any earlier draft). Raises HubError when the cookie has no room."""
    _write(session, {"u": url})


def _write(session, rec):
    """Set the draft, or refuse and leave the session without an oversized state."""
    before = session.get("cr")
    session["cr"] = rec
    if _too_big(session):
        if before is None:
            session.pop("cr", None)
        else:
            session["cr"] = before
        if _too_big(session):
            session.pop("cr", None)   # even the old draft no longer fits: drop it rather than keep an oversized cookie
        raise HubError(FULL)


def _clean(value, limit):
    return " ".join(str(value).split())[:limit]


def _list(value):
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else [str(value)] if value else []


def save(session, data):
    """Apply what the draft form posted. Reads only the answers, the five FIELDS and the two boxes; anything else is ignored.

    Raises HubError when there is no draft, or when the cookie has no room left (the draft is then unchanged).
    """
    rec = get_rec(session)
    if not rec:
        raise HubError("Paste a link first.")
    if not data.get("form"):
        return
    old = resolve(rec)
    n = len(old.fx.days)
    days = _list(data.get("days"))
    rec["a"] = {"d": "".join(str(i) for i in range(n) if str(i) in days) or "".join(str(i) for i in range(n)),
                "w": "".join(c for c, k in _WHO.items() if k in _list(data.get("who"))),
                "s": data.get("season") if data.get("season") in SEASONS else old.season}
    e = dict(rec.get("e") or {})

    def put(field, default):
        if field not in data:
            return
        value = _clean(data[field], MAX[field])
        if value and value != default:
            e[KEYS[field]] = value
        else:
            e.pop(KEYS[field], None)

    put("title", old.fx.title)
    put("tip", old.fx.tip)
    for slot, field in enumerate(("hl1", "hl2")):
        if slot < len(old.kept):
            put(field, _default_hl(old.fx, old.kept, slot))
    if "cover" in data:
        if data["cover"] in COVERS and data["cover"] != old.fx.cover:
            e["c"] = data["cover"]
        else:
            e.pop("c", None)
    rec["e"] = {k: v for k, v in e.items() if v}
    if not rec["e"]:
        rec.pop("e")
    ticks = ("1" if data.get("ok1") else "") + ("2" if data.get("ok2") else "")
    if ticks:
        rec["k"] = ticks
    else:
        rec.pop("k", None)
    _write(session, rec)


def _too_big(session):
    import json
    return len(json.dumps(dict(session))) > ses.BUDGET


def slug_for(traveler_id, url) -> str:
    return "creator-" + hashlib.sha256(f"gitaway-creator|{traveler_id}|{url}".encode()).hexdigest()[:8]


def published(session, traveler_id) -> dict:
    """{slug: record} of the creator trips this person has published (the records live with the snapshot in the community database)."""
    return {r["slug"]: r["meta"] for r in community.rows(kind="creator", owner=traveler_id)}


def publish(session) -> hub.HubCard:
    """Publish the confirmed draft to the community database. Raises HubError with a message fit to show."""
    t = ses.current_traveler(session)
    if not t:
        raise HubError("Sign in to publish your trip.")
    rec = get_rec(session)
    if not rec:
        raise HubError("Paste a link first.")
    if rec.get("k") != "12":
        raise HubError("Tick both boxes first: that it is accurate, and that you give GitAway permission to publish it.")
    d = resolve(rec)
    slug = slug_for(t.id, d.url)
    if len([s for s in published(session, t.id) if s != slug]) >= MAX_TRIPS:
        raise HubError(f"You have {MAX_TRIPS} creator trips here already. This demo keeps it small.")
    stored = {k: v for k, v in rec.items() if k != "k"}
    row = community.publish(session, trip(stored, slug), kind="creator", tags=list(d.who), meta=stored)
    session.pop("cr", None)
    return hub._from_itinerary(community.trip_of(row))


# ---------- the page behind /trips/<slug> ----------

def trip(rec, slug) -> Itinerary:
    """The scrapbook Itinerary for a creator record."""
    d = resolve(rec)
    temp, sky, _label = SEASONS[d.season]
    days = []
    for n, fxd in enumerate(d.days, start=1):
        stops = [Stop(t, title, kind, bubble, meta=f"At {at} in the video") for t, at, title, kind, bubble in fxd.stops]
        if n <= len(d.hl) and stops:
            stops[0] = replace(stops[0], note=d.hl[n - 1])
        days.append(Day(n, f"DAY {n}", fxd.title, f"{temp}, {sky}", stops, collapsed=n > 3))
    stops_total = sum(len(x.stops) for x in days)
    tags = [Tag(hub.TAGS[k][0], hub.TAGS[k][1], hub.TAGS[k][2], (-3, 2, -1.5)[i % 3]) for i, k in enumerate(d.who)]
    tags.append(Tag(f"Best in {d.season}", "sky", "clock", (2, -1.5, -3)[len(tags) % 3]))
    photo, alt = COVERS[d.cover]
    polaroids = [Polaroid(src, a, cap) for src, a, cap in [(PIER, COVERS["pier"][1], "the pier"), (VENICE, COVERS["venice"][1], "Venice")]]
    if d.cover == "venice":
        polaroids.reverse()
    thumb = d.fx.thumb
    return Itinerary(
        slug=slug, title=d.title, headline=f"{d.title}, seen on", accent=d.platform, place="Los Angeles, California",
        lede=f"{d.fx.lede} Creator's tip: {d.tip}", days=days, tags=tags,
        stats=[(f"{len(days)} days", f"best in {d.season}"), (f"{stops_total} stops", "from the video"), (f"{d.fx.mins} min", "of video"), ("0", "families forked it")],
        source=Source(f"{d.fx.creator} · {d.platform} · {d.fx.mins} min", d.fx.video, thumb, COVERS["venice" if thumb == VENICE else "pier"][1],
                      channel_url(d.fx, d.platform), "Visit the channel"),
        polaroids=polaroids if photo else [], weather=(temp, sky), author=d.fx.creator, route="Los Angeles, California", theme="sunset")


def find(slug):
    """The Itinerary behind /trips/<slug> when it is a published creator trip, else None. Anyone can ask."""
    return community.find(slug, "creator")
