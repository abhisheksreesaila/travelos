"""The Ask tab, "Ask GitAway" (phone shell F-067, built in F-072): say or type a change to a day; see it as before and after; Apply tells the family.

GET  /trip/ask?day=N         the box (frames 6 and 9 of docs/design/canvas/Mobile-Storyboards-v1.html and Trip-Canvas-v2.html); `done=N` shows the result of an Apply
POST /trip/ask/propose       text + day -> the proposal (saves nothing). A model failure or BUSY shows the box again, the request kept.
POST /trip/ask/edit          "Change it": back to the box with the request intact
POST /trip/ask/apply         the checked operations -> gitaway.speak.apply (one transaction, one card, one notification), then back here with `done`

The proposal travels between the pages in a hidden field and is checked again at Apply (gitaway.speak). Every write is gated by gitaway.access (editors); a viewer
sees a read-only note instead of the box. The microphone button exists only where the browser has speech recognition (assets/js/ask.js); typing and the
keyboard's own dictation always work.
"""

import json

from fasthtml.common import A, Button, Div, Form, H2, Input, Label, Link, Option, P, Select, Span, Textarea
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from gitaway import access, ai, familythread, pickers, session as ses, speak, tripcal as cal
from gitaway.icons import icon
from gitaway.layout import trip_field

TITLE = "Ask GitAway"
HEAD = (*pickers.HEAD, Link(rel="stylesheet", href="/assets/css/ask.css"))
SCRIPTS = ("/assets/js/ask.js",)
MAX_FIELD = 20000
TAGS = {"new": "NEW", "moved": "MOVED", "removed": "REMOVED", "changed": "CHANGED"}


def _state(request) -> dict:
    return request.scope.get("ask") or {}


def _day_of(request, session, value=None) -> int:
    raw = value if value is not None else request.query_params.get("day", "")
    try:
        return speak.day_index(session, int(raw))
    except (TypeError, ValueError):
        return speak.default_day(session)


def _day_name(t, day) -> str:
    d = cal.days(t)[day]
    return f"{d.strftime('%A')}, {d.strftime('%b')} {d.day}"


def day_url(day) -> str:
    return f"/trip/ask?day={int(day)}"


# ---- pieces --------------------------------------------------------------------------------------------------------------

def _viewer_card():
    return Div(Span(icon("lock", 26, 2.2), cls="ak-ico"), H2("Only editors can change the plan"),
               P("You can look at everything, but not change it. Ask a family admin to make you an editor."), A("Back to Today", href="/trip", cls="tp-btn tp-btn-ink"),
               cls="ak-card ak-center", id="ak-viewer", role="status")


def _day_picker(t, day, today):
    options = []
    for i, d in enumerate(cal.days(t)):
        label = f"{d.strftime('%a %b')} {d.day}" + (" · today" if i == today else "")
        options.append(Option(label, value=str(i), selected=(i == day)))
    return Label(Span("Which day", cls="ak-label"), Select(*options, name="day", id="ak-day", data_ga_label="Which day"), cls="ak-field")


def _box(request, session, day, text="", error="", status_note=""):
    b = ses.booking(session)
    t = cal.trip("", b)
    today = speak.today_index(session)
    return Form(
        trip_field(),
        Div(error, role="alert", cls="tp-error ak-error", id="ak-error") if error else "",
        _day_picker(t, day, today),
        Label(Span("What do you want to change?", cls="ak-label"),
              Textarea(text, name="text", id="ak-text", rows="4", maxlength=str(speak.MAX_REQUEST), required=True, autocomplete="off", spellcheck="true",
                       placeholder="We're tired. Block the next two hours and move lunch to 12:30."), cls="ak-field"),
        Div(Button(icon("mic", 22, 2.2), Span("Hold to talk"), type="button", id="ak-mic", cls="tp-btn tp-btn-white ak-mic", hidden=True, aria_pressed="false"),
            Span("", id="ak-mic-status", cls="ak-mic-status", role="status", aria_live="polite"), cls="ak-microw"),
        P(icon("mic", 16, 2.4), "On an iPhone, tap the microphone on the keyboard to dictate.", cls="ak-hint", id="ak-hint"),
        P(icon("pencil", 16, 2.4), "Reading your day…", cls="ak-progress", id="ak-progress", hidden=True, role="status"),
        Button("Ask GitAway", type="submit", cls="tp-btn tp-btn-coral ak-go", id="ak-go"),
        P("GitAway shows the change first. Nothing changes until you tap Apply.", cls="ak-fine"),
        action="/trip/ask/propose", method="post", id="ak-form", cls="ak-form")


def _chip(c):
    before = Span(c["before"], cls="ak-old") if c["before"] else ""
    arrow = Span(icon("arrow-right", 16, 2.4), cls="ak-arrow", aria_hidden="true") if c["before"] and c["after"] else ""
    after = Span(c["after"], cls="ak-new") if c["after"] else ""
    return Div(Span(TAGS[c["kind"]], cls=f"ak-tag ak-tag-{c['kind']}"), Div(Span(c["label"], cls="ak-what"), Div(before, arrow, after, cls="ak-ba"), cls="ak-x"), cls=f"ak-chip ak-{c['kind']}", data_kind=c["kind"])


