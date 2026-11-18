"""Booking a trip matrix square (F-233, D-480 to D-489; the checkout redone in F-242, D-570 to D-579): the sheet the square grows into, and its two steps.

POST /plan/matrix/book           step 1: the stays' offers are prebooked (the rooms checked, their final price read); the answer is the checkout: three folding cards (guest,
                                 payment, confirm) and "Sandbox booking: nothing is charged". A fragment for assets/js/matrixbook.js (header `X-Matrix: 1`), else a page.
POST /plan/matrix/book/confirm   step 2: the lead guest is checked, the square becomes the family's trip (the same path as Save to trip), each stay is booked once through
                                 LiteAPI's sandbox, the stay is added to the trip, and the answer is the stamped pass with LiteAPI's booking id. The script plays the progress
                                 (holding the room, paying with the test card, booking, putting the trip together) while this call runs, then throws the confetti.

POST /plan/matrix/book/code      "Have a code?" (F-274): the stay is prebooked again with a LiteAPI voucher code; the answer is JSON (a new token, the totals), the discount shown only here
GET  /plan/matrix/book/return    where LiteAPI's payment form sends the browser after paying (F-274, D-842): the stay is booked once with the saved transaction id and the pass is drawn

With the payment form (a live key, or the sandbox with GITAWAY_SANDBOX_FORM=1: `mb.pays_by_form()`) step 2 saves the lead guest and answers the form instead of the pass: LiteAPI's script,
its `secretKey` and our return address; GitAway renders no card field and never sees a card.

Both take `fl` and `st`, the flight and stays chosen on the square (indexes into the square's alternatives; gitaway/tripmatrix.py `pick`): the server prices the chosen trip
itself, and a held room is bound to its choice. Both are plain `def` handlers (a prebook or book can wait on the network) and writes, so the access beforeware gives them to editors
only: a viewer is refused (403) before anything is asked of LiteAPI. Flights are not booked here: the pass links to the flight lane's partner like any other search. The words,
prices and the guest's name and email come out through FastHTML's escaping; the guest's email is never logged and never put in a URL.
"""

import re
from datetime import date

from fasthtml.common import A, Button, Div, Form, H2, H3, Input, Label, Noscript, P, Small, Span, to_xml
from fasthtml.core import FtResponse
from starlette.responses import JSONResponse, RedirectResponse, Response

from gitaway import access, auth, blogbutton, catalog, familydb, importer, liteapi, matrixbook as mb, session as ses, showcase, tripmatrix as tm, walletpass
from gitaway.icons import icon
from gitaway.layout import page
from gitaway.pages import tripmatrix as mx, v2drawer

CONFIRM = mx.BOOK + "/confirm"
CODE = mx.BOOK + "/code"
RETURN = mx.BOOK + "/return"
SIGNIN = "Sign in to book."
STALE = "That room check has expired or is not for this square. Close this and press Book this trip on the square again."
TICK = "Tick the box to say you have read the fare and hotel rules."
SLOW_DOWN = "That is a lot of booking tries. Wait a minute, or try again tomorrow."
MADE_UP = ("Test", "Traveler", "test.traveler@example.com")      # the sandbox form starts with a made-up guest (D-510)
STEPS = (("Lead guest", "Who is the lead guest?"), ("Contact", "Where should we send it?"), ("Requests", "Anything the hotel should know?"), ("Review", "Check it, then book"))
# What the progress says while a booking runs (D-573): the room was really held when this sheet opened; the payment is the sandbox's test card (staged, no money moves);
# the booking and the trip are the real calls. The script plays them one after another and waits for the real answer before the last one is ticked.
STAGES = {"sandbox": ("Holding your room", "Paying with the test card", "Booking your stay with LiteAPI", "Putting the trip together"),
          "sample": ("Holding your room", "Paying with the sample card", "Confirming your sample stay", "Putting the trip together")}
STAGES_FORM = ("Holding your room", "Opening LiteAPI’s secure payment form")
CONFETTI = 64
CODES_OFF = "Codes are off for today. Book without one."
NEEDS_PHONE = "Add a mobile number: the booking needs one."
PAID_BUT = ("Your payment may have gone through, but we could not confirm the booking just now. Do not pay again. Reload this page in a minute to try once more; "
            "if it still does not confirm, write to LiteAPI with the payment reference below.")


def _head(s, lane, w, sample: bool, booked: bool = False):
    return Div(Div(Span("Booked" if booked else "Book my trip", cls="mxb-k0"), H2(f"Book {lane.name}", cls="mxb-h"), P(f"{tm.when(w)} · {w.nights} nights · {mx.party_words(s)}", cls="mxb-sub"), cls="mxb-top"),
               P(icon("shield", 16, 2.4), mb.words(sample), cls="mxb-sandbox" + (" is-booked" if booked else ""), role="status" if booked else "note"), cls="mxb-head")


def _stay_row(row: mb.Row):
    pre, part = row.prebook, row.part
    nights = (pre.checkout - pre.checkin).days
    words = [pre.room or part.room, f"{nights} night{'s' if nights != 1 else ''}", f"{pre.checkin:%b} {pre.checkin.day} to {pre.checkout:%b} {pre.checkout.day}",
             "Refundable" if pre.refundable else "Non-refundable"]
    return Div(Span(icon("bed", 16, 2.2), cls="mx-kt k-stay"),
               Div(P(part.name, cls="mx-r-h"), P(f"{row.place} · " + " · ".join(w for w in words if w), cls="mx-r-s"),
                   P(f"{catalog.money(pre.due_at_stay_cents)} of it is paid at the hotel", cls="mx-r-s mx-r-due") if pre.due_at_stay_cents else ""),
               Span(catalog.money(row.total_cents), cls="mx-r-n"), cls="mx-row mxb-row")


