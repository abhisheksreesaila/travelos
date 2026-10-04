"""Add to the trip (F-080): paste the family's messages, Convert, answer two questions, Add; and a block's parts and steps.

GET  /trip/add                   the paste page (frame 2 of docs/design/canvas/Trip-Canvas-v2.html)
POST /trip/add/convert           text -> step 1, "Here's what we found" (frame 3). Saves nothing. A model failure shows the page again, text intact.
POST /trip/add/questions         the draft -> step 2, "two quick questions" (frame 4): who the initials are, which day each park is, who a list is for
POST /trip/add/edit              back to the paste page with the text intact
POST /trip/add/save              "Add to trip": the only thing that saves (gitaway.canvas.save)
GET  /trip/block?id=a3           a block's parts and steps, with notes, done and Set aside
POST /trip/block/step            one tap on a step: done, not done, set aside, put back

The draft travels between the steps in a hidden field of the page's own form (and is checked again by gitaway.canvas.clean on every post), never in the
cookie or the database. Every write is gated by gitaway.access (editors); a viewer who opens /trip/add sees why they cannot convert.
"""

import json
from datetime import timedelta
from urllib.parse import urlencode

from fasthtml.common import A, Button, Details, Div, Fieldset, Form, H2, H3, Input, Label, Legend, Li, Link, Main, P, Span, Summary, Textarea, Ul
from fasthtml.core import FtResponse
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from gitaway import access, ai, canvas, members, phone, session as ses, tripcal as cal
from gitaway.icons import icon
from gitaway.layout import avatar, join_note, trip_field
from gitaway.pages.trip import trip_url

HEAD = (Link(rel="stylesheet", href="/assets/css/canvas.css"),)
SCRIPTS = ("/assets/js/canvas.js",)
KICKER_TIME = "9:00 AM – 9:00 PM"


def _hidden(name, value):
    return Input(type="hidden", name=name, value=value)


def _shell(request, session, title, body, kicker=None, status=200):
    b = ses.booking(session)
    t = cal.trip("", b)
    kicker = kicker or f"{t.title.upper()} · {cal.range_label(t.depart, t.return_).upper()}"
    page = phone.shell("today", phone.header(kicker, title), join_note(), Main(*body, id="main", cls="ph-main cv"), title=title, head=HEAD, scripts=SCRIPTS)
    return FtResponse(page, status_code=status) if status != 200 else page


def _viewer_card():
    return Div(Span(icon("lock", 26, 2.2), cls="cv-ico"), H2("Only editors can add to the trip"),
               P("You can look at everything, but not change it. Ask a family admin to make you an editor."), A("Back to Today", href="/trip", cls="tp-btn tp-btn-ink"), cls="cv-card cv-center", id="cv-viewer", role="status")


# ---- step 0: paste -------------------------------------------------------------------------------------------------------

def paste_page(request, session, text="", error="", status=200):
    if not access.can_edit(access.request_role()):
        return _shell(request, session, "Add to the trip", [_viewer_card()])
    ses.booking(session)    # opens the family, so trip_field() knows the trip
    form = Form(
        trip_field(),
        Div(error, role="alert", cls="tp-error cv-error", id="cv-error") if error else "",
        Label(Span("Pasted from Messages", cls="cv-label"),
              Textarea(text, name="text", id="cv-text", rows="12", maxlength=str(canvas.MAX_TEXT), required=True, placeholder="Paste the messages here, as they are. No tidying first.", autocomplete="off", spellcheck="true")),
        Button("Convert", type="submit", cls="tp-btn tp-btn-coral cv-convert", id="cv-convert"),
        Div(Span(icon("pencil", 14, 2.4), cls="cv-spin-ico"), "Reading your messages…", role="status", id="cv-progress", cls="cv-progress", hidden=True),
        Div(icon("mic", 16, 2.4), Span("or tap the mic on your keyboard and just say the plan"), cls="cv-hint"),
        action="/trip/add/convert", method="post", id="cv-form", cls="cv-form")
    howto = Div(H3("On iPhone, copy then paste."), P("Web apps can't be in the share sheet, so in Messages touch and hold the text, tap Copy, then paste it here."), cls="cv-card cv-how")
    return _shell(request, session, "Add to the trip", [form, howto], status=status)