def _proposal(session, prop, text, t):
    day = prop["day"]
    return Div(
        Div(Span(icon("check", 18, 3), cls="ak-badge"), Span(f"Here's the change · {_day_name(t, day)}", cls="ak-ph"), Span("Not applied yet", cls="ak-pill"), cls="ak-phead"),
        P(prop["summary"], cls="ak-say", id="ak-say") if prop["summary"] else "",
        Div(*[_chip(c) for c in prop["changes"]], cls="ak-chips", id="ak-chips"),
        Div(P("Left out:", cls="ak-label"), *[P(d, cls="ak-dropped") for d in prop["dropped"]], cls="ak-card ak-leftout", id="ak-leftout") if prop["dropped"] else "",
        Form(trip_field(), Input(type="hidden", name="day", value=str(day)), Input(type="hidden", name="ops", value=json.dumps(prop["ops"], separators=(",", ":"))),
             Input(type="hidden", name="text", value=text),
             Button(icon("check", 20, 3), "Apply and tell the family", type="submit", cls="tp-btn tp-btn-coral ak-go", id="ak-apply"),
             action="/trip/ask/apply", method="post", id="ak-apply-form"),
        Div(Form(Input(type="hidden", name="day", value=str(day)), Input(type="hidden", name="text", value=text),
                 Button("Change it", type="submit", cls="tp-btn tp-btn-white", id="ak-change"), action="/trip/ask/edit", method="post"),
            A("Cancel", href=day_url(day), cls="tp-btn tp-btn-white", id="ak-cancel"), cls="ak-acts"),
        P("Nothing changes until you tap Apply.", cls="ak-fine"),
        cls="ak-prop", id="ak-prop")


def _done(session, day, count):
    t = cal.trip("", ses.booking(session))
    word = f"{count} change{'s' if count != 1 else ''}"
    return Div(Span(icon("check", 26, 3), cls="ak-ico"), H2("Done"), P(f"{word} on {_day_name(t, day)}. The family has been told."),
               A("See the day", href=f"/trip?day={day}", cls="tp-btn tp-btn-ink", id="ak-see"), A("Ask for something else", href=day_url(day), cls="tp-btn tp-btn-white", id="ak-again"),
               cls="ak-card ak-center", id="ak-done", role="status")


# ---- the tab -------------------------------------------------------------------------------------------------------------

def content(request, session):
    if not access.can_edit(access.request_role()):
        ses.booking(session)
        return Div(_viewer_card(), cls="ak")
    st = _state(request)
    day = st["day"] if "day" in st else _day_of(request, session)
    t = cal.trip("", ses.booking(session))
    if st.get("proposal"):
        return Div(_proposal(session, st["proposal"], st.get("text", ""), t), cls="ak")
    done = request.query_params.get("done", "")
    if done.isdigit() and 0 < int(done) <= speak.MAX_OPS:
        return Div(_done(session, day, int(done)), cls="ak")
    return Div(_box(request, session, day, st.get("text", ""), st.get("error", "")), cls="ak")


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

    @app.post("/trip/ask/propose")
    async def propose(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        text = (form.get("text") or "")[: speak.MAX_REQUEST + 1]
        day = _day_of(request, session, form.get("day", ""))
        try:
            prop = await run_in_threadpool(speak.propose, session, day, text)   # the model takes seconds: never on the event loop (context variables travel along)
        except speak.SpeakError as e:
            return show(request, session, day=day, text=text, error=str(e), status=422)
        except ai.AIError as e:
            return show(request, session, day=day, text=text, error=str(e), status=503)
        return show(request, session, day=day, text=text, proposal=prop)

    @app.post("/trip/ask/edit")
    async def edit(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        return show(request, session, day=_day_of(request, session, form.get("day", "")), text=(form.get("text") or "")[: speak.MAX_REQUEST])

    @app.post("/trip/ask/apply")
    async def apply(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        day = _day_of(request, session, form.get("day", ""))
        text = (form.get("text") or "")[: speak.MAX_REQUEST]
        try:
            ops = json.loads((form.get("ops") or "")[:MAX_FIELD])
        except ValueError:
            return show(request, session, day=day, text=text, error="That proposal was lost. Ask again.", status=409)
        try:
            done = await run_in_threadpool(speak.apply, session, day, ops, form.get("trip") or None)
        except (speak.SpeakError, familythread.ThreadError) as e:
            return show(request, session, day=day, text=text, error=str(e), status=409)
        return RedirectResponse(f"{day_url(day)}&done={done['count']}", status_code=303)


def _guard(session):
    from gitaway import phone
    return phone.guard(session, "/trip/ask")