def _flight_row(sq):
    f = sq.flight
    return Div(Span(icon("plane", 16, 2.2), cls="mx-kt k-flight"),
               Div(P(f.airline, cls="mx-r-h"), P(v2drawer.times(f.out), cls="mx-r-s"), P(v2drawer.times(f.back), cls="mx-r-s") if f.back else "",
                   P("Flight booking is next.", cls="mx-r-s")),
               Span(catalog.money(f.cents), cls="mx-r-n"), cls="mx-row mxb-row")


def _moved(prep: mb.Prep):
    if not prep.changed:
        return ""
    was = sum(r.part.cents for r in prep.rows)
    words = (f"The price moved: it was {catalog.money(was)} on the square and is {catalog.money(prep.total_cents)} now."
             if was != prep.total_cents else "The room’s terms changed since the square. Read them below, then book.")
    return P(icon("bell", 16, 2.4), words, cls="mxb-note is-warn", role="status")


def _field(name, label, value, error, required=True, **attrs):
    return Div(Label(label, fr=f"mxb-{name}", cls="mxb-l"), Input(id=f"mxb-{name}", name=name, value=value, required=required, aria_invalid="true" if error else None,
                                                                  aria_describedby=f"mxb-{name}-e" if error else None, **attrs),
               P(error, id=f"mxb-{name}-e", cls="mxb-err", role="alert") if error else "", cls="mxb-field" + (" has-err" if error else ""))


def pick_fields(pk: tuple) -> dict:
    """The choice a form carries to the next route: {"fl": "1", "st": "0,2", "rm": "1,0"} (flight, hotel and room indexes), the shown part being index 0."""
    return {"fl": str(pk[0]), "st": ",".join(str(i or 0) for i in pk[1]), "rm": ",".join(str(i or 0) for i in (pk[2] if len(pk) > 2 else ()))}


def _hidden(s, lane, w, pk=(0, (), ()), **more):
    return [Input(type="hidden", name=n, value=str(v)) for n, v in {**mx.params(s, lane=lane.key, w=w.key), **pick_fields(pk), **more}.items()]


def _chips(name, options, picked, attr):
    return Div(*[Button(v, type="button", cls="v2-chip", aria_pressed="true" if v in picked else "false", **{attr: v}) for v in options], cls="v2-chips")


def _party(s) -> str:
    """The party in words ("2 adults, 1 kid (ages 7)"): the review's line, and kept with the prebook for the booked email (F-285)."""
    kids = len(s.kid_ages)
    return f"{s.adults} adult{'' if s.adults == 1 else 's'}" + (f", {kids} kid{'' if kids == 1 else 's'} (ages {', '.join(map(str, s.kid_ages))})" if kids else "")


def _rv(k, v, small="", edit=None, mark=None):
    """One line of the review: what, its answer, and an Edit link that goes back to the question (`data-go`)."""
    return Div(Span(k, cls="mxb-rk"), Span(Span(v, **({"data_rv": mark} if mark else {})), Small(small, **({"data_rv": mark + "-s"} if mark else {})) if (small or mark) else "", cls="mxb-rv-v"),
               Button("Edit", type="button", cls="mxb-ed", data_go=str(edit), aria_label=f"Change: {k}") if edit is not None else "", cls="mxb-rvr")


