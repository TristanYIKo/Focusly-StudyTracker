from PySide6.QtCore import QObject, Signal, QTimer
from BackEnd.repos import session_repo

class TimerService(QObject):
	tick = Signal(int)  # emits elapsed seconds
	state_changed = Signal(str)  # emits 'running', 'paused', 'stopped'

	def __init__(self):
		super().__init__()
		self.running = False
		self.paused = False
		self.elapsed_sec = 0
		self.session_id = None
		self._timer = QTimer()
		self._timer.setInterval(1000)
		self._timer.timeout.connect(self._on_tick)

	def start(self):
		if self.running:
			return
		self.session_id = session_repo.start_session()
		self.elapsed_sec = 0
		self.running = True
		self.paused = False
		self._timer.start()
		self.state_changed.emit('running')

	def pause(self):
		if not self.running or self.paused:
			return
		self._timer.stop()
		self.paused = True
		self.state_changed.emit('paused')

	def resume(self):
		if not self.running or not self.paused:
			return
		self._timer.start()
		self.paused = False
		self.state_changed.emit('running')

	def stop(self):
		if not self.running:
			return
		self._timer.stop()
		if self.session_id is not None:
			session_repo.stop_session(self.session_id)
		self.running = False
		self.paused = False
		self.session_id = None
		self.state_changed.emit('stopped')

	def _on_tick(self):
		self.elapsed_sec += 1
		self.tick.emit(self.elapsed_sec)

	def resume_active_session(self):
		"""If there's an active session in DB, resume it and set elapsed_sec."""
		active = session_repo.active_session()
		if active:
			from datetime import datetime, timezone
			start_utc = active['start_utc']
			start_dt = datetime.fromisoformat(start_utc)
			now = datetime.now(timezone.utc)
			self.elapsed_sec = int((now - start_dt).total_seconds())
			self.session_id = active['id']
			self.running = True
			self.paused = False
			self._timer.start()
			self.state_changed.emit('running')
