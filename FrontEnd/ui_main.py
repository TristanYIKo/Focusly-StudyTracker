from PySide6.QtWidgets import (
	QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QListWidget,
	QStackedWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QSizePolicy
)
from PySide6.QtCore import Qt
from BackEnd.services.timer_service import TimerService
from BackEnd.repos import session_repo
from BackEnd.core.clock import fmt_hms

class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Study Tracker")
		self.resize(1000, 600)

		# Sidebar navigation
		self.sidebar = QListWidget()
		self.sidebar.setFixedWidth(140)
		self.sidebar.setSpacing(8)
		self.sidebar.setStyleSheet("font-size: 16px; font-weight: 500;")
		self.sidebar.addItem(QListWidgetItem("⏱ Timer"))
		self.sidebar.addItem(QListWidgetItem("📚 Study History"))
		self.sidebar.setCurrentRow(0)

		# Stacked widget for tab content
		self.stack = QStackedWidget()
		self.timer_tab = self._build_timer_tab()
		self.history_tab = self._build_history_tab()
		self.stack.addWidget(self.timer_tab)
		self.stack.addWidget(self.history_tab)

		# Layout
		main_layout = QHBoxLayout()
		main_layout.addWidget(self.sidebar)
		main_layout.addWidget(self.stack)
		container = QWidget()
		container.setLayout(main_layout)
		self.setCentralWidget(container)

		self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)

	def _build_timer_tab(self):
		w = QWidget()
		layout = QVBoxLayout()
		layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

		self.timer_label = QLabel("00:00:00")
		self.timer_label.setStyleSheet("font-size: 56px; font-weight: bold; margin: 32px;")
		self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

		self.today_label = QLabel("Today: 0m")
		self.today_label.setStyleSheet("font-size: 22px; margin-bottom: 24px;")
		self.today_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

		btn_layout = QHBoxLayout()
		self.start_btn = QPushButton("Start")
		self.pause_btn = QPushButton("Pause")
		self.resume_btn = QPushButton("Resume")
		self.stop_btn = QPushButton("Stop")
		for btn in (self.start_btn, self.pause_btn, self.resume_btn, self.stop_btn):
			btn.setMinimumWidth(120)
			btn.setMinimumHeight(40)
			btn.setStyleSheet("font-size: 18px;")
			btn_layout.addWidget(btn)

		layout.addWidget(self.timer_label)
		layout.addWidget(self.today_label)
		layout.addLayout(btn_layout)
		w.setLayout(layout)

		# Timer logic
		self.timer_service = TimerService()
		self.timer_service.tick.connect(self._on_tick)
		self.timer_service.state_changed.connect(self._on_state)
		self._update_today_label()

		self.start_btn.clicked.connect(self._start)
		self.pause_btn.clicked.connect(self._pause)
		self.resume_btn.clicked.connect(self._resume)
		self.stop_btn.clicked.connect(self._stop)

		self._set_buttons("stopped")
		self.timer_service.resume_active_session()
		if self.timer_service.running:
			self._set_buttons("running")
			self._on_tick(self.timer_service.elapsed_sec)

		return w

	def _build_history_tab(self):
		w = QWidget()
		layout = QVBoxLayout()
		layout.setAlignment(Qt.AlignmentFlag.AlignTop)

		self.history_table = QTableWidget()
		self.history_table.setColumnCount(5)
		self.history_table.setHorizontalHeaderLabels([
			"Date", "Start (UTC)", "End (UTC)", "Duration", "Subject"
		])
		self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
		self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
		self.history_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		layout.addWidget(self.history_table)
		w.setLayout(layout)
		self._refresh_history()
		return w

	def _on_tick(self, elapsed):
		self.timer_label.setText(fmt_hms(elapsed))

	def _on_state(self, state):
		self._set_buttons(state)
		if state == "stopped":
			self._update_today_label()
			self._refresh_history()

	def _set_buttons(self, state):
		self.start_btn.setEnabled(state in ("stopped",))
		self.pause_btn.setEnabled(state == "running")
		self.resume_btn.setEnabled(state == "paused")
		self.stop_btn.setEnabled(state in ("running", "paused"))

	def _start(self):
		self.timer_service.start()
		self._set_buttons("running")

	def _pause(self):
		self.timer_service.pause()
		self._set_buttons("paused")

	def _resume(self):
		self.timer_service.resume()
		self._set_buttons("running")

	def _stop(self):
		self.timer_service.stop()
		self._set_buttons("stopped")

	def _update_today_label(self):
		total_sec = session_repo.today_total_seconds()
		self.today_label.setText(f"Today: {total_sec // 60}m")

	def _refresh_history(self):
		sessions = self._get_sessions()
		self.history_table.setRowCount(len(sessions))
		for row, sess in enumerate(sessions):
			self.history_table.setItem(row, 0, QTableWidgetItem(sess["local_date"]))
			self.history_table.setItem(row, 1, QTableWidgetItem(sess["start_utc"]))
			self.history_table.setItem(row, 2, QTableWidgetItem(sess["end_utc"] or ""))
			dur = fmt_hms(sess["duration_sec"] or 0) if sess["duration_sec"] is not None else ""
			self.history_table.setItem(row, 3, QTableWidgetItem(dur))
			self.history_table.setItem(row, 4, QTableWidgetItem(sess["subject"] or ""))

	def _get_sessions(self):
		with session_repo.connect() as conn:
			cur = conn.execute(
				"SELECT local_date, start_utc, end_utc, duration_sec, subject FROM sessions ORDER BY start_utc DESC"
			)
			return [dict(row) for row in cur.fetchall()]
