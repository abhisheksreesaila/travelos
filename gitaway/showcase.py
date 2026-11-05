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
          "/rides",  # the simulated Uber (rides)
          "/sandbox")  # the stand-in partner checkout (M3): partners keep real bookings, there is nothing to stand in for
_NOT_ITINERARY = ("build", "import", "switch")  # /trips/<word> routes that are the family's own
_ITINERARY = re.compile(r"/trips/([^/]+)/?")

PREVIEW = "Preview: sample prices, nothing is booked."


def on() -> bool:
    flag = os.getenv("GITAWAY_SHOWCASE", "").strip()
    if flag in ("0", "1"):
        return flag == "1"
    return not auth.production()


def _needs_keys(path: str) -> bool:
    """Pages that exist off the showcase only with real partner keys: /partners reads real statistics (TRAVELPAYOUTS_TOKEN) and /go/... sends a
    traveler to a real tracked link (TRAVELPAYOUTS_MARKER); without them there is nothing real to show or send anyone to."""
    if path == "/partners" or path.startswith("/partners/"):
        return not os.getenv("TRAVELPAYOUTS_TOKEN", "").strip()
    return path.startswith("/go/") and not os.getenv("TRAVELPAYOUTS_MARKER", "").strip()


def hidden(path: str, query=None) -> bool:
    """Is this request for something that does not exist when the showcase is off?"""
    if any(path == p or path.startswith(p + "/") for p in HIDDEN) or _needs_keys(path):
        return True
    m = _ITINERARY.fullmatch(path)
    if m and m.group(1) not in _NOT_ITINERARY:  # /trips/<slug>: a sample or community itinerary page
        return True
    return bool(query is not None and query.get("demo") == "long")  # the 20-day calendar fixture (the body is checked in `guard`)


async def guard(req, sess):
    """Beforeware: 404 for everything `hidden` while the showcase is off."""
    if on():
        return None
    gone = hidden(req.url.path, req.query_params)
    if not gone and req.method in ("POST", "PUT", "PATCH", "DELETE") and "form" in req.headers.get("content-type", ""):
        gone = (await req.form()).get("demo") == "long"   # the fixture's name can come in the body too
    return not_found() if gone else None


def not_found():
    """The 404 page of everything that does not exist (also what an unknown /go offer gets)."""
    from gitaway.layout import page
    from fasthtml.common import A, Div, H1, P, Section
    return FtResponse(page("Not found", Section(Div(H1("Nothing here"), P("That page isn't part of GitAway."), A("Back home", href="/", cls="btn btn-primary")),
                                                 cls="ga-soon ga-wrap")), status_code=404)
