"""The Family chats in the desktop panel (F-143, frame A3 of docs/design/canvas/Web-Trip-v1.html; docs/trip-canvas.md "Family chat in the panel").

`pane(session, day, key)` draws the Family mode of the day's docked panel (gitaway/pages/daydock.py): the trip's chats as rows (the whole trip first, then each plan's and part's, with
unread counts), a link to "People and invites" (/family), the open chat below and, fixed at the panel's foot, its message bar. The chat is the Family tab's own markup
(`tab_family.fragment`) and the phone's own script (`thread.js`), so sending, retrying, the live poll and the order of messages are the phone's; nothing is forked.
The chats are named by keys (gitaway/familychats.py): "trip", "<plan id>" or "<plan id>:<part id>".

GET /trip/family/panel?thread=KEY&day=N   the pane and its message bar as a fragment (the panel fetches it when Family opens or another chat is picked); opening a chat marks it read
GET /trip/family/list?open=KEY&day=N      just the rows (the panel asks again while Family is open); the open chat shows no count, it is polled and read; `X-Family-Unread` has the total
"""

from datetime import timedelta

from fasthtml.common import A, Button, Div, Form, H3, Input, P, Section, Span, to_xml
from starlette.responses import Response

from gitaway import familychats as fc, familythread, plantalk, session as ses, tripcal as cal
from gitaway.icons import icon
from gitaway.pages import tab_family

POLL_MS = tab_family.POLL_MS
PAGE = familythread.PAGE
PEEK = 56      # the newest line of a chat in its row is shortened to this many characters, at a word


def _short(text) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= PEEK else text[:PEEK].rsplit(" ", 1)[0]


def _tile(act, kind):
    from gitaway.pages import daydock, tripcanvas as tc
    if not act:
        return Span(icon("users", 18, 2.2), cls="cz-fam-ic cz-fam-ic-trip", aria_hidden="true")
    tint = kind if kind in tc.KIND_TINT else "fun"
    return Span(icon(daydock.KIND_ICON.get(kind, "star"), 18, 2.2), cls=f"cz-fam-ic cz-k-{tint}", aria_hidden="true")


def rows(session, day, open_key, shown=None):
    """The chats as links to the day with that chat open. `shown`: the threads already read (so the list is not read twice)."""
    from gitaway.pages import tripcanvas as tc
    out = []
    for t in shown if shown is not None else fc.threads(session, open_key):
        on = t["key"] == open_key
        unread = 0 if on else t["unread"]
        line = f"{t['who']}: {_short(t['last'])}" if t["last"] else "Nothing said yet"
        out.append(A(_tile(t["act"], t["kind"]), Span(Span(t["title"], cls="cz-fam-tt"), Span(line, cls="cz-fam-ls"), cls="cz-fam-tx"),
                     Span(str(unread), Span(" unread", cls="sr-only"), cls="cz-fam-un") if unread else "",
                     href=tc.curl(day=day, panel="family", thread=t["key"]), cls=f"cz-fam-th{' is-on' if on else ''}", data_thread=t["key"], aria_current="true" if on else None))
    return Div(*out, cls="cz-fam-list", id="cz-fam-list", aria_label="Chats on this trip")


def unread_badge(n):
    return Span(str(n), Span(" unread", cls="sr-only"), cls="cz-dock-un", id="cz-dock-un") if n else ""


def _when(session, a):
    t = cal.trip("", ses.booking(session))
    d = t.depart + timedelta(days=a.day)
    return f"{d.strftime('%a')} {cal.fmt_time(a.start)}"


def _thread(session, key):
    """(the heading, the newest PAGE items, the live poll's address, the message form's extra fields, its action, the address of earlier ones or "" when there are none) of the chat `key`."""
    act, part = fc.split(key)
    if not act:
        its = familythread.items(session, scope="trip", limit=PAGE + 1)
        poll = "/trip/family/thread?scope=trip"
        heading, fields, action = "Whole trip", {"scope": "trip"}, "/trip/family/message"
    else:
        a, p = plantalk.target(session, act, part)
        its = plantalk.items(session, a.id, p["id"] if p else "", limit=PAGE + 1)
        poll = f"/trip/talk/items?act={a.id}" + (f"&part={p['id']}" if p else "")
        heading, fields, action = f"{plantalk.label(a, p)} · {_when(session, a)}", {"act": a.id, "part": p["id"] if p else ""}, "/trip/talk/message"
    return heading, its[-PAGE:], poll + "&read=1", fields, action, poll if len(its) > PAGE else ""


