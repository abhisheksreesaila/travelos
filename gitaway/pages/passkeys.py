"""Face ID sign-in routes and cards (F-074). The logic is gitaway.passkeys; assets/js/passkeys.js does the browser half.

POST /passkeys/register/options  signed in    -> the options for navigator.credentials.create
POST /passkeys/register          signed in    -> {"ok": true, "id", "name"} after the browser's answer checks out
POST /passkeys/auth/options      signed out   -> the options for navigator.credentials.get (any passkey for this site)
POST /passkeys/auth              signed out   -> {"ok": true, "next", "name"} and the session, exactly as after Google sign-in
POST /passkeys/remove            signed in    -> removes one of my own passkeys, back to /family

Every one is open to any member or visitor in gitaway.access (they change only the person's own sign-in, never a family's plans).
CSRF: bodies are JSON only (a cross-site form cannot send that without a preflight), an Origin header, when present, must be this site's, and the
session cookie is SameSite=Lax. Answers never echo credential material.
"""

import json

from fasthtml.common import Button, Div, Form, H2, Input, Link, P, Script, Section, Span
from starlette.responses import JSONResponse, RedirectResponse

from gitaway import auth, passkeys, session as ses
from gitaway.icons import icon

HEAD = (Link(rel="stylesheet", href="/assets/css/passkeys.css"), Script(src="/assets/js/passkeys.js", defer=True))
SCRIPT = Script(src="/assets/js/passkeys.js", defer=True)


def _fail(message, code=400):
    return JSONResponse({"ok": False, "error": message}, status_code=code)


async def _body(request):
    """The JSON object posted, or a refusal response. Returns (data, None) or (None, response)."""
    rp = passkeys.relying_party(request)
    if rp is None:
        return None, _fail("Face ID is not set up on this site.", 404)
    origin = request.headers.get("origin")
    if origin is not None and origin != rp[1]:
        return None, _fail("That did not come from this site.", 403)
    if (request.headers.get("content-type") or "").split(";")[0].strip().lower() != "application/json":
        return None, _fail("That was not a Face ID request.")
    try:
        data = await request.json()
    except Exception:
        return None, _fail("That was not a Face ID request.")
    return (data, None) if isinstance(data, dict) else (None, _fail("That was not a Face ID request."))


def card(session, *, today=False):
    """"Use Face ID next time": hidden until passkeys.js finds this browser can make one (and, on Today, that this is the Home Screen app).
    "" when the site cannot do passkeys or the person has one already."""
    if not passkeys.configured() or not session.get("user_id"):
        return ""
    return Div(
        Div(Span(icon("face-id", 24, 2.2), cls="pk-ico", aria_hidden="true"),
            Div(Span("Use Face ID next time", cls="tp-what pk-what"), Span("Skip the Google step on this phone.", cls="tp-sub pk-sub"), cls="pk-text"), cls="pk-row"),
        Div(Button("Turn on Face ID", type="button", id="pk-add", cls="btn btn-primary btn-sm pk-go"),
            Button("Not now", type="button", id="pk-later", cls="btn btn-sm pk-later") if today else "", cls="pk-actions"),
        P("", id="pk-error", role="alert", cls="pk-error", hidden=True),
        P("Face ID is on for this phone.", id="pk-done", role="status", cls="pk-done", hidden=True),
        Script(src="/assets/js/passkeys.js", defer=True),
        id="pk-card", cls="pk-card", data_passkey="add", data_where="today" if today else "family", hidden=True)


def today_card(session):
    """The card on the phone Today view: only for someone who has no passkey yet; passkeys.js shows it in the Home Screen app, once per phone."""
    return card(session, today=True) if session.get("user_id") and not passkeys.count(session["user_id"]) else ""


def family_section(request, session):
    """"This phone" on /family: the card (always, while there is no passkey) and the list of this person's passkeys with Remove."""
    if not passkeys.available(request):
        return ""
    mine = passkeys.listing(session["user_id"])
    rows = [Div(Span(p["name"], cls="pk-name"), Span(f"Added {p['created_at'][:10]}" + (f" · used {p['last_used'][:10]}" if p["last_used"] else " · not used yet"), cls="pk-when"),
                Form(Input(type="hidden", name="id", value=p["id"]), Button("Remove", type="submit", cls="btn btn-sm fam-btn fam-remove", aria_label=f"Remove Face ID for {p['name']}"),
                     action="/passkeys/remove", method="post", cls="fam-inline"), cls="pk-item", data_passkey_id=p["id"]) for p in mine]
    add = card(session) if not mine else Div(
        Button("Add another phone", type="button", id="pk-add", cls="btn btn-sm pk-go", hidden=True), P("", id="pk-error", role="alert", cls="pk-error", hidden=True),
        P("Face ID is on for this phone.", id="pk-done", role="status", cls="pk-done", hidden=True), SCRIPT, id="pk-card", cls="pk-more", data_passkey="add", data_where="family")
    return Section(H2("This phone", id="fam-phone-id-h"),
                   P("Sign in with Face ID or your fingerprint instead of going through Google each time.", cls="fam-sub"),
                   add, Div(*rows, cls="pk-list", id="pk-list") if rows else "",
                   aria_labelledby="fam-phone-id-h", id="this-phone", cls="fam-sec")


def register(app):
    @app.post("/passkeys/register/options")
    async def register_options(request, session):
        data, bad = await _body(request)
        if bad:
            return bad
        if not ses.current_traveler(session):
            return _fail("Sign in first.", 401)
        try:
            return JSONResponse(json.loads(passkeys.registration_options(session, request, session["user_id"], session.get("email") or "")))
        except passkeys.PasskeyError as e:
            return _fail(str(e))

    @app.post("/passkeys/register")
    async def register_done(request, session):
        data, bad = await _body(request)
        if bad:
            return bad
        if not ses.current_traveler(session):
            return _fail("Sign in first.", 401)
        try:
            made = passkeys.register(session, request, session["user_id"], data.get("credential"), request.headers.get("user-agent", ""))
        except passkeys.PasskeyError as e:
            return _fail(str(e))
        return JSONResponse({"ok": True, **made})

    @app.post("/passkeys/auth/options")
    async def auth_options(request, session):
        data, bad = await _body(request)
        if bad:
            return bad
        try:
            return JSONResponse(json.loads(passkeys.authentication_options(session, request)))
        except passkeys.PasskeyError as e:
            return _fail(str(e))

    @app.post("/passkeys/auth")
    async def auth_done(request, session):
        data, bad = await _body(request)
        if bad:
            return bad
        from gitaway.pages.signin import _continue
        try:
            row = passkeys.authenticate(session, request, data.get("credential"))
            passkeys.sign_in(session, row)
        except passkeys.PasskeyError as e:
            return _fail(str(e))
        auth.make_room(session)
        next_path = ses.safe_next(data.get("next"), "/start")
        landing = "/trip" if next_path == "/start" else next_path   # no destination: open Today (it sends someone with no trip on to /start)
        intent = data.get("intent") if data.get("intent") in ses.INTENTS else ""
        _continue(session, intent, next_path)
        return JSONResponse({"ok": True, "next": landing, "name": ses.current_traveler(session).name.split()[0]})

    @app.post("/passkeys/remove")
    def remove(request, session, id: str = ""):
        if not ses.current_traveler(session):
            return RedirectResponse("/signin?next=/family", status_code=303)
        passkeys.remove(session["user_id"], id)
        return RedirectResponse("/family#this-phone", status_code=303)
