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

import json
import re
from urllib.parse import quote, urlsplit

from fasthtml.common import A, Button, Details, Div, Fieldset, Form, H1, H2, Img, Input, Label, Legend, Li, Link, Ol, Option, P, Script, Section, Select, Span, Summary, Textarea
from fasthtml.core import FtResponse
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, RedirectResponse, Response, StreamingResponse

from gitaway import ai, community, creatordraft as cd, importsource, session as ses, stoplinks
from gitaway.hub import HubError
from gitaway.icons import icon
from gitaway.itinerary_view import HEAD as VIEW_HEAD, _icon, itinerary_body
from gitaway.layout import page
from gitaway.pages import creatordrafts
from gitaway import hub

PATH = "/creators/import"
HEAD = (Link(rel="stylesheet", href="/assets/css/scrapbook.css"), Link(rel="stylesheet", href="/assets/css/creatorimport.css"), Script(src="/assets/js/creatorimport.js", defer=True))
STOP_MAX = cd.MAX_STOP
NOTHING = "Paste the link to your post, or the text of it."
_LONE_LINK = re.compile(r"https?://\S+", re.I)


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
    stage = Section(
        Div(Div(Img(alt="", cls="cm-img", referrerpolicy="no-referrer", hidden=True), Span(icon("play", 36, 2), cls="cm-ph", aria_hidden="true"), cls="cm-photo"),
            Div(Span("", cls="cm-site", id="cm-site"), H2("Opening your post…", id="cm-title", cls="cm-title"), P("", cls="cm-by", id="cm-by"), cls="cm-meta"), cls="cm-post"),
        Ol(*[Li(Span(icon("check", 16, 3), cls="cm-tick", aria_hidden="true"), label, cls="cm-step", data_step=str(i)) for i, label in enumerate(("Opening your post", "Finding the days and stops", "Laying out your trip"))], cls="cm-steps", id="cm-steps"),
        P(Span(cls="cm-caret", aria_hidden="true"), Span("Opening your post", id="cm-log"), cls="cm-log", aria_hidden="true"),
        P(Span("From your post", cls="cm-say-k"), Span("", cls="cm-word", id="cm-word"), cls="cm-say", id="cm-say", aria_hidden="true"),
        Ol(cls="cm-days", id="cm-days"),
        Div(Div(Span(icon("check", 22, 2.6), "Your trip is ready", cls="pb-chip pb-chip-live"), P("", cls="cm-count", id="cm-count"), cls="cm-ready"),
            Form(Label(Input(type="checkbox", name="own", value="1", id="cm-own", required=True, cls="ci-own"), Span("This is my post", cls="ci-own-t"), cls="ci-own-l"),
                 Input(type="hidden", name="do", value="publish"),
                 Button(icon("check", 20, 2.6), "Publish", type="submit", id="cm-publish", cls="btn btn-primary"),
                 A("Preview what strangers see", href=PATH, id="cm-preview", cls="btn"), A("Edit the draft", href=PATH, id="cm-edit", cls="btn"),
                 action=PATH, method="post", id="cm-form", cls="cm-form"),
            P("Nothing is public until you tick the box and publish.", cls="ci-hint"), cls="cm-done", id="cm-done", hidden=True),
        P("", role="status", cls="sr-only", id="cm-live"),
        cls="cm", id="ci-magic", hidden=True, aria_label="Making your trip")
    body = Section(Div(H1("Turn your post into a trip"), P("Paste a link or your text. GitAway drafts the days, you fix what is off, and nothing is public until you tick \"This is my post\" and publish.", cls="ci-lede"), note, cls="ci-top"),
                   form, stage, creatordrafts.bulk_card() if mode != "manual" else "", P(A("Add your affiliate marker", href="/creators/settings", id="ci-marker"), " so flight bookings from your trips pay you.", cls="ci-hint"), cls="ci ga-wrap")
    return FtResponse(page("Turn your post into a trip", body, current="/creators", head=HEAD), status_code=status)


