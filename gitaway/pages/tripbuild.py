"""The guided trip builder (F-055): a few friendly questions, one step at a time, that make the same trip as the template.

GET  /trips/build          step 1
POST /trips/build          a step: the form carries the `draft` (every answer so far, in a hidden field), the `step` and the button pressed (`nav`:
                           next, back, add, remove-N). A good "next" draws the next step; a bad one the same step again (422) with a message on each field.
                           After the last question it draws the importer's own preview (gitaway.pages.tripimport.preview_page).
POST /trips/build/save     the draft is built into a Plan again and saved by gitaway.importer.save, exactly as the template is

The model is gitaway.tripbuild. Signed out goes through sign-in; a viewer cannot build (the same rule and wording as importing).
"""

from fasthtml.common import A, Button, Datalist, Div, Fieldset, Form, H1, H2, Input, Label, Legend, Li, Link, Ol, Option, P, Script, Select, Span, Textarea, Ul
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import catalog, importer, pickers, session as ses, tripbuild as tb, tripimport as ti
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import tripimport as tip

HEAD = (*pickers.HEAD, Link(rel="stylesheet", href="/assets/css/tripimport.css"), Link(rel="stylesheet", href="/assets/css/tripbuild.css"),
        Script(src="/assets/js/tripbuild.js", defer=True))
PATH = "/trips/build"
LABELS = ("Where", "Dates", "Who", "Flights", "Hotel", "Car", "Notes")
TITLES = ("Where are you going?", "When are you going?", "Who’s going?", "How are you getting there?", "Where are you staying?", "Do you have a rental car?", "Anything else to remember?")
LEDES = ("Give the trip a name your family will recognise.", "Pick the day you leave and the day you come home.",
         "Everyone on the booking. Kids’ ages help us plan the right rides and rooms.",
         "Add each flight, one leg at a time: a connection is two legs. Times are local to the airport.", "Add each place you are staying. Two hotels are fine.",
         "Only if you booked one. Skip it if you are using rides.", "Anything we should keep with the trip. Confirmation numbers are shown only to your family.")


# ---- small form pieces ----------------------------------------------------------------------------------------------

class Ctx:
    """What a step needs to draw itself: the draft and the errors by field name."""

    def __init__(self, draft, errors=None):
        self.draft, self.errors = draft, errors or {}

    def err(self, name):
        return self.errors.get(name, "")

    def attrs(self, name):
        return {"aria_invalid": "true", "aria_describedby": f"tb-err-{name}"} if name in self.errors else {}


def field(c, name, label, control, hint="", extra_cls=""):
    """A labelled field: the label wraps the control, the hint and the error are read out with it."""
    return Label(Span(label, cls="tb-label"), control, Span(hint, cls="tb-hint") if hint else "",
                 Span(c.err(name), cls="tb-error", id=f"tb-err-{name}") if c.err(name) else "", cls=f"tb-field {extra_cls}".strip(), data_field=name)


def text(c, name, label, value, hint="", **attrs):
    attrs.setdefault("type", "text")
    return field(c, name, label, Input(name=name, id=f"tb-{name}", value=value or "", autocomplete=attrs.pop("autocomplete", "off"), **attrs, **c.attrs(name)), hint)


def when(c, name, label, value, kind, **attrs):
    return field(c, name, label, Input(type=kind, name=name, id=f"tb-{name}", value=value or "", data_ga_label=label, **attrs, **c.attrs(name)))


def airport(c, name, label, value):
    return field(c, name, label, Input(type="text", name=name, id=f"tb-{name}", value=value or "", list="tb-airports", maxlength="3", autocapitalize="characters",
                                      autocomplete="off", spellcheck="false", **c.attrs(name)), "Three letters, like SFO")


def choice(c, name, current, options, legend):
    """A yes/no question as two big radio buttons; `data-toggle` lets the script hide the rows that do not apply."""
    return Fieldset(Legend(legend, cls="tb-legend"),
                    Div(*[Label(Input(type="radio", name=name, value=v, id=f"tb-{name}-{v}", checked=(current == v), data_toggle=name), Span(text_), cls="tb-choice") for v, text_ in options], cls="tb-choices"),
                    Span(c.err(name), cls="tb-error", id=f"tb-err-{name}", role="alert") if c.err(name) else "", cls="tb-fieldset", id=f"tb-{name}",
                    **({"aria_invalid": "true", "aria_describedby": f"tb-err-{name}"} if name in c.errors else {}))


