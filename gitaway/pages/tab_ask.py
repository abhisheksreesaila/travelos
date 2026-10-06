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
import re

from fasthtml.common import A, Button, Div, Fieldset, Form, H2, H3, Input, Label, Legend, Link, Option, P, Select, Span, Textarea, to_xml
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response

from gitaway import access, ai, canvas, familythread, pickers, say, session as ses, speak, tripcal as cal, voicenotes
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


def _heard(raw) -> list:
    """What was dictated in another language: [[what was said, its English], ...] from the page's hidden field. Anything malformed is dropped."""
    try:
        items = json.loads((raw or "")[:MAX_FIELD])
    except ValueError:
        return []
    out = []
    for it in items if isinstance(items, list) else []:
        if isinstance(it, list) and len(it) == 2 and all(isinstance(x, str) and x.strip() for x in it):
            out.append([it[0][: say.LIMIT], it[1][: say.LIMIT]])
    return out[:20]


def _for_the_planner(text, heard) -> str:
    """The box's text with each dictated passage swapped for its English version, so the planner reads English; typed words and edits stay as they are, and a
    passage the person changed is simply left as written (the planner reads any language)."""
    for spoken, english in list(heard)[:20]:
        if len(spoken) < 3:
            continue        # a stray letter would match everywhere
        text = text.replace(spoken, english, 1)
        if len(text) > say.LIMIT:
            return text[: say.LIMIT + 1]       # over the limit: say.start refuses it with the usual message
    return text


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


def _day_chip(t, day, today, auto):
    """The sheet's day: a small date chip that opens a row of the trip's days (and "Any day": GitAway places it). The hidden `day` field carries the choice; the script
    (assets/js/ask_sheet.js) moves it and the chip's words. Without script the chip does nothing and the day stays as drawn."""
    days = [("", "Any day")] + [(str(i), f"{d.strftime('%a %b')} {d.day}" + (" · today" if i == today else "")) for i, d in enumerate(cal.days(t))]
    label = dict(days).get("" if day is None else str(day), "Any day")
    return Div(
        Div(Button(icon("calendar", 16, 2.4), Span(label, id="ak-chip-label"), type="button", id="ak-chip", cls="ak-chip-day", aria_expanded="false", aria_controls="ak-days-pick", data_ga_label="Which day"),
            cls="ak-chiprow"),
        Div(*[Button(name, type="button", cls="ak-dpick", data_d=v, aria_pressed="true" if v == ("" if day is None else str(day)) else "false") for v, name in days],
            id="ak-days-pick", cls="ak-dpicks", role="group", aria_label="Which day", hidden=True),
        Input(type="hidden", name="day", id="ak-day", value="" if day is None else str(day), **({"data_auto": str(day)} if auto else {})),
        cls="ak-daybar")


