"""F-182 fix 2 (M1): every community table with a column that names a person is covered by `forget-person`. The tables are read from the real schema (what the app creates), so a new
table with an owner_user / claimed_by / reporter column fails here until scripts/forget_person.py `community_plan` deletes by it. This is how the creator_draft_jobs and scan counts were missed."""

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import forget_person as fp  # noqa: E402

from gitaway import auth, community, creatordraft as cd, draftjobs as dj  # noqa: E402

PERSON_COLUMNS = ("owner_user", "claimed_by", "published_by", "reporter", "who", "user_id", "author", "created_by", "invited_by", "accepted_by", "email")
# Tables where the column is not a person who must be forgotten, and why.
NOT_A_PERSON = {("creator_drafts", "published_by"): "set only on a row whose owner_user is the publisher (creatordraft._store), so it goes with that row"}


def _community_tables():
    with community.connect():
        pass
    with cd._db():
        pass
    with dj._db():
        pass
    c = sqlite3.connect(auth.data_dir() / "community.db")
    try:
        names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {t: [r[1] for r in c.execute(f"PRAGMA table_info({t})")] for t in names}
    finally:
        c.close()


def test_every_community_table_with_a_person_column_is_in_the_forget_plan(client):
    tables = _community_tables()
    assert "creator_draft_jobs" in tables and "creator_import_hits" in tables      # the scan found the tables it should
    rows, _paths = fp.community_plan(auth.data_dir(), "u-1", "x@example.com")
    uncovered = []
    for table, cols in tables.items():
        for col in cols:
            if col in PERSON_COLUMNS and (table, col) not in NOT_A_PERSON and not any(t == table and re.search(rf"\b{col}\b", where) for _l, _f, t, where, _p in rows):
                uncovered.append(f"{table}.{col}")
    assert uncovered == [], f"scripts/forget_person.py community_plan must delete by these columns: {uncovered}"
