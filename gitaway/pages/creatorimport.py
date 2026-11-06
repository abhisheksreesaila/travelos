"""A creator pastes a link or text and gets a draft trip they review and publish (F-183). The rules are gitaway/creatordraft.py (and importsource, safefetch, ai); these are the screens.

GET  /creators/import                     the paste page: a link and/or text; "Draft my trip" (the model), "Write it myself" (an empty draft)
POST /creators/import                     read the post, draft it, go to the editor (or say plainly why not)
GET  /creators/import/<id>                the editor: title, name, place, days with stops, tips, the post's pictures to pick from, the source card
POST /creators/import/<id>                do=save, do=preview (save, then the preview), add_stop:<d>, del_stop:<d>:<s>, add_day, del_day:<d>; do=publish (needs the "own" tick); do=unpublish
GET  /creators/import/<id>/preview        the public page exactly as strangers will see it, with "This is my post" and Publish
GET  /creators/import/<id>/photo/<file>   a picked picture for its owner's preview

A draft belongs to the person who made it (anyone else gets a 404) and needs no family trip. The one POST path under /creators/import/ is open to every member in gitaway.access (it changes no family plan);
its parameter is called `token` because tests/test_roles.py matches the open prefixes that way.
"""

from urllib.parse import quote

from fasthtml.common import A, Button, Details, Div, Fieldset, Form, H1, H2, Img, Input, Label, Legend, Link, Option, P, Script, Section, Select, Span, Summary, Textarea
from fasthtml.core import FtResponse
from starlette.responses import FileResponse, RedirectResponse, Response

from gitaway import ai, creatordraft as cd, importsource, session as ses
from gitaway.hub import HubError
from gitaway.icons import icon
from gitaway.itinerary_view import HEAD as VIEW_HEAD, _icon, itinerary_body
from gitaway.layout import page
from gitaway import hub

PATH = "/creators/import"
HEAD = (Link(rel="stylesheet", href="/assets/css/scrapbook.css"), Link(rel="stylesheet", href="/assets/css/creatorimport.css"), Script(src="/assets/js/creatorimport.js", defer=True))
STOP_MAX = cd.MAX_STOP
NOTHING = "Paste the link to your post, or the text of it."


def _signin(path):
    return RedirectResponse(f"/signin?next={quote(path, safe='/')}&intent=publish", status_code=303)


def _gone():
    return FtResponse(page("Not found", Section(Div(H1("Nothing here"), P("That draft is not yours, or it is gone."), A("Start a new one", href=PATH, cls="btn btn-primary"), cls="ga-wrap"), cls="ga-soon ga-wrap")), status_code=404)


# ---- paste ---------------------------------------------------------------------------------------------------------------

