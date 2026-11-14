"""Sign-in (F-017, F-039, F-052; Direction A since F-200): /signin?next=<local path>&intent=<save|pay|invite|fork>.

Everything is browsable signed out; save, pay, invite and fork land here, then continue to `next`. Without a `next`
the traveler lands on /, which opens their trip or the trip matrix (F-231).
Google sign-in is /login and /auth/callback (fh-saas); the local dev sign-in is a POST here (see gitaway.auth).
The page (docs/design/reskin, a-signin): the intent as the title, what signing in is for as a trip card with B's ticket stub (what the card says comes from `next`,
gitaway.signin_context), two big buttons (Google, a passkey); on a laptop the left half carries the line ("Take a trip. Leave a trail.") over the trip's widgets.
"""

from urllib.parse import quote

from fasthtml.common import A, Button, Details, Div, Form, H1, H2, Header, Input, Label, Link, Main, NotStr, P, Script, Span, Summary, Title, to_xml
from fh_saas.utils_auth import handle_login_request, handle_logout
from starlette.responses import RedirectResponse, Response

from gitaway import auth, hostdb, passkeys, session as ses
from gitaway.icons import icon
from gitaway.layout import brand, clear_site_data, mark, preview, styles
from gitaway.signin_context import context

HEAD = (Link(rel="stylesheet", href="/assets/css/signin.css"), Link(rel="stylesheet", href="/assets/css/passkeys.css"), Script(src="/assets/js/signin.js", defer=True), Script(src="/assets/js/passkeys.js", defer=True))

TITLES = {
    "pay": "Sign in to book this trip",
    "fork": "Sign in to fork this trip",
    "invite": "Sign in to invite your crew",
    "save": "Sign in to save this trip",
    "publish": "Sign in to publish your trip",
    "ride": "Sign in to schedule an Uber",
    "join": "Sign in to join your family",
}

LINE = ("Take a trip.", "Leave a trail.")   # the brief's line (docs/briefs/free-and-polished.md "The line")
SUBHEAD = "Share the whole trip, not just the photos, so the next family can follow it, make it theirs, and say thanks."
NEW_HERE = "New here? The same buttons make your account. No password to remember."
# the two small widgets: an icon and a kind (its colour) per pass; the words are the pass's own (s1, s2)
WIDGETS = {"cold": (("food", "k-food"), ("sun", "k-see")), "search": (("bed", "k-stay"), ("users", "k-see")), "fork": (("calendar", "k-stay"), ("calendar", "k-see"))}


def sky(ctx):
    """The decorative half beside the card on a laptop (hidden on a phone): the line, its subhead, and the trip as Direction A widgets: the route on the flight's
    colour (its two codes), and the pass's two small facts (a search's nights and party, a fork's first two days, or the generic pass's)."""
    (i1, k1), (i2, k2) = WIDGETS.get(ctx.kind, WIDGETS["cold"])
    route = Div(Span(ctx.k2 if ctx.kind != "cold" else "ROUTE", cls="si-w-k"), icon("plane", 22, 2.2),
                P(Span(ctx.origin, cls="si-code"), icon("arrow-right", 22, 2.6), Span(ctx.dest, cls="si-code"), cls="si-w-big"),
                P(ctx.v2, cls="si-w-sub"), cls="si-w si-w-route k-flight")
    small = [Div(icon(ico, 22, 2.2), Span(text, cls=f"si-stick si-stick{n}"), cls=f"si-w si-w-small {kind}") for n, (ico, kind, text) in enumerate(((i1, k1, ctx.s1), (i2, k2, ctx.s2)), 1)]
    return Div(
        P(Span(LINE[0]), " ", Span(LINE[1], cls="si-line-two"), cls="si-line"),
        P(SUBHEAD, cls="si-line-sub"),
        Div(route, *small, cls="si-widgets"),
        aria_hidden="true", cls="si-sky")


def welcome():
    """Storyboard frame 2 (F-074): the full-screen moment after a Face ID sign-in. Hidden; passkeys.js fills the name and shows it for a beat before opening Today."""
    return Div(
        Div(mark("si-logo"), Span("GitAway", cls="si-brand"), cls="sw-brand"),
        Span(icon("face-id", 64, 1.8), cls="sw-glyph", aria_hidden="true"),
        H2("Welcome back, ", Span("", id="si-welcome-name"), cls="sw-title"),
        P("Signed in with Face ID. No password, no code by text.", cls="sw-line"),
        P("Your passkey stays on this ", Span("device", id="si-welcome-device"), ".", cls="sw-note"),
        id="si-welcome", cls="si-welcome", role="status", aria_live="polite", hidden=True)


