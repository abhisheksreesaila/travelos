"""Flights and boarding passes (F-083): per traveller a seat, boarding group, gate, boarding time and the boarding pass itself, for the family only.

* Flights. An imported trip's flights are read from its template (key "leg:<n>", never copied). The captain's trip may have none, so an editor can add
  a flight here (airline and number, from and to by airport code, the date and the time it leaves; key "f:<id>", a `pass_flights` row).
* Who. Editors add and fix flights and passes; viewers read them. The writes are plain editor POSTs (gitaway/access.py gates them). Adding or
  changing one puts a card in the family thread (gitaway.familythread.change) so the family hears about it.
* What is accepted for a pass file. PDF, JPEG, PNG, WebP and HEIC, recognised by their first bytes and not by the file name or the browser's claimed
  type, at most MAX_BYTES each. A picture is stored as it came and re-encoded as a display copy and a thumbnail (HEIC becomes JPEG, no EXIF;
  gitaway.photos does that). A PDF is stored as it came and its first page is rendered to a picture when pypdfium2 can (pixi), so the gate view
  can show it large; when it cannot, the gate view opens the PDF itself.
* Where. `<data folder>/passes/<family>/<trip>/<random id>.<ext>`; paths are built from ids made here, never from the name a person sent.
* Who may see. `get` looks the id up in the signed-in person's own family database, so another family's pass is "not found" whatever id is tried.
  The route (gitaway/pages/passes.py) serves files with `Cache-Control: private, no-cache` and an ETag, never a static path.
"""

import io
import logging
import re
import secrets
import shutil
from datetime import date
from pathlib import Path

from gitaway import auth, familydb, familythread, members, photos, session as ses, tripcal as cal, zones

log = logging.getLogger("gitaway.passes")

MAX_BYTES = 10 * 1024 * 1024
SIZES = ("display", "thumb", "file")
_ID = re.compile(r"^[0-9a-f]{32}$")
_KEY = re.compile(r"^(leg:\d{1,2}|f:[0-9a-f]{32})$")
_CODE = re.compile(r"^[A-Za-z]{3}$")
_NUMBER = re.compile(r"^[A-Za-z0-9]{1,6}$")
_URL = re.compile(r"^https://[^\s<>\"']{4,480}$")
MIME = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "heic": "image/heic", "pdf": "application/pdf"}

# Every refusal, by key: the routes redirect with the key and the page shows the sentence, so a link can never put its own words on the page.
ERRORS = {
    "stale": "This trip changed. Reload the page.",
    "flight_name": "Give the airline and the flight number, like UA 1234.",
    "flight_route": "Use two different three-letter airport codes, like LAX and SFO.",
    "flight_date": "Pick the date the flight leaves.",
    "flight_time": "Pick the time the flight leaves.",
    "flight_missing": "That flight is not on this trip.",
    "traveller": "Say who the pass is for.",
    "time": "Pick a boarding time, or leave it empty.",
    "url": "The airline link has to start with https://",
    "empty": "That file is empty.",
    "big": f"That file is too large (at most {MAX_BYTES // (1024 * 1024)} MB).",
    "type": "Only PDF, JPEG, PNG, WebP and HEIC files can be added.",
    "open": "That file could not be opened.",
    "pages": "That PDF has too many pages (at most 50). Add just the boarding pass.",
    "room": "There is no room to keep more files right now. Tell the family admin.",
    "pass_missing": "That pass is not on this trip.",
}


class PassError(ValueError):
    """Something that cannot be saved. `key` is one of ERRORS; the message is fit to show; `status` is the HTTP status for a route that answers with one."""

    def __init__(self, key, status=400):
        super().__init__(ERRORS[key])
        self.key, self.status = key, status


def root() -> Path:
    """The folder pass files live in, on the data volume. Absolute: the process runs from the data folder, but never relies on it."""
    return auth.data_dir() / "passes"


def _folder(tenant_id, trip_id) -> str:
    return photos._folder(tenant_id, trip_id)


# ---- the file ---------------------------------------------------------------------------------------------------------------