def _sheet_box(request, session, day, text="", error="", mode="", heard=()):
    """The box as the Ask sheet draws it (F-104): the day chip, the big mic, the note, a small Paste, one Done. No title, no day dropdown, no second Ask button, and the keyboard-mic
    hint only where this phone cannot record or recognise speech (the script shows it then)."""
    t = cal.trip("", ses.booking(session))
    today = speak.today_index(session)
    auto = day is None and today is not None and say.route(text) == "change"
    if auto:
        day = today
    return Form(
        trip_field(),
        Div(error, role="alert", cls="tp-error ak-error", id="ak-error") if error else "",
        Div(_day_chip(t, day, today, auto), Button(icon("clipboard", 20, 2.2), Span("Paste", cls="sr-only"), type="button", id="ak-paste", cls="ak-paste-icon", title="Paste", aria_label="Paste"), cls="ak-sheet-top"),
        Div(Button(Span(cls="ak-dot", aria_hidden="true"), icon("mic", 34, 2.2), Span("Tap to talk", id="ak-mic-label"), Span("0:00", id="ak-mic-time", cls="ak-time", hidden=True),
                   type="button", id="ak-mic", cls="ak-mic ak-bigmic", hidden=True, aria_pressed="false", data_max_secs=str(voicenotes.MAX_SECONDS), data_piece_secs=str(PIECE_SECONDS),
                   data_server="1" if ai.configured("transcribe") else ""),
            Button(icon("x", 18, 2.4), Span("Cancel"), type="button", id="ak-rec-cancel", cls="ak-cancel", hidden=True), cls="ak-microw"),
        Span("", id="ak-mic-status", cls="ak-mic-status", role="status", aria_live="polite"),
        P(icon("pencil", 16, 2.4), Span("Transcribing…"), Span("", id="ak-tr-elapsed", cls="ak-elapsed"), cls="ak-progress", id="ak-transcribing", hidden=True, role="status"),
        Textarea(text, name="text", id="ak-text", rows="3", required=True, autocomplete="off", spellcheck="true", aria_label="What do you want to change or add?", data_limit=str(say.LIMIT), data_long=str(speak.MAX_REQUEST),
                 placeholder="Say it or type it…"),
        P("", id="ak-understood", cls="ak-understood", role="status", aria_live="polite", hidden=True),
        _hidden("heard", json.dumps(list(heard), ensure_ascii=False, separators=(",", ":")) if heard else ""),
        P("", id="ak-count", cls="ak-count", role="status", aria_live="polite", hidden=True),
        P(icon("mic", 16, 2.4), "Tap the microphone on the keyboard to dictate.", cls="ak-hint", id="ak-hint", hidden=True),
        P(icon("pencil", 16, 2.4), Span("Reading it…", id="ak-progress-text"), Span("", id="ak-elapsed", cls="ak-elapsed"), cls="ak-progress", id="ak-progress", hidden=True, role="status"),
        Button("Done", type="submit", cls="tp-btn tp-btn-coral ak-go", id="ak-go"),
        action="/trip/ask/propose", method="post", id="ak-form", cls="ak-form ak-sheetform", data_sheet="1", **({"data_mode": mode} if mode in MODES else {}))


def _box(request, session, day, text="", error="", mode="", heard=()):
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
        Div(Button(Span(cls="ak-dot", aria_hidden="true"), icon("mic", 24, 2.2), Span("Tap to talk", id="ak-mic-label"), Span("0:00", id="ak-mic-time", cls="ak-time", hidden=True),
                   type="button", id="ak-mic", cls="tp-btn tp-btn-white ak-mic", hidden=True, aria_pressed="false", data_max_secs=str(voicenotes.MAX_SECONDS), data_piece_secs=str(PIECE_SECONDS),
                   data_server="1" if ai.configured("transcribe") else ""),
            Button(icon("clipboard", 22, 2.2), Span("Paste"), type="button", id="ak-paste", cls="tp-btn tp-btn-white ak-paste"),
            Button(icon("x", 22, 2.2), Span("Cancel"), type="button", id="ak-rec-cancel", cls="tp-btn tp-btn-white ak-cancel", hidden=True), cls="ak-inputs"),
        Span("", id="ak-mic-status", cls="ak-mic-status", role="status", aria_live="polite"),
        P(icon("pencil", 16, 2.4), Span("Transcribing…"), Span("", id="ak-tr-elapsed", cls="ak-elapsed"), cls="ak-progress", id="ak-transcribing", hidden=True, role="status"),
        Label(Span("What do you want to change or add?", cls="ak-label"),
              Textarea(text, name="text", id="ak-text", rows="5", required=True, autocomplete="off", spellcheck="true", data_limit=str(say.LIMIT), data_long=str(speak.MAX_REQUEST),
                       placeholder="Say it, type it or paste it. A change (\"move lunch to 12:30\") or a whole plan from a message or a web page."), cls="ak-field"),
        P("", id="ak-understood", cls="ak-understood", role="status", aria_live="polite", hidden=True),
        _hidden("heard", json.dumps(list(heard), ensure_ascii=False, separators=(",", ":")) if heard else ""),
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


