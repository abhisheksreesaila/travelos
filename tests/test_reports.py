"""F-185: report a public trip or creator, and the captain's take down and restore. Through the HTTP seam, in both showcase modes."""

import re
from html import unescape

import pytest

from gitaway import community, publish, reports
from gitaway.community import HubError
from gitaway.pages import admin
from tests.live_trips import live_trip
from tests.pagebody import without_bar
from tests.test_signin import sign_in, tid


@pytest.fixture(params=["1", "0"], ids=["showcase", "live"])
def mode(request, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", request.param)
    return request.param


@pytest.fixture
def trip(mode):
    return live_trip()


def stranger(client):
    return client.__class__(client.app, client=("127.0.0.1", 50000))


def send(c, slug, reason="copyright", ip="203.0.113.7", **extra):
    return c.post("/report", data={"kind": "trip", "target": slug, "reason": reason, "note": "", "email": "", "website": "", **extra}, headers={"x-forwarded-for": ip})


def stored():
    return reports.all_reports()


# ---- the form ------------------------------------------------------------------------------------------------------

def test_every_public_trip_and_creator_page_offers_the_report(client, trip):
    row, handle, _ = trip
    page = without_bar(client.get(f"/trips/{row['slug']}").text)
    assert f'href="/report?trip={row["slug"]}"' in page and "Report this trip" in page
    assert f'href="/report?creator={handle}"' in client.get(f"/creators/{handle}").text and "Report this creator" in client.get(f"/creators/{handle}").text


def test_the_form_has_a_reason_list_an_optional_note_and_email_and_a_hidden_trap(client, trip):
    row, _, _ = trip
    html = client.get(f"/report?trip={row['slug']}").text
    assert "Report this trip" in html and "Three easy days in Santa Monica" in html
    assert re.findall(r'<option value="([a-z]*)"', html) == ["", "copyright", "misleading", "private", "offensive", "spam", "other"]
    assert 'name="note"' in html and 'name="email"' in html and 'type="email"' in html
    assert 'aria-hidden="true"' in re.search(r'<div[^>]*rp-bee[^>]*>', html).group(0) and 'name="website"' in html and 'tabindex="-1"' in html


def test_the_form_is_not_there_for_what_is_not_public(client, mode):
    assert client.get("/report?trip=sun-tacos-and-tide-pools").status_code == 404      # a sample trip
    assert client.get("/report?trip=nope-123456").status_code == 404
    assert client.get("/report?creator=nobody").status_code == 404
    assert client.get("/report").status_code == 404


def test_a_draft_trip_that_was_never_published_cannot_be_reported(client, mode):
    assert client.get("/report?trip=three-easy-days-in-santa-monica-a1b2c3").status_code == 404


# ---- sending -------------------------------------------------------------------------------------------------------

def test_a_stranger_can_send_a_report_and_it_is_stored_exactly(client, trip):
    row, _, _ = trip
    r = client.post("/report", data={"kind": "trip", "target": row["slug"], "reason": "copyright", "note": "  These are\x00 my photos\n\nfrom my blog.  ", "email": "Mia@Example.com", "website": ""})
    assert r.status_code == 200 and "Report sent" in r.text and "Thank you. The person who runs GitAway will read this." in r.text
    (rep,) = stored()
    assert (rep["kind"], rep["target"], rep["reason"], rep["note"], rep["email"]) == ("trip", row["slug"], "copyright", "These are my photos from my blog.", "mia@example.com")
    assert community.get(row["slug"]) is not None            # a report hides nothing by itself


def test_a_signed_in_person_reports_too_and_their_id_is_kept_for_the_limit_only(client, trip):
    row, _, _ = trip
    sign_in(client, "sam")
    assert send(client, row["slug"], "spam").status_code == 200
    with community.connect() as db:
        from sqlalchemy import text
        who = db.conn.execute(text("SELECT reporter FROM reports")).scalar()
    assert who == tid("sam") and "reporter" not in stored()[0]


def test_a_creator_can_be_reported(client, trip):
    _, handle, _ = trip
    r = client.post("/report", data={"kind": "creator", "target": handle, "reason": "misleading", "website": ""})
    assert r.status_code == 200 and stored()[0]["kind"] == "creator" and stored()[0]["target"] == handle


@pytest.mark.parametrize("data,message", [
    ({"reason": ""}, "Pick the reason that fits best."),
    ({"reason": "nonsense"}, "Pick the reason that fits best."),
    ({"reason": "spam", "email": "not an email"}, "That email address does not look right. Leave it empty if you would rather not be answered."),
])
def test_a_bad_report_is_sent_back_with_what_to_fix_and_keeps_what_was_typed(client, trip, data, message):
    row, _, _ = trip
    r = client.post("/report", data={"kind": "trip", "target": row["slug"], "note": "keep this words", **data})
    assert r.status_code == 422 and message in unescape(r.text) and "keep this words" in r.text and stored() == []


def test_a_long_note_is_cut_and_a_report_for_nothing_is_refused(client, trip):
    row, _, _ = trip
    send(client, row["slug"], note="x" * 900)
    assert len(stored()[0]["note"]) == 500
    r = client.post("/report", data={"kind": "trip", "target": "nope-123456", "reason": "spam"})
    assert r.status_code == 404 and len(stored()) == 1


def test_the_note_is_shown_as_text_never_as_markup_on_the_admin_page(client, trip, monkeypatch):
    row, _, _ = trip
    send(client, row["slug"], note="<script>alert(1)</script>")
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "cap@example.com")
    sign_in(client, "cap@example.com")
    html = client.get("/admin").text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html