def row_buttons(label, i):
    return Button(icon("x", 16, 2.6), "Remove", type="submit", name="nav", value=f"remove-{i}", cls="btn btn-sm tb-remove", formnovalidate=True, aria_label=f"Remove {label}")


# ---- the steps ------------------------------------------------------------------------------------------------------

def step_where(c):
    d = c.draft
    return [text(c, "title", "Trip name", d.get("title"), "What your family will see, like “LA with the kids”", maxlength="60", autocomplete="off"),
            text(c, "destination", "Where to?", d.get("destination"), "A city or a region", maxlength="60")]


def step_dates(c):
    d = c.draft
    return [Div(when(c, "start", "Leaving", d.get("start"), "date", data_ga_range="trip"),
                when(c, "end", "Coming home", d.get("end"), "date", data_ga_range="trip", data_ga_end=""), cls="tb-pair")]


def _ages(n):
    return "Under 1" if n == 0 else str(n)


def step_who(c):
    d = c.draft
    adults, kids = tb.adults_of(d), d.get("kids", [])
    ages = [Div(field(c, f"k{i}", f"Kid {i} age", Select(Option("Pick age", value=""), *[Option(_ages(a), value=str(a), selected=(kids[i - 1] == str(a) if i <= len(kids) else False)) for a in range(catalog.MAX_KID_AGE + 1)],
                                                     name=f"k{i}", id=f"tb-k{i}", data_ga="chips", data_ga_label=f"Kid {i} age", **c.attrs(f"k{i}"))),
                cls="tb-row", data_row=f"k{i}") for i in range(1, tb.MAX_KIDS + 1)]
    names, emails = d.get("names", []), d.get("emails", [])
    people = [Div(text(c, f"an{i}", f"Adult {i} name", names[i - 1] if i <= len(names) else "", maxlength="40", autocomplete="given-name" if i == 1 else "off"),
                  field(c, f"ae{i}", f"Adult {i} email (optional)", Input(type="email", name=f"ae{i}", id=f"tb-ae{i}", value=emails[i - 1] if i <= len(emails) else "", maxlength="80", autocomplete="off", **c.attrs(f"ae{i}")),
                        "To invite them to the trip later" if i == 1 else ""),
                  cls="tb-person", data_row=f"a{i}", **({"hidden": True} if i > adults else {})) for i in range(1, tb.MAX_ADULTS + 1)]
    return [Div(field(c, "adults", "Adults", Select(*[Option(str(n), value=str(n), selected=(n == adults)) for n in range(1, tb.MAX_ADULTS + 1)], name="adults", id="tb-adults", data_ga="stepper", data_ga_label="Adults", data_ga_hint="18 and over", **c.attrs("adults"))),
                field(c, "nkids", "Kids", Select(*[Option(str(n), value=str(n), selected=(n == len(kids))) for n in range(tb.MAX_KIDS + 1)], name="nkids", id="tb-nkids", data_ga="stepper", data_ga_label="Kids", data_ga_hint="under 18", **c.attrs("nkids"))), cls="tb-pair"),
            Div(Span("Kids’ ages", cls="tb-label"), *ages, cls="tb-ages", id="tb-ages"),
            Div(H2("Who are the adults?", cls="tb-h2"), P("Names are optional. An email lets you invite them to edit or view the trip later.", cls="tb-hint"), *people, cls="tb-people")]


