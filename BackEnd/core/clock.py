from datetime import datetime, timezone, timedelta

def utc_now_iso():
	"""Return current UTC time as ISO8601 string (no microseconds)."""
	return datetime.utcnow().replace(tzinfo=timezone.utc, microsecond=0).isoformat()

def local_today_str():
	"""Return local date as YYYY-MM-DD string."""
	return datetime.now().date().isoformat()

def fmt_hms(seconds: int) -> str:
	"""Format seconds as HH:MM:SS."""
	h = seconds // 3600
	m = (seconds % 3600) // 60
	s = seconds % 60
	return f"{h:02}:{m:02}:{s:02}"
