"""A creator's blog buttons: GET /creators/settings (F-191; it held the affiliate marker too until F-297 removed it, D-971).

Signed-in only. One "Put this on your blog" panel per live trip of the creator's (pages/blogbutton.py). Registered before /creators/<handle>, which would otherwise take "settings" for a name.
"""

from urllib.parse import quote

from fasthtml.common import A, H1, Link, P, Div, Section
from starlette.responses import RedirectResponse

from gitaway import community, howpaid, session as ses, v2pages
from gitaway.layout import page
from gitaway.pages import blogbutton

PATH = "/creators/settings"
HEAD = (Link(rel="stylesheet", href="/assets/css/report.css"), *v2pages.HEAD)


def settings_page(owner):
    creator = community.creator_of(owner)
    blogs = [blogbutton.panel(r["slug"], creator["handle"], f"bb{i}") for i, r in enumerate(community.rows(owner=owner))] if creator else []   # F-191: the blog button of each live trip
    return page("Your blog button", Section(Div(H1("Your blog button"), P(howpaid.LINKS_YOURS, cls="rp-lede", id="st-says"), cls="rp-top"), *blogs,
                                            P(A("Your creator page", href=f"/creators/{creator['handle']}"), " · ", A("Your stats", href="/creators/stats"), " · ", A("Turn a post into a trip", href="/creators/import"), cls="rp-more") if creator
                                            else P(A("Turn a post into a trip", href="/creators/import"), cls="rp-more"), cls="rp ga-wrap"), head=HEAD, v2=True, quiet=True)


def register(app):
    @app.get(PATH)
    def settings_get(session):
        me = ses.current_traveler(session)
        if not me:
            return RedirectResponse(f"/signin?next={quote(PATH, safe='/')}&intent=publish", status_code=303)
        return settings_page(me.id)
