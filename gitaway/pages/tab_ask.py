"""The Ask tab, the one box (F-072, F-087): talk, type or paste a change to a day, or a whole itinerary; quick follow-ups; one preview, day by day; one Apply.

GET  /trip/ask?day=N[&mode=paste|talk]   the box. With a day, everything goes on that day; without one GitAway spreads a pasted plan across the trip. `mode=paste`
                                          puts the Paste button first, `mode=talk` starts dictation where the browser can. `done=N` shows the result of an Apply.
GET  /trip/add                            the old "Add to the trip" address: lands in the box, paste first (F-087 folded the Convert screens into this one)
POST /trip/ask/propose                    text + day -> follow-up questions or the preview (saves nothing). A model failure or BUSY shows the box again, the text kept.
POST /trip/ask/answer                     the follow-up answers + the state -> the next questions or the preview (a plan needs no new model call)
POST /trip/ask/edit                       "Change it": back to the box with the text intact
POST /trip/ask/apply                      the previewed plan or change -> gitaway.say.apply / gitaway.speak.apply (one transaction, one card, one notification), then
                                          back here with `done`

The model side is gitaway/say.py (a short request is a change, a long one a plan). The state travels between the pages in hidden fields and is checked again at
Apply. Every write is gated by gitaway.access (editors); a viewer sees a read-only note instead of the box. The microphone button exists only where the browser has
speech recognition (assets/js/ask.js); the Paste button reads the clipboard where the browser allows it and otherwise points at the box; typing and the keyboard's
own dictation always work.
"""

import json

from fasthtml.common import A, Button, Div, Fieldset, Form, H2, H3, Input, Label, Legend, Link, Option, P, Select, Span, Textarea
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from gitaway import access, ai, canvas, familythread, pickers, say, session as ses, speak, tripcal as cal
from gitaway.icons import icon
from gitaway.layout import trip_field

TITLE = "Ask GitAway"
HEAD = (*pickers.HEAD, Link(rel="stylesheet", href="/assets/css/ask.css"))
SCRIPTS = ("/assets/js/ask.js",)
MAX_FIELD = 200000      # a plan's state (a long paste read into parts and steps) travels in one hidden field
TAGS = {"new": "NEW", "moved": "MOVED", "removed": "REMOVED", "changed": "CHANGED"}
MODES = ("paste", "talk")


def _state(request) -> dict:
    return request.scope.get("ask") or {}


def _day_of(request, session, value=None):
    """The trip day named (query string or form), or None when there is none or it is not a day of the trip."""
    raw = value if value is not None else request.query_params.get("day", "")
    try:
        return speak.day_index(session, int(raw))
    except (TypeError, ValueError):
        return None


def _day_name(t, day) -> str:
    d = cal.days(t)[day]
    return f"{d.strftime('%A')}, {d.strftime('%b')} {d.day}"


def day_url(day) -> str:
    return "/trip/ask" if day is None else f"/trip/ask?day={int(day)}"


def _hidden(name, value):
    return Input(type="hidden", name=name, value="" if value is None else str(value))


# ---- pieces --------------------------------------------------------------------------------------------------------------

def _viewer_card():
    return Div(Span(icon("lock", 26, 2.2), cls="ak-ico"), H2("Only editors can change the plan"),
               P("You can look at everything, but not change it. Ask a family admin to make you an editor."), A("Back to Today", href="/trip", cls="tp-btn tp-btn-ink"),
               cls="ak-card ak-center", id="ak-viewer", role="status")


def _day_picker(t, day, today, auto=False):
    options = [Option("Let GitAway place it", value="", selected=(day is None))]
    for i, d in enumerate(cal.days(t)):
        label = f"{d.strftime('%a %b')} {d.day}" + (" · today" if i == today else "")
        options.append(Option(label, value=str(i), selected=(i == day)))
    return Label(Span("Which day", cls="ak-label"), Select(*options, name="day", id="ak-day", data_ga_label="Which day", **({"data_auto": str(day)} if auto else {})), cls="ak-field")


