"""F-191: the badge file and the "Put this on your blog" panel.

GET /badge/plan-this-trip.svg and /badge/plan-this-trip-dark.svg   public, no sign-in, no cookie, cacheable for a day (the URL is what a blog embeds, so it must stay put)
`panel(slug, handle)`   drawn on a creator's own live trip page (itinerary_view) and on /creators/settings, only for that creator; `for_owner(session, trip)` decides who sees it.
The copy-paste text is built in gitaway/blogbutton.py.
"""

import hashlib

from fasthtml.common import Button, Div, H2, Img, Label, Link, P, Script, Section, Textarea
from starlette.responses import Response

from gitaway import blogbutton, community, session as ses
from gitaway.icons import icon

HEAD = (Link(rel="stylesheet", href="/assets/css/blogbutton.css"), Script(src="/assets/js/blogbutton.js", defer=True))
BADGES = {blogbutton.LIGHT: False, blogbutton.DARK: True}


def for_owner(session, slug):
    """The panel for the signed-in person when `slug` is one of their own live trips, else "" (a stranger, a signed-out reader and a taken-down trip see nothing)."""
    me = ses.current_traveler(session)
    row = community.get(slug) if me else None
    creator = community.creator_of(me.id) if row and row["owner_user"] == str(me.id) else None
    return panel(slug, creator["handle"]) if creator else ""


def _copy(uid, kind, label, value, rows):
    field = f"{uid}-{kind}"
    return Div(Label(label, fr=field, cls="bb-lab"),
               Textarea(value, id=field, readonly=True, rows=str(rows), spellcheck="false", autocomplete="off", cls="bb-text"),
               Button(icon("link", 20, 2.4), "Copy", type="button", data_copy=field, id=f"{field}-copy", cls="btn btn-primary bb-copy"), cls="bb-row")


def panel(slug, handle, uid="bb"):
    """The panel with its own stylesheet and script, so any page can drop it in."""
    return Div(*HEAD, Section(
        H2("Put this on your blog"),
        P("A button that sends your readers to this trip on GitAway. It is a plain link and a picture: no script, and nothing tracks your readers.", cls="bb-lede"),
        Div(Img(src=blogbutton.LIGHT, alt=blogbutton.ALT, width=blogbutton.SIZE[0], height=blogbutton.SIZE[1], cls="bb-badge"),
            Img(src=blogbutton.DARK, alt=blogbutton.ALT, width=blogbutton.SIZE[0], height=blogbutton.SIZE[1], cls="bb-badge"), cls="bb-badges"),
        _copy(uid, "html", "HTML for your blog", blogbutton.html_snippet(slug, handle), 6),
        _copy(uid, "link", "Or just a link", blogbutton.text_link(slug, handle), 2),
        id=uid, cls="bb ga-wrap", data_slug=slug))


def register(app):
    @app.get(blogbutton.LIGHT)
    @app.get(blogbutton.DARK)
    def badge(request):
        svg = blogbutton.badge_svg(BADGES[request.url.path]).encode()
        return Response(svg, media_type="image/svg+xml", headers={
            "Cache-Control": "public, max-age=86400", "ETag": '"' + hashlib.sha256(svg).hexdigest()[:16] + '"',
            "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox"})
