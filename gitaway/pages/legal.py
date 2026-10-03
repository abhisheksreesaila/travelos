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
    return P("Contact the person who runs this GitAway site.", id="legal-contact")


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
         P("When you sign in with Google we keep your email address and your Google account number. The name shown in the app is made from your email address. Google also sends a name and a picture; we do not keep them. When you use GitAway we keep what you put in:"),
         Ul(Li("trips, plans, calendar entries and the notes on them;"), Li("messages in the family thread;"),
            Li("photos you add, with the time and place they were taken (we keep the picture and the time and place, and take the location out of the copies we show);"),
            Li("phone numbers you or your family type in, for example your own or a hotel's;"),
            Li("booking confirmation numbers from trips you import;"),
            Li("email addresses of people you invite;"),
            Li("push subscriptions, a code your phone gives us so it can get notifications;"),
            Li("passkeys (Face ID sign-in). We keep only the public half; your fingerprint or face never leaves your phone; and"),
            Li("server logs, which include your email address when you sign in."))),
        ("Who sees it",
         P("Your family sees the trips, plans, notes, messages, photos and phone numbers. Push subscriptions and passkeys are not shown to the family. What each person may change depends on their role."),
         P("The person who runs this site can read the stored data to run and fix it, and to delete it when you ask. Railway hosts it. An invite link shows the family's name and a masked email address to anyone who has the link, so share invite links only with the person they are for.")),
        ("Which outside services get what",
         Ul(Li(Strong("Google sign-in"), " tells us who you are. We send Google nothing about your trips."),
            Li(Strong("Google Fonts"), " loads the type on every page, so Google sees your IP address."),
            Li(Strong("Railway"), " hosts the app and everything it stores."),
            Li(Strong("Nominatim (OpenStreetMap)"), " finds places. It gets place text only, such as a hotel name or a city."),
            Li(Strong("OSRM (router.project-osrm.org)"), " works out drives. It gets pairs of coordinates, not names."),
            Li(Strong("OpenStreetMap map tiles"), " (tile.openstreetmap.org) draw the map tab. They see your IP address and the area of the map you look at."),
            Li(Strong("Apple and Google push services"), " carry the morning plan and notices of family messages and plan changes to your phone. The messages are encrypted, so they cannot read them."))),  # F-072: when the assistant ships, add a Gemini bullet here (Google's AI; gets what you ask and the plan it needs) and a test phrase.
        ("Selling and ads", P("We do not sell your information. We do not show ads and we do not use anything you add for ads or to build a profile of you.")),
        ("Cookies", P("One cookie keeps you signed in, for up to 30 days. We use no tracking or advertising cookies.")),
        ("Getting your data deleted",
         P("Ask and we will delete your account and, if you ask, your family's trips and photos. Messages and photos you added to a family that keeps going stay with that family unless you ask us to remove them. We do this by hand and will tell you when it is done."), contact()),
    ])


def terms():
    return _doc("Terms of use", "GitAway is a small family-planning app. By using it you agree to the plain rules below.", [
        ("What GitAway is",
         P("A place for a family to plan a trip together: flights, stays and days on one calendar. It is offered as-is, by a small team, for families who were invited.")),
        ("No bookings or payments",
         P("GitAway does not book anything and does not take payments. The booking screens are a preview with sample prices. Check every flight, stay and time with the airline, hotel or company before you rely on it.")),
        ("What you post",
         P("You are responsible for what you add: notes, messages, photos and phone numbers. Do not add anything unlawful, abusive or that belongs to someone else. We may remove content, or a person, that is abusive.")),
        ("Who can use it", P("Anyone with a Google account can sign in and gets their own family. Families invite others to join."),),
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
