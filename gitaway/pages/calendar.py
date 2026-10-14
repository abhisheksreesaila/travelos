"""The old trip calendar's addresses (retired in F-147). Nothing is drawn here: old links, home-screen shortcuts and push notifications still land somewhere.

GET /calendar   the trip's day: today during the trip, else day 1 (a ?day=N, or the old ?add=N, asks for that day); the open trip (a ?trip= names one) is in the address
GET /trips      the same, the current trip
GET /invite     the invitations in Family (/family#invite); signed out goes through sign-in first

Where each thing the old page did lives now is in docs/trip-canvas.md ("Retired: the old calendar").
"""

from urllib.parse import quote

from starlette.responses import RedirectResponse

from gitaway import session as ses


def to_the_trip(session, day=""):
    """A redirect to the trip's day view (or to sign-in or Start when there is no trip to show yet)."""
    if not ses.current_traveler(session):
        return RedirectResponse("/signin?next=%2Ftrip", status_code=303)
    if not ses.booking(session):
        return RedirectResponse("/start", status_code=303)
    from gitaway.pages import tripcanvas
    return RedirectResponse(tripcanvas.today_url(session, day if day.isdigit() else ""), status_code=303)


def register(app):
    @app.get("/calendar")
    def calendar(session, day: str = "", add: str = ""):
        return to_the_trip(session, day or add)

    @app.get("/invite")
    def invite_entry(session):
        """Invitations live in Family: signed out goes through sign-in (intent=invite) and comes back there."""
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={quote('/family#invite', safe='')}&intent=invite", status_code=303)
        return RedirectResponse("/family#invite", status_code=303)
