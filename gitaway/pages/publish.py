"""Publish a family trip as a creator page (F-181), and the public photos of a published trip.

GET  /trip/publish                the editor: name and title, stickers, the cover, a note and the photos for each day, tips (editors and admins; a viewer is told to ask)
POST /trip/publish/save           keep the choices (do=preview goes on to the preview, else back to the editor)
GET  /trip/publish/preview        the public page exactly as strangers will see it, with Publish (or Update) and Back
POST /trip/publish                publish or update: public copies of the photos (stripped of EXIF and position) and the snapshot
POST /trip/publish/unpublish      take the public page and its photo copies down (who published it, or a family admin)
GET  /pub/<slug>/<file>           a published trip's public photo (`<16 hex>-display.jpg` / `-thumb.jpg`), public and cacheable; the family's own photos stay at /trip/photos

The writes need the editor role like every other POST (gitaway.access); the rules and the storage are gitaway/publish.py, the page itself is itinerary_view.
"""

from urllib.parse import quote

from fasthtml.common import A, Button, Details, Div, Fieldset, Form, H1, H2, H3, Img, Input, Label, Legend, Link, P, Script, Section, Span, Summary, Textarea
from fasthtml.core import FtResponse
from starlette.responses import FileResponse, RedirectResponse, Response

from gitaway import access, community, hub, phone, publish, session as ses
from gitaway.hub import HubError
from gitaway.icons import icon
from gitaway.itinerary_view import HEAD as VIEW_HEAD, _icon, itinerary_body
from gitaway.layout import page, trip_field

PATH = "/trip/publish"
HEAD = (Link(rel="stylesheet", href="/assets/css/scrapbook.css"), Script(src="/assets/js/publish.js", defer=True))
WHAT_IS_PUBLIC = "Strangers see your title, your name, the days, the plans and their times, your notes and tips, and the photos you pick."
WHAT_IS_NOT = "Never shown: booking and confirmation numbers, dates, flight numbers, hotel names and addresses (only the area), prices, who is in your family, chat, and where a photo was taken."


def _signin(path=PATH):
    return RedirectResponse(f"/signin?next={quote(path, safe='/')}&intent=publish", status_code=303)


def _sorry(title, message, status=403):
    return FtResponse(page(title, Section(Div(H1(title), P(message), A("Back to the trip", href="/trip", cls="btn btn-primary"), cls="ga-wrap"), cls="ga-soon ga-wrap")), status_code=status)


def _gate(session):
    """The redirect or the refusal a request gets before the editor, or None when this person may publish the open trip."""
    if (r := phone.guard(session, PATH)):
        return r
    if not access.can_edit(access.request_role()):
        return _sorry("Only editors can publish", publish.NEEDS_EDITOR)
    return None


def _pill(kind, name, value, label, on, ico=""):
    return Label(Input(type=kind, name=name, value=value, checked=on or None, cls="sr-only"), Span(_icon(ico, 18, 2.2) if ico else "", label, cls="pb-pill"))


def _tile(p, picked, cover, fresh, me):
    pid = p["id"]
    by = Span(f"Added by {(str(p['author_name']).split() or ['a family member'])[0]}: check with them", cls="pb-by") if p["author"] != me else ""     # F-182: another member's photo goes public only if its publisher means it to
    return Div(
        Label(Input(type="checkbox", name="photos", value=pid, checked=pid in picked or pid in fresh or None, cls="sr-only pb-pick"),
              Img(src=f"/trip/photos/{pid}/thumb", alt=p["plan_title"] or p["caption"] or "A photo from the trip", loading="lazy"),
              Span(icon("check", 16, 3), cls="pb-tick", aria_hidden="true"), cls="pb-photo"),
        by,
        Label(Input(type="radio", name="cover", value=pid, checked=pid == cover or None, cls="sr-only pb-cover"),
              Span(icon("star", 16, 2.4), Span("Cover", cls="pb-cover-t"), cls="pb-cover-b"), title="Use as the cover photo"),
        cls="pb-tile")


