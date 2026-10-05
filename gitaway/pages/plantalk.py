"""Talk on the block (F-091): the chat of one plan, or of one part of a park day, and the small badge the canvas shows for it.

GET  /trip/talk?act=aN[&part=pN]         the chat: bubbles (mine on the right), voice notes that play in place, photos; a composer with text, photo and a
                                         tap-to-record mic. Inside the phone shell; the header names the plan (and part) and goes back to its day.
GET  /trip/talk/items?act=&part=&since=  the items after `since` as an HTML fragment (the page polls it like the Family tab does); the highest item
                                         number is in the `X-Thread-Last` header
POST /trip/talk/message                  a text message (fields act, part, text, trip, since)
POST /trip/talk/photo                    a photo (multipart: `photo`, optional `caption`, act, part, trip)
POST /trip/talk/voice                    a voice note (multipart: `voice`, `secs` as the page timed it, act, part, trip)
GET  /trip/talk/voice/<item id>          the audio of a voice note, only to a member of the family that owns it, with byte ranges (iPhone needs them to play)

The three POSTs are on gitaway.access.OPEN_POSTS (and tests/test_roles.py) on purpose: talking changes no plan, so a viewer may do it, as in the Family
tab's thread. With the header `X-Fragment: 1` an answer is the fragment of what is new (or a plain message with a 4xx status); otherwise a redirect to the chat.
The rules and the storage are in gitaway/plantalk.py and gitaway/voicenotes.py; the chat's script is assets/js/plantalk.js (thread.js polls and sends text).
"""

from urllib.parse import quote

from fasthtml.common import A, Button, Div, Form, Input, Label, Link, Main, P, Span, to_xml
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, PlainTextResponse, RedirectResponse, Response

from gitaway import familythread, phone, photos, plantalk, session as ses, tripcal as cal, voicenotes
from gitaway.icons import icon
from gitaway.pages import tab_family

HEAD = (*tab_family.photos_ui.HEAD, Link(rel="stylesheet", href="/assets/css/plantalk.css"))
SCRIPTS = ("/assets/js/thread.js", "/assets/js/voicenote.js", "/assets/js/plantalk.js")
PATHS = ("/trip/talk/photo", "/trip/talk/voice")
LIMITS = {"/trip/talk/photo": photos.MAX_BYTES, "/trip/talk/voice": voicenotes.MAX_BYTES}
OVERHEAD = 100_000   # the form's own fields around the file
POLL_MS = tab_family.POLL_MS


# ---- the badge on the canvas -----------------------------------------------------------------------------------------------

def talk_badge(counts, act, part="", cls=""):
    """The small pill the canvas shows on a plan or part: a bubble with how many messages (and a mic when one is a voice note), linking to the chat. With
    nothing said yet a plan shows a quiet "+ chat" and a part a quiet bubble, so a conversation can start on either. `counts` is `plantalk.counts(session)`."""
    c = counts.get((act, part or ""))
    link = plantalk.url(act, part, ses.open_trip_id())
    if not c:
        if part:
            return A(icon("chat", 16, 2.4), href=link, cls=f"pt-badge pt-badge-new pt-badge-part {cls}".strip(), aria_label="Start a chat about this part", title="Talk about this part")
        return A(icon("plus", 14, 2.6), Span("chat"), href=link, cls=f"pt-badge pt-badge-new {cls}".strip(), aria_label="Start a chat about this plan")
    what = f"{c['n']} message{'' if c['n'] == 1 else 's'}" + (", with a voice note" if c["voice"] else "") + (", with a photo" if c["photo"] else "")
    return A(icon("chat", 16, 2.4), Span(str(c["n"]), cls="pt-n"), icon("mic", 14, 2.4) if c["voice"] else "", href=link, cls=f"pt-badge {cls}".strip(), aria_label=f"Open the chat: {what}")


# ---- the chat ---------------------------------------------------------------------------------------------------------------

def _head(a, p, session):
    t = cal.trip("", ses.booking(session))
    d = t.depart.fromordinal(t.depart.toordinal() + a.day)
    when = f"{d.strftime('%a %b').upper()} {d.day} · {cal.fmt_time(a.start)} – {cal.fmt_time(a.end)}"
    if p:
        return f"{a.title.upper()} · {p['time_of_day'].upper() if p['time_of_day'] else when}", p["name"]
    return when, a.title


