"""Demo sign-in (F-017): /signin?next=<local path>&intent=<save|pay|invite|fork>.

Everything is browsable signed out; save, pay, invite and fork land here, then continue to `next`. Without a `next`
the traveler lands on /start, "Where to?" (F-035).
Choosing a traveler is a POST that stores them in the session (see gitaway.session).
"""

from urllib.parse import quote

from fasthtml.common import A, Button, Div, Form, H2, Input, Link, P, Script, Span
from starlette.responses import RedirectResponse, Response

from gitaway import session as ses
from gitaway.layout import avatar, page

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


def _pick(t):
    return Button(
        avatar(t, "si-avatar"),
        Span(Span(f"Continue as {t.name}", cls="si-name"), Span(t.blurb, cls="si-blurb"), cls="si-who"),
        type="submit", name="traveler", value=t.id, cls="si-pick",
    )


def cancel_href(next_path):
    """Cancel goes back to the picks: the pay sheet itself would only bounce a signed-out traveler back here."""
    if next_path.startswith("/creators/finish"):
        return "/creators/draft"   # the finish page bounces a signed-out traveler straight back here
    return next_path.replace("/plan/pay?", "/plan?", 1) if next_path.startswith("/plan/pay?") else next_path


def dialog(next_path, intent):
    return Div(
        Form(
            Span("One tiny step", cls="sticker si-sticker"),
            H2(TITLES[intent], id="si-title"),
            P("We'll keep your picks exactly as they are. This is a demo, so pick a traveler and go.", id="si-desc"),
            Div(*[_pick(t) for t in ses.TRAVELERS.values()], cls="si-list"),
            Input(type="hidden", name="next", value=next_path),
            Input(type="hidden", name="intent", value=intent),
            Div(A("Cancel", href=cancel_href(next_path), id="si-cancel", cls="btn btn-sm"), cls="si-actions"),
            P("Real sign-in with Google comes later. Nothing here leaves your browser.", cls="si-note"),
            action="/signin", method="post",
        ),
        role="dialog", aria_modal="true", aria_labelledby="si-title", aria_describedby="si-desc", id="si-dialog", cls="si-card",
    )


def register(app):
    @app.get("/signin")
    def signin_page(session, next: str = "/start", intent: str = "save"):
        next_path, intent = ses.safe_next(next), _intent(intent)
        if ses.current_traveler(session):
            if intent == "fork":
                ses.add_fork(session, next_path)
            return RedirectResponse(next_path, status_code=303)
        return page("Sign in", Div(dialog(next_path, intent), cls="si-backdrop"), head=HEAD)

    @app.post("/signin")
    def signin_submit(session, traveler: str = "", next: str = "/start", intent: str = "save"):
        if not ses.sign_in(session, traveler):
            return Response("Unknown demo traveler", status_code=400)
        next_path = ses.safe_next(next)
        if _intent(intent) == "fork":
            ses.add_fork(session, next_path)
        return RedirectResponse(next_path, status_code=303)

    @app.post("/fork")
    def fork(session, next: str = "/"):
        """Fork the trip at `next` (/trips/<slug>) for the signed-in traveler, then go back. Signed out: sign in first."""
        next_path = ses.safe_next(next)
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={quote(next_path, safe='/')}&intent=fork", status_code=303)
        ses.add_fork(session, next_path)
        return RedirectResponse(next_path, status_code=303)

    @app.post("/signout")
    def signout(session):
        ses.sign_out(session)
        return RedirectResponse("/", status_code=303)
