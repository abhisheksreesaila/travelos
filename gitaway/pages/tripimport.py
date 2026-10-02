"""Import a trip booked elsewhere (F-042). The parsing is gitaway.tripimport, the saving gitaway.importer.

GET  /trips/import            the paste box, with "Download the template"
POST /trips/import            preview: exactly what will be saved, or friendly line-specific errors with the text kept
POST /trips/import/save       save it (the text is read again, never trusted), then open the calendar on that trip
GET  /trips/import/template   docs/trip-template.md as a download
GET  /trip/details            the open imported trip with its confirmation numbers (signed-in family members only)

Signed out goes through sign-in. Once family roles exist (F-043) a viewer cannot import: the check reads the session's role and
lets everyone else through. Confirmation numbers are drawn only on /trip/details and the calendar's booking detail, both behind the
family sign-in; the preview shows what the person pasted back to them.
"""

from pathlib import Path

from fasthtml.common import A, Button, Div, Form, H1, H2, H3, Input, Label, Li, Link, Ol, P, Section, Span, Textarea, Ul
from fasthtml.core import FtResponse
from starlette.datastructures import UploadFile
from starlette.responses import RedirectResponse, Response

from gitaway import access, expedia, importer, session as ses, tripcal as cal, tripimport as ti
from gitaway.icons import icon
from gitaway.layout import page, trip_field

HEAD = (Link(rel="stylesheet", href="/assets/css/tripimport.css"),)
TEMPLATE = Path(__file__).resolve().parent.parent.parent / "docs" / "trip-template.md"
PATH = "/trips/import"
CANNOT = "Only editors and admins of your family can import a trip. Ask the family owner for editor access."


def _signin():
    return RedirectResponse(f"/signin?next={PATH}&intent=save", status_code=303)


def can_import(session=None) -> bool:
    """Editors and admins import; viewers read only. The role comes from gitaway.access (the host database, every request)."""
    return access.can_edit(access.request_role())


def can_delete(session=None) -> bool:
    """Only family admins (the owner included) delete a trip."""
    return access.request_role() in ("admin", "owner")


def _when(at):
    return ti.when_text(at)


# ---- the paste page ------------------------------------------------------------------------------------------------

def paste_page(text="", errors=(), warnings=(), status=200):
    box = Form(
        Label(Span("Your filled-in template", cls="ti-label"),
              Textarea(text, name="text", id="ti-text", rows="18", spellcheck="false", autocomplete="off", maxlength=str(ti.MAX_BYTES),
                       placeholder="trip:\n  title: LA with the kids\n  destination: Los Angeles\n  start: 2026-10-16\n  end: 2026-10-20\n…",
                       aria_describedby="ti-errors" if errors else None, aria_invalid="true" if errors else None, cls="ti-box")),
        Label(Span("Or upload the Expedia itinerary PDF", cls="ti-label"), Input(type="file", name="file", id="ti-file", accept=".pdf,application/pdf", cls="ti-file")),
        Ul(*[Li(e) for e in errors], role="alert", id="ti-errors", cls="ti-errors") if errors else "",
        Div(Button(icon("check", 16, 2.6), "Preview", type="submit", cls="btn btn-ink", id="ti-preview"), cls="ti-actions"),
        action=PATH, method="post", enctype="multipart/form-data", cls="ti-form",
    )
    how = Div(
        H2("How it works", cls="ti-h2"),
        Ol(Li("Download the template and fill it in from your Expedia confirmation."), Li("Paste the whole thing here and press Preview."),
           Li("Check what will be saved, then save. Your calendar opens on the trip."), cls="ti-steps"),
        A(icon("arrow-right", 16, 2.6), "Download the template", href=f"{PATH}/template", cls="btn btn-sm", id="ti-template", download="trip-template.md"),
        A(icon("arrow-right", 16, 2.6), "Rather answer a few questions?", href="/trips/build", cls="btn btn-sm", id="ti-build"),
        P("Flights, the hotel and a car go on your calendar marked “Booked elsewhere”. Confirmation numbers are shown only to your family.", cls="ti-note"),
        cls="ti-card ti-aside",
    )
    out = page("Import a trip", Div(
        Div(H1("Import a trip", cls="ti-title"), P("Booked on Expedia or anywhere else? Paste your details and plan the days here.", cls="ti-lede"), cls="ti-head"),
        Div(Div(box, cls="ti-card ti-main"), how, cls="ti-cols"), cls="ti-wrap"), head=HEAD)
    return FtResponse(out, status_code=status) if status != 200 else out


# ---- the preview ---------------------------------------------------------------------------------------------------

def _row(label, value, **kw):
    return Div(Span(label, cls="ti-k"), Span(value, cls="ti-v", **kw), cls="ti-kv")


