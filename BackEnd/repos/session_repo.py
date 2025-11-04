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

	# Migration: ensure new columns exist on older DBs
	cur = conn.execute("PRAGMA table_info(sessions)")
	cols = {r['name'] for r in cur.fetchall()}
	if 'elapsed_sec' not in cols:
		try:
			conn.execute("ALTER TABLE sessions ADD COLUMN elapsed_sec INTEGER")
		except Exception:
			pass
	if 'source' not in cols:
		try:
			conn.execute("ALTER TABLE sessions ADD COLUMN source TEXT DEFAULT 'timer'")
		except Exception:
			pass
	return conn

def start_session(subject="", note="", source="timer"):
	"""Start a new session and return session_id. Source is 'timer' or 'pomodoro'."""
	now_utc = utc_now_iso()
	today = local_today_str()
	with connect() as conn:
		cur = conn.execute(
			"""
			INSERT INTO sessions (start_utc, local_date, subject, note, updated_at, source)
			VALUES (?, ?, ?, ?, ?, ?)
			""",
			(now_utc, today, subject, note, now_utc, source)
		)
		return cur.lastrowid

def update_elapsed(session_id, elapsed_sec):
	"""Update the elapsed_sec and updated_at for an active session (no end_utc)."""
	now = utc_now_iso()
	with connect() as conn:
		conn.execute(
			"UPDATE sessions SET elapsed_sec=?, updated_at=? WHERE id=?",
			(int(elapsed_sec), now, session_id)
		)
		conn.commit()

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
			"SELECT id, start_utc, local_date, subject, source, elapsed_sec FROM sessions WHERE end_utc IS NULL ORDER BY start_utc DESC LIMIT 1"
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

def get_daily_streak():
	"""
	Calculate the current daily streak - consecutive days with study sessions.
	Returns 0 if the user skipped a full day (from 12 AM to 12 AM).
	"""
	import datetime
	today = datetime.date.today()
	with connect() as conn:
		# Get all unique dates with completed sessions, ordered descending
		cur = conn.execute(
			"SELECT DISTINCT local_date FROM sessions WHERE duration_sec IS NOT NULL AND duration_sec > 0 ORDER BY local_date DESC"
		)
		dates = [datetime.date.fromisoformat(row["local_date"]) for row in cur.fetchall()]
	
	if not dates:
		return 0
	
	# Check if today has any study time - if not, streak is 0
	if today not in dates:
		return 0
	
	# Count consecutive days backwards from today
	streak = 0
	current_date = today
	for study_date in dates:
		if study_date == current_date:
			streak += 1
			current_date -= datetime.timedelta(days=1)
		elif study_date < current_date:
			# Gap found - streak broken
			break
	
	return streak

def get_total_days_studied():
	"""
	Returns the total number of unique days the user has studied since using the app.
	"""
	with connect() as conn:
		cur = conn.execute(
			"SELECT COUNT(DISTINCT local_date) as total FROM sessions WHERE duration_sec IS NOT NULL AND duration_sec > 0"
		)
		row = cur.fetchone()
		return row["total"] if row else 0

def get_total_hours_studied():
	"""
	Returns the total hours studied across all sessions since using the app.
	"""
	with connect() as conn:
		cur = conn.execute(
			"SELECT COALESCE(SUM(duration_sec), 0) as total FROM sessions WHERE duration_sec IS NOT NULL AND duration_sec > 0"
		)
		row = cur.fetchone()
		total_seconds = row["total"] if row else 0
		return total_seconds / 3600.0  # Convert to hours
