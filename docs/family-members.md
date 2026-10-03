# Family members, invites and roles (F-043)

A family is an fh-saas tenant (ADR-0004). People join it by invitation; what they may do depends on their role. The code is `gitaway/members.py` (the model), `gitaway/access.py` (the rule every request passes through) and `gitaway/pages/family.py` (the `/family` page and the `/join/<token>` link).

## Roles

| Role | Can |
|---|---|
| admin | everything an editor can, plus invite people, change roles and remove members |
| editor | change the family's plans: trips, calendar, notes, rides, forks, saves, sharing, booking |
| viewer | read everything; no write |

fh-saas stores a role per `Membership` (`core_memberships.role`). The person who signs up is `owner` (fh-saas's word); GitAway treats `owner` as `admin` (`members.effective_role`). Invites offer editor or viewer; an admin promotes later. A family always keeps at least one admin. The owner stays an admin (not even they can demote themselves) and only they can remove themselves; nobody else can change or remove the owner.

## Where things are stored

In the **host database**, next to fh-saas's own tables (made with `CREATE TABLE IF NOT EXISTS` the first time they are used):

- `ga_invites`: id, token, email (lowercased), email_key, family (tenant id), role, invited_by, created_at, expires_at (14 days), status (`pending`, `accepted`, `revoked`), accepted_by, accepted_at. "Expired" is computed from `expires_at`.
- `ga_last_family`: the family a person last worked in, so signing in again lands there.

They are in the host database, not a file of their own, so accepting an invite (the new `Membership` and the invite marked accepted) is one commit. All host access goes through `hostdb.locked()`.

The family's own database also gets a `TenantUser` row (fh-saas's `local_role`) for each member, kept in step with the membership. The membership row is the truth; the `TenantUser` write is best effort.

## Joining

1. An admin invites an email on `/family`. The invite shows a link (`/join/<token>`) to copy. Email sending comes later (`fh-saas utils_email`).
2. **Sign-in hook.** Only a **verified** email joins anything. The Google callback is composed from fh-saas's public steps (`auth.sign_in_google`: `verify_oauth_state`, `retr_info`, `create_or_get_global_user`, provisioning, `create_user_session`) so Google's `email_verified` is kept; the dev sign-in counts as verified (local only). An unverified email still signs in, to a family of its own, but gets a notice ("Your Google email isn't verified...") and the invite stays pending; the join link is refused the same way. Any domain may be invited: verification is the gate. The session holds `verified` (0/1).
   The hook The dev sign-in and the Google callback both end with `auth.after_sign_in` -> `members.after_sign_in`. It finds live invites for the person's email, creates the `Membership` with the invited role under the host lock, marks the invites accepted, then asks before moving anyone: the last family joined becomes the active one (`tenant_id`, `tenant_role`, `invalidate_auth_cache`) **only when the family they would otherwise work in has no trips yet** (a first sign-in). Otherwise they stay where they are. Either way a dismissable notice follows them (`session["note"]`, shown by `layout.join_note` on pages and the calendar): "You joined X's family" with Switch / Stay (`POST /family/switch`, `POST /family/stay`), or just OK when they were moved.
3. **The link.** `/join/<token>` signed out shows who invited you and a Sign in button that comes back to the link. Signed in with a matching email it offers one Join button. Signed in with another email it is refused (403) and the mismatch is logged with the invite id and masked addresses; the token alone gets nobody in.
4. Emails are lowercased. For `gmail.com` / `googlemail.com` the dots and `+tag` are ignored when comparing (Google treats them as one mailbox).

fh-saas has still made the invited person's own empty family on their first sign-in (it cannot join an existing tenant: `docs/fh-saas-proposals.md` row 1). That is fine: they keep it and can switch to it.

## Choosing the family

A person in two families gets a switcher on `/family` (`POST /family/switch`). `members.set_active` checks the membership against the host database every time; a tenant id from a form or cookie is never trusted. After sign-in the active family is the one just joined, else the one last used (`ga_last_family`), else the first.

## The rule every request passes (`gitaway/access.py`)

`access.guard` is a beforeware on every request:

- It reads the person's role **from the membership row**, never the cookie. A removed member's next request moves them to another family of theirs (or signs them out if they have none); a changed role takes effect on the next request and the cookie's `tenant_role` is brought into step.
- Any request that is not a read (GET, HEAD, OPTIONS) needs the **editor** role, unless its path is on `OPEN_POSTS` / `OPEN_PREFIXES` (sign in and out, switching trip, switching family, creator drafts, using an invite link) or on `ADMIN_POSTS` (invite, revoke, change role, remove: **admin**).
- A refused person gets a 403 with a friendly message. A refused calendar write returns the calendar with the message on it (its soft navigation swaps that page in).

A new write route is therefore safe by default. `tests/test_roles.py` walks every POST route in the app as a viewer and fails if one is neither refused nor on the expected open list, so opening a route takes two deliberate edits.

Fh-saas's `require_role` is not used: with `setup_tenant_db=False` the beforeware gives every non-owner `role = None`, and `owner` short-circuits to admin whichever family is active (proposals row 15).

## The family thread (F-070)

`POST /trip/family/message` (a message in the trip's thread on the Family tab) and `POST /trip/family/quiet` (my own Quiet switch for the thread's pushes) are on `OPEN_POSTS`: **every member may use them, viewers too**. This is deliberate. A viewer cannot change a plan, but a grandparent who may only look should still be able to say "see you at 6". A viewer's message is the only thing a viewer can add; plan-change cards come from plan writes, which stay editor-only, so a viewer never causes one.

## Offline cache

`layout.cache_key` (the `ga-user` meta the service worker files saved pages under) hashes the person **and the active family**, so switching family or being removed changes the key and the other family's saved pages are dropped.

## The calendar

- Avatars and "planning with you" are the family's real members (`members.crew`), on every trip.
- The pretend friends (the Mom / Sam quick picks) and Mom's scripted add (F-020) only exist on **demo trips** (`trips.source = 'demo'`, `session.Family.is_demo`). On any other trip the Invite button goes to `/family#invite`, and `POST /calendar/friends` is refused with a message.
- Viewers get a banner, no add/edit/invite/voice dialogs, no Share button, and cannot drag blocks (`cal-readonly`).

## Known limits

- `access.py` does not support system-admin sessions (no family): such a session is signed out. GitAway has no system admins.
- The dev sign-in trusts any email and only runs on this machine.
- No email is sent; the admin copies the link.
- One worker per data folder (the host lock is per process; see `docs/family-db.md`).
