"""F-234: share the trip to Instagram, on the founder's Tahoe trip (tests/tahoe.py): the share sheet, the card as a public picture, the public page that tells nothing
private, and the choices (first names, exact dates) that are off until the family turns them on."""

import io
import re

import pytest
from PIL import Image

from gitaway import catalog, geopack, tripshare
from tests import tahoe
from tests.test_signin import person, sign_in

SECRETS = ("KQ7821", "VR4821936", "H77418215", "UA 5521", "Hertz", "United", "Heavenly", "Ski Run", "ari.rivera", "example.com", "Kid 1", "Kid 2", "Maya", "Abhi", "$")


def at(monkeypatch, utc):
    monkeypatch.setattr(catalog, "now_utc", lambda: utc)
    monkeypatch.setattr(catalog, "today", lambda: utc.astimezone(catalog.TZ).date())


@pytest.fixture
def tahoe_trip(client, monkeypatch):
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    monkeypatch.setattr(geopack, "LONG_SIDE", 512)
    sign_in(client)
    tahoe.seed(client, monkeypatch)
    at(monkeypatch, tahoe.NOW)
    return client


def token_of(html) -> str:
    return re.search(r'data-link="[^"]*/s/([A-Za-z0-9_-]+)"', html).group(1)


def open_sheet(client):
    r = client.get("/trip/share")
    assert r.status_code == 200
    return r.text


# ---- what a share says ----------------------------------------------------------------------------------------------------------------------

def test_the_snapshot_is_the_trips_title_place_route_month_and_length(tahoe_trip):
    s = tripshare.snapshot(person("ari"))
    assert (s["title"], s["place"], s["art"], s["month"], s["days"]) == ("Tahoe at Christmas", "South Lake Tahoe", "laketahoe", "December 2026", 8)
    assert s["route"] == ("SFO", "South Lake Tahoe")
    assert (s["exact"], s["names"], s["slug"]) == ("", "", "")      # off until the family chooses


def test_exact_dates_and_first_names_only_when_chosen(tahoe_trip):
    s = tripshare.snapshot(person("ari"), names=True, exact=True)
    assert s["exact"] == "Dec 19 – 26, 2026"
    assert s["names"] == "Ari"      # the family's members (people with an account), never the trip's traveller list: Kid 1 and Kid 2 are on it


def test_a_share_keeps_one_link_per_trip(tahoe_trip):
    me = person("ari")
    first = tripshare.save(me)
    again = tripshare.save(me, names=True, exact=True)
    assert again.token == first.token and len(first.token) == 16
    assert tripshare.find(first.token).names == "Ari"


def test_art_is_found_for_a_place_named_with_more_words():
    assert tripshare.art_for("South Lake Tahoe") == "laketahoe" and tripshare.art_for("San Diego") == "sandiego" and tripshare.art_for("Reykjavik") == ""


# ---- the sheet -------------------------------------------------------------------------------------------------------------------------------

def test_the_cockpit_has_the_button_and_it_opens_the_sheet(tahoe_trip):
    cockpit = tahoe_trip.get("/trip/cockpit").text
    assert re.search(r'<a [^>]*href="/trip/share"[^>]*id="sh-open"[^>]*>', cockpit) and "Share to Instagram" in cockpit
    assert "/assets/js/share.js" in cockpit and "/assets/css/share.css" in cockpit


def test_the_sheet_previews_the_card_with_both_choices_off(tahoe_trip):
    html = open_sheet(tahoe_trip)
    assert 'id="sh-img"' in html and re.search(r'src="/s/[A-Za-z0-9_-]{16}/card\.png\?v=[0-9a-f]{8}"', html)
    assert not re.search(r'name="names"[^>]*checked', html) and not re.search(r'name="exact"[^>]*checked', html)
    assert "Never a booking, a price, an email" in html
    fragment = tahoe_trip.get("/trip/share", headers={"X-Share": "1"}).text
    assert fragment.startswith('<div') and 'class="sh-frag"' in fragment[:60] and "<html" not in fragment and 'id="sh-title"' in fragment


