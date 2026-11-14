"""A trip matrix square saved to the family's trip (F-222): "Booking opens soon", so a square is kept, never booked.

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
    """A stay booked through LiteAPI's sandbox from a matrix square (F-233, D-480). Personal data: the lead guest's name and email, kept only to show the confirmation
    again; never logged, always escaped on output. One row per stay booked (a two-place square books two)."""
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
    guest_name: str
    guest_email: str
    sample: int = 0         # 1: made on the showcase's sample squares, nothing was sent to LiteAPI
    created_at: str


MATRIX_TABLES = [(MatrixSave, "matrix_saves", "id"), (MatrixBooking, "matrix_bookings", "id")]
