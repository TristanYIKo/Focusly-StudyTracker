from PySide6.QtCore import QObject, Signal, QTimer
from BackEnd.repos import session_repo

class TimerService(QObject):
	tick = Signal(int)  # emits elapsed seconds
	state_changed = Signal(str)  # emits 'idle', 'running', 'paused', 'stopped'

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

	def pause_resume(self):
		if not self.running:
			return
		if self.paused:
			self._timer.start()
			self.paused = False
			self.state_changed.emit('running')
		else:
			self._timer.stop()
			self.paused = True
			self.state_changed.emit('paused')

	def stop(self):
		if not self.running:
			return
		self._timer.stop()
		if self.session_id is not None:
			session_repo.stop_session(self.session_id)
		self.running = False
		self.paused = False
		self.session_id = None
		self.elapsed_sec = 0
		self.state_changed.emit('idle')

	def force_end(self):
		"""Force end session without UI reset (for confirmation dialog)."""
		if self.running and self.session_id is not None:
			self._timer.stop()
			session_repo.stop_session(self.session_id)
			self.running = False
			self.paused = False
			self.session_id = None
			self.elapsed_sec = 0
			self.state_changed.emit('idle')

	def _on_tick(self):
		self.elapsed_sec += 1
		self.tick.emit(self.elapsed_sec)

	def resume_active_session(self, paused: bool = False):
		"""If there's an active session in DB, resume it and set elapsed_sec.

		Backwards-compatible: accepts optional keyword `paused` which, when True,
		restores the session but does not start the internal timer.
		"""
		active = session_repo.active_session()
		if active:
			from datetime import datetime, timezone
			start_utc = active['start_utc']
			start_dt = datetime.fromisoformat(start_utc)
			now = datetime.now(timezone.utc)
			# compute elapsed as fallback; other code may persist elapsed_sec in DB
			self.elapsed_sec = int((now - start_dt).total_seconds())
			self.session_id = active['id']
			self.running = True
			self.paused = bool(paused)
			if not self.paused:
				self._timer.start()
				self.state_changed.emit('running')
			else:
				self._timer.stop()
				self.state_changed.emit('paused')