def _leg(c, i, leg, many):
    n, p = i + 1, f"leg{i}_"
    return Div(Div(H2(f"Flight {n}", cls="tb-h2"), row_buttons(f"flight {n}", i) if many else "", cls="tb-rowhead"),
               Div(text(c, p + "airline", "Airline", leg["airline"], maxlength="40"), text(c, p + "number", "Flight number", leg["number"], "Like AS 1234", maxlength="12"), cls="tb-pair"),
               Div(airport(c, p + "from", "From", leg["from"]), airport(c, p + "to", "To", leg["to"]), cls="tb-pair"),
               Div(when(c, p + "depart_date", "Leaves (date)", leg["depart_date"], "date"), when(c, p + "depart_time", "Leaves (time)", leg["depart_time"], "time"), cls="tb-pair"),
               Div(when(c, p + "arrive_date", "Lands (date)", leg["arrive_date"], "date"), when(c, p + "arrive_time", "Lands (time)", leg["arrive_time"], "time"), cls="tb-pair"),
               Div(text(c, p + "confirmation", "Confirmation (optional)", leg["confirmation"], "Shown only to your family", maxlength="20"), text(c, p + "seats", "Seats (optional)", leg["seats"], maxlength="60"), cls="tb-pair"),
               cls="tb-card tb-item", data_row=f"leg{i}")


def step_flights(c):
    legs = c.draft.get("legs", [])
    return [choice(c, "flying", c.draft.get("flying", "yes"), (("yes", "Yes, add flights"), ("no", "I’m not flying")), "Are you flying?"),
            Div(Datalist(*[Option(a) for a in tb.AIRPORTS], id="tb-airports"), *[_leg(c, i, leg, len(legs) > 1) for i, leg in enumerate(legs)],
                Button(icon("plus", 16, 2.6), "Add another flight", type="submit", name="nav", value="add", cls="btn btn-sm tb-add", formnovalidate=True) if len(legs) < ti.MAX_LEGS else "",
                P("Common airports: " + ", ".join(tb.AIRPORTS) + ".", cls="tb-hint"), cls="tb-rows", data_when="flying")]


def _hotel(c, i, h, many):
    p = f"hotel{i}_"
    return Div(Div(H2(f"Hotel {i + 1}" if many else "Your hotel", cls="tb-h2"), row_buttons(f"hotel {i + 1}", i) if many else "", cls="tb-rowhead"),
               text(c, p + "name", "Hotel name", h["name"], maxlength="80"), text(c, p + "address", "Address", h["address"], maxlength="120", autocomplete="street-address"),
               Div(when(c, p + "check_in_date", "Check in (date)", h["check_in_date"], "date"), when(c, p + "check_in_time", "Check in (time)", h["check_in_time"], "time"), cls="tb-pair"),
               Div(when(c, p + "check_out_date", "Check out (date)", h["check_out_date"], "date"), when(c, p + "check_out_time", "Check out (time)", h["check_out_time"], "time"), cls="tb-pair"),
               Div(text(c, p + "confirmation", "Confirmation (optional)", h["confirmation"], "Shown only to your family", maxlength="30"), text(c, p + "room", "Room (optional)", h["room"], "Like 2 Queen Beds", maxlength="80"), cls="tb-pair"),
               text(c, p + "phone", "Hotel phone (optional)", h["phone"], maxlength="30", type="tel"),
               cls="tb-card tb-item", data_row=f"hotel{i}")


def step_hotel(c):
    hotels = c.draft.get("hotels", [])
    return [choice(c, "stay", c.draft.get("stay", "yes"), (("yes", "Yes, add a hotel"), ("no", "No hotel")), "Do you have a hotel?"),
            Div(*[_hotel(c, i, h, len(hotels) > 1) for i, h in enumerate(hotels)],
                Button(icon("plus", 16, 2.6), "Add another hotel", type="submit", name="nav", value="add", cls="btn btn-sm tb-add", formnovalidate=True) if len(hotels) < ti.MAX_HOTELS else "",
                cls="tb-rows", data_when="stay")]


