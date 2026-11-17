-- UP --
ALTER TABLE matrix_payments ADD COLUMN hotel_address TEXT NOT NULL DEFAULT '';
-- DOWN --
ALTER TABLE matrix_payments DROP COLUMN hotel_address;