def plan_sections(plan):
    """Everything a plan holds, as cards. Used by the preview and by the trip details page (both show the confirmation numbers)."""
    cards = [Div(
        H3("Trip", cls="ti-h3"), _row("Title", plan.title), _row("Destination", plan.destination),
        _row("Dates", cal.range_label(plan.start, plan.end) + f" · {(plan.end - plan.start).days + 1} days"), _row("Booked on", plan.booked_on),
        *([_row("Itinerary number", plan.itinerary)] if plan.itinerary else []), cls="ti-sec", id="ti-trip")]
    cards.append(Div(H3(f"Travelers · {plan.party_text}", cls="ti-h3"),
                     Ul(*[Li(Span(t.name, cls="ti-chip-name"), Span(f"age {t.age}" if t.age is not None else (t.email or "adult"), cls="ti-chip-sub"), cls="ti-chip") for t in plan.travelers], cls="ti-chips"),
                     cls="ti-sec", id="ti-travelers"))
    if plan.legs:
        arrive, depart = plan.arrive_leg, plan.depart_leg
        rows = []
        for leg in plan.legs:
            note = " · arrival at your destination" if leg is arrive else " · flight home" if leg is depart else ""
            rows.append(Div(Span(icon("plane", 16, 2.2), Span(f"{leg.name} · {leg.origin} → {leg.dest}", cls="ti-strong"), cls="ti-line"),
                            Span(f"{_when(leg.depart)} → {_when(leg.arrive)}{note}", cls="ti-sub"),
                            Span(f"Confirmation {leg.confirmation}" + (f" · seats {leg.seats}" if leg.seats else ""), cls="ti-sub ti-conf") if leg.confirmation or leg.seats else "",
                            cls="ti-item"))
        cards.append(Div(H3("Flights", cls="ti-h3"), *rows, cls="ti-sec", id="ti-flights"))
    if plan.hotels:
        items = [Div(Span(icon("bed", 16, 2.2), Span(h.name, cls="ti-strong"), cls="ti-line"), Span(h.address, cls="ti-sub"),
                     Span(f"Check in {_when(h.check_in)} · check out {_when(h.check_out)}", cls="ti-sub"),
                     Span(" · ".join(x for x in (h.room, f"{h.rooms} rooms" if h.rooms != 1 else "", h.phone) if x), cls="ti-sub") if (h.room or h.rooms != 1 or h.phone) else "",
                     Span(f"Confirmation {h.confirmation}", cls="ti-sub ti-conf") if h.confirmation else "", cls="ti-item") for h in plan.hotels]
        cards.append(Div(H3("Hotels" if len(items) > 1 else "Hotel", cls="ti-h3"), *items, cls="ti-sec", id="ti-hotel"))
    if plan.rental:
        c = plan.rental
        cards.append(Div(H3("Car", cls="ti-h3"),
                         Div(Span(icon("car", 16, 2.2), Span(f"{c.company}" + (f" · {c.car}" if c.car else ""), cls="ti-strong"), cls="ti-line"),
                             Span(f"Pick up {c.pickup_place} · {_when(c.pickup)}", cls="ti-sub"), Span(f"Drop off {c.dropoff_place} · {_when(c.dropoff)}", cls="ti-sub"),
                             Span(f"Confirmation {c.confirmation}", cls="ti-sub ti-conf") if c.confirmation else "", cls="ti-item"), cls="ti-sec", id="ti-car"))
    if plan.notes:
        cards.append(Div(H3("Notes", cls="ti-h3"), P(plan.notes, cls="ti-notes"), cls="ti-sec", id="ti-notes"))
    return cards


def _consequences(plan):
    """The sentences that say what the calendar and the rides will do with this trip."""
    n = len(ti.block_specs(plan))
    out = [f"{n} booked item{'s' if n != 1 else ''} will go on your calendar, marked “Booked elsewhere · {plan.booked_on}”."]
    arrive = plan.arrive_leg
    if arrive:
        out.append(f"You land at {_when(arrive.arrive)}: plans before then are not allowed" + (f", and none within {cal.AIRPORT_BUFFER // 60} hours of your flight home." if plan.depart_leg else "."))
    if plan.rental:
        out.append("You have a car, so there are no Uber rides to schedule.")
    elif arrive and arrive.dest in ("LAX", "BUR") and plan.depart_leg:
        out.append(f"No car: you can schedule simulated Ubers from {arrive.dest} to your hotel and back." + (" Your group needs an XL." if len(plan.travelers) >= 5 else ""))
    else:
        out.append("Rides are only available for trips that land at LAX or BUR with a flight home.")
    return out