# ---- step 1: what we found -----------------------------------------------------------------------------------------------

def _stat(n, label):
    return Div(Span(str(n), cls="cv-stat-n"), Span(label, cls="cv-stat-l"), cls="cv-stat")


def _areas(day) -> str:
    """"Lower Lot, lunch, then Upper Lot": the day's areas in order (meals in lower case)."""
    names = [p["name"].lower() if p["name"].casefold() in ("breakfast", "lunch", "dinner", "snack") else p["name"] for p in day["parts"]]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + ", then " + names[-1]


def _plural(n, one, many):
    return one if n == 1 else many


def found_page(request, session, draft, text, status=200):
    ses.booking(session)
    s = canvas.summary(draft)
    days = []
    for d in draft["days"]:
        chips = [Span(Span(p["name"], cls="cv-part-name"), Span(str(len(p["steps"])), cls="cv-count") if p["steps"] else Span(p["time_of_day"] or "no rides yet", cls="cv-when"), cls="cv-part") for p in d["parts"]]
        days.append(Div(H3(d["place"]), Span(_areas(d), cls="cv-sub"), Div(*chips, cls="cv-parts"), cls="cv-card cv-day"))
    tidy = []
    if draft["merged_repeats"]:
        tidy.append(Li(Span("Merged ", cls="cv-b"), f"{draft['merged_repeats']} repeated {_plural(draft['merged_repeats'], 'item', 'items')}. It was sent twice."))
    if draft["set_aside"]:
        tidy.append(Li(Span("Set aside: ", cls="cv-b"), ", ".join(a["title"] for a in draft["set_aside"]) + ". Still in the trip, just not in a day."))
    if draft["notes_kept"]:
        tidy.append(Li(Span("Kept your notes: ", cls="cv-b"), Span(" · ".join(draft["notes_kept"]), cls="cv-hand")))
    for lst in draft["lists"]:
        tidy.append(Li(Span("Made a list: ", cls="cv-b"), f"{lst['name']} ({len(lst['items'])})."))
    form = Form(
        trip_field(), _hidden("draft", json.dumps(draft, separators=(",", ":"))), _hidden("text", text),
        Button("Next: 2 quick questions", type="submit", cls="tp-btn tp-btn-coral", id="cv-next"),
        Button("Edit text", type="submit", cls="tp-btn tp-btn-plain", id="cv-edit", formaction="/trip/add/edit", formnovalidate=True),
        action="/trip/add/questions", method="post", cls="cv-actions", id="cv-found-form")
    stats = Div(_stat(s["days"], _plural(s["days"], "park day", "park days")), _stat(s["areas"], _plural(s["areas"], "area", "areas")), _stat(s["steps"], _plural(s["steps"], "ride or show", "rides and shows")), cls="cv-stats", id="cv-stats")
    back = Button(icon("chev-left", 16, 2.6), "Back", type="submit", form="cv-found-form", formaction="/trip/add/edit", formnovalidate=True, cls="cv-topback", id="cv-top-back")
    return _shell(request, session, "Here's what we found", [back, Span("WE READ YOUR MESSAGES", cls="cv-kicker"), stats, *days,
                                                             Div(Span("WHAT WE TIDIED", cls="cv-kicker"), Ul(*tidy, cls="cv-tidy") if tidy else P("Nothing needed tidying.", cls="cv-sub"), cls="cv-card", id="cv-tidied"), form], status=status)


# ---- step 2: two quick questions -----------------------------------------------------------------------------------------

def _person_choice(name, person, value, checked, extra=""):
    face = ses.Friend(person["name"], person["initials"], person["color"])
    return Label(Input(type="radio", name=name, value=value, checked=checked or None), avatar(face, "tp-av"), Span(person["name"].split()[0] if person["name"] else "Someone"), extra, cls="cv-choice")


