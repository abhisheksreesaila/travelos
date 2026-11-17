"""The review drawer (F-282, D-895..D-899): every review LiteAPI gave for the hotel, newest first, with a filter chip for each traveller type among them. It is drawn into the hotel's fragment, hidden,
and assets/js/hotelfine.js moves it to the page and opens it from the score, the last-100 strip or a complaint ("Read the 6 reviews"), which filter it to the reviews whose cons say that.

    drawer(h, rv)       the hidden side sheet (a full-height sheet on a phone), or "" when LiteAPI gave no review

Reviews are guests' text: escaped, never markup (hotelview._review draws each one). The order is hotelfine.newest_first, the same list a complaint's ids point into.
"""

from collections import Counter

from fasthtml.common import Aside, Button, Div, H2, P, Small, Span

from gitaway import hotelfine
from gitaway.icons import icon
from gitaway.pages import hotelview

TITLE = "What guests said"


def _chips(items):
    kinds = Counter(r.type for r in items if r.type)
    chip = lambda label, key, on=False: Button(label, type="button", cls="rv-chip", data_rv_type=key, aria_pressed="true" if on else "false")      # noqa: E731
    return Div(chip(f"All {len(items)}", "", True), *[chip(f"{hotelview.TYPES.get(k, k.replace('_', ' ').capitalize())} {n}", k) for k, n in kinds.most_common()], cls="rv-chips", role="group", aria_label="Traveller type")


def drawer(h, rv):
    if not rv or not rv.items:
        return ""
    items = hotelfine.newest_first(rv.items)
    word = hotelview.rating_word(h.rating)
    sub = " · ".join(x for x in ((word if word else ""), f"{(rv.total or h.review_count):,} in all" if (rv.total or h.review_count) else "", f"the {len(items)} newest, newest first") if x)
    top = Div(Span(hotelview.score_text(h.rating), cls="rv-n num") if h.rating is not None else "", Div(H2(TITLE, cls="rv-title"), Small(sub)),
              Button(icon("x", 18, 2.4), type="button", cls="rv-x", data_rv_close="1", aria_label="Close the reviews"), cls="rv-top")
    body = Div(_chips(items), Div(Span(cls="rv-why"), Button("Show all", type="button", cls="rv-all", data_rv_type=""), cls="rv-filter", hidden=True),
               Div(*[Div(hotelview._review(r), cls="rv-item", data_i=str(i), data_type=r.type) for i, r in enumerate(items)], cls="rv-list"),
               P(hotelview.source_line(rv), cls="dr-fine tr-src"), cls="rv-body")
    return Aside(top, body, cls="rv", hidden=True, role="dialog", aria_modal="true", aria_label=f"{TITLE}: {h.name}", tabindex="-1")
