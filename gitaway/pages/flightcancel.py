"""A flight booked here, on its booking page (F-276, D-977): what it is now, and cancelling it with the quote first.

    panel(v, leg, back)          what a flight's booking page adds below its words when the flight was booked here through LiteAPI (or is a labelled sample): its status in LiteAPI's honest words
                                 (waiting for the airline, or tickets issued), the booking reference and the airline's locator, the fare's rules; for an editor "See what cancelling would cost",
                                 then LiteAPI's quote in money and a confirm; once cancelled, what LiteAPI says came back, and "pending" when it has accepted and not finished.
POST /trip/booking/flight/cancel   `step=quote` asks LiteAPI what cancelling would give back and cost (nothing is cancelled), `step=confirm` cancels on that quote (an editor's write, only after a
                                 fresh quote, only a flight in this family's `matrix_flights`, by the booking id read from the flight's reference); a sample flight never calls LiteAPI.

Changes (new dates) are not offered here: LiteAPI charges for each change (D-977).
"""

from fasthtml.common import Button, Div, Form, Input, Label, P, Span
from starlette.responses import RedirectResponse, Response

from gitaway import access, bookingmail, catalog, familydb, flightbook as fb, liteapi, matrixbook as mb, reports, session as ses
from gitaway.icons import icon
from gitaway.pages import passes as passes_ui, staycancel

PATH = "/trip/booking/flight/cancel"


def quote_words(refund: int, penalty: int) -> str:
    """What LiteAPI's quote means, in money: the refund comes back to the card that paid, the penalty is what cancelling costs."""
    if refund and penalty:
        return f"If you cancel now: {catalog.money(refund)} comes back to the card you paid with, and cancelling costs {catalog.money(penalty)}."
    if refund:
        return f"If you cancel now: {catalog.money(refund)} comes back to the card you paid with."
    if penalty:
        return f"If you cancel now: nothing comes back, and cancelling costs {catalog.money(penalty)}."
    return "If you cancel now: nothing is charged and nothing comes back."


def _done_words(c) -> str:
    if c["status"] == "PENDING":
        return (f"Cancellation requested. LiteAPI has accepted it and the airline has not finished. Quoted: {catalog.money(c['refund_cents'])} comes back, "
                f"cancelling costs {catalog.money(c['fee_cents'])}.")
    return staycancel._came_back(c)