def _steps(session, link, text, how):
    """What a paste becomes, step by step: ("read", material) once the post is read, then ("made", draft). Raises SourceError, ai.AIError or HubError (a sentence fit to show).
    `how` is "draft" or "manual" ("Write it myself": nothing is fetched and no model is asked)."""
    me = ses.current_traveler(session)
    name = me.name if me else ""
    if how == "manual" or cd.mode() == "manual":
        if how != "manual" and not text.strip():
            raise HubError(cd.NOT_ON)
        why = "" if how == "manual" else cd.NOT_ON + " Your text is shown beside the editor to write from."
        material = importsource.offline(link, text)
        yield "read", material
        yield "made", cd.blank(me.id, material, name, why)
        return
    if (hit := cd.allow(me.id)):
        raise HubError(cd.SITE_LIMIT_HIT if hit == "site" else cd.LIMIT_HIT)
    if cd.mode() == "sample":      # the local showcase's simulated draft: nothing is fetched and no model is asked
        material = importsource.offline(link, text)
        yield "read", material
        yield "made", cd.sample(me.id, material, name)
        return
    material = importsource.gather(link, text)
    yield "read", material
    yield "made", cd.make(me.id, me.id, material, name)


def _read(session, link, text, how):
    """The draft a paste becomes, or (None, message)."""
    try:
        made = None
        for step, value in _steps(session, link, text, how):
            made = value if step == "made" else made
        return made, ""
    except (importsource.SourceError, ai.AIError, HubError) as e:
        return None, str(e)


# ---- the magic import (F-235): the same steps, told to the page as they happen ---------------------------------------------------

def _line(**event) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def _told(step, value) -> str:
    if step == "read":
        return _line(event="read", title=value.title, by=value.by, image=(value.images[0] if value.images else value.thumb) or "", site=urlsplit(value.url).hostname or "",
                     kind=value.kind, chars=len(value.text), words=importsource.own_words(value.text))
    d = value
    return _line(event="draft", id=d["id"], title=d["title"], place=d["place_name"] or cd.PLACES.get(d["place"], ""), editor=f"{PATH}/{d['id']}", preview=f"{PATH}/{d['id']}/preview",
                 days=[{"title": day["title"], "stops": [{"time": s["time"], "name": s["name"], "note": s["note"]} for s in day["stops"]]} for day in d["days"]], tips=d["tips"], unsure=cd.UNNAMED)


def _stream(session, link, text, how):
    try:
        for step, value in _steps(session, link, text, how):
            yield _told(step, value)
    except (importsource.SourceError, ai.AIError, HubError) as e:
        yield _line(event="error", message=str(e))


# ---- the editor ---------------------------------------------------------------------------------------------------------

def _pill(name, value, label, on, ico=""):
    return Label(Input(type="checkbox", name=name, value=value, checked=on or None, cls="sr-only"), Span(_icon(ico, 18, 2.2) if ico else "", label, cls="pb-pill"))


