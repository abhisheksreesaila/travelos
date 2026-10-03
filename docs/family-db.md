# The family database (F-040)

A family is an fh-saas tenant (ADR-0004). Everything a family plans together lives in that tenant's own SQLite file, and the session cookie holds only the sign-in.

| Where | What |
|---|---|
| `gitaway/familydb.py` | The tables (`FAMILY_TABLES`), how a database is opened, the small SQL helpers. Screens never import it. |
| `gitaway/session.py` | `family(session)`, `booking`, `book`, `trips`, `switch_trip`, `friends`, `add_friend`, `remembered_plan`. |
| `gitaway/tripcal.py` | The calendar: `activities`, `add_activity`, `notes`, `add_note`, `delete_activity`, `undo_delete`, `live_add`, `apply_plans`, `remove_plans`. |
| `gitaway/rides.py` | `list_rides`, `get_ride`, `save_ride`, `cancel_ride`, `step_ride`: the only code that touches the `rides` table. |
| `gitaway/familydb_social.py` | The forks and saves tables (F-041); `familydb` appends `SOCIAL_TABLES` to `FAMILY_TABLES`. |
| `gitaway/familydb_import.py` | The `trip_imports` table (F-042): one validated template per imported trip, confirmation numbers included; `familydb.booking_for_trip` reads it back as the booking dict (under `"imported"`). |
| `gitaway/tripimport.py`, `gitaway/importer.py` | Parse `docs/trip-template.md` (safe YAML, line-specific errors), and save the plan as a trip with `source = "imported"`. The screens are `gitaway/pages/tripimport.py`. |

Who is in the family and what each person may do: `docs/family-members.md` (F-043).

## Tables

`members` (display info, the trip each person has open, their remembered workspace picks) · `trips` (title, `source` demo or imported, `params` = `catalog.trip_query`, dates) · `bookings` (the pay flow's picks, one per trip, money in cents) · `activities` and `notes` (the calendar; `gone` is 0 live, 1 last deleted so Undo works; older deletions are removed from the file) · `cal_state` (per trip and scope: the last id number, whether Mom's scripted add has happened) · `push_subscriptions` (F-066, migration 002: one row per phone with the morning plan on: the push address and keys, the chosen time, the day it was last sent; managed only by `gitaway/morning.py`) · `thread` (F-070: a trip's family thread, oldest first by rowid: `kind` message, change or photo, the author's id and first name, text, a JSON `payload`; written only by `gitaway/familythread.py` and, for change cards, by the plan writes in `gitaway/tripcal.py` and `gitaway/importer.py` in their own transaction) · `thread_prefs` (F-070: per person, `quiet`, the last thread push time and how many updates are waiting) · `friends` (per trip) · `rides` (per family and set of picks, so every member sees them) · `forks`, `saves` (F-041) · `trip_imports` (F-042: the document of an imported trip; its flights, hotel and car are read from it, never copied into `bookings`; confirmation numbers exist only here and are drawn only on the calendar's booking detail and `/trip/details`).

`geo_cache` (F-068, `gitaway/geo.py`, made when a family is first opened): where each place is (`kind` place; `found` 0 means the geocoder has no such place) and how long each drive takes with its route line (`kind` drive), so every place and drive is asked of the public services once per family. A failed call is never stored. **What leaves the server:** to OpenStreetMap's Nominatim only the place text of a stop (a hotel's name and address, a car desk, or a plan's title plus the trip's destination, e.g. "Griffith Observatory, Los Angeles"), and to OSRM only pairs of coordinates; never a member's name, a confirmation number, a note or a phone number. Plan titles are looked up because that is what puts plans on the map; a title that is really a note ("call Mom") is sent too and simply comes back not found. Nominatim gets at most one request a second, and both services are left alone for ten minutes after a 429 or 403.

A trip belongs to the family, not to a person. Each member has their own *open* trip (`members.trip_id`; the family's newest until they choose). Booking different picks makes another trip; paying the same picks again opens the trip they made. The calendar's trip switcher is `POST /trips/switch`.

## Opening it

`familydb.family_db(request_or_session)` returns the handle (the caller closes it); `familydb.using(session)` is the same as a `with` block and gives `None` when signed out or not a member. Both go through fh-saas `require_tenant_access`, so membership is checked on every open. A Request is accepted for routes; the model modules take the session. Signed out, nothing opens a database: the demo workspace and pay sheet work without one.

## Schema changes: register on open, migrate later

- **Baseline = register on open.** The first time a family is opened in a process, `register_tables` creates any missing table from `FAMILY_TABLES` and `create_indexes` the indexes. It is idempotent, so a new table is one line: `familydb.FAMILY_TABLES.append((Model, "name", "pk"))` (and `FAMILY_INDEXES`).
- **Changes to an existing table = `utils_migrate`.** Add `migrations/family/NNN_description.sql` with `-- UP --` and `-- DOWN --`. Pending migrations are applied to each family the first time it is opened after a deploy (lazily, one family at a time, no big loop over every tenant). Keep them additive; a destructive one needs a deliberate, dry-run-first script.
- `register_tables` never alters an existing table, which is why changes are migrations.

## Two people at once

Every change is one short transaction on its own rows, never a read-modify-write of a whole document. A write that reads first (calendar validation, id counters, booking idempotency) starts with a write statement (`familydb.lock`), which takes SQLite's write lock, so the reads after it are current; the second writer waits (busy timeout 5 s). WAL mode keeps readers out of the way. Edits to different fields of one activity both survive (`update_activity` writes only the fields it was given). Ids come from `cal_state.q` inside that transaction, so two people adding at once get different ids.

## One worker

The write lock and the host-database lock (`gitaway/hostdb.py`) are per process. Run one worker (one process) per data folder, or add a cross-process file lock before a multi-worker deploy; SQLite's own file locking keeps the data safe, but the in-process serialisation of fh-saas's shared host connection does not reach other processes.

## Which trip a request works on

Every calendar, voice, forks-apply and ride form carries a hidden `trip` (the trip the page was drawn for), and `calendar.js` sends it with its moves, deletes and live adds. `session.family` resolves it against the family's own trips; only a plain GET with no `trip` uses the person's open trip (`members.trip_id`). A write naming a trip the family does not have changes nothing, so a stale tab cannot write into the trip someone else opened since.

## Limits (a demo family stays small)

`MAX_TRIPS` 20 per family, `MAX_ACTIVITIES` 400 and `MAX_NOTES` 800 per trip, 6 friends per trip, `MAX_RIDES` 40 per family (and at most one live ride per leg per trip). Each refusal is a friendly message.

## Tests

`tests/test_signin.py`: `person(traveler)` is a session dict signed in as the dev sign-in does it (a real person with a family database behind it), `stored_booking()` and `stored_calendar()` read what the database holds. `tests/conftest.py` and `tests_browser/conftest.py` empty the family tables of the families the test opened (`familydb.take_opened`, which survives `forget_schema_cache`) and the community database after each test; `tests/test_wipe.py` covers it. `tests/test_family_storage.py` covers restart, two members, several trips, concurrency and migrations.
