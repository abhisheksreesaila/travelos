"""Photos on the plan (F-071): the family adds photos in the app, and each lands on the plan it was taken during.

* Who. Every member can add photos, viewers too, and sees them all: a grandparent who may only look at the plans can still share what they saw
  (like a message in the thread, and for the same reason: it changes no plan). Only the person who added a photo, or a family admin, removes it.
  POST /trip/photos and /trip/photos/remove are on gitaway.access.OPEN_POSTS on purpose; `remove` checks author-or-admin itself.
* What is accepted. JPEG, PNG, WebP and HEIC (iPhone), recognised by their first bytes and not by the file name or the type the browser says,
  at most MAX_BYTES each, at most MAX_PIXELS pixels (a decompression-bomb guard), and at most MAX_FILES in one upload.
* What is stored. Under `<data folder>/photos/<family>/<trip>/<random id>.<ext>`: the original as it came, a display copy (longest side
  DISPLAY_EDGE, JPEG) and a thumbnail (THUMB_EDGE). The two copies are re-encoded from the pixels, so they carry no EXIF and no GPS; the
  taken-at time and the coordinates are kept in the family database (`photos` table) and nowhere else. The original is kept (it holds
  the camera's EXIF) but is never served. Paths are built from ids made here, never from the file name a person sent.
  HEIC is read with pillow-heif (conda-forge); a HEIC the decoder cannot open is refused with a message, not stored.
* When and where. The time is the EXIF DateTimeOriginal (read as the trip's clock when the photo says no offset), else the time it was added.
  A photo is matched to the plan on that day whose time window contains the minute; if none does and the photo has a position and
  gitaway.geo (F-068) already knows where the day's plans are, to the nearest of them within NEAR_KM; otherwise it belongs to the day only.
* Who may see. `get`/`open_file` look the id up in the signed-in person's own family database, so another family's photo is "not found"
  whatever id or path is tried. The route (gitaway/pages/photos.py) serves the files with `Cache-Control: private`.
* The thread. An added photo posts a photo card (gitaway.familythread.post_photo) pointing at its thumbnail address; removing the photo
  removes the card.
"""

import io
import logging
import math
import re
import secrets
import shutil
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from gitaway import auth, familydb, familythread, session as ses, tripcal as cal, tripday as td

log = logging.getLogger("gitaway.photos")

MAX_BYTES = 15 * 1024 * 1024
MAX_FILES = 6
MAX_PIXELS = 50_000_000
MIN_FREE = 2 * 1024 ** 3     # refuse uploads when the volume has less than this free
DISPLAY_EDGE = 1600
THUMB_EDGE = 640
NEAR_KM = 3.0
MAX_CAPTION = 140
SIZES = ("display", "thumb")
_EXIF_IFD, _GPS_IFD = 0x8769, 0x8825

TYPES = {"jpeg": ("jpg", "image/jpeg"), "png": ("png", "image/png"), "webp": ("webp", "image/webp"), "heic": ("heic", "image/heic")}
_HEIC_BRANDS = (b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"mif1", b"msf1")
_SAFE = re.compile(r"[^A-Za-z0-9_-]")
_ID = re.compile(r"^[0-9a-f]{32}$")


class PhotoError(ValueError):
    """A photo that cannot be kept; the message is fit to show. `status` is the HTTP status an upload route answers with."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def root() -> Path:
    """The folder photos live in, on the data volume. Absolute: the process runs from the data folder, but never relies on it."""
    return auth.data_dir() / "photos"


def kind_of(data: bytes):
    """'jpeg', 'png', 'webp' or 'heic' from the first bytes, else None. The file name and the browser's claimed type are not trusted."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:8] == b"ftyp" and data[8:12] in _HEIC_BRANDS:
        return "heic"
    return None


def check(data: bytes) -> str:
    """The kind of an upload, or raise PhotoError for one that is empty, too big or not a picture we keep."""
    if not data:
        raise PhotoError("That file is empty.")
    if len(data) > MAX_BYTES:
        raise PhotoError(f"That photo is too large (at most {MAX_BYTES // (1024 * 1024)} MB).", 413)
    kind = kind_of(data)
    if kind is None:
        raise PhotoError("Only JPEG, PNG, WebP and HEIC photos can be added.", 415)
    return kind


