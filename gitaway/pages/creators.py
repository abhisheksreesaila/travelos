"""Creator link import at /creators (F-023). The creator is also the editor: paste, answer a few questions, edit five spots, confirm, Submit.

GET  /creators          paste a YouTube or Instagram link (about 5 minutes from here to done)
POST /creators          validate the link, start the draft, go to the draft behind a skeleton
GET  /creators/draft    the drafted scrapbook: source card, quick questions, five editable spots, the two confirm boxes
POST /creators/draft    save answers and edits (do=save), or save and publish (do=submit)
GET  /creators/finish   publish after the demo sign-in (a signed-out Submit comes back here)
GET  /creators/done     it is live: links to the trip page and the hub

All the rules (link checks, the fixtures, the five fields, publishing) live in gitaway.creators. This module is the screens.
"""

from urllib.parse import quote

from fasthtml.common import A, Button, Div, Fieldset, Form, H1, H2, Img, Input, Label, Legend, Li, Link, Ol, P, Script, Section, Span, Textarea, Ul
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import creators, hub, session as ses
from gitaway.creators import MAX, SEASONS
from gitaway.icons import icon
from gitaway.itinerary_view import _icon
from gitaway.layout import page
from gitaway.pages.discover import HEAD as HUB_HEAD, card as hub_card

HEAD = (Link(rel="stylesheet", href="/assets/css/creators.css"), Script(src="/assets/js/creators.js", defer=True))
SAMPLES = (("a YouTube sample", "https://www.youtube.com/watch?v=our-la-family-week"), ("an Instagram sample", "https://www.instagram.com/reel/Cxyz123/"))
STEPS = ("Paste", "Check it", "Live")
# Runs as the first thing inside the stage, so the draft can sit behind its skeleton before first paint (no JavaScript: no skeleton, no wait).
BOOT = Script("document.documentElement.classList.add('cr-js');"
              "if(/[?&]new=1/.test(location.search)&&!matchMedia('(prefers-reduced-motion: reduce)').matches)"
              "document.getElementById('cr-stage').setAttribute('data-wait','1');")


def time_text(mins, paste=False):
    if paste:
        return f"Time check: about {mins} minutes in all"
    return f"Time check: about {mins} minute{'s' if mins != 1 else ''} left"


def progress(stage, mins, paste=False, text=""):
    return Div(Ol(*[Li(Span(str(i + 1), cls="cr-step-n"), label, aria_current="step" if i == stage else None) for i, label in enumerate(STEPS)],
                  cls="cr-steps", aria_label="Your progress"),
               Span(text or time_text(mins, paste), id="cr-time", role="status", cls="cr-time"),
               id="cr-progress", cls="cr-progress")


def alert(message):
    return P(message, role="alert", cls="cr-alert", id="cr-alert") if message else ""


# ---------- paste ----------

def paste_page(session, link="", error="", status=200):
    rec = creators.get_rec(session)
    form = Form(
        Label(Span("Video or post link", cls="sr-only"),
              Input(type="text", inputmode="url", name="link", value=link, placeholder="Paste a YouTube or Instagram link", autocomplete="off",
                    maxlength=str(creators.MAX_LINK + 100), aria_describedby="cr-hint", aria_invalid="true" if error else None, id="cr-link", cls="cr-link")),
        Button("Make it a trip", type="submit", cls="btn btn-primary cr-go"), action="/creators", method="post", cls="cr-paste-form")
    steps = Ol(*[Li(Span(str(i + 1), cls="cr-note-n"), Span(t, cls="cr-note-t"), Span(s, cls="cr-note-s"), cls=f"cr-note cr-note-{i + 1}")
                 for i, (t, s) in enumerate((("Paste", "Your video or post link, from the share button."),
                                             ("Check", "Answer a few quick questions and fix five spots."),
                                             ("Submit", "Tick two boxes and it is in the hub.")))], cls="cr-notes")
    body = Section(
        progress(0, 5, paste=True),
        Div(H1("Your vlog, as a trip people can fork"),
            P("Paste a link and we draft the itinerary. You check it, fix what is off and press Submit. Every fork links back to your channel."),
            form,
            alert(error),
            P(Span("No link handy? Try ", cls="cr-sample-lead"), *[x for i, (label, url) in enumerate(SAMPLES) for x in
                                                              ((Span(" or ", cls="cr-sample-lead"),) if i else ()) + (A(label, href=f"/creators?link={quote(url, safe='')}"),)],
              id="cr-hint", cls="cr-hint"),
            P("Demo: nothing is fetched. The draft is a made-up transcript, picked from your link.", cls="cr-fine"),
            A(icon("note", 18, 2.2), "Pick up your draft", href="/creators/draft", cls="btn btn-sm cr-resume") if rec else "",
            cls="cr-paste-copy"),
        steps, cls="cr cr-paste ga-wrap")
    return FtResponse(page("For creators", body, current="/creators", head=HEAD), status_code=status)