def _day(day, d, fresh, me):
    n = day["n"]
    return Fieldset(
        Legend(Span(f"Day {n}", cls="pb-day-n"), Span(f"{day['date']:%a %b} {day['date'].day}", cls="pb-day-date")),
        Label("A note for this day", Span(f"Short, in your own words ({publish.MAX_NOTE} characters)", cls="pb-hint"), fr=f"pb-note-{n}", cls="pb-lab"),
        Textarea(d["notes"].get(str(n), ""), id=f"pb-note-{n}", name=f"note_{n}", rows="2", maxlength=str(publish.MAX_NOTE), placeholder="What was this day like?", cls="pb-note"),
        Div(*[_tile(p, d["photos"], d["cover"], fresh, me) for p in day["photos"]], cls="pb-grid") if day["photos"] else P("No photos on this day yet.", cls="pb-none"),
        cls="pb-day")


def _status(live):
    if not live:
        return Span(icon("note", 16, 2.4), "Draft: nobody can see this yet", cls="pb-chip")
    return Span(icon("check", 16, 3), "Live", cls="pb-chip pb-chip-live")


def _unpublish(live):
    return Details(Summary(icon("x", 18, 2.4), Span("Unpublish"), cls="pb-unpub", id="pb-unpublish"),
                   Form(P("This takes the page and its photo copies off GitAway for everyone. Your draft stays here, so you can publish again."), trip_field(),
                        Button("Yes, take it down", type="submit", id="pb-unpublish-yes", cls="btn btn-sm pb-unpub-yes"), action=f"{PATH}/unpublish", method="post", cls="pb-unpub-form"),
                   cls="pb-confirm") if live else ""


def editor_page(session, live=None, fresh=(), error="", just=False):
    d = publish.get(session)
    days = publish.editor_days(session)
    c = community.creator_of(ses.current_traveler(session).id)
    tips = (d["tips"] + [""] * 3)[:max(3, min(len(d["tips"]) + 1, publish.MAX_TIPS))]   # three boxes, one more once they are used, at most five
    n_photos = sum(len(x["photos"]) for x in days)
    top = Div(H1("Publish this trip"), _status(live),
              P(WHAT_IS_PUBLIC, cls="pb-lede"), P(WHAT_IS_NOT, cls="pb-never"), cls="pb-top")
    done = Div(Span(icon("check", 22, 2.6), "It's live", cls="pb-chip pb-chip-live"),
               P("Anyone can read it and fork it now. Publish again to update it."),
               Div(A(icon("share", 20), "View your trip page", href=f"/trips/{live['slug']}", cls="btn btn-primary", id="pb-view"),
                   A("See it in Community trips", href="/community", cls="btn"), cls="pb-actions"), cls="pb-live card", role="status") if live and just else ""
    add = Div(Label(icon("plus", 20, 2.4), Span("Add photos from your phone"), Input(type="file", name="photo", accept="image/jpeg,image/png,image/webp,image/heic,image/heif,image/*", multiple=True, id="pb-add", cls="sr-only"), cls="btn pb-add-b", fr="pb-add"),
              Span(role="status", aria_live="polite", id="pb-add-say", cls="pb-hint"), cls="pb-addrow")
    form = Form(
        trip_field(),
        Div(Label("Title", fr="pb-title", cls="pb-lab"),
            Input(type="text", id="pb-title", name="title", value=d["title"], maxlength=str(publish.MAX_TITLE), autocomplete="off", cls="pb-input"),
            Label("Your name on it", Span("Shown as the creator. Your profile address stays the same once you publish.", cls="pb-hint"), fr="pb-name", cls="pb-lab"),
            Input(type="text", id="pb-name", name="name", value=d["name"], maxlength=str(publish.MAX_NAME), autocomplete="name", cls="pb-input"),
            Span(f"gitaway.me/creators/{c['handle']}", cls="pb-handle") if c else "", cls="pb-card card"),
        Fieldset(Legend("Who is it good for?"), Div(*[_pill("checkbox", "stickers", k, label, k in d["stickers"], ico) for k, (label, _t, ico) in hub.TAGS.items()], cls="pb-picks"), cls="pb-card card pb-stickers"),
        Div(H2("Photos and notes"), P(f"Tap a photo to include it. Tap the star to make it the cover. {n_photos} on this trip so far." if n_photos else "No photos on this trip yet. Add some below.", cls="pb-hint"),
            add, cls="pb-sec"),
        *[_day(day, d, fresh, ses.current_traveler(session).id) for day in days],
        Fieldset(Legend("A few tips"), *[Input(type="text", name="tip", value=t, maxlength=str(publish.MAX_TIP), placeholder="One thing you'd tell a friend going", autocomplete="off", aria_label=f"Tip {i + 1}", cls="pb-input")
                                         for i, t in enumerate(tips)], cls="pb-card card pb-tips"),
        Div(P(error, role="alert", cls="pb-error", id="pb-error") if error else "",
            Button(icon("image", 20, 2.4), "Preview what strangers see", type="submit", name="do", value="preview", cls="btn btn-primary", id="pb-preview"),
            Button("Save draft", type="submit", name="do", value="save", cls="btn", id="pb-save"), cls="pb-bar"),
        action=f"{PATH}/save", method="post", id="pb-form", cls="pb-form")
    return page("Publish this trip", Section(top, done, form, _unpublish(live), cls="pb ga-wrap"), head=HEAD)


