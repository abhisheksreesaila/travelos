"""The paper map's geo pack table (F-201): one row per trip, written by gitaway/geopack.py.

Part of the family database (gitaway.familydb appends GEOPACK_TABLES to its FAMILY_TABLES). The row links the trip to the pack built for its region (the
images and shapes are shared by region in the community database's `geo_regions`, which holds no person) and keeps the trip's build attempts, so a daily
budget and the wait after a failure survive a restart. The box is worked out from the trip's own places, so the row is the family's data like `geo_cache`;
it goes when the trip is deleted (gitaway.importer.delete) and is never written for a trip that is gone.
"""


class GeoPack:
    """`region` and `key` name the linked pack (`version` is gitaway.geopack.VERSION when it was linked; `box` is "west,south,east,north"); `day` is the UTC
    day the `attempts` were counted on; `failed_at` (ISO, UTC) and `error` (what failed, never where) are the last failure's, cleared when a pack is linked."""
    trip_id: str
    region: str = ""
    key: str = ""
    version: int = 0
    box: str = ""
    built_at: str = ""
    day: str = ""
    attempts: int = 0
    failed_at: str = ""
    error: str = ""


GEOPACK_TABLES = [(GeoPack, "geo_packs", "trip_id")]
