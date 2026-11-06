"""F-182 (M2): `forget-person` also removes what a person published: their public trips, creator record, drafts, affiliate marker, reports they sent, their try counts, and the picture
files under public/<slug>/ of every slug that was theirs. Another creator's rows and files stay."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import forget_person as fp  # noqa: E402

from gitaway import community  # noqa: E402
from tests.test_forget_person import EMAIL, count, folder  # noqa: E402,F401  (the fixture)

DRAFTS = """CREATE TABLE IF NOT EXISTS creator_drafts (id TEXT PRIMARY KEY, owner_user TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, data TEXT NOT NULL, published_by TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
HITS = "CREATE TABLE IF NOT EXISTS creator_import_hits (owner_user TEXT NOT NULL, day TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (owner_user, day))"


@pytest.fixture
def pub(folder):
    dst, uid, fid = folder
    c = sqlite3.connect(dst / "community.db")
    for ddl in (community._SCHEMA, community._CREATORS, *community._MORE, DRAFTS, HITS):
        c.execute(ddl)
    for slug, owner in (("mine-live-111111", uid), ("theirs-live-222222", "someone-else")):
        c.execute("INSERT INTO published VALUES (?, 'scrapbook', ?, '', 't', '[]', 'sunset', '{}', '{}', 'n', 'n')", (slug, owner))
    c.execute("INSERT INTO creators VALUES ('me', ?, 'Me', 'n', 'n')", (uid,))
    c.execute("INSERT INTO creators VALUES ('other', 'someone-else', 'Other', 'n', 'n')")
    c.execute("INSERT INTO creator_markers VALUES (?, '123456', 'n')", (uid,))
    c.execute("INSERT INTO creator_markers VALUES ('someone-else', '999999', 'n')")
    c.execute("INSERT INTO creator_drafts VALUES ('d1', ?, 'mine-draft-333333', '{}', '', 'n', 'n')", (uid,))
    c.execute("INSERT INTO creator_drafts VALUES ('d2', 'someone-else', 'theirs-draft-444444', '{}', '', 'n', 'n')")
    c.execute("INSERT INTO reports (kind, target, reason, note, email, reporter, ip_hash, created_at) VALUES ('trip', 'x', 'spam', '', ?, '', 'h', 'n')", (EMAIL,))
    c.execute("INSERT INTO reports (kind, target, reason, note, email, reporter, ip_hash, created_at) VALUES ('trip', 'x', 'spam', '', '', ?, 'h', 'n')", (uid,))
    c.execute("INSERT INTO reports (kind, target, reason, note, email, reporter, ip_hash, created_at) VALUES ('trip', 'x', 'spam', '', 'other@example.com', 'someone-else', 'h', 'n')")
    c.execute("INSERT INTO creator_import_hits VALUES (?, 'd', 3)", (uid,))
    c.execute("INSERT INTO creator_import_hits VALUES (?, 'd', 1)", (f"pic:{uid}",))
    c.execute("INSERT INTO creator_import_hits VALUES ('*site*', 'd', 9)")
    c.execute("INSERT INTO fork_counts VALUES ('mine-live-111111', 4)")
    c.execute("INSERT INTO takedowns VALUES ('mine-live-111111', 'n')")
    c.commit()
    c.close()
    for slug in ("mine-live-111111", "mine-draft-333333", "theirs-live-222222", "theirs-draft-444444"):
        (dst / "public" / slug).mkdir(parents=True)
        (dst / "public" / slug / "0123456789abcdef-display.jpg").write_bytes(b"x")
    return dst, uid


def n(dst, sql):
    return count(dst, "community.db", sql)


def test_a_dry_run_lists_the_community_rows_and_files_and_deletes_nothing(pub):
    dst, uid = pub
    out = []
    fp.run(dst, EMAIL, out=out.append)
    text = "\n".join(out)
    for want in ("(published)", "(creators)", "(creator_drafts)", "(creator_markers)", "(reports)", "public/mine-live-111111", "public/mine-draft-333333"):
        assert want in text.replace("\\", "/"), want
    assert n(dst, "SELECT count(*) FROM published") == 2 and (dst / "public" / "mine-live-111111").is_dir()


@pytest.mark.parametrize("family", [False, True])
def test_a_persons_published_trips_creator_drafts_marker_reports_counts_and_picture_files_go(pub, family):
    dst, uid = pub
    fp.run(dst, EMAIL, family=family, yes=True, out=lambda s: None)
    assert n(dst, "SELECT group_concat(slug) FROM published") == "theirs-live-222222"
    assert n(dst, "SELECT group_concat(handle) FROM creators") == "other"
    assert n(dst, "SELECT group_concat(owner_user) FROM creator_markers") == "someone-else"
    assert n(dst, "SELECT group_concat(slug) FROM creator_drafts") == "theirs-draft-444444"
    assert n(dst, "SELECT count(*) FROM reports") == 1 and n(dst, "SELECT email FROM reports") == "other@example.com"       # theirs by address and by id are gone
    assert n(dst, "SELECT group_concat(owner_user) FROM creator_import_hits") in ("*site*", "*site*,")
    assert n(dst, "SELECT count(*) FROM fork_counts") == 0
    assert n(dst, "SELECT count(*) FROM takedowns") == 1          # a takedown is about the address, not the person: it stays, so the page cannot return
    assert sorted(p.name for p in (dst / "public").iterdir()) == ["theirs-draft-444444", "theirs-live-222222"]