def _box(request, session, day, text="", error="", mode=""):
    b = ses.booking(session)
    t = cal.trip("", b)
    today = speak.today_index(session)
    extra = {"data_mode": mode} if mode in MODES else {}
    auto = day is None and today is not None and say.route(text) == "change"
    if auto:
        day = today         # on the trip the box opens on today; a long paste is left for GitAway to place
    return Form(
        trip_field(),
        Div(error, role="alert", cls="tp-error ak-error", id="ak-error") if error else "",
        _day_picker(t, day, today, auto),
        Div(Button(icon("mic", 24, 2.2), Span("Tap to talk", id="ak-mic-label"), type="button", id="ak-mic", cls="tp-btn tp-btn-white ak-mic", hidden=True, aria_pressed="false"),
            Button(icon("clipboard", 22, 2.2), Span("Paste"), type="button", id="ak-paste", cls="tp-btn tp-btn-white ak-paste"), cls="ak-inputs"),
        Span("", id="ak-mic-status", cls="ak-mic-status", role="status", aria_live="polite"),
        Label(Span("What do you want to change or add?", cls="ak-label"),
              Textarea(text, name="text", id="ak-text", rows="5", required=True, autocomplete="off", spellcheck="true", data_limit=str(say.LIMIT), data_long=str(speak.MAX_REQUEST),
                       placeholder="Say it, type it or paste it. A change (\"move lunch to 12:30\") or a whole plan from a message or a web page."), cls="ak-field"),
        P("", id="ak-count", cls="ak-count", role="status", aria_live="polite", hidden=True),
        P(icon("mic", 16, 2.4), "On an iPhone, tap the microphone on the keyboard to dictate.", cls="ak-hint", id="ak-hint"),
        P(icon("pencil", 16, 2.4), Span("Reading it…", id="ak-progress-text"), Span("", id="ak-elapsed", cls="ak-elapsed"),
          Span("A long paste can take up to half a minute. Your text is safe.", cls="ak-progress-note"), cls="ak-progress", id="ak-progress", hidden=True, role="status"),
        Button("Ask GitAway", type="submit", cls="tp-btn tp-btn-coral ak-go", id="ak-go"),
        P("GitAway shows what it would change first. Nothing changes until you tap Apply.", cls="ak-fine"),
        action="/trip/ask/propose", method="post", id="ak-form", cls="ak-form", **extra)


def _chip(c):
    before = Span(c["before"], cls="ak-old") if c["before"] else ""
    arrow = Span(icon("arrow-right", 16, 2.4), cls="ak-arrow", aria_hidden="true") if c["before"] and c["after"] else ""
    after = Span(c["after"], cls="ak-new") if c["after"] else ""
    warn = Div(icon("lock", 14, 2.4), c["warn"], cls="ak-warn") if c.get("warn") else ""
    detail = P(c["detail"], cls="ak-detail") if c.get("detail") else ""
    return Div(Span(TAGS[c["kind"]], cls=f"ak-tag ak-tag-{c['kind']}"), Div(Span(c["label"], cls="ak-what"), Div(before, arrow, after, cls="ak-ba"), detail, warn, cls="ak-x"),
               cls=f"ak-chip ak-{c['kind']}", data_kind=c["kind"])


def _group(g):
    return Div(H3(g["label"], cls="ak-dayh"), Div(*[_chip(c) for c in g["chips"]], cls="ak-chips"), cls="ak-day", data_day=str(g["day"]))


def _proposal(session, step, text, day, t):
    prev = step["preview"]
    plan = prev["kind"] == "plan"
    state = step["state"]
    keep = [trip_field(), _hidden("day", day), _hidden("text", text)]
    payload = [_hidden("plan", json.dumps(state, separators=(",", ":")))] if plan else [_hidden("ops", json.dumps(prev["ops"], separators=(",", ":"))), _hidden("token", prev["token"])]
    return Div(
        Div(Span(icon("check", 18, 3), cls="ak-badge"), Span("Here's the plan" if plan else "Here's the change", cls="ak-ph"), Span("Not applied yet", cls="ak-pill"), cls="ak-phead"),
        P(prev["summary"], cls="ak-say", id="ak-say") if prev["summary"] else "",
        Div(*[_group(g) for g in prev["groups"]], cls="ak-days", id="ak-chips"),
        Div(P("Also:", cls="ak-label"), *[P(x, cls="ak-dropped") for x in prev["tidy"]], cls="ak-card ak-leftout", id="ak-tidy") if prev["tidy"] else "",
        Div(P("Left out:", cls="ak-label"), *[P(d, cls="ak-dropped") for d in prev["dropped"]], cls="ak-card ak-leftout", id="ak-leftout") if prev["dropped"] else "",
        Form(*keep, *payload, Button(icon("check", 20, 3), "Apply and tell the family", type="submit", cls="tp-btn tp-btn-coral ak-go", id="ak-apply"),
             action="/trip/ask/apply", method="post", id="ak-apply-form"),
        Div(Form(_hidden("day", day), _hidden("text", text), Button("Change it", type="submit", cls="tp-btn tp-btn-white", id="ak-change"), action="/trip/ask/edit", method="post", id="ak-change-form"),
            A("Cancel", href=day_url(day), cls="tp-btn tp-btn-white", id="ak-cancel"), cls="ak-acts"),
        P("Nothing changes until you tap Apply.", cls="ak-fine"),
        cls="ak-prop", id="ak-prop")


