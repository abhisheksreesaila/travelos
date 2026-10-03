"""The family's photos table (F-071): one row per photo a member added to a trip.

Part of the family database (gitaway.familydb appends PHOTO_TABLES to its FAMILY_TABLES, like familydb_thread). The files are on disk under
`<data folder>/photos/<family>/<trip>/` (paths here are relative to `<data folder>/photos`); the logic is gitaway/photos.py.
"""


class Photo:
    """A photo on a trip. `taken_at` is ISO 8601 with its offset in the trip's time zone (the camera's own time when it has one, else when it was
    added); `taken_date` ("2026-10-05") and `taken_min` (minutes after midnight) are the same moment as the trip's clock showed it, for
    grouping and matching. `lat`/`lon` are the camera's position (None when the photo carries none); they stay in this database and are
    never in the files served to anyone. `plan_id` / `plan_title` are the plan it was matched to ("" for the day alone). `orig`, `display`
    and `thumb` are the stored files, relative to the photos folder; only the last two are ever served."""
    id: str
    trip_id: str
    author: str
    author_name: str = ""
    taken_at: str
    taken_date: str
    taken_min: int = 0
    lat: float = None
    lon: float = None
    plan_id: str = ""
    plan_title: str = ""
    caption: str = ""
    orig: str
    display: str
    thumb: str
    created_at: str


PHOTO_TABLES = [(Photo, "photos", "id")]
PHOTO_INDEXES = [("photos", ["trip_id", "taken_date"], False, "ix_photos_trip_day")]