def kind_of(data: bytes):
    """'pdf', 'jpeg', 'png', 'webp' or 'heic' from the first bytes, else None."""
    if data[:5] == b"%PDF-":
        return "pdf"
    return photos.kind_of(data)


def check(data: bytes) -> str:
    """The kind of an upload, or raise PassError for one that is empty, too big or not a file we keep."""
    if not data:
        raise PassError("empty")
    if len(data) > MAX_BYTES:
        raise PassError("big", 413)
    kind = kind_of(data)
    if kind is None:
        raise PassError("type", 415)
    return kind


def _check_pdf(data: bytes):
    """Open the PDF to be sure it is one (pypdf); a damaged or password-protected file is refused."""
    from pypdf import PdfReader
    try:
        r = PdfReader(io.BytesIO(data), strict=False)
        if r.is_encrypted or len(r.pages) < 1:
            raise PassError("open")
        if len(r.pages) > MAX_PAGES:
            raise PassError("pages")
    except PassError:
        raise
    except Exception as e:
        log.info("pass pdf not opened: %s", type(e).__name__)
        raise PassError("open") from e


MAX_PAGES = 50
RENDER_TIMEOUT = 10   # seconds: drawing runs in its own process, so a PDF that hangs or eats memory cannot block uploads
_DRAW = """
import io, sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 ** 2, 768 * 1024 ** 2))   # the drawing process gets at most 768 MB
except Exception:
    pass
import pypdfium2 as pdfium
edge = float(sys.argv[1])
pdf = pdfium.PdfDocument(sys.stdin.buffer.read())
page = pdf[0]
w, h = page.get_size()
img = page.render(scale=min(6.0, edge / max(w, h))).to_pil().convert("RGB")
img.save(sys.stdout.buffer, "PNG")
"""


def render_pdf(data: bytes):
    """The first page of a PDF as a picture (long side photos.DISPLAY_EDGE), or None when pypdfium2 is not there, takes longer than RENDER_TIMEOUT or cannot draw it.

    Only the first page is drawn, in a separate process with a time limit and a memory limit set inside that process (no preexec_fn: the app runs threads)."""
    import subprocess
    import sys
    from PIL import Image
    try:
        done = subprocess.run([sys.executable, "-c", _DRAW, str(photos.DISPLAY_EDGE)], input=data, capture_output=True, timeout=RENDER_TIMEOUT)
        if done.returncode != 0:
            log.info("pass pdf not drawn: exit %s", done.returncode)
            return None
        img = Image.open(io.BytesIO(done.stdout))
        img.load()
        return img.convert("RGB")
    except subprocess.TimeoutExpired:
        log.info("pass pdf not drawn: timed out")
        return None
    except Exception as e:
        log.info("pass pdf not drawn: %s", type(e).__name__)
        return None


def _pictures(kind, data):
    """(display JPEG bytes, thumbnail JPEG bytes) for a file, or (None, None) for a PDF that cannot be drawn."""
    if kind == "pdf":
        _check_pdf(data)
        img = render_pdf(data)
        return photos._copies(img) if img is not None else (None, None)
    try:
        return photos._copies(photos._open(data))
    except photos.PhotoError as e:
        raise PassError("open") from e


# ---- flights ----------------------------------------------------------------------------------------------------------------

def _clean(text, limit) -> str:
    return " ".join((text or "").split())[:limit]


def _flight_row(r) -> dict:
    return {"key": f"f:{r['id']}", "id": r["id"], "name": f"{r['airline']} {r['number']}".strip(), "airline": r["airline"], "number": r["number"], "origin": r["origin"], "dest": r["dest"],
            "date": date.fromisoformat(r["fly_on"]), "depart_min": r["depart_min"], "terminal": r["terminal"], "source": "added"}


def _leg_flights(session) -> list:
    b = ses.booking(session)
    if not cal.is_imported(b):
        return []
    return [{"key": f"leg:{i}", "id": "", "name": leg.name, "airline": leg.airline, "number": leg.number, "origin": leg.origin, "dest": leg.dest, "date": leg.depart.date(),
             "depart_min": leg.depart.hour * 60 + leg.depart.minute, "terminal": "", "source": "import"} for i, leg in enumerate(cal.plan_of(b).legs)]