# ---- reading the picture ---------------------------------------------------------------------------------------------------

def _open(data: bytes):
    from PIL import Image
    import pillow_heif
    pillow_heif.register_heif_opener()
    try:
        img = Image.open(io.BytesIO(data))
        if img.width * img.height > MAX_PIXELS:
            raise PhotoError("That photo is too large to open.")
        if img.format == "JPEG":
            img.draft("RGB", (DISPLAY_EDGE, DISPLAY_EDGE))   # the decoder shrinks while reading: a 48 MP photo never fills memory at full size
        img.load()
        return img
    except PhotoError:
        raise
    except Exception as e:
        log.info("photo not opened: %s", type(e).__name__)
        raise PhotoError("That photo could not be opened.") from e


def _deg(parts, ref):
    d, m, s = (float(x) for x in parts)
    v = d + m / 60 + s / 3600
    return -v if str(ref).upper() in ("S", "W") else v


def exif_of(img):
    """(taken, (lat, lon) or None) from a photo's EXIF. `taken` is a datetime (aware when the camera wrote its offset) or None."""
    try:
        ex = img.getexif()
    except Exception:
        return None, None
    taken = None
    try:
        ifd = ex.get_ifd(_EXIF_IFD)
        raw = ifd.get(0x9003) or ifd.get(0x9004) or ex.get(0x0132)
        if raw:
            taken = datetime.strptime(str(raw).strip().replace("\x00", "")[:19], "%Y:%m:%d %H:%M:%S")
            off = str(ifd.get(0x9011) or ifd.get(0x9010) or "").strip()
            m = re.fullmatch(r"([+-])(\d\d):(\d\d)", off)
            if m:
                delta = timedelta(hours=int(m[2]), minutes=int(m[3]))
                taken = taken.replace(tzinfo=timezone(-delta if m[1] == "-" else delta))
    except Exception:
        taken = None
    coords = None
    try:
        gps = ex.get_ifd(_GPS_IFD)
        if gps.get(2) and gps.get(4):
            lat, lon = _deg(gps[2], gps.get(1, "N")), _deg(gps[4], gps.get(3, "E"))
            if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat or lon):
                coords = (lat, lon)
    except Exception:
        coords = None
    return taken, coords


def _upright(img):
    """The pixels turned upright, RGB, the longest side at most DISPLAY_EDGE (one downscale; the thumbnail is made from this, not from the original)."""
    from PIL import Image, ImageOps
    icc = img.info.get("icc_profile")
    out = ImageOps.exif_transpose(img)
    out = out.convert("RGB") if out.mode != "RGB" else out
    if max(out.size) > DISPLAY_EDGE:
        out = out.resize(tuple(max(1, round(v * DISPLAY_EDGE / max(out.size))) for v in out.size), Image.LANCZOS)
    return out, icc


def _jpeg(img, quality, icc=None):
    buf = io.BytesIO()
    # no exif= argument: nothing of the camera's metadata (time, position) is carried over; the colour profile has no location, so it stays
    img.save(buf, "JPEG", quality=quality, optimize=True, **({"icc_profile": icc} if icc else {}))
    return buf.getvalue()


def _copies(img):
    """(display JPEG bytes, thumbnail JPEG bytes) with no EXIF or GPS."""
    from PIL import Image
    full, icc = _upright(img)
    small = full.copy()
    small.thumbnail((THUMB_EDGE, THUMB_EDGE), Image.LANCZOS)
    return _jpeg(full, 82, icc), _jpeg(small, 78, icc)


def room() -> bool:
    """Is there space for more photos? False when the volume under the photos folder has less than MIN_FREE free."""
    base = root()
    base.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(base).free >= MIN_FREE


# ---- matching to the plan --------------------------------------------------------------------------------------------------

