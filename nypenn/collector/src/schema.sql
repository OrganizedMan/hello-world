-- Transition log: one row per *change* to a train's live state, not per poll.
-- Debugging and lead-time analysis only; purged on a rolling window.
CREATE TABLE IF NOT EXISTS observations (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  observed_at   TEXT    NOT NULL,          -- ISO 8601 UTC
  train_id      TEXT    NOT NULL,
  service_date  TEXT    NOT NULL,          -- YYYY-MM-DD, 03:00 ET cutoff
  line          TEXT    NOT NULL,
  destination   TEXT    NOT NULL,
  scheduled_dep TEXT    NOT NULL,
  track         TEXT,                      -- NULL until NJT posts it
  status        TEXT,
  seconds_late  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_obs_purge ON observations (observed_at);
CREATE INDEX IF NOT EXISTS idx_obs_train ON observations (train_id, service_date);

-- The asset. One row per train per service day, kept forever.
-- This is the only table the predictor reads.
CREATE TABLE IF NOT EXISTS departures (
  train_id        TEXT NOT NULL,
  service_date    TEXT NOT NULL,
  line            TEXT NOT NULL,
  line_code       TEXT NOT NULL DEFAULT '',
  destination     TEXT NOT NULL,
  scheduled_dep   TEXT NOT NULL,
  final_track     TEXT,                    -- NULL if never posted before the train left the board
  track_posted_at TEXT,                    -- first sighting of a non-empty track
  seconds_late    INTEGER NOT NULL DEFAULT 0,
  resolved_at     TEXT NOT NULL,
  PRIMARY KEY (train_id, service_date)
);

-- Predictor's read path: "history for this train, most recent first".
CREATE INDEX IF NOT EXISTS idx_dep_train_date
  ON departures (train_id, service_date DESC);

-- Fallback path: "history for this line".
CREATE INDEX IF NOT EXISTS idx_dep_line_date
  ON departures (line, service_date DESC);

-- Single-row collector heartbeat, so the server can report liveness
-- without the two processes sharing memory.
CREATE TABLE IF NOT EXISTS collector_state (
  id            INTEGER PRIMARY KEY CHECK (id = 1),
  last_poll_at  TEXT,
  last_error    TEXT,
  last_error_at TEXT,
  poll_count    INTEGER NOT NULL DEFAULT 0
);

INSERT OR IGNORE INTO collector_state (id, poll_count) VALUES (1, 0);

-- Live board snapshot, overwritten each poll. Lets the server serve the
-- board without calling NJT itself, and survives a server restart.
CREATE TABLE IF NOT EXISTS live_board (
  train_id      TEXT PRIMARY KEY,
  service_date  TEXT NOT NULL,
  line          TEXT NOT NULL,
  line_code     TEXT NOT NULL DEFAULT '',
  destination   TEXT NOT NULL,
  scheduled_dep TEXT NOT NULL,
  track         TEXT,
  status        TEXT,
  seconds_late  INTEGER NOT NULL DEFAULT 0,
  -- Carried here as well as in `departures` so a collector restart mid-day
  -- does not lose when the track was first posted.
  track_posted_at TEXT,
  updated_at    TEXT NOT NULL
);
