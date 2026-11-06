"""F-181: a family publishes a real trip as a creator page. The flow (draft, preview, publish, update, unpublish), who may, what a stranger sees and never sees
(the stored snapshot, the page, the hub, the profile and the photo files), the public photo route, forks, and what exists with the showcase on and off.
All through the HTTP seam; pictures are generated in the test (tests/photo_files.py)."""

import re
from html import unescape

import pytest
from PIL import Image

from gitaway import community, itineraries, publish, session as ses
from tests.photo_files import image
from tests.test_members import addr, browser, invite
from tests.test_signin import person, sign_in
from tests.test_trip_import import TEMPLATE, imported

STROLL = "2026:10:17 10:30:00"
GPS = (33.8121, -117.9190)   # Disneyland's front gate: a position that must never reach a public file
PRIVATE = ("ABCDEF", "987654321", "H1234567", "7123456789012", "AS 1234", "AS 1235", "Alaska Airlines", "Example Hotel", "123 Ocean", "90401",
           "CHAT-SECRET-77", "CAPTION-SECRET-88", "priya@gmail.com", "you@gmail.com", "Priya", "Zelda", "Expedia")
NOTE, TIP = "Rope drop at 8 and the Matterhorn first.", "Bring a poncho for Splash Mountain season."


def upload(client, caption="", **meta):
    r = client.post("/trip/photos", files=[("photo", ("pic.jpg", image("jpeg", **meta), "image/jpeg"))], data={"caption": caption}, headers={"X-Fragment": "1"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture
def family(client):
    """Ari with the imported LA trip (confirmation numbers, a hotel address, travelers' emails), a plan, a photo with a GPS position and a caption, a chat line, and a second
    member (Zelda) who has posted a photo and a line too."""
    imported(client)
    assert client.post("/trip/plans", data={"id": "a1", "day": "1", "start": "10:00", "title": "Rope drop at the park", "kind": "fun"}, follow_redirects=False).status_code in (200, 303)
    client.post("/trip/family/message", data={"text": "CHAT-SECRET-77"}, headers={"X-Fragment": "1"})
    pid = upload(client, caption="CAPTION-SECRET-88", taken=STROLL, gps=GPS)
    z = addr("zelda")
    invite(client, z, "editor")
    other = browser(client)
    sign_in(other, z)
    other.post("/trip/family/message", data={"text": "Zelda was here"}, headers={"X-Fragment": "1"})
    upload(other, caption="CAPTION-SECRET-88", taken=STROLL, gps=GPS)
    return client, pid


def draft(client, pid, **over):
    data = {"title": "Our Disneyland week", "name": "Ari Rivera", "photos": [pid], "cover": pid, "stickers": ["kid"], "note_2": NOTE, "tip": [TIP, "", ""], **over}
    r = client.post("/trip/publish/save", data=data, follow_redirects=False)
    assert r.status_code == 303, r.text[:300]
    return r


def go_live(client, pid, **over):
    draft(client, pid, **over)
    r = client.post("/trip/publish", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/trip/publish?live=1"), r.text[:400]
    return community.rows(kind="scrapbook")[-1]


def stranger(client):
    other = browser(client)
    other.cookies.clear()
    return other


def main_of(html):
    return html.split("<main")[1].split("</main>")[0]


# ---- the flow --------------------------------------------------------------------------------------------------------

def test_the_editor_shows_every_day_with_its_photos_and_what_stays_private(family):
    client, pid = family
    html = client.get("/trip/publish").text
    assert "Publish this trip" in html and "Draft: nobody can see this yet" in html
    assert "Never shown: booking and confirmation numbers" in html
    assert 'name="note_1"' in html and 'name="note_5"' in html and 'name="note_6"' not in html   # Oct 16 to 20: five days
    assert f'value="{pid}"' in html and f"/trip/photos/{pid}/thumb" in html
    assert 'value="Ari"' in html and 'value="Ari Rivera"' not in html and 'value="LA with the kids"' in html     # F-182 L4: the name shown on a public page starts as the first name only


def test_preview_is_the_public_page_with_publish_and_back(family):
    client, pid = family
    html = client.post("/trip/publish/save", data={"title": "Our Disneyland week", "name": "Ari Rivera", "photos": [pid], "cover": pid, "note_2": NOTE, "tip": [TIP], "do": "preview"}, follow_redirects=False)
    assert html.headers["location"] == "/trip/publish/preview"
    page = client.get("/trip/publish/preview").text
    assert "This is exactly what strangers will see" in page
    assert NOTE in page and TIP in page and "Our Disneyland week" in page
    assert 'id="pb-publish"' in page and ">Publish<" in page.replace("</svg>", "") and 'id="pb-back"' in page
    assert community.rows() == []   # a preview publishes nothing


def test_publishing_makes_a_page_a_signed_out_stranger_can_read(family):
    client, pid = family
    row = go_live(client, pid)
    slug = row["slug"]
    r = stranger(client).get(f"/trips/{slug}")
    assert r.status_code == 200
    page = unescape(main_of(r.text))
    assert "Our Disneyland week" in page and NOTE in page and TIP in page and "By Ari Rivera" in page
    assert "Rope drop at the park" in page and "Flight to LAX" in page and "a hotel in Santa Monica" in page
    assert "Kid friendly" in page and "1 photos" in page
    assert re.search(r'href="/plan\?[^"]*to=la', r.text.replace("&amp;", "&")), "Plan this trip goes to the LA place"
    assert re.search(r'src="/pub/' + slug + r'/[0-9a-f]{16}-display\.jpg"', r.text)
    assert 'href="/creators/ari-rivera"' in r.text and row["kind"] == "scrapbook"


def test_plan_this_trip_has_dates_ahead_for_as_many_days_as_the_trip(family):
    client, pid = family
    slug = go_live(client, pid)["slug"]
    href = unescape(re.search(r'href="(/plan\?[^"]+)"', stranger(client).get(f"/trips/{slug}").text).group(1))
    q = dict(x.split("=") for x in href.split("?")[1].split("&"))
    from datetime import date
    d, r = date.fromisoformat(q["d"]), date.fromisoformat(q["r"])
    assert q["to"] == "la" and q["a"] == "2" and d.weekday() == 4 and (d - date(2026, 9, 30)).days >= 45 and (r - d).days == 4


def test_the_public_page_is_on_the_creators_profile_and_community_trips(family):
    client, pid = family
    row = go_live(client, pid)
    s = stranger(client)
    profile = s.get("/creators/ari-rivera")
    assert profile.status_code == 200 and "Ari Rivera" in profile.text and f'href="/trips/{row["slug"]}"' in profile.text
    hub = s.get("/community").text
    assert "Our Disneyland week" in hub and f'href="/trips/{row["slug"]}"' in hub
    assert "Ari Rivera" in s.get("/creators").text


def test_the_creator_handle_comes_from_the_name_is_unique_and_never_changes(family):
    client, pid = family
    go_live(client, pid)
    assert community.creator_of(person("ari")["user_id"])["handle"] == "ari-rivera"
    go_live(client, pid, name="Ari R.")   # a new name shows, the address stays
    c = community.creator_of(person("ari")["user_id"])
    assert c["handle"] == "ari-rivera" and c["name"] == "Ari R."
    other = community.claim_creator("someone-else", "Ari Rivera")   # the same name for another person gets its own address
    assert other["handle"] == "ari-rivera-2"
    assert community.claim_creator("x", "Sunny Ines")["handle"] == "sunny-ines-2"   # a sample creator's handle is taken too


def test_publishing_again_updates_the_page_and_keeps_its_address(family):
    client, pid = family
    first = go_live(client, pid)
    second = go_live(client, pid, note_2="Changed my mind: Space Mountain first.")
    assert second["slug"] == first["slug"] and len(community.rows(kind="scrapbook")) == 1
    page = stranger(client).get(f"/trips/{first['slug']}").text
    assert "Space Mountain first." in page and NOTE not in page


def test_unpublish_takes_down_the_page_the_photo_copies_and_the_cards(family):
    client, pid = family
    row = go_live(client, pid)
    slug = row["slug"]
    s = stranger(client)
    copy = re.search(r'/pub/[^"]+-display\.jpg', s.get(f"/trips/{slug}").text).group(0)
    assert s.get(copy).status_code == 200 and (publish.root() / slug).is_dir()
    r = client.post("/trip/publish/unpublish", follow_redirects=False)
    assert r.status_code == 303
    assert s.get(f"/trips/{slug}").status_code == 404 and s.get(copy).status_code == 404
    assert not (publish.root() / slug).exists() and community.rows() == []
    assert "Draft: nobody can see this yet" in client.get("/trip/publish").text   # the draft stays, to publish again


def test_a_viewer_cannot_publish_or_unpublish(family):
    client, pid = family
    go_live(client, pid)
    v = addr("vera")
    invite(client, v, "viewer")
    other = browser(client)
    sign_in(other, v)
    assert other.get("/trip/publish").status_code == 403 and other.get("/trip/publish/preview").status_code == 403
    for path in ("/trip/publish/save", "/trip/publish", "/trip/publish/unpublish"):
        assert other.post(path, data={"title": "x"}, follow_redirects=False).status_code == 403, path
    assert len(community.rows(kind="scrapbook")) == 1


def test_another_editor_cannot_replace_or_remove_the_publishers_page_but_an_admin_can_remove_it(family):
    client, pid = family
    go_live(client, pid)
    e = addr("edie")
    invite(client, e, "editor")
    other = browser(client)
    sign_in(other, e)
    assert other.post("/trip/publish", follow_redirects=False).status_code == 409
    assert other.post("/trip/publish/unpublish", follow_redirects=False).status_code == 403
    assert len(community.rows(kind="scrapbook")) == 1
    assert client.post("/trip/publish/unpublish", follow_redirects=False).status_code == 303   # Ari is the family's admin (and the publisher)
    assert community.rows() == []


def test_signed_out_goes_through_sign_in(client):
    for method, path in (("get", "/trip/publish"), ("get", "/trip/publish/preview"), ("post", "/trip/publish"), ("post", "/trip/publish/save"), ("post", "/trip/publish/unpublish")):
        r = getattr(client, method)(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/signin?next="), path


def test_only_the_trips_own_photos_can_be_picked(family):
    client, pid = family
    other = browser(client)
    sign_in(other, "sam")
    other.post("/trips/import/save", data={"text": TEMPLATE}, follow_redirects=False)
    foreign = upload(other, taken=STROLL)
    go_live(client, pid, photos=[pid, foreign, "../../etc/passwd"], cover=foreign)
    d = publish.get(person("ari"))
    assert d["photos"] == [pid] and d["cover"] == pid
    assert len(list((publish.root() / d["slug"]).iterdir())) == 2   # one photo: its display and its thumbnail


def test_an_email_address_in_the_text_is_refused(family):
    client, pid = family
    r = client.post("/trip/publish/save", data={"title": "Our trip", "name": "Ari Rivera", "tip": ["write me at ari@example.com"]}, follow_redirects=False)
    assert r.status_code == 200 and "Take the email address out" in r.text
    assert publish.get(person("ari"))["tips"] == []


def test_a_mention_of_a_family_member_is_flagged_in_the_preview(family):      # and blocks publishing until ticked: tests/test_kids_names.py (F-194)
    client, pid = family
    draft(client, pid, note_2="Zelda loved the teacups.")
    page = client.get("/trip/publish/preview").text
    assert 'id="pb-warn"' in page and "It mentions Zelda" in page


def test_deleting_the_trip_takes_its_public_page_down(family):
    client, pid = family
    row = go_live(client, pid)
    trip_id = ses.trips(person("ari"))[0].id
    assert client.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False).status_code in (200, 303)
    assert stranger(client).get(f"/trips/{row['slug']}").status_code == 404 and not (publish.root() / row["slug"]).exists()


# ---- privacy ---------------------------------------------------------------------------------------------------------

def public_everything(client, row):
    """Every place a stranger can read it, and what is stored: the page, the hub card, the profile, the snapshot row, and every public photo's bytes."""
    s = stranger(client)
    page = s.get(f"/trips/{row['slug']}").text
    hub = s.get("/community").text
    prof = s.get("/creators/ari-rivera").text
    stored = repr({k: v for k, v in community.get(row["slug"]).items() if k not in ("created_at", "updated_at")})   # when it was published is not a date of the trip
    text = unescape(re.sub(r'/plan\?[^"]*', "", main_of(page) + main_of(hub) + main_of(prof)) + stored)   # "Plan this trip" carries dates ahead, not the trip's own
    files = b"".join(f.read_bytes() for f in (publish.root() / row["slug"]).iterdir())
    return text, files


def test_the_private_details_really_are_in_the_family_own_pages(family):
    """The control for the test below: every secret it looks for is in the family's data, so its absence from the public page means something."""
    client, pid = family
    own = unescape(client.get("/trip/details").text + client.get("/trip/family?view=chat").text + client.get("/family").text)
    for secret in ("ABCDEF", "987654321", "H1234567", "7123456789012", "AS 1234", "Alaska Airlines", "Example Hotel", "123 Ocean", "90401", "priya@gmail.com", "Expedia", "CHAT-SECRET-77", "Zelda"):
        assert secret in own, secret


def test_no_private_detail_reaches_the_page_the_hub_the_profile_or_the_stored_snapshot(family):
    client, pid = family
    row = go_live(client, pid)
    text, _ = public_everything(client, row)
    for secret in PRIVATE:
        assert secret not in text, secret
    assert not re.search(r"\$\s?\d", text), "no prices"
    assert not re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b", text), "no calendar dates"
    assert not re.search(r"\b20\d\d-\d\d-\d\d\b", text)
    assert "Santa Monica" in text   # the area is allowed, the street is not


def test_the_stored_snapshot_has_only_the_allowed_fields(family):
    client, pid = family
    row = go_live(client, pid)
    import json
    snap = json.loads(row["snapshot"])
    assert set(snap) == {"slug", "title", "headline", "accent", "place", "lede", "days", "tags", "stats", "forks", "source", "polaroids", "weather", "route", "author", "theme",
                         "tips", "real", "handle", "plan_to", "plan_days"}
    assert set(snap["days"][1]) == {"n", "date", "title", "weather", "stops", "collapsed", "note", "photos"}
    assert set(snap["days"][0]["stops"][0]) == {"time", "title", "kind", "bubble", "booked", "tag", "tag_color", "meta", "note", "photo", "photo_alt"}
    assert set(row["meta"]) == {"handle", "name", "place"} and snap["source"] is None
    assert "Priya" not in repr(row) and "Zelda" not in repr(row)


def test_public_photo_copies_carry_no_exif_no_position_and_no_comment(family):
    client, pid = family
    row = go_live(client, pid)
    folder = publish.root() / row["slug"]
    names = sorted(f.name for f in folder.iterdir())
    assert len(names) == 2 and names[0].endswith("-display.jpg") and names[1].endswith("-thumb.jpg")
    for f in folder.iterdir():
        raw = f.read_bytes()
        img = Image.open(f)
        assert img.format == "JPEG" and dict(img.getexif()) == {} and img.getexif().get_ifd(0x8825) == {}, f.name
        assert not {"exif", "comment", "xmp", "photoshop"} & set(img.info), f.name
        assert b"Exif" not in raw and b"http://ns.adobe.com" not in raw
        assert f"{GPS[0]:.2f}".encode() not in raw


def test_the_family_photo_routes_stay_members_only(family):
    client, pid = family
    row = go_live(client, pid)
    s = stranger(client)
    assert s.get(f"/trip/photos/{pid}/display").status_code == 401 and s.get(f"/trip/photos/{pid}/thumb").status_code == 401
    assert client.get(f"/trip/photos/{pid}/display").status_code == 200
    assert row["slug"] not in client.get(f"/trip/photos/{pid}/display").headers.get("cache-control", "")


# ---- the public photos -----------------------------------------------------------------------------------------------

def test_a_public_photo_is_served_to_anyone_and_cacheable(family):
    client, pid = family
    slug = go_live(client, pid)["slug"]
    copy = re.search(r'/pub/[^"]+-display\.jpg', stranger(client).get(f"/trips/{slug}").text).group(0)
    r = stranger(client).get(copy)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.headers["cache-control"] == "public, no-cache" and r.headers["x-content-type-options"] == "nosniff"
    again = stranger(client).get(copy, headers={"if-none-match": r.headers["etag"]})
    assert again.status_code == 304


@pytest.mark.parametrize("name", ["../x-display.jpg", "0123456789abcdef-original.jpg", "0123456789abcdef-display.png", "nothex0000000000-display.jpg", "%2e%2e%2fx-display.jpg"])
def test_a_public_photo_route_refuses_anything_it_did_not_make(family, name):
    client, pid = family
    slug = go_live(client, pid)["slug"]
    assert stranger(client).get(f"/pub/{slug}/{name}").status_code == 404


def test_an_unpublished_or_unknown_slug_has_no_photos(family):
    client, pid = family
    assert stranger(client).get("/pub/nothing-here/0123456789abcdef-display.jpg").status_code == 404
    assert stranger(client).get("/pub/../photos/x/y.jpg").status_code == 404


# ---- fork ------------------------------------------------------------------------------------------------------------

def test_a_signed_in_stranger_can_fork_it_and_a_signed_out_one_is_sent_to_sign_in(family):
    client, pid = family
    slug = go_live(client, pid)["slug"]
    s = stranger(client)
    page = s.get(f"/trips/{slug}").text
    assert f"/signin?next=/trips/{slug}&amp;intent=fork" in page or f"/signin?next=/trips/{slug}&intent=fork" in page
    fan = browser(client)
    sign_in(fan, "sam", next=f"/trips/{slug}", intent="fork")
    assert slug in ses.forks(person("sam"))
    assert "Our Disneyland week" in fan.get("/forks").text
    assert fan.get(f"/trips/{slug}").status_code == 200


# ---- the showcase switch ---------------------------------------------------------------------------------------------

def test_with_the_showcase_off_nothing_is_public_until_a_real_trip_is_published(family, monkeypatch):
    client, pid = family
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    s = stranger(client)
    for path in ("/community", "/discover", "/creators", "/creators/sunny-ines", "/forks", "/share", "/trips/sun-tacos"):
        assert s.get(path).status_code == 404, path
    assert client.get("/trip/publish").status_code == 200   # publishing itself is not hidden: it is how real content starts


def test_with_the_showcase_off_only_real_content_shows(family, monkeypatch):
    client, pid = family
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    row = go_live(client, pid)
    s = stranger(client)
    hub = s.get("/community")
    assert hub.status_code == 200
    body = unescape(main_of(hub.text))
    assert "Our Disneyland week" in body and "Ari Rivera" in body
    assert not re.search(r"\b\d+ forks?\b", body) and "Our LA family week" not in body and "Be the first to share one" not in body
    assert "Turn a link into a trip" not in body and "From creators" not in body
    roster = s.get("/creators")
    assert roster.status_code == 200 and "ari-rivera" in roster.text and "sunny-ines" not in roster.text and "Paste" not in roster.text
    assert s.get("/creators/ari-rivera").status_code == 200 and s.get("/creators/sunny-ines").status_code == 404
    for path in ("/creators/draft", "/creators/finish", "/creators/done", "/share", "/sandbox/x", "/trips/sun-tacos", "/trips/nothing-here"):
        assert s.get(path).status_code == 404, path
    assert s.post("/creators", data={"link": "https://www.youtube.com/watch?v=x"}).status_code == 404
    assert s.get(f"/trips/{row['slug']}").status_code == 200 and s.get("/forks", follow_redirects=False).status_code == 200


def test_with_the_showcase_off_a_sample_trip_cannot_be_forked_or_saved(family, monkeypatch):
    client, pid = family
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    go_live(client, pid)
    fan = browser(client)
    sign_in(fan, "sam")
    fan.post("/fork", data={"next": "/trips/sun-tacos"}, follow_redirects=False)
    fan.post("/save", data={"next": "/trips/sun-tacos"}, follow_redirects=False)
    assert ses.forks(person("sam")) == [] and ses.saved(person("sam")) == []


def test_unpublishing_the_last_trip_puts_the_pages_back_to_404(family, monkeypatch):
    client, pid = family
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    go_live(client, pid)
    client.post("/trip/publish/unpublish", follow_redirects=False)
    s = stranger(client)
    assert s.get("/community").status_code == 404 and s.get("/creators").status_code == 404 and s.get("/creators/ari-rivera").status_code == 404


def test_the_nav_links_to_community_trips_only_when_there_is_real_content_or_the_showcase(family, monkeypatch):
    client, pid = family
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert 'href="/community"' not in client.get("/trip/publish").text
    go_live(client, pid)
    assert 'href="/community"' in client.get("/trip/publish").text


def test_on_the_showcase_the_samples_stay_and_real_creators_join_them(family):
    client, pid = family
    go_live(client, pid)
    s = stranger(client)
    sample = next(iter(itineraries.ITINERARIES.values())).title
    assert unescape(sample) in unescape(s.get("/community").text) and "Our Disneyland week" in s.get("/community").text
    roster = s.get("/creators").text
    assert "sunny-ines" in roster and "ari-rivera" in roster and "Paste" in roster
    assert s.get("/creators/sunny-ines").status_code == 200


def test_a_photo_another_member_added_is_marked_so_the_publisher_checks_with_them(family):
    """F-182 L4: the editor listed every member's photos alike, so a member's photo could go public on someone else's page unnoticed."""
    client, pid = family
    html = client.get("/trip/publish").text
    tiles = re.findall(r'<div class="pb-tile">.*?</div>', html, re.S)
    mine = [t for t in tiles if f'value="{pid}"' in t]
    others = [t for t in tiles if f'value="{pid}"' not in t and "pb-photo" in t]
    assert len(mine) == 1 and "pb-by" not in mine[0] and "Added by" not in mine[0]
    assert others and all("Added by Zelda: check with them" in t and "Zelda" in t for t in others)
    assert "Rivera" not in "".join(others)
