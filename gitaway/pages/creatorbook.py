"""The book's pages (F-253, D-640..): a creator's trip as the scrapbook book of docs/design/creators-v2.

GET /trips/<slug>/book              a published creator trip (or a sample, on the showcase) as a book anyone can read: hearts (the existing Save), Plan this trip (booking's sentence)
GET /creators/import/<id>/book      the owner's own book, draft or live: Edit a word in place, Publish (the existing publish path: the "This is my post" tick, owner check and the review states)

The owner's edits and Publish post to the draft's own route (`POST /creators/import/<id>`, gitaway/pages/creatorimport.py, `do=word|lead|publish` with `X-Book: 1` for a JSON answer).
The book is drawn by gitaway/pages/bookview.py, turned by assets/js/book.js; the trip page at /trips/<slug> is unchanged.
"""

from datetime import datetime, timezone

from fasthtml.common import Link, Script, Section, Div, H1, P, A
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import community, creatorbook as cb, creatordraft as cd, forks as forks_model, seo, session as ses, stats
from gitaway.layout import page
from gitaway.pages import bookview, trips as trips_page

HEAD = (Link(rel="stylesheet", href="/assets/css/cv2.css"), Link(rel="stylesheet", href="/assets/css/placeart.css"), Script(src="/assets/js/book.js", defer=True))


def stamp_of(iso: str = "") -> str:
    """"Nov 15, 2026" from a stored time, or today."""
    when = datetime.fromisoformat(iso) if iso else datetime.now(timezone.utc)
    return f"{when.strftime('%b')} {when.day}, {when.year}"


def reader_page(session, slug, found, auto=True):
    saved = slug in ses.saved(session)
    book = cb.from_trip(found, sample=not found.real)
    waiting = found.real and community.review_state(slug) == "pending"
    body = page(book.title, *bookview.book_markup(book, mode="reader", saved=saved, signed=bool(ses.current_traveler(session)), owner_state={"auto": auto}), current="/community", head=HEAD, v2="cv is-results",
                description=f"{book.title}: a trip by {book.by}, as a book you can flip through and plan from.", noindex=waiting or (found.real and seo.imported(slug)))
    return FtResponse(body, headers={"X-Robots-Tag": "noindex, nofollow"}) if waiting else body


def owner_page(session, d):
    trip = cd.preview(session, d)
    row = community.get(d["slug"]) if d["live"] else None
    book = cb.from_trip(trip, stamped=stamp_of(row["updated_at"]) if row else "")
    state = {"live": d["live"], "where": f"gitaway.me/trips/{d['slug']}/book", "post": cd.domain_of(d)}
    return page(book.title, *bookview.book_markup(book, mode="creator", owner_state=state, lead=bool(d.get("images")) and not d["picks"]), current="/for-creators", head=HEAD, v2="cv is-results",
                noindex=True, description="Your book, before anyone else sees it.")


def register(app):
    @app.get("/trips/{slug}/book")
    def reader(request, session, slug: str):
        found = forks_model.resolve(slug)
        if found is None:
            return trips_page.not_found()
        if found.real:
            stats.count_view(request, session, slug)
        return reader_page(session, slug, found)

    @app.get("/creators/import/{token}/book")
    def owner(session, token: str):
        me = ses.current_traveler(session)
        if not me:
            return RedirectResponse(f"/signin?next=/creators/import/{token}/book&intent=publish", status_code=303)
        d = cd.get(me.id, token)
        if not d:
            return FtResponse(page("Not found", Section(Div(H1("Nothing here"), P("That draft is not yours, or it is gone."), A("Start a new one", href="/creators/import", cls="btn btn-primary"), cls="ga-wrap"),
                                                       cls="ga-soon ga-wrap")), status_code=404)
        return owner_page(session, d)
