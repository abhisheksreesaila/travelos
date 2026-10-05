"""What a booking opens to on the trip canvas (F-093), and the emergency sheet.

    find(v, block_id)            what a booked block on the day is: a flight leg, a stay's check in or out, the car's pick up or drop off (or the demo trip's flight and stay)
    sheet(v, found, ua, back)    (pills, title, the sheet's body) with everything Help showed for it: the stay's address, Directions, Front desk, times, confirmation behind a tap, the phone fix;
                                 the flight's route, times, every traveller's pass and "Show everyone's passes"; the car's counter, Directions and Call
    sos(v, ua)                   (the emergency sheet's body): Call 911, tonight's front desk, the rental counter, the family's numbers, and a way to "This phone" on /family

The pieces are Help's own (gitaway/pages/tab_help.py, gitaway/pages/passes.py), so a fix to a number or a pass is the same code and the same write; the forms return to `back`, the
canvas address of the sheet. Nothing here knows the canvas's markup: gitaway/pages/tripcanvas.py wraps the body in its sheet.
"""

import re

from fasthtml.common import A, Div, H2, P, Span

from gitaway import catalog, morning, passes, passkeys, phones, session as ses, tripcal as cal, tripday as td, tripimport as ti
from gitaway.icons import icon
from gitaway.pages import passes as passes_ui, tab_help


def find(v, block_id):
    """(kind, item, index) for a booked block of the open trip, or None. kind: leg | checkin | checkout | pickup | dropoff | flight | stay (the demo trip's, which has no detail to show beyond its own).
    A red-eye's two halves (`-d`, `-a`) are one booking."""
    base = re.sub(r"-[da]$", "", block_id or "")
    b = v["b"]
    if cal.is_imported(b):
        plan = cal.plan_of(b)
        for spec in ti.block_specs(plan):
            if spec.id != base:
                continue
            pool = plan.legs if spec.kind == "leg" else plan.hotels if spec.kind in ("checkin", "checkout") else [plan.rental]
            return spec.kind, spec.item, next(i for i, x in enumerate(pool) if x is spec.item)
        return None
    if base in ("b-out", "b-back") and cal.flight_of(b):
        return "flight", cal.flight_of(b), 0
    if base in ("b-in", "b-out2") and cal.stay_of(b):
        return ("checkin" if base == "b-in" else "checkout"), cal.stay_of(b), 0
    return None


def _kv(label, value, ident=""):
    return Div(Span(label, cls="hp-k"), Span(value, cls="hp-v"), **({"id": ident} if ident else {}))


def _head(ico, tint, title, line=""):
    return Div(Span(icon(ico, 24, 2.2), cls=f"hp-ico {tint}", aria_hidden="true"), Div(H2(title, cls="hp-h"), Span(line, cls="hp-addr") if line else "", cls="hp-who"), cls="hp-row")


def _hotel(v, kind, h, index, ua, can_edit, back):
    pill = "Check in" if kind == "checkin" else "Check out"
    when = ti.when_text(h.check_in if kind == "checkin" else h.check_out)
    return [pill, when.split(",")[0]], h.name, [Span(h.address, cls="hp-addr", id="bk-addr") if h.address else "", *tab_help.hotel_parts(h, index, ua, can_edit, back)]


def _demo_stay(v, kind, stay, ua):
    t = v["t"]
    pill = "Check in" if kind == "checkin" else "Check out"
    return [pill], stay.name, [Span(stay.headline, cls="hp-addr"), Div(A(icon("nav", 18, 2.4), "Directions", href=td.maps_url(f"{stay.name}, {t.destination_name}", ua), cls="tp-btn tp-btn-white", id="hp-directions"), cls="hp-acts")]


def _car(v, kind, c, ua, can_edit, back):
    pick = kind == "pickup"
    at, where = (c.pickup, c.pickup_place) if pick else (c.dropoff, c.dropoff_place)
    times = Div(_kv("PICK UP", f"{c.pickup_place} · {ti.when_text(c.pickup)}", "bk-pickup"), _kv("DROP OFF", f"{c.dropoff_place} · {ti.when_text(c.dropoff)}", "bk-dropoff"), cls="hp-times bk-stack")
    return ["Pick up" if pick else "Drop off", ti.when_text(at).split(",")[0]], f"{c.company} rental car", [
        Span(f"{'Counter' if pick else 'Drop off'}: {where}", cls="hp-addr", id="bk-counter"), times,
        tab_help._confirm(c.confirmation), *tab_help.car_parts(c, ua, can_edit, back, place=where)]


