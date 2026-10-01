# Families are tenants on fh-saas; the cookie keeps only the sign-in

Status: accepted (2026-10-01)

GitAway moves from a cookie-only demo to a real backend on fh-saas with SQLite. A **family** (the people planning trips together) is a tenant. The host database holds people, families and memberships (fh-saas `GlobalUser`, `TenantCatalog`, `Membership`). Each family's tenant database holds its trips, bookings (demo or imported), activities, notes, invites, forks, saves and rides. A separate **community** SQLite database holds published itineraries (shared trips and creator trips) that every family can browse and fork.

**Why:**
- Trips are planned with family, and fh-saas already gives per-tenant databases, roles (admin, editor, viewer) and Google sign-in.
- The ~4 KB cookie had become the main source of bugs: the budget refusals in F-021, F-023, F-027 and F-035.

## Consequences
- The session cookie holds only fh-saas's sign-in state. Every other piece of state moves to SQLite, and the cookie budget code and its tests are retired as each part moves.
- Invited emails join the inviter's family on first sign-in instead of being auto-provisioned a new tenant. If fh-saas can't express that, the gap is reported and proposed as a package change.
- Until Google keys are configured, a dev sign-in, guarded by `GITAWAY_DEV_LOGIN=1` plus a localhost check, stands in for OAuth through the same session path.
- SQLite files must live on a persistent volume when deployed (see the fh-saas skill notes); local first.
