"""Install on iPhone (F-044): the web app manifest, the service worker and its offline page.

GET /manifest.webmanifest   "Add to Home Screen" opens GitAway full screen at /start
GET /sw.js                  the service worker, served from the root so its scope is the whole site
GET /offline                what a page shows when there is no connection and it was never opened before

The head tags that point at these live in gitaway.layout.HEAD, so every page carries them.
"""

import json
from pathlib import Path

from fasthtml.common import A, Div, H1, P, Section
from starlette.responses import Response

from gitaway.layout import PAPER, page

SW_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "sw.js"

MANIFEST = {
    "name": "GitAway",
    "short_name": "GitAway",
    "description": "Plan a family trip together: flights, stays and days on one calendar.",
    "start_url": "/start",
    "scope": "/",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": PAPER,
    "theme_color": PAPER,
    "icons": [
        {"src": "/assets/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/assets/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "/assets/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}


def register(app):
    @app.get("/manifest.webmanifest")
    def manifest():
        return Response(json.dumps(MANIFEST), media_type="application/manifest+json")

    @app.get("/sw.js")
    def service_worker():
        # no-cache so a new version is picked up on the next visit; the scope header lets it control "/"
        return Response(SW_PATH.read_text(), media_type="text/javascript", headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})

    @app.get("/offline")
    def offline():
        return page(
            "Offline",
            Section(
                Div(H1("You're offline"), P("This page isn't saved on your phone yet. Pages you opened recently still work offline; the rest will load once you're back online."), A("Back to your trip", href="/start", cls="btn btn-primary")),
                cls="ga-soon ga-wrap",
            ),
        )
