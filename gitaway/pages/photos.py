"""Photos on the plan (F-071): the Photos view of the Family tab, the photo page, and the routes that add, serve and remove photos.

POST /trip/photos                 add photos (multipart, field `photo`, one or more; at most photos.MAX_FILES of photos.MAX_BYTES each). With the
                                  header `X-Fragment: 1` the answer is JSON {"ids": [...], "errors": [...]} (400/413/415 when nothing was kept),
                                  otherwise a redirect back to the Photos view.
POST /trip/photos/remove          remove the photo `id` (the person who added it, or an admin; 403 for anyone else, 404 when it is not the family's)
GET  /trip/photos/<id>            the photo's page: big picture, which plan and when, and Remove for whoever may
GET  /trip/photos/<id>/display    the picture (long side 1600) and
GET  /trip/photos/<id>/thumb      its thumbnail, only to a signed-in member of the photo's family, `Cache-Control: private`, never a static path

The two POSTs are on gitaway.access.OPEN_POSTS (and tests/test_roles.py) on purpose: adding a photo changes no plan, so a viewer may add
one; removal checks author-or-admin itself. The rules and the storage are in gitaway/photos.py.
"""

import asyncio
from datetime import date
from urllib.parse import quote

from fasthtml.common import A, Button, Details, Div, Form, Img, Input, Link, Main, P, Span, Summary
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response

from gitaway import access, phone, photos, session as ses, tripcal as cal
from gitaway.icons import icon

HEAD = (Link(rel="stylesheet", href="/assets/css/morning.css"), Link(rel="stylesheet", href="/assets/css/thread.css"), Link(rel="stylesheet", href="/assets/css/photos.css"))
PATH = "/trip/photos"
VIEW_URL = "/trip/family?view=photos"
ACCEPT = "image/jpeg,image/png,image/webp,image/heic,image/heif,image/*"
MIME = {"display": "image/jpeg", "thumb": "image/jpeg"}
TOO_BIG = "That upload is too large (at most {mb} MB a photo, {n} photos at a time)."


def clock(minute) -> str:
    return cal.fmt_time(int(minute))


def day_label(iso) -> str:
    d = date.fromisoformat(iso)
    return f"{d.strftime('%A, %b')} {d.day}"


def where(p) -> str:
    """The plan a photo is pinned to; without one, its date ("Oct 18")."""
    if p["plan_title"]:
        return p["plan_title"]
    d = date.fromisoformat(p["taken_date"])
    return f"{d.strftime('%b')} {d.day}"


# ---- the Photos view ---------------------------------------------------------------------------------------------------------

def _stop_count(items, p) -> int:
    return sum(1 for x in items if x["plan_id"] == p["plan_id"] and x["taken_date"] == p["taken_date"]) if p["plan_id"] else 0


def _polaroid(items):
    latest = max(items, key=lambda x: (x["taken_at"], x["created_at"]))
    n = _stop_count(items, latest)
    chip = f"{where(latest)} · {clock(latest['taken_min'])}"
    if latest["plan_id"]:
        note = f"Found by when it was taken. {n} photo{'s' if n != 1 else ''} on this stop."
    else:
        note = "Not during a plan, so it stays with the day."
    return [
        A(Span(cls="fp-tape"), Img(src=f"{PATH}/{latest['id']}/display", alt=latest["caption"] or f"Latest photo, {chip}", cls="fp-polar-img"),
          Span(latest["caption"] or (f"Added by {latest['author_name']}" if latest["author_name"] else ""), cls="fp-polar-cap"),
          Span(icon("pin", 17, 2.4), chip, cls="fp-pinned"), href=f"{PATH}/{latest['id']}", cls="fp-polar", id="fp-polar", aria_label=f"Open the latest photo, {chip}"),
        Div(Span(icon("pin", 20, 2.2), cls="fp-pin-ico", aria_hidden="true"),
            Span(Span(f"Pinned to {where(latest)}" if latest["plan_id"] else f"On {day_label(latest['taken_date'])}", cls="fp-pinto-t"), Span(note, cls="fp-pinto-s"), cls="fp-pinto-x"), cls="fp-pinto", id="fp-pinto"),
    ]


