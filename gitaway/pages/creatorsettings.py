"""A creator's affiliate marker (F-184): GET and POST /creators/settings.

A person pastes their own Travelpayouts marker (digits only) and the flight links from their published trips pay them (gitaway/affiliate.py). Signed-in only; it is the
person's own setting, not a family's, so every role may save it (gitaway/access.py). Registered before /creators/<handle>, which would otherwise take "settings" for a name.
"""

from urllib.parse import quote

from fasthtml.common import A, Button, Div, Form, H1, Input, Label, Link, P, Section, Span
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import affiliate, community, session as ses
from gitaway.community import HubError
from gitaway.icons import icon
from gitaway.layout import page

PATH = "/creators/settings"
HEAD = (Link(rel="stylesheet", href="/assets/css/report.css"),)


def settings_page(owner, *, value=None, error="", saved=False):
    marker = affiliate.marker_of(owner) if value is None else value
    creator = community.creator_of(owner)
    form = Form(
        Label(Span("Your Travelpayouts marker", cls="rp-lab"),
              Span("Digits only, like 801445. In Travelpayouts it is under Profile. Leave it empty to use GitAway's.", cls="rp-hint", id="st-hint"),
              Input(type="text", name="marker", id="st-marker", value=marker, inputmode="numeric", maxlength="10", autocomplete="off", aria_describedby="st-hint", cls="rp-input")),
        P(error, role="alert", id="st-error", cls="rp-error") if error else "",
        P("Saved.", role="status", id="st-saved", cls="rp-ok") if saved else "",
        Div(Button(icon("check", 20, 2.4), "Save", type="submit", id="st-save", cls="btn btn-primary"), cls="rp-actions"),
        action=PATH, method="post", id="st-form", cls="rp-form card")
    paying = ("Flights booked from your trips carry your marker, so Aviasales pays you. Stays and things to do (Klook) still go through GitAway's account for now, and the page on each trip says so."
              if marker else "Without a marker, bookings from your trips support GitAway, and your trip pages say so.")
    return page("Your marker", Section(Div(H1("Keep your affiliate links"), P(paying, cls="rp-lede", id="st-says"), cls="rp-top"), form,
                                       P(A("Your creator page", href=f"/creators/{creator['handle']}"), " · ", A("Turn a post into a trip", href="/creators/import"), cls="rp-more") if creator
                                       else P(A("Turn a post into a trip", href="/creators/import"), cls="rp-more"), cls="rp ga-wrap"), head=HEAD)


def register(app):
    @app.get(PATH)
    def settings_get(session):
        me = ses.current_traveler(session)
        if not me:
            return RedirectResponse(f"/signin?next={quote(PATH, safe='/')}&intent=publish", status_code=303)
        return settings_page(me.id)

    @app.post(PATH)
    async def settings_post(session, request):
        me = ses.current_traveler(session)
        if not me:
            return RedirectResponse(f"/signin?next={quote(PATH, safe='/')}&intent=publish", status_code=303)
        from gitaway import reports
        if not reports.same_site(request):
            return FtResponse(settings_page(me.id, error="That did not come from GitAway. Open this page again and save."), status_code=403)
        value = str((await request.form()).get("marker") or "")
        try:
            saved = affiliate.set_marker(me.id, value)
        except HubError as e:
            return FtResponse(settings_page(me.id, value=value.strip(), error=str(e)), status_code=422)
        return settings_page(me.id, value=saved, saved=True)
