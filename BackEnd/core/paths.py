import os
from pathlib import Path

def user_data_dir(app_name="StudyTracker"):
	"""Return per-user data dir (Windows/macOS/Linux)."""
	if os.name == "nt":
		base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
	elif os.name == "posix":
		base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
	else:
		base = os.path.expanduser("~")
	path = Path(base) / app_name
	path.mkdir(parents=True, exist_ok=True)
	return path

def db_path():
	"""Return Path to study.db inside user data dir."""
	return user_data_dir() / "study.db"