def _strips(items):
    days = {}
    for p in items:
        days.setdefault(p["taken_date"], []).append(p)
    out = []
    for iso in sorted(days):
        group = sorted(days[iso], key=lambda x: (x["taken_min"], x["created_at"]))
        out.append(Div(
            Div(Span(day_label(iso).upper()), Span(f"{len(group)} photo{'s' if len(group) != 1 else ''}"), cls="fp-sec"),
            Div(*[A(Img(src=f"{PATH}/{p['id']}/thumb", alt=p["caption"] or f"Photo at {clock(p['taken_min'])}{', ' + p['plan_title'] if p['plan_title'] else ''}", loading="lazy", cls="fp-thumb"),
                    Span(clock(p["taken_min"]), cls="fp-time"), href=f"{PATH}/{p['id']}", cls="fp-s", data_photo=p["id"], title=where(p)) for p in group],
                cls="fp-strip", role="list", aria_label=f"Photos from {day_label(iso)}", data_date=iso),
            cls="fp-day", data_date=iso))
    return out


def view(session, hidden=False, error=""):
    """The Photos panel of the Family tab: add buttons, the latest photo as a polaroid pinned to its plan, and a strip of photos per day."""
    items = photos.listing(session)
    adders = Div(
        Button(icon("camera", 20, 2.2), Span("Take a photo"), type="button", cls="fp-add fp-add-main", data_pick="camera"),
        Button(icon("image", 20, 2.2), Span("From your library"), type="button", cls="fp-add", data_pick="library"), cls="fp-adders")
    body = [adders, P(error, id="fp-error", cls="fp-error", role="alert", hidden=not error)]
    if items:
        body += [P(f"{len(items)} photo{'s' if len(items) != 1 else ''}", cls="fp-count", id="fp-count"), *_polaroid(items), *_strips(items)]
    else:
        body.append(P("No photos yet. Take one and it lands on the plan it was taken during.", id="fp-empty", cls="fp-empty"))
    body.append(P("Only your family can see these. Where a photo was taken stays inside the family.", cls="fp-privacy"))
    return Div(*body, id="fp", cls="fp", data_view="photos", hidden=hidden)


def pickers():
    """The two hidden file inputs: the camera (iPhone opens the camera) and the library (iPhone offers its photo library). Both take several."""
    return Div(Input(type="file", id="ph-camera", name="photo", accept=ACCEPT, capture="environment", multiple=True, hidden=True, aria_label="Take a photo"),
               Input(type="file", id="ph-library", name="photo", accept=ACCEPT, multiple=True, hidden=True, aria_label="Choose photos from your library"),
               cls="fp-inputs", data_max=str(photos.MAX_BYTES), data_files=str(photos.MAX_FILES))


# ---- the photo's own page ----------------------------------------------------------------------------------------------------

def photo_page(request, session, p):
    me = ses.current_traveler(session)
    role = access.request_role()
    chip = f"{where(p)} · {clock(p['taken_min'])}"
    removable = photos.can_remove(p, me.id if me else "", role)
    body = Div(
        A(icon("chev-left", 18, 2.4), "All photos", href=VIEW_URL, cls="fp-back", id="fp-back"),
        Img(src=f"{PATH}/{p['id']}/display", alt=p["caption"] or f"Photo, {chip}", cls="fp-big", id="fp-big"),
        Div(Span(icon("pin", 18, 2.4), cls="fp-pin-ico", aria_hidden="true"),
            Span(Span(f"Pinned to {where(p)}" if p["plan_id"] else f"On {day_label(p['taken_date'])}", cls="fp-pinto-t"),
                 Span(f"{day_label(p['taken_date'])}, {clock(p['taken_min'])} · added by {p['author_name'] or 'someone'}", cls="fp-pinto-s"), cls="fp-pinto-x"), cls="fp-pinto", id="fp-meta"),
        P(p["caption"], cls="fp-caption") if p["caption"] else "",
        Details(Summary(icon("x", 18, 2.4), Span("Remove photo"), id="fp-remove", cls="fp-remove"),
                Form(P("Remove this photo for the whole family? This cannot be undone. To keep it, press Remove photo again.", cls="fp-privacy"),
                     Input(type="hidden", name="id", value=p["id"]),
                     Button(Span("Yes, remove it"), type="submit", id="fp-remove-yes", cls="fp-remove fp-remove-yes"),
                     method="post", action=f"{PATH}/remove", cls="fp-remove-form"), cls="fp-confirm", id="fp-confirm") if removable else
        P("Only the person who added this photo, or a family admin, can remove it.", cls="fp-privacy", id="fp-keep"),
        cls="fp fp-page")
    b = ses.booking(session)
    t = cal.trip("", b)
    return phone.shell("family", phone.header(f"{t.title.upper()} · {cal.range_label(t.depart, t.return_).upper()}", "Photo"), Main(body, id="main", cls="ph-main"), title="Photo",
                       head=HEAD)


