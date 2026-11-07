"""Privacy and terms (F-076): GET /privacy and GET /terms, plain summaries, open to everyone signed out.

What they say is checked against the code: docs/family-db.md (what a family stores), docs/photos.md, gitaway/geo.py (place lookup and
routing), gitaway/around.py (nearby places), gitaway/morning.py (push), gitaway/passkeys.py. Change one of those and read these pages again.
The contact address comes from GITAWAY_CONTACT_EMAIL; without it the pages say "Contact the person who runs this GitAway site." and show no address.
"""

import os

from fasthtml.common import A, Div, H1, H2, Li, Link, P, Section, Strong, Ul

from gitaway.layout import page
from gitaway.planforme import PROMISE

EFFECTIVE = "November 6, 2026"
HEAD = (Link(rel="stylesheet", href="/assets/css/legal.css"),)
NOT_LAWYER = "These are plain-language summaries written by the people who run GitAway, not legal advice prepared by a lawyer."


def contact(then=" and say which family you are in.", id="legal-contact"):
    """The contact: a link when GITAWAY_CONTACT_EMAIL is set, else the fallback sentence. Never a built-in address. `then` finishes the sentence after the address (deletion by default; the takedown section
    says what a notice holds); a page that shows it twice gives each its own `id`."""
    addr = os.getenv("GITAWAY_CONTACT_EMAIL", "").strip()
    if addr:
        return P("Email ", A(addr, href=f"mailto:{addr}", id=id), then)
    return P("Contact the person who runs this GitAway site.", id=id)


