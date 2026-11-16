"""Cancel a stay booked here through LiteAPI (F-274, D-845), on the stay's booking page.

    panel(v, h, back)      what a stay's booking page adds below its words when the stay was booked here (a LiteAPI booking, not a sample): the cancelling policy as it was shown
                           before paying; for an editor a "Cancel this stay" button (with a tick to say it is meant); once cancelled, what LiteAPI says came back.
POST /trip/booking/cancel  one stay: LiteAPI's cancel (`matrixbook.cancel`), the stay marked Cancelled on the trip, back to the booking page. An editor's write like every other.

A refundable stay's cancel gives the money back, a non-refundable one's charges what LiteAPI says (the fee): both are said before and after. Only a stay in this family's
`matrix_bookings` is ever cancelled, by LiteAPI's booking id read from the stay's confirmation; a sample booking (`SAMPLE-...`) never calls LiteAPI.
"""

from fasthtml.common import Button, Div, Form, Input, Label, P, Span
from starlette.responses import RedirectResponse

from gitaway import access, catalog, familydb, liteapi, matrixbook as mb, session as ses
from gitaway.icons import icon
from gitaway.pages import passes as passes_ui

PATH = "/trip/booking/cancel"
TICK = "Tick the box to say you mean to cancel this stay."


def _came_back(c) -> str:
    """What LiteAPI said about the cancel, in words: the refund, or the charge."""
    if c["status"] == "CANCELLED":
        return f"Cancelled. LiteAPI says {catalog.money(c['refund_cents'])} comes back to the card you paid with." if c["refund_cents"] else "Cancelled. Nothing was charged."
    return f"Cancelled. Nothing comes back: LiteAPI charged {catalog.money(c['fee_cents'])} for cancelling." if c["fee_cents"] else "Cancelled. Nothing comes back."


def panel(v, h, back: str = ""):
    """The cancel part of a stay's booking page, or nothing when the stay was not booked here through LiteAPI."""
    booking = (h.confirmation or "").strip()
    if not booking or booking.startswith("SAMPLE-"):
        return ""
    with ses.family(v["session"]) as fam:
        if not fam:
            return ""
        row = familydb.row(fam.db, "SELECT * FROM matrix_bookings WHERE booking_id = :b AND sample = 0", b=booking)
        if not row:
            return ""
        done = mb.cancelled(fam.db, booking)
        pay = familydb.row(fam.db, "SELECT policy FROM matrix_payments WHERE booking_id = :b", b=booking) or {}
    if done:
        return Div(Div(icon("check", 16, 2.6), Span("Cancelled"), cls="hp-k"), P(_came_back(done), cls="bk-cancel-done", id="bk-cancelled"), cls="bk-cancel")
    policy = pay.get("policy") or ("Refundable: LiteAPI gives the money back." if row["refundable"] else "Non-refundable: if you cancel, nothing comes back.")
    ask = Form(Input(type="hidden", name="booking", value=booking), Input(type="hidden", name="next", value=back),
               Label(Input(type="checkbox", name="sure", value="1", required=True), Span("I want to cancel this stay"), cls="bk-cancel-sure"),
               Button(icon("x", 16, 2.6), "Cancel this stay", type="submit", cls="tp-btn tp-btn-white bk-cancel-go", id="bk-cancel-go"), method="post", action=PATH, cls="bk-cancel-f") \
        if access.can_edit(v["role"]) else ""
    return Div(Div(Span("Cancelling", cls="hp-k"), cls="bk-cancel-h"), P(policy, cls="bk-cancel-policy", id="bk-policy"), ask, cls="bk-cancel")


def register(app):
    @app.post(PATH)
    def cancel(session, booking: str = "", sure: str = "", next: str = ""):
        me = ses.current_traveler(session)
        back = passes_ui.safe_back(next) or "/trip/plan"
        sep = "&" if "?" in back else "?"
        if not me:
            return RedirectResponse(ses.signin_href(back), status_code=303)
        if sure != "1" or not booking or len(booking) > 60:
            return RedirectResponse(f"{back}{sep}err=cancel_tick", status_code=303)
        family = session.get("tenant_id") or ""
        with ses.family(session) as fam:
            if not fam:
                return RedirectResponse(ses.signin_href(back), status_code=303)
            status, got = mb.cancel(fam.db, family, booking, me.id)
            trip_id = (familydb.row(fam.db, "SELECT trip_id FROM matrix_bookings WHERE booking_id = :b", b=booking) or {}).get("trip_id", "")
        if status != liteapi.OK:
            return RedirectResponse(f"{back}{sep}err=cancel", status_code=303)
        mb.mark_cancelled(session, trip_id, booking)
        return RedirectResponse(back, status_code=303)
