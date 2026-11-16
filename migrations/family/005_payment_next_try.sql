-- UP --
ALTER TABLE matrix_payments ADD COLUMN next_try_at TEXT NOT NULL DEFAULT '';
-- DOWN --
ALTER TABLE matrix_payments DROP COLUMN next_try_at;
