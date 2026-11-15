"""Where you sleep tonight, the rental car, 911 and the family's own phone numbers: the pieces of a booking's page and of "Who to call" (gitaway/pages/booking.py, booked.py). It was the Help tab (F-069);
the tab itself retired in F-254.

POST /trip/help/phone     (editor) add or fix a hotel's or the rental car's phone number: kind=hotel|car, index, phone, trip

Plain links and forms. A call button is a `tel:` link with the digits only (gitaway.phones.tel). The confirmation number sits behind a tap. Viewers see no edit forms (gitaway.access gates the POST).
"""

from fasthtml.common import A, Button, Details, Div, Form, H2, Input, Label, Link, P, Span, Summary
from starlette.responses import RedirectResponse

from gitaway import access, catalog, members, phones, pickers, session as ses, tripcal as cal, tripday as td, tripimport as ti
from gitaway.icons import icon
from gitaway.pages import passes as passes_ui

TITLE = "Help"
TWO = "Who to call."
HEAD = (*pickers.HEAD, Link(rel="stylesheet", href="/assets/css/help.css"), *passes_ui.HEAD)   # pickers: the flight form has date and time fields (F-083)


def _call(number, label, cls="tp-btn tp-btn-coral"):
    n = phones.tel(number)
    return A(icon("phone", 18, 2.4), label, href=f"tel:{n}", cls=cls) if n else ""


def _fix(kind, index, number, what, back=""):
    """Add or fix a number right here (editors only): a small form that posts to /trip/help/phone. `back`: a booking's address to return to (F-093, F-254), else "Who to call"."""
    return Details(Summary(icon("pencil", 15, 2.4), f"{'Fix' if number else 'Add'} the {what} number", cls="tp-mini hp-fix-sum"),
                   Form(Label(Span(f"The {what} phone number", cls="hp-lab"), Input(type="tel", name="phone", value=number, maxlength=str(phones.MAX_PHONE), autocomplete="off", placeholder="+1 310 555 0100")),
                        Input(type="hidden", name="kind", value=kind), Input(type="hidden", name="index", value=str(index)), Input(type="hidden", name="trip", value=ses.open_trip_id()),
                        Input(type="hidden", name="next", value=back) if back else "",
                        Div(A("Cancel", href=back or "/trip/booking?sos=1", cls="tp-btn tp-btn-plain"), Button("Save the number", type="submit", cls="tp-btn tp-btn-ink"), cls="hp-fix-acts"),
                        action="/trip/help/phone", method="post", cls="hp-fix-form"),
                   cls="hp-fix", data_fix=f"{kind}{index}")


def _confirm(code):
    if not code or code == "none given":
        return ""
    return Details(Summary(icon("key", 18, 2.2), "Confirmation", Span("••••••", cls="hp-dots", aria_hidden="true"), cls="hp-conf-sum"),
                   Span("Confirmation number", cls="tp-sub"), Span(code, cls="tp-conf-num"), cls="hp-conf", data_confirm="hotel")


def hotel_parts(h, index, ua, can_edit, back=""):
    """What Help shows for a stay below its name: check in and out, the confirmation behind a tap, Front desk and Directions, the phone fix. The canvas's booking sheet (F-093) draws the same."""
    place = f"{h.name}, {h.address}" if h.address else h.name
    return [Div(Div(Span("CHECK IN", cls="hp-k"), Span(ti.when_text(h.check_in), cls="hp-v"), id="hp-in"), Div(Span("CHECK OUT", cls="hp-k"), Span(ti.when_text(h.check_out), cls="hp-v"), id="hp-out"), cls="hp-times"),
            _confirm(h.confirmation),
            Div(_call(h.phone, "Front desk") or Span("No phone number yet", cls="hp-none", id="hp-hotel-none"),
                A(icon("nav", 18, 2.4), "Directions", href=td.maps_url(place, ua), cls="tp-btn tp-btn-white", id="hp-directions"), cls="hp-acts"),
            _fix("hotel", index, h.phone, "hotel", back) if can_edit else ""]


def car_parts(c, ua, can_edit, back="", place=""):
    """What Help shows for the rental car below its name: Call the counter, and (F-093, in the booking sheet) Directions to the counter or the drop-off place, and the phone fix."""
    where = place or c.pickup_place
    return [Div(_call(c.phone, "Rental counter") or Span("No phone number yet", cls="hp-none", id="hp-car-none"),
                A(icon("nav", 18, 2.4), "Directions", href=td.maps_url(f"{c.company}, {where}", ua), cls="tp-btn tp-btn-white", id="hp-car-directions") if ua is not None else "", cls="hp-acts"),
            _fix("car", 0, c.phone, "rental counter", back) if can_edit else ""]


def _family(session):
    tid = session.get("tenant_id")
    numbers = phones.member_phones(session)
    me = session.get("user_id")
    people = [(m, numbers.get(m["user_id"], "")) for m in members.members(tid)]
    with_phone = [(m, n) for m, n in people if phones.tel(n)]
    mine = numbers.get(me, "")
    lines = [A(Span(m["initials"], cls=f"hp-av fill-{m['color']}"), Span(f"{m['name']}{' (you)' if m['user_id'] == me else ''}", cls="hp-cn"), Span(n, cls="hp-cs"), href=f"tel:{phones.tel(n)}", cls="hp-contact", data_member=m["user_id"])
             for m, n in with_phone]
    return lines, bool(phones.tel(mine))


def register(app):
    @app.post("/trip/help/phone")
    def fix_phone(session, kind: str = "", index: str = "0", phone: str = "", next: str = ""):
        try:
            phones.set_stay_phone(session, kind, index, phone)
        except phones.PhoneError as e:
            back = passes_ui.safe_back(next)
            return RedirectResponse(f"{back}{'&' if '?' in back else '?'}err=phone" if back else "/trip/booking?sos=1&err=phone", status_code=303)
        return RedirectResponse(passes_ui.safe_back(next) or "/trip/booking?sos=1", status_code=303)
