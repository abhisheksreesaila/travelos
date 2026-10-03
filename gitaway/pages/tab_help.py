"""The Help tab (phone shell, F-067; built in F-069): where you sleep tonight, the rental car, 911 and the family's own phone numbers.

GET  /trip/help           the tab (the route and the shell are gitaway/pages/phone_tabs.py; this module is its `content`)
POST /trip/help/phone     (editor) add or fix a hotel's or the rental car's phone number: kind=hotel|car, index, phone, trip

Everything is drawn by the server and is plain links and forms, so the page works from the service worker's saved copy with no
connection (assets/sw.js keeps a signed-in person's pages per person). A call button is a `tel:` link with the digits only
(gitaway.phones.tel). The confirmation number sits behind a tap, like on Today. Viewers see no edit forms (gitaway.access gates the POST).
"""

from fasthtml.common import A, Button, Details, Div, Form, H2, Input, Label, Link, P, Span, Summary
from starlette.responses import RedirectResponse

from gitaway import access, catalog, members, phones, session as ses, tripcal as cal, tripday as td, tripimport as ti
from gitaway.icons import icon

TITLE = "Help"
HEAD = (Link(rel="stylesheet", href="/assets/css/help.css"),)


def _call(number, label, cls="tp-btn tp-btn-coral"):
    n = phones.tel(number)
    return A(icon("phone", 18, 2.4), label, href=f"tel:{n}", cls=cls) if n else ""


def _fix(kind, index, number, what):
    """Add or fix a number right here (editors only): a small form that posts to /trip/help/phone."""
    return Details(Summary(icon("pencil", 15, 2.4), f"{'Fix' if number else 'Add'} the {what} number", cls="tp-mini hp-fix-sum"),
                   Form(Label(Span(f"The {what} phone number", cls="hp-lab"), Input(type="tel", name="phone", value=number, maxlength=str(phones.MAX_PHONE), autocomplete="off", placeholder="+1 310 555 0100")),
                        Input(type="hidden", name="kind", value=kind), Input(type="hidden", name="index", value=str(index)), Input(type="hidden", name="trip", value=ses.open_trip_id()),
                        Div(A("Cancel", href="/trip/help", cls="tp-btn tp-btn-plain"), Button("Save the number", type="submit", cls="tp-btn tp-btn-ink"), cls="hp-fix-acts"),
                        action="/trip/help/phone", method="post", cls="hp-fix-form"),
                   cls="hp-fix", data_fix=f"{kind}{index}")


def _confirm(code):
    if not code or code == "none given":
        return ""
    return Details(Summary(icon("key", 18, 2.2), "Confirmation", Span("••••••", cls="hp-dots", aria_hidden="true"), cls="hp-conf-sum"),
                   Span("Confirmation number", cls="tp-sub"), Span(code, cls="tp-conf-num"), cls="hp-conf", data_confirm="hotel")


def _hotel_card(h, index, plan, ua, can_edit):
    place = f"{h.name}, {h.address}" if h.address else h.name
    return Div(
        Div(Span(icon("hotel", 24, 2.2), cls="hp-ico hp-sky"), Div(H2(h.name, cls="hp-h"), Span(h.address, cls="hp-addr") if h.address else "", cls="hp-who"), cls="hp-row"),
        Div(Div(Span("CHECK IN", cls="hp-k"), Span(ti.when_text(h.check_in), cls="hp-v"), id="hp-in"), Div(Span("CHECK OUT", cls="hp-k"), Span(ti.when_text(h.check_out), cls="hp-v"), id="hp-out"), cls="hp-times"),
        _confirm(h.confirmation),
        Div(_call(h.phone, "Call the front desk") or Span("No phone number yet", cls="hp-none", id="hp-hotel-none"),
            A(icon("nav", 18, 2.4), "Directions", href=td.maps_url(place, ua), cls="tp-btn tp-btn-white", id="hp-directions"), cls="hp-acts"),
        _fix("hotel", index, h.phone, "hotel") if can_edit else "",
        cls="hp-card", id="hp-hotel")


