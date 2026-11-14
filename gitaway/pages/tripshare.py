"""Share the trip to Instagram (F-234, D-490..D-496). The model is gitaway/tripshare.py, the picture gitaway/sharecard.py.

GET  /trip/share             the share sheet for the open trip (editors and admins): the card's preview, "say our first names" and "show the exact dates", Share (the phone's
                             share sheet), Download, Copy link and Stop sharing. With the header `X-Share: 1` it is just the fragment the cockpit's button grows out of (assets/js/share.js);
                             without, a page of its own that works with no script. Opening it makes the trip's share (the same link every time).
POST /trip/share             keep the two choices (`names`, `exact`); answers JSON {link, card, names, exact} to a script, else goes back to the sheet
POST /trip/share/off         turn the share off: its card and page answer 404 from then on
GET  /s/<token>              the public page: the place's art, the title, where from and to, the month and the length, and a way to plan your own. Nothing else: no names, no exact dates,
                             no booking; noindex. A published trip is linked at /trips/<slug> instead (tripshare.Share.link).
GET  /s/<token>/card.png     the card itself (1080 x 1350), public like the page, drawn on request in a worker thread (a cheap picture, kept five minutes by caches)

Plain def handlers on purpose: Starlette runs them in its thread pool, so drawing a PNG never holds up the event loop (tests/test_event_loop.py).
"""

import hashlib
import json
from collections import OrderedDict
from threading import Lock
from urllib.parse import quote

from fasthtml.common import A, Button, Div, Form, H1, H2, Img, Input, Label, Link, Main, NotStr, P, Section, Span
from fasthtml.common import to_xml
from fasthtml.core import FtResponse
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from gitaway import access, blogbutton, phone, placeart, session as ses, sharecard, tripshare
from gitaway.icons import icon
from gitaway.layout import join_note, page

PATH = "/trip/share"
HEAD = (Link(rel="stylesheet", href="/assets/css/share.css"),)
SCRIPTS = ("/assets/js/share.js",)
NOT_SHOWN = "The card shows the title, the place, where from and to, the month and the length. Never a booking, a price, an email, a hotel or who is travelling unless you say it."


class CardCache:
    """The rendered PNGs, a small LRU keyed by the card's contents (D-495): a repeated or varying `?v=` costs one render, never a thread each. At most `cap` pictures
    (about 150 KB each); a share that is stopped drops its own."""

    def __init__(self, cap=24):
        self.cap, self.items, self.lock = cap, OrderedDict(), Lock()

    def get(self, token, card):
        key = (token, hashlib.sha1(repr(card).encode()).hexdigest())
        with self.lock:
            if key in self.items:
                self.items.move_to_end(key)
                return self.items[key]
        png = sharecard.render(card)
        with self.lock:
            self.items[key] = png
            while len(self.items) > self.cap:
                self.items.popitem(last=False)
        return png

    def drop(self, token):
        with self.lock:
            for key in [k for k in self.items if k[0] == token]:
                del self.items[key]


CARDS = CardCache()


def card_path(sh) -> str:
    """The card's address, with a short fingerprint of what it says so a changed card is a new address (caches keep the old one)."""
    v = hashlib.sha1(json.dumps([sh.title, sh.place, sh.art, sh.route, sh.month, sh.exact, sh.days, sh.names, sh.link()]).encode()).hexdigest()[:8]
    return f"/s/{quote(sh.token, safe='')}/card.png?v={v}"


def _button(trip_label="Share to Instagram"):
    """The cockpit's button (a link to the sheet's own page until share.js turns it into the grow-out sheet)."""
    return A(icon("share", 18, 2.4), Span(trip_label), href=PATH, cls="sh-open", id="sh-open", aria_haspopup="dialog")


def open_button(role):
    """What the cockpit draws beside its date chips: the button, for anyone who may change the trip's plans (a viewer cannot make a public link). Styles and script ride the cockpit's HEAD and SCRIPTS."""
    return _button() if access.can_edit(role) else ""


def _toggle(name, on, label, hint):
    return Label(Input(type="checkbox", name=name, value="1", checked=on or None, cls="sr-only sh-cb"), Span(cls="sh-sw", aria_hidden="true"),
                 Span(Span(label, cls="sh-t"), Span(hint, cls="sh-h"), cls="sh-tt"), cls="sh-toggle")


def sheet(sh, names_hint, exact_hint):
    """The sheet's contents, for the dialog and for the page of its own."""
    colours = ("flight", "stay", "car", "food", "tix", "see")
    return Div(
        Div(H2("Share to Instagram", id="sh-title"), Button(icon("x", 18, 2.6), type="button", cls="sh-x", aria_label="Close", data_close="1"), cls="sh-head"),
        Div(Div(*[Span(cls=f"sh-dot sh-d{i}", style=f"--k:var(--k-{c})", aria_hidden="true") for i, c in enumerate(colours * 2)], cls="sh-dots"),
            Img(src=card_path(sh), alt=f"Your trip card: {sh.title}, {sh.place}, {sh.exact or sh.month}, {sh.days} days", width=1080, height=1350, cls="sh-img", id="sh-img"),
            cls="sh-card"),
        Form(_toggle("names", bool(sh.names), "Say our first names", names_hint or "No names to show: they are read from a first.last email address"),
             _toggle("exact", bool(sh.exact), "Show the exact dates", exact_hint),
             Button("Update the card", cls="btn btn-sm sh-update", type="submit"), method="post", action=PATH, id="sh-form", cls="sh-form"),
        Div(Button(icon("share", 18, 2.4), "Share", type="button", cls="btn btn-ink sh-share", id="sh-share", hidden=True),
            A(icon("image", 18, 2.4), "Download the card", href=card_path(sh), download="trip-card.png", cls="btn sh-dl", id="sh-dl"),
            Button(icon("link", 18, 2.4), "Copy link", type="button", cls="btn sh-copy", id="sh-copy"), cls="sh-acts"),
        Input(value=sh.link(), readonly=True, aria_label="The link back", cls="sh-link", id="sh-link"),
        P(NOT_SHOWN, cls="sh-priv"), P("", cls="sh-live", id="sh-live", role="status"),
        Form(Button("Stop sharing this trip", type="submit", cls="sh-stop"), method="post", action=f"{PATH}/off", cls="sh-offf", id="sh-off"),
        cls="sh-body", data_link=sh.link())