# ---------- the draft ----------

def _pill(kind, name, value, label, on, fill="", ico=""):
    return Label(Input(type=kind, name=name, value=value, checked=on, cls="sr-only"),
                 Span(_icon(ico, 18, 2.2) if ico else "", label, cls="cr-pill" + (f" cr-fill-{fill}" if fill else "")))


def _questions(d):
    days = Fieldset(Legend("Which days are in your video?"), Div(*[_pill("checkbox", "days", str(i), f"Day {n} · {x.title}", i in d.kept)
                                                                   for n, (i, x) in enumerate(((i, d.fx.days[i]) for i in range(len(d.fx.days))), start=1)], cls="cr-picks"))
    who = Fieldset(Legend("Who does it suit?"), Div(*[_pill("checkbox", "who", k, label, k in d.who, fill, ico) for k, (label, fill, ico) in hub.TAGS.items()], cls="cr-picks"))
    season = Fieldset(Legend("Best season to go?"), Div(*[_pill("radio", "season", k, label, k == d.season) for k, (_t, _s, label) in SEASONS.items()], cls="cr-picks"))
    return Div(H2("A few quick questions"),
               P("We guessed these from your video. Tap anything that is off; the draft updates.", cls="cr-q-lead"),
               days, who, season,
               Button("Update the draft", type="submit", name="do", value="save", cls="btn btn-sm cr-update"),
               cls="cr-questions card")


def _source(d):
    alt = creators.COVERS["venice" if d.fx.thumb == creators.VENICE else "pier"][1]
    return Div(Div(Img(src=d.fx.thumb, alt=alt), Span(icon("play", 18), cls="cr-play"), cls="cr-thumb"),
               Span(d.fx.video, cls="cr-src-title"),
               Span(f"{d.fx.creator} · {d.platform} · {d.fx.mins} min", cls="cr-src-by"),
               cls="cr-source card")


def _day(n, x, d):
    slot = n - 1
    fields = []
    if slot < len(d.hl):
        fields = [Label("Day highlight", Span(icon("note", 14, 2.2), cls="cr-pen"), fr=f"cr-hl{n}", cls="cr-lab"),
                  Input(type="text", id=f"cr-hl{n}", name=f"hl{n}", value=d.hl[slot], maxlength=str(MAX[f"hl{n}"]), autocomplete="off", cls="cr-hl")]
    if slot >= len(d.hl):
        fields = [Span("Laid out for you from your video", cls="cr-laid")]
    stops = Ul(*[Li(Span(Span(t, cls="cr-stop-t"), Span(f"at {at} in video", cls="cr-stop-at"), cls="cr-stop-row"), Span(title, cls="cr-stop-title"), cls="cr-stop")
                 for t, at, title, _k, _b in x.stops], cls="cr-stops")
    return Div(Span(Span(f"{n:02d}", cls="cr-day-n"), Span(x.title, cls="cr-day-t"), cls="cr-day-head"), *fields, stops,
               cls=f"cr-day tint-{creators._FILL[slot % 3]}", style=f"--i:{n}")


def _cover(d):
    opts = []
    for key, label in creators.COVER_LABELS.items():
        src, alt = creators.COVERS[key]
        face = Img(src=src, alt="") if src else Span(icon("pin", 28, 2), cls="cr-nophoto")
        opts.append(Label(Input(type="radio", name="cover", value=key, checked=key == d.cover, cls="sr-only"),
                          Span(face, Span(label, cls="cr-cap"), cls=f"cr-polaroid cr-pol-{key}"), title=alt or label))
    return Fieldset(Legend("Cover photo"), Div(*opts, cls="cr-covers"), role="radiogroup", cls="cr-cover")


