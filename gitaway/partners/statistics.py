"""A simulated conversion, shaped like a row of the Travelpayouts booking-statistics API (D-22).

Real rows (affiliate-programs booking statistics) carry `marker`, `sub_id`, `price`, `profit`, `state` and `booked_at` (plus program and
currency fields we do not need). A sandbox booking produces one row, so the day the real endpoint is wired (TRAVELPAYOUTS_TOKEN)
`/partners` reads the same shape. Amounts here are decimal dollars like the API; GitAway keeps cents.
"""

from gitaway.partners import travelpayouts


def row(click) -> dict:
    """The statistics row for a booked click (a click row of the family database)."""
    return {"marker": travelpayouts.marker() or "sandbox", "sub_id": click["sub_id"], "price": click["price_cents"] / 100, "profit": click["commission_cents"] / 100,
            "state": "processing", "booked_at": click["booked_at"]}

