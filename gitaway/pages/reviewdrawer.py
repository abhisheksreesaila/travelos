"""The review drawer (F-282, D-895..D-899; F-290, D-937..D-940): everything long about the guests' reviews, so the square keeps only a compact dashboard. From the top: "Ask the reviews" (a search box
that filters the reviews live as you type, in the page's script only: no AI, no network), a filter chip for each traveller type, the AI's reading (a paragraph per category, what guests like and
watch for; shown while nothing is filtered), then every review LiteAPI gave for the hotel (its last 100), newest first. It is drawn into the hotel's fragment, hidden, and assets/js/hotelfine.js moves it
to the page and opens it from the score, the strip, "Read the reviews" or a complaint ("Read the 6 reviews"), which filters it to the reviews whose cons say that.

    drawer(h, rv)       the hidden side sheet (a full-height sheet on a phone), or "" when LiteAPI gave no review

Reviews are guests' text: escaped, never markup (hotelview._review draws each one). The order is hotelfine.newest_first, the same list a complaint's ids point into.
"""

from collections import Counter

from fasthtml.common import Aside, Button, Div, H2, H3, H4, Input, Label, Li, P, Small, Span, Ul

from gitaway import hotelfine
from gitaway.icons import icon
from gitaway.pages import hotelview

TITLE = "What guests said"


def _chips(items):
    kinds = Counter(r.type for r in items if r.type)
    chip = lambda label, key, on=False: Button(label, type="button", cls="rv-chip", data_rv_type=key, aria_pressed="true" if on else "false")      # noqa: E731
    return Div(chip(f"All {len(items)}", "", True), *[chip(f"{hotelview.TYPES.get(k, k.replace('_', ' ').capitalize())} {n}", k) for k, n in kinds.most_common()], cls="rv-chips", role="group", aria_label="Traveller type")


def _ask():
    return Label(Span(icon("search", 18, 2.2), cls="rv-qi", aria_hidden="true"),
                 Input(type="search", cls="rv-q", placeholder="Ask the reviews: parking, breakfast, noise", aria_label="Ask the reviews", autocomplete="off", autocapitalize="off", spellcheck="false", enterkeyhint="search"),
                 cls="rv-ask"), P(cls="rv-found", role="status", hidden=True)


def summary(rv):
    """What the AI read in the reviews, labelled as such: what guests like and what to watch for (LiteAPI's own lists), then a paragraph for each category."""
    if not rv or not (rv.categories or rv.pros or rv.cons):
        return ""
    cats = Div(*[Div(Div(Span(c.name), Span(hotelview.score_text(c.rating), cls="num"), cls="dr-ch"), P(c.description) if c.description else "", cls="rv-cat") for c in rv.categories], cls="rv-cats") if rv.categories else ""
    lists = Div(Div(H4("Guests like", cls="dr-sub"), Ul(*[Li(icon("check", 15, 2.4), t) for t in rv.pros[:4]], cls="dr-pros")) if rv.pros else "",
                Div(H4("Watch for", cls="dr-sub"), Ul(*[Li(icon("flag", 15, 2.2), t) for t in rv.cons[:4]], cls="dr-cons")) if rv.cons else "", cls="dr-pc")
    return Div(H3("What the reviews say", cls="rv-h"), P(hotelview.AI_NOTE + ".", cls="dr-fine"), lists, cats, cls="rv-ai")


def drawer(h, rv):
    if not rv or not rv.items:
        return ""
    items = hotelfine.newest_first(rv.items)
    word = hotelview.rating_word(h.rating)
    sub = " · ".join(x for x in ((word if word else ""), f"{(rv.total or h.review_count):,} in all" if (rv.total or h.review_count) else "", f"the {len(items)} newest, newest first") if x)
    top = Div(Span(hotelview.score_text(h.rating), cls="rv-n num") if h.rating is not None else "", Div(H2(TITLE, cls="rv-title"), Small(sub)),
              Button(icon("x", 18, 2.4), type="button", cls="rv-x", data_rv_close="1", aria_label="Close the reviews"), cls="rv-top")
    body = Div(*_ask(), _chips(items), Div(Span(cls="rv-why"), Button("Show all", type="button", cls="rv-all", data_rv_type=""), cls="rv-filter", hidden=True),
               summary(rv), Div(*[Div(hotelview._review(r), cls="rv-item", data_i=str(i), data_type=r.type) for i, r in enumerate(items)], cls="rv-list"),
               P(hotelview.source_line(rv), cls="dr-fine tr-src"), cls="rv-body")
    return Aside(top, body, cls="rv", hidden=True, role="dialog", aria_modal="true", aria_label=f"{TITLE}: {h.name}", tabindex="-1")