def _proposal(session, step, text, day, t, heard=(), sheet=False):
    prev = step["preview"]
    kept = _hidden("heard", json.dumps(list(heard), ensure_ascii=False, separators=(",", ":")) if heard else "")
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
        Form(*keep, *payload, Button(icon("check", 20, 3), "Apply" if sheet else "Apply and tell the family", type="submit", cls="tp-btn tp-btn-coral ak-go", id="ak-apply"),
             action="/trip/ask/apply", method="post", id="ak-apply-form"),
        Div(Form(_hidden("day", day), _hidden("text", text), kept, Button("Change it", type="submit", cls="tp-btn tp-btn-white", id="ak-change"), action="/trip/ask/edit", method="post", id="ak-change-form"),
            *([] if sheet else [A("Cancel", href=day_url(day), cls="tp-btn tp-btn-white", id="ak-cancel")]), cls="ak-acts"),
        *([] if sheet else [P("Nothing changes until you tap Apply.", cls="ak-fine")]),
        cls="ak-prop ak-prop-sheet" if sheet else "ak-prop", id="ak-prop")


def _option(qid, o, suggest, picked):
    on = o["value"] == picked
    return Label(Input(type="radio", name=f"a_{qid}", value=o["value"], checked=on or None), Span(o["label"]),
                 Span("Suggested", cls="ak-sug") if o["value"] == suggest and suggest != "" else "", cls="ak-opt")


def _question(q):
    return Fieldset(Legend(q["text"]), P(q["why"], cls="ak-why") if q.get("why") else "", Div(*[_option(q["id"], o, q["suggest"], q["suggest"]) for o in q["options"]], cls="ak-opts"),
                    cls="ak-card ak-q", data_q=q["id"])


def _questions(session, step, text, day, error="", heard=(), sheet=False):
    qs = step["questions"]
    kept = _hidden("heard", json.dumps(list(heard), ensure_ascii=False, separators=(",", ":")) if heard else "")
    return Div(
        Div(error, role="alert", cls="tp-error ak-error", id="ak-error") if error else "",
        Form(trip_field(), _hidden("day", day), _hidden("text", text), kept, _hidden("state", json.dumps(step["state"], separators=(",", ":"))),
             Div(Span("QUICK QUESTION" if len(qs) == 1 else f"{len(qs)} QUICK QUESTIONS", cls="ak-label"), P("The answer GitAway would guess is already chosen. Change it with one tap.", cls="ak-fine ak-left"), cls="ak-qhead"),
             *[_question(q) for q in qs],
             P(icon("pencil", 16, 2.4), Span("Reading it…"), Span("", cls="ak-elapsed"), cls="ak-progress", id="ak-q-progress", hidden=True, role="status"),
             Button("Continue", type="submit", cls="tp-btn tp-btn-coral ak-go", id="ak-continue"),
             Button("Change the words", type="submit", cls="tp-btn tp-btn-white ak-go", id="ak-change-text", formaction="/trip/ask/edit", formnovalidate=True),
             *([] if sheet else [P("Nothing changes until you tap Apply.", cls="ak-fine")]),
             action="/trip/ask/answer", method="post", id="ak-questions-form", cls="ak-form", **({"data_tap": "1"} if sheet and len(qs) == 1 else {})),     # in the sheet one question is one tap
        id="ak-questions")


