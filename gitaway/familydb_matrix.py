"""A trip matrix square saved to the family's trip (F-222), and the stays booked from one through LiteAPI's sandbox (F-233).

Part of the family database (gitaway.familydb appends MATRIX_TABLES to its FAMILY_TABLES; a new table needs no migration). One row per square a family saved,
keyed by the trip and the square, so pressing Save twice keeps one row (the newer price). The words and prices are what the source said when it was saved
(gitaway/gridsource.py `square`), with `fetched` its age: a quote, never a booking. Written only by gitaway/pages/tripmatrix.py.
"""


class MatrixSave:
    id: str                 # the trip id and the square's key, hashed
    trip_id: str
    user_id: str = ""
    lane: str               # "Los Angeles + San Diego"
    depart: str             # ISO dates
    return_: str
    total_cents: int = 0
    flight: str = ""        # "United Airlines · Sat, Dec 12 · SFO 8:05 AM → LAX 9:32 AM · Nonstop"
    stays: str = ""         # "2 nights at Hotel A, Los Angeles · 2 nights at Hotel B, San Diego"
    fetched: str = ""       # when the price was fetched (ISO), "" for sample prices
    sample: int = 0
    saved_at: str


class MatrixBooking:
    """A stay booked through LiteAPI's sandbox from a matrix square (F-233, D-480). No personal data: the lead guest's name and email go to LiteAPI and are not kept (D-510). One row per stay booked (a two-place square books two)."""
    id: str                 # the client reference sent to LiteAPI (the idempotency key), so a second press finds this row
    trip_id: str = ""       # the family trip this stay became ("" if the trip could not be made)
    user_id: str = ""
    booking_id: str         # LiteAPI's booking id (a sample booking: "SAMPLE-" and the reference)
    place: str = ""
    hotel: str
    room: str = ""
    checkin: str
    checkout: str
    total_cents: int = 0    # what LiteAPI says the stay costs, taxes included
    due_at_stay_cents: int = 0   # of it (or on top, as the source said) paid at the hotel
    refundable: int = 0
    confirmation: str = ""  # the hotel's confirmation code ("test" in the sandbox)
    sample: int = 0         # 1: made on the showcase's sample squares, nothing was sent to LiteAPI
    created_at: str


class MatrixPayment:
    """A stay prebooked for LiteAPI's payment form (F-274, D-842): saved the moment the prebook answers, because LiteAPI cannot give the `prebookId` and `transactionId` back later.
    The card is never ours (LiteAPI's form takes it, Nuitée is the merchant): this row holds the ids, the amounts and the lead guest only for as long as the booking needs him or her
    (`guest_*`, the name, email, mobile number and requests, are blanked once the booking is made, or after 7 days)."""
    id: str                 # the sheet's token, the idempotency key's base (`matrixbook.reference`)
    user_id: str = ""
    trip_id: str = ""
    place: str = ""
    hotel: str = ""
    room: str = ""
    checkin: str = ""
    checkout: str = ""
    prebook_id: str = ""
    transaction_id: str = ""
    charge_cents: int = 0   # what the card is charged for the stay (the voucher's discount taken off)
    due_at_stay_cents: int = 0
    refundable: int = 0
    voucher_code: str = ""
    discount_cents: int = 0
    policy: str = ""        # the refund policy as it was shown before paying (matrixbook.policy_words)
    status: str = "prebooked"   # prebooked, then paying (the guest is saved and the form is shown), then booked; or unpaid (LiteAPI said the form was never paid: given up, deleted by the purge);
    # or needs_help (paid perhaps, not booked after the hour: kept, listed on /admin, still retried) and resolved (the captain dealt with it: deleted by the purge).
    # `attempts` and `next_try_at` (the worker's back-off) are NOT here: migrations/family/004_payment_backoff.sql adds them, so fresh and older databases both get them (D-851)
    booking_id: str = ""
    guest_first: str = ""
    guest_last: str = ""
    guest_email: str = ""
    guest_phone: str = ""
    guest_remarks: str = ""
    created_at: str = ""
    updated_at: str = ""


