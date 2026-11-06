"""Publish a family's trip as a creator page (F-181): photos, a note per day, tips, under the person's own name.

The family keeps a draft per trip (`publications`, gitaway.familydb_publish): which photos, what to say, the cover, the stickers, the title and the
name shown. Publishing builds a public **snapshot** (gitaway.community, kind "scrapbook") and re-encoded copies of the picked photos
(`<data folder>/public/<slug>/`); unpublishing deletes both. Publishing again replaces them.

What reaches the public, and only this (the snapshot is built from these fields and has no others):
  title, creator name and handle, place (the destination's name), stickers, a day-by-day list of the trip's stops (flights as "Flight to LAX", a stay as
  "a hotel in <area>", a car as an airport or an area; plans by their titles and clock times, never their notes), the creator's day notes and tips,
  the picked photos (public copies) with the plan title as caption when there is one.
Never: confirmation numbers, calendar dates, flight numbers, hotel names or street addresses, prices, who is in the family, chat, photo captions,
the camera's EXIF or position (the public copy is rebuilt from the pixels), the photo's author. The stops come from gitaway.share, which already follows
F-046 (no dates, no hotel names) and is tested for it; this module adds the creator's own words and photos, which the preview shows exactly.
"""

import json
import logging
import re
import secrets
import shutil
from datetime import date, timedelta
from pathlib import Path

from gitaway import auth, catalog, community, familydb, hub, members, photos, session as ses, share, tripcal as cal
from gitaway.hub import HubError
from gitaway.itineraries import Day, Itinerary, Polaroid, Tag

log = logging.getLogger("gitaway.publish")

MAX_TITLE = 60
MAX_NAME = 40
MAX_NOTE = 300
MAX_TIPS = 5
MAX_TIP = 140
MAX_PHOTOS = 24
SIZES = ("display", "thumb")
_NAME = re.compile(r"^[0-9a-f]{16}$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,70}$")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
NEEDS_EDITOR = "Only an editor or admin of the family can publish a trip. Ask a family admin to make you an editor."

# the words that put a destination on one of the catalog's places (where "Plan this trip" can go), and the airports that serve them. Only names that are that place and no other:
# no "disney" (Walt Disney World, Disneyland Paris, Tokyo), no "california" (Tahoe, Yosemite, San Francisco and Napa are California too, and San Diego is not Los Angeles),
# no "hawaii" (Maui, Kauai and the Big Island are Hawaii, but HNL is on Oahu). Matched as whole words ("queens" is not "Queenstown"). F-194.
_PLACES = (("la", r"los angeles|anaheim|(?<!hong kong )disneyland resort(?! paris)|santa monica|burbank|pasadena|orange county|hollywood|long beach", {"LAX", "BUR", "SNA", "LGB"}),
           ("sd", r"san diego|coronado|la jolla", {"SAN"}),
           ("hi", r"honolulu|oahu|waikiki", {"HNL"}),
           ("nyc", r"new york|manhattan|brooklyn|queens", {"JFK", "EWR", "LGA"}))


def root() -> Path:
    """The folder the public photo copies live in, on the data volume (absolute, like photos.root)."""
    return auth.data_dir() / "public"


def _says(words, text) -> bool:
    return bool(re.search(rf"\b(?:{words})\b", str(text).casefold()))


def place_key(destination, airports=()) -> str:
    """The catalog place ("la", "sd", "hi", "nyc") a destination belongs to, or "" when it is none of them (then there is no "Plan this trip")."""
    codes = {a.upper() for a in airports}
    for key, words, airport_codes in _PLACES:
        if _says(words, destination) or airport_codes & codes:
            return key
    return ""


def names_place(key, text) -> bool:
    """Does `text` (a whole post) name a place of this catalog place, by the same words `place_key` uses?"""
    return any(k == key and _says(words, text) for k, words, _codes in _PLACES)


# ---- the draft ---------------------------------------------------------------------------------------------------------

def _loads(raw, default):
    try:
        got = json.loads(raw or "")
    except ValueError:
        return default
    return got if isinstance(got, type(default)) else default