# ---- the trap, the limits, the origin -------------------------------------------------------------------------------

def test_a_filled_in_trap_is_thanked_and_forgotten(client, trip):
    row, _, _ = trip
    r = send(client, row["slug"], website="https://spam.example")
    assert r.status_code == 200 and "Report sent" in r.text and stored() == []


def test_the_sixth_report_from_one_address_in_an_hour_is_refused(client, trip):
    row, _, _ = trip
    assert [send(client, row["slug"]).status_code for _ in range(5)] == [200] * 5
    r = send(client, row["slug"])
    assert r.status_code == 429 and "That is a lot of reports in an hour. Please try again later." in r.text and len(stored()) == 5
    assert send(client, row["slug"], ip="198.51.100.9").status_code == 200       # another address is another allowance


def test_a_forged_first_forwarded_address_does_not_buy_more_reports(client, trip):
    row, _, _ = trip
    codes = [send(client, row["slug"], ip=f"10.0.0.{i}, 203.0.113.50").status_code for i in range(7)]
    assert codes == [200] * 5 + [429] * 2


def test_one_signed_in_person_has_one_allowance_whatever_address_they_use(client, trip):
    row, _, _ = trip
    sign_in(client, "sam")
    codes = [send(client, row["slug"], ip=f"192.0.2.{i}").status_code for i in range(7)]
    assert codes == [200] * 5 + [429] * 2


def test_everyone_together_have_a_ceiling_too(client, trip, monkeypatch):
    row, _, _ = trip
    monkeypatch.setattr(reports, "ALL_PER_WINDOW", 3)
    assert [send(client, row["slug"], ip=f"192.0.2.{i}").status_code for i in range(5)] == [200] * 3 + [429] * 2


def test_the_ceiling_for_signed_out_reports_does_not_block_a_signed_in_person_and_logs_a_warning(client, trip, monkeypatch, caplog):
    """F-182 L3: twelve addresses could fill the site-wide 60 an hour and so stop every real reporter. The ceiling is for signed-out reports only; it says so in the log."""
    row, _, _ = trip
    monkeypatch.setattr(reports, "ALL_PER_WINDOW", 3)
    with caplog.at_level("WARNING", logger="gitaway.reports"):
        assert [send(client, row["slug"], ip=f"192.0.2.{i}").status_code for i in range(5)] == [200] * 3 + [429] * 2
    assert any("signed-out report ceiling" in r.getMessage() for r in caplog.records) and not any("192.0.2" in r.getMessage() for r in caplog.records)
    sign_in(client, "sam")
    assert send(client, row["slug"], ip="198.51.100.77").status_code == 200       # a signed-in person still gets through