def paste_page(session, link="", text="", error="", status=200):
    mode = cd.mode()
    note = P(cd.NOT_ON, role="status", cls="ci-note", id="ci-off") if mode == "manual" else P("Sample mode: no AI key is set on this copy, so a made-up draft stands in for the real one.", role="status", cls="ci-note", id="ci-sample") if mode == "sample" else ""
    form = Form(
        Label(Span("The link to your post", cls="ci-lab"), Span("A blog post, a YouTube video, or an Instagram post.", cls="ci-hint"), fr="ci-link"),
        Input(type="text", inputmode="url", id="ci-link", name="link", value=link, placeholder="https://", autocomplete="off", maxlength=str(importsource.MAX_LINK), cls="ci-input", aria_describedby="ci-links"),
        P("Blog: we read the article and offer its pictures. YouTube: we read the title, description and chapters; paste the transcript below for a better draft. Instagram does not let anyone read a post, so paste the caption below and we keep your link as the source.",
          id="ci-links", cls="ci-hint"),
        Label(Span("Or paste the text", cls="ci-lab"), Span("The post itself, a caption or a transcript. This always works.", cls="ci-hint"), fr="ci-text"),
        Textarea(text, id="ci-text", name="text", rows="7", maxlength=str(importsource.MAX_PASTE), placeholder="Day 1: we started at the pier...", cls="ci-input ci-text"),
        P(error, role="alert", cls="ci-error", id="ci-error") if error else "",
        Div(Button(icon("star", 20, 2.4), "Draft my trip", type="submit", name="do", value="draft", cls="btn btn-primary", id="ci-draft"),
            Button("Write it myself", type="submit", name="do", value="manual", cls="btn", id="ci-manual"), cls="ci-actions"),
        action=PATH, method="post", id="ci-form", cls="ci-form card")
    skeleton = Div(Div(cls="skeleton ci-sk-line ci-sk-title"), Div(cls="skeleton ci-sk-line"), *[Div(cls="skeleton ci-sk-day") for _ in range(3)],
                   Span("Reading your post and drafting the days…", cls="ci-sk-say"),
                   cls="ci-skel", id="ci-skel", hidden=True, role="status", aria_busy="true", aria_label="Drafting your trip")
    body = Section(Div(H1("Turn your post into a trip"), P("Paste a link or your text. GitAway drafts the days, you fix what is off, and nothing is public until you tick \"This is my post\" and publish.", cls="ci-lede"), note, cls="ci-top"),
                   form, skeleton, cls="ci ga-wrap")
    return FtResponse(page("Turn your post into a trip", body, current="/creators", head=HEAD), status_code=status)


def _read(session, link, text, how):
    """The draft a paste becomes, or (None, message). `how` is "draft" or "manual" ("Write it myself": nothing is fetched and no model is asked)."""
    me = ses.current_traveler(session)
    name = me.name if me else ""
    try:
        if how == "manual" or cd.mode() == "manual":
            if how != "manual" and not text.strip():
                return None, cd.NOT_ON
            why = "" if how == "manual" else cd.NOT_ON + " Your text is shown beside the editor to write from."
            return cd.blank(me.id, importsource.offline(link, text), name, why), ""
        if not cd.allow(me.id):
            return None, cd.LIMIT_HIT
        if cd.mode() == "sample":      # the local showcase's simulated draft: nothing is fetched and no model is asked
            return cd.sample(me.id, importsource.offline(link, text), name), ""
        return cd.make(me.id, me.id, importsource.gather(link, text), name), ""
    except importsource.SourceError as e:
        return None, str(e)
    except (ai.AIError, HubError) as e:
        return None, str(e)


# ---- the editor ---------------------------------------------------------------------------------------------------------

def _pill(name, value, label, on, ico=""):
    return Label(Input(type="checkbox", name=name, value=value, checked=on or None, cls="sr-only"), Span(_icon(ico, 18, 2.2) if ico else "", label, cls="pb-pill"))


def _stop(i, j, s):
    k = f"d{i}s{j}"
    return Div(Input(type="text", name=f"{k}_time", value=s["time"], placeholder="9:00 AM", maxlength="12", autocomplete="off", aria_label=f"Day {i + 1} stop {j + 1} time", cls="pb-input ci-time"),
               Input(type="text", name=f"{k}_name", value=s["name"], placeholder="Where", maxlength=str(STOP_MAX), autocomplete="off", aria_label=f"Day {i + 1} stop {j + 1} name",
                     aria_invalid="true" if s["name"] == cd.UNNAMED else None, cls="pb-input ci-name" + (" ci-unsure" if s["name"] == cd.UNNAMED else "")),
               Input(type="text", name=f"{k}_note", value=s["note"], placeholder="A short note (optional)", maxlength=str(cd.MAX_STOP_NOTE), autocomplete="off", aria_label=f"Day {i + 1} stop {j + 1} note", cls="pb-input ci-snote"),
               Button(icon("x", 18, 2.4), type="submit", name="do", value=f"del_stop:{i}:{j}", formnovalidate=True, aria_label=f"Remove stop {j + 1} from day {i + 1}", cls="btn ci-del"), cls="ci-stop")