def dmca_agent():
    """Who receives copyright notices: the name (and address) in DMCA_AGENT, shown as text; until the agent is registered with the U.S. Copyright Office the page says so (F-196)."""
    agent = " ".join(os.getenv("DMCA_AGENT", "").split())[:300]
    if agent:
        return P("Our designated copyright agent: ", Strong(agent, id="dmca-agent"), ".")
    return P("Our designated copyright agent is pending registration with the U.S. Copyright Office. Until it is registered, send notices to the contact below.", id="dmca-agent")


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
            Li("passkeys (Face ID sign-in). We keep only the public half; your fingerprint or face never leaves your phone;"),
            Li("Plan it for me orders: where you asked to go, the dates, your home airport, how many adults and the ages of any kids (and, if you gave them, their heights, which we delete as soon as your plan is delivered), your budget and pace, what you typed under must-dos, your email address, the amount and Stripe's code for the payment, and the trip we built. Before we send a plan, the person who runs GitAway reads the order and the plan to check it. We do not keep your card number. The family sees the trip, not the order; and"),
            Li("server logs, which can include your email address, for example when a sign-in fails."))),
        ("Who sees it",
         P("Your family sees the trips, plans, notes, messages, photos and phone numbers. Push subscriptions and passkeys are not shown to the family. What each person may change depends on their role."),
         P("The person who runs this site can read the stored data to run and fix it, and to delete it when you ask. Railway hosts it. An invite link shows the family's name and a masked email address to anyone who has the link, so share invite links only with the person they are for.")),
        ("Which outside services get what",
         Ul(Li(Strong("Google sign-in"), " tells us who you are. We send Google nothing about your trips."),
            Li(Strong("Google Fonts"), " loads the type on every page, so Google sees your IP address."),
            Li(Strong("Railway"), " hosts the app and everything it stores."),
            Li(Strong("Nominatim (OpenStreetMap)"), " finds places. It gets place text only, such as a hotel name or a city."),
            Li(Strong("OSRM (router.project-osrm.org)"), " works out drives. It gets pairs of coordinates, not names."),
            Li(Strong("OpenStreetMap Overpass (overpass-api.de)"), " finds places near you when you tap a button on Around you. It gets your approximate location, rounded to within about 100 metres, and the kind of place you tapped (for example pharmacy). Your phone shares where it is only when you tap, and only while that page is open. GitAway does not store your location, and the family does not see it. Results for that rounded point are kept in the server's memory for up to 30 minutes, not linked to you."),
            Li(Strong("OpenStreetMap map tiles"), " (tile.openstreetmap.org) draw the map tab. They see your IP address and the area of the map you look at."),
            Li(Strong("The trip's paper map"), " is drawn once for each area a trip is in, from OpenStreetMap shapes (overpass-api.de, © OpenStreetMap contributors) and elevation tiles (AWS Terrain Tiles at s3.amazonaws.com (elevation-tiles-prod), from USGS and other sources). The server asks them for the corners of the area and the tile numbers it covers, never a place name, a person or a booking. The finished map of an area is kept on the server and reused for every trip in the same area; your trip only points at it."),
            Li(Strong("Open map"), " on the trip's home loads a street map only when you tap it: the map library is this site's own copy, and the map comes from OpenFreeMap (tiles.openfreemap.org), which sees your IP address and the area of the map you look at."),
            Li(Strong("Apple and Google push services"), " carry the morning plan and notices of family messages and plan changes to your phone. The messages are encrypted, so they cannot read them."),
            Li(Strong("Azure OpenAI (Microsoft)"), " does three jobs. When you tap Convert in Add to the trip, it reads the messages you paste and turns them into a plan; it gets only the text you pasted (so anything you wrote in it, such as a first name) and nothing we add. When you use Ask GitAway, it gets what you ask or say plus the plan for that day: the trip title, the date and time zone, the titles of the plans that day, plan notes and booking titles, the parts and steps with who is on each, and the first names of the family. We never add emails, phone numbers, confirmation numbers, prices or photos to what it gets (only what you or your family wrote in those titles and notes goes). We log that a call happened, which feature it was for, how many tokens it used and how long it took, never what was in it. When you use Around you and the assistant is on, it gets the kind of place you tapped, your family's food preference (vegetarian or not), and a list of the names of nearby places with how far they are and whether they are open. It never gets your location or the names of your family. Later assistant features send what you ask in the same way."),
            Li(Strong("Sarvam AI (India)"), " turns your voice into words. When you record your voice in the Ask box (only on a phone whose browser cannot turn speech into text itself or when its own speech recognition fails, and only when you tap the microphone), the recording goes to it to be written out as words, and in English too when you spoke another language such as Hindi. It gets the audio and nothing else; GitAway does not keep the recording or the words once they are in your box, and the log only says that a call happened and how long it took."),
            Li(Strong("Anthropic (Claude Haiku)"), " drafts a trip from a creator's post. When a creator uses Turn your post into a trip, it gets the text of the post, pasted or read from the link the creator gave (a blog's article text, or a video's title, description and chapters), and nothing else: not the creator's name or email address, and nothing from any family's trips. Our server reads the page behind the link; the creator checks and fixes the draft before anything is public. We log that a call happened, how many tokens it used and how long it took, never what was in it."),
            Li(Strong("Stripe"), " takes the payment for Plan it for me. You type your card on Stripe's own page, so GitAway never sees or keeps your card number. Stripe gets your email address (for the receipt) and the amount, and keeps its own record of the payment under its own rules."),
            Li(Strong("Anthropic (Claude Sonnet)"), " builds your trip when you order Plan it for me. It gets where you want to go, your dates, your home airport, how many adults and the ages (and any heights you gave) of any kids, your budget and pace, what you typed under must-dos, and the title of a creator's trip if you started from one. It never gets your name, your email address or anything from your family's other trips. We log that a call happened, how many tokens it used and how long it took, never what was in it."),
            Li(Strong("Travelpayouts, Aviasales and Klook"), " are the partners behind the Book buttons. When you press Book they get a SubID, a short code that tells us which trip, place, day and kind of booking the click came from, with no name, email address or other personal detail. Once you are on their site they see you as any website does, including your IP address."),
            Li(Strong("Travelpayouts Drive"), " is a script from Travelpayouts (tp-em.com) that GitAway loads only on the landing page you see signed out, and only when it has been switched on, never on a page you see signed in. Travelpayouts uses it to confirm this site is ours and can turn travel links on that page into partner links that credit GitAway. It runs in your browser, so Travelpayouts sees your IP address and browser as any website does, and it may set its own cookies; their policy covers them."))),  # a new outside AI service gets a bullet here and a test phrase (F-079 logs every call: docs/ai-usage.md)
        ("How readers of a creator's trip are counted",
         P("A creator can see how many people read their trip. We count a reader with no cookie and keep nothing about you. When you open a published trip we add one to that trip's count for the day. To tell a second visit from a new reader, we make a short code made from your address and browser, mixed with a random value that is thrown away at the end of the day. The random value is gone at the end of the day, so the code cannot be turned back into your address or linked to a later visit; the codes themselves are deleted when the next day's first reader arrives or the server restarts. Your address and the name of your browser are never stored. We count each reader once a day. Known bots, and the creator's own visits, are not counted. The creator sees only totals per trip and per day, and how many people forked a trip or tapped Plan this trip.")),
        ("Selling and ads",P("We do not sell your information. We do not show ads and we do not use anything you add for ads or to build a profile of you.")),
        ("Cookies",
         P("Two cookies. One keeps you signed in, for up to 30 days. The other, ", Strong("ga_via"), ", is a 30-day affiliate attribution cookie: it is set only when you tap Plan this trip on a creator's page, holds the public handle of the creator and nothing about you, and tells us which creator a flight you book supports, so their marker goes on the booking link. It exists to credit the creator, not to build a profile of you. GitAway sets no analytics or advertising cookie."),
         P(Strong("Partner links. "), "When you press Book you go to Aviasales, Klook or another booking partner (through Travelpayouts), and their own sites may set their own tracking cookies to credit GitAway, or the creator, for the booking. Their policies cover those cookies.")),
        ("Getting your data deleted",
         P("Ask and we will delete your account and, if you ask, your family's trips and photos. Messages and photos you added to a family that keeps going stay with that family unless you ask us to remove them. Your Plan it for me orders go too. Stripe keeps its own record of a payment. We do this by hand and will tell you when it is done."), contact()),
    ])