def _option(qid, o, suggest, picked):
    on = o["value"] == picked
    return Label(Input(type="radio", name=f"a_{qid}", value=o["value"], checked=on or None), Span(o["label"]),
                 Span("Suggested", cls="ak-sug") if o["value"] == suggest and suggest != "" else "", cls="ak-opt")


def _question(q):
    return Fieldset(Legend(q["text"]), P(q["why"], cls="ak-why") if q.get("why") else "", Div(*[_option(q["id"], o, q["suggest"], q["suggest"]) for o in q["options"]], cls="ak-opts"),
                    cls="ak-card ak-q", data_q=q["id"])


def _questions(session, step, text, day, error=""):
    qs = step["questions"]
    return Div(
        Div(error, role="alert", cls="tp-error ak-error", id="ak-error") if error else "",
        Form(trip_field(), _hidden("day", day), _hidden("text", text), _hidden("state", json.dumps(step["state"], separators=(",", ":"))),
             Div(Span("QUICK QUESTION" if len(qs) == 1 else f"{len(qs)} QUICK QUESTIONS", cls="ak-label"), P("The answer GitAway would guess is already chosen. Change it with one tap.", cls="ak-fine ak-left"), cls="ak-qhead"),
             *[_question(q) for q in qs],
             P(icon("pencil", 16, 2.4), Span("Reading it…"), Span("", cls="ak-elapsed"), cls="ak-progress", id="ak-q-progress", hidden=True, role="status"),
             Button("Continue", type="submit", cls="tp-btn tp-btn-coral ak-go", id="ak-continue"),
             Button("Change the words", type="submit", cls="tp-btn tp-btn-white ak-go", id="ak-change-text", formaction="/trip/ask/edit", formnovalidate=True),
             P("Nothing changes until you tap Apply.", cls="ak-fine"),
             action="/trip/ask/answer", method="post", id="ak-questions-form", cls="ak-form"),
        id="ak-questions")


def _done(session, day, count, kind="", steps=0):
    t = cal.trip("", ses.booking(session))
    if kind == "plan":
        said = f"{count} {'day' if count == 1 else 'days'} added" + (f", with {steps} {'ride or show' if steps == 1 else 'rides and shows'}" if steps else "")
        said = f"{said}, from {_day_name(t, day)}." if count > 1 else f"{said} on {_day_name(t, day)}."
    else:
        said = f"{count} change{'s' if count != 1 else ''} on {_day_name(t, day)}."
    return Div(Span(icon("check", 26, 3), cls="ak-ico"), H2("Done"), P(f"{said} The family has been told."),
               A("See the day" if count == 1 or kind != "plan" else "See the first day", href=f"/trip/canvas?day={day}", cls="tp-btn tp-btn-ink", id="ak-see"),
               A("Ask for something else", href=day_url(day), cls="tp-btn tp-btn-white", id="ak-again"), cls="ak-card ak-center", id="ak-done", role="status")


# ---- the tab -------------------------------------------------------------------------------------------------------------

def content(request, session):
    if not access.can_edit(access.request_role()):
        ses.booking(session)
        return Div(_viewer_card(), cls="ak")
    st = _state(request)
    day = st["day"] if "day" in st else _day_of(request, session)
    t = cal.trip("", ses.booking(session))
    if st.get("preview"):
        return Div(_proposal(session, st["step"], st.get("text", ""), day, t), cls="ak")
    if st.get("step"):
        return Div(_questions(session, st["step"], st.get("text", ""), day, st.get("error", "")), cls="ak")
    done = request.query_params.get("done", "")
    plan = request.query_params.get("kind") == "plan"
    if day is not None and done.isdigit() and 0 < int(done) <= (canvas.MAX_DAYS if plan else speak.MAX_OPS):
        steps = request.query_params.get("steps", "")
        return Div(_done(session, day, int(done), "plan" if plan else "", int(steps) if steps.isdigit() else 0), cls="ak")
    mode = request.query_params.get("mode", "")
    return Div(_box(request, session, day, st.get("text", ""), st.get("error", ""), st.get("mode", mode)), cls="ak")


def ask_button(day, compact=False, ident="ak-open") -> A:
    """The small "Ask GitAway" button the canvas puts on a day or a block: opens this tab with that day selected. `compact` is the round microphone alone (its name is
    still read out), for Today's heading where there is no room for the words."""
    if compact:
        return A(icon("mic", 18, 2.4), Span("Ask GitAway", cls="sr-only"), href=day_url(day), cls="btn btn-sm tp-edit ak-open ak-open-icon", id=ident, title="Ask GitAway")
    return A(icon("mic", 14, 2.4), "Ask GitAway", href=day_url(day), cls="btn btn-sm tp-edit ak-open", id=ident)


