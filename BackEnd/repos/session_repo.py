import sqlite3
from pathlib import Path
from BackEnd.core.paths import db_path
from BackEnd.core.clock import utc_now_iso, local_today_str

SCHEMA_PATH = Path(__file__).parent.parent.parent / "SQL" / "schema.sql"

def connect():
	"""Open SQLite connection and ensure schema is applied."""
	dbfile = db_path()
	conn = sqlite3.connect(dbfile)
	conn.row_factory = sqlite3.Row
	with open(SCHEMA_PATH, encoding="utf-8") as f:
		conn.executescript(f.read())
	return conn

def start_session(subject="", note=""):
	"""Start a new session and return session_id."""
	now_utc = utc_now_iso()
	today = local_today_str()
	with connect() as conn:
		cur = conn.execute(
			"""
			INSERT INTO sessions (start_utc, local_date, subject, note, updated_at)
			VALUES (?, ?, ?, ?, ?)
			""",
			(now_utc, today, subject, note, now_utc)
		)
		return cur.lastrowid

def stop_session(session_id):
	"""Stop session, set end_utc, duration_sec, updated_at. Returns duration_sec."""
	now_utc = utc_now_iso()
	with connect() as conn:
		cur = conn.execute(
			"SELECT start_utc FROM sessions WHERE id=? AND end_utc IS NULL", (session_id,))
		row = cur.fetchone()
		if not row:
			return None
		start_utc = row["start_utc"]
		start_dt = sqlite3.datetime.datetime.fromisoformat(start_utc)
		end_dt = sqlite3.datetime.datetime.fromisoformat(now_utc)
		duration = int((end_dt - start_dt).total_seconds())
		conn.execute(
			"""
			UPDATE sessions SET end_utc=?, duration_sec=?, updated_at=? WHERE id=?
			""",
			(now_utc, duration, now_utc, session_id)
		)
		return duration

def active_session():
	"""Return dict for active session (end_utc IS NULL), or None."""
	with connect() as conn:
		cur = conn.execute(
			"SELECT id, start_utc, local_date, subject FROM sessions WHERE end_utc IS NULL ORDER BY start_utc DESC LIMIT 1"
		)
		row = cur.fetchone()
		return dict(row) if row else None

def today_total_seconds():
	"""Sum duration_sec for sessions with local_date = today."""
	today = local_today_str()
	with connect() as conn:
		cur = conn.execute(
			"SELECT COALESCE(SUM(duration_sec),0) as total FROM sessions WHERE local_date=? AND duration_sec IS NOT NULL",
			(today,)
		)
		row = cur.fetchone()
		return row["total"] if row else 0
