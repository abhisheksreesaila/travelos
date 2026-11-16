"""What is left of publishing a family's trip as a creator page (F-181; the editor retired in F-254): the folder of public photo copies (`<data folder>/public/<slug>/`) and how they are served
(`public_file`, at /pub/<slug>/<file>), taking a trip's public page down with the trip (`take_down_trip`), whether the open trip is live (`live`), the place keys the creator import and the family
use (`place_key`, `names_place`, `_check_text`), and `sample_dates`. The rows the editor wrote (`publications`, gitaway.familydb_publish) and the pages and copies it made are still read and still
deleted; nothing writes new ones. A creator's own guide is gitaway/creatordraft.py, which uses this module's folder and sizes.
"""

import json
import re
import shutil
from datetime import timedelta
from pathlib import Path

from gitaway import auth, catalog, community, familydb, session as ses, share, tripcal as cal
from gitaway.hub import HubError

SIZES = ("display", "thumb")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,70}$")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# the words that put a destination on one of the catalog's places (where "Plan this trip" can go), and the airports that serve them. Only names that are that place and no other:
# no "disney" (Walt Disney World, Disneyland Paris, Tokyo), no "california" (Tahoe, Yosemite, San Francisco and Napa are California too, and San Diego is not Los Angeles),
# no "hawaii" (Maui, Kauai and the Big Island are Hawaii, but HNL is on Oahu). Matched as whole words ("queens" is not "Queenstown"). F-194.
_PLACES = (("la", r"los angeles|anaheim|(?<!hong kong )(?<!tokyo )(?<!shanghai )(?<!paris )disneyland resort(?! paris)|santa monica|burbank|pasadena|orange county|hollywood|long beach", {"LAX", "BUR", "SNA", "LGB"}),
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


def _check_text(*texts):
    for x in texts:
        if _EMAIL.search(x):
            raise HubError("Take the email address out: your page is public, and so is everything you write on it.")


# ---- what strangers will see -------------------------------------------------------------------------------------------

def join_names(names) -> str:
    """"Mira", "Mira and Theo", "Mira, Theo and Sam"."""
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else "".join(names)


# ---- publishing --------------------------------------------------------------------------------------------------------

def public_src(slug, name, size="display") -> str:
    return f"/pub/{slug}/{name}-{size}.jpg"


def live(session) -> dict | None:
    """The community row of the open trip while it is published, else None."""
    d = get(session)
    return community.get(d["slug"]) if d and d["slug"] and d["published_by"] else None


def _remove_files(slug) -> None:
    if _SLUG.match(slug or ""):
        shutil.rmtree(root() / slug, ignore_errors=True)


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


def sample_dates(days, today=None) -> tuple:
    """Sensible dates for "Plan this trip": the first Friday at least 45 days from today, and `days` days from there."""
    start = (today or catalog.today()) + timedelta(days=45)
    start += timedelta(days=(4 - start.weekday()) % 7)
    return start, start + timedelta(days=max(days, 1) - 1)