def _draft_of(row, fam, t):
    b = fam.booking()      # the name shown starts as the first name only; the person chooses to show more (F-182)
    return {
        "trip_id": fam.trip_id, "slug": row["slug"] if row else "", "title": row["title"] if row and row["title"] else share.title_for(t),
        "name": row["name"] if row and row["name"] else (fam.traveler.name.split() or [""])[0], "cover": row["cover"] if row else "",
        "stickers": _loads(row["stickers"], []) if row else (["kid"] if t.kid_ages else []),
        "notes": _loads(row["notes"], {}) if row else {}, "tips": _loads(row["tips"], []) if row else [], "photos": _loads(row["photos"], []) if row else [],
        "copies": _loads(row["copies"], {}) if row else {}, "published_by": row["published_by"] if row else "", "published_at": row["published_at"] if row else "",
        "booked": b is not None}


def get(session) -> dict | None:
    """The draft of the trip this request works on (defaults for a trip never drafted), or None when signed out or there is no trip."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id or fam.booking() is None:
            return None
        row = familydb.row(fam.db, "SELECT * FROM publications WHERE trip_id = :t", t=fam.trip_id)
        return _draft_of(row, fam, cal.trip_of(fam.booking()))


def _line(text, limit) -> str:
    return " ".join(str(text or "").split())[:limit]


def _check_text(*texts):
    for x in texts:
        if _EMAIL.search(x):
            raise HubError("Take the email address out: your page is public, and so is everything you write on it.")


def save(session, data) -> dict:
    """Keep the editor's choices for the open trip. `data`: title, name, cover, stickers (list), photos (list of ids), note_<n> per day, tip (list).
    Anything not of this trip is dropped (a photo id must be one of the trip's photos). Raises HubError with a message fit to show."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id or fam.booking() is None:
            raise HubError("Open the trip you want to publish first.")
        t = cal.trip_of(fam.booking())
        title, name = _line(data.get("title"), MAX_TITLE), _line(data.get("name"), MAX_NAME)
        n_days = (t.return_ - t.depart).days + 1
        notes = {str(n): _line(data.get(f"note_{n}"), MAX_NOTE) for n in range(1, n_days + 1)}
        notes = {k: v for k, v in notes.items() if v}
        tips = [x for x in (_line(x, MAX_TIP) for x in (data.get("tip") or [])) if x][:MAX_TIPS]
        _check_text(title, name, *notes.values(), *tips)
        mine = {r["id"] for r in familydb.rows(fam.db, "SELECT id FROM photos WHERE trip_id = :t", t=fam.trip_id)}
        picked = list(dict.fromkeys(p for p in (data.get("photos") or []) if p in mine))[:MAX_PHOTOS]
        cover = data.get("cover") if data.get("cover") in picked else (picked[0] if picked else "")
        stickers = [k for k in hub.TAGS if k in (data.get("stickers") or [])]
        old = familydb.row(fam.db, "SELECT * FROM publications WHERE trip_id = :t", t=fam.trip_id)
        slug = old["slug"] if old else f"{community.slugify(title, 30) or 'trip'}-{secrets.token_hex(3)}"
        with familydb.transaction(fam.db):
            familydb.lock(fam.db)
            if old:
                familydb.run(fam.db, "UPDATE publications SET title = :ti, name = :n, cover = :c, stickers = :s, notes = :no, tips = :tp, photos = :p, updated_at = :u WHERE trip_id = :t",
                             ti=title, n=name, c=cover, s=json.dumps(stickers), no=json.dumps(notes), tp=json.dumps(tips), p=json.dumps(picked), u=familydb.now(), t=fam.trip_id)
            else:
                familydb.run(fam.db, "INSERT INTO publications (trip_id, slug, title, name, cover, stickers, notes, tips, photos, copies, published_by, published_at, updated_at) "
                             "VALUES (:t, :sl, :ti, :n, :c, :s, :no, :tp, :p, '{}', '', '', :u)",
                             t=fam.trip_id, sl=slug, ti=title, n=name, c=cover, s=json.dumps(stickers), no=json.dumps(notes), tp=json.dumps(tips), p=json.dumps(picked), u=familydb.now())
        row = familydb.row(fam.db, "SELECT * FROM publications WHERE trip_id = :t", t=fam.trip_id)
        return _draft_of(row, fam, t)


# ---- what strangers will see -------------------------------------------------------------------------------------------

def _day_of(photo, t) -> int:
    """The day index (0 is the first) a photo belongs to: the day it was taken, kept inside the trip's days."""
    try:
        d = (date.fromisoformat(photo["taken_date"]) - t.depart).days
    except ValueError:
        d = 0
    return min(max(d, 0), (t.return_ - t.depart).days)


def _alt(n, photo) -> str:
    return f"Photo from day {n}" + (f", {photo['plan_title']}" if photo["plan_title"] else "")


def build(session, d, src, handle="") -> Itinerary:
    """The public page of the open trip as an Itinerary. `src(photo)` gives each picked photo's address (the family's private one for the preview,
    the public copy once published), so the preview is the same page. Needs the trip's photos, so call it inside no other family block."""
    b = ses.booking(session)
    t = cal.trip_of(b)
    blocks, acts = cal.booked_blocks(b, t), cal.activities(session)
    by_id = {p["id"]: p for p in photos.listing(session)}
    shots = {pid: by_id[pid] for pid in d["photos"] if pid in by_id}
    last = (t.return_ - t.depart).days
    days = []
    for i, _day in enumerate(cal.days(t)):
        items = sorted([*((x.start, 0, share._stop(x, b, t)) for x in blocks if x.day == i), *((a.start, 1, share._plan(a)) for a in acts if a.day == i)], key=lambda r: r[:2])
        stops = [r[2] for r in items]
        pics = [Polaroid(src(p), _alt(i + 1, p), p["plan_title"]) for p in shots.values() if _day_of(p, t) == i]
        days.append(Day(i + 1, f"DAY {i + 1}", share._day_title(i, last, stops), "", stops, collapsed=False, note=d["notes"].get(str(i + 1), ""), photos=pics))
    cover = shots.get(d["cover"]) or next(iter(shots.values()), None)
    rest = [p for p in shots.values() if p is not cover]
    polaroids = [Polaroid(src(p), _alt(_day_of(p, t) + 1, p), p["plan_title"]) for p in ([cover] if cover else []) + rest[:1]]
    plans = sum(len(x.stops) for x in days)
    name = d["name"] or "a traveler"
    place = t.destination_name
    key = place_key(place, t.airports)
    return Itinerary(
        slug=d["slug"], title=d["title"], headline=f"{d['title']}:", accent=f"{name.split()[0]}'s scrapbook", place=place,
        lede=f"{len(days)} days in {place}: photos, notes and tips from {name}.", days=days,
        tags=[Tag(hub.TAGS[k][0], hub.TAGS[k][1], hub.TAGS[k][2], (-3, 2, -1.5)[n % 3]) for n, k in enumerate(k for k in hub.TAGS if k in d["stickers"])],
        stats=[(f"{len(days)} days", "from landing to flight home"), (f"{plans} plans", "bookings and things to do"), (f"{len(shots)} photos", "from the trip")],
        polaroids=polaroids, route=place, author=name, real=True, handle=handle, plan_to=key, plan_days=len(days), tips=list(d["tips"]))


def private_src(photo) -> str:
    return f"/trip/photos/{photo['id']}/display"


def preview(session) -> Itinerary | None:
    """The page exactly as it will be published (photos from the family's own, private routes: the preview is for members only)."""
    d = get(session)
    if d is None:
        return None
    me = ses.current_traveler(session)
    c = community.creator_of(me.id) if me else None
    return build(session, d, private_src, c["handle"] if c else "")


_PLACEHOLDER = re.compile(r"(?:adult|kid|child|traveler|traveller|guest)(?: \d+)?", re.I)      # the names an import makes for people it has not been told (Kid 1, Adult 2)


def family_names(session) -> list:
    """Everyone the family has named: its members, the open trip's travellers (an imported trip's, children included) and the names on its boarding passes. Full names, each once."""
    from gitaway import passes  # here, not at the top: passes reads the open trip like this module
    seen, out = set(), []
    for n in [*passes.travellers(session), *(p["traveller"] for ps in passes.listing(session).values() for p in ps)]:
        if n and n.casefold() not in seen:
            seen.add(n.casefold())
            out.append(n)
    return out


def join_names(names) -> str:
    """"Mira", "Mira and Theo", "Mira, Theo and Sam"."""
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else "".join(names)


def mentions(session, trip: Itinerary) -> list:
    """First names of the family (`family_names`) that the public text says ("Mira"): the title, tips, day notes, stops and the photos' captions and alt text. The publisher's own name,
    the one shown as the author, is not one, and nor is a placeholder (Kid 1). Publishing waits until the editor ticks that they are happy to be named (F-194)."""
    me = ses.current_traveler(session)
    own = {w.casefold() for name in (trip.author, me.name if me else "") for w in re.findall(r"\w+", name)}
    shots = [p for d in trip.days for p in d.photos] + list(trip.polaroids)
    text = " ".join([trip.title, *trip.tips, *(d.note for d in trip.days), *(f"{s.title} {s.note} {s.meta}" for d in trip.days for s in d.stops), *(f"{p.caption} {p.alt}" for p in shots)])
    out = []
    for full in family_names(session):
        first = (full.split() or [""])[0]
        if len(first) > 1 and first.casefold() not in own and not _PLACEHOLDER.fullmatch(full.strip()) and re.search(rf"\b{re.escape(first)}\b", text, re.I) and first not in out:
            out.append(first)
    return out


# ---- publishing --------------------------------------------------------------------------------------------------------

def public_src(slug, name, size="display") -> str:
    return f"/pub/{slug}/{name}-{size}.jpg"


def _public_copy(source: Path, folder: Path, name: str) -> None:
    """Write the public display and thumbnail of one photo: rebuilt from the pixels of the family's display copy, so nothing but the picture carries
    over (no EXIF, no position, no comment, no author). The original upload (which holds the camera's EXIF) is never read."""
    from PIL import Image
    with Image.open(source) as im:
        rgb = im.convert("RGB")
        icc = im.info.get("icc_profile")   # the colour profile has no location; it keeps the colours true
        clean = Image.frombytes("RGB", rgb.size, rgb.tobytes())
    small = clean.copy()
    small.thumbnail((photos.THUMB_EDGE, photos.THUMB_EDGE), Image.LANCZOS)
    (folder / f"{name}-display.jpg").write_bytes(photos._jpeg(clean, 82, icc))
    (folder / f"{name}-thumb.jpg").write_bytes(photos._jpeg(small, 78, icc))


def live(session) -> dict | None:
    """The community row of the open trip while it is published, else None."""
    d = get(session)
    return community.get(d["slug"]) if d and d["slug"] and d["published_by"] else None


def publish(session, names_ok=False) -> dict:
    """Publish (or update) the open trip. The person who publishes owns the page; another editor cannot replace or remove it (a family admin can remove it). A page whose text names
    someone in the family (`mentions`) waits for `names_ok`, the editor's tick that they are happy to be named. Raises HubError with a message fit to show."""
    me = ses.current_traveler(session)
    if not me:
        raise HubError("Sign in to publish a trip.")
    d = get(session)
    if d is None or not d["slug"]:
        raise HubError("Choose what to share first, then publish.")
    if not d["title"] or not d["name"]:
        raise HubError("Give the trip a title and add the name to show on it.")
    old = community.get(d["slug"])
    if old and old["owner_user"] != me.id:
        raise HubError("This trip is already published by someone else in your family.")
    if (named := mentions(session, build(session, d, private_src))) and not names_ok:      # before anything is made: no files, no profile address
        raise HubError(f"This page names {join_names(named)} from your family. Tick the box to say they are happy to be on a public page, then publish.")
    creator = community.claim_creator(me.id, d["name"])
    mine = {p["id"]: p for p in photos.listing(session)}
    folder = root() / d["slug"]
    folder.mkdir(parents=True, exist_ok=True)
    copies = {}
    try:
        for pid in d["photos"]:
            p = mine.get(pid)
            src = photos.file_path(p, "display") if p else None
            if src is None:
                continue
            name = d["copies"].get(pid) if _NAME.match(d["copies"].get(pid, "")) else secrets.token_hex(8)
            _public_copy(src, folder, name)
            copies[pid] = name
    except Exception:
        log.warning("a public photo copy failed", exc_info=True)
        raise HubError("One of the photos could not be prepared. Take it out and try again.") from None
    keep = {f"{n}-{s}.jpg" for n in copies.values() for s in SIZES}
    for f in folder.iterdir():
        if f.name not in keep:
            f.unlink(missing_ok=True)
    live_d = {**d, "copies": copies}
    trip = build(session, {**live_d, "photos": list(copies)}, lambda p: public_src(d["slug"], copies[p["id"]]), creator["handle"])
    row = community.publish(session, trip, kind="scrapbook", tags=[k for k in hub.TAGS if k in d["stickers"]], theme="sunset",
                            meta={"handle": creator["handle"], "name": creator["name"], "place": trip.plan_to})
    with ses.family(session) as fam:
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "UPDATE publications SET copies = :c, published_by = :u, published_at = :a WHERE trip_id = :t",
                         c=json.dumps(copies), u=me.id, a=familydb.now(), t=fam.trip_id)
    return row


