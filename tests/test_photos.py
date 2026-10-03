"""F-071: photos on the plan. Validation, EXIF time and position, matching to a plan, where the files go, who can see and remove them, and the
thread card. Pictures are generated in the test (tests/photo_files.py); nothing is fetched."""

import io
from datetime import datetime, timezone

import pytest
from PIL import Image

from gitaway import familythread as ft, photos, tripday
from tests.photo_files import image
from tests.test_calendar import add, book
from tests.test_members import addr, browser, invite
from tests.test_signin import person, sign_in, tid

UTC = timezone.utc
# the sample trip is Oct 16-20 2026 in Los Angeles; day 1 is Sat Oct 17. `add` makes "Venice Canals stroll" on day 1, 10:00-11:30.
STROLL = "2026:10:17 10:30:00"


def upload(client, *files, caption="", fragment=True):
    parts = [("photo", (name, data, mime)) for name, data, mime in files]
    return client.post("/trip/photos", files=parts, data={"caption": caption}, headers={"X-Fragment": "1"} if fragment else {}, follow_redirects=False)


def jpg(**meta):
    return ("pic.jpg", image("jpeg", **meta), "image/jpeg")


@pytest.fixture
def trip(client):
    """Ari with the sample trip booked and one plan (Venice Canals stroll, Sat 10:00-11:30)."""
    book(client)
    add(client)
    return client


@pytest.fixture
def ari():
    return person("ari")


# ---- what is accepted ------------------------------------------------------------------------------------------------------

def test_the_kind_comes_from_the_first_bytes_not_the_name_or_claimed_type():
    assert photos.kind_of(image("jpeg")) == "jpeg" and photos.kind_of(image("png")) == "png"
    assert photos.kind_of(image("webp")) == "webp" and photos.kind_of(image("heic")) == "heic"
    assert photos.kind_of(b"GIF89a....") is None and photos.kind_of(b"%PDF-1.7") is None and photos.kind_of(b"<svg xmlns='x'/>") is None


@pytest.mark.parametrize("kind", ["jpeg", "png", "webp", "heic"])
def test_each_accepted_type_is_kept(trip, ari, kind):
    p = photos.add(ari, image(kind))
    assert p["orig"].endswith({"jpeg": ".jpg", "png": ".png", "webp": ".webp", "heic": ".heic"}[kind])
    assert photos.get(ari, p["id"])["id"] == p["id"]