def preview_page(session, live=None, error=""):
    trip = publish.preview(session)
    warn = publish.mentions(session, trip)
    bar = Div(
        Div(Span(icon("image", 18, 2.4), "This is exactly what strangers will see", cls="pb-pv-t"),
            P("Your photos here are your private copies; the published ones are rebuilt without where they were taken.", cls="pb-hint"),
            *([P(f"It mentions {publish.join_names(warn)} from your family. Check they're happy to be on a public page.", role="note", cls="pb-warn", id="pb-warn")] if warn else []),
            P(error, role="alert", cls="pb-error", id="pb-error") if error else "", cls="pb-pv-text"),
        Div(Form(trip_field(),
                 Label(Input(type="checkbox", name="names_ok", value="1", id="pb-names-ok", cls="pb-names-box"), Span(f"Yes, {publish.join_names(warn)} {'is' if len(warn) == 1 else 'are'} happy to be named", cls="pb-names-t"), cls="pb-names") if warn else "",
                 Button(icon("check", 20, 2.6), "Update the public page" if live else "Publish", type="submit", id="pb-publish", cls="btn btn-primary"), action=PATH, method="post"),
            A(icon("chev-left", 18, 2.4), "Back to edit", href=PATH, cls="btn", id="pb-back"), cls="pb-pv-act"),
        cls="pb-pv", id="pb-pv", role="region", aria_label="Preview")
    return page(trip.title, bar, itinerary_body(trip), head=(*VIEW_HEAD, *HEAD), theme=trip.theme)


def register(app):
    @app.get(PATH)
    def editor(session, added: str = "", live: str = ""):
        if (r := _gate(session)):
            return r
        return editor_page(session, publish.live(session), fresh={x for x in added.split(",") if x}, just=live == "1")

    @app.post(PATH + "/save")
    async def save(request, session):
        if not ses.current_traveler(session):
            return _signin()
        f = await request.form()
        data = {"title": f.get("title"), "name": f.get("name"), "cover": f.get("cover"), "stickers": f.getlist("stickers"), "photos": f.getlist("photos"), "tip": f.getlist("tip"),
                **{k: f.get(k) for k in f.keys() if k.startswith("note_")}}
        try:
            publish.save(session, data)
        except HubError as e:
            return editor_page(session, publish.live(session), error=str(e))
        if request.headers.get("x-fragment") == "1":
            return Response(status_code=204)
        return RedirectResponse(PATH + "/preview" if f.get("do") == "preview" else PATH, status_code=303)

    @app.get(PATH + "/preview")
    def preview(session):
        if (r := _gate(session)):
            return r
        return preview_page(session, publish.live(session))

    @app.post(PATH)
    def go(session, names_ok: str = ""):
        if not ses.current_traveler(session):
            return _signin()
        try:
            publish.publish(session, names_ok == "1")
        except HubError as e:
            return FtResponse(preview_page(session, publish.live(session), str(e)), status_code=409)
        return RedirectResponse(PATH + "?live=1", status_code=303)

    @app.post(PATH + "/unpublish")
    def unpublish(session):
        if not ses.current_traveler(session):
            return _signin()
        try:
            publish.unpublish(session, access.request_role())
        except PermissionError as e:
            return _sorry("Not yours to take down", str(e))
        return RedirectResponse(PATH, status_code=303)

    @app.get("/pub/{slug}/{filename}")
    def public_photo(request, slug: str, filename: str):
        path = publish.public_file(slug, filename)
        if path is None:
            return Response("Not found.", status_code=404)
        headers = {"Cache-Control": "public, no-cache", "X-Content-Type-Options": "nosniff", "ETag": f'"{filename}-{path.stat().st_mtime_ns}"'}
        if request.headers.get("if-none-match") == headers["ETag"]:
            return Response(status_code=304, headers=headers)
        return FileResponse(path, media_type="image/jpeg", headers=headers)
