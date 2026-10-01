"""Sign-in (F-017, F-039): /signin?next=<local path>&intent=<save|pay|invite|fork>.

Everything is browsable signed out; save, pay, invite and fork land here, then continue to `next`. Without a `next`
the traveler lands on /start, "Where to?" (F-035).
Google sign-in is /login and /auth/callback (fh-saas); the local dev sign-in is a POST here (see gitaway.auth).
"""

from urllib.parse import quote

from fasthtml.common import A, Button, Div, Form, H2, Input, Label, Link, P, Script, Span, to_xml
from fh_saas.utils_auth import handle_login_request, handle_logout, handle_oauth_callback
from starlette.responses import RedirectResponse, Response

from gitaway import auth, session as ses
from gitaway.layout import clear_site_data, page

HEAD = (Link(rel="stylesheet", href="/assets/css/signin.css"), Script(src="/assets/js/signin.js", defer=True))

TITLES = {
    "pay": "Sign in to book this trip",
    "fork": "Sign in to fork this trip",
    "invite": "Sign in to invite your crew",
    "save": "Sign in to save this trip",
    "publish": "Sign in to publish your trip",
}


def _intent(value):
    return value if value in ses.INTENTS else "save"


def cancel_href(next_path):
    """Cancel goes back to the picks: the pay sheet itself would only bounce a signed-out traveler back here."""
    if next_path.startswith("/creators/finish"):
        return "/creators/draft"   # the finish page bounces a signed-out traveler straight back here
    return next_path.replace("/plan/pay?", "/plan?", 1) if next_path.startswith("/plan/pay?") else next_path


def dialog(next_path, intent, asked=None, dev=False, google=False, error=""):
    """`asked` is the intent the link carried ("" for a plain Sign in); it is what the forms post back.

    `google` shows the Google button (keys are set); `dev` shows the local email form (flag on and request from this machine).
    """
    asked = intent if asked is None else asked
    hidden = (Input(type="hidden", name="next", value=next_path), Input(type="hidden", name="intent", value=asked))
    google_btn = A("Sign in with Google", href=f"/login?next={quote(next_path, safe='')}&intent={asked}", cls="btn btn-ink si-google", id="si-google") if google else ""
    dev_form = Form(
        Label(Span("Email", cls="si-label"), Input(type="email", name="email", id="si-email", placeholder="you@example.com", required=True, autocomplete="email",
                                                   **({"aria_invalid": "true", "aria_describedby": "si-error"} if error else {})), cls="si-field"),
        P(error, id="si-error", role="alert", cls="si-error") if error else "",
        Button("Dev sign-in (local only)", type="submit", cls="btn si-dev"),
        P("Local development only. It never appears on a real site.", cls="si-note"),
        *hidden, action="/signin", method="post", id="si-dev-form", cls="si-dev-form",
    ) if dev else ""
    nothing = P("Sign-in isn't set up on this server yet. See docs/setup.md.", cls="si-note", id="si-off") if not (google or dev) else ""
    return Div(
        Div(
            Span("One tiny step", cls="sticker si-sticker"),
            H2(TITLES[intent], id="si-title"),
            P("We'll keep your picks exactly as they are." + (" Your family space is made the first time you sign in." if google or dev else ""), id="si-desc"),
            google_btn, dev_form, nothing,
            Div(A("Cancel", href=cancel_href(next_path), id="si-cancel", cls="btn btn-sm"), cls="si-actions"),
            cls="si-body",
        ),
        role="dialog", aria_modal="true", aria_labelledby="si-title", aria_describedby="si-desc", id="si-dialog", cls="si-card",
    )


def _continue(session, intent, next_path):
    """What the signed-in traveler meant to do before the sign-in: fork or save the trip at `next`."""
    try:
        if intent == "fork":
            ses.add_fork(session, next_path)
        elif intent == "save":  # only when asked for: a plain "Sign in" on a trip page must not save it
            ses.add_save(session, next_path)
    except ses.KeepError as e:
        from gitaway.pages.forks import sorry
        return sorry(str(e), next_path)