def step_car(c):
    car = c.draft.get("car") or tb.blank(tb.CAR)
    return [choice(c, "rent", c.draft.get("rent", "no"), (("yes", "Yes, I have a rental car"), ("no", "No car")), "Did you book a rental car?"),
            Div(Datalist(*[Option(a) for a in tb.AIRPORTS], id="tb-airports"),
                text(c, "car_company", "Rental company", car["company"], maxlength="40"),
                Div(text(c, "car_pickup_place", "Pick up at", car["pickup_place"], "An airport or an address", maxlength="80", list="tb-airports"), text(c, "car_dropoff_place", "Drop off at", car["dropoff_place"], maxlength="80", list="tb-airports"), cls="tb-pair"),
                Div(when(c, "car_pickup_date", "Pick up (date)", car["pickup_date"], "date"), when(c, "car_pickup_time", "Pick up (time)", car["pickup_time"], "time"), cls="tb-pair"),
                Div(when(c, "car_dropoff_date", "Drop off (date)", car["dropoff_date"], "date"), when(c, "car_dropoff_time", "Drop off (time)", car["dropoff_time"], "time"), cls="tb-pair"),
                Div(text(c, "car_confirmation", "Confirmation (optional)", car["confirmation"], "Shown only to your family", maxlength="30"), text(c, "car_car", "Car (optional)", car["car"], "Like Midsize SUV", maxlength="40"), cls="tb-pair"),
                cls="tb-card tb-item", data_when="rent")]


def step_notes(c):
    d = c.draft
    return [field(c, "notes", "Notes (optional)", Textarea(d.get("notes", ""), name="notes", id="tb-notes", rows="5", maxlength=str(ti.MAX_NOTES), **c.attrs("notes")), "Allergies, parking codes, who is picking up whom"),
            Div(text(c, "booked_on", "Where did you book it? (optional)", d.get("booked_on"), "Shown as “Booked elsewhere: Expedia”", maxlength="30"),
                text(c, "itinerary", "Itinerary number (optional)", d.get("itinerary"), "Helps us spot a correction later", maxlength="30"), cls="tb-pair")]


BODIES = (step_where, step_dates, step_who, step_flights, step_hotel, step_car, step_notes)


# ---- drawing --------------------------------------------------------------------------------------------------------

def indicator(step):
    """"Step 3 of 7" and the seven dots; the current one is marked for screen readers."""
    items = [Li(Span(str(i), cls="tb-num"), Span(LABELS[i - 1], cls="tb-name"), cls="tb-dot" + (" is-now" if i == step else " is-done" if i < step else ""), **({"aria_current": "step"} if i == step else {}))
             for i in range(1, len(LABELS) + 1)]
    return Div(P(f"Step {step} of {len(LABELS)}" if step <= len(LABELS) else "Last check", cls="tb-count", id="tb-count"), Ol(*items, cls="tb-steps", aria_label="Progress"), cls="tb-progress")


def _hidden(draft, step, nav=None):
    return [Input(type="hidden", name="draft", value=tb.dump(draft)), Input(type="hidden", name="step", value=str(step)), *([Input(type="hidden", name="nav", value=nav)] if nav else [])]


def step_page(step, draft, errors=None, status=200, notice=""):
    tb.seed(step, draft)
    c = Ctx(draft, errors)
    banner = Div(notice, role="alert", cls="tb-errors", id="tb-notice") if notice else ""
    summary = Div(P("Let’s fix this first:", cls="tb-summary-h"), Ul(*[Li(A(msg, href=f"#tb-{name}")) for name, msg in c.errors.items()]), role="alert", cls="tb-errors", id="tb-errors") if c.errors else ""
    last = step == len(LABELS)
    form = Form(
        Button("Next", type="submit", name="nav", value="next", cls="tb-default", tabindex="-1", aria_hidden="true"),  # Enter submits "Next", never "Back"
        *_hidden(draft, step), banner, summary, *BODIES[step - 1](c),
        Div(Button(icon("chev-left", 16, 2.6), "Back", type="submit", name="nav", value="back", cls="btn btn-sm tb-back", id="tb-back", formnovalidate=True) if step > 1 else A("Cancel", href="/trips/import", cls="ti-link", id="tb-cancel"),
            Button("Check my trip" if last else f"Next: {LABELS[step]}", icon("arrow-right", 18, 2.6), type="submit", name="nav", value="next", cls="btn btn-ink tb-next", id="tb-next"), cls="tb-nav"),
        action=PATH, method="post", cls="tb-form", id="tb-form", novalidate=True, data_step=str(step), aria_label=TITLES[step - 1])
    out = page(f"{LABELS[step - 1]}: build a trip", Div(
        Div(Span("BUILD A TRIP", cls="eyebrow"), H1(TITLES[step - 1], cls="ti-title", id="tb-heading"), P(LEDES[step - 1], cls="ti-lede"), cls="ti-head"),
        indicator(step), Div(form, cls="ti-card tb-main"), cls="ti-wrap tb-wrap"), head=HEAD)
    return FtResponse(out, status_code=status) if status != 200 else out