def _km(a, b) -> float:
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def match_plan(acts, day, minute, coords=None, destination=""):
    """The plan a photo taken on trip day `day` at `minute` belongs to: (id, title), or ("", "") for the day alone.

    The plan whose window contains the minute (the one that started last, when two overlap), else the nearest plan that day to `coords`
    (latitude, longitude) within NEAR_KM, using only places gitaway.geo already has cached (no network call here)."""
    todays = [a for a in acts if a.day == day]
    inside = [a for a in todays if a.start <= minute < a.end]
    if inside:
        a = max(inside, key=lambda x: (x.start, x.id))
        return a.id, a.title
    if coords:
        best = None
        for a in todays:
            where = td.cached_coords(f"{a.title}, {destination}" if destination else a.title)
            if where:
                d = _km(coords, where)
                if d <= NEAR_KM and (best is None or d < best[0]):
                    best = (d, a)
        if best:
            return best[1].id, best[1].title
    return "", ""


# ---- adding ----------------------------------------------------------------------------------------------------------------

def _folder(tenant_id, trip_id) -> str:
    return f"{_SAFE.sub('_', tenant_id or '')[:80]}/{_SAFE.sub('_', trip_id or '')[:80]}"


def _local(taken, zone, now):
    """(aware datetime in the trip's zone, whether the camera told us the time). A time with no offset is the trip's own clock."""
    z = ZoneInfo(zone)
    if taken is None:
        return now.astimezone(z), False
    return (taken.replace(tzinfo=z) if taken.tzinfo is None else taken.astimezone(z)), True


def _scope(session):
    """gitaway.geo's cache scope (F-068) when that module exists, else nothing: matching by place reads only places it has cached."""
    try:
        import importlib
        return importlib.import_module("gitaway.geo").cache_scope(session)
    except Exception:
        return nullcontext()


STALE = "This trip changed. Reload the page."


def add(session, data: bytes, caption: str = "", now=None, trip_id=None, talk=None):
    """Keep one uploaded photo for the open trip: validate it, store the files, record it, put a card in the thread. Returns the photo (a dict).

    `talk` is a photo sent in a plan's chat (F-091): {"act", "title", "extra" (the card's payload: which plan and part), "push" (the push's text)}. The photo
    is then pinned to that plan, whatever time it was taken.

    Raises PhotoError for anything that cannot be kept (the message is fit to show)."""
    if not room():
        raise PhotoError("There is no room to keep more photos right now. Tell the family admin.", 507)
    with ses.family(session) as fam:   # the page names the trip it was drawn for (like a message in the thread): another one is refused
        if not fam or not fam.trip_id or (trip_id and fam.trip_id != trip_id):
            raise PhotoError(STALE, 409)
    kind = check(data)
    img = _open(data)
    taken, coords = exif_of(img)
    display, thumb = _copies(img)
    ext = TYPES[kind][0]
    caption = " ".join((caption or "").split())[:MAX_CAPTION]
    acts = cal.activities(session)
    b = ses.booking(session)
    trip = cal.trip("", b)
    pid, written = secrets.token_hex(16), []
    with ses.family(session) as fam:
        if not fam or not fam.trip_id or (trip_id and fam.trip_id != trip_id):
            raise PhotoError(STALE, 409)
        zone = familydb.trip_zone(fam.db, fam.trip_id)
        when, known = _local(taken, zone, now or datetime.now(timezone.utc))
        day = (when.date() - trip.depart).days
        minute = when.hour * 60 + when.minute
        with _scope(session):
            plan_id, plan_title = match_plan(acts, day, minute, coords, trip.destination_name) if 0 <= day <= (trip.return_ - trip.depart).days else ("", "")
        if talk:
            plan_id, plan_title = talk["act"], talk["title"]
        folder = _folder(session.get("tenant_id"), fam.trip_id)
        base = root() / folder
        try:
            base.mkdir(parents=True, exist_ok=True)
            names = {"orig": f"{folder}/{pid}.{ext}", "display": f"{folder}/{pid}-display.jpg", "thumb": f"{folder}/{pid}-thumb.jpg"}
            for key, blob in (("orig", data), ("display", display), ("thumb", thumb)):
                path = root() / names[key]
                path.write_bytes(blob)
                written.append(path)
            with familydb.transaction(fam.db):
                familydb.run(fam.db, "INSERT INTO photos (id, trip_id, author, author_name, taken_at, taken_date, taken_min, lat, lon, plan_id, plan_title, caption, orig, display, thumb, created_at) "
                             "VALUES (:i, :t, :a, :n, :ta, :td, :tm, :la, :lo, :pi, :pt, :c, :o, :d, :th, :cr)",
                             i=pid, t=fam.trip_id, a=fam.traveler.id, n=familythread.first_name(fam.traveler), ta=when.isoformat(timespec="seconds"), td=when.date().isoformat(),
                             tm=minute, la=coords[0] if coords else None, lo=coords[1] if coords else None, pi=plan_id, pt=plan_title, c=caption,
                             o=names["orig"], d=names["display"], th=names["thumb"], cr=familydb.now())
                row = familydb.row(fam.db, "SELECT * FROM photos WHERE id = :i", i=pid)
        except Exception:
            for path in written:
                path.unlink(missing_ok=True)
            raise
    try:
        if talk:
            familythread.post_photo(session, card_url(pid), caption, {**talk["extra"], "photo": pid}, talk["push"])
        else:
            familythread.post_photo(session, card_url(pid), caption or (f"At {plan_title}" if plan_title else ""))
    except familythread.ThreadError as e:
        log.info("photo card not posted: %s", e)
    return dict(row)