def test_signed_in_reports_do_not_use_up_the_signed_out_ceiling(client, trip, monkeypatch):
    row, _, _ = trip
    monkeypatch.setattr(reports, "ALL_PER_WINDOW", 2)
    sign_in(client, "sam")
    assert [send(client, row["slug"]).status_code for _ in range(3)] == [200] * 3
    out = stranger(client)
    assert [send(out, row["slug"], ip=f"192.0.2.{i}").status_code for i in range(3)] == [200, 200, 429]


def test_the_limit_is_counted_from_the_database_so_a_restart_does_not_reset_it(client, trip):
    row, _, _ = trip
    for _ in range(5):
        send(client, row["slug"])
    community._ready.clear()
    community._engines.clear()             # a new process: nothing in memory
    assert send(client, row["slug"]).status_code == 429


def test_the_address_is_stored_only_as_a_salted_hash(client, trip):
    row, _, _ = trip
    send(client, row["slug"], ip="203.0.113.7")
    with community.connect() as db:
        from sqlalchemy import text
        h = db.conn.execute(text("SELECT ip_hash FROM reports")).scalar()
    assert re.fullmatch(r"[0-9a-f]{16}", h) and "203.0.113.7" not in h and h == reports.ip_hash("203.0.113.7")


def test_a_form_posted_from_another_site_is_refused(client, trip):
    row, _, _ = trip
    r = client.post("/report", data={"kind": "trip", "target": row["slug"], "reason": "spam"}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403 and stored() == []
    r = client.post("/report", data={"kind": "trip", "target": row["slug"], "reason": "spam"}, headers={"sec-fetch-site": "cross-site"})
    assert r.status_code == 403 and stored() == []
    r = client.post("/report", data={"kind": "trip", "target": row["slug"], "reason": "spam"}, headers={"origin": "http://testserver"})
    assert r.status_code == 200 and len(stored()) == 1


# ---- the admin page: who may see it --------------------------------------------------------------------------------

def test_no_one_is_an_admin_until_the_environment_names_them(client, trip, monkeypatch):
    monkeypatch.delenv("GITAWAY_ADMIN_EMAILS", raising=False)
    sign_in(client, "cap@example.com")
    assert client.get("/admin").status_code == 404 and client.post("/admin/takedown", data={"slug": trip[0]["slug"]}).status_code == 404
    assert community.get(trip[0]["slug"]) is not None


def test_the_admin_page_is_404_for_everyone_else_signed_in_or_not(client, trip, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "cap@example.com")
    assert client.get("/admin").status_code == 404                                  # signed out
    sign_in(client, "sam")
    assert client.get("/admin").status_code == 404                                  # signed in, not the captain
    assert client.post("/admin/takedown", data={"slug": trip[0]["slug"]}).status_code == 404
    assert client.post("/admin/restore", data={"slug": trip[0]["slug"]}).status_code == 404
    assert community.is_down(trip[0]["slug"]) is False
    assert "Nothing here" in client.get("/admin").text


def test_the_captain_gets_in_whatever_the_case_or_spacing_of_the_list(client, trip, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", " Other@Example.com ,  CAP@example.com;third@example.com")
    sign_in(client, "cap@example.com")
    assert client.get("/admin").status_code == 200


def test_an_address_that_google_has_not_verified_is_not_the_captain(client, monkeypatch):
    """F-182 M1: the flag is session["verified"] (the "unverified" note exists only when an invitation is waiting), so an unverified address with no invitation was let in."""
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "cap@example.com")
    assert admin.is_admin({"email": "cap@example.com", "verified": 0}) is False
    assert admin.is_admin({"email": "cap@example.com"}) is False
    assert admin.is_admin({"email": "cap@example.com", "verified": 1}) is True
    from gitaway import auth
    real = auth.after_sign_in
    monkeypatch.setattr(auth, "after_sign_in", lambda session, verified=True: real(session, verified=False))
    sign_in(client, "cap@example.com")
    assert client.get("/admin").status_code == 404
    assert client.post("/admin/takedown", data={"slug": "x"}).status_code == 404


def test_the_list_is_read_from_the_environment_never_from_code():
    import inspect
    source = inspect.getsource(admin)
    assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", source) and "GITAWAY_ADMIN_EMAILS" in source


# ---- the admin page: what it shows ---------------------------------------------------------------------------------

@pytest.fixture
def captain(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "cap@example.com")
    sign_in(client, "cap@example.com")
    return client


def numbers(html):
    return {k: unescape(re.search(rf'id="{k}"[^>]*>([^<]*)<', html).group(1)) for k in ("ad-goal", "ad-live", "ad-reports", "ad-commission")}


def test_the_summary_counts_creators_toward_150_live_trips_and_reports(captain, trip):
    row, _, _ = trip
    live_trip("lee@example.com", "Lee Park", "Two days in San Diego")
    send(captain, row["slug"])
    assert numbers(captain.get("/admin").text) == {"ad-goal": "2 of 150", "ad-live": "2", "ad-reports": "1", "ad-commission": "$0"}


def test_reports_are_listed_newest_first_with_reason_note_and_reply_address(captain, trip):
    row, _, _ = trip
    send(captain, row["slug"], "copyright", note="First one", email="a@example.com")
    send(captain, row["slug"], "spam", note="Second one")
    html = captain.get("/admin").text
    assert html.index("Second one") < html.index("First one")
    assert "It uses someone else&#x27;s words or photos" in html or "It uses someone else's words or photos" in unescape(html)
    assert "Reply to: a@example.com" in html and "It is spam or an advertisement" in unescape(html)
    assert f'href="/trips/{row["slug"]}"' in html


def test_each_creator_shows_their_marker_and_clicks_from_their_trips(captain, trip):
    from gitaway import affiliate
    _, handle, owner = trip
    html = captain.get("/admin").text
    assert "no marker: GitAway&#x27;s" in html or "no marker: GitAway's" in unescape(html)
    affiliate.set_marker(owner["user_id"], "555111")
    affiliate.log_click(handle, "aviasales", "flight", True)
    affiliate.log_click(handle, "klook", "stay", False)
    html = unescape(captain.get("/admin").text)
    assert "marker 555111" in html and "2 clicks from their trips, 1 with their marker · bookings: not reported yet" in html


# ---- take down and restore -----------------------------------------------------------------------------------------

def test_take_down_hides_the_trip_everywhere_and_restore_brings_it_back(captain, trip, monkeypatch):
    row, handle, _ = trip
    slug = row["slug"]
    public = stranger(captain)
    assert public.get(f"/trips/{slug}").status_code == 200 and slug in public.get("/community").text and handle in public.get("/creators").text
    r = captain.post("/admin/takedown", data={"slug": slug}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/admin#{slug}"
    assert re.search(rf'<span[^>]*id="state-{slug}"[^>]*>Taken down<', captain.get("/admin").text) or re.search(rf'is-down" id="state-{slug}">Taken down<', captain.get("/admin").text)
    assert public.get(f"/trips/{slug}").status_code == 404
    assert public.get(f"/creators/{handle}").status_code == 404 and handle not in public.get("/creators").text
    assert public.get(f"/report?trip={slug}").status_code == 404
    assert slug not in public.get("/community").text
    assert community.rows(kind="scrapbook") == [] and community.has_real() is False
    r = captain.post("/admin/restore", data={"slug": slug}, follow_redirects=False)
    assert r.status_code == 303
    assert public.get(f"/trips/{slug}").status_code == 200 and slug in public.get("/community").text and handle in public.get("/creators").text


def test_take_down_hides_the_public_photos_too_and_restore_brings_them_back(captain, trip):
    row, _, _ = trip
    slug, name = row["slug"], "0123456789abcdef-display.jpg"
    folder = publish.root() / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(b"\xff\xd8\xff\xe0jpeg")
    public = stranger(captain)
    assert public.get(f"/pub/{slug}/{name}").status_code == 200
    captain.post("/admin/takedown", data={"slug": slug})
    assert public.get(f"/pub/{slug}/{name}").status_code == 404
    assert (folder / name).is_file()                                  # hidden, not deleted: restore needs it
    captain.post("/admin/restore", data={"slug": slug})
    assert public.get(f"/pub/{slug}/{name}").status_code == 200


def test_a_taken_down_page_cannot_be_published_again_by_its_owner(captain, trip):
    row, _, owner = trip
    captain.post("/admin/takedown", data={"slug": row["slug"]})
    with pytest.raises(HubError, match="GitAway took this page down"):
        community.publish(owner, community.trip_of(community.get(row["slug"], hidden=True)), kind="scrapbook")
    assert community.unpublish(owner, row["slug"]) is True and community.get(row["slug"], hidden=True) is None and community.is_down(row["slug"])      # F-182: the owner can delete it; the takedown stays


def test_the_admin_lists_a_down_trip_with_a_restore_button_and_a_live_one_with_take_down(captain, trip):
    row, _, _ = trip
    html = captain.get("/admin").text
    assert 'action="/admin/takedown"' in html and 'action="/admin/restore"' not in html and ">Live<" in html
    captain.post("/admin/takedown", data={"slug": row["slug"]})
    html = captain.get("/admin").text
    assert 'action="/admin/restore"' in html and 'action="/admin/takedown"' not in html and ">Taken down<" in html


def test_a_slug_that_does_not_exist_changes_nothing_and_is_not_put_in_the_address(captain, trip):
    r = captain.post("/admin/takedown", data={"slug": "x\r\nSet-Cookie: a=b"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin" and community.is_down("x") is False


def test_the_admin_buttons_refuse_a_form_from_another_site(captain, trip):
    r = captain.post("/admin/takedown", data={"slug": trip[0]["slug"]}, headers={"origin": "https://evil.example"})
    assert r.status_code == 404 and community.is_down(trip[0]["slug"]) is False


def test_a_creator_with_every_trip_down_has_no_public_page(captain, trip):
    row, handle, _ = trip
    captain.post("/admin/takedown", data={"slug": row["slug"]})
    assert stranger(captain).get(f"/creators/{handle}").status_code == 404
    assert f'href="/creators/{handle}"' in captain.get("/admin").text   # the admin still lists them


# ---- the commission moved here -------------------------------------------------------------------------------------

def test_commission_is_on_the_admin_page_and_no_longer_on_the_family_page(client, monkeypatch):
    from tests.test_partners import complete, nokeys as _nokeys  # noqa: F401
    for name in ("TRAVELPAYOUTS_MARKER", "TRAVELPAYOUTS_TOKEN", "TRAVELPAYOUTS_TRS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "ari.rivera@example.com")
    sign_in(client, "ari")
    for offer in ("hif1", "hih1", "hic1"):
        assert complete(client, offer).status_code == 303
    family = unescape(client.get("/partners").text)
    assert "estimated commission" not in family.lower() and "$180.90" not in family and "$11.70" not in family and "$146" not in family
    html = unescape(client.get("/admin").text)
    assert numbers(html)["ad-commission"] == "$180.90"
    text_ = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    assert "Aviasales 1 click · 1 booked · $11.70" in text_ and "Klook 2 clicks · 2 booked · $169.20" in text_


def test_a_family_database_that_cannot_be_read_is_logged_and_counted_on_the_admin_page(captain, trip, monkeypatch, caplog):
    """F-182 (reviewer Should 5): the commission total silently left out an unreadable family. It still renders, but says how many were skipped and logs a content-free warning."""
    from gitaway import familydb
    real = familydb.ensure_schema
    hit = []

    def broken(db, tenant_id):
        import inspect
        if not hit and any(f.function == "all_clicks" for f in inspect.stack()):
            hit.append(tenant_id)
            raise RuntimeError("secret detail: ari@example.com")
        return real(db, tenant_id)
    monkeypatch.setattr(familydb, "ensure_schema", broken)
    with caplog.at_level("WARNING", logger="gitaway.partners.log"):
        html = captain.get("/admin").text
    assert re.search(r'id="ad-skipped"[^>]*>1 family could not be read, so its clicks are not in these totals\.<', html)
    warns = [r.getMessage() for r in caplog.records if r.name == "gitaway.partners.log"]
    assert warns == [f"all_clicks: skipped family {hit[0]} (RuntimeError)"] and "ari@example.com" not in "".join(warns)
    caplog.clear()
    monkeypatch.setattr(familydb, "ensure_schema", real)
    assert 'id="ad-skipped"' not in captain.get("/admin").text