def _intent(value):
    return value if value in ses.INTENTS else "save"


def cancel_href(next_path):
    """Cancel goes back to the picks: the pay sheet itself would only bounce a signed-out traveler back here."""
    if next_path.startswith("/creators/finish"):
        return "/creators/draft"   # the finish page bounces a signed-out traveler straight back here
    if next_path == "/trip" or next_path.startswith("/trip?"):
        return "/"             # /trip bounces a signed-out traveler straight back here
    return next_path.replace("/plan/pay?", "/plan?", 1) if next_path.startswith("/plan/pay?") else next_path


# Google's own G (its sign-in brand guidelines): four fixed colours, the same in light and dark, on the button's own surface
GOOGLE_G = NotStr('<svg viewBox="0 0 48 48" width="20" height="20" focusable="false">'
                  '<path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>'
                  '<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>'
                  '<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>'
                  '<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>'
                  '</svg>')


def dialog(next_path, intent, asked=None, dev=False, google=False, error="", faceid=False):
    """The sign-in card and the half beside it: (card, sky). `asked` is the intent the link carried ("" for a plain Sign in); it is what the
    forms post back.

    `google` shows the Google button (keys are set); `dev` shows the local email form (flag on and request from this machine).
    The trip card is filled from the request (gitaway.signin_context): a search, a fork, or the generic pass.
    """
    asked = intent if asked is None else asked
    ctx = context(next_path, intent)
    hidden = (Input(type="hidden", name="next", value=next_path), Input(type="hidden", name="intent", value=asked))
    google_btn = A(Span(GOOGLE_G, cls="si-g", aria_hidden="true"), "Continue with Google", href=f"/login?next={quote(next_path, safe='')}&intent={asked}",
                   cls="btn si-google", id="si-google") if google else ""
    faceid_btn = Div(Button(icon("face-id", 22, 2.2), "Sign in with Face ID", type="button", id="si-faceid", cls="btn btn-ink si-faceid", hidden=True, data_next=next_path, data_intent=asked),
                     P("", id="si-faceid-status", role="status", cls="si-note si-faceid-status", hidden=True), cls="si-faceid-box") if faceid else ""
    dev_form = Form(
        Label(Span("Email", cls="si-label"), Input(type="email", name="email", id="si-email", placeholder="you@example.com", required=True, autocomplete="email",
                                                   **({"aria_invalid": "true", "aria_describedby": "si-error"} if error else {})), cls="si-field"),
        P(error, id="si-error", role="alert", cls="si-error") if error else "",
        Button("Dev sign-in (local only)", type="submit", cls="btn btn-ink si-dev"),
        P("Local development only. It never appears on a real site.", cls="si-note"),
        *hidden, action="/signin", method="post", id="si-dev-form", cls="si-dev-form",
    ) if dev else ""
    dev_box = Details(Summary(icon("chev-right", 16, 2.6), "Local dev sign-in", cls="si-sum"), dev_form, cls="si-dev-box", **({"open": True} if error or not google else {})) if dev else ""
    nothing = P("Sign-in isn't set up on this server yet. See docs/setup.md.", cls="si-note", id="si-off") if not (google or dev) else ""
    stub = Div(*[Span(Span(k, cls="si-k"), Span(v, cls="si-v"), cls="si-cell") for k, v in (("ROUTE", ctx.route), (ctx.k2, ctx.v2), ("STAY SIGNED IN", "30 days"))], cls="si-stub")
    trip = Div(
        Div(Span(icon("plane" if ctx.kind != "fork" else "fork", 20, 2.2), cls="si-trip-tile k-flight", aria_hidden="true"),
            Div(P(ctx.head, cls="si-dest", id="si-dest"), P(f"{ctx.route} · {ctx.v2}", cls="si-trip-sub"), cls="si-trip-text"), cls="si-trip-top"),
        Div(cls="si-perf", aria_hidden="true"),
        stub, cls="si-trip")
    card = Div(
        H1(TITLES[intent], id="si-title"),
        P(ctx.sub + (" Your family space is made the first time you sign in." if google or dev else ""), id="si-desc"),
        trip,
        Div(google_btn, faceid_btn, nothing, cls="si-buttons"),
        dev_box,
        P(NEW_HERE, cls="si-new") if google or dev or faceid else "",
        P("By continuing you agree to the ", A("Terms", href="/terms"), " and the ", A("Privacy policy", href="/privacy"), ".", cls="si-note si-legal", id="si-legal"),
        role="dialog", aria_modal="true", aria_labelledby="si-title", aria_describedby="si-desc", id="si-dialog", cls="si-card", data_pass=ctx.kind,
    )
    return card, sky(ctx)


