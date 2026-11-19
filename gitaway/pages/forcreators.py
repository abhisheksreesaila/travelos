"""Make a guide from your blog post (F-186, F-262): GET /guides/make (it was /for-creators, which redirects to the guide hub), the page the captain sends to bloggers.

It sells in ten seconds: the paste box first (it posts to the F-183 import at /creators/import), a live example trip (the most-forked real published trip, or a
drawn example, labelled, while nothing real is published), the three promises, "Free. Terms shown on day one.", the creator terms in plain words, and the questions
bloggers ask. It lives here (module name kept) and not at /creators because /creators is the roster of real creators and answers 404 until someone has published (D-107).

Open to everyone, in both showcase modes, with no sample content in it: every word is about what is built.
"""

from fasthtml.common import A, Button, Details, Div, Em, Form, I, H1, H2, H3, Img, Label, Li, Link, Ol, P, Section, Span, Summary, Textarea, Ul

from gitaway import community, creatordraft as cd, howpaid, planforme, session as ses
from gitaway.icons import icon
from gitaway.itinerary_view import _icon
from gitaway.layout import page
from gitaway.pages import bookview, studio

IMPORT = "/creators/import"
FREE = "Free. Terms shown on day one."
HEAD_LINE = "Your post deserves more than a scroll."
SUB = "It becomes a trip people plan, book and take, in one place. Your words and your links stay yours."
LEDE = f"{HEAD_LINE} {SUB} Paste it once: a blog link, a YouTube video or an Instagram caption."

PROMISES = (
    ("ext", "fc-p1", "Another place your post travels", "Your postcard has a page and a link of its own, a card for Instagram and a badge for your blog. It opens with your name and a link back to your post."),
    ("spark", "fc-p2", "Readers can plan the trip", "\"Plan this trip\" starts a search at the postcard's place, and \"Add to my plan\" drops your stops into their calendar."),
    ("link", "fc-p3", "The links stay yours", f"Each stop shows your own link, labelled as yours; GitAway adds nothing to its price. {howpaid.LINKS_YOURS}"),
    ("users", "fc-p4", "You can see who reads it", "Your stats page counts readers, plans started and clicks from your postcards, with no cookies and no tracking of who they are."),
)
TERMS = (
    ("What we show", "Your name, the days, stops and tips you approve, up to two photos you pick (copied without where they were taken) and a link to your post. Never anything else."),
    ("Take it down any time", "Unpublish in one tap and the page and its photos go. Anyone can report a trip, and the person who runs GitAway can take a page down."),
    ("How GitAway is paid", howpaid.PAID + " Nothing on a postcard carries a tracking code of ours."),
)
FAQ = (
    ("Does it work with Instagram?", "Instagram does not let anyone read a post, so paste the caption. We keep your link as the source and the draft comes from your words."),
    ("Can I share a post to GitAway from my phone?", "On Android, install GitAway to your home screen and it shows up in the share sheet: share a YouTube video, an Instagram post or a blog page and the import opens with the link filled in. iPhone does not let web apps receive shares yet, so copy the link, open GitAway and paste it."),
    ("And YouTube?", "We read the title, the description and the chapters. For a better draft, paste the transcript into the box: more of what you said means fewer unnamed stops."),
    ("What about my blog?", "Paste the link. We read the article and offer its pictures (up to two) to pick from, copied without where they were taken."),
    ("What if the draft gets something wrong?", "It happens. A place it is not sure of shows as an unnamed stop, and nothing goes public until you fix it, tick \"This is my post\" and press Publish."),
    ("Will GitAway's copy compete with my post in Google?", "No. We tell Google not to index this copy, so your post keeps its ranking."),
    ("What does it cost?", "Nothing. Drafting, publishing and your page are free, and the terms are on this page before you start."),
)
# the drawn example, shown only while nothing real is published: (time, title, icon, tint)
SAMPLE_STOPS = (("9:00", "Venice Beach boardwalk", "sun", "sun"), ("12:30", "Lunch on Abbot Kinney", "food", "bubble"), ("17:30", "Sunset at the pier", "pin", "sky"))


def _stops(items):
    return Ol(*[Li(Span(_icon(kind, 20, 2.1), cls=f"fc-tile fc-b-{tint}", aria_hidden="true"), Span(Span(title, cls="fc-stop-t"), Span(time, cls="fc-stop-m"), cls="fc-stop-x")) for time, title, kind, tint in items],
              cls="fc-stops")


