"""F-259: a creator's edit stays in the v2 look (D-680..). Every way a creator can reach "edit the details" from the v2 pages lands on one editor drawn in the book's language
(layout.page(v2="cv"), cv2.css + cvedit.css), and every write still goes through creatordraft.apply (the one write path, its checks and the owner gate). The post is the recorded
"48 Hours in Lisbon" (tests/fixtures/creator_import); nothing reaches the network or a model."""
import re
from html import unescape

from gitaway import creatordraft
from tests.creator_import_support import as_post, form_of
from tests.test_creator_book import lisbon, made, post, stranger, words  # noqa: F401  (the fixtures)
from tests.test_signin import sign_in, tid


def editor(client, d):
    return client.get(f"/creators/import/{d['id']}").text


def posted(client, d, do, **edits):
    """What the editor's form posts, with `do` pressed, and the given fields changed (all copies)."""
    html = editor(client, d)
    fields = form_of(html, f"/creators/import/{d['id']}", "ci-edit")
    fields = [(k, v) for k, v in fields if k not in edits] + [(k, v) for k, v in edits.items()]
    return client.post(f"/creators/import/{d['id']}", data=as_post([*fields, ("do", do)]), follow_redirects=False)


def names(d, day=0):
    return [s["name"] for s in creatordraft.get(tid(), d["id"])["days"][day]["stops"]]


def test_the_editor_is_a_page_in_the_guides_language_not_the_old_form(made):
    client, d = made
    html = editor(client, d)
    assert 'class="ga-page v2 cv' in html and "/assets/css/cvedit.css" in html and "/assets/css/cv2.css" in html
    assert "scrapbook.css" not in html and "creatorimport.css" not in html          # the old form's stylesheets are gone from this page
    assert f'href="/creators/import/{d["id"]}/guide"' in html and "Back to the postcard" in words(html)
    fields = dict(form_of(html, f"/creators/import/{d['id']}", "ci-edit"))
    assert fields["title"] == creatordraft.get(tid(), d["id"])["title"] == "48 hours in Lisbon"
    assert fields["d0s0_name"] == "Belem Tower" and fields["d0s3_name"] == "Pastéis de Belém"      # each stop, in the post's order


def test_every_stop_has_its_move_and_remove_buttons_at_phone_size_labels(made):
    client, d = made
    html = editor(client, d)
    for do in ("up_stop:0:1", "down_stop:0:0", "del_stop:0:0"):
        assert f'value="{do}"' in html
    assert 'value="up_stop:0:0"' not in html and 'value="down_stop:0:6"' not in html        # the first cannot go up, the last cannot go down
    assert 'aria-label="Move Belem Tower down"' in unescape(html)


def test_moving_a_stop_down_then_up_reorders_it_through_the_same_write_path(made):
    client, d = made
    before = names(d)
    assert posted(client, d, "down_stop:0:0").status_code == 303
    assert names(d)[:3] == [before[1], before[0], before[2]]
    assert posted(client, d, "up_stop:0:1").status_code == 303
    assert names(d) == before


def test_deleting_a_stop_and_editing_the_details_are_saved(made):
    client, d = made
    before = names(d)
    posted(client, d, "del_stop:0:2")
    assert names(d) == before[:2] + before[3:]
    posted(client, d, "save", title="Lisbon in two days", name="Sam", d0_title="Belém morning", d0s0_time="9:00 AM", d0s0_note="Go early")
    stored = creatordraft.get(tid(), d["id"])
    day = stored["days"][0]
    assert (stored["title"], stored["name"], day["title"]) == ("Lisbon in two days", "Sam", "Belém morning")
    assert (day["stops"][0]["time"], day["stops"][0]["note"]) == ("9:00 AM", "Go early")


def test_the_save_and_open_the_guide_button_saves_then_shows_the_guide(made):
    client, d = made
    r = posted(client, d, "book", title="A new title")
    assert r.status_code == 303 and r.headers["location"] == f"/creators/import/{d['id']}/guide"
    assert "A new title" in words(client.get(r.headers["location"]).text)


def test_a_refused_write_shows_its_sentence_in_the_v2_editor_and_changes_nothing(made):
    client, d = made
    r = posted(client, d, "save", title="Write me at someone@example.com")
    html = r.text
    assert r.status_code == 200 and 'role="alert"' in html and 'class="ga-page v2 cv' in html
    assert creatordraft.get(tid(), d["id"])["title"] != "Write me at someone@example.com"


def test_the_book_links_to_the_details_editor(made):
    client, d = made
    html = client.get(f"/creators/import/{d['id']}/book").text
    assert re.search(rf'<a[^>]+href="/creators/import/{d["id"]}"[^>]*>', html) and "Edit details" in words(html)


def test_my_drafts_opens_the_guide_and_offers_the_details(made):
    client, d = made
    html = client.get("/creators/drafts").text
    assert f'href="/creators/import/{d["id"]}/guide"' in html and f'href="/creators/import/{d["id"]}"' in html and "Details" in words(html)


def test_a_publish_that_is_refused_says_what_to_fix_and_links_the_editor(made):
    client, d = made
    r = client.post(f"/creators/import/{d['id']}", data={"do": "publish"}, headers={"X-Book": "1"})
    assert r.status_code == 422 or r.status_code == 409
    assert r.json()["editor"] == f"/creators/import/{d['id']}"


def test_only_the_owner_can_open_or_write_the_editor(made):
    client, d = made
    other = stranger(client)
    sign_in(other, "sam")
    assert other.get(f"/creators/import/{d['id']}", follow_redirects=False).status_code == 404
    assert other.post(f"/creators/import/{d['id']}", data={"do": "down_stop:0:0"}, follow_redirects=False).status_code == 404
    assert names(d)[0] == "Belem Tower"
    signed_out = stranger(client)
    r = signed_out.get(f"/creators/import/{d['id']}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin")
    r = signed_out.post(f"/creators/import/{d['id']}", data={"do": "down_stop:0:0"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin") and names(d)[0] == "Belem Tower"
