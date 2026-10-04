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

from fasthtml.common import A, Button, Div, Form, Img, Input, P, Span, to_xml
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response

from gitaway import familythread, session as ses
from gitaway.icons import icon
from gitaway.pages import photos as photos_ui

TITLE = "Family"
HEAD = photos_ui.HEAD
SCRIPTS = ("/assets/js/thread.js", "/assets/js/photos.js")
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


def item_view(it, me, zone):
    """One thread entry. Changes are cards, messages are bubbles (mine on the right), photos show their image."""
    at = _clock(it["at"], zone)
    base = {"data_n": str(it["n"]), "data_kind": it["kind"]}
    if it["kind"] == "change":
        action = it["payload"].get("action", "change")
        return Div(Span(icon(_ICONS.get(action, "note"), 18, 2.2), cls="ft-si", aria_hidden="true"),
                   Span(Span(it["text"], cls="ft-what"), Span(f"Plan change · {at}", cls="ft-meta"), cls="ft-x"),
                   cls=f"ft-sys ft-{_TINTS.get(action, 'plain')}", **base)
    mine = it["author"] == me
    if it["kind"] == "photo":
        url = it["payload"].get("url", "")
        if familythread._image_url(url):
            body = Div(Img(src=url, alt=it["text"] or f"Photo from {it['name']}", loading="lazy", cls="ft-photo"), Span(it["text"], cls="ft-cap") if it["text"] else "", cls="ft-photo-bub")
            return Div(_avatar(it["name"], it["author"]) if not mine else "", body, cls=f"ft-msg{' ft-me' if mine else ''}", **base)
        return ""
    bubble = Div(Span(it["name"], cls="ft-nm") if not mine else "", it["text"], Span(at, cls="ft-time"), cls="ft-bub")
    return Div(_avatar(it["name"], it["author"]) if not mine else "", bubble, cls=f"ft-msg{' ft-me' if mine else ''}", **base)


def fragment(its, me, zone):
    return [v for v in (item_view(it, me, zone) for it in its) if v != ""]


def _switch(view):
    on = lambda v: "true" if view == v else "false"  # noqa: E731
    return Div(A("Chat", href="/trip/family", id="fam-chat", cls="fam-seg", data_v="chat", aria_current=on("chat")),
               A("Photos", href="/trip/family?view=photos", id="fam-photos", cls="fam-seg", data_v="photos", aria_current=on("photos")),
               cls="fam-switch", role="group", aria_label="Family view", id="famseg")


def _people(role):
    """A row above the switch: admins get the Invite button (the form at /family#invite), everyone else a link to see who is in the family."""
    if role == "admin":
        return Div(A(icon("user-plus", 20, 2.2), Span("Invite"), href="/family#invite", id="fam-invite", cls="btn btn-primary btn-sm fam-invite"), cls="fam-people")
    return Div(A(icon("users", 20, 2.2), Span("Who's in the family"), href="/family", id="fam-invite", cls="btn btn-sm fam-invite"), cls="fam-people")


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
        Div(*fragment(its, me, zone), id="ft-thread", cls="ft-thread", data_last=str(last), data_poll=str(POLL_MS), data_trip=trip, role="log", aria_live="polite", aria_label="Family thread"),
        P("No messages yet. Say hello, or change a plan and it shows up here.", id="ft-empty", cls="ft-empty", hidden=bool(its)),
        Form(Input(type="hidden", name="trip", value=trip),
             Input(type="text", name="text", id="ft-text", maxlength=str(familythread.MAX_MESSAGE), placeholder="Message the family", autocomplete="off", aria_label="Message the family", cls="ft-input", required=True),
             Button(icon("camera", 20, 2.2), Span("Take a photo", cls="sr-only"), type="button", id="ft-camera", cls="ft-round", data_pick="camera"),
             Button(icon("arrow-right", 20, 2.4), Span("Send", cls="sr-only"), type="submit", id="ft-send", cls="ft-send"),
             method="post", action="/trip/family/message", id="ft-compose", cls="ft-compose"),
        P("", id="ft-error", cls="ft-error", role="alert", hidden=True),
        id="ft-chat", cls="ft-panel", data_view="chat", hidden=view != "chat")
    return Div(_people(getattr(request.state, "family_role", None)), _switch(view), P("", id="ph-status", cls="fp-status", role="status", hidden=True), chat,
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
    body = "".join(to_xml(v) for v in fragment(its, me, zone))
    return Response(body, media_type="text/html; charset=utf-8", headers={"X-Thread-Last": str(its[-1]["n"] if its else max(0, since)), "Cache-Control": "no-store"})


def register(app):
    photos_ui.register(app)

    @app.get("/trip/family/thread")
    def poll(session, since: int = 0, trip: str = ""):
        return _new_items(session, since, trip) if _signed_in(session) else Response(status_code=401)

    @app.post("/trip/family/message")
    def message(request, session, text: str = "", since: int = 0, trip: str = ""):
        if not _signed_in(session):
            return Response("Sign in first.", status_code=401)
        wants_fragment = request.headers.get("x-fragment") == "1"
        try:
            familythread.post_message(session, text, trip=trip or None)
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
