"""F-196 item 6: a new report reaches the captain. A WARNING in the server log and a "new" badge on /admin always; an email through fh-saas when SMTP is set. The email never carries
the reporter's words or address (they are a stranger's text, and the admin page shows them as text)."""

import logging
import re

import pytest
from fh_saas import utils_email

from gitaway import reports
from tests.live_trips import live_trip
from tests.test_signin import sign_in

CAP = "cap@example.com"


@pytest.fixture
def trip():
    return live_trip()[0]


@pytest.fixture
def sent(monkeypatch):
    """Mail goes out at once in these tests (the app sends it from a thread) and into a list, never to a server."""
    out = []
    monkeypatch.setattr(reports, "_run", lambda fn, *a: fn(*a))
    monkeypatch.setattr(utils_email, "send_email", lambda *a, **k: out.append((a, k)) or {"status": "success"})
    return out


def smtp(monkeypatch):
    for k, v in (("SMTP_HOST", "smtp.example.org"), ("SMTP_USER", "u"), ("SMTP_PASSWORD", "p"), ("SMTP_MAIL_FROM", "gitaway@example.org")):
        monkeypatch.setenv(k, v)


def report(client, slug, reason="copyright", note="", email="", ip="203.0.113.7"):
    return client.post("/report", data={"kind": "trip", "target": slug, "reason": reason, "note": note, "email": email, "website": ""}, headers={"x-forwarded-for": ip})


def captain(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAP)
    other = client.__class__(client.app, client=("127.0.0.1", 50001))
    sign_in(other, CAP)
    return other


# ---- the log ---------------------------------------------------------------------------------------------------------------------------

def test_a_new_report_is_one_warning_line_that_names_the_page_and_the_reason_and_nothing_the_reporter_wrote(client, trip, sent, caplog):
    with caplog.at_level(logging.WARNING, logger="gitaway.reports"):
        report(client, trip["slug"], "copyright", note="my secret words", email="rep@example.com")
    (line,) = [r for r in caplog.records if r.name == "gitaway.reports" and r.levelno == logging.WARNING]
    text = line.getMessage()
    assert text == f"new report: trip {trip['slug']}, reason copyright (read it at /admin)"
    assert "my secret words" not in text and "rep@example.com" not in text


def test_a_refused_report_makes_no_noise(client, trip, sent, caplog):
    with caplog.at_level(logging.WARNING, logger="gitaway.reports"):
        report(client, trip["slug"], "nonsense")
        report(client, "nope-123456", "spam")
    assert not [r for r in caplog.records if "new report" in r.getMessage()] and sent == []


# ---- the badge -------------------------------------------------------------------------------------------------------------------------

def badge(html):
    m = re.search(r'id="ad-new"[^>]*>([^<]*)<', html)
    return m.group(1) if m else None


def test_the_admin_page_shows_how_many_reports_are_new_until_the_captain_marks_them_read(client, trip, sent, monkeypatch):
    cap = captain(client, monkeypatch)
    assert badge(cap.get("/admin").text) is None                      # nothing to say
    report(client, trip["slug"], "copyright", note="First")
    report(client, trip["slug"], "spam", note="Second", ip="203.0.113.8")
    html = cap.get("/admin").text
    assert badge(html) == "2 new" and html.count('class="ad-new-chip"') == 2
    assert badge(cap.get("/admin").text) == "2 new"                   # looking is not reading: only the button clears it
    cap.post("/admin/seen", data={"upto": str(max(r["id"] for r in reports.all_reports()))}, follow_redirects=False)
    assert badge(cap.get("/admin").text) is None
    report(client, trip["slug"], "other", note="Third", ip="203.0.113.9")
    html = cap.get("/admin").text
    assert badge(html) == "1 new" and html.count('class="ad-new-chip"') == 1 and html.index('class="ad-new-chip"') < html.index("Third") < html.index("Second")      # the chip is on Third only


