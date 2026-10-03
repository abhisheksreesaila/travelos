"""F-076: scripts/forget_person.py against a throwaway copy of the host + family databases the dev sign-in builds."""

import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import forget_person as fp  # noqa: E402

from gitaway import auth  # noqa: E402
from tests.test_signin import person  # noqa: E402

EMAIL = "forget-ari@example.com"


@pytest.fixture
def folder(client):
    """A copy of the data folder after two people signed in, with rows in every table the script touches and three photo files."""
    ari = person(EMAIL)
    person("forget-sam@example.com")
    uid = ari["user_id"]
    src = auth.data_dir()
    host = sqlite3.connect(src / "app_host.db")
    fid = host.execute("SELECT tenant_id FROM core_memberships WHERE user_id = ?", (uid,)).fetchone()[0]
    host.close()
    dst = Path(str(src) + "-copy")
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)
    host = sqlite3.connect(dst / "app_host.db")   # the copy, never the live databases
    host.execute("INSERT INTO sys_audit_logs (id, actor_user_id, event_type, target_id, details, ip_address, created_at) VALUES ('a1', ?, 'login', ?, ?, '', 'now')", (uid, uid, EMAIL))
    host.commit()
    host.close()
    fam = sqlite3.connect(dst / f"{fid}_db.db")
    fam.executescript("""
        CREATE TABLE IF NOT EXISTS push_subscriptions (endpoint TEXT PRIMARY KEY, user_id TEXT, p256dh TEXT, auth TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS thread (id TEXT PRIMARY KEY, author TEXT, text TEXT);
        CREATE TABLE IF NOT EXISTS photos (id TEXT PRIMARY KEY, author TEXT, orig TEXT, display TEXT, thumb TEXT);
        CREATE TABLE IF NOT EXISTS members (id TEXT PRIMARY KEY, email TEXT);
    """)
    fam.execute("INSERT OR IGNORE INTO members (id, email) VALUES (?, ?)", (uid, EMAIL))
    fam.execute("INSERT INTO push_subscriptions VALUES ('https://x/1', ?, 'k', 'a', 'now')", (uid,))
    fam.execute("INSERT INTO thread VALUES ('m1', ?, 'hi')", (uid,))
    fam.execute("INSERT INTO photos VALUES ('p1', ?, ?, ?, ?)", (uid, f"{fid}/t/p1.jpg", f"{fid}/t/p1-display.jpg", f"{fid}/t/p1-thumb.jpg"))
    fam.commit()
    fam.close()
    (dst / "photos" / fid / "t").mkdir(parents=True)
    for n in ("p1.jpg", "p1-display.jpg", "p1-thumb.jpg"):
        (dst / "photos" / fid / "t" / n).write_bytes(b"x")
    yield dst, uid, fid
    shutil.rmtree(dst, ignore_errors=True)


def count(folder, db, sql, *a):
    c = sqlite3.connect(folder / db)
    try:
        return c.execute(sql, a).fetchone()[0]
    finally:
        c.close()


def test_dry_run_deletes_nothing(folder):
    dst, uid, fid = folder
    out = []
    fp.run(dst, EMAIL, out=out.append)
    assert any("would delete" in line for line in out) and out[-1].startswith("Dry run")
    assert count(dst, "app_host.db", "SELECT count(*) FROM core_users WHERE id = ?", uid) == 1
    assert count(dst, f"{fid}_db.db", "SELECT count(*) FROM push_subscriptions") == 1


def test_person_only_keeps_family_and_content(folder):
    dst, uid, fid = folder
    fp.run(dst, EMAIL.upper(), yes=True, out=lambda s: None)
    assert count(dst, "app_host.db", "SELECT count(*) FROM core_users WHERE id = ?", uid) == 0
    assert count(dst, "app_host.db", "SELECT count(*) FROM core_memberships WHERE user_id = ?", uid) == 0
    assert count(dst, "app_host.db", "SELECT count(*) FROM sys_audit_logs WHERE id = 'a1'") == 0
    assert count(dst, f"{fid}_db.db", "SELECT count(*) FROM push_subscriptions WHERE user_id = ?", uid) == 0
    assert count(dst, f"{fid}_db.db", "SELECT count(*) FROM members WHERE id = ?", uid) == 0
    assert count(dst, f"{fid}_db.db", "SELECT count(*) FROM thread WHERE author = ?", uid) == 1   # stays with the family
    assert (dst / "photos" / fid / "t" / "p1.jpg").exists()
    assert count(dst, "app_host.db", "SELECT count(*) FROM core_users WHERE email = 'forget-sam@example.com'") == 1


def test_content_removes_messages_and_photos(folder):
    dst, uid, fid = folder
    fp.run(dst, EMAIL, content=True, yes=True, out=lambda s: None)
    assert count(dst, f"{fid}_db.db", "SELECT count(*) FROM thread WHERE author = ?", uid) == 0
    assert count(dst, f"{fid}_db.db", "SELECT count(*) FROM photos WHERE author = ?", uid) == 0
    assert not (dst / "photos" / fid / "t" / "p1.jpg").exists()


def test_whole_family(folder):
    dst, uid, fid = folder
    fp.run(dst, EMAIL, family=True, yes=True, out=lambda s: None)
    assert not (dst / f"{fid}_db.db").exists() and not (dst / "photos" / fid).exists()
    assert count(dst, "app_host.db", "SELECT count(*) FROM core_tenants WHERE id = ?", fid) == 0
    assert count(dst, "app_host.db", "SELECT count(*) FROM core_memberships WHERE tenant_id = ?", fid) == 0
    assert count(dst, "app_host.db", "SELECT count(*) FROM sys_audit_logs WHERE id = 'a1'") == 0


def test_unknown_email_stops(folder):
    with pytest.raises(SystemExit):
        fp.run(folder[0], "nobody@example.com")
