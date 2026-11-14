"""The front door at / (F-206, F-231).

Signed out: the cover story (gitaway/pages/cover.py). Signed in: one way in, decided here (D-461): the family's trip (its cockpit) when it has one, else the
trip matrix, where a new trip begins (or, where the matrix does not exist, the import of a trip already booked). The old signed-in landing, "Fork a getaway", is gone.
"""

import base64
import os

from fasthtml.common import Script
from starlette.responses import RedirectResponse

from gitaway import session as ses, showcase
from gitaway.pages import cover

COCKPIT = "/trip/cockpit"


def footer_links():
    """The links that left the landing's header. Sign in only while signed out."""
    links = ([("Community trips", "/community")] if showcase.on() else []) + [("For creators", "/for-creators")]
    return links if ses.request_traveler() else [*links, ("Sign in", ses.signin_href())]


def _drive():
    """Travelpayouts Drive, their site-verification script: on the signed-out landing only, and only when TRAVELPAYOUTS_DRIVE_ID
    (the partner id, digits) is set. Never on signed-in pages, which show a family's names and trips."""
    pid = os.getenv("TRAVELPAYOUTS_DRIVE_ID", "").strip()
    if not pid.isascii() or not pid.isdigit() or ses.request_traveler():
        return ()
    return (Script(src=f"https://tp-em.com/{base64.b64encode(pid.encode()).decode()}.js?t={pid}", **{"async": True}),)


def register(app):
    @app.get("/")
    def home(session, htmlkw):
        if not ses.current_traveler(session):      # F-206: a stranger gets the cover story (gitaway/pages/cover.py)
            htmlkw["cls"] = "cv-root"
            return cover.page(footer_links(), _drive())
        return RedirectResponse(COCKPIT if ses.booking(session) else showcase.planning_path(), status_code=303)
