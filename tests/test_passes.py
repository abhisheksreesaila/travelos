"""F-083: passes & documents. Flights an editor adds (the captain's trip has none imported), per-traveller seat, group, gate, boarding time and the pass file,
what files are accepted, who can see and change them, the family thread card, the Help section, Today's flight card and the gate view. Files are generated here."""

import io
import re
from datetime import datetime, timezone
from html import unescape

import pytest
from pypdf import PdfWriter

from gitaway import catalog, familythread as ft, passes
from tests.photo_files import image
from tests.test_calendar import book
from tests.test_members import addr, browser, invite
from tests.test_signin import person, sign_in
from tests.test_trip_import import TEMPLATE, imported

FLIGHT = {"airline": "United", "number": "1234", "from_code": "lax", "to_code": "SFO", "fly_on": "2026-10-17", "time": "14:25", "terminal": "7"}


def pdf(pages=1):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=300, height=500)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def text(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def add_flight(client, **over):
    return client.post("/trip/help/flight", data={**FLIGHT, **over}, follow_redirects=False)


def keys(session):
    return [f["key"] for f in passes.flights(session)]


def add_pass(client, flight, name="Abhi", file=None, **over):
    files = {"file": file} if file else None
    data = {"flight": flight, "traveller": name, "seat": "21a", "grp": "3", "gate": "71b", "boards": "13:40", **over}
    return client.post("/trip/help/pass", data=data, files=files or {"file": ("", b"", "application/octet-stream")}, follow_redirects=False)


@pytest.fixture
def trip(client):
    """Ari with the sample trip (no imported flights) and one flight added by hand: UA 1234 LAX → SFO, Sat Oct 17, 2:25 PM."""
    book(client)
    assert add_flight(client).status_code == 303
    return client


@pytest.fixture
def ari():
    return person("ari")


@pytest.fixture
def key(ari, trip):
    return keys(ari)[0]


@pytest.fixture
def crew(trip):
    ed_mail, vi_mail = addr("ed"), addr("vi")
    invite(trip, ed_mail, "editor"), invite(trip, vi_mail, "viewer")
    ed, vi = browser(trip), browser(trip)
    sign_in(ed, ed_mail), sign_in(vi, vi_mail)
    return trip, ed, vi


# ---- flights --------------------------------------------------------------------------------------------------------------

def test_an_editor_adds_a_flight_and_it_is_listed_by_when_it_leaves(trip, ari):
    [f] = passes.flights(ari)
    assert (f["name"], f["origin"], f["dest"], f["terminal"], f["source"]) == ("United 1234", "LAX", "SFO", "7", "added")
    assert f["date"].isoformat() == "2026-10-17" and f["depart_min"] == 14 * 60 + 25
    add_flight(trip, number="88", fly_on="2026-10-16")
    assert [x["name"] for x in passes.flights(ari)] == ["United 88", "United 1234"]


@pytest.mark.parametrize("bad, err", [({"airline": ""}, "flight_name"), ({"number": "12 34 5678"}, "flight_name"), ({"from_code": "LA"}, "flight_route"), ({"to_code": "lax"}, "flight_route"),
                                      ({"fly_on": "tomorrow"}, "flight_date"), ({"time": ""}, "flight_time")])
def test_a_flight_that_is_not_filled_in_is_refused_with_a_sentence(trip, ari, bad, err):
    r = add_flight(trip, **bad)
    assert r.status_code == 303 and r.headers["location"].startswith(f"/trip/help?err={err}")
    assert len(passes.flights(ari)) == 1
    assert passes.ERRORS[err] in text(trip.get(r.headers["location"]).text)


def test_the_error_comes_from_a_fixed_list_so_a_link_cannot_write_on_the_page(trip):
    html = trip.get("/trip/help?err=Call+this+number+now").text
    assert "Call this number now" not in html and 'id="pz-problem"' not in html


def test_a_flight_can_be_fixed_and_removed_with_its_passes(trip, ari, key):
    add_pass(trip, key, file=("p.pdf", pdf(), "application/pdf"))
    fid = passes.flights(ari)[0]["id"]
    assert add_flight(trip, flight_id=fid, time="15:10", terminal="").status_code == 303
    assert passes.flights(ari)[0]["depart_min"] == 15 * 60 + 10 and len(passes.flights(ari)) == 1
    folder = passes.root()
    assert any(folder.rglob("*.pdf"))
    r = trip.post("/trip/help/flight/remove", data={"flight_id": fid}, follow_redirects=False)
    assert r.status_code == 303 and passes.flights(ari) == [] and passes.listing(ari) == {}
    assert not any(folder.rglob("*.*"))


def test_a_flight_of_an_imported_trip_is_read_from_the_template(client):
    imported(client, TEMPLATE)
    ari = person("ari")
    legs = passes.flights(ari)
    assert legs and all(f["source"] == "import" and f["key"].startswith("leg:") for f in legs)
    assert add_pass(client, legs[0]["key"], "Ari").status_code == 303
    assert passes.listing(ari)[legs[0]["key"]][0]["traveller"] == "Ari"


# ---- passes and their files ------------------------------------------------------------------------------------------------

def test_a_pass_keeps_seat_group_gate_and_boarding_time_and_names_the_member(trip, ari, key):
    r = add_pass(trip, key, "ari rivera")
    assert r.status_code == 303 and r.headers["location"].startswith("/trip/help") and "err=" not in r.headers["location"]
    [p] = passes.listing(ari)[key]
    assert (p["seat"], p["grp"], p["gate"], p["boards_min"], p["kind"]) == ("21A", "3", "71B", 13 * 60 + 40, "")
    assert p["traveller"] == "ari rivera"


def test_a_pdf_is_kept_and_its_first_page_is_drawn_for_the_gate(trip, ari, key):
    add_pass(trip, key, file=("whatever.txt", pdf(), "text/plain"))   # the name and claimed type are not trusted
    [p] = passes.listing(ari)[key]
    assert p["kind"] == "pdf" and p["orig"].endswith(".pdf")
    r = trip.get(f"/trip/passes/{p['id']}/file")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:5] == b"%PDF-"
    for size in ("display", "thumb"):
        r = trip.get(f"/trip/passes/{p['id']}/{size}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:3] == b"\xff\xd8\xff"


@pytest.mark.parametrize("kind", ["jpeg", "png", "webp", "heic"])
def test_a_picture_is_kept_and_shown_as_a_jpeg(trip, ari, key, kind):
    add_pass(trip, key, file=("pass", image(kind, size=(300, 500)), "application/octet-stream"))
    [p] = passes.listing(ari)[key]
    assert p["kind"] == "image"
    shown = trip.get(f"/trip/passes/{p['id']}/display")
    assert shown.status_code == 200 and shown.content[:3] == b"\xff\xd8\xff"   # HEIC is converted
    assert trip.get(f"/trip/passes/{p['id']}/file").status_code == 404          # only a PDF has a file of its own


@pytest.mark.parametrize("name, data, err", [
    ("a.pdf", b"%PDF-1.4 this is not really a pdf", "open"),
    ("a.jpg", b"GIF89a\x01\x00", "type"),
    ("a.pdf", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "type"),
    ("a.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 200, "open"),
    ("a.pdf", b"%PDF-" + b"0" * (passes.MAX_BYTES + 1), "big"),
])
def test_a_file_that_is_not_a_pass_is_refused_and_nothing_is_kept(trip, ari, key, name, data, err):
    r = add_pass(trip, key, file=(name, data, "application/pdf"))
    assert r.status_code in (303, 413) and (err in r.headers.get("location", "") or r.status_code == 413)
    assert passes.listing(ari) == {} and not any(passes.root().rglob("*.*"))


def test_an_upload_over_the_limit_is_refused_before_it_is_read(trip, key):
    r = trip.post("/trip/help/pass", data={"flight": key, "traveller": "A"}, files={"file": ("big.pdf", b"%PDF-" + b"0" * (passes.MAX_BYTES + 200_000), "application/pdf")}, follow_redirects=False)
    assert r.status_code == 413 and "too large" in r.text


def test_the_airline_link_is_only_kept_when_pasted_and_only_https(trip, ari, key):
    assert "err=url" in add_pass(trip, key, app_url="javascript:alert(1)").headers["location"]
    assert "err=url" in add_pass(trip, key, app_url="http://x.example.com/a").headers["location"]
    assert passes.listing(ari) == {}
    add_pass(trip, key, "With", app_url="https://www.united.com/app")
    add_pass(trip, key, "Without")
    html = trip.get("/trip/help").text
    assert html.count("Open in airline app") == 1 and 'href="https://www.united.com/app"' in html
    assert "noopener" in re.search(r'<a[^>]*data-app=[^>]*>', html).group(0)


def test_a_pass_can_be_fixed_and_a_new_file_replaces_the_old_one(trip, ari, key):
    add_pass(trip, key, file=("a.pdf", pdf(), "application/pdf"))
    [p] = passes.listing(ari)[key]
    old = sorted(passes.root().rglob("*.*"))
    r = add_pass(trip, key, "Abhi", pass_id=p["id"], seat="22C", file=("b.png", image("png", size=(200, 300)), "image/png"))
    assert r.status_code == 303 and "err=" not in r.headers["location"]
    [q] = passes.listing(ari)[key]
    assert (q["id"], q["seat"], q["kind"]) == (p["id"], "22C", "image")
    now = sorted(passes.root().rglob("*.*"))
    assert not set(old) & set(now) and len(now) == 3   # the old files are gone; original, display and thumbnail of the new one
    add_pass(trip, key, "Abhi", pass_id=p["id"], seat="22D")   # no file picked: the file stays
    assert passes.listing(ari)[key][0]["kind"] == "image" and passes.listing(ari)[key][0]["seat"] == "22D"


def test_a_pass_is_removed_with_its_files(trip, ari, key):
    add_pass(trip, key, file=("a.pdf", pdf(), "application/pdf"))
    [p] = passes.listing(ari)[key]
    assert trip.post("/trip/help/pass/remove", data={"pass_id": p["id"]}, follow_redirects=False).status_code == 303
    assert passes.listing(ari) == {} and not any(passes.root().rglob("*.*"))
    assert trip.get(f"/trip/passes/{p['id']}/display").status_code == 404
    assert "err=pass_missing" in trip.post("/trip/help/pass/remove", data={"pass_id": p["id"]}, follow_redirects=False).headers["location"]


# ---- who sees it ---------------------------------------------------------------------------------------------------------

def test_files_are_private_to_the_family_and_revalidated(trip, ari, key):
    add_pass(trip, key, file=("a.pdf", pdf(), "application/pdf"))
    [p] = passes.listing(ari)[key]
    url = f"/trip/passes/{p['id']}/display"
    r = trip.get(url)
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-cache" and r.headers["x-content-type-options"] == "nosniff"
    assert trip.get(url, headers={"If-None-Match": r.headers["etag"]}).status_code == 304
    other = browser(trip)
    sign_in(other, addr("outsider"))
    assert other.get(url).status_code == 404 and other.get(f"/trip/passes/{p['id']}/file").status_code == 404   # another family: not found
    assert "United 1234" not in other.get("/trip/help").text
    trip.cookies.clear()
    assert trip.get(url, follow_redirects=False).status_code in (303, 401)
    assert not str(passes.root()).startswith(str(passes.root().parents[0] / "assets"))


def test_a_bad_id_or_size_is_not_found(trip, key):
    add_pass(trip, key, file=("a.pdf", pdf(), "application/pdf"))
    for url in ("/trip/passes/zzz/display", "/trip/passes/" + "0" * 32 + "/display", "/trip/passes/../../etc/passwd/display"):
        assert trip.get(url).status_code == 404


def test_a_viewer_sees_the_passes_but_cannot_change_them(crew, ari, key):
    owner, editor, viewer = crew
    add_pass(owner, key, file=("a.pdf", pdf(), "application/pdf"))
    [p] = passes.listing(ari)[key]
    html = viewer.get("/trip/help").text
    shown = text(html)
    assert "United 1234" in shown and "21A" in shown and "71B" in shown and "1:40 PM" in shown and "Abhi" in shown
    assert "<form" not in html.split('id="hp-passes"')[1] and "Add a pass" not in html and "Add a flight" not in html
    assert viewer.get(f"/trip/passes/{p['id']}/thumb").status_code == 200
    for path, data in (("/trip/help/flight", FLIGHT), ("/trip/help/flight/remove", {"flight_id": passes.flights(ari)[0]["id"]}), ("/trip/help/pass", {"flight": key, "traveller": "X"}),
                       ("/trip/help/pass/remove", {"pass_id": p["id"]})):
        assert viewer.post(path, data=data, follow_redirects=False).status_code == 403, path
    assert len(passes.listing(ari)[key]) == 1 and len(passes.flights(ari)) == 1


def test_an_editor_sees_the_forms_and_can_add(crew, ari, key):
    owner, editor, viewer = crew
    html = editor.get("/trip/help").text.split('id="hp-passes"')[1]
    assert "Add a pass" in html and "Add a flight" in html and 'enctype="multipart/form-data"' in html
    assert add_pass(editor, key, "Editor's pick").status_code == 303 and passes.listing(ari)[key][0]["traveller"] == "Editor's pick"


# ---- Help --------------------------------------------------------------------------------------------------------------

def test_help_shows_a_card_per_traveller_with_a_thumbnail_that_opens_the_gate(trip, ari, key):
    add_pass(trip, key, "Abhi", file=("a.pdf", pdf(), "application/pdf"))
    add_pass(trip, key, "Kay", seat="21B", file=("b.png", image("png", size=(200, 300)), "image/png"))
    add_pass(trip, key, "Bhoomija", seat="21C")
    html = trip.get("/trip/help").text
    sec = html.split('id="hp-passes"')[1]
    assert "Passes &amp; documents" in html and "Only your family sees these." in text(sec)
    cards = re.findall(r'<div[^>]*data-pass="([0-9a-f]{32})"', sec)
    assert len(cards) == 3
    assert "United 1234 · LAX → SFO" in text(sec) and "Sat Oct 17" in text(sec) and "2:25 PM" in text(sec) and "Terminal 7" in text(sec)
    assert 'src="/trip/passes/%s/thumb"' % cards[0] in sec and "No boarding pass attached yet" in text(sec)
    link = re.search(r'<a[^>]*data-open-gate="%s"[^>]*>' % cards[0], sec).group(0)
    assert f"/trip/passes/gate?flight={key.replace(':', '%3A')}#gp-{cards[0]}" in unescape(link) or f"flight={key}" in unescape(link)
    assert "Open in airline app" not in html


def test_help_without_a_flight_says_so_and_offers_to_add_one(trip, ari, key):
    trip.post("/trip/help/flight/remove", data={"flight_id": passes.flights(ari)[0]["id"]})
    html = trip.get("/trip/help").text
    assert 'id="pz-none"' in html and "Add a flight" in html


# ---- the family hears about it ---------------------------------------------------------------------------------------------

def test_adding_a_flight_and_passes_puts_cards_in_the_thread_without_seat_numbers(trip, ari, key):
    add_pass(trip, key, "Abhi", file=("a.pdf", pdf(), "application/pdf"))
    add_pass(trip, key, "Kay")
    cards = [i["text"] for i in ft.items(ari) if i["kind"] == "change"]
    assert any("added the flight United 1234 LAX → SFO" in c for c in cards)
    assert any("Abhi's boarding pass for United 1234" in c for c in cards) and any("Kay's seat details for United 1234" in c for c in cards)
    assert not any("21A" in c or "71B" in c for c in cards)


def test_a_refused_pass_leaves_no_card(trip, ari, key):
    before = len(ft.items(ari))
    add_pass(trip, key, "Abhi", file=("a.pdf", b"%PDF-1.4 junk", "application/pdf"))
    assert len(ft.items(ari)) == before


# ---- Today on the travel day -----------------------------------------------------------------------------------------------

@pytest.fixture
def clock(monkeypatch):
    """Pin the instant: clock(10, 17, 12, 58) is Oct 17, 12:58 PM in Los Angeles."""
    def pin(month, day, hour, minute):
        utc = datetime(2026, month, day, hour + 7, minute, tzinfo=timezone.utc)
        monkeypatch.setattr(catalog, "now_utc", lambda: utc)
        monkeypatch.setattr(catalog, "today", lambda: utc.astimezone(catalog.TZ).date())   # the suite pins today to Sep 30: undo that here
    return pin


def test_on_the_travel_day_the_flight_is_the_focal_card(trip, ari, key, clock):
    add_pass(trip, key, "Abhi", seat="21A", file=("a.pdf", pdf(), "application/pdf"))
    add_pass(trip, key, "Kay", seat="21B")
    clock(10, 17, 12, 58)
    html = trip.get("/trip").text
    shown = text(html.split('id="tp-up"')[1][:2500])
    assert "BOARDING IN 42 MIN" in shown and "LAX" in shown and "SFO" in shown and "United 1234" in shown and "2:25 PM" in shown and "Terminal 7" in shown
    assert "1:40 PM" in shown and "71B" in shown and "21A, 21B" in shown
    assert "Show everyone's passes" in shown
    href = re.search(r'<a[^>]*id="pz-show-0"[^>]*>', html).group(0)
    assert "/trip/passes/gate?flight=" in unescape(href)
    assert 'class="tp-up pz-up"' in html


def test_the_card_counts_down_to_departure_after_boarding_starts_and_steps_aside_when_it_leaves(trip, ari, key, clock):
    add_pass(trip, key, "Abhi")
    clock(10, 17, 13, 50)
    assert "DEPARTS IN 35 MIN" in trip.get("/trip").text
    clock(10, 17, 14, 30)
    html = trip.get("/trip").text
    assert 'id="pz-show-0"' not in html and "pz-up" not in html


def test_the_card_is_only_on_the_flights_own_day_and_only_while_the_trip_is_on(trip, ari, key, clock):
    add_pass(trip, key, "Abhi")
    clock(10, 18, 9, 0)
    assert "pz-up" not in trip.get("/trip").text
    clock(9, 30, 9, 0)   # before the trip starts: the countdown card stays
    assert "pz-up" not in trip.get("/trip").text


def test_the_card_offers_editors_to_add_passes_and_tells_viewers_there_are_none(crew, ari, key, clock):
    owner, editor, viewer = crew
    clock(10, 17, 12, 58)
    assert "Add the boarding passes" in text(editor.get("/trip").text)
    html = viewer.get("/trip").text
    assert "No passes added yet." in text(html) and "Add the boarding passes" not in html


# ---- the gate view ------------------------------------------------------------------------------------------------------

def test_the_gate_view_has_a_white_slide_per_traveller_with_big_seat_group_and_gate(trip, ari, key):
    add_pass(trip, key, "Abhi", file=("a.pdf", pdf(), "application/pdf"))
    add_pass(trip, key, "Kay", seat="21B", file=("b.png", image("png", size=(200, 300)), "image/png"))
    add_pass(trip, key, "Bhoomija", seat="21C")
    ids = [p["id"] for p in passes.listing(ari)[key]]
    r = trip.get(f"/trip/passes/gate?flight={key}")
    html = r.text
    assert r.status_code == 200 and "Brightness up" in html and 'id="gp-close"' in html and "/assets/js/passes.js" in html
    assert re.findall(r'<div[^>]*\bid="gp-([0-9a-f]{32})"', html) == ids
    for pid in ids[:2]:
        assert f'src="/trip/passes/{pid}/display"' in html
    assert "No boarding pass file added yet" in text(html)
    assert html.count('class="gp-dot"') == 3 and "1 of 3" in text(html)
    big = text(html.split(f'id="gp-{ids[1]}"')[1].split('id="gp-')[0])
    assert "21B" in big and "GROUP 3" in big and "GATE 71B" in big
    assert 'data-dot="2"' in html


def test_a_gate_view_of_a_pdf_that_could_not_be_drawn_opens_the_pdf(trip, ari, key, monkeypatch):
    monkeypatch.setattr(passes, "render_pdf", lambda data: None)
    add_pass(trip, key, "Abhi", file=("a.pdf", pdf(), "application/pdf"))
    [p] = passes.listing(ari)[key]
    assert p["display"] == "" and trip.get(f"/trip/passes/{p['id']}/display").status_code == 404
    html = trip.get(f"/trip/passes/gate?flight={key}").text
    assert f'href="/trip/passes/{p["id"]}/file"' in html and "Open the PDF" in html
    help_html = trip.get("/trip/help").text
    assert "pz-pdf" in help_html and f'/trip/passes/{p["id"]}/thumb' not in help_html


def test_the_gate_view_needs_sign_in_and_a_known_flight_with_passes(trip, key):
    assert trip.get("/trip/passes/gate?flight=f:" + "0" * 32, follow_redirects=False).headers["location"] == "/trip/help"
    assert trip.get(f"/trip/passes/gate?flight={key}", follow_redirects=False).headers["location"] == "/trip/help#hp-passes"   # no passes yet
    trip.cookies.clear()
    assert trip.get(f"/trip/passes/gate?flight={key}", follow_redirects=False).headers["location"].startswith("/signin")


def test_deleting_an_imported_trip_removes_its_pass_files(client):
    imported(client, TEMPLATE)
    ari = person("ari")
    legs = passes.flights(ari)
    add_pass(client, legs[0]["key"], "Ari", file=("a.pdf", pdf(), "application/pdf"))
    assert any(passes.root().rglob("*.pdf"))
    from tests.test_trip_edit import trip_ids
    [trip_id] = trip_ids()
    client.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False)
    assert not any(passes.root().rglob("*.*"))