def _remove_files(slug) -> None:
    if _SLUG.match(slug or ""):
        shutil.rmtree(root() / slug, ignore_errors=True)


def unpublish(session, role="") -> bool:
    """Take the open trip's public page and its photo copies down. The person who published may; so may an admin of the family. False when nothing is live."""
    me = ses.current_traveler(session)
    d = get(session)
    row = community.get(d["slug"], hidden=True) if me and d and d["slug"] else None      # hidden=True: a page the captain took down can still be deleted by its owner (F-182)
    if not row or row["kind"] != "scrapbook":
        return False
    if row["owner_user"] != me.id and not (role == "admin" and row["owner_family"] == str(session.get("tenant_id") or "")):
        raise PermissionError("Only the person who published this trip, or a family admin, can take it down.")
    return _take_down(session, d["slug"], row["owner_user"])


def _take_down(session, slug, owner) -> bool:
    community.unpublish({"user_id": owner}, slug)
    _remove_files(slug)
    with ses.family(session) as fam:
        if fam:
            with familydb.transaction(fam.db):
                familydb.run(fam.db, "UPDATE publications SET published_by = '', published_at = '', copies = '{}' WHERE slug = :s", s=slug)
    return True


def take_down_trip(session, trip_id) -> None:
    """A trip that is being deleted: its public page and photo copies go with it, whoever published it (the draft row goes with the trip)."""
    with ses.family(session) as fam:
        row = familydb.row(fam.db, "SELECT slug FROM publications WHERE trip_id = :t", t=trip_id) if fam else None
    if row:
        community.unpublish({"user_id": (community.get(row["slug"], hidden=True) or {}).get("owner_user", "")}, row["slug"])
        _remove_files(row["slug"])