def _flight(v, i, leg, can_edit, back):
    key = f"leg:{i}"
    f = next((x for x in passes.flights(v["session"]) if x["key"] == key), None)
    ps = passes.listing(v["session"]).get(key, [])
    names = passes.travellers(v["session"])
    cards, add = passes_ui.pass_cards(f, ps, can_edit, names, back) if f else ([], "")
    times = Div(_kv("LEAVES", ti.when_text(leg.depart), "bk-leaves"), _kv("ARRIVES", ti.when_text(leg.arrive), "bk-arrives"), cls="hp-times")
    show = A(icon("ticket", 18, 2.4), "Show everyone's passes", href=passes_ui.gate_url(key), cls="tp-btn tp-btn-coral", id="bk-show-passes") if ps else ""
    return ["Flight", ti.when_text(leg.depart).split(",")[0]], f"{leg.origin} → {leg.dest}", [
        Span(leg.name, cls="hp-addr", id="bk-flight"), times, tab_help._confirm(leg.confirmation), show,
        Div(Span("Passes & documents", cls="hp-k"), *cards, add, cls="bk-passes", id="bk-passes")]


def _demo_flight(v, x):
    return ["Flight"], x.name, [Span("Add the boarding passes on Help once you have them.", cls="hp-addr")]


def sheet(v, found, ua, back):
    """(pill words, title, body children) of a booking's sheet."""
    kind, item, index = found
    can_edit = v["role"] in ("admin", "editor")
    if kind in ("checkin", "checkout"):
        return _hotel(v, kind, item, index, ua, can_edit, back) if cal.is_imported(v["b"]) else _demo_stay(v, kind, item, ua)
    if kind in ("pickup", "dropoff"):
        return _car(v, kind, item, ua, can_edit, back)
    if kind == "leg":
        return _flight(v, index, item, can_edit, back)
    return _demo_flight(v, item)


def sos(v, ua):
    """The emergency sheet's body: 911, tonight's front desk, the rental counter, the family's numbers."""
    session, b = v["session"], v["b"]
    today = catalog.today_in(ses.trip_zone(session))
    plan = cal.plan_of(b) if cal.is_imported(b) else None
    rows = [Div(A(icon("phone", 22, 2.4), "Call 911", href="tel:911", cls="tp-btn tp-btn-ink hp-911"), cls="bk-sos-911", id="sos-911")]
    if plan and plan.hotels:
        h = plan.hotels[phones.tonight(plan.hotels, today)]
        rows.append(Div(Span("Tonight's hotel", cls="hp-k"), Span(h.name, cls="hp-v"), tab_help._call(h.phone, "Front desk") or Span("No phone number yet", cls="hp-none"), cls="bk-sos-row", id="sos-hotel"))
    elif not plan and (stay := cal.stay_of(b)):
        rows.append(Div(Span("Tonight's hotel", cls="hp-k"), Span(stay.name, cls="hp-v"), Span("No phone number yet", cls="hp-none"), cls="bk-sos-row", id="sos-hotel"))
    if plan and plan.rental:
        rows.append(Div(Span("Rental counter", cls="hp-k"), Span(plan.rental.company, cls="hp-v"), tab_help._call(plan.rental.phone, "Rental counter") or Span("No phone number yet", cls="hp-none"), cls="bk-sos-row", id="sos-car"))
    contacts, has_mine = tab_help._family(session)
    rows.append(Div(Span("The family", cls="hp-k"), Div(*contacts, cls="hp-contacts", id="sos-contacts") if contacts else P("Nobody has added a phone number yet.", cls="hp-empty", id="sos-nocontacts"),
                    A("Add your number", href="/family#my-phone", cls="hp-add", id="sos-add-mine") if not has_mine else "", cls="bk-sos-row bk-sos-family"))
    if morning.configured() or passkeys.configured():       # the family page has these two cards only where the server can do them
        rows.append(Div(Span("This phone", cls="hp-k"), A(icon("bell", 18, 2.4), "Morning plan and Face ID", href="/family#morning-plan" if morning.configured() else "/family#this-phone", cls="tp-btn tp-btn-white", id="sos-phone"), cls="bk-sos-row"))
    return rows
