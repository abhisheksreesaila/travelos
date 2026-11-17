-- UP --
ALTER TABLE matrix_bookings ADD COLUMN cancel_email_at TEXT NOT NULL DEFAULT '';
-- DOWN --
ALTER TABLE matrix_bookings DROP COLUMN cancel_email_at;