class MatrixCancel:
    """A LiteAPI booking cancelled from the booking page (F-274): what LiteAPI said came back. One row a booking."""
    booking_id: str
    user_id: str = ""
    status: str = ""        # CANCELLED or CANCELLED_WITH_CHARGES
    refund_cents: int = 0
    fee_cents: int = 0
    cancelled_at: str = ""


class FlightPayment:
    """A flight prebooked for LiteAPI's payment form (F-276, D-972, D-974): saved the moment the prebook answers (LiteAPI cannot give the ids back). The card is never ours. `travellers` holds
    the passengers and the contact LiteAPI's booking needs (names, birth dates, passport numbers, email, phone): personal data, blanked the moment the flight is booked (`contact` keeps only the
    lead's first name and email until the tickets email is sent, 7 days at most), never logged, never sent anywhere but LiteAPI and the lead's own email."""
    id: str                 # the sheet's token (also the stay's), the idempotency key's base
    user_id: str = ""
    trip_id: str = ""
    status: str = "paying"  # paying (the form is shown), booking (the book call is in flight: one caller only), booked, expired (LiteAPI says the prebook is gone), needs_help (the book may have gone through)
    prebook_id: str = ""
    transaction_id: str = ""
    charge_cents: int = 0   # what the card is charged for the flight
    airline: str = ""
    route: str = ""         # "SFO to SAN"
    legs: str = ""          # JSON: the flights (direction, origin, destination, depart, arrive, airline, code, number)
    facts: str = ""         # JSON: the fare family, bags, refundable, changeable, as shown before paying
    party: str = ""         # "2 adults, 1 kid"
    stay_token: str = ""    # the stay this flight is booked with, paid next (its own payment row, `matrix_payments`)
    back_href: str = ""     # the square's address, for "try again" when the stay cannot follow
    travellers: str = ""    # JSON, see above
    contact: str = ""       # JSON {first, email}: kept after booking only for the tickets email
    booking_id: str = ""
    created_at: str = ""
    updated_at: str = ""


class FlightBooking:
    """A flight booked through LiteAPI (F-276), or a labelled sample one (nothing was sent). One row a booking (both ways of a round trip). No passenger data: it is in `matrix_flight_payments`
    until booked, then gone. The status follows LiteAPI's lookup (`flightbook.refresh`)."""
    id: str                 # our reference: family, token and "flight" hashed
    trip_id: str = ""
    user_id: str = ""
    booking_id: str         # LiteAPI's (a UUID); a sample booking: "SAMPLE-" and the reference
    ref: str = ""           # LiteAPI's short reference, the one to read out ("FH-26B-1VO6TJ6Z")
    pnr: str = ""           # the order's locator
    locators: str = ""      # JSON [[airline code, the airline's own PNR], ...]
    status: str = "PENDING_CONFIRMATION"   # LiteAPI's: PENDING_CONFIRMATION, CONFIRMED, CANCELLED, CANCELLED_WITH_CHARGES, ...
    payment_status: str = ""
    total_cents: int = 0
    airline: str = ""
    legs: str = ""
    facts: str = ""
    party: str = ""
    ticket_limit: str = ""
    sample: int = 0
    checks: int = 0         # how many times the worker has asked LiteAPI whether it is confirmed
    next_check_at: str = ""
    booked_email_at: str = ""   # the markers of the emails, each sent once (`bookingmail`)
    tickets_email_at: str = ""
    cancel_email_at: str = ""
    quote_at: str = ""      # the cancel quote last shown and what it said: a cancel is only made after one
    quote_refund_cents: int = 0
    quote_fee_cents: int = 0
    created_at: str = ""


MATRIX_TABLES = [(MatrixSave, "matrix_saves", "id"), (MatrixBooking, "matrix_bookings", "id"), (MatrixPayment, "matrix_payments", "id"), (MatrixCancel, "matrix_cancels", "booking_id"),
                 (FlightPayment, "matrix_flight_payments", "id"), (FlightBooking, "matrix_flights", "id")]
