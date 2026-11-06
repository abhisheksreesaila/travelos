"""One switch for sample data (F-064): the live site shows only what's real.

`on()` is true on a local copy and false in production (`auth.production()`). GITAWAY_SHOWCASE=1 or 0 overrides it, so tests and
screenshots can see either mode without touching the production lock on the dev sign-in.

When it is off there are no sample trips anywhere: no Community trips, creators, forks, saves or sharing, no sample itineraries (names,
fork counts), no `?demo=long` calendar, no pretend-friends invite. Their routes answer 404 (`guard`) and nothing links to them. What stays:
the landing's illustrations, and the booking workspace, labelled a preview with sample prices.

Real content is the exception (F-181): once a person publishes a real trip (`community.has_real()`), Community trips, the creator pages, forks and
saves exist off the showcase too, but show only real content: `/trips/<slug>` answers for a published real trip and no sample slug, `/creators/<handle>`
for a real creator, and the paste-a-link import (/creators POST, draft, finish, done) and /share stay local-only.
"""

import os
import re

from fasthtml.core import FtResponse

from gitaway import auth

# Paths (and everything under them) that exist only for sample or community content.
HIDDEN = ("/share",  # the old one-tap demo share (F-022); real trips are published at /trip/publish
          "/rides",  # the simulated Uber (rides)
          "/sandbox",  # the stand-in partner checkout (M3): partners keep real bookings, there is nothing to stand in for
          "/creators/draft", "/creators/finish", "/creators/done")  # the paste-a-link import is simulated (F-023)
# These exist off the showcase only once a real trip is published (F-181); then they list and fork real content alone.
REAL = ("/community", "/discover", "/creators", "/forks", "/save", "/unsave", "/fork")
REAL_ALWAYS = ("/creators/import", "/creators/settings", "/creators/drafts", "/creators/stats")   # (F-190: their drafts and a batch of their posts; F-192: their stats) a creator's import of their own post (F-183) exists off the showcase before anyone has published: it is how the first trip gets published
_NOT_ITINERARY = ("build", "import", "switch")  # /trips/<word> routes that are the family's own
_ITINERARY = re.compile(r"/trips/([^/]+)/?")

PREVIEW = "Preview: sample prices, nothing is booked."


def on() -> bool:
    flag = os.getenv("GITAWAY_SHOWCASE", "").strip()
    if flag in ("0", "1"):
        return flag == "1"
    return not auth.production()


def community_open() -> bool:
    """Do Community trips and the creator pages exist? On the showcase always; off it only once a real trip is published (F-181)."""
    from gitaway import community
    return on() or community.has_real()


def _needs_keys(path: str) -> bool:
    """Pages that exist off the showcase only with real partner keys: /partners reads real statistics (TRAVELPAYOUTS_TOKEN), /go/... sends a
    traveler to a real tracked link (TRAVELPAYOUTS_MARKER) and /plan-for-me sells with STRIPE_SECRET_KEY; without them there is nothing real to show or send anyone to."""
    if path == "/partners" or path.startswith("/partners/"):
        return not os.getenv("TRAVELPAYOUTS_TOKEN", "").strip()
    if path == "/plan-for-me" or path.startswith("/plan-for-me/"):      # Plan it for me (F-193) is for sale only with a Stripe key; the webhook is not here, it answers 503 without its own secret
        return not os.getenv("STRIPE_SECRET_KEY", "").strip()
    return path.startswith("/go/") and not os.getenv("TRAVELPAYOUTS_MARKER", "").strip()


def _under(path: str, prefixes) -> bool:
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def hidden(path: str, query=None, method: str = "GET") -> bool:
    """Is this request for something that does not exist when the showcase is off?"""
    from gitaway import community
    if _under(path, HIDDEN) or _needs_keys(path):
        return True
    if _under(path, REAL) and not _under(path, REAL_ALWAYS):
        if not community.has_real():
            return True
        if path == "/creators" and method != "GET":  # the paste form posts here: simulated
            return True
        m = re.fullmatch(r"/creators/([^/]+)/?", path)
        if m and community.creator(m.group(1)) is None:  # a sample creator's profile, or nobody's
            return True
    m = _ITINERARY.fullmatch(path)
    if m and m.group(1) not in _NOT_ITINERARY:  # /trips/<slug>: a page of a real published trip, never a sample or a demo share
        return not community.is_real(m.group(1))
    return bool(query is not None and query.get("demo") == "long")  # the 20-day calendar fixture (the body is checked in `guard`)


async def guard(req, sess):
    """Beforeware: 404 for everything `hidden` while the showcase is off."""
    if on():
        return None
    gone = hidden(req.url.path, req.query_params, req.method)
    if not gone and req.method in ("POST", "PUT", "PATCH", "DELETE") and "form" in req.headers.get("content-type", ""):
        gone = (await req.form()).get("demo") == "long"   # the fixture's name can come in the body too
    return not_found() if gone else None


def not_found():
    """The 404 page of everything that does not exist (also what an unknown /go offer gets)."""
    from gitaway.layout import page
    from fasthtml.common import A, Div, H1, P, Section
    return FtResponse(page("Not found", Section(Div(H1("Nothing here"), P("That page isn't part of GitAway."), A("Back home", href="/", cls="btn btn-primary")),
                                                 cls="ga-soon ga-wrap")), status_code=404)
