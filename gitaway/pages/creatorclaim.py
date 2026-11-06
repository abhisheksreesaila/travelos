"""Ready-made drafts (F-188): the captain's "Draft for a creator" section of /admin and the creator's claim page. Rules and storage: gitaway/creatorclaim.py.

GET  /claim/<token>        signed out: sign in, then come back. Signed in: the creator's post as a trip, "This is my post: publish it" and "Edit first"; "already claimed" for a used link
POST /claim/<token>        do=publish (claim, then publish: the tap is the "this is my post" tick) or do=edit (claim, then the F-183 editor)
POST /admin/draft          the captain drafts one post (`link`, `name`) or the ticked rows of docs/research/creators.csv (`url`, at most MAX_BATCH at a time) and sees each message to copy
POST /admin/link           a fresh claim link and message for a draft (links are stored hashed, so an old one cannot be shown again); the old link stops working
POST /admin/revoke         the link stops working

Every /admin route answers 404 unless the sign-in is in GITAWAY_ADMIN_EMAILS and verified (admin.is_admin). A claim link is shown only in the response to the captain's POST, never in an address.
Drafting fetches pages and calls the model, so it runs in run_in_threadpool (F-182).
"""

from urllib.parse import quote

from fasthtml.common import A, Button, Details, Div, Form, H1, H2, Input, Label, Li, Link, Main, P, Script, Section, Span, Summary, Textarea, Ul
from fasthtml.core import FtResponse
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from gitaway import affiliate, ai, creatorclaim as cc, creatordraft as cd, importsource, reports, session as ses, showcase
from gitaway.hub import HubError
from gitaway.icons import icon
from gitaway.itinerary_view import HEAD as VIEW_HEAD, itinerary_body
from gitaway.layout import page
from gitaway.pages import creatorimport

MAX_BATCH = 5
GOAL = 150
HEAD = (Link(rel="stylesheet", href="/assets/css/creatorclaim.css"), Script(src="/assets/js/blogbutton.js", defer=True))
NO_STORE = {"Cache-Control": "private, no-store"}
DEMO = (("https://demo.example.com/three-days-in-san-diego", "Maya Chen"), ("https://demo.example.com/maui-with-toddlers", "Leslie Harvey"), ("https://demo.example.com/disneyland-first-timers", "Katie Dillon"))
STATE_WORDS = {"waiting": "Waiting", "claimed": "Claimed", "revoked": "Revoked", "expired": "Expired"}


# ---- the captain's section ----------------------------------------------------------------------------------------------------

def _result(i, r):
    if r.get("error"):
        return Li(Span(r["name"] or r["link"], cls="cc-name"), P(r["error"], role="alert", cls="cc-error"), cls="cc-result is-error", id=f"cc-result-{i}")
    field = f"cc-msg-{i}"
    return Li(Span(r["title"] or r["name"], cls="cc-name"), Span(f"for {r['name']}" if r["name"] else "", cls="cc-meta"),
              Textarea(r["message"], id=field, readonly=True, rows="11", spellcheck="false", autocomplete="off", aria_label=f"Message for {r['name'] or 'the creator'}", cls="cc-msg"),
              Button(icon("link", 20, 2.4), "Copy the message", type="button", data_copy=field, id=f"{field}-copy", cls="btn btn-primary cc-copy"),
              P("GitAway does not send this. Paste it into an email or a message yourself.", cls="cc-meta"), cls="cc-result", id=f"cc-result-{i}")


def _draft_row(r):
    acts = []
    if r["published"]:
        acts.append(A("View", href=f"/trips/{r['slug']}", cls="btn btn-sm"))
    elif r["state"] in ("waiting", "expired", "revoked"):
        hidden = Input(type="hidden", name="draft_id", value=r["draft_id"])
        acts.append(Form(hidden, Button("New link and message", type="submit", cls="btn btn-sm"), action="/admin/link", method="post", cls="ad-inline"))
        if r["state"] == "waiting":
            acts.append(Form(hidden, Button("Revoke link", type="submit", cls="btn btn-sm ad-danger"), action="/admin/revoke", method="post", cls="ad-inline"))
    return Li(Div(Span(r["title"] or r["post_url"], cls="cc-name"), Span(r["name"], cls="cc-meta") if r["name"] else "", Span(f"claimed by {r['email']}", cls="cc-meta cc-by") if r["email"] else "",
                  Span("Published" if r["published"] else STATE_WORDS[r["state"]], cls=f"cc-state is-{'published' if r['published'] else r['state']}")),
              Div(*acts, cls="cc-acts"), cls="cc-draft", id=f"cc-draft-{r['draft_id']}")