def _who_question(i, entry, people, vals):
    token = entry["token"]
    picked = vals.get(f"who_{i}") or (f"m:{entry['member']}" if entry["member"] else "keep")
    choices = [_person_choice(f"who_{i}", p, f"m:{p['user_id']}", picked == f"m:{p['user_id']}", Span(entry["why"], cls="cv-why") if entry["member"] == p["user_id"] and entry["why"] else "") for p in people]
    choices.append(Div(Label(Input(type="radio", name=f"who_{i}", value="new", checked=(picked == "new") or None), Span("+ Someone new"), cls="cv-choice"),
                       Input(type="text", name=f"new_{i}", value=vals.get(f"new_{i}", ""), placeholder="Name", maxlength="30", autocomplete="off", aria_label=f"Name for {token}", cls="cv-new")))
    choices.append(Label(Input(type="radio", name=f"who_{i}", value="keep", checked=(picked == "keep") or None), Span(f"Keep as {token}"), cls="cv-choice"))
    suggested = next((p for p in people if p["user_id"] == entry["member"]), None) if entry["member"] else None
    if suggested and picked == f"m:{suggested['user_id']}":     # a confident suggestion is one confirmed chip; "change" opens every option
        face = ses.Friend(suggested["name"], suggested["initials"], suggested["color"])
        chip = Div(avatar(face, "tp-av"), Span(suggested["name"].split()[0], cls="cv-chip-name"), Span(entry["why"], cls="cv-why") if entry["why"] else "", Span(icon("check", 14, 3), cls="cv-sure", aria_hidden="true"), cls="cv-confirmed", data_chip="")
        return Fieldset(Legend(Span(token, cls="cv-token"), f"Who is {token}?"), chip, Details(Summary("change", cls="cv-change"), *choices, cls="cv-more"), cls="cv-card cv-whoq", data_token=token)
    return Fieldset(Legend(Span(token, cls="cv-token"), f"Who is {token}?"), *choices, cls="cv-card cv-whoq", data_token=token)


def _day_question(i, d, dates, vals):
    chips = [Label(Input(type="radio", name=f"day_{i}", value=str(n), checked=(vals.get(f"day_{i}") == str(n)) or None, required=(n == 0) or None),
                   Span(day.strftime("%a").upper(), cls="cv-dow"), Span(str(day.day), cls="cv-dom"), cls="cv-day-chip") for n, day in enumerate(dates)]
    return Fieldset(Legend(d["place"]), Div(*chips, cls="cv-days"), cls="cv-card cv-whichday", data_park=str(i))


def _list_question(j, lst, people, vals):
    picked = vals.get(f"listfor_{j}", "none")
    choices = [_person_choice(f"listfor_{j}", p, f"m:{p['user_id']}", picked == f"m:{p['user_id']}") for p in people]
    choices.append(Div(Label(Input(type="radio", name=f"listfor_{j}", value="other", checked=(picked == "other") or None), Span("Someone else"), cls="cv-choice"),
                       Input(type="text", name=f"listother_{j}", value=vals.get(f"listother_{j}", ""), placeholder="Name", maxlength="30", autocomplete="off", aria_label=f"Who {lst['name']} is for", cls="cv-new")))
    choices.append(Label(Input(type="radio", name=f"listfor_{j}", value="none", checked=(picked == "none") or None), Span("Just keep it as a list"), cls="cv-choice"))
    return Fieldset(Legend(f"{lst['name']}: who's it for?"), *choices, cls="cv-card cv-listfor")


def questions_page(request, session, draft, text, vals=None, error="", status=200):
    vals = vals or {}
    b = ses.booking(session)
    t = cal.trip("", b)
    people = canvas.family_people(session)
    q = canvas.questions(draft, people, text)
    asked = {e["token"]: e for e in q["who"]}
    blocks = []
    if q["who"]:
        blocks.append(Div(Span("1", cls="cv-step"), H2("Who are " + _oxford([e["token"] for e in q["who"]]) + "?"), cls="cv-qhead"))
        blocks += [_who_question(i, asked[tok], people, vals) for i, tok in enumerate(draft["initials"]) if tok in asked]
    blocks.append(Div(Span("2" if q["who"] else "1", cls="cv-step"), H2("Which day is each park?"), cls="cv-qhead"))
    dates = cal.days(t)
    blocks += [_day_question(i, d, dates, vals) for i, d in enumerate(draft["days"])]
    blocks += [_list_question(j, lst, people, vals) for j, lst in enumerate(draft["lists"])]
    form = Form(
        trip_field(), _hidden("draft", json.dumps(draft, separators=(",", ":"))), _hidden("text", text),
        Div(error, role="alert", cls="tp-error cv-error", id="cv-error") if error else "",
        *blocks,
        P("Nothing is saved until you tap Add to trip.", cls="cv-sub", id="cv-promise"),
        Button("Add to trip", type="submit", cls="tp-btn tp-btn-coral", id="cv-add"),
        Button("Back", type="submit", cls="tp-btn tp-btn-plain", id="cv-back", formaction="/trip/add/found", formnovalidate=True),
        action="/trip/add/save", method="post", id="cv-questions-form", cls="cv-form")
    back = Button(icon("chev-left", 16, 2.6), "Back", type="submit", form="cv-questions-form", formaction="/trip/add/found", formnovalidate=True, cls="cv-topback", id="cv-top-back")
    return _shell(request, session, "Two quick questions", [back, Span("CONVERT, STEP 2", cls="cv-kicker"), form], status=status)