def _day(i, day, many):
    return Fieldset(
        Legend(Span(f"Day {i + 1}", cls="pb-day-n")),
        Input(type="text", name=f"d{i}_title", value=day["title"], maxlength=str(cd.MAX_DAY_TITLE), placeholder="A title for the day", autocomplete="off", aria_label=f"Day {i + 1} title", cls="pb-input"),
        Textarea(day["note"], name=f"d{i}_note", rows="2", maxlength=str(cd.MAX_NOTE), placeholder="What was this day like? (optional, in your own words)", aria_label=f"Day {i + 1} note", cls="pb-note"),
        *[_stop(i, j, s) for j, s in enumerate(day["stops"])],
        Div(Button(icon("plus", 18, 2.4), "Add a stop", type="submit", name="do", value=f"add_stop:{i}", formnovalidate=True, cls="btn ci-add"),
            Button("Remove this day", type="submit", name="do", value=f"del_day:{i}", formnovalidate=True, cls="btn ci-add") if many else "", cls="ci-row"),
        cls="pb-day ci-day")


def _tile(d, n, url):
    copy = d["copies"].get(str(n))
    src = f"/creators/import/{d['id']}/photo/{copy}-thumb.jpg" if copy else url
    return Div(Label(Input(type="checkbox", name="pick", value=str(n), checked=n in d["picks"] or None, cls="sr-only pb-pick"),
                     Img(src=src, alt=f"Picture {n + 1} from your post", loading="lazy", referrerpolicy="no-referrer"), Span(icon("check", 16, 3), cls="pb-tick", aria_hidden="true"), cls="pb-photo"),
               Label(Input(type="radio", name="cover", value=str(n), checked=str(n) == d["cover"] or None, cls="sr-only pb-cover"),
                     Span(icon("star", 16, 2.4), Span("Cover", cls="pb-cover-t"), cls="pb-cover-b"), title="Use as the cover photo"), cls="pb-tile")


def _source_card(d):
    s = d.get("source") or {}
    if not s.get("url"):
        return ""
    return Div(Span("Your post", cls="ci-kicker"), A(s.get("title") or s["url"], href=s["url"], rel="noopener noreferrer", target="_blank", cls="ci-src-link"),
               Span(s.get("by") or "", cls="ci-hint") if s.get("by") else "", cls="ci-source card", id="ci-source")