def create_sheet():
    """The sheet of a trip that is not shared (never shared, or stopped): what sharing makes, and the one button that makes it."""
    return Div(
        Div(H2("Share to Instagram", id="sh-title"), Button(icon("x", 18, 2.6), type="button", cls="sh-x", aria_label="Close", data_close="1"), cls="sh-head"),
        P("Make a card of this trip for Instagram and a link back to it. You choose whether it says your first names and the exact dates.", cls="sh-priv"),
        P(NOT_SHOWN, cls="sh-priv"), P("", cls="sh-live", id="sh-live", role="status"),
        Form(Button(icon("share", 18, 2.4), "Create link", type="submit", cls="btn btn-ink sh-create", id="sh-create"), method="post", action=PATH, cls="sh-form", id="sh-make"),
        cls="sh-body", data_link="")


def _gate(session):
    if (r := phone.guard(session, PATH)):
        return r
    if not access.can_edit(access.request_role()):
        return Response("Only editors can share a trip.", status_code=403, media_type="text/plain")
    return None


def public_page(sh):
    link = sh.link()
    art = placeart.art(sh.art, wx=None) if sh.art else None
    route = [Span(s, cls="sp-stop") for s in sh.route]
    return page(sh.title, Section(
        Div(Div(NotStr(art) if art else "", cls="sp-art"),
            Div(Span(f"{sh.days} day{'s' if sh.days != 1 else ''}", cls="sp-pill"), H1(sh.title), P(" · ".join(x for x in (sh.place, sh.month) if x), cls="sp-sub"),
                Div(*[x for i, s in enumerate(route) for x in ((s, Span("→", cls="sp-arrow", aria_hidden="true")) if i < len(route) - 1 else (s,))], cls="sp-route") if route else "",
                P("A family planned this trip on GitAway: flights, stays and days on one calendar.", cls="sp-note"),
                A("Plan your own trip", href="/start", cls="btn btn-ink sp-cta"), cls="sp-body"), cls="sp-card"),
        cls="ga-wrap sp-wrap"),
        head=HEAD, noindex=True, description=f"{sh.title}: {sh.days} days in {sh.place or 'a new place'}, planned on GitAway.", image=blogbutton.base_url() + card_path(sh),
        og_type="article")


def register(app):
    @app.get(PATH)
    def share_sheet(request, session):
        if (r := _gate(session)):
            return r
        sh = tripshare.find_open(session)      # read-only: a GET never makes, changes or revives a share (a stopped one stays stopped until "Create link" is posted)
        body = sheet(sh, tripshare.first_names(session), tripshare.snapshot(session, exact=True)["exact"]) if sh else create_sheet()
        if request.headers.get("x-share") == "1":
            return HTMLResponse(to_xml(Div(body, cls="sh-frag", data_sheet="1")), headers={"Cache-Control": "no-store"})
        return phone.shell("trip", join_note(), Main(Div(H1("Share to Instagram", cls="sh-page-h"), body, cls="sh-page"), id="main", cls="ph-main"), title="Share the trip", head=HEAD, scripts=SCRIPTS)

    @app.post(PATH)
    def share_save(request, session, names: str = "", exact: str = ""):
        if (r := _gate(session)):
            return r
        sh = tripshare.save(session, names == "1", exact == "1")
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"link": sh.link(), "card": card_path(sh), "names": sh.names, "exact": sh.exact}, headers={"Cache-Control": "no-store"})
        return RedirectResponse(PATH, status_code=303)

    @app.post(f"{PATH}/off")
    def share_off(request, session):
        if (r := _gate(session)):
            return r
        CARDS.drop(tripshare.off(session))
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"off": True}, headers={"Cache-Control": "no-store"})
        return RedirectResponse("/trip/cockpit", status_code=303)

    @app.get("/s/{token}")
    def share_page(token: str):
        sh = tripshare.find(token)
        if not sh:
            return FtResponse(page("Not shared", Section(Div(H1("This trip is not shared"), P("The link was turned off, or it is not right."), A("Plan a trip", href="/start", cls="btn btn-ink"), cls="ga-wrap"),
                                                        cls="ga-soon ga-wrap"), noindex=True), status_code=404)
        return public_page(sh)

    @app.get("/s/{token}/card.png")
    def share_card(token: str):
        sh = tripshare.find(token)
        if not sh:
            return Response("not found", status_code=404, media_type="text/plain")
        return Response(CARDS.get(sh.token, sh.card()), media_type="image/png", headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"})
