"""Tap a plan: its note, right there (F-106, F-107). On the day grid a tap on a block opens a card over the day (assets/js/day_card.js); this module draws what is in it
and takes its one write. The card holds the title and time, the notes and two links; the chat is not in it (the captain: "No message needed inside block"), "Open chat" leads to it.

GET  /trip/canvas/card?act=aN[&trip=]   the card's body as a fragment: the links "Open chat" (with how much was said, "Open chat · 3") and, on a park block, "Rides", then the plan's note(s) as the sticky
                                        (an editor edits a note of their own in place, or adds one)
POST /trip/canvas/actnote               a note on a plan: fields act (required), text, and note (the id of the person's own note to change; none adds one, with `id` the calendar's next number as the page was given it, so a retry adds nothing twice). JSON {note: {id, text}}, or 422 {error}

The note is a row of the calendar's notes (gitaway/tripcal.py): the write is `cal.add_note` or `cal.edit_note`, so a viewer (no editor role) is refused by gitaway.access.
"""

from fasthtml.common import A, Button, Div, Span
from starlette.responses import PlainTextResponse, Response

from gitaway import access, familythread, members, plantalk, session as ses, tripcal as cal
from gitaway.icons import icon
from gitaway.pages import calendar as calui, tripcanvas as tc

def plan_notes(session, act):
    """[(Note, name to show or "" for the person's own)] of a plan, oldest first."""
    who = ses.current_traveler(session)
    people = {f.name.casefold(): f for f in ses.friends(session)}
    family = members.family_people(session)
    out = []
    for n in cal.notes(session):
        if n.act == act:
            name = calui.note_writer(n, who, people, family)[0]
            out.append((n, "" if name == "You" else name))
    return out


def _is_mine(session, n):
    me = ses.current_traveler(session)
    return bool(me) and not n.by and n.by_id == me.id


def notes_view(session, act, editor):
    """The sticky: each note in full on its yellow paper. An editor's own note is a button (a tap edits it in place); a note someone else wrote is plain. An editor always has "Add a note"
    (the empty sticky when there is no note yet, a quiet line when there is one). A viewer with no note to read gets nothing."""
    stickers = []
    for n, by in plan_notes(session, act):
        mine = editor and _is_mine(session, n)
        attrs = {"data_mine": "1", "role": "button", "tabindex": "0", "aria_label": f"Edit this note: {n.text}"} if mine else {}
        stickers.append(Div(Span(n.text, cls="cz-card-text"), Span(by, cls="cz-card-by") if by else "", cls="cz-card-note" + (" is-mine" if mine else ""), data_note=n.id, **attrs))
    if editor:
        empty = not stickers
        stickers.append(Button(icon("plus", 16, 2.6), Span("Add a note"), type="button", cls="cz-card-note cz-card-add" + (" is-empty" if empty else ""), data_add="1"))
    return Div(*stickers, cls="cz-card-notes", aria_label="Notes", **({"data_next": cal.next_id(session)} if editor else {})) if stickers else ""


def links_view(v, a, trip):
    """"Open chat" (the full chat page) and, on a park block, "Open plan" (the block level: what a tap on a park block used to do)."""
    said = sum(m["n"] for key, m in v["talk"].items() if key[0] == a.id)
    out = [A(icon("chat", 16, 2.4), Span(f"Open chat · {said}" if said else "Open chat"), href=plantalk.url(a.id, "", trip), cls="cz-card-link", id="cz-card-chat")]
    if tc.has_block(v, a.id):       # F-119: "Rides" read as Uber rides; this is the plan's steps, so it says so and shows how far along
        n, done = tc._counts(v["plan"][a.id])
        out.insert(0, A(icon("clipboard", 16, 2.4), Span(f"Open plan · {done} of {n} done" if n else "Open plan"), href=tc.curl(block=a.id), cls="cz-card-link", id="cz-card-rides", data_zoom="in", data_zk=f"blk-{a.id}"))
    return Div(*out, cls="cz-card-links")


def card_body(session, act, trip=""):
    """The card's body for plan `act` as an element, or None when the plan is not on this trip. Raises familythread.StaleTrip for another trip's page."""
    v = tc.load(session)
    a = v["by_id"].get(act)
    if a is None:
        return None
    open_trip = ses.open_trip_id()
    if trip and trip != open_trip:
        raise familythread.StaleTrip(plantalk.STALE)
    editor = access.can_edit(v["role"])
    return Div(links_view(v, a, open_trip), notes_view(session, a.id, editor), cls="cz-card-inner", data_act=a.id)


def register(app):
    @app.get("/trip/canvas/card")
    def card(session, act: str = "", trip: str = ""):
        if (r := tc._guard(session)):
            return r
        try:
            body = card_body(session, act[:20], trip[:40])
        except familythread.StaleTrip:
            return PlainTextResponse(plantalk.STALE, status_code=409)
        if body is None:
            return Response("not found", status_code=404, media_type="text/plain")
        return tc.fragment(body)

    @app.post("/trip/canvas/actnote")
    async def actnote(request, session):
        if (r := tc._guard(session)):
            return r
        form = await request.form()
        act, note_id, text = tc._field(form, "act", 20), tc._field(form, "note", 12), str(form.get("text") or "")[:cal.MAX_NOTE * 3]
        if not act:
            return tc._json({"error": "Pick a plan to write the note on."}, 422)
        try:
            n = cal.edit_note(session, note_id, text) if note_id else cal.add_note(session, text, act=act, id=tc._field(form, "id", 12) or None)      # the card's own id: a retry after a lost reply adds nothing twice
        except cal.CalendarError as e:
            return tc._json({"error": str(e)}, 422)
        got = {"note": {"id": n.id, "text": n.text}}
        return tc._reply(request, session, got, tc.safe_next(form.get("next"))) if form.get("next") else tc._json(got)      # F-124: with the day drawn after it