def _book(d, message=""):
    stickers = [Span(_icon(hub.TAGS[k][2], 18, 2.2), hub.TAGS[k][0], cls=f"sticker fill-{hub.TAGS[k][1]}") for k in d.who]
    stickers.append(Span(_icon("clock", 18, 2.2), f"Best in {d.season}", cls="sticker fill-sky"))
    ok1 = Label(Input(type="checkbox", name="ok1", value="1", checked="1" in d.ticks, cls="sr-only"),
                Span(icon("check", 18, 3), cls="cr-box"), Span("This is accurate. I checked the days, stops and times against my video."), cls="cr-ok")
    ok2 = Label(Input(type="checkbox", name="ok2", value="1", checked="2" in d.ticks, cls="sr-only"),
                Span(icon("check", 18, 3), cls="cr-box"), Span("I give GitAway permission to publish it."), cls="cr-ok")
    return Div(
        Div(Label("Name your trip", Span(icon("note", 14, 2.2), cls="cr-pen"), fr="cr-title", cls="cr-lab"),
            Input(type="text", id="cr-title", name="title", value=d.title, maxlength=str(MAX["title"]), autocomplete="off", cls="cr-title"), cls="cr-title-row"),
        Div(*stickers, cls="cr-stickers"),
        Div(*[_day(n, x, d) for n, x in enumerate(d.days, start=1)], cls=f"cr-days cr-days-{len(d.days)}"),
        Div(Div(Label("Your best tip", Span(icon("note", 14, 2.2), cls="cr-pen"), fr="cr-tip", cls="cr-lab"),
                Textarea(d.tip, id="cr-tip", name="tip", rows="3", maxlength=str(MAX["tip"]), cls="cr-tip-input"), Span(cls="cr-tape"), cls="cr-tip"),
            _cover(d), cls="cr-extras"),
        alert(message),
        Div(ok1, ok2, Button(icon("check", 20, 2.6), "Submit to GitAway", type="submit", name="do", value="submit", cls="btn btn-ink cr-submit"), cls="cr-confirm"),
        id="cr-book", cls="cr-book")


def _skeleton():
    return Div(Div(cls="skeleton cr-sk-title"), Div(cls="skeleton cr-sk-tags"),
               Div(*[Div(cls="skeleton cr-sk-day") for _ in range(3)], cls="cr-sk-days"),
               Span("Watching your video and drafting the days…", cls="cr-sk-say"),
               cls="cr-skel", aria_busy="true", role="status", aria_label="Drafting your trip from the video")


def draft_page(session, new=False, message="", status=200):
    rec = creators.get_rec(session)
    if not rec:
        return RedirectResponse("/creators", status_code=303)
    d = creators.resolve(rec)
    stage = Div(BOOT, _skeleton() if new else "", _book(d, message), id="cr-stage", cls="cr-stage", data_new="1" if new else None)
    body = Section(
        Form(Input(type="hidden", name="form", value="1"),
             Div(H1("Check your trip"), progress(1, creators.minutes_left(rec)), cls="cr-top"),
             Div(Div(_source(d), _questions(d), cls="cr-side"), stage, cls="cr-grid"),
             action="/creators/draft", method="post", id="cr-form", cls="cr-form"),
        cls="cr ga-wrap")
    return FtResponse(page("Check your trip", body, current="/creators", head=HEAD), status_code=status)


# ---------- done ----------