def _page(request, next_path, intent, asked, error="", status=200):
    body = dialog(next_path, intent, asked, dev=auth.dev_login_allowed(request), google=auth.google_enabled(), error=error)
    out = page("Sign in", Div(body, cls="si-backdrop"), head=HEAD)
    return out if status == 200 else Response(to_xml(out), status_code=status, media_type="text/html")


def register(app):
    @app.get("/signin")
    def signin_page(request, session, next: str = "/start", intent: str = ""):
        next_path, asked, intent = ses.safe_next(next), (intent if intent in ses.INTENTS else ""), _intent(intent)
        if ses.current_traveler(session):
            if (full := _continue(session, asked, next_path)):
                return full
            return RedirectResponse(next_path, status_code=303)
        return _page(request, next_path, intent, asked)

    @app.post("/signin")
    def signin_submit(request, session, email: str = "", next: str = "/start", intent: str = ""):
        """The local dev sign-in: any email, only with GITAWAY_DEV_LOGIN=1 and a request from this machine."""
        if not auth.dev_login_allowed(request):
            return Response("Dev sign-in is off.", status_code=403)
        next_path, asked = ses.safe_next(next), (intent if intent in ses.INTENTS else "")
        if not (clean := auth.clean_email(email)):
            return _page(request, next_path, _intent(asked), asked, "Type a full email address, like you@example.com.", status=400)
        auth.sign_in_dev(session, clean)
        auth.make_room(session)
        if (full := _continue(session, asked, next_path)):
            return full
        return RedirectResponse(next_path, status_code=303)

    @app.get("/login")
    def login(request, session, next: str = "/start", intent: str = ""):
        """Start Google sign-in through fh-saas. Without Google keys this is just the sign-in page."""
        next_path = ses.safe_next(next, "/start")
        if not auth.google_enabled():
            return RedirectResponse(f"/signin?next={quote(next_path, safe='')}&intent={intent if intent in ses.INTENTS else ''}", status_code=303)
        next_path = next_path if len(next_path) <= auth.MAX_NEXT else "/start"  # the cookie is tiny; a long address is not worth keeping
        session["login_next"], session["login_intent"] = next_path, (intent if intent in ses.INTENTS else "")
        return RedirectResponse(handle_login_request(request, session), status_code=303)

    @app.get("/auth/callback")
    def auth_callback(request, session, code: str = "", state: str = "", error: str = ""):
        """Google sends people back here. fh-saas verifies, signs in and makes the family tenant; we then go where they were headed."""
        next_path, asked = ses.safe_next(session.get("login_next"), "/start"), session.get("login_intent") or ""
        try:
            if error or not code or not state:  # Google sends ?error=access_denied (no code) when the person cancels
                raise ValueError("no code")
            handle_oauth_callback(code, state, request, session)  # its own redirect (/dashboard) is not ours
        except Exception:
            for key in ("oauth_state", "login_next", "login_intent"):
                session.pop(key, None)
            return Response("That sign-in did not work. Go back and try again.", status_code=400)
        auth.make_room(session)
        session.pop("login_next", None), session.pop("login_intent", None)
        if (full := _continue(session, asked, next_path)):
            return full
        return RedirectResponse(next_path, status_code=303)

    @app.post("/fork")
    def fork(session, next: str = "/"):
        """Fork the trip at `next` (/trips/<slug>) for the signed-in traveler, then go back. Signed out: sign in first."""
        next_path = ses.safe_next(next)
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={quote(next_path, safe='/')}&intent=fork", status_code=303)
        try:
            ses.add_fork(session, next_path)
        except ses.KeepError as e:
            from gitaway.pages.forks import sorry
            return sorry(str(e), next_path)
        return RedirectResponse(next_path, status_code=303)

    @app.route("/logout", methods=["GET", "POST"])
    @app.post("/signout")  # the header form posts here (F-044's pwa.js clears its page cache on that form); same handler
    def logout(session):
        """Sign out through fh-saas's handle_logout, which clears the session. Until F-040 moves trip state into SQLite
        the cookie still holds some (calendar, forks), so everything that is not sign-in state is put back."""
        keep = {k: v for k, v in session.items() if k not in ses.AUTH_KEYS}
        handle_logout(session)
        keep.pop("cr", None)  # the creator draft belongs to the person who made it, not the next one at this browser
        session.update(keep)
        return clear_site_data(RedirectResponse("/", status_code=303))
