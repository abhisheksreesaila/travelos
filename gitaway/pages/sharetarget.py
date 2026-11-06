"""Share to GitAway from the phone (F-189): the installed app is a Web Share Target (manifest `share_target`, method GET).

GET /share-to-gitaway?title=&text=&url=   the first http(s) link among url, then text, then title opens the import with that link filled in
                                          (signed out: sign in first, then land on the same filled-in import). Nothing is fetched here: the import reads the post only when the creator presses Draft.

Android Chrome supports share_target for an installed web app; iOS Safari does not, so on an iPhone the creator copies the link (docs/briefs/creator-import.md, the For creators FAQ says so).
"""

import re
from urllib.parse import quote

from starlette.responses import RedirectResponse

from gitaway import importsource, session as ses

ACTION = "/share-to-gitaway"
IMPORT = "/creators/import"
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)


def shared_link(url="", text="", title=""):
    """The first valid http(s) link in the shared url, text or title (in that order), or ""."""
    for field in (url, text, title):
        for m in _URL.finditer(field or ""):
            try:
                return importsource.clean_link(m.group(0).rstrip(".,;:!?)]}"))
            except importsource.SourceError:
                continue
    return ""


def import_href(link):
    return f"{IMPORT}?link={quote(link, safe='')}" if link else IMPORT


def register(app):
    @app.get(ACTION)
    def share_target(session, url: str = "", text: str = "", title: str = ""):
        target = import_href(shared_link(url, text, title))
        if not ses.current_traveler(session):
            return RedirectResponse(f"/signin?next={quote(target, safe='')}&intent=publish", status_code=303)
        return RedirectResponse(target, status_code=303)