def _checkout(s, lane, w, sq, prep, pk, values=None, errors=None):
    """The checkout (the prototype's four questions, F-251): lead guest, contact, requests, then review with Edit links, a required tick and the sum; one form. With the script the
    questions come one at a time with a progress bar, Continue and Back; without it all four are open and the one button books. The guest starts as a made-up one (sandbox);
    LiteAPI's test card pays, so no card number is asked or kept. Only the lead guest's name and email go to LiteAPI; the phone, the requests and the arrival are shown on the review and the
    pass and are never sent, stored or logged."""
    form, live = mb.pays_by_form() and not prep.sample, mb.mode() == mb.LIVE
    values, errors = values or ({} if live else dict(zip(("first", "last", "email"), MADE_UP))), errors or {}
    sample = prep.sample
    who = _party(s)
    held = P(icon("lock", 16, 2.2), f"Your room is held for {mb.HOLD // 60} minutes while you answer.", cls="mxb-held")
    guest = (P("The name on the hotel booking. It must match an ID at check-in." + ("" if live else " A made-up guest is filled in: this is the sandbox, so there is no need to type a real name."), cls="mxb-lede"),
             Div(_field("first", "First name", values.get("first", ""), errors.get("first"), autocomplete="given-name", maxlength=mb.NAME_MAX),
                 _field("last", "Last name", values.get("last", ""), errors.get("last"), autocomplete="family-name", maxlength=mb.NAME_MAX), cls="mxb-two"),
             Div(f"Travelling · {s.travelers}", cls="dr-sub"), P(who, cls="mxb-trav"), held)
    contact = (P("The confirmation and any change from the hotel come here. LiteAPI is sent your name, email and mobile number to make the booking; GitAway keeps them only until it is made."
                 if form else "The confirmation and any change from the hotel. LiteAPI’s sandbox is sent your name and email only; GitAway keeps neither.", cls="mxb-lede"),
               _field("email", "Email", values.get("email", ""), errors.get("email"), type="email", autocomplete="email", maxlength=mb.EMAIL_MAX, inputmode="email"),
               _field("phone", "Mobile number" if form else "Mobile, for texts on the day (optional)", values.get("phone", ""), errors.get("phone"), required=form, type="tel", autocomplete="tel",
                      maxlength=mb.PHONE_MAX, inputmode="tel"),
               P("The hotel may use it to reach you about the stay." if form else "The mobile number stays on this screen and your pass: it is not sent anywhere.", cls="mxb-hint"))
    picked = {x for x in str(values.get("req", "")).split("|") if x}
    requests = (P("Requests, not promises: the hotel does its best. They are sent with the booking." if form else
                  "Requests, not promises: the hotel does its best. In this sandbox they stay on your pass; the test hotel is not sent them.", cls="mxb-lede"),
                _chips("req", mb.REQUESTS, picked, "data_req"), Div("Arriving at the hotel", cls="dr-sub"), _chips("arrive", mb.ARRIVALS, {values.get("arrive", "")}, "data_arr"),
                Input(type="hidden", name="req", value="|".join(r for r in mb.REQUESTS if r in picked), data_field="req"), Input(type="hidden", name="arrive", value=values.get("arrive", ""), data_field="arrive"))
    nights = (w.return_ - w.depart).days
    name = " ".join(x for x in (values.get("first", ""), values.get("last", "")) if x)
    f = sq.flight
    stays = " + ".join(r.part.name for r in prep.rows)
    rv = Div(_rv("Trip", lane.name, f"{tm.when(w)} · {nights} nights"),
             _rv("Flights", f"{s.home} ⇄ {lane.places[0].iata} · {f.airline}", f"{v2drawer.times(f.out)} · {v2drawer.stops_words(f.stops).lower()}. Flight booking is next."),
             _rv("Stay", stays, " · ".join(f"{r.prebook.room or r.part.room} · {'Refundable' if r.prebook.refundable else 'Non-refundable'}" + (f" · {catalog.money(r.prebook.due_at_stay_cents)} of it is paid at the hotel" if r.prebook.due_at_stay_cents else "") for r in prep.rows)),
             _rv("Guest", f"{name} + {s.travelers - 1}", "", 0, "guest"), _rv("Contact", values.get("email", ""), values.get("phone", ""), 1, "contact"),
             _rv("Requests", ", ".join(r for r in mb.REQUESTS if r in picked) or "None", f"Arriving in the {values['arrive'].lower()}" if values.get("arrive") else "", 2, "requests"), cls="mxb-rv")
    stays_total = prep.total_cents
    sums = Div(*[Div(Span(r.part.name + f" · {(r.prebook.checkout - r.prebook.checkin).days} night" + ("s" if (r.prebook.checkout - r.prebook.checkin).days != 1 else "")),
                     Span(catalog.money(r.total_cents), cls="num", data_sum="stay")) for r in prep.rows], cls="mxb-sum-rows")
    discount = sum(r.prebook.discount_cents for r in prep.rows)
    off = Div(Span(f"Code {prep.voucher}", data_sum="code"), Span("−" + catalog.money(discount) if discount else "", cls="num", data_sum="discount"), cls="mxb-off", hidden=not discount) if form else ""
    summary = Div(Div(Span(f"Flight · {s.travelers} seats, {f.airline}"), Span(catalog.money(f.cents), cls="num")), sums, off,
                  Div(Span("Total for the trip", cls="mxb-tl"), Span(catalog.money(f.cents + stays_total), cls="num mxb-total", data_sum="total"), cls="t"), cls="mxb-sum")
    agree = Label(Input(type="checkbox", name="agree", required=True, checked=values.get("agree") == "on", cls="mxb-tick"), Span(icon("check", 16, 3), cls="mxb-cb", aria_hidden="true"),
                  Span("I have read the fare and hotel rules, including whether each stay is refundable."), cls="mxb-agree" + (" has-err" if errors.get("agree") else ""))
    last = (P(mb.SAMPLE_WORDS if sample else mb.NOTHING_CHARGED + ". LiteAPI’s test card pays; no email is sent.", cls="mxb-fine") if not form else
            P((mb.LIVE_WORDS if live else "Sandbox booking: the form takes LiteAPI’s test card, nothing is charged") + ". Next is LiteAPI’s secure payment form.", cls="mxb-fine"))
    review = (rv, Div(_moved(prep), data_moved="1"), _policy(prep) if form else "", _code_box(prep) if form else "", summary,
              P(f"This booking covers the stay{'s' if len(prep.rows) > 1 else ''}: {catalog.money(stays_total)}. Flight booking is next.", cls="mxb-fine"),
              agree, P(errors["agree"], id="mxb-agree-e", cls="mxb-err", role="alert") if errors.get("agree") else "", last)
    panes = [Div(H3(STEPS[i][1], cls="mxb-q"), *body, cls="mxb-pane", data_pane=str(i), data_small=STEPS[i][0]) for i, body in enumerate((guest, contact, requests, review))]
    prog = Div(*[Span(cls="on" if i == 0 else "") for i in range(len(STEPS))], cls="mxb-prog", aria_hidden="true")
    foot = Div(Button("Back", type="button", cls="mxb-b2", data_back="1"), Span("Step 1 of 4", cls="mxb-stepn"),
               Button("Tick the rules to book", type="button", cls="mxb-need", data_need="1"),      # overnight walk 2026-11-17: the greyed Book said nothing; this says why and shows the box (it never ticks it)
               Button(Span("Continue"), icon("arrow-right", 20, 2.4), type="button", cls="mxb-b1", data_cont="1"),
               Button(icon("check", 20, 2.8), Span(f"Continue · {catalog.money(stays_total)}" if form else f"Book for {catalog.money(stays_total)}", data_sum="go"), type="submit",
                      cls="mxb-b1 mxb-go sun"), cls="mxb-foot")
    at = min((i for f, i in (("first", 0), ("last", 0), ("email", 1), ("phone", 1), ("agree", 3)) if f in errors), default=0)      # the question a mistake is in opens first
    return Form(prog, Div(*panes, cls="mxb-panes"), foot, *_hidden(s, lane, w, pk, token=prep.token), method="post", action=CONFIRM, cls="mxb-f", data_step=str(at),
                data_stages="|".join(STAGES["sample" if sample else "sandbox"]), data_travel=str(s.travelers - 1), **({"data_pay": "1", "data_code_url": CODE} if form else {}))


