"""One switch for sample data (F-064): the live site shows only what's real.

`on()` is true on a local copy and false in production (`auth.production()`). GITAWAY_SHOWCASE=1 or 0 overrides it, so tests and
screenshots can see either mode without touching the production lock on the dev sign-in.

When it is off there are no sample trips anywhere: no Community trips, creators, forks, saves or sharing, no sample itineraries (names,
fork counts), no `?demo=long` calendar, no pretend-friends invite. Their routes answer 404 (`guard`) and nothing links to them. What stays:
the landing's illustrations, and the booking workspace, labelled a preview with sample prices.
"""

import os
import re

from fasthtml.core import FtResponse

from gitaway import auth

# Paths (and everything under them) that exist only for sample or community content.
HIDDEN = ("/community", "/discover", "/creators", "/forks", "/share", "/save", "/unsave", "/fork",
          "/calendar/friends", "/calendar/live", "/calendar/voice")  # the last two: the demo trip's pretend friends
_NOT_ITINERARY = ("build", "import", "switch")  # /trips/<word> routes that are the family's own
_ITINERARY = re.compile(r"/trips/([^/]+)/?")

PREVIEW = "Preview: sample prices, nothing is booked."


def on() -> bool:
    flag = os.getenv("GITAWAY_SHOWCASE", "").strip()
    if flag in ("0", "1"):
        return flag == "1"
    return not auth.production()


def hidden(path: str, query=None) -> bool:
    """Is this request for something that does not exist when the showcase is off?"""
    if any(path == p or path.startswith(p + "/") for p in HIDDEN):
        return True
    m = _ITINERARY.fullmatch(path)
    if m and m.group(1) not in _NOT_ITINERARY:  # /trips/<slug>: a sample or community itinerary page
        return True
    return bool(query is not None and query.get("demo") == "long")  # the 20-day calendar fixture


async def guard(req, sess):
    """Beforeware: 404 for everything `hidden` while the showcase is off."""
    if on() or not hidden(req.url.path, req.query_params):
        return None
    from gitaway.layout import page
    from fasthtml.common import A, Div, H1, P, Section
    return FtResponse(page("Not found", Section(Div(H1("Nothing here"), P("That page isn't part of GitAway."), A("Back home", href="/", cls="btn btn-primary")),
                                                 cls="ga-soon ga-wrap")), status_code=404)
