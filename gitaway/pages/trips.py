"""Public trip pages at /trips/{slug} (F-014 renders the scrapbook page for known trips; a creator's trip is a guide, gitaway/pages/guidepage.py), the Save heart and a published trip's public photos.

POST /save, /unsave   the heart (signed out: through the demo sign-in with intent=save)
GET  /pub/<slug>/<file>   a published trip's public photo, public and cacheable; the family's own photos are never here
"""

from urllib.parse import quote

from fasthtml.common import A, Div, H1, P, Section, cookie
from fasthtml.core import FtResponse
from starlette.responses import FileResponse, RedirectResponse, Response

from gitaway import affiliate, community, forks as forks_model, guide as gd, publish, seo, session as ses, showcase, stats
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
                A("Find another guide", href="/guides", cls="btn btn-primary") if showcase.on() else A("Back home", href="/", cls="btn btn-primary"),
            ),
            cls="ga-soon ga-wrap",
        ),
    )
    return FtResponse(body, status_code=404)


def register(app):
    @app.get("/trips/{slug}")
    def trip(request, session, slug: str, theme: str = "", state: str = ""):
        found = forks_model.resolve(slug)
        if found is None:
            return not_found()
        if found.real:
            stats.count_view(request, session, slug)   # F-192: one reader once a day, no cookie, nothing personal kept (a plain def, so the write is off the event loop)
        from gitaway.pages import guidepage      # here: guidepage draws with layout, which imports the pages
        if gd.is_guide(found):      # F-262: a creator's trip is a guide (the run sheet); a family's own published trip keeps this page
            return guidepage.reader_page(session, slug, found)
        waiting = found.real and community.review_state(slug) == "pending"      # F-194: reachable by its link, in no list, and not for search engines
        forked = slug in ses.forks(session)
        body = itinerary_page(found, theme=theme, loading=(state == "loading"), saved=slug in ses.saved(session), forked=forked,
                              blog=blogbutton.for_owner(session, slug) if found.real else "", noindex=found.real and seo.imported(slug), waiting=waiting)      # a copy of a creator's post is not for search (F-196)
        # F-195: a family that forked a creator's trip books for them (every fork path, signed in or through sign-in, ends on this page)
        unchecked = found.real and community.waits(slug)       # pending or unverified: nobody earns from it yet, so forking it sets no cookie and forgets an earlier one
        via = ()
        if forked and found.real and not unchecked and affiliate.valid_via(found.handle):
            via = (cookie(affiliate.COOKIE, found.handle, **affiliate.cookie_args()),)
        elif forked and unchecked and affiliate.COOKIE in request.cookies:
            via = (cookie(affiliate.COOKIE, "", max_age=0, path="/"),)
        if waiting:
            return FtResponse((body, *via), headers={"X-Robots-Tag": "noindex, nofollow"})
        return (body, *via) if via else body

    def trip_path(next_path):
        path = ses.safe_next(next_path, "")
        return path if ses.trip_slug(path) else "/guides"

    @app.post("/save")
    def save(session, next: str = ""):
        """The heart on a trip or a guide: save it for the signed-in person (signed out: through sign-in with intent=save)."""
        path = trip_path(next)
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={quote(path, safe='/')}&intent=save", status_code=303)
        ses.add_save(session, path)
        return RedirectResponse(path, status_code=303)

    @app.post("/unsave")
    def unsave(session, next: str = ""):
        path = trip_path(next)
        ses.remove_save(session, path)
        return RedirectResponse(path, status_code=303)

    @app.get("/pub/{slug}/{filename}")
    def public_photo(request, slug: str, filename: str):
        """A published trip's public photo (`<16 hex>-display.jpg` / `-thumb.jpg`), public and cacheable."""
        path = publish.public_file(slug, filename)
        if path is None:
            return Response("Not found.", status_code=404)
        headers = {"Cache-Control": "public, no-cache", "X-Content-Type-Options": "nosniff", "ETag": f'"{filename}-{path.stat().st_mtime_ns}"'}
        if request.headers.get("if-none-match") == headers["ETag"]:
            return Response(status_code=304, headers=headers)
        return FileResponse(path, media_type="image/jpeg", headers=headers)