def register(app):
    from gitaway.pages import phone_tabs

    def show(request, session, *, status=200, **state):
        request.scope["ask"] = state
        page = phone_tabs.tab_page("ask", request, session)
        if status == 200:
            return page
        from fasthtml.core import FtResponse
        return FtResponse(page, status_code=status)

    def next_page(request, session, step, text, day, status=200, error=""):
        """The questions or the preview a step asks for."""
        if step["state"].get("kind") == "change" and isinstance(step["state"].get("day"), int):
            day = step["state"]["day"]      # the day it was read for (asked, or guessed from today), not the box's: Apply and "Change it" carry it
        if step["questions"]:
            return show(request, session, day=day, text=text, step=step, error=error, status=status)
        return show(request, session, day=day, text=text, step=step, preview=True, status=status)

    @app.get("/trip/add")
    def add_page(request, session):
        """The old Add to the trip address: the box, paste first (F-087)."""
        from gitaway import phone
        if (r := phone.guard(session, "/trip/ask?mode=paste")):
            return r
        return RedirectResponse("/trip/ask?mode=paste", status_code=303)

    @app.post("/trip/ask/propose")
    async def propose(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        text = (form.get("text") or "")[: say.LIMIT + 1]
        day = _day_of(request, session, form.get("day", ""))
        try:
            step = await run_in_threadpool(say.start, session, text, day)   # the model takes seconds: never on the event loop (context variables travel along)
        except (say.SayError, speak.SpeakError, canvas.CanvasError) as e:
            return show(request, session, day=day, text=text, error=str(e), status=422)
        except ai.AIError as e:
            return show(request, session, day=day, text=text, error=str(e), status=503)
        return next_page(request, session, step, text, day)

    @app.post("/trip/ask/answer")
    async def answer(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        text = (form.get("text") or "")[: say.LIMIT + 1]
        day = _day_of(request, session, form.get("day", ""))
        try:
            state = json.loads((form.get("state") or "")[:MAX_FIELD])
        except ValueError:
            return show(request, session, day=day, text=text, error="That was lost. Ask again.", status=409)
        answers = {k: v for k, v in form.items() if isinstance(v, str) and k.startswith("a_")}
        try:
            step = await run_in_threadpool(say.answer, session, state, answers, text)
        except say.SayError as e:
            if e.step:
                return next_page(request, session, e.step, text, day, status=422, error=str(e))
            return show(request, session, day=day, text=text, error=str(e), status=409)
        except (speak.SpeakError, canvas.CanvasError) as e:
            return show(request, session, day=day, text=text, error=str(e), status=422)
        except ai.AIError as e:
            return show(request, session, day=day, text=text, error=str(e), status=503)
        return next_page(request, session, step, text, day)

    @app.post("/trip/ask/edit")
    async def edit(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        return show(request, session, day=_day_of(request, session, form.get("day", "")), text=(form.get("text") or "")[: say.LIMIT + 1])

    @app.post("/trip/ask/apply")
    async def apply(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        day = _day_of(request, session, form.get("day", ""))
        text = (form.get("text") or "")[: say.LIMIT + 1]
        if form.get("plan"):
            try:
                state = json.loads(form["plan"][:MAX_FIELD])
                done = await run_in_threadpool(say.apply, session, state, "", form.get("trip") or None)
            except ValueError as e:     # json, then SayError: both are fit to show
                return show(request, session, day=day, text=text, error=str(e) if isinstance(e, say.SayError) else "That plan was lost. Ask again.", status=409)
            return RedirectResponse(f"{day_url(min(done['days']))}&done={done['count']}&kind=plan&steps={done['steps']}", status_code=303)
        try:
            ops = json.loads((form.get("ops") or "")[:MAX_FIELD])
        except ValueError:
            return show(request, session, day=day, text=text, error="That proposal was lost. Ask again.", status=409)
        if day is None:
            return show(request, session, day=day, text=text, error="That proposal was lost. Ask again.", status=409)
        try:
            done = await run_in_threadpool(speak.apply, session, day, ops, form.get("token") or "", form.get("trip") or None)
        except (speak.SpeakError, familythread.ThreadError) as e:
            return show(request, session, day=day, text=text, error=str(e), status=409)
        return RedirectResponse(f"{day_url(day)}&done={done['count']}", status_code=303)


def _guard(session):
    from gitaway import phone
    return phone.guard(session, "/trip/ask")
