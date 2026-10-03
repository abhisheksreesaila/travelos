-- UP --
CREATE TABLE IF NOT EXISTS push_subscriptions (
  endpoint TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  at_min INTEGER NOT NULL DEFAULT 450,
  enabled INTEGER NOT NULL DEFAULT 1,
  last_sent TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
-- DOWN --
DROP TABLE push_subscriptions;
