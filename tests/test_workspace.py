"""The booking workspace at /plan: server-rendered ledger, URL-held picks, catalog-derived totals."""
import json
import re
from urllib.parse import parse_qs, urlparse

from gitaway import catalog
from gitaway.pages import placeholders, plan


def test_default_ledger_shows_the_default_pick_total(client):
    r = client.get("/plan")
    assert r.status_code == 200
    assert catalog.money(catalog.quote("f1", "h1", "c1").total_cents) == "$3,088"
    assert "$3,088" in r.text
    assert "$1,236" in r.text and "$1,540" in r.text and "$312" in r.text


def test_cheapest_combination_from_the_url(client):
    r = client.get("/plan?f=f4&h=h3&c=c3")
    assert "$2,040" in r.text and "The cheapest combination" in r.text


def test_default_total_is_flagged_as_more_than_cheapest(client):
    assert "$1,048 more than the cheapest combo" in client.get("/plan").text


def test_bad_or_wrong_lane_ids_fall_back_to_the_default(client):
    assert "$3,088" in client.get("/plan?f=nope&h=zzz&c=").text
    assert "$3,088" in client.get("/plan?f=h1&h=c2&c=f3").text  # ids from the wrong lane
    assert plan.resolve_pick("f4", "bogus", "c3") == ("f4", "h1", "c3")  # a good lane keeps its pick
    assert plan.resolve_pick(None, None, None) == ("f1", "h1", "c1")
    assert "$2,308" in client.get("/plan?f=f4&h=bogus&c=c3").text


def test_every_offer_renders_with_its_catalog_price(client):
    h = client.get("/plan").text
    assert len(re.findall(r'data-lane="flight"', h)) == 5
    assert len(re.findall(r'data-lane="stay"', h)) == 3
    assert len(re.findall(r'data-lane="car"', h)) == 3
    assert h.count('aria-pressed="true" data-lane') == 3
    for o in [*catalog.offers("flight"), *catalog.offers("stay"), *catalog.offers("car")]:
        assert o.name.replace("&", "&amp;") in h
        assert catalog.money(o.price_cents) in h


def test_stays_show_the_area_photo_captioned_as_the_area(client):
    h = client.get("/plan").text
    assert "/assets/photos/santa-monica-beach-pier.jpg" in h
    assert "Santa Monica area" in h and "Venice area" in h
    assert "Tidewater</figcaption>" not in h


def test_burbank_flight_is_shown(client):
    h = client.get("/plan").text
    assert "Pacific Hop 312" in h and "Lands BUR" in h


def test_book_link_carries_next_and_pay_intent(client):
    h = client.get("/plan?f=f2&h=h2&c=c2").text
    href = re.search(r'id="ws-book"[^>]*href="(/signin\?[^"]+)"', h) or re.search(r'href="(/signin\?[^"]+)"[^>]*id="ws-book"', h)
    href = href.group(1).replace("&amp;", "&")
    qs = parse_qs(urlparse(href).query)
    assert qs["intent"] == ["pay"]
    assert qs["next"] == ["/plan?f=f2&h=h2&c=c2"]
    assert "%2Fplan" in href  # url-encoded


def test_embedded_quotes_match_catalog_for_every_combination(client):
    h = client.get("/plan").text
    raw = re.search(r'<script[^>]*id="ws-data"[^>]*>(.*?)</script>', h, re.S).group(1)
    data = json.loads(raw)
    assert len(data["quotes"]) == 45
    for key, entry in data["quotes"].items():
        q = catalog.quote(*key.split("|"))
        assert entry["total"] == catalog.money(q.total_cents)
        assert (entry["delta"] == "The cheapest combination") == (q.above_cheapest_cents == 0)
        assert entry["book"].startswith("/signin?next=%2Fplan%3Ff%3D") and entry["book"].endswith("&intent=pay")


def test_placeholder_is_gone_and_brand_is_gitaway(client):
    assert "/plan" not in placeholders.PLACEHOLDERS
    h = client.get("/plan").text
    assert "TravelOS" not in h and "Opening soon" not in h
    assert "/assets/css/workspace.css" in h and "/assets/js/workspace.js" in h
    assert client.get("/assets/js/workspace.js").status_code == 200
    assert client.get("/assets/css/workspace.css").status_code == 200
    assert "workspace.css" not in client.get("/").text


def test_context_column_is_one_quiet_placeholder(client):
    assert client.get("/plan").text.count('data-pane="context"') == 1