def panel(v, leg, back: str = ""):
    """The booked-here part of a flight's booking page, or nothing when the flight was not booked here."""
    ref = (leg.confirmation or "").strip()
    if not ref:
        return ""
    with ses.family(v["session"]) as fam:
        if not fam:
            return ""
        row = fb.row_for_ref(fam.db, ref)
        if not row:
            return ""
        done = mb.cancelled(fam.db, row["booking_id"])
    facts = fb.facts_of_row(row)
    locs = ", ".join(f"{a} {p}".strip() for a, p in fb.locators(row)) or row["pnr"]
    pending = row["status"] == "PENDING_CONFIRMATION" and not row["sample"]
    status = Div(Span("Status", cls="hp-k"), P(icon("bell" if pending else "check", 15, 2.4), fb.status_words(row), cls="bk-fstatus" + (" is-wait" if pending else ""), id="bk-fstatus", data_status=row["status"]), cls="bk-fl-row")
    refs = Div(Span("Booking reference", cls="hp-k"), P(row["ref"] or row["booking_id"], cls="bk-fref", id="bk-fref"), cls="bk-fl-row") if not row["sample"] else ""
    pnr = Div(Span("Airline booking reference", cls="hp-k"), P(locs, cls="bk-fref", id="bk-fpnr"), cls="bk-fl-row") if locs and not row["sample"] else ""
    rules = Div(Span("Fare", cls="hp-k"), P(f"{facts.get('fare') or 'Flight'} · {fb.refund_words(facts.get('refundable') is True)}. {fb.change_words(facts.get('changeable') is True)}.", cls="bk-fpolicy", id="bk-fpolicy"),
                cls="bk-fl-row") if facts else ""
    who = P(mb.merchant_words(), cls="bk-cancel-merchant", id="bk-merchant") if not row["sample"] else P(fb.SAMPLE_WORDS + ".", cls="bk-cancel-merchant", id="bk-merchant")
    head = [status, refs, pnr, rules, who]
    if row["sample"]:
        return Div(*head, cls="bk-cancel bk-flight")
    if done:
        return Div(*head, Div(icon("check", 16, 2.6), Span("Cancelled" if done["status"] != "PENDING" else "Cancelling"), cls="hp-k"), P(_done_words(done), cls="bk-cancel-done", id="bk-cancelled"), cls="bk-cancel bk-flight")
    if not access.can_edit(v["role"]):
        return Div(*head, cls="bk-cancel bk-flight")
    hidden = [Input(type="hidden", name="booking", value=row["booking_id"]), Input(type="hidden", name="next", value=back)]
    if fb.quoted(row):
        ask = Form(*hidden, Input(type="hidden", name="step", value="confirm"), P(quote_words(row["quote_refund_cents"], row["quote_fee_cents"]), cls="bk-cancel-policy", id="bk-fquote"),
                   Label(Input(type="checkbox", name="sure", value="1", required=True), Span("I want to cancel this flight on that quote"), cls="bk-cancel-sure"),
                   Button(icon("x", 16, 2.6), "Cancel this flight", type="submit", cls="tp-btn tp-btn-white bk-cancel-go", id="bk-fcancel-go"), method="post", action=PATH, cls="bk-cancel-f")
    else:
        ask = Form(*hidden, Input(type="hidden", name="step", value="quote"), P("Nothing is cancelled until you confirm. First see what it would cost.", cls="bk-cancel-policy"),
                   Button(icon("arrow-right", 16, 2.6), "See what cancelling would cost", type="submit", cls="tp-btn tp-btn-white bk-cancel-go", id="bk-fquote-go"), method="post", action=PATH, cls="bk-cancel-f")
    return Div(*head, ask, cls="bk-cancel bk-flight")


def register(app):
    @app.post(PATH)
    def flight_cancel(request, session, booking: str = "", step: str = "", sure: str = "", next: str = ""):
        if not reports.same_site(request):      # a cross-site form cancels nothing (L3)
            return Response("That did not come from GitAway. Open the booking again and press the button.", status_code=403)
        me = ses.current_traveler(session)
        back = passes_ui.safe_back(next) or "/trip/plan"
        sep = "&" if "?" in back else "?"
        if not me:
            return RedirectResponse(ses.signin_href(back), status_code=303)
        if not booking or len(booking) > 60 or step not in ("quote", "confirm"):
            return RedirectResponse(f"{back}{sep}err=flight_quote", status_code=303)
        family = session.get("tenant_id") or ""
        with ses.family(session) as fam:
            if not fam:
                return RedirectResponse(ses.signin_href(back), status_code=303)
            if step == "quote":
                if not mb.allow(me.id):      # the per-person limit on booking presses counts a quote too (D-980)
                    return RedirectResponse(f"{back}{sep}err=flight_slow", status_code=303)
                status, _ = fb.quote(fam.db, family, booking, me.id)
                return RedirectResponse(back if status == liteapi.OK else f"{back}{sep}err=flight_quote", status_code=303)
            if sure != "1":
                return RedirectResponse(f"{back}{sep}err=flight_tick", status_code=303)
            row = familydb.row(fam.db, "SELECT * FROM matrix_flights WHERE booking_id = :b", b=booking)
            status, got = fb.cancel(fam.db, family, booking, me.id)
            if status == fb.NEEDS_QUOTE:
                return RedirectResponse(f"{back}{sep}err=flight_stale", status_code=303)
            if status == liteapi.OK:      # the person who cancelled is told what LiteAPI reported (once: the marker on the booking)
                bookingmail.flight_cancelled(fam.db, booking, session.get("email") or "", got.refund_cents, got.fee_cents)
        if status not in (liteapi.OK, liteapi.PENDING):
            return RedirectResponse(f"{back}{sep}err=flight_cancel", status_code=303)
        if status == liteapi.OK and row:
            fb.mark_cancelled(session, row["trip_id"], row["ref"] or row["booking_id"])
        return RedirectResponse(back, status_code=303)