# ---- reading the public side -------------------------------------------------------------------------------------------

def public_file(slug, filename) -> Path | None:
    """The file of a public photo, only for a live published trip and only a name this module made: `<16 hex>-display.jpg` or `-thumb.jpg`."""
    m = re.fullmatch(r"([0-9a-f]{16})-(display|thumb)\.jpg", filename or "")
    if not m or not _SLUG.match(slug or "") or not community.is_real(slug):
        return None
    path = (root() / slug / filename).resolve()
    return path if (root() / slug).resolve() in path.parents and path.is_file() else None


def editor_days(session) -> list:
    """The open trip's days for the editor: for each its number, its date (private, shown only to the family) and the trip's photos taken that day."""
    t = cal.trip_of(ses.booking(session))
    ph = photos.listing(session)
    return [{"n": i + 1, "date": day, "photos": [p for p in ph if _day_of(p, t) == i]} for i, day in enumerate(cal.days(t))]


def sample_dates(days, today=None) -> tuple:
    """Sensible dates for "Plan this trip": the first Friday at least 45 days from today, and `days` days from there."""
    start = (today or catalog.today()) + timedelta(days=45)
    start += timedelta(days=(4 - start.weekday()) % 7)
    return start, start + timedelta(days=max(days, 1) - 1)
