"""The fine print, up front, drawn (F-282, D-895..D-899): the section of the opened square's hotel that says what booking sites hide. The facts are gitaway/hotelfine.py's (LiteAPI's own words and
nothing else); this file only draws them and leaves the places the page's script fills from the room, the flight and the pins the person is looking at (assets/js/hotelfine.js):

    section(h, rv, card, sample_note)    the section as an element: costs not in the price, policies that bite, fits your family, getting there and around (the "See it from above" card
                                         `card` lives here, F-284), what guests complain about, and "The usual: ..." line; `sample_note` labels sample data on the showcase

A `data-live` row starts as "not listed" and is rewritten by the script: due (fees paid at the hotel), board, refund (the chosen room's refundability), landing (the flight's landing against
check-in), drive (minutes from the airport). The "what the stay really costs" box (`data-live="real"`) is hidden unless the chosen room has a real amount paid at the hotel.
"""

from fasthtml.common import Button, Div, H3, H4, P, Section, Span

from gitaway import hotelfine
from gitaway.icons import icon

TITLE = "The fine print, up front"
LEDE = "What hotels tuck away, we put first. Anything unusual or extra is marked."
HEADS_UP = "Heads up"
LIVE = {"due": "Paid at the hotel: not listed", "board": "Breakfast: not listed", "refund": "Refundability: not listed", "landing": "Check-in against your flight: not listed",
        "drive": "Drive from the airport: not listed"}


def _row(cls: str, title: str, note: str = "", flag: bool = False, live: str = ""):
    mark = icon("flag", 18, 2.2) if flag else icon("check", 18, 2.4) if "is-ok" in cls else icon("info", 18, 2)
    return Div(Span(mark, cls="fp-m", aria_hidden="true"), Div(Span(title, Span(HEADS_UP, cls="fp-flag") if flag else "", cls="fp-t"), P(note, cls="fp-n") if note else ""),
               cls=f"fp-i {cls}", data_live=live or None)


def _item(i: hotelfine.Item):
    return _row("is-hu" if i.flag else "is-ok" if i.state == "ok" else "is-no" if i.state == "unknown" else "is-plain", i.title, i.note, i.flag)


def _live(key: str):
    return _row("is-no", LIVE[key], live=key)


def _card(cls: str, title: str, *body):
    return Div(H4(title, cls="fp-ct"), Div(*body, cls="fp-list"), cls=f"fp-c {cls}")


def _complaint(c: hotelfine.Complaint):
    open_ = Button(icon("arrow-right", 16, 2.2), f"Read the {c.count} review{'' if c.count == 1 else 's'}", type="button", cls="fp-read", data_rv_open="some", data_rv_ids=",".join(map(str, c.ids)),
                   data_rv_why=c.text) if c.count else Span("No review we fetched says it", cls="fp-none")
    return Div(Span(icon("flag", 18, 2.2), cls="fp-m", aria_hidden="true"), Div(Span(c.text, cls="fp-t"), open_), cls="fp-i is-plain fp-gripe")


def section(h, rv, card="", sample_note=""):
    fp = hotelfine.build(h, rv)
    costs = _card("fp-costs", "Costs not in the price", _live("due"), *[_item(i) for i in fp.costs], _live("board"),
                  Div(Span("What the stay really costs", cls="fp-rk"), Span(cls="fp-rn num", data_real="total"), P(cls="fp-rw", data_real="words"), cls="fp-real", data_live="real", hidden=True))
    policies = _card("fp-policies", "Policies that bite", _live("refund"), *[_item(i) for i in fp.policies[:2]], _live("landing"), *[_item(i) for i in fp.policies[2:]])
    family = _card("fp-family", "Fits your family?", *[_item(i) for i in fp.family])
    going = _card("fp-going", "Getting there and around", _live("drive"), Div(P("Looking around the hotel in OpenStreetMap…", cls="fp-n"), cls="fp-pins", data_pins="1"), card)
    gripes = _card("fp-gripes", "What guests complain about", *([_complaint(c) for c in fp.complaints] or [_row("is-no", "Complaints: not listed", "LiteAPI gave no summary of what guests complain about")]))
    return Section(Div(Span(icon("shield", 22, 2), cls="fp-eye", aria_hidden="true"), Div(H3(TITLE), P(LEDE)), Span(cls="fp-count", data_count="1", role="status"), cls="fp-h"),
                   P(sample_note, cls="fp-sample") if sample_note else "", Div(costs, policies, family, going, gripes, cls="fp-grid"), P(fp.usual, cls="fp-usual") if fp.usual else "",
                   cls="fp", aria_label=TITLE, data_checkin=str(fp.checkin_minutes) if fp.checkin_minutes is not None else "")
