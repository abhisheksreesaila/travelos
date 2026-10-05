"""Voice notes on a plan (F-091): the files, nothing else. A voice note is a thread item (gitaway/plantalk.py); its audio lives under
`<data folder>/voicenotes/<family>/<trip>/<random id>.<ext>`, on the same volume as photos and passes, and is served only by the thread item's
own address to members of the family that owns it (gitaway/pages/plantalk.py).

* What is accepted. What a phone's or laptop's recorder makes: MP4/M4A (iPhone Safari), WebM (Chrome, Firefox, Android) and Ogg, recognised
  by their first bytes and never by the file name or the type the browser claims; at most MAX_BYTES (3 minutes of speech is far less) and
  at most MAX_SECONDS long, as the page timed it (the audio is not decoded here). Empty, too big, too long or another type is refused with
  a message fit to show.
* Paths are built from ids made here, never from anything a person sent.
"""

import re
import secrets
import shutil
from pathlib import Path

from gitaway import auth, photos

MAX_BYTES = 4 * 1024 * 1024
MAX_SECONDS = 180
TYPES = {"mp4": ("m4a", "audio/mp4"), "webm": ("webm", "audio/webm"), "ogg": ("ogg", "audio/ogg")}
_SAFE = re.compile(r"[^A-Za-z0-9_-]")


class VoiceError(ValueError):
    """A voice note that cannot be kept; the message is fit to show. `status` is the HTTP status an upload route answers with."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def root() -> Path:
    return auth.data_dir() / "voicenotes"


def kind_of(data: bytes):
    """'mp4', 'webm' or 'ogg' from the first bytes, else None (a HEIC photo has the same box but its own brand, and is not audio)."""
    if data[4:8] == b"ftyp" and data[8:12] not in photos._HEIC_BRANDS:
        return "mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if data[:4] == b"OggS":
        return "ogg"
    return None


def seconds(value) -> int:
    """The length the page timed, as whole seconds (at least 1), or raise VoiceError."""
    try:
        s = float(value)
    except (TypeError, ValueError):
        raise VoiceError("That voice note has no length. Record it again.") from None
    if s != s or s <= 0:
        raise VoiceError("That voice note has no length. Record it again.")
    if s > MAX_SECONDS + 1:
        raise VoiceError(f"Voice notes can be up to {MAX_SECONDS // 60} minutes.", 413)
    return max(1, min(MAX_SECONDS, round(s)))


def check(data: bytes, secs) -> tuple:
    """(kind, whole seconds) of an upload, or raise VoiceError for one that is empty, too big, too long or not audio we keep."""
    if not data:
        raise VoiceError("That voice note is empty. Record it again.")
    if len(data) > MAX_BYTES:
        raise VoiceError(f"That voice note is too large (at most {MAX_BYTES // (1024 * 1024)} MB).", 413)
    kind = kind_of(data)
    if kind is None:
        raise VoiceError("That is not a voice note this app can keep. Record it in the app.", 415)
    return kind, seconds(secs)


def _folder(tenant_id, trip_id) -> str:
    return f"{_SAFE.sub('_', tenant_id or '')[:80]}/{_SAFE.sub('_', trip_id or '')[:80]}"


def save(tenant_id, trip_id, data: bytes, secs) -> dict:
    """Validate and store one voice note. {"file": path relative to root(), "mime", "secs"}. Raises VoiceError; a full volume is refused too."""
    kind, n = check(data, secs)
    if not photos.room():
        raise VoiceError("There is no room to keep more recordings right now. Tell the family admin.", 507)
    ext, mime = TYPES[kind]
    rel = f"{_folder(tenant_id, trip_id)}/{secrets.token_hex(16)}.{ext}"
    path = root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"file": rel, "mime": mime, "secs": n}


def path_of(rel) -> Path | None:
    """The stored file for a relative name from a thread item, only ever one under the voice folder."""
    if not isinstance(rel, str) or not rel:
        return None
    path = (root() / rel).resolve()
    return path if root().resolve() in path.parents and path.is_file() else None


def remove(rel) -> None:
    path = path_of(rel)
    if path:
        path.unlink(missing_ok=True)


def purge_trip(tenant_id, trip_id) -> None:
    """Delete the voice folder of a trip that is gone (its rows go in the same transaction as the trip: gitaway.importer.delete)."""
    shutil.rmtree(root() / _folder(tenant_id, trip_id), ignore_errors=True)
