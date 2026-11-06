"""Public itinerary pages at /trips/{slug} (F-014 renders the scrapbook page for known trips) and the family's trip switcher (F-040).

POST /trips/switch   open another of the family's trips for the signed-in person (trip=<id>), then back to the trip
"""

from fasthtml.common import A, Div, H1, P, Section, cookie
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import affiliate, community, forks as forks_model, seo, session as ses, showcase, stats
from gitaway.pages import blogbutton
from gitaway.itinerary_view import itinerary_page
from gitaway.layout import page


def not_found():
    body = page(
        "Trip not found",
        Section(
            Div(
                H1("This trip wandered off"),
                P("We couldn't find that itinerary. It may have been renamed, or the link is missing a piece."),
                A("Find another trip", href="/community", cls="btn btn-primary") if showcase.on() else A("Back home", href="/", cls="btn btn-primary"),
            ),
            cls="ga-soon ga-wrap",
        ),
    )
    return FtResponse(body, status_code=404)


def register(app):
    @app.get("/trips")
    @app.get("/trips/")
    def current_trip(session, day: str = ""):
        """/trips has nothing of its own: it goes to the current trip (the one address that used to be a 404)."""
        from gitaway.pages.calendar import to_the_trip
        return to_the_trip(session, day)

    @app.get("/trips/{slug}")
    def trip(request, session, slug: str, theme: str = "", state: str = ""):
        found = forks_model.resolve(slug)
        if found is None:
            return not_found()
        if found.real:
            stats.count_view(request, session, slug)   # F-192: one reader once a day, no cookie, nothing personal kept (a plain def, so the write is off the event loop)
        waiting = found.real and community.review_state(slug) == "pending"      # F-194: reachable by its link, in no list, and not for search engines
        forked = slug in ses.forks(session)
        body = itinerary_page(found, theme=theme, loading=(state == "loading"), saved=slug in ses.saved(session), forked=forked,
                              blog=blogbutton.for_owner(session, slug) if found.real else "", noindex=found.real and seo.imported(slug), waiting=waiting)      # a copy of a creator's post is not for search (F-196)
        # F-195: a family that forked a creator's trip books for them (every fork path, signed in or through sign-in, ends on this page)
        via = (cookie(affiliate.COOKIE, found.handle, **affiliate.cookie_args()),) if forked and found.real and affiliate.valid_via(found.handle) else ()
        if waiting:
            return FtResponse((body, *via), headers={"X-Robots-Tag": "noindex, nofollow"})
        return (body, *via) if via else body

    @app.post("/trips/switch")
    def switch(session, trip: str = "", next: str = ""):
        """Open another of the family's trips. A trip that is not the family's changes nothing. Always lands on the trip (or `next`)."""
        if not ses.current_traveler(session):
            return RedirectResponse("/signin?next=%2Ftrip", status_code=303)
        ses.switch_trip(session, trip)
        return RedirectResponse(ses.safe_next(next, "/trip"), status_code=303)