def preview_page(text, parsed, match=None, moves=0, *, fields=None, save_action=None, edit=None, lead="", expedia_read=False):
    """The preview. The trip builder (F-055) draws this same page with its own hidden `fields` (its draft instead of the pasted `text`),
    its own `save_action`, and `edit` = (action, hidden fields, button label) for the way back; `lead` goes above the heading."""
    plan = parsed.plan
    hidden = fields if fields is not None else [Input(type="hidden", name="text", value=text)]
    save_to = save_action or f"{PATH}/save"
    edit_to, edit_fields, edit_label = edit or (PATH, [Input(type="hidden", name="text", value=text)], "Change something")
    token = importer.new_token()
    out = page("Preview your trip", Div(
        lead,
        Div(H1("Check your trip", cls="ti-title"), P("This is exactly what will be saved. Nothing is saved until you press Save.", cls="ti-lede"), cls="ti-head"),
        Div(P("Read from an Expedia itinerary. Expedia names only who booked, so check the travelers and rename the placeholders (like “Adult 3”), then check each line.", cls="ti-note", id="ti-expedia"), cls="ti-warns") if expedia_read else "",
        Div(*[Div(w, cls="ti-warn", role="status") for w in parsed.warnings], cls="ti-warns") if parsed.warnings else "",
        Div(Div(*plan_sections(plan), cls="ti-main ti-stack", id="ti-preview-body"),
            Div(H2("What happens next", cls="ti-h2"), Ul(*[Li(s) for s in _consequences(plan)], cls="ti-next"),
                *([Div(P(f"You already imported “{match[1]}”. Is this a correction?", cls="ti-note"),
                       Form(*hidden, Input(type="hidden", name="replace", value=match[0]),
                            Button(icon("check", 16, 2.6), "Replace the existing trip", type="submit", cls="btn btn-ink ti-save", id="ti-replace"),
                            P("Its calendar plans, notes and rides stay." + (f" {moves} scheduled Uber ride{'s' if moves != 1 else ''} will move to the new flight times and hotel." if moves else ""), cls="ti-note", **({"id": "ti-moves"} if moves else {})), action=save_to, method="post"), cls="ti-match")] if match else []),
                Form(*hidden, Input(type="hidden", name="token", value=token),
                     Button(icon("check", 16, 2.6), "Save as a new trip" if match else "Save this trip", type="submit", cls="btn btn-sm ti-save" if match else "btn btn-ink ti-save", id="ti-save"),
                     action=save_to, method="post"),
                Form(*edit_fields, Button(edit_label, type="submit", cls="btn btn-sm", id="ti-edit"), action=edit_to, method="post", cls="ti-edit"),
                cls="ti-card ti-aside"), cls="ti-cols"),
        cls="ti-wrap"), head=HEAD)
    return out


# ---- the trip details page -----------------------------------------------------------------------------------------

def details_page(plan, trip_id="", admin=False):
    return page(f"{plan.title}: details", Div(
        Div(H1(plan.title, cls="ti-title"), P(f"Booked elsewhere · {plan.booked_on}. Confirmation numbers are shown only to your family.", cls="ti-lede"),
            Div(A(icon("arrow-right", 16, 2.6), "Open the calendar", href="/calendar", cls="btn btn-sm", id="ti-cal"),
                A("Correct it", href=PATH, cls="ti-link", id="ti-correct"),
                A("Delete this trip", href=f"/trip/delete?trip={trip_id}", cls="ti-link ti-danger", id="ti-delete") if admin and trip_id else "", cls="ti-actions"), cls="ti-head"),
        Div(*plan_sections(plan), cls="ti-stack ti-wide", id="ti-details"), cls="ti-wrap"), head=HEAD)


def _sorry(title, message, *links, status=200):
    out = page(title, Div(Div(H1(title, cls="ti-title"), P(message, cls="ti-lede"), Div(*links, cls="ti-actions"), cls="ti-head"), cls="ti-wrap ti-narrow"), head=HEAD)
    return FtResponse(out, status_code=status) if status != 200 else out


# ---- routes --------------------------------------------------------------------------------------------------------

