"""All my posts at once, and the one list of my drafts (F-190). The rules are gitaway/blogscan.py (find the posts) and gitaway/draftjobs.py (draft them in the background); these are the screens.

GET  /creators/drafts          My drafts: every draft I have (drafting, ready, failed, published), each to open or delete; polled every few seconds while any is drafting (`?part=1` is just the list)
GET  /creators/drafts/scan     the address box on its own (the import page has the same one)
POST /creators/drafts/scan     read a blog's sitemap or feed and show its trip-like posts to tick
POST /creators/drafts/start    queue the ticked posts (at most 20, counted against the daily limit) and go to My drafts
POST /creators/drafts/<id>     do=delete: delete a draft (and its public page if live), or take a failed post off the list

A draft belongs to the person who made it; admin-made drafts that a creator claims (F-188) are theirs from then on and show here too, because this reads the same drafts table the editor does.
The POST paths are open to every member in gitaway.access (they change no family plan).
"""

from datetime import date
from urllib.parse import quote, urlsplit

from fasthtml.common import A, Button, Details, Div, Form, H1, Input, Label, Li, Link, P, Script, Section, Span, Summary, Ul, to_xml
from fasthtml.core import FtResponse
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse, RedirectResponse

from gitaway import blogscan, creatordraft as cd, draftjobs as dj, importsource, session as ses
from gitaway.icons import icon
from gitaway.layout import page

PATH = "/creators/drafts"
IMPORT = "/creators/import"
HEAD = (Link(rel="stylesheet", href="/assets/css/scrapbook.css"), Link(rel="stylesheet", href="/assets/css/creatorimport.css"), Link(rel="stylesheet", href="/assets/css/creatordrafts.css"), Script(src="/assets/js/creatordrafts.js", defer=True))
LABEL = {"drafting": "Drafting", "ready": "Ready to check", "failed": "Could not draft", "published": "Published"}
ICON = {"drafting": "rotate", "ready": "check", "failed": "x", "published": "check"}


def _signin(path):
    return RedirectResponse(f"/signin?next={quote(path, safe='/')}&intent=publish", status_code=303)


def _when(iso) -> str:
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return ""
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def left_line(n) -> str:
    cap = min(n, dj.MAX_BATCH)
    return f"You can have {n} more post{'s' if n != 1 else ''} drafted today" + (f", up to {cap} at a time." if n else ". Come back tomorrow, or write one yourself.")


# ---- the address box (here and on the import page) ----------------------------------------------------------------------------

def scan_form(site="", error="", cls="card"):
    return Form(
        Label(Span("Your blog's address", cls="ci-lab"), Span("We read its sitemap or feed and list the posts that look like trips. Nothing is drafted until you tick them.", cls="ci-hint"), fr="cdr-site"),
        Input(type="text", inputmode="url", id="cdr-site", name="site", value=site, placeholder="https://yourblog.com", autocomplete="off", maxlength=str(importsource.MAX_LINK), cls="ci-input", aria_describedby="cdr-err" if error else None),
        P(error, role="alert", cls="ci-error", id="cdr-err") if error else "",
        Div(Button(icon("map", 20, 2.4), "Find my posts", type="submit", cls="btn btn-primary", id="cdr-find"), cls="ci-actions"),
        action=f"{PATH}/scan", method="post", id="cdr-scan", cls=f"ci-form {cls}")


def bulk_card():
    """The "Import several posts" block on the import page."""
    return Section(Span("Import several posts", cls="ci-kicker"), P("Have a blog full of trips? Paste its address and tick the posts you want drafted.", cls="ci-hint"),
                   scan_form(cls="cdr-inline"), A(icon("note", 18, 2.4), "My drafts", href=PATH, cls="btn", id="cdr-mine"), cls="cdr-bulk card", id="cdr-bulk")


# ---- picking ------------------------------------------------------------------------------------------------------------------

def _post(i, p):
    return Li(Label(Input(type="checkbox", name="url", value=p.url, cls="cdr-box"), Span(Span(p.title, cls="cdr-t"), Span(_when(p.date), cls="cdr-d") if p.date else "", Span(urlsplit(p.url).path or "/", cls="cdr-u"), cls="cdr-txt"),
                          cls="cdr-pick"))


