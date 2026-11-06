"""The For creators page (F-186): GET /for-creators, the page the captain sends to bloggers.

It sells in ten seconds: the paste box first (it posts to the F-183 import at /creators/import), a live example trip (the most-forked real published trip, or a
drawn example, labelled, while nothing real is published), the three promises, "Free. Terms shown on day one.", the creator terms in plain words, and the questions
bloggers ask. It lives here and not at /creators because /creators is the roster of real creators and answers 404 until someone has published (D-107).

Open to everyone, in both showcase modes, with no sample content in it: every word is about what is built.
"""

from fasthtml.common import A, Button, Details, Div, Form, H1, H2, H3, Img, Label, Li, Link, Ol, P, Script, Section, Span, Summary, Textarea, Ul

from gitaway import community, session as ses
from gitaway.icons import icon
from gitaway.itinerary_view import _icon
from gitaway.layout import page

HEAD = (Link(rel="stylesheet", href="/assets/css/for_creators.css"), Script(src="/assets/js/for_creators.js", defer=True))
IMPORT = "/creators/import"
FREE = "Free. Terms shown on day one."
LEDE = "Paste your blog link, YouTube video or Instagram caption. GitAway drafts the days, you fix what is off, and families can fork your trip into their own plans."

PROMISES = (
    ("spark", "fc-p1", "Under a minute", "Paste your post, glance at the draft, publish. The days, stops and tips are drafted for you; you only fix what is off."),
    ("link", "fc-p2", "Your links keep paying you", "Add your Travelpayouts marker and flight bookings from your trips carry it, so Aviasales pays you. We say on every trip who earns."),
    ("ext", "fc-p3", "It links back to your post", "Every trip opens with a source card that sends readers to your original post, with your name on it."),
)
TERMS = (
    ("What we show", "Your name, the days, stops and tips you approve, up to two photos you pick (copied without where they were taken) and a link to your post. Never anything else."),
    ("Take it down any time", "Unpublish in one tap and the page and its photos go. Anyone can report a trip, and the person who runs GitAway can take a page down."),
    ("Your marker", "Paste your own Travelpayouts marker once. Flights from your trips use it. Stays and things to do (Klook) use GitAway's account for now, and the trip page says so."),
    ("Later, a share for big creators", "When a creator's trips bring a lot of bookings, we want to share what Klook pays us with them. That is a plan, not a promise of an amount."),
)
FAQ = (
    ("Does it work with Instagram?", "Instagram does not let anyone read a post, so paste the caption. We keep your link as the source and the draft comes from your words."),
    ("Can I share a post to GitAway from my phone?", "On Android, install GitAway to your home screen and it shows up in the share sheet: share a YouTube video, an Instagram post or a blog page and the import opens with the link filled in. iPhone does not let web apps receive shares yet, so copy the link, open GitAway and paste it."),
    ("And YouTube?", "We read the title, the description and the chapters. For a better draft, paste the transcript into the box: more of what you said means fewer unnamed stops."),
    ("What about my blog?", "Paste the link. We read the article and offer its pictures (up to two) to pick from, copied without where they were taken."),
    ("What if the draft gets something wrong?", "It happens. A place it is not sure of shows as an unnamed stop, and nothing goes public until you fix it, tick \"This is my post\" and press Publish."),
    ("Will GitAway's copy compete with my post in Google?", "No. We tell Google not to index this copy, so your post keeps its ranking."),
    ("What does it cost?", "Nothing. Drafting, publishing and your page are free, and the terms are on this page before you start."),
    ("How do I get my marker?", "In Travelpayouts, under Profile. It is a number such as 801445. Save it on your creator settings and it goes on the flight links of your trips."),
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


def _paste(signed_in):
    return Form(
        Label("A link to your blog post, YouTube video or Instagram post, or the text itself", fr="fc-text", cls="sr-only"),
        Textarea(id="fc-text", name="text", rows="3", maxlength="100000", placeholder="Paste a link to your post, or the text of it", autocomplete="off", spellcheck="false", cls="fc-input"),
        Div(Button(icon("spark", 20, 2.4), "Draft my trip", type="submit", name="do", value="draft", id="fc-draft", cls="btn btn-primary fc-go"),
            Button("Write it myself", type="submit", name="do", value="manual", id="fc-manual", cls="btn fc-write"), cls="fc-bar"),
        action=IMPORT, method="post", id="fc-paste", cls="fc-paste", data_signed_in="1" if signed_in else "0")


def page_body(signed_in):
    return Div(
        Section(
            Div(Span("For creators", cls="fc-eyebrow"),
                H1("Turn your post into a trip, ", Span("in under a minute.", cls="fc-accent")),
                P(LEDE, cls="fc-lede"),
                _paste(signed_in),
                P(FREE, " You tick \"This is my post\" before anything goes public.", cls="fc-fine", id="fc-free"),
                cls="fc-copy"),
            example(), cls="fc-hero ga-wrap"),
        Section(*[Div(Span(icon(ic, 24, 2.2), cls=f"fc-pi {cls}", aria_hidden="true"), H3(title), P(text), cls="fc-promise") for ic, cls, title, text in PROMISES],
                cls="fc-promises ga-wrap", aria_label="What you get"),
        Section(Div(Span(FREE, cls="fc-eyebrow", id="fc-terms-free"), H2("The terms, in plain words"), cls="fc-sec-head"),
                Ul(*[Li(H3(h), P(t), cls="fc-term") for h, t in TERMS], cls="fc-terms"),
                P("Your post stays yours. We never claim it, and you confirm it is yours before it is public. ", A("Privacy", href="/privacy"), " · ", A("Terms", href="/terms"), cls="fc-fine"),
                id="terms", cls="fc-sec ga-wrap"),
        Section(Div(H2("Questions bloggers ask"), cls="fc-sec-head"),
                Div(*[Details(Summary(q), P(a), cls="fc-q") for q, a in FAQ], cls="fc-faq"), id="faq", cls="fc-sec ga-wrap"),
        Section(Div(H2("Your next trip post is a trip someone can use."), A(icon("spark", 20, 2.4), "Start with your post", href="#fc-text", cls="btn btn-primary", id="fc-again"),
                    A("Your marker", href="/creators/settings", cls="btn", id="fc-marker"), cls="fc-end-in"), cls="fc-end ga-wrap"),
        cls="fc")


def register(app):
    @app.get("/for-creators")
    def for_creators(session):
        return page("For creators", page_body(bool(ses.current_traveler(session))), current="/for-creators", head=HEAD, description=LEDE)
