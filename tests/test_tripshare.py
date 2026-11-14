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
    """The sheet; a trip that is not shared yet shows "Create link", which is pressed (the way a person makes the share)."""
    r = client.get("/trip/share")
    assert r.status_code == 200
    if 'id="sh-make"' in r.text:
        assert client.post("/trip/share", data={}, follow_redirects=False).status_code == 303
        r = client.get("/trip/share")
    return r.text


def rows():
    """(token, on) of the signed-in family's open trip's share rows (never more than one); none before the first one made."""
    from gitaway import community
    from sqlalchemy import text
    me = person("ari")
    with community.connect() as c:
        try:
            return [tuple(r) for r in c.conn.execute(text("SELECT token, on_ FROM trip_shares WHERE family = :f AND trip = :t"), {"f": me["tenant_id"], "t": tripshare.trip_id(me)})]
        except Exception:
            return []


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


def test_two_opens_at_once_make_one_link(tahoe_trip, monkeypatch):
    """The sheet is asked for twice when a finger goes down and then lifts: the second save meets the first's row and must answer with that row's token (a different one 404ed)."""
    me = person("ari")
    first = tripshare.save(me)
    monkeypatch.setattr(tripshare.secrets, "token_urlsafe", lambda n: "another-token-here")
    assert tripshare.save(me).token == first.token


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


# ---- the review's fixes (F-234) ---------------------------------------------------------------------------------------------------------------------

def test_a_get_never_makes_or_revives_a_share(tahoe_trip):
    old = token_of(open_sheet(tahoe_trip))
    tahoe_trip.post("/trip/share/off", headers={"Accept": "application/json"})
    for _ in range(3):      # the sheet opened, prefetched or tabbed past: still stopped
        html = tahoe_trip.get("/trip/share", headers={"X-Share": "1"}).text
        assert 'id="sh-make"' in html and "sh-img" not in html and "Create link" in html
    tahoe_trip.cookies.clear()
    assert tahoe_trip.get(f"/s/{old}").status_code == 404 and tahoe_trip.get(f"/s/{old}/card.png").status_code == 404
    assert [on for _, on in rows()] == [0]


def test_a_stopped_share_comes_back_under_a_new_token_when_created_again(tahoe_trip):
    old = token_of(open_sheet(tahoe_trip))
    tahoe_trip.post("/trip/share/off", headers={"Accept": "application/json"})
    new = token_of(open_sheet(tahoe_trip))
    assert new != old and len(new) == 16
    assert tahoe_trip.get(f"/s/{old}").status_code == 404 and tahoe_trip.get(f"/s/{new}").status_code == 200
    assert len(rows()) == 1


def test_a_viewer_gets_403_everywhere_and_nothing_is_written(tahoe_trip, monkeypatch):
    from gitaway import access
    token = token_of(open_sheet(tahoe_trip))
    before = rows()
    monkeypatch.setattr(access, "request_role", lambda: "viewer")
    hdr = {"Accept": "application/json"}
    assert tahoe_trip.get("/trip/share").status_code == 403
    assert tahoe_trip.post("/trip/share", data={"names": "1", "exact": "1"}, headers=hdr).status_code == 403
    assert tahoe_trip.post("/trip/share/off", headers=hdr).status_code == 403
    assert rows() == before and tripshare.find(token).names == ""      # not changed, not stopped
    assert 'id="sh-open"' not in tahoe_trip.get("/trip/cockpit").text      # and the cockpit does not offer it


def test_a_viewer_cannot_start_a_share_for_a_trip_that_has_none(tahoe_trip, monkeypatch):
    from gitaway import access
    before = rows()
    monkeypatch.setattr(access, "request_role", lambda: "viewer")
    assert tahoe_trip.post("/trip/share", data={}).status_code == 403
    assert rows() == before


def test_the_same_card_is_drawn_once_and_a_stopped_share_drops_its_picture(tahoe_trip, monkeypatch):
    from gitaway import sharecard
    from gitaway.pages import tripshare as page
    drawn = []
    real = sharecard.render
    monkeypatch.setattr(sharecard, "render", lambda c: drawn.append(c) or real(c))
    token = token_of(open_sheet(tahoe_trip))
    first = tahoe_trip.get(f"/s/{token}/card.png").content
    for v in ("1", "2", "3"):      # a varying ?v= is the same picture, drawn once
        assert tahoe_trip.get(f"/s/{token}/card.png?v={v}").content == first
    assert len(drawn) == 1
    tahoe_trip.post("/trip/share/off", headers={"Accept": "application/json"})
    assert not [k for k in page.CARDS.items if k[0] == token]


def test_the_picture_cache_is_capped(monkeypatch):
    from gitaway import sharecard
    from gitaway.pages.tripshare import CardCache
    monkeypatch.setattr(sharecard, "render", lambda c: c.title.encode())
    cache = CardCache(cap=3)
    for i in range(10):
        cache.get("t", sharecard.Card(f"Trip {i}", "Place"))
    assert [k[0] for k in cache.items] == ["t"] * 3 and list(cache.items.values()) == [b"Trip 7", b"Trip 8", b"Trip 9"]


def test_markup_in_a_title_is_text_on_the_page_and_the_sheet(tahoe_trip, monkeypatch):
    title = 'Fish & "chips" <b>on</b> <script>alert(1)</script>'
    real = tripshare.snapshot
    monkeypatch.setattr(tripshare, "snapshot", lambda *a, **k: {**real(*a, **k), "title": title})
    token = token_of(open_sheet(tahoe_trip))
    assert tripshare.find(token).title == title
    sheet = tahoe_trip.get("/trip/share").text
    tahoe_trip.cookies.clear()
    page = tahoe_trip.get(f"/s/{token}").text
    for html in (sheet, page):
        assert "<script>alert(1)</script>" not in html and "<b>on</b>" not in html and "alert(1)" not in html.replace("&lt;script&gt;alert(1)&lt;/script&gt;", "")
    assert 'Fish &amp; "chips" &lt;b&gt;on&lt;/b&gt; &lt;script&gt;alert(1)&lt;/script&gt;' in page
    assert tahoe_trip.get(f"/s/{token}/card.png").status_code == 200


def test_a_name_is_said_only_when_the_email_is_first_dot_last(tahoe_trip, monkeypatch):
    from gitaway import members
    people = [{"email": "ari.rivera@example.com"}, {"email": "jsmith99@example.com"}, {"email": "maya@example.com"}, {"email": "x_y.z@example.com"}, {"email": ""}, {"email": "a1.b2@example.com"}]
    monkeypatch.setattr(members, "members", lambda tid: people)
    assert tripshare.first_names(person("ari")) == "Ari and X"      # a handle, a single word, nothing and digits print nothing
    monkeypatch.setattr(members, "members", lambda tid: [{"email": "jsmith99@example.com"}, {"email": "traveler@example.com"}])
    assert tripshare.first_names(person("ari")) == ""