def flights(session) -> list:
    """The open trip's flights, in the order they leave: the imported legs and the ones an editor added (dicts: key, name, origin, dest, date, depart_min, terminal, source)."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return []
        added = [_flight_row(r) for r in familydb.rows(fam.db, "SELECT * FROM pass_flights WHERE trip_id = :t", t=fam.trip_id)]
    return sorted([*_leg_flights(session), *added], key=lambda f: (f["date"], f["depart_min"], f["key"]))


def flight_label(f) -> str:
    return f"{f['name']} {f['origin']} → {f['dest']}"


def flight_zone(f, fallback="America/Los_Angeles") -> str:
    """The zone the flight's time is local to: the airport it leaves from."""
    return zones.AIRPORTS.get(f["origin"], fallback)


def save_flight(session, *, trip_id="", flight_id="", airline="", number="", origin="", dest="", fly_on="", time="", terminal="") -> str:
    """Add a flight (or fix the one `flight_id`) to the open trip and tell the family. Returns its key. Raises PassError."""
    airline, number, terminal = _clean(airline, 24), _clean(number, 20).replace(" ", ""), _clean(terminal, 12)
    origin, dest = (origin or "").strip().upper(), (dest or "").strip().upper()
    if not airline or not _NUMBER.match(number):
        raise PassError("flight_name")
    if not (_CODE.match(origin) and _CODE.match(dest)) or origin == dest:
        raise PassError("flight_route")
    try:
        day = date.fromisoformat((fly_on or "").strip())
    except ValueError:
        raise PassError("flight_date") from None
    try:
        minute = cal.parse_time(time, "departure")
    except cal.CalendarError:
        raise PassError("flight_time") from None
    with ses.family(session) as fam:
        if not fam or not fam.trip_id or (trip_id and fam.trip_id != trip_id):
            raise PassError("stale", 409)
        name = f"{airline} {number}"
        with familydb.transaction(fam.db):
            if flight_id:
                changed = _ID.match(flight_id) and familydb.run(
                    fam.db, "UPDATE pass_flights SET airline = :a, number = :n, origin = :o, dest = :d, fly_on = :f, depart_min = :m, terminal = :te WHERE id = :i AND trip_id = :t",
                    a=airline, n=number, o=origin, d=dest, f=day.isoformat(), m=minute, te=terminal, i=flight_id, t=fam.trip_id)
                if not changed:
                    raise PassError("flight_missing", 404)
                verb = "changed"
            else:
                flight_id, verb = secrets.token_hex(16), "added"
                familydb.run(fam.db, "INSERT INTO pass_flights (id, trip_id, airline, number, origin, dest, fly_on, depart_min, terminal, created_by, created_at) "
                             "VALUES (:i, :t, :a, :n, :o, :d, :f, :m, :te, :c, :cr)", i=flight_id, t=fam.trip_id, a=airline, n=number, o=origin, d=dest, f=day.isoformat(), m=minute, te=terminal,
                             c=fam.traveler.id, cr=familydb.now())
            familythread.change(session, fam, f"{familythread.first_name(fam.traveler)} {verb} the flight {name} {origin} → {dest}, {day.strftime('%a %b')} {day.day}", action="add" if verb == "added" else "change")
    return f"f:{flight_id}"


def remove_flight(session, flight_id, trip_id="") -> bool:
    """Remove a hand-added flight with its passes and their files. False when it is not this trip's."""
    if not isinstance(flight_id, str) or not _ID.match(flight_id):
        return False
    with ses.family(session) as fam:
        if fam and trip_id and fam.trip_id != trip_id:
            raise PassError("stale", 409)
        if not fam or not fam.trip_id:
            return False
        key = f"f:{flight_id}"
        gone = familydb.rows(fam.db, "SELECT orig, display, thumb FROM passes WHERE trip_id = :t AND flight_key = :k", t=fam.trip_id, k=key)
        with familydb.transaction(fam.db):
            if not familydb.run(fam.db, "DELETE FROM pass_flights WHERE id = :i AND trip_id = :t", i=flight_id, t=fam.trip_id):
                return False
            familydb.run(fam.db, "DELETE FROM passes WHERE trip_id = :t AND flight_key = :k", t=fam.trip_id, k=key)
    for r in gone:
        _unlink(r)
    return True