def _continue(session, intent, next_path):
    """What the signed-in traveler meant to do before the sign-in: fork or save the trip at `next`."""
    if intent == "fork":
        ses.add_fork(session, next_path)
    elif intent == "save":  # only when asked for: a plain "Sign in" on a trip page must not save it
        ses.add_save(session, next_path)


def _page(request, next_path, intent, asked, error="", status=200):
    """The whole document: a full-screen page (no site nav or footer, D-200-sign-in): the brand and Cancel on top, the card, and on a laptop the half beside it."""
    card, sky_ = dialog(next_path, intent, asked, dev=auth.dev_login_allowed(request), google=auth.google_enabled(), error=error, faceid=passkeys.available(request))
    top = Header(A("Skip to content", href="#main", cls="ga-skip"), Div(brand(), preview(), cls="ga-brand-row"),
                 A(icon("x", 20, 2.6), Span("Cancel", cls="sr-only"), href=cancel_href(next_path), id="si-cancel", cls="si-x"), cls="ga-header si-head")
    out = (Title("GitAway · Sign in"), *styles(*HEAD),
           Div(top, Main(Div(sky_, Div(card, cls="si-pass"), cls="si-wrap"), id="main"), welcome() if passkeys.available(request) else "", data_theme="sunset", cls="ga-page si-page"))
    return out if status == 200 else Response(to_xml(out), status_code=status, media_type="text/html")


def register(app):
    @app.get("/signin")
    def signin_page(request, session, next: str = "/", intent: str = ""):
        next_path, asked, intent = ses.safe_next(next), (intent if intent in ses.INTENTS else ""), _intent(intent)
        if ses.current_traveler(session):
            if (full := _continue(session, asked, next_path)):
                return full
            return RedirectResponse(next_path, status_code=303)
        return _page(request, next_path, intent, asked)

    @app.post("/signin")
    def signin_submit(request, session, email: str = "", next: str = "/", intent: str = ""):
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
    def login(request, session, next: str = "/", intent: str = ""):
        """Start Google sign-in through fh-saas. Without Google keys this is just the sign-in page."""
        next_path = ses.safe_next(next, "/")
        if not auth.google_enabled():
            return RedirectResponse(f"/signin?next={quote(next_path, safe='')}&intent={intent if intent in ses.INTENTS else ''}", status_code=303)
        next_path = next_path if len(next_path) <= auth.MAX_NEXT else "/"  # the cookie is tiny; a long address is not worth keeping
        session["login_next"], session["login_intent"] = next_path, (intent if intent in ses.INTENTS else "")
        return RedirectResponse(handle_login_request(request, session), status_code=303)

    @app.get("/auth/callback")
    def auth_callback(request, session, code: str = "", state: str = "", error: str = ""):
        """Google sends people back here. fh-saas verifies, signs in and makes the family tenant; we then go where they were headed."""
        next_path, asked = ses.safe_next(session.get("login_next"), "/"), session.get("login_intent") or ""
        try:
            if error or not code or not state:  # Google sends ?error=access_denied (no code) when the person cancels
                raise ValueError("no code")
            auth.sign_in_google(code, state, request, session)  # fh-saas's steps, keeping email_verified; joins invited families when verified (F-043)
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
        ses.add_fork(session, next_path)
        return RedirectResponse(next_path, status_code=303)

    @app.route("/logout", methods=["GET", "POST"])
    @app.post("/signout")  # the header form posts here (F-044's pwa.js clears its page cache on that form); same handler
    def logout(session):
        """Sign out through fh-saas's handle_logout, which clears the session. The cookie holds only the sign-in (and a creator draft,
        which belongs to the person who made it, not the next one at this browser); trips, calendar, forks and saves stay in the
        family's database for the next sign-in (F-040, F-041)."""
        handle_logout(session)
        return clear_site_data(RedirectResponse("/", status_code=303))
