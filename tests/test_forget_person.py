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
        CREATE TABLE IF NOT EXISTS passes (id TEXT PRIMARY KEY, member_id TEXT, created_by TEXT, orig TEXT, display TEXT, thumb TEXT);
    """)
    for pid, member, made in (("own", uid, "someone"), ("made", "kid", uid), ("other", "kid", "someone")):   # F-083: whose pass it is, who added it, a stranger's
        fam.execute("INSERT INTO passes VALUES (?, ?, ?, ?, ?, ?)", (pid, member, made, f"{fid}/t/{pid}.pdf", f"{fid}/t/{pid}-display.jpg", f"{fid}/t/{pid}-thumb.jpg"))
    fam.execute("INSERT OR IGNORE INTO members (id, email) VALUES (?, ?)", (uid, EMAIL))
    fam.execute("INSERT INTO push_subscriptions VALUES ('https://x/1', ?, 'k', 'a', 'now')", (uid,))
    fam.execute("INSERT INTO thread VALUES ('m1', ?, 'hi')", (uid,))
    fam.execute("INSERT INTO photos VALUES ('p1', ?, ?, ?, ?)", (uid, f"{fid}/t/p1.jpg", f"{fid}/t/p1-display.jpg", f"{fid}/t/p1-thumb.jpg"))
    fam.commit()
    fam.close()
    (dst / "photos" / fid / "t").mkdir(parents=True)
    for n in ("p1.jpg", "p1-display.jpg", "p1-thumb.jpg"):
        (dst / "photos" / fid / "t" / n).write_bytes(b"x")
    (dst / "passes" / fid / "t").mkdir(parents=True)
    for pid in ("own", "made", "other"):
        for n in (f"{pid}.pdf", f"{pid}-display.jpg", f"{pid}-thumb.jpg"):
            (dst / "passes" / fid / "t" / n).write_bytes(b"x")
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


def pass_ids(dst, fid):
    c = sqlite3.connect(dst / f"{fid}_db.db")
    try:
        return sorted(r[0] for r in c.execute("SELECT id FROM passes"))
    finally:
        c.close()


def pass_files(dst, fid):
    return sorted(p.name.split(".")[0].split("-")[0] for p in (dst / "passes" / fid / "t").glob("*"))


def test_the_default_run_removes_the_persons_own_boarding_pass_and_files_only(folder):
    dst, uid, fid = folder
    fp.run(dst, EMAIL, yes=True, out=lambda s: None)
    assert pass_ids(dst, fid) == ["made", "other"]
    assert sorted(set(pass_files(dst, fid))) == ["made", "other"] and not (dst / "passes" / fid / "t" / "own.pdf").exists()


def test_content_also_removes_the_passes_they_added_for_others(folder):
    dst, uid, fid = folder
    fp.run(dst, EMAIL, content=True, yes=True, out=lambda s: None)
    assert pass_ids(dst, fid) == ["other"] and sorted(set(pass_files(dst, fid))) == ["other"]


def test_the_whole_family_removes_its_pass_folder(folder):
    dst, uid, fid = folder
    fp.run(dst, EMAIL, family=True, yes=True, out=lambda s: None)
    assert not (dst / "passes" / fid).exists()


def test_a_dry_run_keeps_the_pass_rows_and_files(folder):
    dst, uid, fid = folder
    fp.run(dst, EMAIL, content=True, out=lambda s: None)
    assert pass_ids(dst, fid) == ["made", "other", "own"] and len(list((dst / "passes" / fid / "t").glob("*"))) == 9