def test_turning_the_choices_on_changes_the_card_and_keeps_the_link(tahoe_trip):
    first = open_sheet(tahoe_trip)
    token = token_of(first)
    j = tahoe_trip.post("/trip/share", data={"names": "1", "exact": "1"}, headers={"Accept": "application/json"}).json()
    assert j["names"] == "Ari" and j["exact"] == "Dec 19 – 26, 2026" and j["link"].endswith(f"/s/{token}")
    assert j["card"].startswith(f"/s/{token}/card.png?v=") and j["card"] != re.search(r'src="([^"]+)"', first).group(1)
    again = open_sheet(tahoe_trip)
    assert re.search(r'name="names"[^>]*checked', again) and re.search(r'name="exact"[^>]*checked', again)      # the sheet remembers
    off = tahoe_trip.post("/trip/share", data={}, headers={"Accept": "application/json"}).json()
    assert off["names"] == "" and off["exact"] == ""


def test_without_script_the_form_goes_back_to_the_sheet(tahoe_trip):
    open_sheet(tahoe_trip)
    r = tahoe_trip.post("/trip/share", data={"names": "1"}, follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (303, "/trip/share")


def test_signed_out_is_sent_to_sign_in(client, tahoe_trip):
    client.cookies.clear()
    assert client.get("/trip/share", follow_redirects=False).headers["location"].startswith("/signin")


# ---- the public card and page -----------------------------------------------------------------------------------------------------------------

def test_the_card_is_a_public_1080_by_1350_png(tahoe_trip):
    token = token_of(open_sheet(tahoe_trip))
    tahoe_trip.cookies.clear()      # a stranger
    r = tahoe_trip.get(f"/s/{token}/card.png")
    assert (r.status_code, r.headers["content-type"], r.headers["cache-control"]) == (200, "image/png", "public, max-age=300")
    img = Image.open(io.BytesIO(r.content))
    assert (img.format, img.size) == ("PNG", (1080, 1350)) and img.getpixel((540, 2)) == (214, 233, 247)


def test_the_public_page_tells_nothing_private(tahoe_trip):
    token = token_of(open_sheet(tahoe_trip))
    tahoe_trip.post("/trip/share", data={}, headers={"Accept": "application/json"})
    tahoe_trip.cookies.clear()
    r = tahoe_trip.get(f"/s/{token}")
    assert r.status_code == 200
    page = r.text
    for word in ("Tahoe at Christmas", "South Lake Tahoe", "December 2026", "8 days", "SFO", "Plan your own trip"):
        assert word in page, word
    assert 'name="robots" content="noindex"' in page
    for secret in SECRETS:
        assert secret not in page, secret
    assert not re.search(r"Dec(ember)? (19|2\d)\b", page)      # no exact day of the stay
    assert re.search(r'property="og:image" content="https://[^"]+/s/' + token + r'/card\.png\?v=[0-9a-f]{8}"', page)


def test_even_with_names_and_dates_chosen_the_page_stays_plain_and_the_card_never_holds_a_secret(tahoe_trip):
    token = token_of(open_sheet(tahoe_trip))
    tahoe_trip.post("/trip/share", data={"names": "1", "exact": "1"}, headers={"Accept": "application/json"})
    tahoe_trip.cookies.clear()
    page = tahoe_trip.get(f"/s/{token}").text
    assert not re.search(r"\bAri\b", page)      # the card may say the first names the family chose; the page never does
    assert "Dec 19" not in page and "Dec 26" not in page
    card = tripshare.find(token).card()
    assert (card.names, card.when) == ("Ari", "Dec 19 – 26, 2026")
    assert set(vars(card)) == {"title", "place", "route", "when", "days", "names", "link", "art_slug"}      # no field a booking could ride in on


def test_turning_it_off_answers_404_for_the_page_and_the_card(tahoe_trip):
    token = token_of(open_sheet(tahoe_trip))
    assert tahoe_trip.post("/trip/share/off", headers={"Accept": "application/json"}).json() == {"off": True}
    tahoe_trip.cookies.clear()
    assert tahoe_trip.get(f"/s/{token}").status_code == 404 and tahoe_trip.get(f"/s/{token}/card.png").status_code == 404


def test_an_unknown_or_odd_token_is_404(client):
    for t in ("nope", "x" * 16, "..%2f..%2fetc", "a" * 80):
        assert client.get(f"/s/{t}").status_code == 404 and client.get(f"/s/{t}/card.png").status_code == 404
