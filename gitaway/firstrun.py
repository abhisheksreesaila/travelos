"""The first-run welcome (F-053): what a family with no trips yet sees instead of an empty page.

One component, three ways in, in the GitAway voice: plan a trip, import one you booked, browse community trips. Every page that has
nothing to show a brand-new family (the start page, the calendar, the forks page, the trip details) draws it, so none of them is a dead end.
`is_new(session)` says whether the signed-in family has no trip yet.
"""

from fasthtml.common import A, Div, H2, P, Section, Span

from gitaway import session as ses
from gitaway.icons import icon

PLAN = "/start"
IMPORT = "/trips/import"
BUILD = "/trips/build"
COMMUNITY = "/community"


def is_new(session) -> bool:
    """True for a signed-in person whose family has no trip yet (booked, imported or in progress)."""
    return bool(ses.current_traveler(session)) and not ses.trips(session)


def _path(href, ico, fill, title, text, label):
    return A(Span(icon(ico, 26, 2.2), cls=f"fr-ico fill-{fill}", aria_hidden="true"),
             Span(Span(title, cls="fr-title"), Span(text, cls="fr-text"), cls="fr-body"),
             Span(label, icon("arrow-right", 18, 2.6), cls="fr-go"), href=href, cls="fr-path")


def _import_path():
    """"Import a trip you booked" has two ways in (F-055), so it is a card with two links rather than one link."""
    return Div(Span(icon("ledger", 26, 2.2), cls="fr-ico fill-mint", aria_hidden="true"),
               Span(Span("Import a trip you booked", cls="fr-title"), Span("Already booked elsewhere? Bring it in and it becomes your shared calendar.", cls="fr-text"), cls="fr-body"),
               Div(A("Answer a few questions", icon("arrow-right", 18, 2.6), href=BUILD, cls="fr-go"), A("Paste the template", icon("arrow-right", 18, 2.6), href=IMPORT, cls="fr-go"), cls="fr-choices"),
               cls="fr-path fr-path-multi")


def paths(plan_href=PLAN):
    """The three ways to begin: a plain list of links, so it works without JavaScript."""
    return Div(
        _path(plan_href, "plane", "sun", "Plan a trip", "Pick a place and dates. We line up flights, a stay and a car with one honest total.", "Start planning"),
        _import_path(),
        _path(COMMUNITY, "fork", "bubble", "Browse community trips", "Real trips from travelers and creators. Fork one and make it yours.", "Take a look"),
        cls="fr-paths")


def welcome(title="Welcome to GitAway", lede="Your family has no trips yet, so this is the fun part. Pick a way to begin.", plan_href=PLAN, heading=H2, eyebrow="FIRST TRIP"):
    return Section(Span(eyebrow, cls="eyebrow"), heading(title, cls="fr-h"), P(lede, cls="fr-lede"), paths(plan_href), cls="fr", aria_label="Start your first trip")
