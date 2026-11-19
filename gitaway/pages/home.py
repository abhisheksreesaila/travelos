"""The front door at / (F-206, F-231).

Signed out: the cover story (gitaway/pages/cover.py). Signed in: one way in, decided here (D-461): the family's trip (its cockpit) when it has one, else the
trip matrix, where a new trip begins (or, where the matrix does not exist, the import of a trip already booked). The old signed-in landing, "Fork a getaway", is gone.
"""

from starlette.responses import RedirectResponse

from gitaway import session as ses, showcase
from gitaway.pages import cover



def footer_links():
    """The links that left the landing's header. Sign in only while signed out."""
    links = [("Postcards", "/guides")]
    return links if ses.request_traveler() else [*links, ("Sign in", ses.signin_href())]


def register(app):
    @app.get("/")
    def home(session, htmlkw):
        if not ses.current_traveler(session):      # F-206: a stranger gets the cover story (gitaway/pages/cover.py)
            htmlkw["cls"] = "cv-root"
            return cover.page(footer_links())
        return RedirectResponse(showcase.planning_path(), status_code=303)      # D-600: always the journey's first step (What are you after?); the trip is reached from Plan this trip and the bar
