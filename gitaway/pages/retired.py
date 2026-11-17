"""The addresses of the old app (F-254, D-750..): every page the v2 journey replaced is gone, and its address still answers, so an old link, bookmark, home-screen shortcut or push notification lands
in the journey's matching place instead of a 404.

    to /trip/plan     the trip: the cockpit, the day and canvas pages, the Ask box, the old tabs (map, family, help, photos, talk), rides, the trip's publish editor
    to /plan/ask      the way in: the booking lanes, the trip grid, the old checkout, Where to?, a new trip
    to /guides        what other people did: forks, the old share and publish pages

A page is a 303 (a person may be sent somewhere else tomorrow); the public pages that search engines know are a 301 (`PERMANENT`). A write that has no place any more (a POST to the old canvas, the old
checkout) gets the same redirect, so a stale tab lands somewhere calm; nothing is written. `RETIRED` is also the list tests/test_retired.py holds every page, script and email to: none may link to
one of these. Where a kept route lives under a retired prefix (/trip/family/message, /trip/help/phone, /trip/talk/message, /trip/plan/...), only the exact retired paths are listed here.
"""

from starlette.responses import RedirectResponse

from gitaway import session as ses, showcase

TRIP, WAY_IN, GUIDES = "/trip/plan", "/plan/ask", "/guides"

PERMANENT = {"/plan", "/plan/grid", "/forks", "/trips"}
POST_ONLY = {"/trips/switch"}      # /trips/<slug> is a page, so a GET of this one is a trip that is not there

RETIRED = {
    TRIP: (
        "/trip", "/trip/cockpit", "/trip/cockpit/map", "/trip/cockpit/pack/{name}",
        "/trip/canvas", "/trip/canvas/card", "/trip/canvas/step", "/trip/canvas/move", "/trip/canvas/undo", "/trip/canvas/plan", "/trip/canvas/add", "/trip/canvas/note", "/trip/canvas/actnote",
        "/trip/map", "/trip/map/around", "/trip/block", "/trip/block/step", "/trip/add",
        "/trip/ask", "/trip/ask/mic-event", "/trip/ask/transcribe", "/trip/ask/propose", "/trip/ask/answer", "/trip/ask/edit", "/trip/ask/apply",
        "/trip/family", "/trip/family/thread", "/trip/family/quiet", "/trip/family/panel", "/trip/family/seen", "/trip/family/list",
        "/trip/help", "/trip/photos", "/trip/photos/remove", "/trip/photos/{pid}", "/trip/photos/{pid}/{size}",
        "/trip/talk", "/trip/talk/items", "/trip/talk/photo", "/trip/talk/voice", "/trip/plans", "/trip/notes",
        "/trip/publish", "/trip/publish/save", "/trip/publish/preview", "/trip/publish/unpublish",
        "/calendar", "/trips", "/trips/switch", "/booked", "/partners",
        "/rides/new", "/rides", "/rides/{ride_id}", "/rides/{ride_id}/step", "/rides/{ride_id}/cancel",
    ),
    WAY_IN: (
        "/plan", "/plan/grid", "/plan/grid/trip", "/plan/quote", "/plan/explore", "/plan/pay", "/pay", "/trip/book", "/trip/new",
    ),
    GUIDES: (
        "/forks", "/forks/apply", "/forks/undo", "/fork", "/share", "/share/unpublish", "/share/done",
    ),
}
# /trip/today came back as the new Today (F-287); the old one's address is no longer listed here.
# /community, /discover and /for-creators were retired earlier (F-262): gitaway/pages/guides.py redirects them to /guides with the hub's filters, and tests/test_retired.py holds links off them too.


def _redirect(target, permanent):
    def go(session, day: str = ""):
        if target == TRIP and not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={TRIP.replace('/', '%2F')}", status_code=303)
        if target == TRIP and not ses.booking(session):      # no trip yet: the way in, not an empty calendar
            return RedirectResponse(showcase.planning_path(), status_code=303)
        return RedirectResponse(f"{target}?day={day}" if target == TRIP and day.isdigit() else target, status_code=301 if permanent else 303)
    return go


def paths():
    """Every retired address, as a flat list."""
    return [p for group in RETIRED.values() for p in group]


def register(app):
    for target, group in RETIRED.items():
        for path in group:
            app.route(path, methods=["POST"] if path in POST_ONLY else ["GET", "POST"], name="retired_" + path.strip("/").replace("/", "_").replace("{", "").replace("}", "") or "retired_root")(_redirect(target, path in PERMANENT))
