"""One booking of the open trip, on a page of its own (F-254, D-754): the place a locked block on the planning calendar opens to. It is what the old canvas's booking sheet (F-093) was, now over the
v2 sky: a flight's route, times and every traveller's boarding pass, a stay's address, times and front desk, the rental car's counter, a tour's start; the confirmation behind a tap, Directions,
the phone fix, and where it was booked with "Change or cancel" (the pieces are gitaway/pages/booked.py, tab_help.py, passes.py and bookedwhere.py).

GET /trip/booking?block=<block id>[&err=]   the booking behind a calendar block (planv2's `href`); a block that is not a booking goes back to the plan
GET /trip/booking?sos=1                     "Who to call": 911, tonight's front desk, the rental counter, the family's numbers

The forms inside return here (`back`); removing a booking goes to /trip/plan (`gone`). Every role may read; the writes are the editor's (gitaway/access.py).
"""

from urllib.parse import quote

from fasthtml.common import A, Div, H1, Link, Main, Span
from starlette.responses import RedirectResponse

from gitaway import access, phone, session as ses, tripcal as cal
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import booked

PATH = "/trip/booking"
PLAN = "/trip/plan"
HEAD = (Link(rel="stylesheet", href="/assets/css/trip.css"), Link(rel="stylesheet", href="/assets/css/help.css"), Link(rel="stylesheet", href="/assets/css/passes.css"), Link(rel="stylesheet", href="/assets/css/booking.css"))


def href(block="", sos=False) -> str:
    """The address of one booking (or of "Who to call"), as the calendar links to it."""
    return f"{PATH}?block={quote(block, safe='')}" if block else f"{PATH}?sos=1" if sos else PATH


def _view(session):
    """What gitaway.pages.booked reads: the session, the booking, the trip and the person's role."""
    b = ses.booking(session)
    return dict(session=session, b=b, t=cal.trip("", b), role=access.request_role())


def _page(title, pills, body, session):
    return page(title, Main(Div(A(icon("chev-left", 16, 2.6), "Back to the plan", href=PLAN, cls="bk-back", id="bk-back"),
                                Div(*[Span(x, cls="bk-pill") for x in pills], cls="bk-pills") if pills else "", H1(title, id="bk-title"), *body, cls="bk-page v2-glass", id="bk-page"), cls="bk-wrap"),
                current="trip", head=HEAD, noindex=True, footer=False, v2=True, quiet=True)


def register(app):
    @app.get(PATH)
    def booking(request, session, block: str = "", sos: str = "", err: str = ""):
        if (r := phone.guard(session, href(block, sos == "1"))):
            return r
        v, ua = _view(session), request.headers.get("user-agent", "")
        if sos == "1":
            return _page("Who to call", ["Emergency"], [booked.problem(err), *booked.sos(v, ua, href(sos=True))], session)
        found = booked.find(v, block)
        if found is None:
            return RedirectResponse(PLAN, status_code=303)
        pills, title, body = booked.sheet(v, found, ua, href(block), PLAN)
        return _page(title, pills, [booked.problem(err), *body], session)