def editor_page(d, error="", just=False):
    place = Select(*[Option(label, value=k, selected=k == d["place"] or None) for k, label in [*cd.PLACES.items(), ("other", "Somewhere else")]], name="place", id="ci-place", cls="pb-input")
    unsure = sum(1 for day in d["days"] for s in day["stops"] if s["name"] == cd.UNNAMED)
    top = Div(H1("Check your draft"), Span(icon("check", 16, 3), "Live", cls="pb-chip pb-chip-live") if d["live"] else Span(icon("note", 16, 2.4), "Draft: nobody can see this yet", cls="pb-chip"),
              P("GitAway read your post. Fix anything that is off: nothing is public until you tick \"This is my post\" and publish.", cls="pb-lede"),
              *[P(n, role="note", cls="ci-note", id=f"ci-notice-{i}") for i, n in enumerate(d["notices"])],
              P(f"{unsure} stop{'s' if unsure != 1 else ''} GitAway was not sure of {'are' if unsure != 1 else 'is'} marked \"{cd.UNNAMED}\". Name {'them' if unsure != 1 else 'it'} or take {'them' if unsure != 1 else 'it'} out.",
                role="note", cls="ci-note ci-unsure-note", id="ci-unsure") if unsure else "", cls="pb-top")
    done = Div(Span(icon("check", 22, 2.6), "It's live", cls="pb-chip pb-chip-live"), P("Anyone can read it and fork it now. Publish again to update it."),
               Div(A(icon("share", 20), "View your trip page", href=f"/trips/{d['slug']}", cls="btn btn-primary", id="pb-view"), A("See it in Community trips", href="/community", cls="btn"), cls="pb-actions"),
               cls="pb-live card", role="status") if d["live"] and just else ""
    paste = Details(Summary("Your pasted text"), P(d["text"], cls="ci-pasted"), cls="ci-details card", id="ci-pasted") if d.get("text") else ""
    tips = (d["tips"] + [""] * 3)[:max(3, min(len(d["tips"]) + 1, cd.MAX_TIPS))]
    pics = Div(H2("Pictures from your post"), P(f"Optional. Tap up to {cd.MAX_PICKS} to put on your page; they are copied from your own post and stripped of where they were taken. Tap the star for the cover.", cls="pb-hint"),
               Div(*[_tile(d, n, u) for n, u in enumerate(d["images"])], cls="pb-grid"), cls="pb-sec ci-pics", id="ci-pics") if d["images"] else ""
    form = Form(
        Button("Save", type="submit", name="do", value="save", cls="sr-only", tabindex="-1", aria_hidden="true"),     # Enter in a field saves; it never removes a stop
        Div(Label("Title", fr="ci-title", cls="pb-lab"), Input(type="text", id="ci-title", name="title", value=d["title"], maxlength=str(cd.MAX_TITLE), autocomplete="off", cls="pb-input"),
            Label("Your name on it", fr="ci-name", cls="pb-lab"), Input(type="text", id="ci-name", name="name", value=d["name"], maxlength=str(cd.MAX_NAME), autocomplete="name", cls="pb-input"),
            Label("Where was it?", fr="ci-place", cls="pb-lab"), place,
            Input(type="text", id="ci-place-name", name="place_name", value=d["place_name"], maxlength=str(cd.MAX_PLACE), placeholder="Name the place", autocomplete="off", aria_label="Name of the place", cls="pb-input"),
            cls="pb-card card"),
        Fieldset(Legend("Who is it good for?"), Div(*[_pill("stickers", k, label, k in d["stickers"], ico) for k, (label, _t, ico) in hub.TAGS.items()], cls="pb-picks"), cls="pb-card card pb-stickers"),
        Div(H2("Days and stops"), P("Times are optional. Add what the post leaves out.", cls="pb-hint"), cls="pb-sec"),
        *[_day(i, day, len(d["days"]) > 1) for i, day in enumerate(d["days"])],
        Button(icon("plus", 18, 2.4), "Add a day", type="submit", name="do", value="add_day", formnovalidate=True, cls="btn ci-add-day", id="ci-add-day") if len(d["days"]) < cd.MAX_DAYS else "",
        Fieldset(Legend("A few tips"), *[Input(type="text", name="tip", value=t, maxlength=str(cd.MAX_TIP), placeholder="One thing you'd tell a friend going", autocomplete="off", aria_label=f"Tip {i + 1}", cls="pb-input")
                                         for i, t in enumerate(tips)], cls="pb-card card pb-tips"),
        pics,
        Div(P(error, role="alert", cls="pb-error", id="pb-error") if error else "",
            Button(icon("image", 20, 2.4), "Preview what strangers see", type="submit", name="do", value="preview", cls="btn btn-primary", id="pb-preview"),
            Button("Save draft", type="submit", name="do", value="save", cls="btn", id="pb-save"), cls="pb-bar"),
        action=f"{PATH}/{d['id']}", method="post", id="ci-edit", cls="pb-form")
    unpub = Details(Summary(icon("x", 18, 2.4), Span("Unpublish"), cls="pb-unpub", id="pb-unpublish"),
                    Form(P("This takes the page off GitAway for everyone. Your draft stays here, so you can publish again."), Input(type="hidden", name="do", value="unpublish"),
                         Button("Yes, take it down", type="submit", id="pb-unpublish-yes", cls="btn btn-sm pb-unpub-yes"), action=f"{PATH}/{d['id']}", method="post", cls="pb-unpub-form"), cls="pb-confirm") if d["live"] else ""
    return page("Check your draft", Section(top, done, _source_card(d), paste, form, unpub, cls="pb ci-edit ga-wrap"), current="/creators", head=HEAD)