def content(session, a, p):
    its = plantalk.items(session, a.id, p["id"] if p else "")
    me, zone = ses.current_traveler(session).id, ses.trip_zone(session)
    trip = ses.open_trip_id()
    part = p["id"] if p else ""
    last = its[-1]["n"] if its else 0
    poll = f"/trip/talk/items?act={quote(a.id)}" + (f"&part={quote(part)}" if part else "")
    who = a.title if not p else f"{p['name']} · {a.title}"
    return Div(
        A(icon("chev-left", 18, 2.4), "Back to the day", href=f"/trip/canvas?day={a.day}" + (f"&trip={quote(trip)}" if trip else ""), cls="fp-back", id="pt-back"),
        Div(*tab_family.fragment(its, me, zone), id="ft-thread", cls="ft-thread", data_last=str(last), data_poll=str(POLL_MS), data_trip=trip, data_poll_url=poll, role="log", aria_live="polite", aria_label=f"Chat: {who}"),
        P("Nothing said here yet. Write a note, add a photo or leave a voice note.", id="ft-empty", cls="ft-empty", hidden=bool(its)),
        Div(Span(cls="pt-dot", aria_hidden="true"), Span("0:00", id="pt-timer", cls="pt-timer", role="timer"), Span("Recording", cls="pt-state", id="pt-state"),
            Button(icon("x", 18, 2.4), Span("Cancel"), type="button", id="pt-cancel", cls="pt-btn pt-cancel"),
            Button(icon("arrow-right", 18, 2.4), Span("Send"), type="button", id="pt-rec-send", cls="pt-btn pt-send"),
            id="pt-rec", cls="pt-rec", hidden=True),
        Form(Input(type="hidden", name="trip", value=trip), Input(type="hidden", name="act", value=a.id), Input(type="hidden", name="part", value=part),
             Input(type="text", name="text", id="ft-text", maxlength=str(familythread.MAX_MESSAGE), placeholder="Message the family", autocomplete="off", aria_label=f"Message about {who}", cls="ft-input", required=True),
             Label(icon("camera", 20, 2.2), Span("Add a photo", cls="sr-only"), fr="pt-photo", id="pt-photo-btn", cls="ft-round pt-photo-btn", hidden=True),
             Button(icon("mic", 20, 2.2), Span("Record a voice note", cls="sr-only"), type="button", id="pt-mic", cls="ft-round", hidden=True),
             Button(icon("arrow-right", 20, 2.4), Span("Send", cls="sr-only"), type="submit", id="ft-send", cls="ft-send"),
             method="post", action="/trip/talk/message", id="ft-compose", cls="ft-compose"),
        Input(type="file", id="pt-photo", accept="image/*", cls="sr-only", aria_label="Add a photo", data_max=str(photos.MAX_BYTES)),      # focusable (visually hidden): a keyboard or screen reader reaches it; the label is what a finger taps
        P("", id="ft-error", cls="ft-error", role="alert", hidden=True),
        id="ft", cls="ft pt", data_act=a.id, data_part=part, data_max_secs=str(voicenotes.MAX_SECONDS), data_url="/trip/talk")


def chat_page(session, act, part):
    a, p = plantalk.target(session, act, part)
    kicker, title = _head(a, p, session)
    return phone.shell("today", phone.header(kicker, title), Main(content(session, a, p), id="main", cls="ph-main"), title=title, head=HEAD, scripts=SCRIPTS)


# ---- the routes -------------------------------------------------------------------------------------------------------------

