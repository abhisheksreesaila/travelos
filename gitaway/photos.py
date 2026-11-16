"""What is left of the family's photos (F-071; adding, listing and serving them retired in F-254 with the Family tab, the Map tab and the plan chat's camera): the checks and the re-encoding the creator import
uses for the post's pictures (`kind_of`, `check`, `_open`, `_copies`, `_jpeg`, `_upright`, `DISPLAY_EDGE`, `THUMB_EDGE`), the passes' file check, the free-space guard (`room`), and `purge_trip`, which deletes a
trip's picture files when the trip is deleted (photos added before F-254 stay in the family database and on the volume until then).

* What is accepted. JPEG, PNG, WebP and HEIC (iPhone), recognised by their first bytes and not by the file name or the type the browser says, at most MAX_BYTES each and MAX_PIXELS pixels (a
  decompression-bomb guard). HEIC is read with pillow-heif (conda-forge); a HEIC the decoder cannot open is refused with a message.
* What is stored (by the creator import and the older photos): under `<data folder>/photos/<family>/<trip>/<random id>`, a display copy (longest side DISPLAY_EDGE, JPEG) and a thumbnail (THUMB_EDGE),
  re-encoded from the pixels, so they carry no EXIF and no GPS. Paths are built from ids made here, never from a file name a person sent.
"""

import io
import logging
import re
import shutil
from pathlib import Path

from gitaway import auth, familydb, session as ses

log = logging.getLogger("gitaway.photos")

MAX_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 50_000_000
MIN_FREE = 2 * 1024 ** 3     # refuse uploads when the volume has less than this free
DISPLAY_EDGE = 1600
THUMB_EDGE = 640
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

# ---- adding ----------------------------------------------------------------------------------------------------------------

def _folder(tenant_id, trip_id) -> str:
    return f"{_SAFE.sub('_', tenant_id or '')[:80]}/{_SAFE.sub('_', trip_id or '')[:80]}"


# ---- reading ---------------------------------------------------------------------------------------------------------------

def get(session, pid):
    """A photo of the signed-in person's family by id (any of its trips), or None. Another family's photo is never found."""
    if not isinstance(pid, str) or not _ID.match(pid):
        return None
    with ses.family(session) as fam:
        found = familydb.row(fam.db, "SELECT * FROM photos WHERE id = :i AND trip_id IN (SELECT id FROM trips)", i=pid) if fam else None
    return dict(found) if found else None


def purge_trip(tenant_id, trip_id) -> None:
    """Delete the photo folder of a trip that is gone (its rows go in the same transaction as the trip: gitaway.importer.delete)."""
    shutil.rmtree(root() / _folder(tenant_id, trip_id), ignore_errors=True)
