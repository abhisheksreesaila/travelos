"""Report a public trip or creator page (F-185). The rules are gitaway/reports.py; this module is the screens.

GET  /report?trip=<slug>  or  /report?creator=<handle>    the form: a reason, an optional note, an optional email address
POST /report                                              store it (kind, target, reason, note, email, and the honeypot `website`, which a person never sees)

Open to everyone, signed in or not, and to every role (it changes no family plan: gitaway/access.py lists it). A report hides nothing.
"""

from fasthtml.common import A, Button, Div, Form, H1, Input, Label, Link, Option, P, Section, Select, Span, Textarea
from fasthtml.core import FtResponse

from gitaway import community, reports, session as ses
from gitaway.icons import icon
from gitaway.layout import page

HEAD = (Link(rel="stylesheet", href="/assets/css/report.css"),)
THANKS = "Thank you. The person who runs GitAway will read this."


def _target(trip="", creator=""):
    """(kind, target, what to call it) of what is being reported, or None when it is not on GitAway (a draft, a sample, a taken-down page, nobody)."""
    if trip and community.is_real(trip):
        return "trip", trip, community.get(trip)["title"]
    named = next((c for c in community.real_creators() if c["handle"] == creator), None) if creator else None
    return ("creator", creator, named["name"]) if named else None


def _gone():
    return FtResponse(page("Not found", Section(Div(H1("Nothing here"), P("That page is not on GitAway any more."), A("Back home", href="/", cls="btn btn-primary"), cls="ga-wrap"), cls="ga-soon ga-wrap")), status_code=404)


def form_page(kind, target, name, *, reason="", note="", email="", error=""):
    what = "this trip" if kind == "trip" else "this creator"
    form = Form(
        Input(type="hidden", name="kind", value=kind), Input(type="hidden", name="target", value=target),
        Label(Span("What is wrong?", cls="rp-lab"),
              Select(Option("Pick the best fit", value="", selected=not reason, disabled=True), *[Option(text, value=k, selected=k == reason) for k, text in reports.REASONS.items()],
                     name="reason", id="rp-reason", required=True, cls="rp-input")),
        Label(Span("Tell us more", cls="rp-lab"), Span("Optional. Say where, or what the original is.", cls="rp-hint"),
              Textarea(note, name="note", id="rp-note", rows="4", maxlength=str(reports.NOTE_MAX), cls="rp-input rp-text")),
        Label(Span("Your email", cls="rp-lab"), Span("Optional. Only so we can write back. It is never shown to anyone.", cls="rp-hint"),
              Input(type="email", name="email", id="rp-email", value=email, autocomplete="email", maxlength="120", cls="rp-input")),
        Div(Label("Leave this empty", Input(type="text", name="website", tabindex="-1", autocomplete="off")), cls="rp-bee", aria_hidden="true"),   # the honeypot: only a program fills it in
        P(error, role="alert", id="rp-error", cls="rp-error") if error else "",
        Div(Button(icon("flag", 20, 2.4), "Send report", type="submit", id="rp-send", cls="btn btn-primary"), A("Cancel", href=f"/trips/{target}" if kind == "trip" else f"/creators/{target}", cls="btn", id="rp-cancel"), cls="rp-actions"),
        action="/report", method="post", id="rp-form", cls="rp-form card")
    return page("Report", Section(Div(H1(f"Report {what}"), P(name, cls="rp-what", id="rp-what"),
                                      P("A report does not hide anything by itself. The person who runs GitAway reads each one and can take a page down.", cls="rp-lede"), cls="rp-top"),
                                  form, cls="rp ga-wrap"), head=HEAD)


def thanks_page():
    return page("Report sent", Section(Div(Span(icon("check", 28, 2.4), cls="rp-badge", aria_hidden="true"), H1("Report sent"), P(THANKS, id="rp-thanks", cls="rp-lede"),
                                           A("Back to GitAway", href="/community", cls="btn btn-primary"), cls="rp-top"), cls="rp ga-wrap"), head=HEAD)


def register(app):
    @app.get("/report")
    def report_get(trip: str = "", creator: str = ""):
        found = _target(trip, creator)
        return form_page(*found) if found else _gone()

    @app.post("/report")
    async def report_post(request, session):
        if not reports.same_site(request):
            return FtResponse(page("Not allowed", Section(Div(H1("That did not come from GitAway"), P("Open the report form from the trip's page and send it again."), cls="ga-wrap"), cls="ga-soon ga-wrap")), status_code=403)
        f = await request.form()
        if str(f.get("website") or "").strip():   # the honeypot was filled in: say thanks, keep nothing
            return thanks_page()
        kind, target = str(f.get("kind") or ""), str(f.get("target") or "")
        me = ses.current_traveler(session)
        try:
            reports.add(kind, target, str(f.get("reason") or ""), f.get("note"), f.get("email"), me.id if me else "", reports.client_ip(request))
        except reports.ReportError as e:
            found = _target(target if kind == "trip" else "", target if kind == "creator" else "")
            if not found:
                return _gone()
            body = form_page(*found, reason=str(f.get("reason") or ""), note=str(f.get("note") or ""), email=str(f.get("email") or ""), error=str(e))
            return FtResponse(body, status_code=e.status)
        return thanks_page()