# ---- the routes --------------------------------------------------------------------------------------------------------------

class BodyLimit:
    """Refuse an oversized upload from its Content-Length, before a byte of the body is read or parsed (as F-056's import does)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"] == PATH:
            headers = dict(scope["headers"])
            if b"content-length" not in headers:   # a body of unknown length cannot be checked before it is read
                await PlainTextResponse("Send the photo with its length.", status_code=411)(scope, receive, send)
                return
            try:
                size = int(headers[b"content-length"] or 0)
            except ValueError:
                size = 0
            if size > photos.MAX_BYTES * photos.MAX_FILES + 100_000:
                msg = TOO_BIG.format(mb=photos.MAX_BYTES // (1024 * 1024), n=photos.MAX_FILES)
                await PlainTextResponse(msg, status_code=413)(scope, receive, send)
                return
        await self.app(scope, receive, send)


_SLOT = None


def _slot():
    global _SLOT
    if _SLOT is None:
        _SLOT = asyncio.Semaphore(1)
    return _SLOT


def _signed_in(session):
    return ses.current_traveler(session) is not None


def register(app):
    app.add_middleware(BodyLimit)

    @app.post(PATH)
    async def add(request, session):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        wants_json = request.headers.get("x-fragment") == "1"
        form = await request.form()
        files = [f for f in form.getlist("photo") if getattr(f, "filename", None) is not None and hasattr(f, "read")]
        caption = form.get("caption") or ""
        trip = form.get("trip") or None
        ids, errors, status = [], [], 400
        if not files:
            errors.append("Choose a photo first.")
        elif len(files) > photos.MAX_FILES:
            errors.append(f"Add at most {photos.MAX_FILES} photos at a time.")
            files = []
        for f in files:
            try:
                data = await f.read(photos.MAX_BYTES + 1)
                async with _slot():   # decoding and resizing are heavy: one at a time, and off the event loop
                    ids.append((await run_in_threadpool(photos.add, session, data, caption, None, trip))["id"])
            except photos.PhotoError as e:
                errors.append(str(e))
                status = e.status
        if wants_json:
            if errors and not ids:
                return PlainTextResponse(errors[0], status_code=status)
            return JSONResponse({"ids": ids, "id": ids[-1], "errors": errors})
        return RedirectResponse(VIEW_URL + (f"&error={quote(errors[0])}" if errors and not ids else ""), status_code=303)

    @app.post(f"{PATH}/remove")
    def remove(request, session, id: str = ""):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        try:
            found = photos.remove(session, id, access.request_role())
        except PermissionError as e:
            return PlainTextResponse(str(e), status_code=403)
        if not found:
            return PlainTextResponse("That photo is not here.", status_code=404)
        return RedirectResponse(VIEW_URL, status_code=303)

    @app.get(PATH + "/{pid}/{size}")
    def picture(request, session, pid: str, size: str):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        p = photos.get(session, pid)
        path = photos.file_path(p, size) if p else None
        if path is None:
            return Response("Not found.", status_code=404)
        headers = {"Cache-Control": "private, no-cache", "X-Content-Type-Options": "nosniff", "ETag": f'"{pid}-{size}-{path.stat().st_mtime_ns}"'}   # the file never changes, but a removal must show at once: revalidate
        if request.headers.get("if-none-match") == headers["ETag"]:
            return Response(status_code=304, headers=headers)
        return FileResponse(path, media_type=MIME[size], headers=headers)

    @app.get(PATH + "/{pid}")
    def one(request, session, pid: str):
        if (r := phone.guard(session, f"{PATH}/{pid}")):
            return r
        p = photos.get(session, pid)
        if p is None:
            return Response("Not found.", status_code=404)
        return photo_page(request, session, p)
