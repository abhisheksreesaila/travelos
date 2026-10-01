"""Talk to plan (F-024): the mic, the voice panel and the apply/undo routes of the trip calendar.

GET  /calendar?voice=1[&night=<day>][&hear=1]   the panel beside the calendar. hear=1 means the mic was just tapped, so voice.js
                                                 plays the scripted sentence word by word; night=<day index> answers the one question.
                                                 Everything else is rendered by the server: the plans, where they land, the clashes.
POST /calendar/voice/apply                       add the ticked plans and a trip note, then redirect to the calendar (?voiced=...)
POST /calendar/voice/undo                        take that apply back out (only what it added)

The script lives in gitaway.voice and the placement rules in gitaway.tripcal (the same ones forks use). Nothing is captured
from the microphone: this page never asks the browser for audio.
"""

import re
from urllib.parse import quote, urlencode

from fasthtml.common import A, Aside, Button, Div, Form, H2, H3, Input, Label, P, Span
from starlette.responses import RedirectResponse

from gitaway import session as ses, tripcal as cal, voice as vo
from gitaway.icons import icon

_KEY = re.compile(r"^v\d$")
_IDS = re.compile(r"^a\d{1,4}$")
_NOTE = re.compile(r"^n\d{1,4}$")
_NIGHT = re.compile(r"^\d{1,3}$")


def voice_url(demo="", **q):
    """The calendar URL with the voice panel open (always the day-by-day view: the drafts need the grid)."""
    params = ([("demo", cal.LONG)] if demo == cal.LONG else []) + [("view", "days"), ("voice", "1")] + [(k, v) for k, v in q.items() if v not in ("", None)]
    return "/calendar?" + urlencode(params)


def parse_night(text):
    """The answer in a URL or form as a day index, or None when it is not a number."""
    return int(text) if _NIGHT.match(text or "") else None


def note_id(text):
    """`text` when it is a note id like "n5", else ""."""
    return text if _NOTE.match(text or "") else ""


def parse_ids(text):
    return [x for x in (text or "").split(",") if _IDS.match(x)][:40]


def _hidden(name, value):
    return Input(type="hidden", name=name, value=value)


# ---- the panel -----------------------------------------------------------------------------------------------------

def _row(x, dates, info):
    p = x.plan
    day = dates[p.day] if 0 <= p.day < len(dates) else None
    when = (f"{day.strftime('%a')} {day.day} · " if day else f"Day {p.day + 1} · ") + f"{cal.fmt_time(p.start)} – {cal.fmt_time(p.end)}"
    if x.state == "have":
        note = Span("Already on your calendar", cls="vo-note vo-note-have")
    elif x.clash:
        note = Span(x.clash[0].upper() + x.clash[1:], cls="vo-note")
    else:
        note = ""
    if info.get(p.key) and x.state != "have":
        extra = Span(info[p.key], cls="vo-note vo-note-info")
        note = Div(note, extra, cls="vo-notes") if note else extra
    off = x.hard or x.state == "have"
    return Label(
        Input(type="checkbox", name="pick", value=p.key, checked=x.checked or None, disabled=off or None, data_plan=p.key, cls="vo-check"),
        Span(Span(p.title, cls="vo-ptitle"), Span(when, cls="vo-when"), note, cls="vo-ptext"),
        cls=f"vo-row{' is-clash' if x.state == 'clash' else ''}{' is-have' if x.state == 'have' else ''}")


def _waiting(question):
    return Div(Span(icon("mic", 18, 2.4), cls="vo-wait-icon"),
               Span(Span("Tacos at Mariscos La Ola", cls="vo-ptitle"), Span("Waiting for your answer", cls="vo-when"), cls="vo-ptext"), cls="vo-row is-wait")


