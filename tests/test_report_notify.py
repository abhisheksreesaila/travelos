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


def test_the_admin_page_shows_how_many_reports_are_new_and_marks_them_until_the_captain_has_looked(client, trip, sent, monkeypatch):
    cap = captain(client, monkeypatch)
    assert badge(cap.get("/admin").text) is None                      # nothing to say
    report(client, trip["slug"], "copyright", note="First")
    report(client, trip["slug"], "spam", note="Second", ip="203.0.113.8")
    html = cap.get("/admin").text
    assert badge(html) == "2 new" and html.count('class="ad-new-chip"') == 2
    assert badge(cap.get("/admin").text) is None                      # seen
    report(client, trip["slug"], "other", note="Third", ip="203.0.113.9")
    html = cap.get("/admin").text
    assert badge(html) == "1 new" and html.count('class="ad-new-chip"') == 1 and html.index('class="ad-new-chip"') < html.index("Third") < html.index("Second")      # the chip is on Third only


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
