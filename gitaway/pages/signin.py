"""Demo sign-in (F-017): /signin?next=<local path>&intent=<save|pay|invite|fork>.

Everything is browsable signed out; save, pay, invite and fork land here, then continue to `next`.
Choosing a traveler is a POST that stores them in the session (see gitaway.session).
"""

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
}


def _intent(value):
    return value if value in ses.INTENTS else "save"


def _pick(t):
    return Button(
        avatar(t, "si-avatar"),
        Span(Span(f"Continue as {t.name}", cls="si-name"), Span(t.blurb, cls="si-blurb"), cls="si-who"),
        type="submit", name="traveler", value=t.id, cls="si-pick",
    )


def dialog(next_path, intent):
    return Div(
        Form(
            Span("One tiny step", cls="sticker si-sticker"),
            H2(TITLES[intent], id="si-title"),
            P("We'll keep your picks exactly as they are. This is a demo, so pick a traveler and go.", id="si-desc"),
            Div(*[_pick(t) for t in ses.TRAVELERS.values()], cls="si-list"),
            Input(type="hidden", name="next", value=next_path),
            Input(type="hidden", name="intent", value=intent),
            Div(A("Cancel", href=next_path, id="si-cancel", cls="btn btn-sm"), cls="si-actions"),
            P("Real sign-in with Google comes later. Nothing here leaves your browser.", cls="si-note"),
            action="/signin", method="post",
        ),
        role="dialog", aria_modal="true", aria_labelledby="si-title", aria_describedby="si-desc", id="si-dialog", cls="si-card",
    )


def register(app):
    @app.get("/signin")
    def signin_page(session, next: str = "/", intent: str = "save"):
        next_path, intent = ses.safe_next(next), _intent(intent)
        if ses.current_traveler(session):
            return RedirectResponse(next_path, status_code=303)
        return page("Sign in", Div(dialog(next_path, intent), cls="si-backdrop"), head=HEAD)

    @app.post("/signin")
    def signin_submit(session, traveler: str = "", next: str = "/", intent: str = "save"):
        if not ses.sign_in(session, traveler):
            return Response("Unknown demo traveler", status_code=400)
        next_path = ses.safe_next(next)
        if _intent(intent) == "fork":
            ses.add_fork(session, next_path)
        return RedirectResponse(next_path, status_code=303)

    @app.post("/signout")
    def signout(session):
        ses.sign_out(session)
        return RedirectResponse("/", status_code=303)