def _oxford(items):
    return cal.oxford(items)


# ---- routes: paste, convert, ask, save -------------------------------------------------------------------------------------

def _guard(session):
    if not ses.current_traveler(session):
        return RedirectResponse("/signin?next=%2Ftrip%2Fadd", status_code=303)
    if not ses.booking(session):
        return RedirectResponse("/start", status_code=303)
    return None


def _draft(draft: str):
    try:
        return canvas.clean(json.loads(draft or ""))
    except ValueError:
        return None


def _answers(draft, form):
    """What the questions page posted -> canvas.save's answers."""
    who = {}
    for i, tok in enumerate(draft["initials"]):
        choice = (form.get(f"who_{i}") or "").strip()
        if choice.startswith("m:"):
            who[tok] = choice
        elif choice == "new":
            who[tok] = "n:" + ((form.get(f"new_{i}") or "").strip() or tok)
        elif choice == "keep":
            who[tok] = f"i:{tok}"
    days = []
    for i in range(len(draft["days"])):
        v = (form.get(f"day_{i}") or "").strip()
        days.append(int(v) if v.isdigit() else None)
    list_for = []
    for j in range(len(draft["lists"])):
        choice = (form.get(f"listfor_{j}") or "none").strip()
        list_for.append(choice if choice.startswith("m:") else "n:" + (form.get(f"listother_{j}") or "").strip() if choice == "other" else "")
    return {"who": who, "days": days, "list_for": list_for}


