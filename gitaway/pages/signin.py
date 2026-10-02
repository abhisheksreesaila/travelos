"""Sign-in (F-017, F-039, F-052): /signin?next=<local path>&intent=<save|pay|invite|fork>.

Everything is browsable signed out; save, pay, invite and fork land here, then continue to `next`. Without a `next`
the traveler lands on /start, "Where to?" (F-035).
Google sign-in is /login and /auth/callback (fh-saas); the local dev sign-in is a POST here (see gitaway.auth).
The page is a boarding pass under an animated sky; what the pass says comes from `next` (gitaway.signin_context).
"""

from urllib.parse import quote

from fasthtml.common import A, Button, Details, Div, Form, H2, Input, Label, Link, P, Script, Span, Summary, to_xml
from fasthtml.svg import Circle, G, Path, Svg
from fh_saas.utils_auth import handle_login_request, handle_logout
from starlette.responses import RedirectResponse, Response

from gitaway import auth, hostdb, session as ses
from gitaway.icons import icon
from gitaway.layout import clear_site_data, page
from gitaway.signin_context import context

HEAD = (Link(rel="stylesheet", href="/assets/css/signin.css"), Script(src="/assets/js/signin.js", defer=True))

TITLES = {
    "pay": "Sign in to book this trip",
    "fork": "Sign in to fork this trip",
    "invite": "Sign in to invite your crew",
    "save": "Sign in to save this trip",
    "publish": "Sign in to publish your trip",
    "ride": "Sign in to schedule an Uber",
    "join": "Sign in to join your family",
}

PLANE = "M2.5 13.5l7.2-1.6L15 4.6c.5-.7 1.6-.8 2.2-.2.5.5.5 1.3.1 1.9l-4.1 7.1 7.4 2.3-.9 1.6-7.6-.8-3.3 3.8.2 2.3-1.3.7-1.6-3.6-3.9-1.1.4-1.4 2.2-.1z"

# Two skies share their parts and differ in the viewBox, the route and where things sit (percent of the stage): a tall one beside the
# pass on desktop and a short banner above it on phones.
STAGES = {
    "d": dict(box="0 0 880 900", route="M 90 520 C 300 200, 560 160, 640 330", a=(90, 520), b=(640, 330),
              pos=dict(sun="left:63.6%;top:33.3%;width:25%", c1="left:13.6%;top:13.3%;width:20.5%;height:6%", c2="left:47.7%;top:23.3%;width:13.6%;height:4.4%",
                       fr="left:6.8%;top:60.5%", to="left:66.5%;top:41%", s1="left:10.9%;top:71%", s2="left:52%;top:80%", note="left:7.3%;top:7.1%")),
    "m": dict(box="0 0 400 240", route="M 44 180 C 110 36, 230 24, 330 110", a=(44, 180), b=(330, 110),   # one sticker: a banner has no room for two
              pos=dict(sun="left:62%;top:12%;width:26%", c1="left:55%;top:4%;width:22%;height:8%", c2="left:2%;top:46%;width:18%;height:8%",
                       fr="left:4.5%;top:79%", to="left:78%;top:60%", s1="left:20%;top:68%", note="left:5%;top:5%")),
}


def sky(ctx):
    """The decorative sky: bands, sun, clouds, the dotted route with the plane flying it, two stickers and a handwritten note."""
    stages = []
    for key, st in STAGES.items():
        pos, (ax, ay), (bx, by) = st["pos"], st["a"], st["b"]
        route = Svg(
            Path(d=st["route"], cls="si-route", fill="none", stroke_width="3", stroke_dasharray="10 10", stroke_linecap="round"),
            Circle(cx=ax, cy=ay, r=9, cls="si-from"), Circle(cx=bx, cy=by, r=9, cls="si-to", stroke_width="4"),
            G(Path(d=PLANE, transform="translate(-22 -22) rotate(45 22 22) scale(1.833)"), cls="si-plane", style=f"offset-path:path('{st['route']}')"),
            viewBox=st["box"], cls="si-svg", focusable="false",
        )
        stages.append(Div(
            Div(cls="si-sun", style=pos["sun"]), Div(cls="si-cloud", style=pos["c1"]), Div(cls="si-cloud si-cloud2", style=pos["c2"]), route,
            Span(ctx.origin, cls="si-code", style=pos["fr"]), Span(ctx.dest, cls="si-code", style=pos["to"]),
            Span(ctx.s1, cls="si-stick si-stick1", style=pos["s1"]), Span(ctx.s2, cls="si-stick si-stick2", style=pos["s2"]) if "s2" in pos else "",
            P(ctx.note, cls="si-hand", style=pos["note"]),
            cls=f"si-stage si-stage-{key}"))
    return Div(Div(cls="si-band si-band1"), Div(cls="si-band si-band2"), Div(cls="si-band si-band3"), *stages, aria_hidden="true", cls="si-sky")


def _intent(value):
    return value if value in ses.INTENTS else "save"


def cancel_href(next_path):
    """Cancel goes back to the picks: the pay sheet itself would only bounce a signed-out traveler back here."""
    if next_path.startswith("/creators/finish"):
        return "/creators/draft"   # the finish page bounces a signed-out traveler straight back here
    if next_path == "/trip" or next_path.startswith("/trip?"):
        return "/"             # /trip bounces a signed-out traveler straight back here
    return next_path.replace("/plan/pay?", "/plan?", 1) if next_path.startswith("/plan/pay?") else next_path


def dialog(next_path, intent, asked=None, dev=False, google=False, error=""):
    """The boarding pass, and the sky beside it: (card, sky). `asked` is the intent the link carried ("" for a plain Sign in); it is what the
    forms post back.

    `google` shows the Google button (keys are set); `dev` shows the local email form (flag on and request from this machine).
    The pass is filled from the request (gitaway.signin_context): a search, a fork, or the generic pass.
    """
    asked = intent if asked is None else asked
    ctx = context(next_path, intent)
    hidden = (Input(type="hidden", name="next", value=next_path), Input(type="hidden", name="intent", value=asked))
    google_btn = A(Span("G", cls="si-g", aria_hidden="true"), "Continue with Google", icon("plane", 22, 2.2), href=f"/login?next={quote(next_path, safe='')}&intent={asked}",
                   cls="btn btn-primary si-google", id="si-google") if google else ""
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
    card = Div(
        Div(
            Div(Span(icon("fork", 20, 2.4), cls="si-logo"), Span("GitAway", cls="si-brand"), Span("BOARDING PASS", cls="si-tag"), cls="si-top"),
            P(ctx.head, cls="si-dest", id="si-dest"),
            H2(TITLES[intent], id="si-title"),
            P(ctx.sub + (" Your family space is made the first time you sign in." if google or dev else ""), id="si-desc"),
            google_btn, nothing,
            cls="si-body",
        ),
        Div(cls="si-perf", aria_hidden="true"),
        Div(stub, dev_box, Div(A("Cancel", href=cancel_href(next_path), id="si-cancel", cls="btn btn-sm"), cls="si-actions"), cls="si-foot"),
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
    card, sky_ = dialog(next_path, intent, asked, dev=auth.dev_login_allowed(request), google=auth.google_enabled(), error=error)
    out = page("Sign in", Div(sky_, Div(card, cls="si-pass"), cls="si-wrap"), head=HEAD)
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
