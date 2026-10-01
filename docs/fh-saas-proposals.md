# Proposed fh-saas changes (found building GitAway)

Found while building GitAway on fh-saas 0.9.14 and checked against the installed source. GitAway works around each one today; the workarounds are logged in `.work/lessons.md`. Each change belongs in the package's `nbs/` notebooks, followed by `nbdev_prepare`.

| # | Priority | Problem | Proposed change |
|---|---|---|---|
| 1 | **High: blocks family invites** | `provision_new_user` always creates a new tenant named "<username>'s Workspace", so an invited email can't join an existing tenant on first sign-in. | Add optional `tenant_name`, plus `join_tenant_id` and `role` (or a pre-provision hook that looks up pending invitations) to `provision_new_user` and `handle_oauth_callback`. |
| 2 | High: data loss risk on deploy | Tenant DB files and stored `db_url`s are relative to the working directory. | Add an optional `DB_DIR` / `TENANT_DB_DIR` setting used by `_build_host_url` and `_tenant_url_from_settings`, storing absolute URLs. |
| 3 | Medium | `handle_oauth_callback` always redirects to `/dashboard`. | Add a `redirect_to` argument or a `post_login_url` hook. |
| 4 | Medium | There's no public "complete login" step, so dev and test sign-ins copy four calls. | Extract `complete_login(session, host_db, oauth_id, email, info)` and call it from the callback. |
| 5 | Medium | `create_auth_beforeware` can only redirect; apps with mostly public pages need a negative-lookahead skip regex. | Add `optional=True`, which sets `request.state.user = None` instead of redirecting. |
| 6 | Low | `handle_logout` clears the whole session and always goes to `/login`. | Add `keep=` and `redirect_to=`. |
| 7 | Low | `db_host.timestamp()` uses the deprecated `datetime.utcnow()`. | Use `datetime.now(timezone.utc)`. |
| 8 | Low (from the skill notes) | Exported cells import `nbdev.showdoc`, so a clean install needs nbdev; `DB_TYPE` defaults also differ between modules. | Move `show_doc` imports out of exported cells, and make the `DB_TYPE` default the same everywhere. |
| 9 | **High: unsafe under load** | `HostDatabase` is one shared SQLAlchemy connection used by `verify_membership`, `get_user_membership` and the beforeware from every threadpool request. | Open a short connection per call (or lock inside `HostDatabase`). |
| 10 | Medium | `get_user_membership` returns the first active membership: a person in two families cannot choose. | Add `tenant_id=` and an ordering, and a session helper to switch tenant. |
| 11 | Medium | `utils_sql.upsert` on SQLite is `INSERT OR REPLACE`: it ignores `conflict_cols` and `update_cols` and replaces the whole row. | Use `INSERT ... ON CONFLICT DO UPDATE` on SQLite 3.24+. |
| 12 | Medium | `with_transaction` does not take a write lock, so read-then-write is stale-prone on SQLite. | `with_transaction(db, immediate=True)` issuing `BEGIN IMMEDIATE`. |
| 13 | Low | No way to set WAL or a busy timeout on tenant engines. | SQLite engine options in settings. |
| 14 | Low | `utils_migrate` has no "all tenants" runner; `apply_migrations` uses `utcnow()` and `db.execute`. | `migrate_all_tenants(host_db, dir, dry_run=True)`. |

Doing #1 first would let GitAway drop its invite workaround in F-043.