def done_page(session, slug):
    t = ses.current_traveler(session)
    c = next((c for c in hub.all_cards(session) if c.slug == slug), None)
    rec = creators.published(session, t.id).get(slug)
    d = creators.resolve(rec)
    body = Section(
        progress(2, 0, text="Done, well inside five minutes"),
        Div(Span(icon("check", 22, 2.6), "Live", cls="sticker fill-mint cr-live-sticker"),
            H1("It's live!"),
            P(f"Your trip is in the community hub. Every fork links back to {d.fx.creator} on {d.platform}."),
            Div(A(icon("share", 20), "See your trip page", href=f"/trips/{slug}", cls="btn btn-primary"),
                A("See it in the hub", href="/discover", cls="btn"), A("Import another", href="/creators", cls="btn"), cls="cr-actions"),
            cls="cr-done-copy"),
        Div(hub_card(c) if c else "", cls="cr-done-card"), cls="cr cr-done ga-wrap", role="status")
    return page("It's live", body, current="/creators", head=(*HUB_HEAD, *HEAD))


def _signin(next_path):
    return RedirectResponse(f"/signin?next={quote(next_path, safe='')}&intent=publish", status_code=303)


def register(app):
    @app.get("/creators")
    def paste_get(session, link: str = ""):
        return paste_page(session, link[:creators.MAX_LINK + 100])

    @app.post("/creators")
    def paste_post(session, link: str = ""):
        try:
            parsed = creators.parse_link(link)
        except creators.LinkError as e:
            return paste_page(session, link[:creators.MAX_LINK + 100], str(e), 422)
        try:
            creators.start(session, parsed.url)
        except hub.HubError as e:
            return paste_page(session, link, str(e), 409)
        return RedirectResponse("/creators/draft?new=1", status_code=303)

    @app.get("/creators/draft")
    def draft_get(session, new: str = ""):
        return draft_page(session, new == "1")

    @app.post("/creators/draft")
    async def draft_post(request, session):
        f = await request.form()
        data = {"form": f.get("form"), "days": f.getlist("days"), "who": f.getlist("who"), "season": f.get("season"),
                "ok1": f.get("ok1"), "ok2": f.get("ok2"), **{k: f.get(k) for k in creators.FIELDS if k in f}}
        try:
            creators.save(session, data)
        except hub.HubError as e:
            return draft_page(session, message=str(e), status=409)
        if f.get("do") != "submit":
            return RedirectResponse("/creators/draft", status_code=303)
        rec = creators.get_rec(session)
        if not rec:
            return RedirectResponse("/creators", status_code=303)
        if rec.get("k") != "12":
            return draft_page(session, message="Tick both boxes first: that it is accurate, and that you give GitAway permission to publish it.", status=422)
        if not ses.current_traveler(session):
            return _signin("/creators/finish")
        try:
            creators.publish(session)
        except hub.HubError as e:
            return draft_page(session, message=str(e), status=409)
        return RedirectResponse("/creators/done", status_code=303)

    @app.get("/creators/finish")
    def finish(session):
        """Where the sign-in lands. Publishing is a POST, so this only shows the button (it presses itself when JavaScript runs)."""
        rec = creators.get_rec(session)
        if not rec:
            return RedirectResponse("/creators", status_code=303)
        if not ses.current_traveler(session):
            return _signin("/creators/finish")
        if rec.get("k") != "12":
            return RedirectResponse("/creators/draft", status_code=303)
        return page("Publish your trip", Section(
            Form(H1("Ready to publish"), P("You are signed in. One tap puts your trip in the community hub."),
                 Div(Button(icon("check", 20, 2.6), "Publish my trip", type="submit", cls="btn btn-ink"), A("Back to the draft", href="/creators/draft", cls="btn"), cls="cr-actions"),
                 action="/creators/finish", method="post", id="cr-finish", data_auto="1", cls="cr-done-copy"), cls="cr ga-wrap"),
            current="/creators", head=HEAD)

    @app.post("/creators/finish")
    def finish_post(session):
        rec = creators.get_rec(session)
        if not rec:
            return RedirectResponse("/creators", status_code=303)
        if not ses.current_traveler(session):
            return _signin("/creators/finish")
        try:
            creators.publish(session)
        except hub.HubError as e:
            return draft_page(session, message=str(e), status=409)
        return RedirectResponse("/creators/done", status_code=303)

    @app.get("/creators/done")
    def done(session):
        t = ses.current_traveler(session)
        mine = creators.published(session, t.id) if t else {}
        slugs = [e["s"] for e in hub.entries(session) if e["s"] in mine]
        return done_page(session, slugs[-1]) if slugs else RedirectResponse("/creators", status_code=303)