def pane(session, day, key=fc.TRIP):
    """-> (the pane, the message bar, the Family tab's count) for the chat `key` (the whole trip when `key` names nothing that is there). Drawing it writes nothing (F-177): the script
    that starts the pane on a laptop says what it showed with /trip/family/seen. The trip's messages are read once, for the rows and the count."""
    key = fc.key_of(*fc.split(key))      # anything that is not a plain key is the whole trip
    try:
        heading, its, poll, fields, action, older = _thread(session, key)
    except familythread.ThreadError:
        key = fc.TRIP
        heading, its, poll, fields, action, older = _thread(session, key)
    me, zone, trip = ses.current_traveler(session).id, ses.trip_zone(session), ses.open_trip_id() or ""
    last = its[-1]["n"] if its else 0
    chats = fc.threads(session, key)
    pane_ = Section(
        rows(session, day, key, chats),
        A(icon("users", 16, 2.4), Span("People and invites"), href="/family", cls="cz-fam-people", id="cz-fam-people"),
        H3(heading, cls="cz-dock-k cz-fam-hd", id="cz-fam-title"),
        Button("Earlier messages", type="button", id="ft-older", cls="cz-fam-older", data_older=older) if older else "",
        Div(*tab_family.fragment(its, me, zone), id="ft-thread", cls="ft-thread cz-fam-msgs", data_last=str(last), data_poll=str(POLL_MS), data_trip=trip, data_poll_url=poll,
            role="log", aria_live="polite", aria_label=f"Chat: {heading}"),
        P("Nothing said here yet. Say hello.", id="ft-empty", cls="cz-pp-none", hidden=bool(its)),
        cls="cz-dock-body cz-fam", id="ft", data_pane="family", data_key=key, data_live="", aria_labelledby="cz-fam-title")
    foot = Form(Input(type="hidden", name="trip", value=trip), *[Input(type="hidden", name=k, value=v) for k, v in fields.items()],
                Input(type="text", name="text", id="ft-text", maxlength=str(familythread.MAX_MESSAGE), placeholder="Message the family", autocomplete="off", aria_label=f"Message: {heading}", cls="cz-pp-text", required=True),
                Button(icon("arrow-right", 16, 2.6), Span("Send", cls="sr-only"), type="submit", id="ft-send", cls="cz-compose-go cz-pp-send"),
                P("", id="ft-error", cls="cz-error", role="alert", hidden=True), action=action, method="post", cls="cz-fam-foot", id="ft-compose", data_pane="family-foot", data_live="")
    return pane_, foot, fc.unread_in(chats, key)


def _day(day):
    return int(day) if isinstance(day, str) and day.isdigit() and len(day) <= 3 else 0


def register(app):
    @app.get("/trip/family/panel")
    def panel(session, thread: str = "trip", day: str = "0"):
        if not ses.current_traveler(session):
            return Response(status_code=401)
        pane_, foot, unread = pane(session, _day(day), thread[:60])
        return Response(to_xml(pane_) + to_xml(foot), media_type="text/html; charset=utf-8", headers={"X-Family-Unread": str(unread), "Cache-Control": "no-store"})

    @app.post("/trip/family/seen")
    def seen(session, key: str = "*", upto: int = 0):
        """I have read the chat `key` ("*": all of them, as the phone's Family page shows them) up to item `upto`, or up to now."""
        if not ses.current_traveler(session):
            return Response("Sign in first.", status_code=401)
        fc.mark_read(session, key[:60], upto or fc.newest(session))
        return Response(status_code=204)

    @app.get("/trip/family/list")
    def listing(session, open: str = "trip", day: str = "0"):      # noqa: A002 - the address says what it means
        if not ses.current_traveler(session):
            return Response(status_code=401)
        chats = fc.threads(session, open[:60])
        total = fc.unread_in(chats, open)
        return Response(to_xml(rows(session, _day(day), open[:60], chats)), media_type="text/html; charset=utf-8", headers={"X-Family-Unread": str(total), "Cache-Control": "no-store"})