def register(app):
    @app.get("/trip/add")
    def add_page(request, session):
        if (r := _guard(session)):
            return r
        return paste_page(request, session)

    @app.post("/trip/add/edit")
    async def edit(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        return paste_page(request, session, text=form.get("text", ""))

    @app.post("/trip/add/found")
    async def found(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        draft = _draft(form.get("draft", ""))
        if draft is None or canvas.empty(draft):
            return paste_page(request, session, text=form.get("text", ""))
        return found_page(request, session, draft, form.get("text", ""))

    @app.post("/trip/add/convert")
    async def convert(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        text = (form.get("text") or "")[: canvas.MAX_TEXT + 1]
        try:
            draft = await run_in_threadpool(canvas.convert, session, text)    # the model takes seconds: never on the event loop (context variables travel along)
        except canvas.CanvasError as e:
            return paste_page(request, session, text=text, error=str(e), status=422)
        except ai.AIError as e:
            return paste_page(request, session, text=text, error=str(e), status=503)
        return found_page(request, session, draft, text)

    @app.post("/trip/add/questions")
    async def questions(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        draft = _draft(form.get("draft", ""))
        if draft is None or canvas.empty(draft):
            return paste_page(request, session, text=form.get("text", ""), error="That draft was lost. Convert the messages again.", status=409)
        return questions_page(request, session, draft, form.get("text", ""))

    @app.post("/trip/add/save")
    async def save(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        text = form.get("text", "")
        draft = _draft(form.get("draft", ""))
        if draft is None or canvas.empty(draft):
            return paste_page(request, session, text=text, error="That draft was lost. Convert the messages again.", status=409)
        vals = {k: v for k, v in form.items() if isinstance(v, str)}
        try:
            done = canvas.save(session, draft, _answers(draft, form))
        except canvas.CanvasError as e:
            return questions_page(request, session, draft, text, vals=vals, error=str(e), status=409)
        if done["acts"]:
            first = done["acts"][0]
            return RedirectResponse(trip_url(day=first[2], new=first[0]), status_code=303)
        return RedirectResponse(trip_url(), status_code=303)

    # ---- a block's parts and steps ---------------------------------------------------------------------------------------

    @app.get("/trip/block")
    def block_page(request, session, id: str = ""):
        if (r := _guard(session)):
            return r
        view = canvas.block(session, id[:8])
        if view is None:
            return RedirectResponse(trip_url(), status_code=303)
        return block_view(request, session, view)

    @app.post("/trip/block/step")
    async def step(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        act = (form.get("act") or "")[:8]
        do = form.get("do") or ""
        sid = (form.get("step") or "")[:40]
        try:
            if do in ("done", "undone"):
                canvas.set_done(session, sid, do == "done")
            elif do in ("aside", "back"):
                canvas.set_aside(session, sid, do == "aside")
        except canvas.CanvasError:
            pass       # a step someone else just removed: show the block as it is now
        return RedirectResponse(f"/trip/block?{urlencode({'id': act, 'trip': ses.open_trip_id()})}", status_code=303)


# ---- a block ---------------------------------------------------------------------------------------------------------------

def _step_row(s, act, editor, aside=False):
    chips = [Span(w, cls="cv-chip") for w in s["who"]]
    meta = Div(Span(s["time"], cls="cv-time") if s["time"] else "", *chips, cls="cv-meta") if (s["time"] or chips) else ""
    note = Span(icon("pencil", 13, 2.4), s["note"], cls="tp-pnote cv-note") if s["note"] else ""
    buttons = ""
    if editor:
        btns = []
        if aside:
            btns.append(Button("Put back", type="submit", name="do", value="back", cls="tp-mini cv-act"))
        else:
            btns.append(Button("Not done" if s["done"] else "Mark done", type="submit", name="do", value="undone" if s["done"] else "done", cls="tp-mini cv-act cv-done-btn"))
            btns.append(Button("Set aside", type="submit", name="do", value="aside", cls="tp-mini cv-act"))
        buttons = Form(_hidden("step", s["id"]), _hidden("act", act), trip_field(), *btns, action="/trip/block/step", method="post", cls="cv-step-form")
    return Div(Div(Span(icon("check", 16, 3), cls="cv-check", aria_hidden="true") if s["done"] else "", Span(s["title"], cls="tp-what cv-title"), Span("Done", cls="sr-only") if s["done"] else "", cls="cv-step-head"),
               meta, note, buttons, cls=f"cv-step-row{' is-done' if s['done'] else ''}{' is-aside' if aside else ''}", id=f"step-{s['id']}", data_step=s["id"])


def block_view(request, session, view):
    a = view["act"]
    b = ses.booking(session)
    t = cal.trip("", b)
    day = t.depart + timedelta(days=a.day)
    editor = access.can_edit(access.request_role())
    sections = []
    for p in view["parts"]:
        head = Div(H3(p["name"]), Span(p["time_of_day"], cls="cv-when") if p["time_of_day"] else "", cls="cv-part-head")
        rows = [_step_row(s, a.id, editor) for s in p["steps"]]
        sections.append(Div(head, *(rows or [P("Nothing here yet.", cls="cv-sub")]), cls="cv-card cv-block-part", data_part=p["id"]))
    if view["aside"]:
        sections.append(Div(Div(H3(f"Set aside · {len(view['aside'])}"), Span("still in the trip", cls="cv-when"), cls="cv-part-head"), *[_step_row(s, a.id, editor, aside=True) for s in view["aside"]], cls="cv-card cv-tray", id="cv-tray"))
    for lst in view["lists"]:
        items = [Li(Span(i["title"], cls="tp-what"), Span(i["note"], cls="cv-sub") if i["note"] else "") for i in lst["items"]]
        sections.append(Div(Div(H3(lst["name"]), Span(f"for {lst['for']}", cls="cv-when") if lst["for"] else "", cls="cv-part-head"), Ul(*items, cls="cv-list"), cls="cv-card cv-triplist", data_list=lst["id"]))
    kicker = f"{day.strftime('%a %b').upper()} {day.day} · {cal.fmt_time(a.start)} – {cal.fmt_time(a.end)}".upper()
    return _shell(request, session, a.title, [*sections, A("Back to the day", href=trip_url(day=a.day), cls="tp-btn tp-btn-plain", id="cv-back-day")], kicker=kicker)