def _done(session, day, count, kind="", steps=0, merged=0):
    t = cal.trip("", ses.booking(session))
    if kind == "plan":
        said = f"{count} {'day' if count == 1 else 'days'} added" + (f", with {steps} {'ride or show' if steps == 1 else 'rides and shows'}" if steps else "")
        said = f"{said}, from {_day_name(t, day)}." if count > 1 else f"{said} on {_day_name(t, day)}."
        if merged:
            said = (f"Added {str(steps) + ' ' + ('ride or show' if steps == 1 else 'rides and shows') + ' ' if steps else ''}to what was already planned on {_day_name(t, day)}." if merged == count and count == 1 else f"{said} {merged} of them were added to a day that was already planned.")
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
        return Div(_proposal(session, st["step"], st.get("text", ""), day, t, st.get("heard", ())), cls="ak")
    if st.get("step"):
        return Div(_questions(session, st["step"], st.get("text", ""), day, st.get("error", ""), st.get("heard", ())), cls="ak")
    done = request.query_params.get("done", "")
    plan = request.query_params.get("kind") == "plan"
    if day is not None and done.isdigit() and 0 < int(done) <= (canvas.MAX_DAYS if plan else speak.MAX_OPS):
        steps = request.query_params.get("steps", "")
        merged = request.query_params.get("merged", "")
        return Div(_done(session, day, int(done), "plan" if plan else "", int(steps) if steps.isdigit() else 0, int(merged) if merged.isdigit() else 0), cls="ak")
    mode = request.query_params.get("mode", "")
    return Div(_box(request, session, day, st.get("text", ""), st.get("error", ""), st.get("mode", mode), st.get("heard", ())), cls="ak")


def wants_sheet(request) -> bool:
    """The Ask sheet (F-104, assets/js/ask_sheet.js) asks for the box, the questions and the preview as fragments with this header."""
    return request.headers.get("x-ask") == "1"