def scan_page(session, site="", posts=None, error="", status=200):
    me = ses.current_traveler(session)
    if posts is None:
        body = Section(Div(H1("Import several posts"), P("Paste your blog's address. GitAway lists the posts that look like trips and drafts the ones you tick, in the background.", cls="ci-lede"),
                           cls="ci-top"), scan_form(site, error), A("My drafts", href=PATH, cls="btn", id="cdr-mine"), cls="ci ga-wrap")
        return FtResponse(page("Import several posts", body, current="/creators", head=HEAD), status_code=status)
    n = dj.remaining(me.id)
    cap = min(n, dj.MAX_BATCH)
    form = Form(
        Input(type="hidden", name="site", value=site),
        Ul(*[_post(i, p) for i, p in enumerate(posts)], cls="cdr-posts", id="cdr-posts"),
        P(error, role="alert", cls="ci-error", id="cdr-err") if error else "",
        Div(Button(icon("star", 20, 2.4), "Draft the ticked posts", type="submit", cls="btn btn-primary", id="cdr-go", disabled=True if not cap else None),
            Span("0 ticked", id="cdr-count", cls="ci-hint", role="status", aria_live="polite"), cls="ci-actions cdr-bar"),
        action=f"{PATH}/start", method="post", id="cdr-pick", data_max=str(cap), cls="cdr-form card")
    body = Section(Div(H1("Pick your posts"), P(f"Found {len(posts)} post{'s' if len(posts) != 1 else ''} on {urlsplit(site if '//' in site else '//' + site).hostname}, trip-like ones first. Tick the ones to draft.", cls="ci-lede"),
                       P(left_line(n), cls="ci-note", id="cdr-left", role="status"), cls="ci-top"), form, A("Use another address", href=f"{PATH}/scan", cls="btn"), cls="ci ga-wrap")
    return FtResponse(page("Pick your posts", body, current="/creators", head=HEAD), status_code=status)


# ---- the list ---------------------------------------------------------------------------------------------------------------------

def _row(r):
    chip = Span(icon(ICON[r["status"]], 16, 2.6), LABEL[r["status"]] if r["status"] != "drafting" else ("Drafting now" if r["now"] else "Waiting"), cls=f"cdr-chip cdr-{r['status']}")
    title = A(r["title"], href=f"{IMPORT}/{r['id']}", cls="cdr-name") if r["kind"] == "draft" else Span(r["title"], cls="cdr-name")
    detail = P(r["error"], cls="cdr-err", role="note") if r["error"] else P(urlsplit(r["url"]).netloc, cls="cdr-host") if r["url"] else ""
    if r["status"] == "drafting":
        acts = ""
    elif r["status"] == "failed":
        acts = Form(Input(type="hidden", name="do", value="delete"), Button(icon("x", 18, 2.4), "Remove", type="submit", cls="btn", aria_label=f"Remove {r['title']} from the list"), action=f"{PATH}/{r['id']}", method="post", cls="cdr-rm")
    else:
        acts = Div(A("Open", href=f"{IMPORT}/{r['id']}", cls="btn btn-sm", aria_label=f"Open {r['title']} in the editor"),
                   A("View page", href=f"/trips/{r['slug']}", cls="btn btn-sm") if r["status"] == "published" else "",
                   Details(Summary(icon("x", 18, 2.4), Span("Delete"), cls="pb-unpub", aria_label=f"Delete {r['title']}"),
                           Form(P("This deletes the draft, its pictures and, if it is live, the public page. It cannot be undone."), Input(type="hidden", name="do", value="delete"),
                                Button("Yes, delete it", type="submit", cls="btn btn-sm pb-unpub-yes"), action=f"{PATH}/{r['id']}", method="post", cls="pb-unpub-form"), cls="pb-confirm cdr-del"), cls="cdr-acts")
    return Li(Div(title, chip, cls="cdr-top"), detail, acts, cls=f"cdr-item cdr-s-{r['status']}", id=f"cdr-{r['id']}")


def drafts_list(owner):
    rows = dj.listing(owner)
    busy = sum(1 for r in rows if r["status"] == "drafting")
    if not rows:
        return Div(P("No drafts yet. Draft one post from its link, or several from your blog.", cls="ci-hint"), Div(A("Draft one post", href=IMPORT, cls="btn btn-primary"), A("Import several posts", href=f"{PATH}/scan", cls="btn"), cls="ci-actions"),
                   cls="cdr-empty card", id="cdr-list", data_busy="0")
    note = P(icon("rotate", 18, 2.4), f"{busy} still to draft, one at a time. You can leave this page: they will be here when you come back.", role="status", cls="ci-note cdr-busy", id="cdr-busy") if busy else ""
    return Div(note, Ul(*[_row(r) for r in rows], cls="cdr-rows"), id="cdr-list", data_busy="1" if busy else "0", cls="cdr-list")