def preview(session, draft):
    """The importer's own preview of the plan the draft builds, or the step to fix."""
    try:
        plan = tb.build(draft)
    except tb.BuildProblem as e:
        return step_page(e.step, draft, e.errors, 422)
    parsed = ti.Parsed(plan, ())
    match = importer.find_match(session, plan)
    return tip.preview_page("", parsed, match, importer.rides_to_retime(session, match[0], plan) if match else 0,
                            fields=[Input(type="hidden", name="draft", value=tb.dump(draft))], save_action=f"{PATH}/save",
                            edit=(PATH, [*_hidden(draft, len(LABELS) + 1), Input(type="hidden", name="nav", value="back")], "Change something"), lead=indicator(len(LABELS) + 1))


def advance(session, form):
    """One POST of the builder: read the step, then go where the button says."""
    draft = tb.load(str(form.get("draft", "") or ""))
    try:
        step = max(1, min(int(str(form.get("step", "1"))), len(LABELS) + 1))
    except ValueError:
        step = 1
    nav = str(form.get("nav", "next") or "next")
    if step <= len(LABELS):
        tb.read(step, form, draft)
    if step <= len(LABELS) and nav == "add":
        return step_page(step, tb.add_row(step, draft))
    if step <= len(LABELS) and nav.startswith("remove-") and nav[7:].isdigit():
        return step_page(step, tb.remove_row(step, draft, int(nav[7:])))
    if nav == "back":
        return step_page(max(1, step - 1), draft)
    if step > len(LABELS):
        return preview(session, draft)
    errors = tb.check(step, draft)
    if errors:
        return step_page(step, draft, errors, 422)
    return preview(session, draft) if step == len(LABELS) else step_page(step + 1, draft)


# ---- routes ---------------------------------------------------------------------------------------------------------

def register(app):
    @app.get(PATH)
    def build_form(session):
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={PATH}&intent=save", status_code=303)
        if not tip.can_import(session):
            return tip._sorry("Build a trip", tip.CANNOT, A("Back to your trips", href="/start", cls="btn btn-ink"), status=403)
        return step_page(1, tb.new_draft())

    @app.post(PATH)
    async def build_step(session, request):
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={PATH}&intent=save", status_code=303)
        if not tip.can_import(session):
            return tip._sorry("Build a trip", tip.CANNOT, A("Back to your trips", href="/start", cls="btn btn-ink"), status=403)
        return advance(session, await request.form())

    @app.post(f"{PATH}/from-import")
    def build_from_import(session, text: str = ""):
        """"Change something" on the import preview (F-058): the builder's first step, filled with everything the previewed text holds."""
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={PATH}&intent=save", status_code=303)
        if not tip.can_import(session):
            return tip._sorry("Build a trip", tip.CANNOT, A("Back to your trips", href="/start", cls="btn btn-ink"), status=403)
        try:
            parsed = ti.parse(text)
        except ti.ImportProblem as e:
            return tip.paste_page(text, e.errors, e.warnings, status=422)
        return step_page(1, tb.from_plan(parsed.plan))

    @app.post(f"{PATH}/save")
    def build_save(session, draft: str = "", token: str = "", replace: str = ""):
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={PATH}&intent=save", status_code=303)
        if not tip.can_import(session):
            return tip._sorry("Build a trip", tip.CANNOT, A("Back to your trips", href="/start", cls="btn btn-ink"), status=403)
        d = tb.load(draft)  # read again: a posted form is never trusted
        try:
            plan = tb.build(d)
        except tb.BuildProblem as e:
            return step_page(e.step, d, e.errors, 422)
        try:
            importer.save(session, plan, token or None, replace or None)
        except importer.SaveError as e:
            return step_page(len(LABELS), d, status=409, notice=str(e))
        return RedirectResponse("/calendar", status_code=303)
