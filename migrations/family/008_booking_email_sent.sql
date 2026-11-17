-- UP --
ALTER TABLE matrix_bookings ADD COLUMN booked_email_at TEXT NOT NULL DEFAULT '';
-- DOWN --
ALTER TABLE matrix_bookings DROP COLUMN booked_email_at;