# ---- passes -----------------------------------------------------------------------------------------------------------------

def travellers(session) -> list:
    """Names to suggest for a pass: the family's members, then the imported trip's travellers."""
    tid = (session or {}).get("tenant_id")
    names = [m["name"] for m in members.members(tid)] if tid else []
    b = ses.booking(session)
    if cal.is_imported(b):
        names += [t.name for t in cal.plan_of(b).travelers]
    seen, out = set(), []
    for n in names:
        if n and n.casefold() not in seen:
            seen.add(n.casefold())
            out.append(n)
    return out


def _member_of(session, name) -> str:
    tid = (session or {}).get("tenant_id")
    for m in members.members(tid) if tid else []:
        if m["name"].casefold() == name.casefold():
            return m["user_id"]
    return ""


def listing(session) -> dict:
    """{flight key: [passes of that flight, oldest first]} for the open trip (dicts)."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return {}
        found = familydb.rows(fam.db, "SELECT * FROM passes WHERE trip_id = :t ORDER BY rowid", t=fam.trip_id)
    out = {}
    for r in found:
        out.setdefault(r["flight_key"], []).append(r)
    return out


def get(session, pid):
    """A pass of the signed-in person's family by id (any of its trips), or None. Another family's pass is never found."""
    if not isinstance(pid, str) or not _ID.match(pid):
        return None
    with ses.family(session) as fam:
        found = familydb.row(fam.db, "SELECT * FROM passes WHERE id = :i AND trip_id IN (SELECT id FROM trips)", i=pid) if fam else None
    return dict(found) if found else None


def file_path(row, size) -> Path | None:
    """The stored file for 'display', 'thumb' or 'file' (the PDF itself), only ever one under the passes folder."""
    if size not in SIZES:
        return None
    name = row["orig"] if size == "file" else row[size]
    if not name or (size == "file" and row["kind"] != "pdf"):
        return None
    path = (root() / name).resolve()
    return path if root().resolve() in path.parents and path.is_file() else None


def _unlink(row, keep=()):
    """Delete the stored files named in `row` (orig, display, thumb), except those in `keep`, then the trip's folder if it is now empty."""
    for key in ("orig", "display", "thumb"):
        name = row.get(key)
        if name and name not in keep:
            try:
                (root() / name).unlink(missing_ok=True)
            except OSError as e:
                log.warning("pass file not removed: %s", type(e).__name__)
    name = row.get("orig") or row.get("display")
    if name:
        try:
            (root() / name).parent.rmdir()
        except OSError:
            pass


