"""The Family tab (F-070): the trip's thread of messages, photos and plan-change cards, a compose bar, and the Quiet switch.

GET  /trip/family/thread?since=N   the thread items after N as an HTML fragment (the page polls it every ~5 s while it is visible);
                                   the highest item number is in the `X-Thread-Last` header
POST /trip/family/message          write a message (any member, viewers too: see gitaway/familythread.py); with the header `X-Fragment: 1`
                                   the answer is the fragment of what is new, otherwise the page is shown again
POST /trip/family/quiet            turn this person's pushes for the thread off (quiet=1) or on (quiet=0)

The two POSTs are on gitaway.access.OPEN_POSTS (and tests/test_roles.py) on purpose: they change nothing in the family's plans.
A photo card is drawn when the item carries an image address (F-071 posts them). The tab has a Chat / Photos switch (`?view=photos` opens the
Photos view, gitaway/pages/photos.py, which also registers the photo routes) and a camera button in the compose row.
"""

import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

from fasthtml.common import A, Audio, Button, Div, Form, Img, Input, Link, Noscript, P, Span, to_xml
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response

from gitaway import familythread, plantalk, session as ses
from gitaway.icons import icon
from gitaway.pages import photos as photos_ui

TITLE = "Family"
HEAD = (*photos_ui.HEAD, Link(rel="stylesheet", href="/assets/css/plantalk.css"))
SCRIPTS = ("/assets/js/thread.js", "/assets/js/photos.js", "/assets/js/voicenote.js")
POLL_MS = 5000
QUIET_ON = "Quiet: no notifications from the family thread."
QUIET_OFF = "Everyone gets a notification when the plan changes."
_COLORS = ("sun", "sky", "grape", "mint", "bubble")
_ICONS = {"add": "plus", "move": "pencil", "remove": "x", "change": "note"}
_TINTS = {"add": "mint", "remove": "bubble"}


def _clock(at, zone):
    try:
        return datetime.fromisoformat(at).astimezone(ZoneInfo(zone)).strftime("%I:%M %p").lstrip("0")
    except (ValueError, TypeError):
        return ""


def _avatar(name, user):
    color = _COLORS[int(hashlib.sha256((user or name).encode()).hexdigest(), 16) % len(_COLORS)]
    return Span((name or "?")[:1].upper(), cls=f"ft-av fill-{color}", aria_hidden="true")


def length(secs) -> str:
    return f"{int(secs) // 60}:{int(secs) % 60:02d}"


def voice_player(it):
    """A voice note that plays in place (assets/js/voicenote.js): a play button, a progress bar and its length. The audio is fetched only when played."""
    secs = int(it["payload"].get("secs") or 0)
    src = f"/trip/talk/voice/{it['id']}"
    return Div(Button(icon("play", 20, 2.2), Span("Play voice note", cls="sr-only"), type="button", cls="vn-btn", data_vn="btn"),
               Span(Span(cls="vn-fill", data_vn="fill"), cls="vn-bar", aria_hidden="true"),
               Span(length(secs), cls="vn-len", data_vn="len", data_total=length(secs)),
               Audio(src=src, preload="none", cls="vn-audio", data_vn="audio"), Noscript(Audio(src=src, controls=True, preload="none")),
               cls="vn", data_secs=str(secs))


def _on(it, labels):
    """The small "on Lunch · Universal Studios" tag of a message that belongs to a plan (or part), linking to that plan's chat."""
    act, part = it["payload"].get("act"), it["payload"].get("part") or ""
    if not act or labels is None or (act, part) not in labels:
        return ""
    return A(icon("chat", 14, 2.4), Span(f"on {labels[(act, part)]}"), href=plantalk.url(act, part), cls="ft-on")


