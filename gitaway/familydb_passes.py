"""The family's flights and boarding passes (F-083): the `pass_flights` and `passes` tables of the family database.

Part of the family database (gitaway.familydb appends PASS_TABLES to its FAMILY_TABLES, like familydb_photos). The files are on disk under
`<data folder>/passes/<family>/<trip>/` (paths here are relative to `<data folder>/passes`); the logic is gitaway/passes.py.
"""


class PassFlight:
    """A flight an editor added by hand (an imported trip's flights are read from its template and are not copied here). `fly_on` is the ISO date and
    `depart_min` the minutes after midnight, both local to the airport it leaves from. `terminal` and `app_url` are optional ("" when not given)."""
    id: str
    trip_id: str
    airline: str
    number: str
    origin: str
    dest: str
    fly_on: str
    depart_min: int = 0
    terminal: str = ""
    created_by: str = ""
    created_at: str


class TravelPass:
    """One traveller on one flight. `flight_key` is "leg:<n>" (the nth flight of an imported trip) or "f:<id>" (a `pass_flights` row). `traveller` is the
    name shown; `member_id` is the family member it matches ("" for a name that is not a member). `grp` is the boarding group, `boards_min` the
    boarding time in minutes after midnight (None when not given). `kind` is "pdf", "image" or "" (no file); `orig` is the file as it came and
    `display` / `thumb` the pictures made from it, all relative to the passes folder. Only the family sees any of them. `app_url` is an https
    link to the airline's app or page that an editor pasted; it is never guessed."""
    id: str
    trip_id: str
    flight_key: str
    traveller: str
    member_id: str = ""
    seat: str = ""
    grp: str = ""
    gate: str = ""
    boards_min: int = None
    app_url: str = ""
    kind: str = ""
    orig: str = ""
    display: str = ""
    thumb: str = ""
    created_by: str = ""
    created_at: str


PASS_TABLES = [(PassFlight, "pass_flights", "id"), (TravelPass, "passes", "id")]
PASS_INDEXES = [("pass_flights", ["trip_id"], False, "ix_pass_flights_trip"), ("passes", ["trip_id", "flight_key"], False, "ix_passes_trip_flight")]
