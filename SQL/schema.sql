PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
	id INTEGER PRIMARY KEY,
	start_utc TEXT NOT NULL,       -- ISO8601 UTC (no microseconds)
	end_utc   TEXT,                -- null until stopped
	duration_sec INTEGER,          -- set when stopped
	local_date TEXT NOT NULL,      -- YYYY-MM-DD, computed at start from local time
	subject TEXT,
	note TEXT,
	client_id TEXT UNIQUE,         -- reserved for future sync
	updated_at TEXT NOT NULL,      -- UTC ISO, touched on every update
	deleted_at TEXT                -- null; reserved for soft deletes
);

CREATE INDEX IF NOT EXISTS idx_sessions_local_date ON sessions(local_date);
CREATE INDEX IF NOT EXISTS idx_sessions_updated   ON sessions(updated_at);
