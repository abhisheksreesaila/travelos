# Family database migrations

See docs/family-db.md. Files here are fh-saas `utils_migrate` migrations, `NNN_description.sql`, each with `-- UP --` and `-- DOWN --`.
They are applied to each family database the first time it is opened after a deploy. Migrations are applied lazily, when a family is first opened, which assumes one worker process (see docs/family-db.md "One worker"). `001_trip_timezone.sql` adds `trips.timezone` (F-057). The tables in
`gitaway/familydb.py` are the baseline and are made when a family database is first opened.