def example():
    """The live example: a real trip's cover, title and first stops, or a drawn stand-in that says it is one."""
    row = community.most_forked()
    if row:
        trip = community.trip_of(row)
        shot = trip.polaroids[0] if trip.polaroids else None
        n = community.fork_count(row["slug"])
        day = trip.days[0] if trip.days else None
        stops = [(s.time, s.title, s.kind, s.bubble) for s in (day.stops[:3] if day else ())]
        return Div(
            A(Img(src=shot.src, alt=shot.alt, loading="lazy", cls="fc-cover") if shot else Span(icon("pin", 44, 2), cls="fc-cover fc-cover-none"), href=f"/trips/{trip.slug}", tabindex="-1", aria_hidden="true"),
            Div(Span("A trip made this way", cls="fc-chip"), Span(f"{n} fork{'s' if n != 1 else ''}", cls="fc-chip fc-chip-n") if n else "",
                H3(A(trip.title, href=f"/trips/{trip.slug}")), P(f"{trip.place} · {len(trip.days)} day{'s' if len(trip.days) != 1 else ''} · by {trip.author}", cls="fc-meta"),
                _stops(stops) if stops else "", A("Open the trip", href=f"/trips/{trip.slug}", cls="btn btn-sm fc-open"), cls="fc-ex-body"),
            cls="fc-ex fc-ex-real", id="fc-example", data_kind="real")
    return Div(
        Div(Span(icon("pin", 40, 2), cls="fc-cover-icon"), Span("Example", cls="fc-chip fc-chip-eg"), cls="fc-cover fc-cover-draw", aria_hidden="true"),
        Div(Span("What a draft looks like", cls="fc-chip"), H3("A family week in Los Angeles"), P("5 days · Los Angeles · by you", cls="fc-meta"), _stops(SAMPLE_STOPS),
            P("An example to show the shape. Your trip is drafted from your own post.", cls="fc-eg"), cls="fc-ex-body"),
        cls="fc-ex fc-ex-draw", id="fc-example", data_kind="drawn")


def off_note():
    """What a creator is told while no AI key is set (production today): the link cannot be read yet, so the paste box takes the text and the captain can draft it from the post (/admin/draft, then a claim link). "" when drafting is on."""
    if cd.mode() != "manual":
        return ""
    mail = planforme.contact_email()
    ask = (" Or send your post to ", A(mail, href=f"mailto:{mail}?subject=My%20post%20as%20a%20guide"), " and we will draft it for you to check and publish.") if mail else ()
    return P("Reading a link is not switched on yet. Paste the text of your post and lay it out yourself.", *ask, role="status", cls="fc-off", id="fc-off")


def _paste(signed_in):
    """The landing's one paste box (the prototype's pill): a link, or the text of the post. Posts to the import; assets/js/creatorimport.js runs it in place."""
    return Form(
        bookview.ico("link"),
        Label("A link to your blog post, YouTube video or Instagram post, or the text itself", fr="fc-text", cls="v2-sr"),
        Textarea(id="fc-text", name="text", rows="1", maxlength="100000", placeholder="Paste the text of your post" if cd.mode() == "manual" else "Paste your blog, YouTube or Instagram link", autocomplete="off", spellcheck="false"),
        Button("Start my postcard" if cd.mode() == "manual" else "Make my postcard", bookview.ico("arrow"), type="submit", name="do", value="draft", id="fc-draft", cls="go"),
        action=IMPORT, method="post", id="fc-paste", cls="paste", data_signed_in="1" if signed_in else "0")


def hero(signed_in):
    return Section(
        Div(Div(Span(I(), "Send a postcard", cls="kicker"), H1("Your post deserves ", Em("more than a scroll."), cls="disp land-h"),
                P(SUB, " Your days, stops and sentences go out as a postcard, with your name on it and your links inside.", cls="land-sub"),
                _paste(signed_in), off_note(), studio.example_chips(link=cd.mode() != "manual"),
                studio.points(Span(Span(icon("check", 17, 2.4), cls="ic", style="--k:var(--bk-tix)"), FREE, " You tick \"This is my post\" before anything goes public.", cls="point v2-glass", id="fc-free")), cls="land-copy"), studio.art(), cls="land"))


def page_body(signed_in):
    return Div(
        Div(hero(signed_in),
            Section(*[Div(Span(_icon(ic, 24, 2.2), cls=f"fc-pi {cls}", aria_hidden="true"), H3(title), P(text), cls="fc-promise") for ic, cls, title, text in PROMISES],
                    cls="fc-promises ga-wrap", aria_label="What you get"),
            Section(example(), cls="fc-sec ga-wrap", aria_label="An example"),
            Section(Div(Span(FREE, cls="fc-eyebrow", id="fc-terms-free"), H2("The terms, in plain words"), cls="fc-sec-head"),
                    Ul(*[Li(H3(h), P(t), cls="fc-term") for h, t in TERMS], cls="fc-terms"),
                    P("Your post stays yours. We never claim it, and you confirm it is yours before it is public. ", A("Privacy", href="/privacy"), " · ", A("Terms", href="/terms"), cls="fc-fine"),
                    id="terms", cls="fc-sec ga-wrap"),
            Section(Div(H2("Questions bloggers ask"), cls="fc-sec-head"), Div(*[Details(Summary(q), P(a), cls="fc-q") for q, a in FAQ], cls="fc-faq"), id="faq", cls="fc-sec ga-wrap"),
            Section(Div(H2("Your next trip post is a trip someone can use."), A(bookview.ico("arrow"), "Start with your post", href="#fc-text", cls="go", id="fc-again"),
                        A("Your blog button", href="/creators/settings", cls="tonal", id="fc-marker"), cls="fc-end-in"), cls="fc-end ga-wrap"), id="landing"),
        studio.stage(), studio.foot(), cls="fc")


def register(app):
    @app.get("/guides/make")
    def make_a_guide(session):
        return page("Send a postcard", page_body(bool(ses.current_traveler(session))), current="/guides", head=(*studio.HEAD, Link(rel="stylesheet", href="/assets/css/guides.css")), description=LEDE, v2="cv")
