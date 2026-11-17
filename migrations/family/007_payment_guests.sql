-- UP --
ALTER TABLE matrix_payments ADD COLUMN guests TEXT NOT NULL DEFAULT '';
-- DOWN --
ALTER TABLE matrix_payments DROP COLUMN guests;