def card_url(pid) -> str:
    return f"/trip/photos/{pid}/thumb"


# ---- reading ---------------------------------------------------------------------------------------------------------------

def listing(session) -> list:
    """The open trip's photos, oldest taken first (dicts, with lat/lon left out: a position is never drawn)."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return []
        found = familydb.rows(fam.db, "SELECT * FROM photos WHERE trip_id = :t ORDER BY taken_at, created_at", t=fam.trip_id)
    return [{k: v for k, v in r.items() if k not in ("lat", "lon")} for r in found]


def get(session, pid):
    """A photo of the signed-in person's family by id (any of its trips), or None. Another family's photo is never found."""
    if not isinstance(pid, str) or not _ID.match(pid):
        return None
    with ses.family(session) as fam:
        found = familydb.row(fam.db, "SELECT * FROM photos WHERE id = :i AND trip_id IN (SELECT id FROM trips)", i=pid) if fam else None
    return dict(found) if found else None


def file_path(row, size) -> Path | None:
    """The stored file for a size ('display' or 'thumb'), only ever one under the photos folder."""
    if size not in SIZES:
        return None
    path = (root() / row[size]).resolve()
    return path if root().resolve() in path.parents and path.is_file() else None


def can_remove(photo, person_id, role) -> bool:
    """The person who added a photo, or a family admin."""
    return role == "admin" or (bool(person_id) and photo["author"] == person_id)


def remove(session, pid, role) -> bool:
    """Remove a photo: its files, its row and its card in the thread. False when it is not this family's; raises PermissionError when this
    person may not (only the person who added it, or an admin)."""
    photo = get(session, pid)
    if photo is None:
        return False
    me = ses.current_traveler(session)
    if not can_remove(photo, me.id if me else "", role):
        raise PermissionError("Only the person who added a photo, or a family admin, can remove it.")
    with ses.family(session) as fam:
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "DELETE FROM photos WHERE id = :i", i=pid)
            familydb.run(fam.db, "DELETE FROM thread WHERE kind = 'photo' AND payload LIKE :p", p=f'%/trip/photos/{pid}/%')
    for key in ("orig", "display", "thumb"):
        try:
            (root() / photo[key]).unlink(missing_ok=True)
        except OSError as e:
            log.warning("photo file not removed: %s", type(e).__name__)
    folder = (root() / photo["orig"]).parent
    try:
        folder.rmdir()  # the trip's folder, once its last photo is gone
    except OSError:
        pass
    return True



def purge_trip(tenant_id, trip_id) -> None:
    """Delete the photo folder of a trip that is gone (its rows go in the same transaction as the trip: gitaway.importer.delete)."""
    shutil.rmtree(root() / _folder(tenant_id, trip_id), ignore_errors=True)
