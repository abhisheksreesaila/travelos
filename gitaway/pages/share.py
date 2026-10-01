"""Share the trip (F-022).

POST /share        one tap from the calendar: share the booked trip with the default tags, then show the confirmation.
                   The options form below posts here too (custom=1 with the tags and theme chosen).
GET  /share        the options: what is shared, what stays private, tags and colour theme, then Publish.
GET  /share/done   the confirmation, with a link to the new page and the hub.

Signed out goes through sign-in; no booked trip gets a friendly page. Everything is plain forms and links.
"""

from fasthtml.common import A, Button, Div, Form, H1, H2, Img, Input, Label, Link, P, Section, Span
from fasthtml.core import FtResponse
from starlette.responses import RedirectResponse

from gitaway import community, hub, session as ses, share
from gitaway.icons import icon
from gitaway.itinerary_view import _icon
from gitaway.itineraries import PIER
from gitaway.layout import page

HEAD = (Link(rel="stylesheet", href="/assets/css/share.css"),)
THEMES = (("sunset", "Sunset"), ("pacific", "Pacific"))


def _signin(path="/share"):
    return RedirectResponse(f"/signin?next={path}&intent=save", status_code=303)


def sorry(message, status=200):
    return FtResponse(page("Share your trip", Section(
        Div(H1("Share your trip"), P(message), A("Plan a trip", href="/plan", cls="btn btn-primary"), A("Back to the calendar", href="/calendar", cls="btn"),
            cls="sh-sorry"), cls="ga-soon ga-wrap"), head=HEAD), status_code=status)


def preview(session, tags):
    """The little polaroid of what is about to be shared (or just was)."""
    trip = share.build(session, tags)
    plans = sum(len(d.stops) for d in trip.days)
    return Div(Img(src=PIER, alt="Santa Monica Pier and beach"), Span(trip.title, cls="sh-card-title"),
               Span(f"{len(trip.days)} days · {plans} plans · your scrapbook page", cls="sh-card-meta"),
               Span(*[Span(hub.TAGS[k][0], cls=f"tag fill-{hub.TAGS[k][1]}") for k in tags], cls="sh-card-tags") if tags else "",
               cls="sh-card")


def _tag_pick(k, on):
    label, fill, ico = hub.TAGS[k]
    return Label(Input(type="checkbox", name="tag", value=k, checked=on, cls="sr-only"), Span(_icon(ico, 18, 2.2), label, cls=f"sh-pill sh-t-{fill}"))


def _theme_pick(key, label, on):
    return Label(Input(type="radio", name="theme", value=key, checked=on, cls="sr-only"), Span(label, cls=f"sh-pill sh-theme-{key}"))


def options_page(session):
    mine = share.shared(session)
    tags = tuple(mine["tags"]) if mine else share.default_tags(session)
    theme = mine["theme"] if mine else "sunset"
    return page("Share your trip", Section(
        Form(
            preview(session, tags),
            Div(H1("Share your trip with everyone"),
                Div(Div(Span("Shared", cls="sh-k"), Span("Days, plans, times and places, flight and stay names, and your tags", cls="sh-v"), cls="sh-box sh-box-yes"),
                    Div(Span("Stays private", cls="sh-k"), Span("Notes, who's coming, the booking reference and what you paid", cls="sh-v"), cls="sh-box"), cls="sh-boxes"),
                Div(Span("Tags", cls="sh-label"), Div(*[_tag_pick(k, k in tags) for k in hub.TAGS], cls="sh-picks"), cls="sh-group", role="group", aria_label="Tags"),
                Div(Span("Colour theme", cls="sh-label"), Div(*[_theme_pick(k, label, k == theme) for k, label in THEMES], cls="sh-picks"), cls="sh-group", role="group", aria_label="Colour theme"),
                Div(Button("Publish to GitAway", type="submit", cls="btn btn-primary"), A("Not now", href="/calendar", cls="btn"), cls="sh-actions"),
                cls="sh-form"),
            Input(type="hidden", name="custom", value="1"), action="/share", method="post", cls="sh-dialog card"),
        cls="sh ga-wrap"), head=HEAD)


def done_page(session, entry):
    slug, tags = entry["slug"], tuple(entry["tags"])
    return page("Your trip is live", Section(
        Div(preview(session, tags),
            Div(Span(icon("check", 22, 2.6), "Shared", cls="sticker fill-mint sh-sticker"),
                H1("Your trip is live"),
                P("Anyone can fork it now. Your notes, who is coming, the booking reference and what you paid stay private."),
                P("This is a snapshot. Share again to update it.", cls="sh-snapshot"),
                Div(A(icon("share", 20), "View your trip page", href=f"/trips/{slug}", cls="btn btn-primary"),
                    A("See it in the hub", href="/discover", cls="btn"), cls="sh-actions"),
                A("Change tags or theme", href="/share", cls="sh-link"),
                Form(Input(type="hidden", name="slug", value=slug), Button("Unpublish", type="submit", cls="btn btn-sm"), action="/share/unpublish", method="post"),
                cls="sh-form"),
            cls="sh-dialog card sh-done", role="status"), cls="sh ga-wrap"), head=HEAD)


NO_BOOKING = "Book a trip first, then share it. Your calendar is what we turn into the scrapbook page."


def register(app):
    @app.get("/share")
    def options(session):
        if not ses.current_traveler(session):
            return _signin()
        return options_page(session) if ses.booking(session) else sorry(NO_BOOKING)

    @app.post("/share")
    def publish(session, custom: str = "", theme: str = "", tag: list[str] = None):
        if not ses.current_traveler(session):
            return _signin("/calendar")
        if not ses.booking(session):
            return sorry(NO_BOOKING, 409)
        try:
            share.publish(session, tags=(tag or []) if custom else None, theme=theme if custom else None)
        except hub.HubError as e:
            return sorry(str(e), 409)
        return RedirectResponse("/share/done", status_code=303)

    @app.post("/share/unpublish")
    def unpublish(session, slug: str = ""):
        """Take the signed-in owner's shared trip down. Anyone else's slug does nothing (community.unpublish checks the owner)."""
        if not ses.current_traveler(session):
            return _signin("/calendar")
        community.unpublish(session, slug)
        return RedirectResponse("/calendar", status_code=303)

    @app.get("/share/done")
    def done(session):
        entry = share.shared(session)
        return done_page(session, entry) if entry else RedirectResponse("/share", status_code=303)
