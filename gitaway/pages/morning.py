"""The "Morning plan" card on the phone Today view (F-066) and the four routes behind it. The logic is gitaway.morning.

POST /trip/morning          turn it on for this device (endpoint, p256dh, authkey, time)       -> {"on": true, "time": "07:30"}
POST /trip/morning/time     change this device's time (endpoint, time)                          -> {"on": true, "time": "06:45"}
POST /trip/morning/off      turn it off for this device (endpoint)                              -> {"on": false, "time": "07:30"}
POST /trip/morning/status   is this device on, and at what time (endpoint)                      -> {"on": true, "time": "07:30"}

A person manages their own phone, so every member may call these (viewers too: gitaway.access lists them open). Signed out is a 401.
The endpoint is in the body, never the URL, because it is a capability to push to that phone. The page draws the card; assets/js/morning.js
decides which part shows (add to the Home Screen / switch / blocked) because only the browser knows.
"""

from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fasthtml.common import Button, Div, Input, Label, Link, P, Script, Span
from starlette.responses import JSONResponse

from gitaway import morning, session as ses
from gitaway.icons import icon

HEAD = (Link(rel="stylesheet", href="/assets/css/morning.css"),)
MAX_ENDPOINT = 2048
MAX_KEY = 256


def card(zone=""):
    """The card, or "" when push is not set up on this server. Starts in the "add to the Home Screen" state; morning.js moves it on."""
    if not morning.configured():
        return ""
    label = ""
    try:
        label = datetime.now(ZoneInfo(zone)).tzname() if zone else ""
    except Exception:
        label = ""
    default = morning.hhmm(morning.DEFAULT_MIN)
    return Div(
        Div(Span(icon("bell", 24, 2.2), cls="mp-ico", aria_hidden="true"),
            Div(Span("Morning plan", cls="tp-what"), Span("Today's plan on your phone each trip morning", cls="tp-sub", id="tp-morning-sub"), cls="mp-text"),
            Button(Span(cls="mp-knob"), Span("Morning plan", cls="sr-only"), type="button", role="switch", aria_checked="false", id="tp-morning-switch", cls="mp-switch", hidden=True),
            cls="mp-row"),
        P("Add GitAway to your Home Screen to get a morning plan.", Span("In Safari tap Share, then Add to Home Screen, and open GitAway from there.", cls="mp-how"), cls="mp-install", id="tp-morning-install"),
        P("Notifications are off for GitAway. Turn them on in your phone's Settings, then try again.", cls="mp-blocked", id="tp-morning-blocked", role="status", hidden=True),
        Div(Label(Span("Send it at", cls="mp-when"), Input(type="time", id="tp-morning-time", value=default, step="900", data_ga_label="Morning plan time")),
            Span(f"Trip time{' (' + label + ')' if label else ''}", cls="mp-zone"), cls="mp-time", id="tp-morning-timerow", hidden=True),
        P("", cls="mp-error", id="tp-morning-error", role="alert", hidden=True),
        Script(src="/assets/js/morning.js", defer=True),
        id="tp-morning", cls="mp", data_key=morning.vapid()["public"], data_state="install")


def _fail(message, code=400):
    return JSONResponse({"error": message}, status_code=code)


def _valid_endpoint(endpoint):
    u = urlparse(endpoint or "")
    return len(endpoint or "") <= MAX_ENDPOINT and u.scheme == "https" and bool(u.netloc)


def register(app):
    def who(session):
        return ses.current_traveler(session) is not None

    @app.post("/trip/morning")
    def turn_on(session, endpoint: str = "", p256dh: str = "", authkey: str = "", time: str = ""):
        if not who(session):
            return _fail("Sign in first.", 401)
        at = morning.parse_time(time) if time else morning.DEFAULT_MIN
        if not _valid_endpoint(endpoint) or not (0 < len(p256dh) <= MAX_KEY) or not (0 < len(authkey) <= MAX_KEY) or at is None:
            return _fail("That subscription did not look right.")
        done = morning.subscribe(session, endpoint, p256dh, authkey, at)
        return JSONResponse(done) if done else _fail("Sign in first.", 401)

    @app.post("/trip/morning/time")
    def change_time(session, endpoint: str = "", time: str = ""):
        if not who(session):
            return _fail("Sign in first.", 401)
        at = morning.parse_time(time)
        if at is None or not _valid_endpoint(endpoint):
            return _fail("Pick a time like 7:30 AM.")
        done = morning.set_time(session, endpoint, at)
        return JSONResponse(done) if done else _fail("Turn the morning plan on first.", 404)

    @app.post("/trip/morning/off")
    def turn_off(session, endpoint: str = ""):
        if not who(session):
            return _fail("Sign in first.", 401)
        done = morning.unsubscribe(session, endpoint)
        return JSONResponse(done) if done else _fail("Sign in first.", 401)

    @app.post("/trip/morning/status")
    def current(session, endpoint: str = ""):
        if not who(session):
            return _fail("Sign in first.", 401)
        found = morning.status(session, endpoint)
        return JSONResponse(found) if found else _fail("Sign in first.", 401)
