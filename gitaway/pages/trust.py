"""How GitAway keeps you safe (F-292, D-943..D-945): GET /trust, a short reading page for a stranger deciding whether to put a card and a name into a newcomer's site.

Every sentence is a claim about the code, and tests/test_trust.py pins each one to the fact it rests on. Change one of these and read the page again; add a claim only with its evidence.
Written in plain words, never as a certification. Evidence, as of F-292 (file:line at the time of writing):

  card      "Your card goes only into Nuitée (LiteAPI)'s own payment form ... GitAway has no card field":
            gitaway/pages/matrixbook.py `pay_form` draws an empty div the form fills (no <input> for a card; tests/test_trust.py checks the sheet and the pay pane for card fields);
            gitaway/liteapi.py:1154-1169 `_allowed`: a live key may only prebook with `usePaymentSdk: true` and no `payment`, and book only with `TRANSACTION_ID`, so ACC_CREDIT_CARD (the
            LiteAPI account's own card) is refused (tests/test_liteapi_pay.py::test_a_live_key_can_never_send_the_sandbox_card); the form's script is the one other-site script of the booking sheet
            (liteapi.py:53 PAYMENT_SDK). Stripe (Plan it for me) is the same by its own page: gitaway/pages/legal.py's privacy page says so; the sentence shows only while `planforme.paid()`.
  guest     "name, email and mobile number go to LiteAPI to make the booking ... erased ... within 7 days":
            gitaway/matrixbook.py:545 `finish` blanks `guest_first/last/email/phone/remarks` in the same UPDATE that marks the row booked; :470-480 `purge` blanks them for any row older than
            `PURGE_GUEST` (:49, 7) days, and the booked email is composed before the blanking (bookingmail.booked). gitaway/bookingjobs.py:26,149 runs `purge` over every family once a day.
            LiteAPI keeps its own record: the privacy page (pages/legal.py `_liteapi_words`) says it.
  sign-in   "Google or a passkey ... no password": gitaway/pages/signin.py (Google and passkey buttons, "No password to remember"), gitaway/passkeys.py:4 (only the public key is stored);
            no password field or hash exists in auth.py, passkeys.py, members.py or the sign-in page (tests/test_trust.py).
  scripts   "no analytics service ... the only scripts from other sites": tests/test_no_cdn_scripts.py (every page loads its own scripts; the allow-list is Travelpayouts Drive); the payment
            form (liteapi.py:53); assets/js/aerial.js:10 `HOSTS` (unpkg.com for MapLibre, cdn.jsdelivr.net for Cesium, loaded only after the "See it from above" tap) and its map tiles
            (OpenFreeMap; Google only with GOOGLE_MAPS_API_KEY); gitaway/pages/home.py:24-30 `_drive`, Travelpayouts' site-verification script on the signed-out front page only, only when
            TRAVELPAYOUTS_DRIVE_ID is set. "No ad trackers" is NOT claimed: Drive is an affiliate partner's script and this page does not argue what it is (D-944).
  counts    "reader counts ... a short code from a random value thrown away each day, no cookie": gitaway/stats.py:1-9 and `_salt_of` (:44), `searcher` (:70): the salt lives in memory
            for the day; no cookie is set there (`ga_via` is another thing: gitaway/affiliate.py, only when a creator's trip is tapped, and the privacy page says so).
  email     "a booking email never writes the address or name to a log": gitaway/bookingmail.py:197-241 log the booking id only, no exception text (a server's refusal repeats the
            address); fh-saas's `send_email`, which logs the recipient, is not used (module docstring). Tests: tests/test_bookingmail.py, tests/test_trust.py.
  review    "money, sign-in and personal-data changes get a separate security review before they go live": true of the process (docs/plan.md tickets F-274, F-285, F-288 carry the
            "security review" check; AGENTS.md, `Risk: high`), not of the code, and said as a practice, not as a certification.
  contact   GITAWAY_CONTACT_EMAIL through `legal.contact`, as /privacy and /terms do.
"""

from fasthtml.common import A, Div, H1, H2, P, Section

from gitaway import matrixbook as mb, planforme
from gitaway.layout import reading
from gitaway.pages import legal

TITLE = "How GitAway keeps you safe"


def claims() -> list[tuple[str, str]]:
    """(heading, sentence) for each claim, in order. The sentences are what the page says word for word (tests read them from here and from the page)."""
    card = ("Your card goes only into the payment form of Nuitée (LiteAPI), which sells and charges for every stay booked here and is its merchant of record. GitAway has no card field, "
            "so it never sees, handles or keeps a card number.")
    if planforme.paid():
        card += " Plan it for me, which is paid, takes its card on Stripe's own page, the same way."
    return [
        ("Who sells it, and who takes your card", card),
        ("What we do with the lead guest's details",
         f"To make a booking we send LiteAPI the lead guest's first and last name, email and mobile number. GitAway erases them from its own records as soon as the booking is made, and in any case "
         f"within {mb.PURGE_GUEST} days. LiteAPI keeps its own record of the booking under its own rules."),
        ("Signing in", "You sign in with Google, or with a passkey (Face ID or your device's lock). GitAway has no password for you to choose, so there is none to store or lose."),
        ("Scripts and tracking",
         "GitAway uses no analytics service. Its pages load their scripts from GitAway itself, apart from these: LiteAPI's payment form, only when you pay; the map libraries and map pictures "
         "behind \"See it from above\", only after you tap it; and, only while it is switched on and only on the front page you see signed out, Travelpayouts' site-verification script, "
         "our affiliate partner's. The privacy policy says what each one gets."),
        ("Counting visitors",
         "Readers of a published trip, and a signed-out visitor's daily searches, are counted from a short code made from a random value that is thrown away each day. It cannot be turned back "
         "into a person, and it needs no cookie."),
        ("Booking emails", "The email that confirms or cancels a booking is sent without writing your address or name to any log."),
        ("How changes are checked",
         "A change that touches payments, sign-in or personal data gets a separate security review before it goes live. That is how we work, not a certification."),
    ]


def trust():
    body = [Section(H2(heading), P(text), cls="lg-sec") for heading, text in claims()]
    body.append(Section(H2("How to reach us"), legal.contact(then=" with a question, or to have your data deleted.", id="trust-contact"), cls="lg-sec"))
    return reading(TITLE, Div(H1(TITLE), P("Plain words, each one true of how GitAway works today.", cls="lg-lead"), *body,
                              P(A("Privacy policy", href="/privacy"), " · ", A("Terms", href="/terms"), " · ", A("Back to GitAway", href="/"), cls="lg-more"), cls="pg-card lg-doc"),
                   head=legal.HEAD, description="What GitAway does and does not do with your card, your details and your clicks.")


def register(app):
    app.get("/trust")(trust)