def _pick(i, c):
    return Li(Label(Input(type="checkbox", name="url", value=c["example_post_url"].strip(), disabled=c["drafted"] or None, cls="cc-check"),
                    Span(Span(c["person"], cls="cc-name"), Span(c["focus"], cls="cc-meta"), cls="cc-pick-t"),
                    Span("A" if (c.get("priority") or "").strip() == "A" else (c.get("priority") or "").strip(), cls="ad-chip"),
                    Span("Drafted", cls="cc-state is-claimed") if c["drafted"] else "", cls="cc-pick"), cls="cc-row")


def section(results=()):
    """The "Ready-made drafts" part of the admin page. `results` are what the captain's last POST made (each with the message to copy)."""
    if showcase.on() and cd.mode() == "sample" and not cc.listing():
        for url, name in DEMO:       # three claimable drafts to try the flow with, only where the showcase is on and no AI key is set (made-up content, never in production)
            cc.draft("demo", url, name)
    n, rows, people = cc.counts(), cc.listing(), cc.candidates()
    cards = (("Drafts made", n["made"], "cc-made"), ("Claimed", n["claimed"], "cc-claimed"), ("Published", n["published"], "cc-published"))
    mode = cd.mode()
    return Section(
        H2("Draft for a creator"),
        P("GitAway drafts the post privately. Nothing is public until the creator claims it and publishes.", cls="ad-meta"),
        P("No AI key is set, so drafting is switched off here." if mode == "manual" else "No AI key is set, so these are made-up sample drafts." if mode == "sample" else "", cls="ad-meta", id="cc-mode") if mode != "ai" else "",
        Div(*[Div(Span(k, cls="ad-k"), Span(str(v), cls="ad-v", id=i)) for k, v, i in cards], cls="ad-cards cc-cards"),
        Div(Span(cls="ad-bar-fill", style=f"width:{min(100, round(100 * n['published'] / GOAL))}%"), cls="ad-bar", role="img", aria_label=f"{n['published']} of {GOAL} creators published from drafts"),
        P(f"{n['published']} of {GOAL} creators published from drafts.", cls="ad-meta", id="cc-goal"),
        *([Ul(*[_result(i, r) for i, r in enumerate(results)], cls="ad-list cc-results", id="cc-results")] if results else []),
        Form(Label(Span("A post link", cls="cc-lab"), Input(type="text", inputmode="url", name="link", placeholder="https://", autocomplete="off", maxlength=str(importsource.MAX_LINK), id="cc-link", cls="cc-input"), fr="cc-link"),
             Label(Span("The creator's name (shown on the trip)", cls="cc-lab"), Input(type="text", name="name", maxlength=str(cd.MAX_NAME), autocomplete="off", id="cc-name", cls="cc-input"), fr="cc-name"),
             Button(icon("star", 20, 2.4), "Draft it privately", type="submit", cls="btn btn-primary", id="cc-go"), action="/admin/draft", method="post", cls="cc-form card", id="cc-one"),
        Details(Summary(f"From the list of creators ({len(people)})"),
                Form(P(f"Tick up to {MAX_BATCH} and draft them together. A priority first.", cls="cc-meta"), Ul(*[_pick(i, c) for i, c in enumerate(people)], cls="cc-picks"),
                     Button(icon("star", 20, 2.4), "Draft the ticked ones", type="submit", cls="btn btn-primary", id="cc-go-many"), action="/admin/draft", method="post", cls="cc-form card", id="cc-many"),
                cls="cc-list", id="cc-csv") if people else "",
        H2("Drafts and claim links"),
        Ul(*[_draft_row(r) for r in rows], cls="ad-list cc-drafts", id="cc-drafts") if rows else P("No drafts yet.", cls="ad-meta", id="cc-none"),
        cls="ad-sec cc", id="cc-section")