def register(app):
    from fasthtml.common import to_xml
    from starlette.middleware.base import BaseHTTPMiddleware

    async def too_big(request, call_next):
        """Refuse an oversized upload before its body is read or parsed (the form is parsed before any route runs)."""
        if request.method == "POST" and request.url.path == PATH:
            try:
                size = int(request.headers.get("content-length", "0"))
            except ValueError:
                size = 0
            if size > expedia.MAX_PDF_BYTES + 100_000:
                msg = f"That upload is too large (at most {expedia.MAX_PDF_BYTES // 1_000_000} MB). Paste the itinerary text instead."
                return Response(to_xml(paste_page("", [msg])), status_code=413, media_type="text/html")
        return await call_next(request)

    app.add_middleware(BaseHTTPMiddleware, dispatch=too_big)

    @app.get(PATH)
    def import_form(session):
        if not ses.current_traveler(session):
            return _signin()
        if not can_import(session):
            return _sorry("Import a trip", CANNOT, A("Back to your trips", href="/start", cls="btn btn-ink"), status=403)
        return paste_page()

    @app.post(PATH)
    async def import_preview(session, text: str = "", file: UploadFile = None):
        if not ses.current_traveler(session):
            return _signin()
        if not can_import(session):
            return _sorry("Import a trip", CANNOT, A("Back to your trips", href="/start", cls="btn btn-ink"), status=403)
        if file is not None and getattr(file, "filename", ""):  # an uploaded PDF wins over the paste box
            data = await file.read(expedia.MAX_PDF_BYTES + 1)
            try:
                text = expedia.pdf_text(data)
            except expedia.PdfProblem as e:
                return paste_page(text, [str(e)], status=422)
        read, extra = False, ()
        if expedia.looks_like_expedia(text):
            converted = expedia.convert(text)
            if not converted.yaml:
                return paste_page(text, [*converted.warnings, "We couldn't read any booking in that itinerary."], status=422)
            text, extra, read = converted.yaml, converted.warnings, True
        try:
            parsed = ti.parse(text)
        except ti.ImportProblem as e:
            return paste_page(text, e.errors, (*extra, *e.warnings), status=422)
        parsed = ti.Parsed(parsed.plan, (*extra, *parsed.warnings))
        match = importer.find_match(session, parsed.plan)
        return preview_page(text, parsed, match, importer.rides_to_retime(session, match[0], parsed.plan) if match else 0, expedia_read=read)

    @app.post(f"{PATH}/save")
    def import_save(session, text: str = "", token: str = "", replace: str = ""):
        if not ses.current_traveler(session):
            return _signin()
        if not can_import(session):
            return _sorry("Import a trip", CANNOT, A("Back to your trips", href="/start", cls="btn btn-ink"), status=403)
        try:
            parsed = ti.parse(text)  # read again: a posted form is never trusted
        except ti.ImportProblem as e:
            return paste_page(text, e.errors, e.warnings, status=422)
        try:
            importer.save(session, parsed.plan, token or None, replace or None)
        except importer.SaveError as e:
            return paste_page(text, [str(e)], status=409)
        return RedirectResponse("/calendar", status_code=303)

    @app.get(f"{PATH}/template")
    def template():
        return Response(TEMPLATE.read_text(), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="trip-template.md"'})

    @app.get("/trip/details")
    def details(session):
        if not ses.current_traveler(session):
            return RedirectResponse("/signin?next=%2Ftrip%2Fdetails&intent=save", status_code=303)
        plan = importer.plan_of(session)
        if plan is None:
            return _sorry("No imported trip is open", "Details with confirmation numbers are kept for trips you import. Open one from your calendar, or import a trip.",
                          A("Import a trip", href=PATH, cls="btn btn-ink"), A("Plan a trip", href="/start", cls="btn btn-sm"), A("Browse community trips", href="/community", cls="btn btn-sm"), A("Back to the calendar", href="/calendar", cls="btn btn-sm"), status=404)
        return details_page(plan, ses.open_trip_id(), can_delete(session))

    @app.get("/trip/delete")
    def delete_ask(session, trip: str = ""):
        if not ses.current_traveler(session):
            return RedirectResponse("/signin?next=%2Ftrip%2Fdetails&intent=save", status_code=303)
        if not can_delete(session):
            return _sorry("Delete a trip", "Only the admins of your family can delete a trip.", A("Back to the calendar", href="/calendar", cls="btn btn-ink"), status=403)
        plan = importer.plan_of(session, trip or None)
        if plan is None:
            return _sorry("Nothing to delete", "That trip is not there, or it was not imported (only imported trips can be deleted here).", A("Back to the calendar", href="/calendar", cls="btn btn-ink"), status=404)
        return _sorry(f"Delete “{plan.title}”?", "This removes the trip from your family: its booked items, calendar plans, notes and Uber rides. If you or anyone in your family shared it, the shared page comes down too. It cannot be undone.",
                      Form(Input(type="hidden", name="trip", value=trip), Button("Delete this trip", type="submit", cls="btn btn-ink", id="ti-confirm-delete"),
                           action="/trip/delete", method="post"), A("Keep it", href="/calendar", cls="ti-link"))

    @app.post("/trip/delete")
    def delete_do(session, trip: str = ""):
        if not ses.current_traveler(session):
            return RedirectResponse("/signin?next=%2Ftrip%2Fdetails&intent=save", status_code=303)
        if not can_delete(session):
            return _sorry("Delete a trip", "Only the admins of your family can delete a trip.", A("Back to the calendar", href="/calendar", cls="btn btn-ink"), status=403)
        if not importer.delete(session, trip):
            return _sorry("Nothing to delete", "That trip is not there, or it was not imported.", A("Back to the calendar", href="/calendar", cls="btn btn-ink"), status=404)
        return RedirectResponse("/calendar", status_code=303)
