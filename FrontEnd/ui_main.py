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
		self.resize(1000, 650)

		# Soft, cool blue theme with #63A4FF as accent
		self.setStyleSheet("""
			QMainWindow { background: #e6eef7; } /* pastel slate blue */
			QWidget { background: transparent; }
			QListWidget {
				background: #3a5372;
				color: #eaf2fb;
				border: none;
				border-radius: 18px;
				padding: 8px 0;
				margin: 12px 0 12px 12px;
				min-width: 180px;
				max-width: 180px;
			}
			QListWidget::item {
				padding: 18px 0 18px 18px;
				margin: 0 0 8px 0;
				border-radius: 12px;
				background: transparent;
				transition: background 0.2s, box-shadow 0.2s;
			}
			QListWidget::item:hover {
				background: #4a6fa5;
				color: #fff;
				box-shadow: 0 0 8px #63A4FF33;
			}
			QListWidget::item:selected {
				background: #63A4FF;
				color: #fff;
				box-shadow: 0 0 16px #63A4FF55;
				border: 2px solid #eaf2fb;
			}
			QLabel#TodayLabel {
				color: #b2c3d9;
				font-size: 14px;
				font-weight: 500;
				margin: 0 0 0 0;
				opacity: 0.7;
			}
			QLabel#TimerLabel {
				color: #f8fafd;
				font-size: 68px;
				font-weight: 700;
				background: #63A4FF;
				border-radius: 24px;
				padding: 32px 60px;
				margin: 0 0 18px 0;
				letter-spacing: 2px;
				box-shadow: 0 2px 24px #63A4FF22;
			}
			QPushButton {
				border-radius: 16px;
				font-size: 20px;
				font-weight: 600;
				padding: 12px 0;
				min-width: 160px;
				min-height: 52px;
				margin: 0 12px;
				background: #dbe7f3;
				color: #3a5372;
				box-shadow: 0 2px 12px #63A4FF11;
				border: none;
				transition: background 0.2s, color 0.2s;
			}
			QPushButton#StartBtn {
				background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #63A4FF, stop:1 #4a90e2);
				color: #fff;
				box-shadow: 0 2px 16px #63A4FF33;
			}
			QPushButton#StartBtn:pressed, QPushButton#StartBtn:hover {
				background: #4a90e2;
			}
			QPushButton#PauseResumeBtn {
				background: #7db7ff;
				color: #fff;
			}
			QPushButton#PauseResumeBtn:pressed, QPushButton#PauseResumeBtn:hover {
				background: #63A4FF;
			}
			QPushButton#EndBtn {
				background: #cfd8e6;
				color: #3a5372;
			}
			QPushButton#EndBtn:pressed, QPushButton#EndBtn:hover {
				background: #b2c3d9;
			}
			QTableWidget {
				background: #e6eef7;
				color: #3a5372;
				border-radius: 12px;
				font-size: 16px;
			}
		""")

		self.sidebar = QListWidget()
		self.sidebar.setFixedWidth(180)
		self.sidebar.setSpacing(12)
		self.sidebar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.sidebar.setStyleSheet("font-size: 20px; font-weight: 600; border: none; background: #3a5372; border-radius: 18px; padding: 8px 0; margin: 12px 0 12px 12px;")
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
		self.timer_label.setObjectName("TimerLabel")
		self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

		btn_layout = QHBoxLayout()
		self.start_btn = QPushButton("Start Session")
		self.start_btn.setObjectName("StartBtn")
		self.pause_resume_btn = QPushButton("Pause")
		self.pause_resume_btn.setObjectName("PauseResumeBtn")
		self.end_btn = QPushButton("End Session")
		self.end_btn.setObjectName("EndBtn")
		for btn in (self.start_btn, self.pause_resume_btn, self.end_btn):
			btn.setMinimumWidth(160)
			btn.setMinimumHeight(52)
			btn_layout.addWidget(btn)

		layout.addStretch()
		layout.addWidget(self.timer_label)
		layout.addSpacing(18)
		layout.addLayout(btn_layout)
		layout.addStretch()

		# Today label at bottom right
		today_bar = QHBoxLayout()
		today_bar.addStretch()
		self.today_label = QLabel("Today: 0m")
		self.today_label.setObjectName("TodayLabel")
		today_bar.addWidget(self.today_label)
		layout.addLayout(today_bar)

		w.setLayout(layout)

		# Timer logic
		self.timer_service = TimerService()
		self.timer_service.tick.connect(self._on_tick)
		self.timer_service.state_changed.connect(self._on_state)
		self._update_today_label()

		self.start_btn.clicked.connect(self._start)
		self.pause_resume_btn.clicked.connect(self._pause_resume)
		self.end_btn.clicked.connect(self._end)

		self._set_buttons("idle")
		self._pending_resume_check = False
		self._check_resume_session()

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
		if state in ("idle", "stopped"):
			self.timer_label.setText("00:00:00")
			self._update_today_label()
			self._refresh_history()


	def _set_buttons(self, state):
		# Only three buttons: Start, Pause/Resume, End
		self.start_btn.setEnabled(state in ("idle",))
		self.pause_resume_btn.setEnabled(state in ("running", "paused"))
		self.end_btn.setEnabled(state in ("running", "paused"))
		if state == "running":
			self.start_btn.setStyleSheet("")
			self.pause_resume_btn.setText("Pause")
			self.pause_resume_btn.setStyleSheet("")
			self.end_btn.setStyleSheet("")
		elif state == "paused":
			self.pause_resume_btn.setText("Resume")
			self.pause_resume_btn.setStyleSheet("")
			self.end_btn.setStyleSheet("")
			self.start_btn.setStyleSheet("")
		else:
			self.start_btn.setStyleSheet("")
			self.pause_resume_btn.setText("Pause")
			self.pause_resume_btn.setStyleSheet("")
			self.end_btn.setStyleSheet("")

	def _start(self):
		self.timer_service.start()
		self._set_buttons("running")

	def _pause_resume(self):
		self.timer_service.pause_resume()
		if self.timer_service.paused:
			self._set_buttons("paused")
		else:
			self._set_buttons("running")

	def _end(self):
		self.timer_service.stop()
		self._set_buttons("idle")

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

	def _check_resume_session(self):
		# On app start, check for unfinished session and prompt user
		from PySide6.QtWidgets import QMessageBox
		active = session_repo.active_session()
		if active and not self._pending_resume_check:
			self._pending_resume_check = True
			msg = QMessageBox(self)
			msg.setWindowTitle("Resume Session?")
			msg.setText("A session was still running when you closed the app. Do you want to continue it?")
			msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
			msg.setDefaultButton(QMessageBox.Yes)
			ret = msg.exec()
			if ret == QMessageBox.Yes:
				self.timer_service.resume_active_session()
				self._set_buttons("running")
			else:
				confirm = QMessageBox(self)
				confirm.setWindowTitle("End Session?")
				confirm.setText("Are you sure you want to end this session? Your progress will be saved and the timer will reset.")
				confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
				confirm.setDefaultButton(QMessageBox.No)
				ret2 = confirm.exec()
				if ret2 == QMessageBox.Yes:
					self.timer_service.force_end()
					self._set_buttons("idle")
				else:
					self.timer_service.resume_active_session()
					self._set_buttons("running")
			self._pending_resume_check = False

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