def _made(captain, link, name, d, claim_link):
    return {"link": link, "name": name, "title": d["title"], "message": cc.outreach(name, d["title"], claim_link, captain)}


def _draft_all(admin_id, captain, jobs):
    """The results of drafting each (link, name): a message to copy, or the sentence saying why not. Blocking: runs in the thread pool."""
    out = []
    for link, name in jobs:
        try:
            if (old := cc.drafted(link)):
                out.append({"link": link, "name": name, "error": f"\"{old['title'] or link}\" is already drafted. Use \"New link and message\" below to get its link again."})
                continue
            d, claim_link = cc.draft(admin_id, link, name)
            out.append(_made(captain, link, name, d, claim_link))
        except (importsource.SourceError, ai.AIError, HubError) as e:
            out.append({"link": link, "name": name, "error": str(e)})
    return out


# ---- the claim page -----------------------------------------------------------------------------------------------------------

def _message(title, body, status):
    return FtResponse(page(title, Section(Div(H1(title), P(body), A("Turn your own post into a trip", href="/creators/import", cls="btn btn-primary"), cls="ga-wrap"), cls="ga-soon ga-wrap")), status_code=status, headers=NO_STORE)


def _claim_page(token, d, error=""):
    trip = cd.build(d, lambda n: "", "")
    name = d["name"] or "there"
    domain = cc.domain_of(d)
    bar = Div(
        Div(H1(f"{name}, your post is ready as a trip"), P("GitAway read your post and drafted this. Nothing is public until you publish, and you can take it down any time.", cls="cl-lede"), cls="cl-text"),
        Form(Label(Input(type="checkbox", name="confirm", value="1", required=True, id="cl-confirm", cls="cl-check"), Span("This is my site ", Span(domain, id="cl-domain", cls="cl-domain"), cls="cl-confirm-t"), cls="cl-confirm"),
             P(error, role="alert", cls="cl-error", id="cl-error") if error else "",
             Button(icon("check", 24, 2.8), "This is my post — publish it", type="submit", name="do", value="publish", id="cl-publish", cls="btn btn-primary cl-publish"),
             Button(icon("note", 20, 2.4), "Edit first", type="submit", name="do", value="edit", id="cl-edit", cls="btn cl-editbtn"),
             P(f"Publishing says this is your own post. {affiliate.pays_you()} The trip links back to your post.", cls="cl-hint"), action=f"/claim/{token}", method="post", cls="cl-actions"),
        cls="cl-bar", id="cl-bar", role="region", aria_label="Claim this trip")
    return page(trip.title or "Your trip", bar, itinerary_body(trip), head=(*VIEW_HEAD, *HEAD), theme=trip.theme)


def _gate(token, me):
    """What the person sees when the link cannot be claimed by them: a finished page, or None when it can."""
    s = cc.state(token, me.id)
    if s == "ok":
        return None
    if s == "claimed":
        return _message("Already claimed", "Someone has already claimed this trip with this link, so it cannot be used again. If it is yours, write to the person who sent it.", 410)
    if s in ("revoked", "expired"):
        return _message("This link no longer works", "It has " + ("been withdrawn." if s == "revoked" else "expired.") + " Ask the person who sent it for a new one.", 410)
    return _message("This link does not work", "Check that you copied all of it, or ask the person who sent it for a new one.", 404)


