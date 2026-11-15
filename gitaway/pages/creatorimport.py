"""A creator pastes a link or text and gets a draft trip they review and publish (F-183). The rules are gitaway/creatordraft.py (and importsource, safefetch, ai); these are the screens.

GET  /creators/import                     the paste page: a link and/or text; "Draft my trip" (the model), "Write it myself" (an empty draft)
POST /creators/import                     read the post, draft it, go to the editor (or say plainly why not)
GET  /creators/import/<id>                the details editor in the book's v2 look (gitaway/pages/creatoredit.py, F-259): title, name, place, cover pictures, days with stops (move, remove), tips, the source card
POST /creators/import/<id>                do=save, do=preview (save, then the preview), do=book (save, then the book), add_stop:<d>, del_stop:<d>:<s>, up_stop|down_stop:<d>:<s>, add_day, del_day:<d>; do=publish (needs the "own" tick); do=unpublish
GET  /creators/import/<id>/preview        the public page exactly as strangers will see it, with "This is my post" and Publish
GET  /creators/import/<id>/photo/<file>   a picked picture for its owner's preview

A draft belongs to the person who made it (anyone else gets a 404) and needs no family trip. The one POST path under /creators/import/ is open to every member in gitaway.access (it changes no family plan);
its parameter is called `token` because tests/test_roles.py matches the open prefixes that way.
"""

import json
import logging
import re
from urllib.parse import quote, urlsplit

from fasthtml.common import A, Button, Div, Form, H1, I, Input, Label, Link, P, Script, Section, Span, Textarea
from fasthtml.core import FtResponse
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse

from gitaway import ai, community, creatorbook, creatordraft as cd, importsource, session as ses
from gitaway.hub import HubError
from gitaway.icons import icon
from gitaway.itinerary_view import HEAD as VIEW_HEAD, itinerary_body
from gitaway.layout import page
from gitaway.pages import creatordrafts, studio
from gitaway.pages.creatoredit import editor_page      # noqa: F401  (the claim page draws it too)

PATH = "/creators/import"
HEAD = (Link(rel="stylesheet", href="/assets/css/scrapbook.css"), Link(rel="stylesheet", href="/assets/css/creatorimport.css"), Script(src="/assets/js/creatorimport.js", defer=True))
STOP_MAX = cd.MAX_STOP
NOTHING = "Paste the link to your post, or the text of it."
UNEXPECTED = "Something went wrong while making your trip. Try again, or paste the text of your post."
log = logging.getLogger("gitaway.creatorimport")
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
        action=PATH, method="post", id="ci-form", cls="ci-form")
    body = Div(Section(Div(Span(I(), "For travel creators", cls="kicker"), H1("Turn your post into a trip", cls="disp ci-h"),
                            P("Paste a link or your text. GitAway drafts the days, you fix what is off, and nothing is public until you tick \"This is my post\" and publish.", cls="ci-lede"), note, cls="ci-top"),
                       form, creatordrafts.bulk_card() if mode != "manual" else "",
                       P(A("Add your affiliate marker", href="/creators/settings", id="ci-marker"), " so flight bookings from your trips pay you.", cls="ci-hint"), id="landing", cls="ci ga-wrap"),
               studio.stage(), studio.foot(), cls="cv-paste")
    return FtResponse(page("Turn your post into a trip", body, current="/for-creators", head=(*studio.HEAD, Link(rel="stylesheet", href="/assets/css/creatordrafts.css")), v2="cv", quiet=True), status_code=status)


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
                     kind=value.kind, chars=len(value.text), words=importsource.own_words(value.text), robots=value.kind == "blog" and bool(value.url) and cd.mode() == "ai")
    d = value
    heard = iter(creatorbook.said(d.get("words") or [], [s["name"] for day in d["days"] for s in day["stops"]]))      # the post's own sentence that names each stop, "" when it names none
    return _line(event="draft", id=d["id"], title=d["title"], place=d["place_name"] or cd.PLACES.get(d["place"], ""), editor=f"{PATH}/{d['id']}", preview=f"{PATH}/{d['id']}/preview",
                 book=f"{PATH}/{d['id']}/book", days=[{"title": day["title"], "stops": [{"time": s["time"], "name": s["name"], "note": s["note"], "kind": creatorbook.kind_of(s["name"]), "said": next(heard)} for s in day["stops"]]} for day in d["days"]],
                 tips=d["tips"], unsure=cd.UNNAMED)


def _stream(session, link, text, how):
    try:
        for step, value in _steps(session, link, text, how):
            yield _told(step, value)
    except (importsource.SourceError, ai.AIError, HubError) as e:
        yield _line(event="error", message=str(e))
    except Exception as e:  # noqa: BLE001 - the stream must end with a sentence, never silently; the log line names only the kind of failure (no post text, no message)
        log.error("creator import stream failed: %s", type(e).__name__)
        yield _line(event="error", message=UNEXPECTED)


# ---- the editor: gitaway/pages/creatoredit.py (F-259); the public-page preview ----

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


async def _book_act(session, me, d, do, f):
    """What the book's script asks of the draft: fix a word, add the post's picture, publish. JSON {ok, ...} or {ok: false, error: a sentence fit to show}."""
    def no(error, status=422):
        return JSONResponse({"ok": False, "error": error, "editor": f"{PATH}/{d['id']}"}, status_code=status, headers={"Cache-Control": "no-store"})
    try:
        if do == "word":
            _, value = await run_in_threadpool(cd.word, me.id, d, str(f.get("key") or ""), str(f.get("value") or ""))
            return JSONResponse({"ok": True, "value": value}, headers={"Cache-Control": "no-store"})
        if do == "lead":
            await run_in_threadpool(cd.lead, me.id, d)
            return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})
        row = await run_in_threadpool(cd.publish, session, d, f.get("own") == "1")
    except HubError as e:
        return no(str(e), 409 if do == "publish" and f.get("own") == "1" else 422)
    return JSONResponse(await run_in_threadpool(_published, me, d, row), headers={"Cache-Control": "no-store"})


def _published(me, d, row) -> dict:
    """What the book's script shows once a draft is published: its link, the blog badge's code, the stamp, and whether it is listed or waits for the captain (D-189)."""
    from gitaway import blogbutton
    from gitaway.pages import creatorbook
    state = community.review_state(d["slug"])
    return {"ok": True, "slug": d["slug"], "link": f"{blogbutton.base_url()}/trips/{d['slug']}/book", "code": blogbutton.html_snippet(d["slug"], (community.creator_of(me.id) or {}).get("handle", "")),
            "stamp": creatorbook.stamp_of(row["updated_at"]), "listed": state != "pending", "state": state, "host": cd.domain_of(d)}


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
        if request.headers.get("x-book") == "1" and do in ("word", "lead", "publish"):      # the book (F-253): the same rules, answered as JSON for the page's own script
            return await _book_act(session, me, d, do, f)
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
        return RedirectResponse({"preview": f"{PATH}/{token}/preview", "book": f"{PATH}/{token}/book"}.get(do, f"{PATH}/{token}"), status_code=303)

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