def _demo_hotel_card(stay, destination, ua):
    return Div(Div(Span(icon("hotel", 24, 2.2), cls="hp-ico hp-sky"), Div(H2(stay.name, cls="hp-h"), Span(stay.headline, cls="hp-addr"), cls="hp-who"), cls="hp-row"),
               Div(A(icon("nav", 18, 2.4), "Directions", href=td.maps_url(f"{stay.name}, {destination}", ua), cls="tp-btn tp-btn-white", id="hp-directions"), cls="hp-acts"),
               cls="hp-card", id="hp-hotel")


def _car_card(c, can_edit):
    return Div(
        Div(Span(icon("car", 24, 2.2), cls="hp-ico hp-sun"), Div(H2(f"{c.company} rental car", cls="hp-h"), Span(f"Counter: {c.pickup_place}", cls="hp-addr", id="hp-counter"), cls="hp-who"), cls="hp-row"),
        Div(_call(c.phone, "Call the counter") or Span("No phone number yet", cls="hp-none", id="hp-car-none"), cls="hp-acts"),
        _fix("car", 0, c.phone, "rental counter") if can_edit else "",
        cls="hp-card", id="hp-car")


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


def content(request, session):
    b = ses.booking(session)
    zone = ses.trip_zone(session)
    t = cal.trip("", b)
    ua = request.headers.get("user-agent", "")
    can_edit = access.can_edit(access.request_role())
    today = catalog.today_in(zone)
    plan = cal.plan_of(b) if cal.is_imported(b) else None
    cards = []
    if plan and plan.hotels:
        i = phones.tonight(plan.hotels, today)
        cards.append(_hotel_card(plan.hotels[i], i, plan, ua, can_edit))
    elif not plan and (stay := cal.stay_of(b)):
        cards.append(_demo_hotel_card(stay, t.destination_name, ua))
    else:
        cards.append(Div(P("No hotel on this trip yet.", cls="hp-empty"), cls="hp-card", id="hp-hotel"))
    if plan and plan.rental:
        cards.append(_car_card(plan.rental, can_edit))
    contacts, has_mine = _family(session)
    people = [*contacts]
    if plan and plan.rental and phones.tel(plan.rental.phone):
        people.append(A(Span(icon("car", 16, 2.4), cls="hp-av fill-sky"), Span(f"{plan.rental.company}", cls="hp-cn"), Span("Rental counter", cls="hp-cs"), href=f"tel:{phones.tel(plan.rental.phone)}", cls="hp-contact", id="hp-car-contact"))
    sos = Div(
        Div(icon("shield", 20, 2.4), Span("Emergency", cls="hp-sos-t"), Span("Opens offline", cls="hp-sos-s"), cls="hp-sos-h"),
        Div(A(icon("phone", 22, 2.4), "Call 911", href="tel:911", cls="tp-btn tp-btn-ink hp-911", id="hp-911"),
            Div(*people, cls="hp-contacts", id="hp-contacts") if people else P("Nobody has added a phone number yet.", cls="hp-empty", id="hp-nocontacts"),
            A("Add your number", href="/family#my-phone", cls="hp-add", id="hp-add-mine") if not has_mine else "",
            cls="hp-sos-b"),
        cls="hp-sos", id="hp-sos")
    problem = Div("That number did not look right. Try something like +1 310 555 0100.", role="alert", cls="hp-problem", id="hp-problem") if request.query_params.get("problem") == "phone" else ""
    return Div(problem, *cards, sos, cls="hp")


def register(app):
    @app.post("/trip/help/phone")
    def fix_phone(session, kind: str = "", index: str = "0", phone: str = ""):
        try:
            phones.set_stay_phone(session, kind, index, phone)
        except phones.PhoneError as e:
            return RedirectResponse("/trip/help?problem=phone", status_code=303)
        return RedirectResponse("/trip/help", status_code=303)