def sheet_fragment(request, session, status=200):
    """What the sheet shows for this step: the box, the follow-up questions or the preview, alone (no page around it)."""
    st = _state(request)
    day = st["day"] if "day" in st else _day_of(request, session)
    t = cal.trip("", ses.booking(session))
    if st.get("preview"):
        body = _proposal(session, st["step"], st.get("text", ""), day, t, st.get("heard", ()), sheet=True)
    elif st.get("step"):
        body = _questions(session, st["step"], st.get("text", ""), day, st.get("error", ""), st.get("heard", ()), sheet=True)
    else:
        body = _sheet_box(request, session, day, st.get("text", ""), st.get("error", ""), st.get("mode", ""), st.get("heard", ()))
    return Response(to_xml(Div(body, id="ak-sheet-body")), status_code=status, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-store"})


def sheet_open(request, session):
    """GET /trip/ask?day=N with X-Ask: the box the sheet opens with (it starts listening when the page lets it: data-mode=talk). Editors only."""
    if not access.can_edit(access.request_role()):
        return PlainTextResponse("Only editors can change the plan.", status_code=403)
    request.scope["ask"] = {"mode": "talk"}
    return sheet_fragment(request, session)


def _toast(kinds, count, plan=False) -> str:
    """"Added 3 plans · Moved 1 · The family has been told", from what Apply did."""
    if plan:
        return f"Added {count} {'day' if count == 1 else 'days'} · The family has been told"
    n = lambda *k: sum(1 for x in kinds if x in k)
    parts = []
    if n("add_plan", "add_step"):
        adds = n("add_plan", "add_step")
        word = "plan" if n("add_step") == 0 else "step" if n("add_plan") == 0 else "item"
        parts.append(f"Added {adds} {word}{'s' if adds != 1 else ''}")
    if n("move_plan", "move_step"):
        parts.append(f"Moved {n('move_plan', 'move_step')}")
    if n("remove_plan"):
        parts.append(f"Removed {n('remove_plan')}")
    rest = len(kinds) - n("add_plan", "add_step", "move_plan", "move_step", "remove_plan")
    if rest:
        parts.append(f"Changed {rest}")
    return " · ".join(parts or [f"Changed {count}"]) + " · The family has been told"


def ask_button(day, compact=False, ident="ak-open") -> A:
    """The small "Ask GitAway" button the canvas puts on a day or a block: opens this tab with that day selected. `compact` is the round microphone alone (its name is
    still read out), for Today's heading where there is no room for the words."""
    if compact:
        return A(icon("mic", 18, 2.4), Span("Ask GitAway", cls="sr-only"), href=day_url(day), cls="btn btn-sm tp-edit ak-open ak-open-icon", id=ident, title="Ask GitAway")
    return A(icon("mic", 14, 2.4), "Ask GitAway", href=day_url(day), cls="btn btn-sm tp-edit ak-open", id=ident)


def register(app):
    from gitaway.pages import phone_tabs
    register_transcribe(app)

    def show(request, session, *, status=200, **state):
        form = getattr(request, "_form", None)         # what was dictated in another language travels with the box through every step
        state.setdefault("heard", _heard(form.get("heard")) if form is not None else [])
        request.scope["ask"] = state
        if wants_sheet(request):
            return sheet_fragment(request, session, status)
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
        planner = _for_the_planner(text, _heard(form.get("heard")))     # English for what was said in another language; the box keeps the original
        try:
            step = await run_in_threadpool(say.start, session, planner, day)   # the model takes seconds: never on the event loop (context variables travel along)
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
            if wants_sheet(request):
                return JSONResponse({"ok": True, "day": min(done["days"]), "ids": [], "toast": _toast([], done["count"], plan=True)})
            return RedirectResponse(f"{day_url(min(done['days']))}&done={done['count']}&kind=plan&steps={done['steps']}&merged={done['merged']}", status_code=303)
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
        if wants_sheet(request):
            return JSONResponse({"ok": True, "day": day, "ids": done["ids"], "toast": _toast(done["kinds"], done["count"])})
        return RedirectResponse(f"{day_url(day)}&done={done['count']}", status_code=303)


def _guard(session):
    from gitaway import phone
    return phone.guard(session, "/trip/ask")


# ---- voice typing where the phone has no speech recognition (F-102) ------------------------------------------------------

TRANSCRIBE_PATH = "/trip/ask/transcribe"
NO_VOICE = "Voice typing isn't set up yet — tap the microphone on your keyboard to dictate."
OVERHEAD = 100_000   # the form's own fields around the recording


class UploadLimit:
    """Refuse an oversized recording from its Content-Length, before a byte of the body is read or parsed."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"] == TRANSCRIBE_PATH:
            headers = dict(scope["headers"])
            try:
                size = int(headers.get(b"content-length") or 0)
            except ValueError:
                size = 0
            if b"content-length" not in headers:
                await PlainTextResponse("Send the recording with its length.", status_code=411)(scope, receive, send)
                return
            if size > voicenotes.MAX_BYTES + OVERHEAD:
                await PlainTextResponse(f"That recording is too large (at most {voicenotes.MAX_BYTES // (1024 * 1024)} MB).", status_code=413)(scope, receive, send)
                return
        await self.app(scope, receive, send)


# ---- where the microphone path stops (F-104) -----------------------------------------------------------------------------------

import logging
import time
from collections import defaultdict, deque

LOG = logging.getLogger("gitaway.ask")
MIC_STAGES = ("tap", "mode", "gum", "recorder", "piece", "result", "speech")
MIC_RATE = (60, 60.0)            # at most 60 events per person per minute
MIC_MAX_BODY = 1024
_mic_hits: dict = defaultdict(deque)
_SAFE = re.compile(r"[^A-Za-z0-9 _.,:=;/+()\-]")


def _mic_clean(value, limit) -> str:
    """A short machine-made fact (an error's name, a size, a mime type): anything else becomes "?", so a log line can neither be forged nor carry words."""
    return _SAFE.sub("?", str(value if isinstance(value, (str, int, float)) else "")[:limit])


def mic_allowed(who, now=None) -> bool:
    now = time.monotonic() if now is None else now
    hits = _mic_hits[who]
    while hits and now - hits[0] > MIC_RATE[1]:
        hits.popleft()
    if len(hits) >= MIC_RATE[0]:
        return False
    hits.append(now)
    return True


PIECE_SECONDS = 25          # the page rotates its recorder this often (data-piece-secs on the mic)
PIECE_MAX_SECONDS = 30      # Sarvam's speech-to-text refuses audio over 30 s ("use the batch API")
MIMES = {"mp4": "audio/mp4", "webm": "audio/webm", "ogg": "audio/ogg"}


def register_transcribe(app):
    app.add_middleware(UploadLimit)

    @app.post("/trip/ask/mic-event")
    async def mic_event(request, session):
        """One step of the Ask microphone, from the page: {stage, name, detail} (short facts such as an error's name or a recording's size; no audio, no words). Editors only (the
        access gate, like every Ask write). Logged as one line by "gitaway.ask" so `railway logs` shows where voice stops on a phone; never stored. 204; 429 past 60 a minute."""
        who = ses.current_traveler(session)
        if who is None:
            return PlainTextResponse("Sign in first.", status_code=401)
        try:
            size = int(request.headers.get("content-length") or 0)
        except ValueError:
            size = 0
        if size > MIC_MAX_BODY:
            return PlainTextResponse("Too large.", status_code=413)
        if not mic_allowed(who.id):
            return PlainTextResponse("Slow down.", status_code=429)
        try:
            data = json.loads((await request.body())[:MIC_MAX_BODY])
        except ValueError:
            return PlainTextResponse("Not understood.", status_code=400)
        if not isinstance(data, dict) or data.get("stage") not in MIC_STAGES:
            return PlainTextResponse("Not understood.", status_code=400)
        LOG.info("ask mic stage=%s name=%s detail=%s", data["stage"], _mic_clean(data.get("name"), 40), _mic_clean(data.get("detail"), 120))
        return Response(status_code=204)

    @app.post(TRANSCRIBE_PATH)
    async def transcribe(request, session):
        """A recording from the Ask box's microphone -> {"text"}. Editors only (gitaway.access). The audio is only ever the request's own upload (over 1 MB the server spools it to a temp file that is deleted when the request ends); GitAway never writes it to the data folder."""
        if ses.current_traveler(session) is None:
            return PlainTextResponse("Sign in first.", status_code=401)
        if not ai.configured("transcribe"):
            return PlainTextResponse(NO_VOICE, status_code=503)
        form = await request.form()
        f = form.get("audio")
        if not hasattr(f, "read"):
            return PlainTextResponse("Record something first.", status_code=400)
        data = await f.read(voicenotes.MAX_BYTES + 1)
        try:
            kind, secs = voicenotes.check(data, form.get("secs"))
        except voicenotes.VoiceError as e:
            return PlainTextResponse(str(e).replace("Voice notes", "Recordings").replace("voice note", "recording"), status_code=e.status)
        if secs > PIECE_MAX_SECONDS:       # the page sends a long recording in pieces of about 25 s; the speech service takes 30 s at most per call
            return PlainTextResponse(f"The voice service takes {PIECE_MAX_SECONDS} seconds at a time. Update the page and record again.", status_code=413)
        lang = form.get("lang") or ""
        lang = lang if re.fullmatch(r"[a-z]{2,3}(-[A-Za-z]{2,4})?", lang) else None      # an optional hint; anything else is ignored and the service detects the language
        try:
            words = await run_in_threadpool(lambda: ai.transcribe((session or {}).get("tenant_id", ""), data, f"voice.{voicenotes.TYPES[kind][0]}", MIMES[kind], language=lang))
        except ai.AIError as e:
            return PlainTextResponse(str(e), status_code=503)
        english = ""
        if words.language and not words.language.lower().startswith("en"):      # said in Hindi, Tamil...: the planner also gets it in English; the person keeps what they said
            try:
                english = str(await run_in_threadpool(lambda: ai.transcribe((session or {}).get("tenant_id", ""), data, f"voice.{voicenotes.TYPES[kind][0]}", MIMES[kind], english=True)))
            except ai.AIError:
                english = ""     # not fatal: the planner is told to write titles in English whatever the language
        return JSONResponse({"text": words[: say.LIMIT], "language": words.language, "english": english[: say.LIMIT]})
