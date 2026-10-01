"""Public itinerary pages at /trips/{slug}. F-014 renders the scrapbook page for known trips."""

from fasthtml.common import A, Div, H1, P, Section
from fasthtml.core import FtResponse

from gitaway import forks as forks_model, session as ses
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
        found = forks_model.resolve(slug)
        if found is None:
            return not_found()
        return itinerary_page(found, theme=theme, loading=(state == "loading"), saved=slug in ses.saved(session), forked=slug in ses.forks(session))