def _stop(i, j, s):
    k = f"d{i}s{j}"
    return Div(Input(type="text", name=f"{k}_time", value=s["time"], placeholder="9:00 AM", maxlength="12", autocomplete="off", aria_label=f"Day {i + 1} stop {j + 1} time", cls="pb-input ci-time"),
               Input(type="text", name=f"{k}_name", value=s["name"], placeholder="Where", maxlength=str(STOP_MAX), autocomplete="off", aria_label=f"Day {i + 1} stop {j + 1} name",
                     aria_invalid="true" if s["name"] == cd.UNNAMED else None, cls="pb-input ci-name" + (" ci-unsure" if s["name"] == cd.UNNAMED else "")),
               Input(type="text", name=f"{k}_note", value=s["note"], placeholder="A short note (optional)", maxlength=str(cd.MAX_STOP_NOTE), autocomplete="off", aria_label=f"Day {i + 1} stop {j + 1} note", cls="pb-input ci-snote"),
               Input(type="text", name=f"{k}_link", value=s.get("link", ""), placeholder="A booking or ticket link (optional)", maxlength=str(stoplinks.MAX), autocomplete="off", inputmode="url", aria_label=f"Day {i + 1} stop {j + 1} link", cls="pb-input ci-slink"),
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


def editor_page(d, error="", just=False, captain=False):
    """The editor. `captain`: the captain reviewing a pre-draft nobody has claimed (F-194): it posts to /admin/drafts/<id>, shows no pictures to pick and nothing to preview, publish or delete."""
    base = f"/admin/drafts/{d['id']}" if captain else f"{PATH}/{d['id']}"
    place = Select(*[Option(label, value=k, selected=k == d["place"] or None) for k, label in [*cd.PLACES.items(), ("other", "Somewhere else")]], name="place", id="ci-place", cls="pb-input")
    unsure = sum(1 for day in d["days"] for s in day["stops"] if s["name"] == cd.UNNAMED)
    top = Div(H1("Check this pre-draft" if captain else "Check your draft"), Span(icon("check", 16, 3), "Live", cls="pb-chip pb-chip-live") if d["live"] else Span(icon("note", 16, 2.4), "Draft: nobody can see this yet", cls="pb-chip"),
              P("Nothing is public. Fix what the model got wrong, then send the claim link." if captain else "GitAway read your post. Fix anything that is off: nothing is public until you tick \"This is my post\" and publish.", cls="pb-lede"),
              *[P(n, role="note", cls="ci-note", id=f"ci-notice-{i}") for i, n in enumerate(d["notices"])],
              P(f"{unsure} stop{'s' if unsure != 1 else ''} GitAway was not sure of {'are' if unsure != 1 else 'is'} marked \"{cd.UNNAMED}\". Name {'them' if unsure != 1 else 'it'} or take {'them' if unsure != 1 else 'it'} out.",
                role="note", cls="ci-note ci-unsure-note", id="ci-unsure") if unsure else "", cls="pb-top")
    waiting = d["live"] and community.review_state(d["slug"]) == "pending"      # F-194: published, but in no list until the captain says yes
    done = Div(Span(icon("check", 22, 2.6), "It's live", cls="pb-chip pb-chip-live"),
               P("It is published but unlisted: only people with its link can see it until the captain approves it. Publish again to update it." if waiting else "Anyone can read it and fork it now. Publish again to update it."),
               Div(A(icon("share", 20), "View your trip page", href=f"/trips/{d['slug']}", cls="btn btn-primary", id="pb-view"), *([] if waiting else [A("See it in Community trips", href="/community", cls="btn")]), cls="pb-actions"),
               cls="pb-live card", role="status") if d["live"] and just else ""
    paste = Details(Summary("Your pasted text"), P(d["text"], cls="ci-pasted"), cls="ci-details card", id="ci-pasted") if d.get("text") else ""
    tips = (d["tips"] + [""] * 3)[:max(3, min(len(d["tips"]) + 1, cd.MAX_TIPS))]
    pics = Div(H2("Pictures from your post"), P(f"Optional. Tap up to {cd.MAX_PICKS} to put on your page; they are copied from your own post and stripped of where they were taken. Tap the star for the cover.", cls="pb-hint"),
               Div(*[_tile(d, n, u) for n, u in enumerate(d["images"])], cls="pb-grid"), cls="pb-sec ci-pics", id="ci-pics") if d["images"] else ""
    form = Form(
        Button("Save", type="submit", name="do", value="save", cls="sr-only", tabindex="-1", aria_hidden="true"),     # Enter in a field saves; it never removes a stop
        Div(Label("Title", fr="ci-title", cls="pb-lab"), Input(type="text", id="ci-title", name="title", value=d["title"], maxlength=str(cd.MAX_TITLE), autocomplete="off", cls="pb-input"),
            Label("Their name on it" if captain else "Your name on it", fr="ci-name", cls="pb-lab"), Input(type="text", id="ci-name", name="name", value=d["name"], maxlength=str(cd.MAX_NAME), autocomplete="name", cls="pb-input"),
            Label("Where was it?", fr="ci-place", cls="pb-lab"), place,
            Input(type="text", id="ci-place-name", name="place_name", value=d["place_name"], maxlength=str(cd.MAX_PLACE), placeholder="Name the place", autocomplete="off", aria_label="Name of the place", cls="pb-input"),
            cls="pb-card card"),
        Fieldset(Legend("Who is it good for?"), Div(*[_pill("stickers", k, label, k in d["stickers"], ico) for k, (label, _t, ico) in hub.TAGS.items()], cls="pb-picks"), cls="pb-card card pb-stickers"),
        Div(H2("Days and stops"), P("Times are optional. Add what the post leaves out.", cls="pb-hint"), cls="pb-sec"),
        *[_day(i, day, len(d["days"]) > 1) for i, day in enumerate(d["days"])],
        Button(icon("plus", 18, 2.4), "Add a day", type="submit", name="do", value="add_day", formnovalidate=True, cls="btn ci-add-day", id="ci-add-day") if len(d["days"]) < cd.MAX_DAYS else "",
        Fieldset(Legend("A few tips"), *[Input(type="text", name="tip", value=t, maxlength=str(cd.MAX_TIP), placeholder="One thing you'd tell a friend going", autocomplete="off", aria_label=f"Tip {i + 1}", cls="pb-input")
                                         for i, t in enumerate(tips)], cls="pb-card card pb-tips"),
        "" if captain else pics,
        Div(P(error, role="alert", cls="pb-error", id="pb-error") if error else "",
            *([Button("Save draft", type="submit", name="do", value="save", cls="btn btn-primary", id="pb-save"), A("Back to the admin page", href="/admin#cc-section", cls="btn", id="pb-back-admin")] if captain else
              [Button(icon("image", 20, 2.4), "Preview what strangers see", type="submit", name="do", value="preview", cls="btn btn-primary", id="pb-preview"),
               Button("Save draft", type="submit", name="do", value="save", cls="btn", id="pb-save")]), cls="pb-bar"),
        action=base, method="post", id="ci-edit", cls="pb-form")
    unpub = Details(Summary(icon("x", 18, 2.4), Span("Unpublish"), cls="pb-unpub", id="pb-unpublish"),
                    Form(P("This takes the page off GitAway for everyone. Your draft stays here, so you can publish again; its pictures are deleted and picked again then."), Input(type="hidden", name="do", value="unpublish"),
                         Button("Yes, take it down", type="submit", id="pb-unpublish-yes", cls="btn btn-sm pb-unpub-yes"), action=f"{PATH}/{d['id']}", method="post", cls="pb-unpub-form"), cls="pb-confirm") if d["live"] else ""
    delete = Details(Summary(icon("x", 18, 2.4), Span("Delete this draft"), cls="pb-unpub", id="ci-delete"),
                     Form(P("This deletes the draft, its pictures and, if it is live, the public page. It cannot be undone."), Input(type="hidden", name="do", value="delete"),
                          Button("Yes, delete it", type="submit", id="ci-delete-yes", cls="btn btn-sm pb-unpub-yes"), action=f"{PATH}/{d['id']}", method="post", cls="pb-unpub-form"), cls="pb-confirm")
    return page("Check this pre-draft" if captain else "Check your draft", Section(top, done, _source_card(d), paste, form, *([] if captain else [unpub, delete]), cls="pb ci-edit ga-wrap"), current="/creators", head=HEAD)


def preview_page(session, d, error=""):
    trip = cd.preview(session, d)
    todo = cd.problems(d)
    host = cd.domain_of(d)
    held = {"unverified": f"Its byline shows {host} for now, and your name once the captain has checked that the post is yours.",
            "pending": f"Your email is not at {host}, so this page will be unlisted until the captain approves it: only people with its link can see it."}.get(cd.review_for(session, d, claimed=cd._claimed(d["id"])), "")
    bar = Div(
        Div(Span(icon("image", 18, 2.4), "This is exactly what strangers will see", cls="pb-pv-t"),
            P("Your photos here are private copies; the published ones are the same pictures without where they were taken.", cls="pb-hint"),
            *([P(" ".join(todo), role="alert", cls="pb-error", id="pb-problems")] if todo else []),
            P(held, role="note", cls="pb-hint", id="pb-held") if held else "",
            P(error, role="alert", cls="pb-error", id="pb-error") if error else "", cls="pb-pv-text"),
        Div(Form(Label(Input(type="checkbox", name="own", value="1", id="ci-own", cls="ci-own"), Span("This is my post", cls="ci-own-t"), cls="ci-own-l"),
                 Button(icon("check", 20, 2.6), "Update the public page" if d["live"] else "Publish", type="submit", name="do", value="publish", id="pb-publish", cls="btn btn-primary"),
                 action=f"{PATH}/{d['id']}", method="post", cls="ci-pub"),
            A(icon("chev-left", 18, 2.4), "Back to edit", href=f"{PATH}/{d['id']}", cls="btn", id="pb-back"), cls="pb-pv-act"),
        cls="pb-pv", id="pb-pv", role="region", aria_label="Preview")
    return page(trip.title or "Your trip", bar, itinerary_body(trip), head=(*VIEW_HEAD, *HEAD), theme=trip.theme)


def register(app):
    @app.get(PATH)
    def paste(session, link: str = ""):
        if not ses.current_traveler(session):
            return _signin(PATH)
        try:
            link = importsource.clean_link(link)     # a shared link (F-189), filled in and never fetched until Draft is pressed
        except importsource.SourceError:
            link = ""
        return paste_page(session, link)

    @app.post(PATH)
    async def draft(request, session):
        if not ses.current_traveler(session):
            return _signin(PATH)
        f = await request.form()
        link, text, how = str(f.get("link") or "").strip(), str(f.get("text") or ""), "manual" if f.get("do") == "manual" else "draft"
        if not link and _LONE_LINK.fullmatch(text.strip()):   # the For creators page has one box: a lone address in it is the link (F-186)
            link, text = text.strip(), ""
        told = request.headers.get("x-magic") == "1"      # the page asked to be told as the draft is made (F-235): one line of JSON per step
        if not link and not text.strip() and how == "draft":
            return (StreamingResponse(iter([_line(event="error", message=NOTHING)]), 422, media_type="application/x-ndjson") if told else paste_page(session, "", "", NOTHING, 422))
        if told:
            return StreamingResponse(_stream(session, link, text, how), media_type="application/x-ndjson", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
        made, error = await run_in_threadpool(_read, session, link, text, how)     # fetches the page, asks the model: never on the event loop (F-182)
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
            await run_in_threadpool(cd.unpublish, session, d)
            return RedirectResponse(f"{PATH}/{token}", status_code=303)
        if do == "delete":
            await run_in_threadpool(cd.delete, session, d)
            return RedirectResponse(PATH, status_code=303)
        if do == "publish":
            try:
                await run_in_threadpool(cd.publish, session, d, f.get("own") == "1")
            except HubError as e:
                return FtResponse(preview_page(session, d, str(e)), status_code=409 if f.get("own") == "1" else 422)
            return RedirectResponse(f"{PATH}/{token}?live=1", status_code=303)
        try:
            await run_in_threadpool(cd.apply, me.id, d, f, do)     # may fetch and re-encode the picked pictures
        except HubError as e:
            return editor_page(getattr(e, "draft", None) or d, error=str(e))      # a refused link shows the form as typed, with the sentence (F-196)
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
