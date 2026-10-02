-- UP --
ALTER TABLE trips ADD COLUMN timezone TEXT NOT NULL DEFAULT 'America/Los_Angeles';
-- DOWN --
ALTER TABLE trips DROP COLUMN timezone;
