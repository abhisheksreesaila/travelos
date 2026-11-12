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


MATRIX_TABLES = [(MatrixSave, "matrix_saves", "id")]