def test_a_file_that_is_not_a_picture_is_refused_whatever_it_is_called(trip, ari):
    for bad in (b"%PDF-1.7 not a picture", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", b"MZ\x90\x00 exe", b"GIF89a\x01\x00"):
        with pytest.raises(photos.PhotoError, match="Only JPEG, PNG, WebP and HEIC"):
            photos.add(ari, bad)
    r = upload(trip, ("evil.jpg", b"%PDF-1.7 not a picture", "image/jpeg"))
    assert r.status_code == 415 and "Only JPEG" in r.text


def test_a_broken_picture_with_a_valid_start_is_refused_without_leaving_files(trip, ari):
    before = list(photos.root().rglob("*")) if photos.root().exists() else []
    with pytest.raises(photos.PhotoError, match="could not be opened"):
        photos.add(ari, b"\xff\xd8\xff\xe0" + b"\x00" * 200)
    assert (list(photos.root().rglob("*")) if photos.root().exists() else []) == before
    assert photos.listing(ari) == []


def test_an_empty_file_is_refused(trip, ari):
    with pytest.raises(photos.PhotoError, match="empty"):
        photos.add(ari, b"")


def test_a_photo_over_the_size_limit_is_refused_by_the_model(trip, ari, monkeypatch):
    monkeypatch.setattr(photos, "MAX_BYTES", 500)
    with pytest.raises(photos.PhotoError, match="too large"):
        photos.add(ari, image("jpeg", size=(300, 300)))


def test_an_oversized_upload_is_refused_before_it_is_read(trip, monkeypatch):
    """The Content-Length check runs before the body is parsed (as F-056's): a request claiming a huge body gets 413 and nothing is stored."""
    monkeypatch.setattr(photos, "MAX_BYTES", 2000)
    monkeypatch.setattr(photos, "MAX_FILES", 1)
    r = trip.post("/trip/photos", content=b"x" * 400_000, headers={"content-type": "multipart/form-data; boundary=zz", "X-Fragment": "1"})
    assert r.status_code == 413 and "too large" in r.text
    r = upload(trip, ("big.jpg", image("jpeg", size=(900, 900), color=(1, 2, 3)) + b"\0" * 5000, "image/jpeg"))
    assert r.status_code in (400, 413) and "too large" in r.text
    assert photos.listing(person("ari")) == []


def test_a_decompression_bomb_is_refused(trip, ari, monkeypatch):
    monkeypatch.setattr(photos, "MAX_PIXELS", 1000)
    with pytest.raises(photos.PhotoError, match="too large to open"):
        photos.add(ari, image("png", size=(100, 100)))


def test_at_most_six_photos_in_one_upload(trip):
    r = upload(trip, *[jpg() for _ in range(photos.MAX_FILES + 1)])
    assert r.status_code == 400 and "at most" in r.text and photos.listing(person("ari")) == []


# ---- EXIF ------------------------------------------------------------------------------------------------------------------

def exif_of(data):
    return photos.exif_of(photos._open(data))


def test_the_taken_time_and_position_are_read_from_the_exif():
    taken, coords = exif_of(image("jpeg", taken=STROLL, gps=(34.0522, -118.2437)))
    assert taken == datetime(2026, 10, 17, 10, 30) and taken.tzinfo is None
    assert coords == pytest.approx((34.0522, -118.2437), abs=1e-3)


def test_south_and_west_are_negative_and_a_time_zone_offset_is_kept():
    taken, coords = exif_of(image("jpeg", taken=STROLL, offset="+10:00", gps=(-33.8688, 151.2093)))
    assert taken.utcoffset().total_seconds() == 10 * 3600 and coords == pytest.approx((-33.8688, 151.2093), abs=1e-3)
    assert exif_of(image("jpeg", gps=(40.7, -74.0)))[1] == pytest.approx((40.7, -74.0), abs=1e-2)


def test_heic_and_webp_exif_are_read_too():
    for kind in ("webp", "heic"):
        taken, coords = exif_of(image(kind, taken=STROLL, gps=(34.0, -118.0)))
        assert taken == datetime(2026, 10, 17, 10, 30), kind
        assert coords == pytest.approx((34.0, -118.0), abs=1e-2), kind


def test_a_photo_with_no_exif_has_no_time_or_position():
    assert exif_of(image("jpeg")) == (None, None) and exif_of(image("png")) == (None, None)


def test_the_taken_time_is_the_trips_clock_and_falls_back_to_the_upload_time(trip, ari):
    p = photos.add(ari, image("jpeg", taken=STROLL))
    assert p["taken_at"].startswith("2026-10-17T10:30:00-07:00") and p["taken_date"] == "2026-10-17" and p["taken_min"] == 10 * 60 + 30
    p = photos.add(ari, image("jpeg"), now=datetime(2026, 10, 18, 3, 15, tzinfo=UTC))   # 8:15 PM on Oct 17 in Los Angeles
    assert p["taken_date"] == "2026-10-17" and p["taken_min"] == 20 * 60 + 15
    p = photos.add(ari, image("jpeg", taken="2026:10:17 12:30:00", offset="-04:00"))      # taken in New York: 9:30 AM trip time
    assert p["taken_min"] == 9 * 60 + 30


def test_the_position_is_kept_in_the_database_but_never_in_the_files_served(trip, ari):
    p = photos.add(ari, image("jpeg", taken=STROLL, gps=(34.0522, -118.2437)))
    assert p["lat"] == pytest.approx(34.0522, abs=1e-3) and p["lon"] == pytest.approx(-118.2437, abs=1e-3)
    assert "lat" not in photos.listing(ari)[0]
    for size in photos.SIZES:
        copy = Image.open(photos.file_path(p, size))
        assert dict(copy.getexif()) == {} and copy.getexif().get_ifd(0x8825) == {} and "exif" not in copy.info
        assert b"Exif" not in photos.file_path(p, size).read_bytes()[:64]
    assert dict(Image.open(photos.root() / p["orig"]).getexif().get_ifd(0x8825))   # the original, never served, keeps the camera's own data


def test_the_copies_are_resized_and_upright(trip, ari):
    big = Image.new("RGB", (3000, 2000), (10, 120, 200))
    buf = io.BytesIO()
    e = Image.Exif()
    e[0x0112] = 6                      # rotated: shown turned 90 degrees
    big.save(buf, "JPEG", exif=e)
    p = photos.add(ari, buf.getvalue())
    disp, thumb = Image.open(photos.file_path(p, "display")), Image.open(photos.file_path(p, "thumb"))
    assert max(disp.size) == photos.DISPLAY_EDGE and disp.size[0] < disp.size[1]       # upright: taller than wide
    assert max(thumb.size) == photos.THUMB_EDGE


# ---- matching to the plan --------------------------------------------------------------------------------------------------

def test_a_photo_lands_on_the_plan_it_was_taken_during(trip, ari):
    assert photos.add(ari, image("jpeg", taken=STROLL))["plan_title"] == "Venice Canals stroll"
    assert photos.add(ari, image("jpeg", taken="2026:10:17 10:00:00"))["plan_title"] == "Venice Canals stroll"      # the start counts
    assert photos.add(ari, image("jpeg", taken="2026:10:17 11:30:00"))["plan_title"] == ""                            # the end does not
    assert photos.add(ari, image("jpeg", taken="2026:10:18 10:30:00"))["plan_title"] == ""                            # another day


def test_a_photo_outside_every_window_goes_to_the_nearest_plan_by_place(trip, ari, monkeypatch):
    places = {"Venice Canals stroll, Los Angeles": (33.9850, -118.4695), "Lunch, Los Angeles": (34.1016, -118.3267)}
    monkeypatch.setattr(tripday, "cached_coords", lambda place: places.get(place))
    add(trip, id="a2", title="Lunch", start="13:00", end="14:00", day="1")
    near_lunch = image("jpeg", taken="2026:10:17 16:00:00", gps=(34.1020, -118.3270))
    assert photos.add(ari, near_lunch)["plan_title"] == "Lunch"
    far_away = image("jpeg", taken="2026:10:17 16:00:00", gps=(36.0, -115.0))
    assert photos.add(ari, far_away)["plan_title"] == ""                                       # nothing within a few kilometres
    no_position = image("jpeg", taken="2026:10:17 16:00:00")
    assert photos.add(ari, no_position)["plan_title"] == ""


def test_without_a_geo_cache_a_photo_with_a_position_belongs_to_the_day(trip, ari, monkeypatch):
    monkeypatch.setattr(tripday, "cached_coords", lambda place: None)
    assert photos.add(ari, image("jpeg", taken="2026:10:17 16:00:00", gps=(34.0, -118.0)))["plan_title"] == ""


def test_match_plan_prefers_the_plan_that_started_last_when_two_overlap():
    from gitaway.tripcal import Activity
    acts = [Activity("a1", 1, 600, 720, "Brunch", "food"), Activity("a2", 1, 660, 780, "Museum", "culture"), Activity("a3", 2, 600, 700, "Hike", "outdoors")]
    assert photos.match_plan(acts, 1, 670) == ("a2", "Museum")
    assert photos.match_plan(acts, 1, 605) == ("a1", "Brunch")
    assert photos.match_plan(acts, 2, 605) == ("a3", "Hike") and photos.match_plan(acts, 3, 605) == ("", "")


def test_a_photo_taken_before_the_trip_belongs_to_no_plan_but_is_kept(trip, ari):
    p = photos.add(ari, image("jpeg", taken="2026:09:01 10:30:00"))
    assert p["plan_title"] == "" and p["taken_date"] == "2026-09-01"


# ---- the files, the table, who sees what -----------------------------------------------------------------------------------

def test_files_are_stored_under_the_data_folder_with_a_random_name(trip, ari):
    p = photos.add(ari, image("jpeg"))
    data_dir = photos.auth.data_dir()
    for key in ("orig", "display", "thumb"):
        path = (photos.root() / p[key]).resolve()
        assert path.is_file() and (data_dir / "photos") in path.parents
        assert not p[key].startswith("/") and ".." not in p[key]
    assert p["id"] in p["orig"] and len(p["id"]) == 32
    other = photos.add(ari, image("jpeg"))
    assert other["id"] != p["id"]


def test_the_file_name_the_browser_sent_never_reaches_the_disk(trip):
    r = upload(trip, ("../../../etc/passwd.jpg", image("jpeg"), "image/jpeg"))
    assert r.status_code == 200
    stored = [p for p in photos.root().rglob("*") if p.is_file()]
    assert stored and all("passwd" not in str(p) and ".." not in p.relative_to(photos.root()).parts for p in stored)


def test_the_photo_is_served_to_the_family_with_private_caching_and_nothing_else(trip, ari):
    pid = upload(trip, jpg(taken=STROLL)).json()["id"]
    for size, edge in (("display", photos.DISPLAY_EDGE), ("thumb", photos.THUMB_EDGE)):
        r = trip.get(f"/trip/photos/{pid}/{size}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
        assert "private" in r.headers["cache-control"] and "public" not in r.headers["cache-control"]
        assert r.headers["x-content-type-options"] == "nosniff"
        assert Image.open(io.BytesIO(r.content)).size[0] <= edge
    assert trip.get(f"/trip/photos/{pid}/orig").status_code == 404           # the original is never served
    assert trip.get(f"/trip/photos/{pid}/../../x").status_code == 404
    assert trip.get("/trip/photos/nothere/thumb").status_code == 404


def test_signed_out_or_another_family_cannot_fetch_a_photo(trip, client):
    from main import app
    from starlette.testclient import TestClient
    pid = upload(trip, jpg()).json()["id"]
    out = TestClient(app, client=("127.0.0.1", 50000))
    for url in (f"/trip/photos/{pid}/thumb", f"/trip/photos/{pid}/display", f"/trip/photos/{pid}"):
        assert out.get(url, follow_redirects=False).status_code in (303, 401), url
    stranger = TestClient(app, client=("127.0.0.1", 50000))
    book(stranger, "sam")
    for url in (f"/trip/photos/{pid}/thumb", f"/trip/photos/{pid}/display", f"/trip/photos/{pid}"):
        assert stranger.get(url).status_code == 404, url
    assert photos.get(person("sam"), pid) is None
    assert stranger.post("/trip/photos/remove", data={"id": pid}, follow_redirects=False).status_code == 404
    assert photos.get(person("ari"), pid)                                           # still there


def test_a_photo_cannot_be_read_by_guessing_a_path(trip):
    pid = upload(trip, jpg()).json()["id"]
    for guess in (f"/photos/{pid}.jpg", f"/assets/photos/{pid}.jpg", f"/data/photos/{pid}-display.jpg", "/photos/"):
        assert trip.get(guess).status_code == 404, guess


# ---- the thread ------------------------------------------------------------------------------------------------------------

def test_an_added_photo_posts_a_card_to_the_thread_and_removing_it_takes_the_card_away(trip, ari):
    pid = upload(trip, jpg(taken=STROLL), caption="  Canals!  ").json()["id"]
    [card] = [i for i in ft.items(ari) if i["kind"] == "photo"]
    assert card["payload"]["url"] == f"/trip/photos/{pid}/thumb" and card["text"] == "Canals!" and card["name"] == "Ari"
    assert trip.post("/trip/photos/remove", data={"id": pid}, follow_redirects=False).status_code in (200, 303)
    assert [i for i in ft.items(ari) if i["kind"] == "photo"] == []
    assert photos.get(ari, pid) is None and trip.get(f"/trip/photos/{pid}/thumb").status_code == 404


def test_the_card_without_a_caption_says_which_plan(trip, ari):
    upload(trip, jpg(taken=STROLL))
    [card] = [i for i in ft.items(ari) if i["kind"] == "photo"]
    assert card["text"] == "At Venice Canals stroll"


def test_removing_a_photo_deletes_its_files(trip, ari):
    p = photos.add(ari, image("jpeg"))
    paths = [photos.root() / p[k] for k in ("orig", "display", "thumb")]
    assert all(x.is_file() for x in paths)
    assert photos.remove(ari, p["id"], "admin") is True
    assert not any(x.exists() for x in paths) and photos.get(ari, p["id"]) is None
    assert photos.remove(ari, p["id"], "admin") is False


# ---- roles -----------------------------------------------------------------------------------------------------------------

@pytest.fixture
def crew(trip):
    """Ari (admin), an editor and a viewer, each in their own browser, all in Ari's family."""
    ed_mail, vi_mail = addr("ed"), addr("vi")
    invite(trip, ed_mail, "editor"), invite(trip, vi_mail, "viewer")
    ed, vi = browser(trip), browser(trip)
    sign_in(ed, ed_mail), sign_in(vi, vi_mail)
    return trip, ed, vi


def test_a_viewer_can_add_a_photo_and_everyone_in_the_family_sees_it(crew):
    ari, ed, vi = crew
    pid = upload(vi, jpg(taken=STROLL)).json()["id"]
    for who in (ari, ed, vi):
        assert who.get(f"/trip/photos/{pid}/thumb").status_code == 200
    assert photos.listing(person("ari"))[0]["author"] == photos.get(person("ari"), pid)["author"]


def test_who_can_remove_a_photo(crew):
    ari, ed, vi = crew
    mine, theirs = upload(ed, jpg()).json()["id"], upload(vi, jpg()).json()["id"]
    assert ed.post("/trip/photos/remove", data={"id": theirs}, follow_redirects=False).status_code == 403     # an editor cannot remove a viewer's
    assert vi.post("/trip/photos/remove", data={"id": mine}, follow_redirects=False).status_code == 403
    assert ari.get(f"/trip/photos/{theirs}/thumb").status_code == 200 and ed.get(f"/trip/photos/{mine}/thumb").status_code == 200
    assert vi.post("/trip/photos/remove", data={"id": theirs}, follow_redirects=False).status_code in (200, 303)   # the author can, a viewer too
    assert ari.post("/trip/photos/remove", data={"id": mine}, follow_redirects=False).status_code in (200, 303)    # an admin can remove anyone's
    assert ari.get(f"/trip/photos/{mine}/thumb").status_code == 404 and ari.get(f"/trip/photos/{theirs}/thumb").status_code == 404
    assert upload(ed, jpg()).status_code == 200


def test_signed_out_cannot_add_or_remove(client):
    assert upload(client, jpg()).status_code in (303, 401, 403)
    assert client.post("/trip/photos/remove", data={"id": "a" * 32}, follow_redirects=False).status_code in (303, 401, 403)
    assert photos.root().exists() is False or not any(p.is_file() for p in photos.root().rglob("*"))



# ---- the screens -----------------------------------------------------------------------------------------------------------

def tag(html, id_):
    import re
    return re.search(rf"<[^>]*\bid=\"{id_}\"[^>]*>", html).group(0)


def test_the_family_tab_has_the_chat_photos_switch_and_a_camera_button(trip):
    html = trip.get("/trip/family").text
    assert 'id="fam-chat"' in html and 'id="fam-photos"' in html and 'href="/trip/family?view=photos"' in html
    assert 'aria-current="true"' in tag(html, "fam-chat") and 'aria-current="false"' in tag(html, "fam-photos")
    cam = tag(html, "ph-camera")
    assert 'type="file"' in cam and 'capture="environment"' in cam and "multiple" in cam and "image/jpeg" in cam and "image/heic" in cam
    assert 'capture' not in tag(html, "ph-library") and "multiple" in tag(html, "ph-library")
    assert 'id="ft-camera"' in html and 'data-pick="camera"' in html and "Take a photo" in html


def test_the_photos_view_is_empty_until_a_photo_is_added(trip):
    html = trip.get("/trip/family?view=photos").text
    assert "No photos yet" in html and 'aria-current="true"' in tag(html, "fam-photos")
    assert 'hidden' in tag(html, "ft-chat") and 'hidden' not in tag(html, "fp")


def test_photos_show_in_a_strip_per_day_with_the_latest_pinned_to_its_plan(trip):
    import re
    for taken in ("2026:10:17 09:05:00", STROLL, "2026:10:18 16:20:00"):
        upload(trip, jpg(taken=taken))
    html = trip.get("/trip/family?view=photos").text
    assert html.count('class="fp-day"') == 2 and "SATURDAY, OCT 17" in html and "SUNDAY, OCT 18" in html and "3 photos" in html
    assert re.findall(r'class="fp-time">([^<]+)<', html) == ["9:05 AM", "10:30 AM", "4:20 PM"]       # time labels, in order, day by day
    assert "Not during a plan" in html and "On Sunday, Oct 18" in html and "Oct 18 · 4:20 PM" in html                               # the latest (Sun 4:20 PM) is on no plan


def test_the_polaroid_names_the_plan_and_counts_the_photos_on_it(trip):
    upload(trip, jpg(taken=STROLL))
    upload(trip, jpg(taken="2026:10:17 11:00:00"))
    html = trip.get("/trip/family?view=photos").text
    assert "Pinned to Venice Canals stroll" in html and "2 photos on this stop" in html and "Venice Canals stroll · 11:00 AM" in html


def test_the_thread_shows_the_photo_card(trip):
    pid = upload(trip, jpg(taken=STROLL)).json()["id"]
    html = trip.get("/trip/family").text
    assert f'src="/trip/photos/{pid}/thumb"' in html and 'data-kind="photo"' in html


def test_the_photo_page_shows_it_and_remove_leads_back_to_the_photos(trip):
    pid = upload(trip, jpg(taken=STROLL)).json()["id"]
    page = trip.get(f"/trip/photos/{pid}")
    assert page.status_code == 200 and f'/trip/photos/{pid}/display' in page.text and "Pinned to Venice Canals stroll" in page.text
    assert 'id="fp-remove"' in page.text and 'href="/trip/family?view=photos"' in page.text
    r = trip.post("/trip/photos/remove", data={"id": pid}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/family?view=photos"
    assert trip.get(f"/trip/photos/{pid}").status_code == 404
    assert "No photos yet" in trip.get("/trip/family?view=photos").text


def test_the_photo_page_offers_remove_only_to_the_author_or_an_admin(crew):
    ari, ed, vi = crew
    pid = upload(ed, jpg()).json()["id"]
    assert 'id="fp-remove"' in ed.get(f"/trip/photos/{pid}").text and 'id="fp-remove"' in ari.get(f"/trip/photos/{pid}").text
    page = vi.get(f"/trip/photos/{pid}").text
    assert 'id="fp-remove"' not in page and "Only the person who added" in page


def test_an_upload_from_a_plain_form_goes_back_to_the_photos_and_shows_the_problem(trip):
    r = upload(trip, jpg(), fragment=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/family?view=photos"
    r = upload(trip, ("x.txt", b"hello", "text/plain"), fragment=False)
    assert r.status_code == 303 and "error=" in r.headers["location"]
    assert "Only JPEG" in trip.get(r.headers["location"]).text
    assert trip.post("/trip/photos", data={}, headers={"X-Fragment": "1"}, follow_redirects=False).status_code == 400


def test_several_photos_in_one_upload_are_all_kept_and_a_bad_one_does_not_stop_the_others(trip):
    r = upload(trip, jpg(taken=STROLL), ("bad.jpg", b"%PDF", "image/jpeg"), jpg(taken="2026:10:17 11:00:00"))
    assert r.status_code == 200 and len(r.json()["ids"]) == 2 and len(r.json()["errors"]) == 1
    assert len(photos.listing(person("ari"))) == 2