class UploadLimit:
    """Refuse an oversized upload from its Content-Length, before a byte of the body is read or parsed (the session beforeware parses forms)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"] in LIMITS:
            headers = dict(scope["headers"])
            if b"content-length" not in headers:
                await PlainTextResponse("Send the file with its length.", status_code=411)(scope, receive, send)
                return
            try:
                size = int(headers[b"content-length"] or 0)
            except ValueError:
                size = 0
            if size > LIMITS[scope["path"]] + OVERHEAD:
                what = "photo" if scope["path"].endswith("photo") else "voice note"
                await PlainTextResponse(f"That {what} is too large (at most {LIMITS[scope['path']] // (1024 * 1024)} MB).", status_code=413)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _signed_in(session):
    return ses.current_traveler(session) is not None


def _new(session, act, part, since, trip=""):
    """The chat's items after `since` as a fragment (X-Thread-Last holds the highest number); 409 when the page was drawn for another trip."""
    try:
        its = plantalk.items(session, act, part, since=max(0, since), trip=trip or None)
    except familythread.StaleTrip:
        return PlainTextResponse(plantalk.STALE, status_code=409)
    me, zone = ses.current_traveler(session).id, ses.trip_zone(session)
    body = "".join(to_xml(v) for v in tab_family.fragment(its, me, zone))
    return Response(body, media_type="text/html; charset=utf-8", headers={"X-Thread-Last": str(its[-1]["n"] if its else max(0, since)), "Cache-Control": "no-store"})


def _done(request, session, act, part, since, trip, error=None, status=400):
    """The answer to a write: the new items (script), a plain message with a status (script, refused), or a redirect to the chat."""
    if request.headers.get("x-fragment") == "1":
        return PlainTextResponse(error, status_code=status) if error else _new(session, act, part, since, trip)
    return RedirectResponse(plantalk.url(act, part, trip), status_code=303)


def _known(e):
    return getattr(e, "status", 409 if isinstance(e, familythread.StaleTrip) else 400)


def register(app):
    app.add_middleware(UploadLimit)

    @app.get("/trip/talk")
    def chat(request, session, act: str = "", part: str = ""):
        if (r := phone.guard(session, plantalk.url(act[:20], part[:40]))):      # signing in comes back to the same chat, part included
            return r
        try:
            return chat_page(session, act, part)
        except familythread.ThreadError:
            return RedirectResponse("/trip/canvas", status_code=303)

    @app.get("/trip/talk/items")
    def items(session, act: str = "", part: str = "", since: int = 0, trip: str = ""):
        return _new(session, act, part, since, trip) if _signed_in(session) else Response(status_code=401)

    @app.post("/trip/talk/message")
    def message(request, session, act: str = "", part: str = "", text: str = "", since: int = 0, trip: str = ""):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        try:
            plantalk.post_message(session, act, part, text, trip=trip or None)
        except familythread.ThreadError as e:
            return _done(request, session, act, part, since, trip, str(e), _known(e))
        return _done(request, session, act, part, since, trip)

    @app.post("/trip/talk/voice")
    async def voice(request, session):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        form = await request.form()
        act, part, trip, since = form.get("act") or "", form.get("part") or "", form.get("trip") or "", int(form.get("since") or 0) if str(form.get("since") or "0").isdigit() else 0
        f = form.get("voice")
        if not hasattr(f, "read"):
            return _done(request, session, act, part, since, trip, "Record a voice note first.", 400)
        data = await f.read(voicenotes.MAX_BYTES + 1)
        try:
            await run_in_threadpool(plantalk.post_voice, session, act, part, data, form.get("secs"), trip or None)
        except (familythread.ThreadError, voicenotes.VoiceError) as e:
            return _done(request, session, act, part, since, trip, str(e), _known(e))
        return _done(request, session, act, part, since, trip)

    @app.post("/trip/talk/photo")
    async def photo(request, session):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        form = await request.form()
        act, part, trip, since = form.get("act") or "", form.get("part") or "", form.get("trip") or "", int(form.get("since") or 0) if str(form.get("since") or "0").isdigit() else 0
        f = form.get("photo")
        if not hasattr(f, "read"):
            return _done(request, session, act, part, since, trip, "Choose a photo first.", 400)
        data = await f.read(photos.MAX_BYTES + 1)
        try:
            await run_in_threadpool(plantalk.post_photo, session, act, part, data, form.get("caption") or "", trip or None)
        except (familythread.ThreadError, photos.PhotoError) as e:
            return _done(request, session, act, part, since, trip, str(e), _known(e))
        return _done(request, session, act, part, since, trip)

    @app.get("/trip/talk/voice/{item}")
    def audio(session, item: str):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        found = plantalk.voice_file(session, item)
        if found is None:
            return Response("Not found.", status_code=404)
        path, mime = found
        return FileResponse(path, media_type=mime, headers={"Cache-Control": "private, no-cache", "X-Content-Type-Options": "nosniff", "Accept-Ranges": "bytes"})