def test_a_report_that_came_in_after_the_page_was_drawn_stays_new_when_the_captain_marks_what_they_saw(client, trip, sent, monkeypatch):
    cap = captain(client, monkeypatch)
    report(client, trip["slug"], "copyright", note="First")
    shown = cap.get("/admin").text
    upto = re.search(r'name="upto" value="(\d+)"', shown).group(1)
    report(client, trip["slug"], "spam", note="Second", ip="203.0.113.8")
    r = cap.post("/admin/seen", data={"upto": upto}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin"
    assert badge(cap.get("/admin").text) == "1 new"


def test_nobody_but_the_captain_can_mark_reports_read(client, trip, sent, monkeypatch):
    cap = captain(client, monkeypatch)
    report(client, trip["slug"])
    assert client.post("/admin/seen", data={"upto": "99"}, follow_redirects=False).status_code == 404
    sign_in(client, "ari")
    assert client.post("/admin/seen", data={"upto": "99"}, follow_redirects=False).status_code == 404
    assert badge(cap.get("/admin").text) == "1 new"


def test_the_captain_sees_the_new_count_in_the_account_menu_and_the_header_on_any_page_and_nobody_else_does(client, trip, sent, monkeypatch):
    cap = captain(client, monkeypatch)
    report(client, trip["slug"], "copyright")
    report(client, trip["slug"], "spam", ip="203.0.113.8")
    def link(html, ident):
        m = re.search(rf'<a [^>]*id="{ident}"[^>]*>.*?</a>', html, re.S)
        return re.sub(r"<[^>]+>", " ", m.group(0)).split() if m else None, m and 'href="/admin"' in m.group(0)

    html = cap.get("/family").text
    assert link(html, "ga-tb-admin") == (["Admin", "2", "new"], True) and link(html, "ga-admin-link") == (["Admin", "(2", "new)"], True)
    assert "ga-tb-dot-new" in html                                     # the avatar carries a dot too, so the menu is worth opening
    cap.post("/admin/seen", data={"upto": str(max(r["id"] for r in reports.all_reports()))})
    html = cap.get("/family").text
    assert link(html, "ga-tb-admin") == (["Admin"], True) and link(html, "ga-admin-link") == (["Admin"], True) and "ga-tb-dot-new" not in html     # still a way in, with nothing to count
    other = client.__class__(client.app, client=("127.0.0.1", 50002))
    sign_in(other, "ari")
    html = other.get("/family").text
    assert "ga-tb-admin" not in html and "ga-admin-link" not in html and "/admin" not in html


def test_a_database_made_before_the_seen_column_gains_it_and_its_old_reports_read_as_unseen(tmp_path, monkeypatch):
    import sqlite3
    from gitaway import community
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE reports (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, target TEXT NOT NULL, reason TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', "
                "email TEXT NOT NULL DEFAULT '', reporter TEXT NOT NULL DEFAULT '', ip_hash TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)")
    old.execute("INSERT INTO reports (kind, target, reason, created_at) VALUES ('trip', 'old-one', 'spam', '2026-01-01T00:00:00')")
    old.commit(); old.close()
    monkeypatch.setattr(community, "_url", lambda: f"sqlite:///{path}")
    (row,) = reports.all_reports()
    assert row["target"] == "old-one" and row["seen"] == 0
    reports.mark_seen(row["id"])
    assert [r["seen"] for r in reports.all_reports()] == [1]


# ---- the email -------------------------------------------------------------------------------------------------------------------------

def test_with_smtp_set_every_admin_gets_an_email_that_says_what_and_where_and_nothing_the_reporter_wrote(client, trip, sent, monkeypatch):
    smtp(monkeypatch)
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "cap@example.com, second@example.com")
    report(client, trip["slug"], "private", note="<b>look</b> at https://evil.example", email="rep@example.com")
    assert [a[0] for a, k in sent] == ["cap@example.com", "second@example.com"]
    (args, kwargs) = sent[0]
    to, name, subject, template, variables = args
    assert subject == "GitAway: new report: It shows private information" and template == "report"
    assert variables == {"what": f"the trip {trip['slug']}", "reason": "It shows private information", "admin_url": "https://gitaway.me/admin"}
    assert str(kwargs["custom_template_path"]).endswith("gitaway/emails/report.md")
    assert "evil.example" not in repr(sent) and "rep@example.com" not in repr(sent)


def test_without_smtp_no_email_is_tried_and_the_report_is_still_kept(client, trip, sent, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAP)
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_MAIL_FROM"):
        monkeypatch.delenv(k, raising=False)
    assert report(client, trip["slug"]).status_code == 200 and sent == [] and len(reports.all_reports()) == 1


def test_with_smtp_set_but_no_admin_named_nothing_is_sent(client, trip, sent, monkeypatch):
    smtp(monkeypatch)
    monkeypatch.delenv("GITAWAY_ADMIN_EMAILS", raising=False)
    assert report(client, trip["slug"]).status_code == 200 and sent == []


def test_an_email_that_cannot_go_is_a_warning_and_the_reporter_still_gets_their_thanks(client, trip, monkeypatch, caplog):
    smtp(monkeypatch)
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAP)
    monkeypatch.setattr(reports, "_run", lambda fn, *a: fn(*a))

    def broken(*a, **k):
        raise ImportError("markdown_merge not installed")
    monkeypatch.setattr(utils_email, "send_email", broken)
    with caplog.at_level(logging.WARNING, logger="gitaway.reports"):
        r = report(client, trip["slug"])
    assert r.status_code == 200 and "Thank you" in r.text and len(reports.all_reports()) == 1
    assert any("report email was not sent" in m.getMessage() and "markdown_merge not installed" in m.getMessage() for m in caplog.records)


def test_an_email_the_server_refused_is_a_warning_too(client, trip, monkeypatch, caplog):
    smtp(monkeypatch)
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAP)
    monkeypatch.setattr(reports, "_run", lambda fn, *a: fn(*a))
    monkeypatch.setattr(utils_email, "send_email", lambda *a, **k: {"status": "error", "error": "535 bad login"})
    with caplog.at_level(logging.WARNING, logger="gitaway.reports"):
        report(client, trip["slug"])
    assert any("report email was not sent" in m.getMessage() and "535 bad login" in m.getMessage() for m in caplog.records)


def test_the_email_is_sent_from_a_thread_so_a_slow_mail_server_cannot_hold_the_page(client, trip, monkeypatch):
    import threading
    import time
    smtp(monkeypatch)
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAP)
    gate, started = threading.Event(), threading.Event()

    def slow(*a, **k):
        started.set()
        gate.wait(5)
        return {"status": "success"}
    monkeypatch.setattr(utils_email, "send_email", slow)
    t0 = time.monotonic()
    assert report(client, trip["slug"]).status_code == 200
    assert time.monotonic() - t0 < 2 and started.wait(5)
    gate.set()
