"""Public itinerary pages at /trips/{slug} (F-014 renders the scrapbook page for known trips) and the family's trip switcher (F-040).

POST /trips/switch   open another of the family's trips for the signed-in person (trip=<id>), then back to their calendar
"""

from fasthtml.common import A, Div, H1, P, Section
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import creators, itineraries, session as ses, share
from gitaway.itinerary_view import itinerary_page
from gitaway.layout import page


def not_found():
    body = page(
        "Trip not found",
        Section(
            Div(
                H1("This trip wandered off"),
                P("We couldn't find that itinerary. It may have been renamed, or the link is missing a piece."),
                A("Find another trip", href="/discover", cls="btn btn-primary"),
            ),
            cls="ga-soon ga-wrap",
        ),
    )
    return FtResponse(body, status_code=404)


def register(app):
    @app.get("/trips/{slug}")
    def trip(session, slug: str, theme: str = "", state: str = ""):
        found = itineraries.get(slug) or share.find(session, slug) or creators.find(session, slug)
        if found is None:
            return not_found()
        return itinerary_page(found, theme=theme, loading=(state == "loading"), saved=slug in ses.saved(session), forked=slug in ses.forks(session))

    @app.post("/trips/switch")
    def switch(session, trip: str = "", next: str = ""):
        """Open another of the family's trips. A trip that is not the family's changes nothing. Always lands on the calendar (or `next`)."""
        if not ses.current_traveler(session):
            return RedirectResponse("/signin?next=%2Fcalendar", status_code=303)
        ses.switch_trip(session, trip)
        return RedirectResponse(ses.safe_next(next, "/calendar"), status_code=303)