def terms():
    return _doc("Terms of use", "GitAway is a small family-planning app. By using it you agree to the plain rules below.", [
        ("What GitAway is",
         P("A place for a family to plan a trip together: flights, stays and days on one calendar. It is offered as-is, by a small team.")),
        ("Bookings and payments",
         P("GitAway does not book anything. A Book button takes you to a partner's own site, and you book and pay there, under their terms. Check every flight, stay and time with the airline, hotel or company before you rely on it."),
         P("The one thing you can pay GitAway for is Plan it for me: a one-time fee, shown before you pay, taken on Stripe's page, for an agent to build a trip in your family's account."),
         P(PROMISE, " If we cannot build your trip, we refund you in full. The trip is a plan made by an AI agent: it can be wrong, it never states prices or opening hours, and it is your job to check every place, time and booking before you rely on it.")),
        ("What you post",
         P("You are responsible for what you add: notes, messages, photos and phone numbers. Do not add anything unlawful, abusive or that belongs to someone else. We may remove content, or a person, that is abusive.")),
        ("What creators publish",
         P("When you publish a trip as a creator, you keep your rights in it. You give GitAway a worldwide, non-exclusive, royalty-free license to host, copy, reformat and show what you publish (your words, the days and stops you approved, your tips and the pictures you picked) on GitAway, so that people can read it, fork it into their own plans and share its link."),
         P("Unpublish and we delete the page and its picture copies, and the license ends. Plans a family has already put into its own calendar stay in that family's calendar: they are that family's copy."),
         P("You promise that you are the author, or have the right to publish what you add. Ticking \"This is my post\" says so. A draft GitAway makes from your link is only for you to review: nothing is public until you tick the box and publish.")),
        ("Copyright takedown",
         P("If something on GitAway copies your work without permission, press ", Strong("Report this trip"), " on the page and pick \"It uses someone else's words or photos\", or send a notice to our designated agent. A notice should hold: the web address of the copy on GitAway and what the original is (with its address), your name and contact details, a statement that you believe in good faith that the use is not allowed by the owner, its agent or the law, a statement, under penalty of perjury, that what you say is accurate and that you are the owner or may act for the owner, and your signature, typed is fine."),
         P("We take a page down quickly when a notice is valid, and we tell the person who published it."),
         dmca_agent(), contact(" with your notice.", "legal-takedown-contact")),
        ("Counter-notice",
         P("If your page was taken down and you believe that was a mistake, send a counter-notice to the same agent. It should hold: your name, address and phone number, the address of the page before it was taken down, a statement, under penalty of perjury, that you believe in good faith it was removed by mistake or misidentification, your consent to the jurisdiction of the federal court for the district where you live (or, outside the United States, where GitAway can be found), and that you will accept service from the person who sent the notice."),
         P("We pass your counter-notice to that person. If they do not tell us within 10 business days that they have gone to court, we may put the page back.")),
        ("Repeat infringers",
         P("If valid copyright notices on two different pages are about the same person, we remove all of that person's pages and close their account. We do this by hand, and we may do it sooner for one clear case.")),
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