def _policy(prep: mb.Prep):
    """The refund policy, word for word as LiteAPI gives it: our sentence from its deadline and fee, then its own remarks, and who sells it (D-843)."""
    rows = [Div(P(r.part.name, cls="mxb-k"), P(mb.policy_words(r.prebook), cls="mxb-pol-h"), P(r.prebook.remarks, cls="mx-r-s mxb-remarks") if r.prebook.remarks else "") for r in prep.rows]
    return Div(Div(icon("shield", 16, 2.2), Span("Cancelling and refunds"), cls="mxb-pol-t"), *rows, P(mb.merchant_words(), " ", A("How GitAway keeps you safe", href="/trust", target="_blank", rel="noopener"), cls="mxb-fine"), cls="mxb-policy")


def _code_box(prep: mb.Prep):
    """"Have a code?": a LiteAPI voucher code, checked by LiteAPI (the script asks POST /plan/matrix/book/code; without it the field is a note that the code needs the script)."""
    if not mb.codes_open():      # too many wrong codes today: the box is off until tomorrow (L1)
        return ""
    return Div(Label("Have a code?", fr="mxb-code", cls="mxb-l"),
               Div(Input(id="mxb-code", type="text", autocomplete="off", autocapitalize="none", spellcheck="false", maxlength="32", value=prep.voucher, data_code="1"),
                   Button("Apply", type="button", cls="mxb-b2 mxb-apply", data_apply="1"), cls="mxb-codebox-r"),
               P("", id="mxb-code-msg", cls="mxb-hint", role="status", data_code_msg="1"), cls="mxb-field mxb-codebox")


def pay_form(prep: mb.Prep, secret: str, return_url: str):
    """The step after the guest: LiteAPI's payment form in our sheet (D-842). Its script is loaded by assets/js/matrixbook.js from `liteapi.PAYMENT_SDK` alone; the card fields are LiteAPI's
    and its processor's, in their own frame. We give the form its `secretKey` (the prebook's), `publicKey` ("live", or "sandbox" with a sandbox key) and where to send the browser after."""
    row = prep.rows[0]
    pre = row.prebook
    nights = (pre.checkout - pre.checkin).days
    sandbox = liteapi.mode() != "live"
    return Div(H3("Pay for your stay", cls="mxb-q"),
               P(f"{row.part.name} · {nights} night{'s' if nights != 1 else ''}, {pre.checkin:%b} {pre.checkin.day} to {pre.checkout:%b} {pre.checkout.day}", cls="mxb-lede"),
               Div(Span("Charged now", cls="mxb-tl"), Span(catalog.money(pre.charge_cents), cls="num mxb-total", data_charge="1"), cls="mxb-sum t"),
               P(f"{catalog.money(pre.due_at_stay_cents)} more is paid at the hotel.", cls="mxb-fine") if pre.due_at_stay_cents else "",
               _policy(prep),
               P("Sandbox: use LiteAPI’s test card 4242 4242 4242 4242, any future date, any 3 digits. Nothing is charged.", cls="mxb-fine") if sandbox else "",
               Div(id="mxb-pay-el", cls="mxb-payel", data_pay_root="1", data_key="sandbox" if sandbox else "live", data_secret=secret, data_return=return_url, aria_label="Payment form"),
               P("Loading LiteAPI’s secure payment form…", cls="mxb-hint", data_pay_wait="1", role="status"),
               Noscript(P("LiteAPI’s payment form needs JavaScript. Turn it on for this page, then book again.", cls="mxb-note is-warn", role="alert")),
               cls="mxb-body mxb-paying", data_pay_pane="1")


def return_url(request, token: str) -> str:
    """Where LiteAPI's form sends the browser after paying: our own return route, on the site's public address in production (never the request's Host), else on this request's origin."""
    base = blogbutton.base_url() if auth.production() else str(request.base_url).rstrip("/")
    return f"{base}{RETURN}?" + "token=" + token


_TOKEN = re.compile(r"^[A-Za-z0-9_-]{8,40}\Z")