def register(app):
    from gitaway.pages import admin

    @app.get("/claim/{token}")
    def claim_page(session, token: str):
        me = ses.current_traveler(session)
        if not me:
            return RedirectResponse(f"/signin?next={quote(f'/claim/{token}', safe='/')}&intent=publish", status_code=303)
        if cc.state(token, me.id) == "mine":
            return RedirectResponse(f"{creatorimport.PATH}/{cc.draft_id_of(token)}", status_code=303)
        if (gone := _gate(token, me)):
            return gone
        d = cd.get(cc.UNCLAIMED, cc.draft_id_of(token))      # a plain def route: it runs in the thread pool
        return FtResponse(_claim_page(token, d), headers=NO_STORE) if d else _message("This link does not work", "That trip is gone.", 404)

    @app.post("/claim/{token}")
    async def claim(request, session, token: str):
        me = ses.current_traveler(session)
        if not me:
            return RedirectResponse(f"/signin?next={quote(f'/claim/{token}', safe='/')}&intent=publish", status_code=303)
        if not reports.same_site(request):
            return showcase.not_found()
        if (cc.state(token, me.id) != "mine") and (gone := _gate(token, me)):
            return gone
        form = await request.form()
        if cc.state(token, me.id) != "mine" and not form.get("confirm"):      # the claimer says the site is theirs before anything is claimed
            d = await run_in_threadpool(cd.get, cc.UNCLAIMED, cc.draft_id_of(token))
            if not d:
                return _message("This link does not work", "That trip is gone.", 404)
            return FtResponse(_claim_page(token, d, f"Tick the box to say {cc.domain_of(d)} is your site, then press the button."), status_code=422, headers=NO_STORE)
        did = cc.claim(token, me.id, session.get("email") or "")
        if not did:
            return _gate(token, me) or _message("This link does not work", "Ask the person who sent it for a new one.", 410)
        d = await run_in_threadpool(cd.get, me.id, did)
        if str(form.get("do")) == "edit" or not d:
            return RedirectResponse(f"{creatorimport.PATH}/{did}", status_code=303)
        try:
            await run_in_threadpool(cd.publish, session, d, True)      # the tap on "This is my post" is the tick; copies pictures, so never on the loop
        except HubError as e:
            return FtResponse(creatorimport.editor_page(d, error=str(e)), status_code=422, headers=NO_STORE)
        return RedirectResponse(f"{creatorimport.PATH}/{did}?live=1", status_code=303)

    def _captain(session):
        me = ses.current_traveler(session)
        return cc.first_name(me.name) if me and me.name else "the GitAway captain"

    async def _gated(request, session):
        return admin.is_admin(session) and reports.same_site(request)

    @app.post("/admin/draft")
    async def draft(request, session):
        if not await _gated(request, session):
            return showcase.not_found()
        f = await request.form()
        jobs = []
        if str(f.get("link") or "").strip():
            jobs.append((str(f.get("link")).strip(), str(f.get("name") or "")))
        known = {(c["example_post_url"] or "").strip(): c["person"] for c in cc.candidates()}
        jobs += [(u, known[u]) for u in dict.fromkeys(f.getlist("url")) if u in known]      # only an address that is in the list
        results = await run_in_threadpool(_draft_all, str(session["user_id"]), _captain(session), jobs[:MAX_BATCH]) if jobs else [{"link": "", "name": "", "error": "Paste a post link, or tick someone from the list."}]
        return FtResponse(await run_in_threadpool(admin.admin_page, results), headers=NO_STORE)

    @app.post("/admin/link")
    async def link(request, session):
        if not await _gated(request, session):
            return showcase.not_found()
        did = str((await request.form()).get("draft_id") or "")
        row = next((r for r in cc.listing() if r["draft_id"] == did), None)
        new = cc.fresh_link(did) if row else ""
        if not new:
            return RedirectResponse("/admin#cc-section", status_code=303)
        d = await run_in_threadpool(cd.get, cc.UNCLAIMED, did) or {"title": row["title"]}
        shown = [{"link": row["post_url"], "name": row["name"], "title": d["title"], "message": cc.outreach(row["name"], d["title"], new, _captain(session))}]
        return FtResponse(await run_in_threadpool(admin.admin_page, shown), headers=NO_STORE)      # the page reads the community database

    @app.post("/admin/revoke")
    async def revoke(request, session):
        if not await _gated(request, session):
            return showcase.not_found()
        cc.revoke(str((await request.form()).get("draft_id") or ""))
        return RedirectResponse("/admin#cc-section", status_code=303)
