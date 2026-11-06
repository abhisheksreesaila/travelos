"""A trip's publishing draft (F-181): what a family editor chose to put on the public page of one trip.

Part of the family database (gitaway.familydb appends PUBLISH_TABLES to its FAMILY_TABLES). One row per trip. It holds the choices, never a copy of
the family's data: the photos picked (ids of the family's own photos), a note per day, tips, the cover, the stickers, the title and the name shown.
`slug` is the stable public address (made once); `published_by` and `published_at` are set while the trip is live. The logic is gitaway/publish.py.
"""


class Publication:
    trip_id: str
    slug: str
    title: str = ""
    name: str = ""            # the creator name shown on the public page
    cover: str = ""           # id of one of the trip's photos, or ""
    stickers: str = "[]"      # JSON list of hub tag keys (kid, pet, couple)
    notes: str = "{}"         # JSON {"<day number>": "short note"}
    tips: str = "[]"          # JSON list of short tips
    photos: str = "[]"        # JSON list of the picked photo ids, in the order shown
    copies: str = "{}"        # JSON {photo id: public file name}: the re-encoded public copies made at publish time
    published_by: str = ""    # user id of the person who published, "" while it is a draft
    published_at: str = ""
    updated_at: str = ""


PUBLISH_TABLES = [(Publication, "publications", "trip_id")]
