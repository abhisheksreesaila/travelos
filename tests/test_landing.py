"""The landing page at /: two doors, prefilled search, feature cards, creators link."""
import html as htmllib
import re

from gitaway.catalog import SAMPLE_TRIP


def _get(client):
    r = client.get("/")
    assert r.status_code == 200
    return r.text


def _inputs(h):
    return {m.group(1): htmllib.unescape(m.group(2))
            for m in re.finditer(r'<input[^>]*name="(\w+)"[^>]*value="([^"]*)"', h)}


def test_two_doors_link_to_plan_and_the_sample_trip(client):
    h = _get(client)
    assert "Fork a" in h and "getaway." in h
    assert "Let\u2019s book it." in h
    assert "No plans yet?" in h
    assert 'href="/plan"' in h
    assert 'href="/trips/sun-tacos-and-tide-pools"' in h
    assert "Browse trips people loved" in h and 'href="/discover"' in h


def test_search_is_a_get_form_to_plan_with_labelled_prefilled_inputs(client):
    h = _get(client)
    form = re.search(r'<form[^>]*>', h).group(0)
    assert 'method="get"' in form and 'action="/plan"' in form
    vals = _inputs(h)
    assert set(vals) == {"from", "to", "when", "who"}
    assert vals["from"] == f"{SAMPLE_TRIP.origin_name} ({SAMPLE_TRIP.origin})"
    assert vals["to"] == "Los Angeles (LAX)"
    assert "Oct 16" in vals["when"] and "Oct 20" in vals["when"]
    assert vals["who"] == SAMPLE_TRIP.summary
    for label in ["From", "To", "When", "Who"]:
        assert re.search(rf"<label[^>]*>.*?{label}.*?<input", h, re.S)
    assert "Open my trip workspace" in h


def test_search_button_submits_the_form(client):
    h = _get(client)
    assert re.search(r'<button[^>]*type="submit"[^>]*>.*?Open my trip workspace', h, re.S)


def test_four_feature_cards(client):
    h = _get(client)
    assert "Not just a booking site" in h
    for title in ["Everything side by side", "One honest total", "Plan it together"]:
        assert title in h
    assert "Fork, don" in h and "start over" in h


def test_after_you_book_and_creators_sections(client):
    h = _get(client)
    assert "AFTER YOU BOOK" in h.upper()
    assert 'href="/creators"' in h and "Turn a link into a trip" in h


def test_no_old_brand_name(client):
    assert "TravelOS" not in _get(client)


def test_page_loads_its_own_stylesheet_and_new_tokens(client):
    assert "/assets/css/landing.css" in _get(client)
    tokens = client.get("/assets/css/tokens.css").text
    assert "--block-sunset: #FF8A63" in tokens and "--block-pacific: #6DB8FF" in tokens


def _order(h, *names):
    idx = [h.index(f"/assets/css/{n}") for n in names]
    assert idx == sorted(idx), idx


def test_stylesheets_load_tokens_then_base_then_page(client):
    _order(_get(client), "tokens.css", "base.css", "landing.css")
    _order(client.get("/trips/sun-tacos-and-tide-pools").text, "tokens.css", "base.css", "itinerary.css")


def test_fictional_card_links_to_discover(client):
    h = _get(client)
    m = re.search(r'<a[^>]*href="([^"]*)"[^>]*class="trip-card[^"]*"[^>]*>(?:(?!</a>).)*slow mornings', h, re.S)
    assert m and m.group(1) == "/discover"


def test_fork_count_comes_from_the_data(client):
    from dataclasses import replace
    from gitaway import itineraries
    slug = "sun-tacos-and-tide-pools"
    original = itineraries.ITINERARIES[slug]
    try:
        itineraries.ITINERARIES[slug] = replace(original, forks=777)
        assert re.search(r'sticker-n">777<', _get(client))
    finally:
        itineraries.ITINERARIES[slug] = original
    assert re.search(rf'sticker-n">{original.forks}<', _get(client))