def panel(session, demo, dates, question, placements, night, hear, error=""):
    """The Talk to plan card. `night` is the answered day index (None while the question is open)."""
    answered = night is not None
    ticked = sum(1 for x in placements if x.checked)
    close = f"/calendar?{urlencode(([('demo', cal.LONG)] if demo == cal.LONG else []) + [('view', 'days')])}"
    hint = "Listening… say what you want to do" if hear else "Uncheck anything you don’t want" if answered else "Got it. One quick question"
    text = vo.sentence(bool(vo.setup(session, demo)[1]))
    said = [Span(w + " ", cls="vo-w") for w in text.split()]
    chips = [A(o.label, href=voice_url(demo, night=o.day), data_soft="", cls="vo-chip", aria_current="true" if o.day == night else None,
               aria_label=f"{question.text} {o.label}" + (", picked" if o.day == night else "")) for o in question.options]
    info = vo.fallback_notes(dates)
    rows = [_row(x, dates, info) for x in placements]
    if not answered:
        rows.insert(0, _waiting(question))
    label = f"Add {ticked} plan{'s' if ticked != 1 else ''}" if answered else "Answer the question first"
    after = Div(
        Div(H3(question.text, id="vo-q"), Div(*chips, cls="vo-chips", role="group", aria_labelledby="vo-q"), cls=f"vo-ask{' is-done' if answered else ''}"),
        Form(
            Span("I’LL ADD THESE", cls="vo-from"),
            Div(*rows, cls="vo-rows", role="group", aria_label="Plans to add", tabindex="0"),
            _hidden("night", str(night)) if answered else "", _hidden("demo", cal.LONG) if demo == cal.LONG else "",
            Button(label, type="submit", id="vo-apply", cls="btn btn-ink vo-applybtn", disabled=(ticked == 0 or not answered) or None,
                   data_locked="1" if not answered else None),
            Span("Your bookings and your crew’s plans stay exactly where they are.", cls="vo-hint"),
            action="/calendar/voice/apply", method="post", id="vo-form", cls="vo-preview"),
        cls="vo-after")
    return Aside(
        Div(H2("Talk to plan", id="vo-title"), Span("Demo voice", cls="vo-pill"), A(icon("x", 16, 2.6), href=close, data_soft="", cls="vo-close", aria_label="Close Talk to plan"), cls="vo-head"),
        Div(Div(error, role="alert", cls="vo-error") if error else "",
            Div(Form(_hidden("view", "days"), _hidden("voice", "1"), _hidden("hear", "1"), _hidden("demo", cal.LONG) if demo == cal.LONG else "",
                  Button(icon("mic", 36, 2.2), type="submit", cls="vo-mic", id="vo-mic", aria_label="Listening" if hear else "Play the demo sentence again"),
                  action="/calendar", method="get", cls="vo-micform"),
                Div(*[Span(cls="vo-bar", style=f"animation-delay:{d}s") for d in (0, .1, .2, .3, .2, .1, 0)], cls="vo-bars", aria_hidden="true"),
                Span(hint, cls="vo-hintline", id="vo-hintline"), cls="vo-micbox"),
            Div(cls="sr-only vo-live", id="vo-live", role="status", aria_live="polite"),
            Div(Span("You said: ", cls="sr-only"), Span(text, cls="sr-only vo-full"),
                P(*said, Span("|", cls="vo-cursor"), cls="vo-said", aria_hidden="true"), cls="vo-bubble"),
            after, cls="vo-scroll"),
        id="cal-voice", cls="cal-voice vo-panel", aria_labelledby="vo-title", data_hear="1" if hear else None)


# ---- routes --------------------------------------------------------------------------------------------------------

def register(app):
    def calendar_page(*a, **kw):
        from gitaway.pages.calendar import calendar_page as page  # imported late: calendar.py imports this module for the panel
        return page(*a, **kw)

    def guard(session, demo):
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={quote(voice_url(demo), safe='')}", status_code=303)
        if not ses.booking(session):
            return RedirectResponse("/calendar", status_code=303)
        return None

    @app.post("/calendar/voice/apply")
    def voice_apply(session, night: str = "", pick: list[str] = None, demo: str = ""):
        demo = cal.LONG if demo == cal.LONG else ""
        if (r := guard(session, demo)):
            return r
        n = parse_night(night)
        dates, _ = vo.setup(session, demo)
        if vo.question(dates).option(n) is None:
            return calendar_page(session, demo, "days", voice={"night": None, "error": "Pick a night for the tacos first."}, status=409)
        try:
            added, note = vo.apply(session, n, [k for k in (pick or []) if _KEY.match(k)], demo)
        except cal.CalendarError as e:
            return calendar_page(session, demo, "days", voice={"night": n, "error": str(e)}, status=409)
        if not added:
            return RedirectResponse(voice_url(demo, night=n), status_code=303)
        q = [("demo", cal.LONG)] if demo == cal.LONG else []
        q += [("view", "days"), ("voiced", ",".join(a.id for a in added)), ("vnote", note.id if note else ""), ("vn", str(n))]
        return RedirectResponse("/calendar?" + urlencode([(k, v) for k, v in q if v], safe=","), status_code=303)

    @app.post("/calendar/voice/undo")
    def voice_undo(session, ids: str = "", night: str = "", nid: str = "", demo: str = ""):
        demo = cal.LONG if demo == cal.LONG else ""
        if (r := guard(session, demo)):
            return r
        n = parse_night(night)
        dates, _ = vo.setup(session, demo)
        if vo.question(dates).option(n) is not None:
            vo.undo(session, n, parse_ids(ids), note_id(nid) or None, demo)
        return RedirectResponse("/calendar?" + urlencode(([("demo", cal.LONG)] if demo == cal.LONG else []) + [("view", "days")]), status_code=303)
