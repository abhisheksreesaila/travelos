-- UP --
ALTER TABLE matrix_bookings ADD COLUMN hotel_id TEXT NOT NULL DEFAULT '';
-- DOWN --
ALTER TABLE matrix_bookings DROP COLUMN hotel_id;
