"""The family's partner clicks and simulated bookings (autopilot M2/M3), one row per click on a "Book on <partner>" link.

Part of the family database (gitaway.familydb appends PARTNER_TABLES to its FAMILY_TABLES; a new table needs no migration). `state` is
"clicked" until a sandbox booking completes it ("booked"). `sub_id` is the Travelpayouts SubID sent with the click: a short hash of the
family plus the place, dates and lane, never a name or an address. Written only by gitaway/partners/log.py.
"""


class PartnerClick:
    id: str
    user_id: str = ""
    offer_id: str
    partner: str
    lane: str
    offer_name: str
    place: str = ""
    query: str = ""         # the trip as catalog.trip_query writes it, to rebuild the offer's price
    sub_id: str
    price_cents: int = 0
    state: str = "clicked"  # clicked | booked
    clicked_at: str
    booked_at: str = ""
    commission_cents: int = 0
    confirmation: str = ""
    trip_id: str = ""       # the family trip the booking was added to


PARTNER_TABLES = [(PartnerClick, "partner_clicks", "id")]