def item_view(it, me, zone, labels=None):
    """One thread entry. Changes are cards, messages are bubbles (mine on the right), photos show their image, voice notes play in place. A message on a plan
    carries a tag naming it when `labels` ({(plan, part): label}) is given (the Family tab; the plan's own chat does not repeat it)."""
    at = _clock(it["at"], zone)
    base = {"data_n": str(it["n"]), "data_kind": it["kind"]}
    if it["payload"].get("cid"):
        base["data_cid"] = it["payload"]["cid"]
    if it["kind"] == "change":
        action = it["payload"].get("action", "change")
        return Div(Span(icon(_ICONS.get(action, "note"), 18, 2.2), cls="ft-si", aria_hidden="true"),
                   Span(Span(it["text"], cls="ft-what"), Span(f"Plan change · {at}", cls="ft-meta"), cls="ft-x"),
                   cls=f"ft-sys ft-{_TINTS.get(action, 'plain')}", **base)
    mine = it["author"] == me
    tag = _on(it, labels)
    if it["kind"] == "photo":
        url = it["payload"].get("url", "")
        if familythread._image_url(url):
            pid = it["payload"].get("photo")
            img = Img(src=url, alt=it["text"] or f"Photo from {it['name']}", loading="lazy", cls="ft-photo")
            body = Div(tag, Span(it["name"], cls="ft-nm") if pid and not mine else "", A(img, href=f"/trip/photos/{pid}", cls="ft-photo-link") if pid else img, Span(it["text"], cls="ft-cap") if it["text"] else "", Span(at, cls="ft-time") if pid else "", cls="ft-photo-bub")
            return Div(_avatar(it["name"], it["author"]) if not mine else "", body, cls=f"ft-msg{' ft-me' if mine else ''}", **base)
        return ""
    if it["kind"] == "voice":
        bubble = Div(tag, Span(it["name"], cls="ft-nm") if not mine else "", voice_player(it), Span(at, cls="ft-time"), cls="ft-bub ft-voice")
    else:
        bubble = Div(tag, Span(it["name"], cls="ft-nm") if not mine else "", it["text"], Span(at, cls="ft-time"), cls="ft-bub")
    return Div(_avatar(it["name"], it["author"]) if not mine else "", bubble, cls=f"ft-msg{' ft-me' if mine else ''}", **base)


def fragment(its, me, zone, labels=None):
    return [v for v in (item_view(it, me, zone, labels) for it in its) if v != ""]


def _switch(view):
    on = lambda v: "true" if view == v else "false"  # noqa: E731
    return Div(A("Chat", href="/trip/family", id="fam-chat", cls="fam-seg", data_v="chat", aria_current=on("chat")),
               A("Photos", href="/trip/family?view=photos", id="fam-photos", cls="fam-seg", data_v="photos", aria_current=on("photos")),
               cls="fam-switch", role="group", aria_label="Family view", id="famseg")


def _people(role):
    """The small link at the end of the header line: admins get Invite (the form at /family#invite), everyone else a link to see who is in the family."""
    if role == "admin":
        return A(icon("user-plus", 16, 2.2), Span("Invite"), href="/family#invite", id="ft-invite", cls="ft-people-btn")
    return A(icon("users", 16, 2.2), Span("Family"), href="/family", id="ft-people", cls="ft-people-btn", aria_label="Who's in the family")


def _bar(role, view):
    """One slim header line (F-094): the Chat / Photos text switch on the left, the people link on the right."""
    return Div(_switch(view), _people(role), cls="fam-bar")