def save_pass(session, *, trip_id="", pass_id="", flight="", traveller="", seat="", grp="", gate="", boards="", app_url="", data=None) -> dict:
    """Add a pass for a traveller on a flight (or fix the one `pass_id`; a new file replaces the old) and tell the family. Returns the pass (a dict).

    `data` is the uploaded file's bytes (None keeps what is there). Raises PassError."""
    if pass_id and not _ID.match(pass_id):   # before any file is written: the id is part of a file name
        raise PassError("pass_missing", 404)
    traveller = _clean(traveller, 40)
    seat, grp, gate = _clean(seat, 6).upper(), _clean(grp, 4).upper(), _clean(gate, 6).upper()
    app_url = (app_url or "").strip()
    if not traveller:
        raise PassError("traveller")
    if app_url and not _URL.match(app_url):
        raise PassError("url")
    boards = (boards or "").strip()
    try:
        boards_min = cal.parse_time(boards, "boarding") if boards else None
    except cal.CalendarError:
        raise PassError("time") from None
    known = {f["key"]: f for f in flights(session)}
    if flight not in known:
        raise PassError("flight_missing", 404)
    kind = display = thumb = None
    if data:
        kind = check(data)
        if not photos.room():
            raise PassError("room", 507)
        display, thumb = _pictures(kind, data)
    pid, written, old, names = pass_id or secrets.token_hex(16), [], None, {}
    with ses.family(session) as fam:
        if not fam or not fam.trip_id or (trip_id and fam.trip_id != trip_id):
            raise PassError("stale", 409)
        member = _member_of(session, traveller)
        folder = _folder(session.get("tenant_id"), fam.trip_id)
        try:
            if data:
                (root() / folder).mkdir(parents=True, exist_ok=True)
                ext = "pdf" if kind == "pdf" else photos.TYPES[kind][0]
                names = {"orig": f"{folder}/{pid}-{secrets.token_hex(4)}.{ext}", "display": f"{folder}/{pid}-{secrets.token_hex(4)}-display.jpg" if display else "",
                         "thumb": f"{folder}/{pid}-{secrets.token_hex(4)}-thumb.jpg" if thumb else ""}
                for key, blob in (("orig", data), ("display", display), ("thumb", thumb)):
                    if blob:
                        path = root() / names[key]
                        path.write_bytes(blob)
                        written.append(path)
            with familydb.transaction(fam.db):
                if pass_id:
                    old = familydb.row(fam.db, "SELECT * FROM passes WHERE id = :i AND trip_id = :t", i=pass_id, t=fam.trip_id) if _ID.match(pass_id) else None
                    if old is None:
                        raise PassError("pass_missing", 404)
                    familydb.run(fam.db, "UPDATE passes SET flight_key = :f, traveller = :tr, member_id = :m, seat = :s, grp = :g, gate = :ga, boards_min = :b, app_url = :u WHERE id = :i AND trip_id = :t",
                                 f=flight, tr=traveller, m=member, s=seat, g=grp, ga=gate, b=boards_min, u=app_url, i=pass_id, t=fam.trip_id)
                    if data:
                        familydb.run(fam.db, "UPDATE passes SET kind = :k, orig = :o, display = :d, thumb = :th WHERE id = :i AND trip_id = :t", k="pdf" if kind == "pdf" else "image", o=names["orig"],
                                     d=names["display"], th=names["thumb"], i=pass_id, t=fam.trip_id)
                    verb = "updated"
                else:
                    familydb.run(fam.db, "INSERT INTO passes (id, trip_id, flight_key, traveller, member_id, seat, grp, gate, boards_min, app_url, kind, orig, display, thumb, created_by, created_at) "
                                 "VALUES (:i, :t, :f, :tr, :m, :s, :g, :ga, :b, :u, :k, :o, :d, :th, :c, :cr)", i=pid, t=fam.trip_id, f=flight, tr=traveller, m=member, s=seat, g=grp, ga=gate, b=boards_min,
                                 u=app_url, k=("pdf" if kind == "pdf" else "image") if data else "", o=names.get("orig", ""), d=names.get("display", ""), th=names.get("thumb", ""), c=fam.traveler.id,
                                 cr=familydb.now())
                    verb = "added"
                what = "boarding pass" if (data or (old and old["kind"])) else "seat details"
                familythread.change(session, fam, f"{familythread.first_name(fam.traveler)} {verb} {traveller}'s {what} for {known[flight]['name']}", action="add" if verb == "added" else "change")
                row = dict(familydb.row(fam.db, "SELECT * FROM passes WHERE id = :i", i=pid))
        except Exception:
            for path in written:
                path.unlink(missing_ok=True)
            raise
    if old and data:   # the file that was replaced
        _unlink(dict(old), keep=names.values())
    return row


def remove_pass(session, pid, trip_id="") -> bool:
    """Remove a pass and its files. False when it is not this family's; PassError("stale") when the page was drawn for another trip than the one open."""
    row = get(session, pid)
    if row is None:
        return False
    with ses.family(session) as fam:
        if trip_id and fam.trip_id != trip_id:
            raise PassError("stale", 409)
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "DELETE FROM passes WHERE id = :i", i=pid)
    _unlink(row)
    return True


def purge_trip(tenant_id, trip_id) -> None:
    """Delete the pass folder of a trip that is gone (its rows go in the same transaction as the trip: gitaway.importer.delete)."""
    shutil.rmtree(root() / _folder(tenant_id, trip_id), ignore_errors=True)
