"""Privacy and terms (F-076): GET /privacy and GET /terms, plain summaries, open to everyone signed out.

What they say is checked against the code: docs/family-db.md (what a family stores), docs/photos.md, gitaway/geo.py (place lookup and
routing), gitaway/morning.py (push), gitaway/passkeys.py. Change one of those and read these pages again.
The contact address comes from GITAWAY_CONTACT_EMAIL; without it the pages say to ask the person who invited you and show no address.
"""

import os

from fasthtml.common import A, Div, H1, H2, Li, Link, P, Section, Strong, Ul

from gitaway.layout import page

EFFECTIVE = "October 3, 2026"
HEAD = (Link(rel="stylesheet", href="/assets/css/legal.css"),)
NOT_LAWYER = "These are plain-language summaries written by the people who run GitAway, not legal advice prepared by a lawyer."


def contact():
    """The deletion contact: a link when GITAWAY_CONTACT_EMAIL is set, else the fallback sentence. Never a built-in address."""
    addr = os.getenv("GITAWAY_CONTACT_EMAIL", "").strip()
    if addr:
        return P("Email ", A(addr, href=f"mailto:{addr}", id="legal-contact"), " and say which family you are in.")
    return P("Ask the person who invited you. They run this copy of GitAway and can pass your request on.", id="legal-contact")


def _doc(title, lead, sections):
    body = []
    for heading, *blocks in sections:
        body.append(Section(H2(heading), *blocks, cls="lg-sec"))
    return page(title, Div(
        H1(title), P(f"Effective {EFFECTIVE}", cls="lg-date", id="legal-date"), P(NOT_LAWYER, cls="lg-note"), P(lead, cls="lg-lead"), *body,
        P(A("Terms", href="/terms") if title == "Privacy policy" else A("Privacy policy", href="/privacy"), " · ", A("Back to GitAway", href="/"), cls="lg-more"),
        cls="lg-doc ga-wrap"), head=HEAD)


def privacy():
    return _doc("Privacy policy", "GitAway is a small app for a family to plan trips together. This page says what it keeps, who can see it, and how to get it deleted.", [
        ("What we store",
         P("When you sign in with Google we keep your name, your email address and your profile picture. When you use GitAway we keep what you put in:"),
         Ul(Li("trips, plans, calendar entries and the notes on them;"), Li("messages in the family thread;"),
            Li("photos you add, with the time and place they were taken (we keep the picture and the time and place, and take the location out of the copies we show);"),
            Li("phone numbers you or your family type in, for example your own or a hotel's;"),
            Li("push subscriptions, a code your phone gives us so it can get the morning plan; and"),
            Li("passkeys (Face ID sign-in). We keep only the public half; your fingerprint or face never leaves your phone."))),
        ("Who sees it",
         P("Only the family. Everything above is shared with the people in your family and nobody else, and what each person may change depends on their role. Nothing you add is public, and nothing is shown on a page that can be opened without signing in.")),
        ("Which outside services get what",
         Ul(Li(Strong("Google sign-in"), " tells us who you are (name, email, picture). We send Google nothing about your trips."),
            Li(Strong("Railway"), " hosts the app and the database, so everything above is stored on their servers."),
            Li(Strong("OpenStreetMap"), " looks up places and drives between them. It gets place text only, such as a hotel name or a city. It does not get your name, email or photos."),
            Li(Strong("Apple and Google push services"), " carry the morning plan to your phone. They get the push subscription and the short message, such as the plans for today."),
            Li(Strong("Gemini"), " (Google's AI) is used only if the family assistant is turned on. It is off unless it says otherwise in the app, and then it gets what you ask it and the plan it needs to answer."))),
        ("Selling and ads", P("We do not sell your information. We do not show ads and we do not use anything you add for ads or to build a profile of you.")),
        ("Cookies", P("One cookie keeps you signed in, for up to 30 days. We use no tracking or advertising cookies.")),
        ("Getting your data deleted",
         P("To have your information, or your whole family's, deleted, ask. We will delete it and tell you when it is done."), contact()),
    ])


def terms():
    return _doc("Terms of use", "GitAway is a small family-planning app. By using it you agree to the plain rules below.", [
        ("What GitAway is",
         P("A place for a family to plan a trip together: flights, stays and days on one calendar. It is offered as-is, by a small team, for families who were invited.")),
        ("No bookings or payments",
         P("GitAway does not book anything and does not take payments. The booking screens are a preview with sample prices. Check every flight, stay and time with the airline, hotel or company before you rely on it.")),
        ("What you post",
         P("You are responsible for what you add: notes, messages, photos and phone numbers. Do not add anything unlawful, abusive or that belongs to someone else. We may remove content, or a person, that is abusive.")),
        ("Your family space", P("Keep your sign-in to yourself. The people in your family can see what you add, as the privacy policy says.")),
        ("The service can change",
         P("We may change GitAway or stop it. We will try to give notice and a way to take your plans with you, but we cannot promise it.")),
        ("No warranty",
         P("GitAway comes without any warranty. To the extent the law allows, we are not liable for losses from using it, including a missed flight or lost data. Nothing here limits rights you have under the law that cannot be limited.")),
        ("Law", P("These terms follow the laws of the United States and the state where the operator lives.")),
        ("Questions or deletion", P("For questions, or to have your data deleted:"), contact()),
    ])


def register(app):
    app.get("/privacy")(privacy)
    app.get("/terms")(terms)