def content(request, session):
    view = "photos" if request.query_params.get("view") == "photos" else "chat"
    its = familythread.items(session)
    trip = ses.open_trip_id()
    me, zone = ses.current_traveler(session).id, ses.trip_zone(session)
    last = its[-1]["n"] if its else 0
    quiet = familythread.quiet(session)
    chat = Div(
        Div(Span(icon("bell", 18, 2.2), cls="ft-bell", aria_hidden="true"),
            Span(QUIET_ON if quiet else QUIET_OFF, id="ft-quiet-text", cls="ft-quiet-text", data_on=QUIET_ON, data_off=QUIET_OFF),
            Form(Input(type="hidden", name="quiet", value="0" if quiet else "1", id="ft-quiet-value"),
                 Button(Span(cls="mp-knob"), Span("Quiet", cls="ft-quiet-label"), type="submit", role="switch", aria_checked="true" if quiet else "false", id="ft-quiet", cls=f"mp-switch ft-switch{' is-on' if quiet else ''}"),
                 method="post", action="/trip/family/quiet", cls="ft-quiet-form"),
            cls="ft-notify"),
        Div(*fragment(its, me, zone, plantalk.labels(session)), id="ft-thread", cls="ft-thread", data_last=str(last), data_poll=str(POLL_MS), data_trip=trip, role="log", aria_live="polite", aria_label="Family thread"),
        P("No messages yet. Say hello, or change a plan and it shows up here.", id="ft-empty", cls="ft-empty", hidden=bool(its)),
        Form(Input(type="hidden", name="trip", value=trip),
             Input(type="text", name="text", id="ft-text", maxlength=str(familythread.MAX_MESSAGE), placeholder="Message the family", autocomplete="off", aria_label="Message the family", cls="ft-input", required=True),
             Button(icon("camera", 20, 2.2), Span("Take a photo", cls="sr-only"), type="button", id="ft-camera", cls="ft-round", data_pick="camera"),
             Button(icon("arrow-right", 20, 2.4), Span("Send", cls="sr-only"), type="submit", id="ft-send", cls="ft-send"),
             method="post", action="/trip/family/message", id="ft-compose", cls="ft-compose"),
        P("", id="ft-error", cls="ft-error", role="alert", hidden=True),
        id="ft-chat", cls="ft-panel", data_view="chat", hidden=view != "chat")
    return Div(_bar(getattr(request.state, "family_role", None), view), P("", id="ph-status", cls="fp-status", role="status", hidden=True), chat,
               photos_ui.view(session, hidden=view != "photos", error=request.query_params.get("error", "")[:200] if view == "photos" else ""), photos_ui.pickers(),
               id="ft", cls="ft", data_view=view)


def _signed_in(session):
    return ses.current_traveler(session) is not None


STALE = "This trip changed. Reload the page."
SORRY = "That did not send. Try again."


def _new_items(session, since, trip=""):
    """The items after `since` as an HTML fragment; the highest item number goes in X-Thread-Last. 409 when the page was drawn for another trip."""
    try:
        its = familythread.items(session, since=max(0, since), trip=trip or None)
    except familythread.StaleTrip:
        return PlainTextResponse(STALE, status_code=409)
    me, zone = ses.current_traveler(session).id, ses.trip_zone(session)
    body = "".join(to_xml(v) for v in fragment(its, me, zone, plantalk.labels(session)))
    return Response(body, media_type="text/html; charset=utf-8", headers={"X-Thread-Last": str(its[-1]["n"] if its else max(0, since)), "Cache-Control": "no-store"})


def register(app):
    photos_ui.register(app)

    @app.get("/trip/family/thread")
    def poll(session, since: int = 0, trip: str = ""):
        return _new_items(session, since, trip) if _signed_in(session) else Response(status_code=401)

    @app.post("/trip/family/message")
    def message(request, session, text: str = "", since: int = 0, trip: str = "", cid: str = ""):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        wants_fragment = request.headers.get("x-fragment") == "1"
        try:
            familythread.post_message(session, text, trip=trip or None, cid=cid)
        except familythread.StaleTrip:
            return PlainTextResponse(STALE, status_code=409) if wants_fragment else RedirectResponse("/trip/family", status_code=303)
        except familythread.ThreadError as e:
            return PlainTextResponse(str(e), status_code=400) if wants_fragment else RedirectResponse("/trip/family", status_code=303)
        if not wants_fragment:
            return RedirectResponse("/trip/family", status_code=303)
        return _new_items(session, since, trip)

    @app.post("/trip/family/quiet")
    def quiet(request, session, quiet: str = "1"):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        on = familythread.set_quiet(session, quiet == "1")
        if request.headers.get("x-fragment") == "1":
            return JSONResponse({"quiet": on})
        return RedirectResponse("/trip/family", status_code=303)