def drafts_page(session, queued=0, hit=""):
    me = ses.current_traveler(session)
    left = dj.remaining(me.id)
    notes = []
    if queued:
        notes.append(P(f"Drafting {queued} post{'s' if queued != 1 else ''} in the background.", cls="ci-note", role="status", id="cdr-queued"))
    if hit:
        notes.append(P(cd.SITE_LIMIT_HIT if hit == "site" else cd.LIMIT_HIT, cls="ci-error", role="alert", id="cdr-hit"))
    body = Section(Div(H1("My drafts"), P("Every post you have drafted from a link or text. Open one to check it; nothing is public until you tick \"This is my post\" and publish.", cls="ci-lede"), *notes, cls="ci-top"),
                   drafts_list(me.id), Div(A(icon("plus", 18, 2.4), "Draft one post", href=IMPORT, cls="btn"), A(icon("map", 18, 2.4), "Import several posts", href=f"{PATH}/scan", cls="btn"), cls="ci-actions"),
                   P(left_line(left), cls="ci-hint", id="cdr-left"), cls="ci cdr ga-wrap")
    return page("My drafts", body, current="/creators", head=HEAD)


def register(app):
    @app.get(PATH)
    def mine(session, queued: int = 0, hit: str = "", part: str = ""):
        me = ses.current_traveler(session)
        if not me:
            return _signin(PATH)
        if part == "1":
            return HTMLResponse(to_xml(drafts_list(me.id)), headers={"Cache-Control": "no-store"})
        return drafts_page(session, queued, hit if hit in ("person", "site") else "")

    @app.get(PATH + "/scan")
    def scan_get(session):
        if not ses.current_traveler(session):
            return _signin(PATH + "/scan")
        return scan_page(session)

    @app.post(PATH + "/scan")
    async def scan(request, session):
        me = ses.current_traveler(session)
        if not me:
            return _signin(PATH + "/scan")
        site = str((await request.form()).get("site") or "").strip()
        if cd.mode() == "manual":
            return scan_page(session, site, error=cd.NOT_ON, status=422)
        try:
            posts = await run_in_threadpool(blogscan.sample if cd.mode() == "sample" else blogscan.discover, site)     # fetches the sitemap and the feed: never on the event loop (F-182)
        except blogscan.ScanError as e:
            return scan_page(session, site, error=str(e), status=422)
        return scan_page(session, site, posts)

    @app.post(PATH + "/start")
    async def start(request, session):
        me = ses.current_traveler(session)
        if not me:
            return _signin(PATH)
        f = await request.form()
        site = str(f.get("site") or "").strip()
        host = urlsplit(site if "//" in site else "//" + site).hostname or ""
        picked = list(dict.fromkeys(str(u).strip() for u in f.getlist("url")))
        picked = [u for u in picked if len(u) <= importsource.MAX_LINK and blogscan.same_site(u, host)][:dj.MAX_BATCH]      # only addresses on the site that was scanned, and at most one batch
        if cd.mode() == "manual":
            return scan_page(session, site, error=cd.NOT_ON, status=422)
        if not picked:
            return scan_page(session, site, error="Tick at least one post, then press Draft. Find your posts again to see the list.", status=422)
        queued, hit = await run_in_threadpool(dj.enqueue, me.id, me.name, [(u, blogscan.title_from_url(u)) for u in picked])
        return RedirectResponse(f"{PATH}?queued={queued}" + (f"&hit={hit}" if hit else ""), status_code=303)

    @app.post(PATH + "/{token}")
    async def act(request, session, token: str):
        me = ses.current_traveler(session)
        if not me:
            return _signin(PATH)
        if str((await request.form()).get("do") or "") == "delete":
            d = await run_in_threadpool(cd.get, me.id, token)
            if d:
                await run_in_threadpool(cd.delete, session, d)
            else:
                await run_in_threadpool(dj.remove, me.id, token)
        return RedirectResponse(PATH, status_code=303)