def preview_page(session, d, error=""):
    trip = cd.preview(ses.current_traveler(session).id, d)
    todo = cd.problems(d)
    bar = Div(
        Div(Span(icon("image", 18, 2.4), "This is exactly what strangers will see", cls="pb-pv-t"),
            P("Your photos here are private copies; the published ones are the same pictures without where they were taken.", cls="pb-hint"),
            *([P(" ".join(todo), role="alert", cls="pb-error", id="pb-problems")] if todo else []),
            P(error, role="alert", cls="pb-error", id="pb-error") if error else "", cls="pb-pv-text"),
        Div(Form(Label(Input(type="checkbox", name="own", value="1", id="ci-own", cls="ci-own"), Span("This is my post", cls="ci-own-t"), cls="ci-own-l"),
                 Button(icon("check", 20, 2.6), "Update the public page" if d["live"] else "Publish", type="submit", name="do", value="publish", id="pb-publish", cls="btn btn-primary"),
                 action=f"{PATH}/{d['id']}", method="post", cls="ci-pub"),
            A(icon("chev-left", 18, 2.4), "Back to edit", href=f"{PATH}/{d['id']}", cls="btn", id="pb-back"), cls="pb-pv-act"),
        cls="pb-pv", id="pb-pv", role="region", aria_label="Preview")
    return page(trip.title or "Your trip", bar, itinerary_body(trip), head=(*VIEW_HEAD, *HEAD), theme=trip.theme)


def register(app):
    @app.get(PATH)
    def paste(session):
        if not ses.current_traveler(session):
            return _signin(PATH)
        return paste_page(session)

    @app.post(PATH)
    async def draft(request, session):
        if not ses.current_traveler(session):
            return _signin(PATH)
        f = await request.form()
        link, text, how = str(f.get("link") or "").strip(), str(f.get("text") or ""), "manual" if f.get("do") == "manual" else "draft"
        if not link and not text.strip() and how == "draft":
            return paste_page(session, "", "", NOTHING, 422)
        made, error = _read(session, link, text, how)
        if made is None:
            return paste_page(session, link, text, error, 422)
        return RedirectResponse(f"{PATH}/{made['id']}", status_code=303)

    @app.get(PATH + "/{token}")
    def editor(session, token: str, live: str = ""):
        me = ses.current_traveler(session)
        if not me:
            return _signin(f"{PATH}/{token}")
        d = cd.get(me.id, token)
        return editor_page(d, just=live == "1") if d else _gone()

    @app.post(PATH + "/{token}")
    async def act(request, session, token: str):
        me = ses.current_traveler(session)
        if not me:
            return _signin(f"{PATH}/{token}")
        d = cd.get(me.id, token)
        if not d:
            return _gone()
        f = await request.form()
        do = str(f.get("do") or "save")
        if do == "unpublish":
            cd.unpublish(session, d)
            return RedirectResponse(f"{PATH}/{token}", status_code=303)
        if do == "publish":
            try:
                cd.publish(session, d, f.get("own") == "1")
            except HubError as e:
                return FtResponse(preview_page(session, d, str(e)), status_code=409 if f.get("own") == "1" else 422)
            return RedirectResponse(f"{PATH}/{token}?live=1", status_code=303)
        try:
            cd.apply(me.id, d, f, do)
        except HubError as e:
            return editor_page(d, error=str(e))
        return RedirectResponse(f"{PATH}/{token}/preview" if do == "preview" else f"{PATH}/{token}", status_code=303)

    @app.get(PATH + "/{token}/preview")
    def preview(session, token: str):
        me = ses.current_traveler(session)
        if not me:
            return _signin(f"{PATH}/{token}")
        d = cd.get(me.id, token)
        return preview_page(session, d) if d else _gone()

    @app.get(PATH + "/{token}/photo/{filename}")
    def photo(session, token: str, filename: str):
        me = ses.current_traveler(session)
        path = cd.private_file(me.id, token, filename) if me else None
        if path is None:
            return Response("Not found.", status_code=404)
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
