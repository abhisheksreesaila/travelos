"""The paper map's geo pack table (F-201): one row per trip, made by gitaway/geopack.py.

Part of the family database (gitaway.familydb appends GEOPACK_TABLES to its FAMILY_TABLES). The box it covers is worked out from the trip's own places,
so the row is the family's data like `geo_cache`; it goes when the trip is deleted (gitaway.importer.delete).
"""


class GeoPack:
    """The trip's paper map: `box` "west,south,east,north" in degrees, `shapes` the OpenStreetMap roads, lakes, towns and borders as JSON, `light` and `dark`
    the relief images (WebP bytes), `size` the three together in bytes. `key` names this build and is part of the addresses the page loads (a browser may keep
    them for good); `version` is gitaway.geopack.VERSION when it was built, so a change in how packs are drawn rebuilds the old ones."""
    trip_id: str
    key: str
    version: int = 1
    box: str
    shapes: str
    light: bytes
    dark: bytes
    size: int = 0
    built_at: str


GEOPACK_TABLES = [(GeoPack, "geo_packs", "trip_id")]
