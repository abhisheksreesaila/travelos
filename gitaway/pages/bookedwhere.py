""""Booked on <partner>" and "Change or cancel" (F-198): one line for every booking of a trip, on its sheet and on the trip's details page.

The button opens the partner's own manage-booking page (gitaway/partners/manage.py) in a new tab: the partner keeps the booking, its changes and its refunds; GitAway never does.
A booking whose partner we were not told says "Booked elsewhere" and has no button.
"""

from fasthtml.common import A, Div, Span

from gitaway import tripcal as cal
from gitaway.icons import icon
from gitaway.partners import manage


def line(kind, item, plan, ident=""):
    where, site = manage.for_booking(kind, item, cal.booked_on(plan, item))
    words = Span(f"Booked on {where}" if where else "Booked elsewhere", cls="bk-where-t")
    go = A(icon("arrow-right", 15, 2.6), "Change or cancel", href=site.url, target="_blank", rel="noopener", cls="tp-btn tp-btn-white bk-manage", data_site=site.name,
           aria_label=f"Change or cancel on {site.name} (opens {site.name})") if site else ""
    return Div(icon("lock", 13, 2.4), words, go, cls="bk-where", **({"id": ident} if ident else {}))