def _paid_page(done, pay, problem: str = "", status: int = 200, family: str = ""):
    """The page the payment form returns to: the pass of the stay just booked (what LiteAPI and the saved prebook say, nothing typed), or why it is not confirmed."""
    back = A(icon("arrow-right", 22, 2.8), Span("Plan this trip"), href="/trip/plan?arrive=1", cls="mxb-plan", data_trip="1")
    if done is None:
        inner = Div(Div(Div(Span("Your booking", cls="mxb-k0"), H2("Not confirmed yet", cls="mxb-h"), cls="mxb-top"), cls="mxb-head"),
                    Div(P(icon("bell", 18, 2.4), problem, cls="mxb-note is-warn", role="alert"), A("Back to the plan", href="/trip/plan", cls="btn mxb-back"), cls="mxb-problem"), cls="mxb", data_at="problem")
    else:
        charged = pay["charge_cents"] if pay else done.total_cents - done.due_at_stay_cents
        what = [Div(P("Stay", cls="mxb-k"), P(done.hotel, cls="mxb-pass-h"), P(f"{done.place} · {_day(done.checkin)} to {_day(done.checkout)}" + (f" · {done.room}" if done.room else ""), cls="mx-r-s"),
                    cls="mxb-pass-row"),
                Div(P("Paid", cls="mxb-k"), P(catalog.money(charged), cls="mxb-pass-h"),
                    P(f"{catalog.money(done.due_at_stay_cents)} more is paid at the hotel.", cls="mx-r-s") if done.due_at_stay_cents else "",
                    P(icon("lock", 14, 2.2), mb.merchant_words(), cls="mx-r-s"), cls="mxb-pass-row"),
                Div(P("Cancelling", cls="mxb-k"), P((pay or {}).get("policy") or ("Refundable: you can cancel it from the booking page." if done.refundable else "Non-refundable: if you cancel, nothing comes back."), cls="mxb-pass-h"),
                    P("LiteAPI or the hotel sends the confirmation by email.", cls="mx-r-s"), cls="mxb-pass-row")]
        stub = Div(Div(P("Booking id", cls="mxb-k"), P(Span(done.booking_id, cls="mxb-id", data_booking_id=done.booking_id), cls="mxb-code"),
                       *([P("Hotel confirmation", cls="mxb-k"), P(Span(done.confirmation, cls="mxb-id"), cls="mxb-code")] if done.confirmation else []), cls="mxb-stub-i"), cls="mxb-stub")
        inner = Div(Div(Div(Span("Booked", cls="mxb-k0"), H2("You’re booked", cls="mxb-h"), P(done.hotel, cls="mxb-sub"), cls="mxb-top"),
                        P(icon("shield", 16, 2.4), mb.words(), cls="mxb-sandbox is-booked", role="status"), cls="mxb-head"),
                    Div(_confetti(), Div(Div(*what, cls="mxb-pass-mid"), stub, cls="mxb-pass"), walletpass.buttons(done.booking_id, family), back, cls="mxb-confirm", data_step="booked"), cls="mxb", data_at="booked")
    out = page("Your booking", Div(Div(inner, cls="mx-side mx-alone mxb-page"), cls="mx mx-one"), current="/plan/matrix", head=mx.HEAD, noindex=True, v2=True, quiet=True)
    return FtResponse(out, status_code=status, headers={"Cache-Control": "no-store"})


