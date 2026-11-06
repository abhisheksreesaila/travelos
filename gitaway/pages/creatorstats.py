"""A creator's stats (F-192): GET /creators/stats.

The signed-in creator's own numbers, per published trip and in total, for the last 7 days, 30 days or all time (`?w=7|30|all`, plain links): readers, forks, "Plan this trip" taps,
partner clicks from their trips and whose marker was on them. No money. Signed out goes to sign-in; someone who has not published sees how to start. Registered before
/creators/<handle>, which would otherwise take "stats" for a name.
"""

from urllib.parse import quote

from fasthtml.common import A, Div, H1, H2, Li, Link, NotStr, P, Section, Span, Ul
from starlette.responses import RedirectResponse

from gitaway import community, session as ses, stats
from gitaway.icons import icon
from gitaway.layout import page

PATH = "/creators/stats"
HEAD = (Link(rel="stylesheet", href="/assets/css/stats.css"),)
LABELS = {"7": "7 days", "30": "30 days", "all": "All time"}
SAYS = {"7": "the last 7 days", "30": "the last 30 days", "all": "all time"}


def plural(n, one, many=None):
    return f"{n} {one if n == 1 else many or one + 's'}"


def spark(points, label):
    """A tiny line of readers a day: one inline SVG, no chart library. A flat line along the bottom when nobody came."""
    w, h, top = 120, 32, max(points) or 1
    xy = [(round(i * w / (len(points) - 1), 1), round(h - 3 - (h - 6) * v / top, 1)) for i, v in enumerate(points)]
    line = " ".join(f"{x},{y}" for x, y in xy)
    return NotStr(f'<svg class="cs-spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img" aria-label="{label}"><polygon points="0,{h} {line} {w},{h}" class="cs-area"/>'
                  f'<polyline points="{line}" class="cs-line" fill="none" vector-effect="non-scaling-stroke"/></svg>')


def figure(value, label, ident=None):
    return Div(Span(str(value), cls="cs-n", id=ident), Span(label, cls="cs-l"), cls="cs-fig")


def trip_card(t, w):
    n = t[w]
    return Li(Div(A(t["title"], href=f"/trips/{t['slug']}", cls="cs-name"),
                  spark(t["spark"], f"Readers a day, last 30 days: {sum(t['spark'])} in all"), cls="cs-trip-top"),
              Div(figure(n["views"], "readers"), figure(n["forks"], "forks"), figure(n["plans"], "Plan this trip taps"), cls="cs-figs"), cls="cs-trip card", id=f"cs-{t['slug']}")


def stats_page(owner, w="30"):
    w = w if w in stats.WINDOWS else "30"
    creator = community.creator_of(owner)
    r = stats.report(owner)
    if not creator or not r["trips"]:
        return page("Your stats", Section(Div(H1("Your stats"), P("Stats start with your first published trip. Turn a post into a trip, publish it, and the readers, forks and taps show up here.", cls="cs-lede"),
                                              A(icon("note", 20, 2.2), "Turn a post into a trip", href="/creators/import", cls="btn btn-primary"), cls="cs-top"),
                                          cls="cs ga-wrap", id="cs-empty"), head=HEAD)
    t, c = r["total"][w], r["clicks"]
    own, all_ = c[f"own_{w}"], c[w]
    chips = Div(*[A(LABELS[k], href=f"{PATH}?w={k}", aria_current="true" if k == w else None, cls="cs-chip") for k in stats.WINDOWS], cls="cs-chips", role="group", aria_label="Time range")
    if not all_:
        marker = "No one has tapped a Book button from your trips in this time."
    else:
        marker = f"{plural(all_, 'partner click')} from your trips: {own} with your marker (flights), {all_ - own} through GitAway's (stays and things to do)."
    return page("Your stats", Section(
        Div(H1("Your stats"), P(f"How your trips did in {SAYS[w]}. Readers are counted once a day each, with no cookie and nothing kept about them.", cls="cs-lede"), cls="cs-top"), chips,
        Div(figure(t["views"], "readers", "cs-readers"), figure(t["forks"], "forks", "cs-forks"), figure(t["plans"], "Plan this trip taps", "cs-taps"), figure(all_, "partner clicks", "cs-clicks"), cls="cs-total card", id="cs-total"),
        P(marker, cls="cs-says", id="cs-marker"),
        Section(H2("Your trips"), Ul(*[trip_card(x, w) for x in r["trips"]], cls="cs-list"), P("Partner clicks are counted for you, not per trip: the link a family follows remembers whose trip it came from, not which one.", cls="cs-note"), cls="cs-trips"),
        P(A("Your creator page", href=f"/creators/{creator['handle']}"), " · ", A("Marker and links", href="/creators/settings"), " · ", A("How readers are counted", href="/privacy"), cls="cs-more"),
        cls="cs ga-wrap"), head=HEAD)


def register(app):
    @app.get(PATH)
    def creator_stats(session, w: str = "30"):
        me = ses.current_traveler(session)
        if not me:
            return RedirectResponse(f"/signin?next={quote(PATH, safe='/')}&intent=publish", status_code=303)
        return stats_page(me.id, w)
