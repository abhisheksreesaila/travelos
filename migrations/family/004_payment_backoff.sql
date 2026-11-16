-- UP --
ALTER TABLE matrix_payments ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
-- DOWN --
ALTER TABLE matrix_payments DROP COLUMN attempts;
