"""Book the open trip (F-198): GET /trip/book sends a signed-in family to the booking lanes (/plan) for their own trip's place, dates and party. Any destination; links only."""

from urllib.parse import urlencode

from starlette.responses import RedirectResponse

from gitaway import session as ses, showcase, tripcal as cal  # noqa: F401 (cal: href() is still used by older pages)


def href(t) -> str:
    """The booking lanes' address for trip `t` (a catalog TripSearch or an imported trip)."""
    q = {"place": t.destination_name, "d": t.depart.isoformat(), "r": t.return_.isoformat(), "a": max(t.adults, 1)}
    if t.kid_ages:
        q["k"] = ",".join(map(str, t.kid_ages))
    return "/plan?" + urlencode(q)


def register(app):
    @app.get("/trip/book")
    def trip_book(session):
        if not ses.current_traveler(session):
            return RedirectResponse(ses.signin_href("/trip/book"), status_code=303)
        return RedirectResponse(showcase.planning_path(), status_code=303)      # D-600: Book is the journey (What are you after?, then the matrix), never the old /plan lanes
