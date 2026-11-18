"""Places GitAway knows and where a booking made elsewhere is managed (F-198). GitAway has no affiliate links of any kind (F-297, D-971): hotels and flights are booked here through LiteAPI.

`places` is the place table the trip matrix and the sentence use, `manage` the partner's own change-or-cancel page for a booking a family pasted or imported, and `uber_deep_link`
the ride link on Today (no account, no key, nothing of ours on it).
"""

from urllib.parse import quote


def uber_deep_link(pickup: str, dropoff: str) -> str:
    """Uber's universal deep link (the ride lane): opens the Uber app, or m.uber.com, with the pickup and dropoff filled in. No account, no key."""
    start = f"pickup[formatted_address]={quote(pickup)}" if pickup else "pickup=my_location"
    return f"https://m.uber.com/ul/?action=setPickup&{start}&dropoff[formatted_address]={quote(dropoff)}"
