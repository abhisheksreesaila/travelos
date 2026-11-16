"""The matrix v3 (F-275, docs/briefs/matrix-v3.md, D-860..): an obvious sentence with suggestion chips, a nights band that draws no labels across the rows, the side widgets
folded into chips that open into cards, and the opened square leading with the hotel. The hotel's data is the recorded Hilton answer (tests/fixtures/liteapi_hotel)."""
import re
from html import unescape
from urllib.parse import parse_qs, urlsplit

from gitaway import v2sentence
from gitaway.pages import tripmatrix as page
from tests.test_tripmatrix_page import MATRIX, spec

SPEC = lambda html: spec(html)      # noqa: E731


def page_html(client, url=MATRIX):
    r = client.get(url)
    assert r.status_code == 200
    return r.text


# ---- the sentence is obvious --------------------------------------------------------------------------------------------------------------------------------

def test_the_sentence_says_to_tap_a_word_and_every_word_is_a_picker_button(client):
    html = page_html(client)
    assert "Tap any word to change it" in html
    words = re.findall(r'<span role="button" tabindex="0" data-k="(\w+)" aria-haspopup="dialog" aria-expanded="false" aria-label="([^"]+)" class="v2-w">', html)
    assert [k for k, _ in words] == list(v2sentence.WORD_KEYS)
    assert dict(words)["nights"] == "How many nights: 4 nights"


def test_the_sentence_sits_on_its_own_opaque_card_with_the_suggestions_in_it(client):
    html = page_html(client)
    card = html.split('class="v2-qcard"', 1)[1].split('class="mx-results"', 1)[0]
    assert 'class="v2-sent"' in card and 'class="v2-sug"' in card and "Try" in card


# ---- the suggestion chips -----------------------------------------------------------------------------------------------------------------------------------

def _form(spec_):
    return {"to": spec_["to"], "home": spec_["home"], "d": spec_["depart"], "n": spec_["nights"], "a": spec_["adults"], "k": ",".join(map(str, spec_["kids"])),
            "x": spec_["flex"], "nb": "" if spec_["nearby"] else "0", "b": spec_["budget"] or ""}


def test_each_chip_is_the_sentence_with_one_word_changed_and_goes_through_address(client):
    html = page_html(client)
    sp = SPEC(html)
    chips = suggestions = v2sentence.suggestions(sp)
    labels = [c[0] for c in chips]
    assert "A week later" in labels and "From OAK" in labels and "3 nights" in labels and "Under $2,500" in labels
    assert any(label not in ("A week later", "From OAK", "3 nights", "Under $2,500") for label in labels)      # a different place
    by = dict(chips)
    week = parse_qs(urlsplit(by["A week later"]).query)
    assert (week["d"], week["r"]) == (["2026-12-19"], ["2026-12-23"]) and week["to"] == ["San Diego"]
    assert parse_qs(urlsplit(by["From OAK"]).query)["home"] == ["OAK"]
    assert parse_qs(urlsplit(by["3 nights"]).query)["r"] == ["2026-12-15"]
    assert parse_qs(urlsplit(by["Under $2,500"]).query)["b"] == ["2500"]
    assert by["A week later"] == v2sentence.address({**_form(sp), "d": "2026-12-19"})[0]      # the one place words become a search
    assert suggestions and all(href.startswith("/plan/matrix?") for _, href in chips)


def test_the_chips_on_the_page_are_links_with_those_addresses(client):
    html = page_html(client)
    found = re.findall(r'<a href="([^"]+)" class="v2-sug"[^>]*>(?:<svg.*?</svg>)?([^<]+)</a>', html, re.S)
    assert dict((unescape(label).strip(), unescape(href)) for href, label in found) == dict(v2sentence.suggestions(SPEC(html)))


def test_a_budget_already_said_offers_any_budget_and_no_chip_is_the_current_sentence(client):
    html = page_html(client, MATRIX + "&b=2000")
    chips = dict(v2sentence.suggestions(SPEC(html)))
    assert "Any budget" in chips and not [k for k in chips if k.startswith("Under")]
    assert parse_qs(urlsplit(chips["Any budget"]).query).get("b") is None
    assert page.href(page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2", "", "2000")) not in chips.values()
