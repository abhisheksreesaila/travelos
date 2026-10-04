"""Delete a person's data by hand (F-076): `pixi run forget-person EMAIL [--family] [--content] [--yes]`.

Plain sqlite3 on the data folder (GITAWAY_DATA_DIR, or --data-dir); stop the app first and copy the folder. Without --yes it only lists what it
would delete (a dry run). Tables that do not exist yet are skipped.

* default       the person: sign-in, memberships, passkeys, invites to or from them, audit-log rows with their id or email, and in each of
                their families: their member row, push subscriptions, thread settings and their own boarding pass (F-083, a pass whose traveller is them: rows and files).
                Messages and photos they added stay with the family.
* --content     also the messages and photos they added in their families (and the photo files), and the boarding passes they added for anyone.
* --family      the whole family of each family they belong to: its database (and -wal/-shm), photos and passes folders, memberships, invites and its
                rows in the host. Other members' sign-ins stay. Implies --content.
"""

import argparse
import os
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def data_dir(arg=None) -> Path:
    return (ROOT / (arg or os.getenv("GITAWAY_DATA_DIR", "data/db"))).resolve()


def _has(conn, table) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _family_file(folder: Path, db_url: str) -> Path:
    return folder / db_url.replace("sqlite:///", "", 1)


def plan(folder: Path, email: str, family=False, content=False):
    """The steps: [(label, file, table, where, params)] for rows, and [(label, path)] for files and folders. Reads only."""
    host = folder / "app_host.db"
    if not host.exists():
        raise SystemExit(f"No host database at {host}")
    rows, paths = [], []
    h = sqlite3.connect(host)
    user = h.execute("SELECT id FROM core_users WHERE lower(email) = lower(?)", (email,)).fetchone()
    if not user:
        raise SystemExit(f"No one with the email {email}")
    uid = user[0]
    families = h.execute("SELECT t.id, t.db_url FROM core_memberships m JOIN core_tenants t ON t.id = m.tenant_id WHERE m.user_id = ?", (uid,)).fetchall() \
        if _has(h, "core_memberships") and _has(h, "core_tenants") else []
    content = content or family
    for tid, db_url in families:
        fdb = _family_file(folder, db_url)
        if family:
            paths += [(f"family database {fdb.name}", p) for p in (fdb, Path(str(fdb) + "-wal"), Path(str(fdb) + "-shm"))]
            paths.append((f"photos of family {tid}", folder / "photos" / tid))
            paths.append((f"boarding passes of family {tid}", folder / "passes" / tid))
            rows += [("memberships of the family", host, "core_memberships", "tenant_id = ?", (tid,)),
                     ("invites of the family", host, "ga_invites", "tenant_id = ?", (tid,)),
                     ("last-family choices", host, "ga_last_family", "tenant_id = ?", (tid,)),
                     ("subscriptions of the family", host, "core_subscriptions", "tenant_id = ?", (tid,)),
                     ("the family", host, "core_tenants", "id = ?", (tid,))]
            continue
        if not fdb.exists():
            continue
        f = sqlite3.connect(fdb)
        rows += [("member row", fdb, "members", "id = ?", (uid,)), ("tenant user row", fdb, "core_tenant_users", "id = ?", (uid,)),
                 ("permissions", fdb, "core_permissions", "user_id = ?", (uid,)), ("push subscriptions", fdb, "push_subscriptions", "user_id = ?", (uid,)),
                 ("thread settings", fdb, "thread_prefs", "user_id = ?", (uid,))]
        if _has(f, "passes"):   # F-083: their own pass always (personal boarding data); with --content also every pass they added
            where, params = ("member_id = ? OR created_by = ?", (uid, uid)) if content else ("member_id = ?", (uid,))
            for r in f.execute(f"SELECT orig, display, thumb FROM passes WHERE {where}", params):
                paths += [("boarding pass file", folder / "passes" / name) for name in r if name]
            rows.append(("boarding passes", fdb, "passes", where, params))
        if content:
            if _has(f, "photos"):
                for r in f.execute("SELECT orig, display, thumb FROM photos WHERE author = ?", (uid,)):
                    paths += [("photo file", folder / "photos" / name) for name in r]
            rows += [("messages", fdb, "thread", "author = ?", (uid,)), ("photos", fdb, "photos", "author = ?", (uid,))]
        f.close()
    if not family:
        rows += [("passkeys", host, "ga_passkeys", "user_id = ?", (uid,)), ("last-family choice", host, "ga_last_family", "user_id = ?", (uid,)),
                 ("memberships", host, "core_memberships", "user_id = ?", (uid,)),
                 ("invites to or from them", host, "ga_invites", "lower(email) = lower(?) OR invited_by = ? OR accepted_by = ?", (email, uid, uid))]
    rows += [("audit log rows", host, "sys_audit_logs", "actor_user_id = ? OR target_id = ? OR details LIKE ?", (uid, uid, f"%{email}%"))]
    if not family:
        rows += [("sign-in", host, "core_users", "id = ?", (uid,))]
    h.close()
    return rows, paths


def run(folder: Path, email: str, family=False, content=False, yes=False, out=print):
    """Print what is (or, with yes, was) deleted. Returns {label: count}."""
    rows, paths = plan(folder, email, family, content)
    done, conns = {}, {}
    for label, file, table, where, params in rows:
        conn = conns.setdefault(file, sqlite3.connect(file))
        if not _has(conn, table):
            continue
        n = conn.execute(f"SELECT count(*) FROM {table} WHERE {where}", params).fetchone()[0]
        if n and yes:
            conn.execute(f"DELETE FROM {table} WHERE {where}", params)
        if n:
            done[f"{label} ({table})"] = done.get(f"{label} ({table})", 0) + n
    for conn in conns.values():
        conn.commit()
        conn.close()
    for label, p in paths:
        if p.exists():
            done[f"{label}: {p.relative_to(folder)}"] = 1
            if yes:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    for k, v in done.items():
        out(f"{'deleted' if yes else 'would delete'}: {v} x {k}")
    if not done:
        out("nothing to delete")
    if not yes:
        out("Dry run. Add --yes to delete.")
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("email")
    ap.add_argument("--family", action="store_true", help="delete the whole family of each family they belong to")
    ap.add_argument("--content", action="store_true", help="also delete the messages and photos they added")
    ap.add_argument("--yes", action="store_true", help="really delete (default is a dry run)")
    ap.add_argument("--dry-run", action="store_true", help="the default; list what would be deleted")
    ap.add_argument("--data-dir")
    a = ap.parse_args(argv)
    run(data_dir(a.data_dir), a.email, a.family, a.content, a.yes and not a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
