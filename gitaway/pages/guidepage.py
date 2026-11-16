"""The guide's pages and writes (F-262, D-710..). The data is gitaway/guide.py, the drawing gitaway/pages/guideview.py, the script assets/js/guide.js.

GET  /trips/<slug>                    a published creator trip (or a creator's sample, on the showcase) as a guide anyone can read: Plan this trip, Add to my plan, Save (the existing /save);
                                      drawn from gitaway/pages/trips.py, which keeps the family trips' own pages
GET  /trips/<slug>/card.png           the guide's card for Instagram, 1080 x 1350 (gitaway/sharecard.py), public like its page; a plain def, so the picture is drawn off the event loop
GET  /trips/<slug>/book               retired (the book): a permanent redirect to the guide
GET  /creators/import/<id>/guide      the owner's own guide, draft or live: fix a word in place, Edit details (the editor, F-259), Publish (the existing path: the "This is my post" tick, the owner
                                      check and the review states); the script posts to the draft's own route (`do=word|lead|publish` with `X-Book: 1`, creatorimport.py)
GET  /creators/import/<id>/book       retired: redirects to the owner's guide
POST /guides/add                      Add to my plan: stops of a guide (`k` = "d0s1", repeated) dropped into the family's calendar's free hours (gitaway/guideplan.py); the editor's role, like any write to the plan
"""

from datetime import datetime, timezone

from fasthtml.common import A, H1, Meta, P
from fasthtml.core import FtResponse
from starlette.responses import JSONResponse, RedirectResponse, Response

from gitaway import access, community, creatordraft as cd, forks as forks_model, guide as gd, guideplan, moods, seo, session as ses, sharecard, showcase, tripcal, tripshare
from gitaway.layout import notice, page
from gitaway.pages import guideview


def stamp_of(iso: str = "") -> str:
    """"Nov 15, 2026" from a stored time, or today."""
    when = datetime.fromisoformat(iso) if iso else datetime.now(timezone.utc)
    return f"{when.strftime('%b')} {when.day}, {when.year}"


def add_state(session) -> str:
    """What "Add to my plan" can do for this person: "yes", or why not: "signin", "trip" (no trip to add to), "viewer" (not an editor of the family)."""
    if not ses.current_traveler(session):
        return "signin"
    if not ses.booking(session):
        return "trip"
    return "yes" if access.can_edit(access.request_role()) else "viewer"


def reader_page(session, slug, found):
    waiting = found.real and community.review_state(slug) == "pending"
    row = community.get(slug) if found.real else None
    g = gd.from_trip(found, stamped=stamp_of(row["updated_at"]) if row else "", handle="" if waiting else found.handle)      # a trip waiting for the captain has no profile page yet (F-194)
    state = {"saved": slug in ses.saved(session), "signed": bool(ses.current_traveler(session)), "add": add_state(session), "signin": ses.signin_href(f"/trips/{slug}"), "start": showcase.planning_path(),
             "report": found.real and community.is_real(slug), "plannable": bool(found.plan_to)}
    head = (*guideview.HEAD, Meta(name="robots", content="noindex, nofollow")) if waiting else guideview.HEAD
    body = page(g.title, *guideview.guide_markup(g, mode="reader", state=state), current="/guides", head=head, v2="cv g is-results", quiet=True, mood=moods.of_text(found.place),
                description=found.lede or f"{g.title}: a guide by {g.by}, laid out stop by stop to plan from.", image=found.polaroids[0].src if found.polaroids else "", og_type="article",
                noindex=not waiting and found.real and seo.imported(slug))      # a copy of a creator's post is not for search (F-196); a trip waiting for the captain is "noindex, nofollow" (F-194)
    return FtResponse(body, headers={"X-Robots-Tag": "noindex, nofollow"}) if waiting else body


def owner_page(session, d, error=""):
    trip = cd.preview(session, d)
    row = community.get(d["slug"]) if d["live"] else None
    g = gd.from_trip(trip, stamped=stamp_of(row["updated_at"]) if row else "", private=[(p["kind"], p["title"]) for p in d.get("private", [])])
    state = {"live": d["live"], "where": f"gitaway.me/trips/{d['slug']}", "post": cd.domain_of(d), "editor": f"/creators/import/{d['id']}"}
    return page(g.title, *guideview.guide_markup(g, mode="owner", state=state), current="/guides", head=guideview.HEAD, v2="cv g is-results", quiet=True, noindex=True, description="Your guide, before anyone else sees it.")


def _gone():
    return notice("Not found", H1("Nothing here"), P("That draft is not yours, or it is gone."), A("Make a guide", href="/guides/make", cls="btn btn-primary"), status=404)


def register(app):
    @app.get("/trips/{slug}/card.png")
    def card(slug: str):
        found = forks_model.resolve(slug)
        row = community.get(slug) if found is not None and found.real else None
        if row is None or not gd.is_guide(found):
            return Response("not found", status_code=404, media_type="text/plain")
        g = gd.from_trip(found)
        png = sharecard.render(sharecard.Card(g.title, g.place, (), "", len(g.days), "", f"gitaway.me/trips/{slug}", tripshare.art_for(g.place)))
        return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"})

    @app.get("/trips/{slug}/book")
    def retired_reader(slug: str):
        return RedirectResponse(f"/trips/{slug}", status_code=301)

    @app.get("/creators/import/{token}/book")
    def retired_owner(token: str):
        return RedirectResponse(f"/creators/import/{token}/guide", status_code=303)

    @app.get("/creators/import/{token}/guide")
    def owner(session, token: str):
        me = ses.current_traveler(session)
        if not me:
            return RedirectResponse(f"/signin?next=/creators/import/{token}/guide&intent=publish", status_code=303)
        d = cd.get(me.id, token)
        return owner_page(session, d) if d else _gone()

    @app.post("/guides/add")
    async def add(request, session):
        """Add to my plan. The route is not open to a viewer (access.py): only an editor or an admin of the family changes its plan."""
        form = await request.form()
        found = forks_model.resolve(str(form.get("slug") or "")[:80])
        if not gd.is_guide(found):
            return JSONResponse({"error": "That guide is not here any more."}, status_code=404)
        g = gd.from_trip(found)
        keys = [k for k in form.getlist("k") if isinstance(k, str)][:guideplan.MAX_AT_ONCE]
        to, after = str(form.get("to") or ""), str(form.get("after") or "")
        day = int(to) if to.isdigit() and len(to) < 3 else None      # a free morning (F-263): the trip's day it goes into, in order from the minute it starts
        try:
            got = guideplan.add(session, g, keys, day, int(after) if after.isdigit() and len(after) < 5 else 0)
        except tripcal.CalendarError as e:
            return JSONResponse({"error": str(e)}, status_code=422)
        n, m = len(got["added"]), len(got["skipped"])
        if not n:
            said = "Already in your plan." if m and len(keys) == 1 else "There is no free time left that fits." if m else "Nothing to add."
            return JSONResponse({**got, "toast": said}, headers={"Cache-Control": "no-store"})
        if day is not None and n > 1:
            first, last = got["added"][0], got["added"][-1]
            said = f"{n} stops added to {first['when'].split(' ')[0]}, {tripcal.fmt_time(first['start'])} to {tripcal.fmt_time(last['end'])}"
        else:
            said = f"{got['added'][0]['title']} added, {got['added'][0]['when']}" if n == 1 else f"{n} stops added to your plan"
        return JSONResponse({**got, "toast": said + (f". {m} left out: already there, or no free time." if m else "")}, headers={"Cache-Control": "no-store"})