def _day(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{day:%b} {day.day}"


def _confetti():
    """Paper thrown once when the pass appears (CSS only, assets/css/matrixbook.css; none under reduced motion). The colours are the kinds'."""
    return Div(*[Span(cls=f"mxb-cf c{i % 6}", style=f"--i:{i}; --x:{(i * 37) % 100}; --r:{(i * 53) % 360}; --d:{(i * 7) % 11}") for i in range(CONFETTI)], cls="mxb-confetti", aria_hidden="true")


def _pass_stay(d: mb.Done, address: str):
    return Div(P("Stay", cls="mxb-k"), P(d.hotel, cls="mxb-pass-h"), P(f"{d.place} · {_day(d.checkin)} to {_day(d.checkout)}" + (f" · {d.room}" if d.room else ""), cls="mx-r-s"),
               P(icon("pin", 14, 2.2), address, cls="mx-r-s mxb-addr") if address else "", cls="mxb-pass-row")


def _confirmation(s, lane, w, sq, prep: mb.Prep, res: mb.Result, who: str, extras=None, family: str = ""):
    """The stamped boarding pass (D-574): where, the flight, each stay with what the answer gives (the booking id, the hotel's confirmation code and its address), the test
    card, and a bold Plan this trip. Only what LiteAPI (or the sample) gave: no phone number or record locator is made up."""
    email, ex = extras if extras else ("", mb.Extras())
    phone = ex.phone
    sample = any(d.sample for d in res.done)
    address = {r.part.name: r.part.address for r in prep.rows}
    end = lane.places[0]
    route = Div(Span(s.home or "Home", cls="mxb-iata"), Span(cls="mxb-dash"), Span(icon("plane", 22, 2.2), cls="mxb-plane"), Span(cls="mxb-dash"), Span(end.iata or end.name, cls="mxb-iata"), cls="mxb-route")
    top = Div(mx._arts(lane, "mxb-pass-art"), route, Span("Sample" if sample else "Booked", cls="mxb-stamp", data_d=_day(w.depart.isoformat()).upper()), P(f"{tm.when(w)} · {mx.party_words(s)}", cls="mxb-pass-when"), cls="mxb-pass-top")
    mid = Div(Div(P("Flight", cls="mxb-k"), P(f"{sq.flight.airline} · {v2drawer.stops_words(sq.flight.stops).lower()}", cls="mxb-pass-h"), P(v2drawer.times(sq.flight.out), cls="mx-r-s"),
                  P(v2drawer.times(sq.flight.back), cls="mx-r-s") if sq.flight.back else "", P("Flight booking is next.", cls="mx-r-s"), cls="mxb-pass-row"),
              *[_pass_stay(d, address.get(d.hotel, "")) for d in res.done],
              Div(P("Lead guest", cls="mxb-k"), P(who, cls="mxb-pass-h"), P(" · ".join(x for x in (email, phone) if x), cls="mx-r-s") if (email or phone) else "",
                  P(icon("lock", 14, 2.2), "Paid with the " + ("sample" if sample else "LiteAPI test") + " card · nothing was charged", cls="mx-r-s"), cls="mxb-pass-row"),
              Div(P("Requests", cls="mxb-k"), P(", ".join(ex.requests) or "None", cls="mxb-pass-h"), P(f"Arriving in the {ex.arrive.lower()}", cls="mx-r-s") if ex.arrive else "", P("Passed to no one: the sandbox hotel is not sent them.", cls="mx-r-s"),
                  cls="mxb-pass-row") if ex.requests or ex.arrive else "",
              cls="mxb-pass-mid")
    stub = Div(*[Div(P("Booking id", cls="mxb-k"), P(Span(d.booking_id, cls="mxb-id", data_booking_id=d.booking_id), cls="mxb-code"),
                     *([P("Hotel confirmation", cls="mxb-k"), P(Span(d.confirmation, cls="mxb-id"), cls="mxb-code")] if d.confirmation else []), cls="mxb-stub-i") for d in res.done], cls="mxb-stub")
    return Div(_confetti(), H3("You’re going to " + lane.name + "!", cls="mxb-q mxb-going"),
               P(f"{who}, your {'sample ' if sample else ''}booking is confirmed.", cls="mxb-hint"), Div(top, mid, stub, cls="mxb-pass"),
               *[walletpass.buttons(d.booking_id, family) for d in res.done], A(icon("arrow-right", 22, 2.8), Span("Plan this trip"), href="/trip/plan?arrive=1", cls="mxb-plan", data_trip="1"),
               cls="mxb-confirm", data_step="booked")


def _problem(words: str):
    return Div(P(icon("bell", 18, 2.4), words, cls="mxb-note is-warn", role="alert"), A("Back to the square", href="#", cls="btn mxb-back", data_close="1"), cls="mxb-problem", data_step="problem")


def sheet(s, lane, w, *, sq=None, prep=None, pk=(0, (), ()), values=None, errors=None, note="", res=None, problem="", sample=False, who="", extras=None, pay=None, family=""):
    """The checkout's inside (a fragment: assets/js/matrixbook.js puts it in the sheet and settles it): the head and one body, the four questions or the pass."""
    if problem:
        body, at = _problem(problem), "room"
    elif pay is not None:
        body, at = pay_form(prep, *pay), "pay"
    elif res is not None and res.ok:
        body, at = _confirmation(s, lane, w, sq, prep, res, who, extras, family), "booked"
    else:
        body, at = Div(P(icon("bell", 16, 2.4), note, cls="mxb-note", role="status") if note else "", _checkout(s, lane, w, sq, prep, pk, values, errors), cls="mxb-body"), "guest"
    return Div(_head(s, lane, w, sample or (prep is not None and prep.sample) or (res is not None and any(d.sample for d in res.done)), booked=at == "booked"), body,
               cls="mxb", data_at=at, data_open=tm.key(lane.key, w.key))


def _answer(request, s, lane, w, inner, status=200):
    """The sheet as a fragment for the script, else as a page of its own (no script: the same words, the same two steps)."""
    if request.headers.get("x-matrix") == "1":
        return Response(to_xml(inner), media_type="text/html", status_code=status, headers={"Cache-Control": "no-store"})
    back = A(icon("chev-left", 18, 2.4), "Back to the matrix", href=mx.href(s, mx.SQUARE, lane=lane.key, w=w.key), cls="btn mx-back")
    out = page(f"Book {lane.name}", Div(back, Div(inner, cls="mx-side mx-alone mxb-page"), cls="mx mx-one"), current="/plan/matrix", head=mx.HEAD, noindex=True, v2=True, quiet=True)
    return FtResponse(out, status_code=status, headers={"Cache-Control": "no-store"})      # the payment form's key may be on it


def _family(session):
    return mx._family(session)


def _read(s, lane_key, w_key, family, pk):
    """(lane, window, square, choice): the square as it was shown (kept answers first), else asked again, with the flight and stays the person chose on it and that choice
    made to fit the square (a forged index is the shown part)."""
    lane, w, sq, _ = mx._square_of(s, lane_key, w_key, family, True)
    if lane is not None and sq is None:
        lane, w, sq, _ = mx._square_of(s, lane_key, w_key, family)
    if sq is None:
        return lane, w, sq, pk
    pk = tm.clamp(sq, pk)
    return lane, w, tm.pick(sq, *pk), pk


def _form(sample: bool) -> bool:
    """Is this booking paid in LiteAPI's payment form? A sample square is never (it books nothing)."""
    return mb.pays_by_form() and not mb.stands_in(sample)


def _prepare(s, lane, w, sq, family, voucher=""):
    dates = [(p.name, a, b) for p, a, b in tm.stays_for(lane, w)]
    prep = mb.prepare(sq.stays, dates, family, sample=mb.stands_in(sq.sample), sdk=_form(sq.sample), voucher=voucher)
    if prep.status == liteapi.GONE:
        liteapi.forget_stays()      # the kept rooms are stale: the matrix asks again
    return prep


def _square_of(s, lane, w, pk) -> tuple:
    """What a held room is bound to: the square's key, the address words it was asked with, and the flight and stays chosen on it."""
    return tm.key(lane.key, w.key), tuple(sorted((n, str(v)) for n, v in {**mx.params(s, lane=lane.key, w=w.key), **pick_fields(pk)}.items()))


def _same_offers(sq, prep) -> bool:
    """The held rooms are the square's chosen stays: LiteAPI's offer ids, or for the sample (no ids) the hotel and its price."""
    mark = lambda p: p.offer_id or (p.name, p.cents)
    return tuple(mark(p) for p in sq.stays) == tuple(mark(r.part) for r in prep.rows)


def _first_step(request, session, s, lane, w, sq, pk, user_id, note=""):
    family = _family(session)
    if not sq.ok or not sq.stays:
        return _answer(request, s, lane, w, sheet(s, lane, w, problem=tm.SAID.get(sq.status, "That square has no stay to book."), sample=mb.stands_in(sq.sample)))
    prep = _prepare(s, lane, w, sq, family)
    if not prep.ok:
        return _answer(request, s, lane, w, sheet(s, lane, w, problem=mb.SAID.get(prep.status, mb.SAID[liteapi.FAILED]), sample=mb.stands_in(sq.sample)))
    mb.hold(family, prep, _square_of(s, lane, w, pk))
    if _form(sq.sample):      # the ids LiteAPI cannot give back are saved the moment its prebook answers
        with ses.family(session) as fam:
            if not fam:
                return _answer(request, s, lane, w, sheet(s, lane, w, problem=SIGNIN, sample=False))
            mb.save_prebook(fam.db, prep.token, user_id, prep.rows[0], guests=_party(s))
    return _answer(request, s, lane, w, sheet(s, lane, w, sq=sq, prep=prep, pk=pk, note=note))


def _slowed(request, s, lane_key, w_key, problem=SLOW_DOWN, status=429):
    """A press the sheet refuses (too many presses: 429; booking not open yet: 403) from the address alone, with no search and no call."""
    lane = tm.lane(s.place, lane_key, s.nearby)
    w = tm.window(s.depart, s.return_, s.flex, catalog.today(), w_key)
    if lane is None or w is None:
        return RedirectResponse(mx.href(s), status_code=303)
    return _answer(request, s, lane, w, sheet(s, lane, w, problem=problem, sample=mb.stands_in(showcase.on())), status)


def _signed_out(s, lane_key, w_key):
    return RedirectResponse(ses.signin_href(mx.href(s, mx.SQUARE, lane=lane_key, w=w_key)), status_code=303)


def register(app):
    @app.post(mx.BOOK)
    def book_room(request, session, lane: str = "", w: str = "", fl: str = "", st: str = "", rm: str = "", to: str = "", home: str = "", d: str = "", r: str = "", a: str = "", k: str = "",
                  x: str = "", nb: str = "", b: str = ""):
        s = mx.state(to, home, d, r, a, k, x, nb, b)
        if s.problems:
            return RedirectResponse(mx.href(s), status_code=303)
        if mb.mode() == mb.SOON:      # a live key in production: the button is disabled, and a forged post is told so and books nothing (F-267, D-768)
            return _slowed(request, s, lane, w, mb.SOON_WORDS + ".", 403)
        me = ses.current_traveler(session)
        if not me:
            return _signed_out(s, lane, w)
        if not mb.allow(me.id):      # before anything is read: a refused press starts no search
            return _slowed(request, s, lane, w)
        pk = tm.picks(fl, st, rm)
        lane_, w_, sq, pk = _read(s, lane, w, _family(session), pk)
        if lane_ is None:
            return RedirectResponse(mx.href(s), status_code=303)
        return _first_step(request, session, s, lane_, w_, sq, pk, me.id)

    @app.post(CONFIRM)
    def book_confirm(request, session, lane: str = "", w: str = "", fl: str = "", st: str = "", rm: str = "", token: str = "", first: str = "", last: str = "", email: str = "", phone: str = "", req: str = "", arrive: str = "", agree: str = "", to: str = "",
                     home: str = "", d: str = "", r: str = "", a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        s = mx.state(to, home, d, r, a, k, x, nb, b)
        if s.problems:
            return RedirectResponse(mx.href(s), status_code=303)
        if mb.mode() == mb.SOON:      # a live key in production: the button is disabled, and a forged post is told so and books nothing (F-267, D-768)
            return _slowed(request, s, lane, w, mb.SOON_WORDS + ".", 403)
        me = ses.current_traveler(session)
        if not me:
            return _signed_out(s, lane, w)
        if not mb.allow(me.id):
            return _slowed(request, s, lane, w)
        family = _family(session)
        pk = tm.picks(fl, st, rm)
        lane_, w_, sq, pk = _read(s, lane, w, family, pk)
        if lane_ is None:
            return RedirectResponse(mx.href(s), status_code=303)
        prep = mb.held(family, token, _square_of(s, lane_, w_, pk))
        if prep is not None and not _same_offers(sq, prep):      # the square was read again and the same picks now name other rooms: never save one hotel while booking another
            prep = None
        if prep is None:      # restarted, kept too long, another family's or another square's (or another choice's) token: nothing is asked of LiteAPI
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, problem=STALE, sample=mb.stands_in(sq.sample)))
        guest, errors = mb.clean_guest(first, last, email)
        extras, more = mb.clean_extras(phone, req, arrive)
        form = _form(prep.sample)
        errors = {**errors, **more, **({} if agree == "on" else {"agree": TICK}), **({"phone": NEEDS_PHONE} if form and not extras.phone and "phone" not in more else {})}      # the required tick is the server's rule too, not only the page's
        typed = {"first": first[:mb.NAME_MAX], "last": last[:mb.NAME_MAX], "email": email[:mb.EMAIL_MAX], "phone": phone[:mb.PHONE_MAX], "req": "|".join(extras.requests),
                 "arrive": extras.arrive, "agree": agree}
        if errors:
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, sq=sq, prep=prep, pk=pk, values=typed, errors=errors))
        try:
            trip_id = mx.save(session, s, lane_, w_, sq)      # the square becomes the family's trip, as Save to trip does
        except importer.SaveError as e:
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, problem=str(e), sample=prep.sample))
        if form:      # LiteAPI's payment form is next; the lead guest is kept only until the booking after it (D-842)
            with ses.family(session) as fam:
                if not fam:
                    return _answer(request, s, lane_, w_, sheet(s, lane_, w_, problem=SIGNIN))
                kept = mb.pay_start(fam.db, prep.token, me.id, mb.with_extras(guest, extras), trip_id)
            if not kept:
                return _answer(request, s, lane_, w_, sheet(s, lane_, w_, problem=STALE))
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, sq=sq, prep=prep, pk=pk, pay=(prep.rows[0].prebook.secret_key, return_url(request, prep.token))))
        with ses.family(session) as fam:
            if not fam:      # the family went away between the steps: sign in again, nothing was asked of LiteAPI
                return _answer(request, s, lane_, w_, sheet(s, lane_, w_, problem=SIGNIN, sample=prep.sample))
            res = mb.book(prep, guest, fam.db, family, trip_id, me.id)
        if res.done:
            mb.add_to_trip(session, trip_id, res.done)
        if res.ok:
            return _answer(request, s, lane_, w_, sheet(s, lane_, w_, sq=sq, prep=prep, pk=pk, res=res, who=f"{guest.first} {guest.last}", extras=(guest.email, extras), family=family))
        said = mb.SAID.get(res.status, mb.SAID[liteapi.FAILED])
        left = f" {len(res.done)} of {len(prep.rows)} stays are booked; press Book again for the rest." if res.done else ""
        return _answer(request, s, lane_, w_, sheet(s, lane_, w_, sq=sq, prep=prep, pk=pk, values={**typed, "first": guest.first, "last": guest.last, "email": guest.email}, note=said + left))


    @app.post(CODE)
    def book_code(request, session, lane: str = "", w: str = "", fl: str = "", st: str = "", rm: str = "", token: str = "", code: str = "", to: str = "", home: str = "", d: str = "", r: str = "",
                  a: str = "", k: str = "", x: str = "", nb: str = "", b: str = ""):
        """"Have a code?": prebook the held stay again with the code (or without, to take it off): a JSON answer with the new token and the totals, the discount shown only here."""
        s = mx.state(to, home, d, r, a, k, x, nb, b)
        refuse = lambda words, status: JSONResponse({"error": words}, status_code=status, headers={"Cache-Control": "no-store"})
        if s.problems or not mb.pays_by_form():
            return refuse("That cannot be done here.", 400)
        me = ses.current_traveler(session)
        if not me:
            return refuse(SIGNIN, 401)
        if not mb.allow(me.id):
            return refuse(SLOW_DOWN, 429)
        family = _family(session)
        pk = tm.picks(fl, st, rm)
        lane_, w_, sq, pk = _read(s, lane, w, family, pk)
        if lane_ is None or sq is None or not sq.ok or not sq.stays or not _form(sq.sample):
            return refuse(STALE, 409)
        held = mb.held(family, token, _square_of(s, lane_, w_, pk))
        if held is None or not _same_offers(sq, held):
            return refuse(STALE, 409)
        voucher, bad = mb.code_shape(code)
        if voucher and not mb.codes_open():
            return refuse(CODES_OFF, 403)
        if bad:
            mb.code_missed()
            return refuse(bad, 422)
        prep = _prepare(s, lane_, w_, sq, family, voucher)
        if prep.status == liteapi.BAD_CODE:
            mb.code_missed()
        if not prep.ok:
            return refuse(mb.SAID.get(prep.status, mb.SAID[liteapi.FAILED]), 422 if prep.status == liteapi.BAD_CODE else 502)
        mb.hold(family, prep, _square_of(s, lane_, w_, pk))
        with ses.family(session) as fam:
            if not fam:
                return refuse(SIGNIN, 401)
            mb.save_prebook(fam.db, prep.token, me.id, prep.rows[0], guests=_party(s))
        f = sq.flight
        discount = sum(r_.prebook.discount_cents for r_ in prep.rows)
        return JSONResponse({"token": prep.token, "code": voucher, "stay": catalog.money(prep.total_cents), "total": catalog.money(f.cents + prep.total_cents), "discount": catalog.money(discount) if discount else "",
                             "go": f"Continue · {catalog.money(prep.total_cents)}", "moved": to_xml(_moved(prep)) if prep.changed else "",
                             "said": f"Code {voucher} applied." if discount else ("Code removed." if not voucher else f"Code {voucher} did not change the price.")},
                            headers={"Cache-Control": "no-store"})

    @app.get(RETURN)
    def book_return(request, session, token: str = ""):
        """Where LiteAPI's payment form sends the browser after paying (D-842): the stay is booked once with the transaction id saved at prebook (a reload finds the stored booking), added to
        the trip, and the pass is drawn. LiteAPI refuses a transaction that was not paid, so nothing is trusted from the address but the token, which is this person's own row."""
        if not _TOKEN.match(token):      # no check that booking is switched on: a guest who paid is finished whatever the switch says (D-848)
            return RedirectResponse("/plan/ask", status_code=303)
        me = ses.current_traveler(session)
        if not me:
            return RedirectResponse(ses.signin_href(f"{RETURN}?token={token}"), status_code=303)
        if not access.can_edit(access.request_role()):
            return _paid_page(None, None, "Only an editor in your family can book.", status=403)
        family = _family(session)
        with ses.family(session) as fam:
            if not fam:
                return RedirectResponse(ses.signin_href(f"{RETURN}?token={token}"), status_code=303)
            res = mb.finish(fam.db, family, token, me.id)
            pay = mb.payment(fam.db, token)
        if pay and pay.get("user_id") != me.id:      # another person's row is nothing of ours to describe (L2)
            pay = None
        if not res.ok:
            kept = f" Payment reference: {pay['transaction_id']}." if pay and pay.get("transaction_id") and pay.get("status") == "paying" else ""
            paying = bool(pay and pay.get("status") == "paying")
            return _paid_page(None, None, (PAID_BUT if paying else "We could not find that booking.") + kept, status=502 if paying else 404)
        done = res.done[0]
        mb.add_to_trip(session, done.trip_id, res.done)
        return _paid_page(done, pay, family=family)
