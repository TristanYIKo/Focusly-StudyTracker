from PySide6.QtWidgets import (
	QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
	QStackedWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QSizePolicy, QComboBox
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import datetime
from PySide6.QtCore import Qt
from BackEnd.services.timer_service import TimerService
from BackEnd.repos import session_repo
from BackEnd.core.clock import fmt_hms
from FrontEnd.styles.design_tokens import COLORS, FONTS
from FrontEnd.components.footer_today import FooterToday

class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Study Tracker")
		self.resize(1000, 650)

		# Apply QSS stylesheet for the new design system
		with open('FrontEnd/styles/studytracker.qss', 'r', encoding='utf-8') as f:
			self.setStyleSheet(f.read())

		# --- Menu Button (Hamburger) ---
		self.menu_btn = QPushButton()
		self.menu_btn.setObjectName("MenuButton")
		self.menu_btn.setFixedSize(50, 50)
		self.menu_btn.setCursor(Qt.PointingHandCursor)
		self.menu_btn.setStyleSheet("margin: 0; padding: 0; border: none;")
		# Draw hamburger icon
		from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
		icon_pixmap = QPixmap(50, 50)
		icon_pixmap.fill(Qt.transparent)
		painter = QPainter(icon_pixmap)
		pen = QPen(QColor("#133c62"))
		pen.setWidth(4)
		painter.setPen(pen)
		for y in [12, 20, 28]:
			painter.drawLine(20, y, 50, y)
		painter.end()
		self.menu_btn.setIcon(QIcon(icon_pixmap))
		self.menu_btn.setIconSize(icon_pixmap.size())

		# --- Sidebar (hidden by default) ---
		self.sidebar = QListWidget()
		self.sidebar.setFixedWidth(240)
		self.sidebar.setSpacing(16)
		self.sidebar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.sidebar.addItem(QListWidgetItem("Timer"))
		self.sidebar.addItem(QListWidgetItem("Pomodoro"))
		self.sidebar.addItem(QListWidgetItem("Study History"))
		self.sidebar.setCurrentRow(0)
		self.sidebar.setMaximumWidth(0)
		self.sidebar.setVisible(False)
		self._sidebar_open = False

		# --- Sidebar Animation ---
		from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QTimer
		self.sidebar_anim = QPropertyAnimation(self.sidebar, b"maximumWidth")
		self.sidebar_anim.setDuration(10)
		self.sidebar_anim.setEasingCurve(QEasingCurve.InOutCubic)

		# --- Layout ---
		from PySide6.QtWidgets import QSpacerItem, QSizePolicy
		topbar = QHBoxLayout()
		topbar.setContentsMargins(0, 0, 0, 0)
		topbar.setSpacing(0)
		topbar.addWidget(self.menu_btn, alignment=Qt.AlignmentFlag.AlignLeft)
		topbar.addStretch()
		topbar_frame = QWidget()
		topbar_frame.setLayout(topbar)
		

		self.stack = QStackedWidget()
		self.timer_tab = self._build_timer_tab()
		self.pomodoro_tab = self._build_pomodoro_tab()
		self.history_tab = self._build_history_tab()
		self.stack.addWidget(self.timer_tab)
		self.stack.addWidget(self.pomodoro_tab)
		self.stack.addWidget(self.history_tab)

		main_layout = QHBoxLayout()
		main_layout.setContentsMargins(0, 0, 0, 0)
		main_layout.setSpacing(0)
		main_layout.addWidget(self.sidebar)
		main_layout.addWidget(self.stack)
		container = QWidget()
		vbox = QVBoxLayout()
		vbox.setContentsMargins(0, 0, 0, 0)
		vbox.setSpacing(0)
		vbox.addWidget(topbar_frame)
		vbox.addLayout(main_layout)
		container.setLayout(vbox)
		self.setCentralWidget(container)

		self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
		self.menu_btn.clicked.connect(self._toggle_sidebar)

	def closeEvent(self, event):
		# Ensure running timer is paused and persisted when app closes so resume restores exact time
		try:
			if hasattr(self, 'timer_service') and self.timer_service.running:
				# pause the timer (stops QTimer) and mark paused
				if not self.timer_service.paused:
					self.timer_service.pause_resume()
				# persist current elapsed seconds
				try:
					from BackEnd.repos import session_repo
					if self.timer_service.session_id is not None:
						session_repo.update_elapsed(self.timer_service.session_id, self.timer_service.elapsed_sec)
				except Exception:
					pass
		except Exception:
			pass
		super().closeEvent(event)

	def _pomodoro_state_path(self):
		from BackEnd.core.paths import user_data_dir
		return user_data_dir() / "pomodoro_state.json"

	def _save_pomodoro_state(self):
		"""Persist current pomodoro UI state to disk so it can be resumed across app restarts."""
		import json
		path = self._pomodoro_state_path()
		state = {
			"pomo_phase": getattr(self, 'pomo_phase', 'study'),
			"pomo_elapsed": getattr(self, 'pomo_elapsed', 0),
			"pomo_cycle_count": getattr(self, 'pomo_cycle_count', 0),
			"pomo_running": bool(getattr(self, 'pomo_running', False)),
			"pomo_session_id": getattr(self, 'pomo_session_id', None),
			"pomo_target": getattr(self, 'pomo_target', None),
		}
		try:
			path.parent.mkdir(parents=True, exist_ok=True)
			with open(path, 'w', encoding='utf-8') as f:
				json.dump(state, f)
		except Exception:
			pass

	def _load_pomodoro_state(self):
		import json
		path = self._pomodoro_state_path()
		if not path.exists():
			return None
		try:
			with open(path, 'r', encoding='utf-8') as f:
				state = json.load(f)
			return state
		except Exception:
			return None

	def _prompt_resume_pomodoro_if_needed(self):
		# Called at startup after UI built
		state = self._load_pomodoro_state()
		if not state:
			return
		# if there was an active pomodoro running when app closed, ask to continue
		if state.get('pomo_running'):
			from PySide6.QtWidgets import QMessageBox
			msg = QMessageBox(self)
			msg.setWindowTitle("Resume Pomodoro?")
			msg.setText("A Pomodoro was running when you closed the app. Do you want to continue it?")
			msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
			msg.setDefaultButton(QMessageBox.Yes)
			ret = msg.exec()
			# restore state into UI and either start or keep paused based on answer
			self.pomo_phase = state.get('pomo_phase', 'study')
			self.pomo_elapsed = int(state.get('pomo_elapsed', 0) or 0)
			self.pomo_cycle_count = int(state.get('pomo_cycle_count', 0) or 0)
			self.pomo_session_id = state.get('pomo_session_id')
			# determine target for phase
			if self.pomo_phase == 'study':
				self.pomo_target = self.POMO_STUDY_SEC
			else:
				self.pomo_target = self.POMO_LONG_BREAK_SEC if state.get('pomo_target') == self.POMO_LONG_BREAK_SEC else self.POMO_SHORT_BREAK_SEC
			# update timer label
			remaining = max(0, self.pomo_target - self.pomo_elapsed)
			mins = remaining // 60
			secs = remaining % 60
			self.pomo_timer_label.setText(f"{mins:02d}:{secs:02d}")
			self.pomo_phase_label.setText('Study Session' if self.pomo_phase == 'study' else 'Break Session')
			if ret == QMessageBox.Yes:
				# start running from exact elapsed
				self.pomo_running = True
				self.pomo_start_btn.setText('Pause')
				self.pomo_timer.start()
			else:
				# keep stopped but reflect saved time
				self.pomo_running = False
				self.pomo_start_btn.setText('Start')
			# clear saved state file once restored
			try:
				path = self._pomodoro_state_path()
				if path.exists():
					path.unlink()
			except Exception:
				pass

	def _toggle_sidebar(self):
		if not self._sidebar_open:
			self.sidebar.setVisible(True)
			self.sidebar_anim.stop()
			self.sidebar_anim.setStartValue(self.sidebar.maximumWidth())
			self.sidebar_anim.setEndValue(240)
			self.sidebar_anim.start()
			self._sidebar_open = True
			self._sidebar_anim_connected = False
		else:
			self.sidebar_anim.stop()
			self.sidebar_anim.setStartValue(self.sidebar.maximumWidth())
			self.sidebar_anim.setEndValue(0)
			# Only connect if not already connected
			if not getattr(self, '_sidebar_anim_connected', False):
				self.sidebar_anim.finished.connect(self._hide_sidebar)
				self._sidebar_anim_connected = True
			self.sidebar_anim.start()
			self._sidebar_open = False

	def _hide_sidebar(self):
		self.sidebar.setVisible(False)
		# Only disconnect if we connected
		if getattr(self, '_sidebar_anim_connected', False):
			try:
				self.sidebar_anim.finished.disconnect(self._hide_sidebar)
			except TypeError:
				pass
			self._sidebar_anim_connected = False

	def _build_timer_tab(self):
		w = QWidget()
		outer = QVBoxLayout()
		outer.setContentsMargins(32, 32, 32, 32)
		outer.setSpacing(0)
		outer.addStretch()

		# Timer card
		timer_card = QWidget()
		timer_card_layout = QVBoxLayout()
		timer_card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
		timer_card.setLayout(timer_card_layout)
		timer_card.setObjectName("TimerCard")

		self.timer_label = QLabel("00:00:00")
		self.timer_label.setObjectName("TimerLabel")
		self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		timer_card_layout.addWidget(self.timer_label)

		# Buttons row
		btn_layout = QHBoxLayout()
		btn_layout.setSpacing(24)
		self.start_pause_btn = QPushButton("Start Session")
		self.start_pause_btn.setObjectName("StartBtn")
		self.end_btn = QPushButton("End Session")
		self.end_btn.setObjectName("EndBtn")
		for btn in (self.start_pause_btn, self.end_btn):
			btn.setMinimumHeight(56)
			btn_layout.addWidget(btn)
		timer_card_layout.addSpacing(24)
		timer_card_layout.addLayout(btn_layout)

		outer.addWidget(timer_card, alignment=Qt.AlignmentFlag.AlignHCenter)
		outer.addStretch()

		# Today pill footer
		self.footer_today = FooterToday("Today: 0m")
		outer.addWidget(self.footer_today, alignment=Qt.AlignmentFlag.AlignRight)

		w.setLayout(outer)

		# Timer logic
		self.timer_service = TimerService()
		self.timer_service.tick.connect(self._on_tick)
		self.timer_service.state_changed.connect(self._on_state)
		self._update_today_label()

		self.start_pause_btn.clicked.connect(self._start_pause)
		self.end_btn.clicked.connect(self._end)

		self._set_buttons("idle")
		self._pending_resume_check = False
		self._check_resume_session()
		# If there is a saved pomodoro state, prompt to restore after UI is ready
		self._prompt_resume_pomodoro_if_needed()

		return w

	def _build_history_tab(self):
		w = QWidget()
		layout = QVBoxLayout()
		layout.setAlignment(Qt.AlignmentFlag.AlignTop)

		# Time frame selector
		timeframe_layout = QHBoxLayout()
		timeframe_label = QLabel("Show study time for:")
		self.timeframe_combo = QComboBox()
		self.timeframe_combo.addItems(["Week", "Month"])
		self.timeframe_combo.setCurrentIndex(0)  # Default to Week
		self.timeframe_combo.setMinimumWidth(140)
		self.timeframe_combo.setStyleSheet("color: #fff;")
		timeframe_label.setStyleSheet("color: #fff;")
		timeframe_layout.addWidget(timeframe_label)
		timeframe_layout.addWidget(self.timeframe_combo)
		timeframe_layout.addStretch()
		layout.addLayout(timeframe_layout)

		# Bar chart (matplotlib)
		self.figure = Figure(figsize=(5, 2.5))
		self.canvas = FigureCanvas(self.figure)
		layout.addWidget(self.canvas)

		# Table
		self.history_table = QTableWidget()
		self.history_table.setColumnCount(6)
		self.history_table.setHorizontalHeaderLabels([
			"Date", "Start (UTC)", "End (UTC)", "Duration", "Subject", "Source"
		])
		self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
		self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
		self.history_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		layout.addWidget(self.history_table)
		w.setLayout(layout)
		self.timeframe_combo.currentIndexChanged.connect(self._update_bar_chart)
		self._refresh_history()
		self._update_bar_chart()
		return w

	def _build_pomodoro_tab(self):
		w = QWidget()
		outer = QVBoxLayout()
		outer.setContentsMargins(32, 32, 32, 32)
		outer.setSpacing(0)
		outer.addStretch()

		# Pomodoro card (match Timer style)
		p_card = QWidget()
		p_layout = QVBoxLayout()
		p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
		p_card.setLayout(p_layout)
		p_card.setObjectName("TimerCard")

		self.pomo_phase_label = QLabel("Study Session")
		self.pomo_phase_label.setObjectName("PomoPhaseLabel")
		self.pomo_phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		p_layout.addWidget(self.pomo_phase_label)

		self.pomo_timer_label = QLabel("25:00")
		self.pomo_timer_label.setObjectName("TimerLabel")
		self.pomo_timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		p_layout.addWidget(self.pomo_timer_label)

		# Buttons row: Start/Pause centered, Skip on right
		controls = QHBoxLayout()
		controls.setSpacing(24)
		controls.addStretch()
		self.pomo_start_btn = QPushButton("Start")
		self.pomo_start_btn.setObjectName("StartBtn")
		self.pomo_start_btn.setMinimumHeight(56)
		controls.addWidget(self.pomo_start_btn, alignment=Qt.AlignmentFlag.AlignCenter)
		self.pomo_skip_btn = QPushButton("Skip Session")
		self.pomo_skip_btn.setObjectName("EndBtn")
		self.pomo_skip_btn.setMinimumHeight(56)
		controls.addWidget(self.pomo_skip_btn, alignment=Qt.AlignmentFlag.AlignRight)

		p_layout.addSpacing(24)
		p_layout.addLayout(controls)

		outer.addWidget(p_card, alignment=Qt.AlignmentFlag.AlignHCenter)
		outer.addStretch()

		w.setLayout(outer)

		# Pomodoro parameters (adjustable variables)
		self.POMO_STUDY_SEC = 25 * 60
		self.POMO_SHORT_BREAK_SEC = 5 * 60
		self.POMO_LONG_BREAK_SEC = 15 * 60
		self.POMO_CYCLES = 4

		# Runtime state
		self.pomo_phase = 'study'  # 'study' or 'break'
		self.pomo_cycle_count = 0
		self.pomo_elapsed = 0
		self.pomo_running = False
		self.pomo_session_id = None

		from PySide6.QtCore import QTimer
		self.pomo_timer = QTimer(self)
		self.pomo_timer.setInterval(1000)
		self.pomo_timer.timeout.connect(self._pomo_tick)

		self.pomo_start_btn.clicked.connect(self._pomo_start_pause)
		self.pomo_skip_btn.clicked.connect(self._pomo_skip)

		# initialize display
		self._pomo_enter_phase('study', autostart=False)

		return w

	def _pomo_start_pause(self):
		if not self.pomo_running:
			# start or resume
			self.pomo_running = True
			self.pomo_start_btn.setText('Pause')
			# if starting a study session, open DB session
			if self.pomo_phase == 'study' and self.pomo_session_id is None:
				self.pomo_session_id = session_repo.start_session(source='pomodoro')
			self.pomo_timer.start()
		else:
			# pause
			self.pomo_running = False
			self.pomo_start_btn.setText('Resume')
			self.pomo_timer.stop()
			# If we paused during a study session, end and save it
			if self.pomo_phase == 'study' and self.pomo_session_id is not None:
				try:
					session_repo.stop_session(self.pomo_session_id)
				except Exception:
					pass
				self.pomo_session_id = None
				# update UI and graphs
				self._update_today_label()
				self._refresh_history()
				if hasattr(self, '_update_bar_chart'):
					self._update_bar_chart()

	def _pomo_skip(self):
		# Skip to next phase immediately
		self.pomo_timer.stop()
		self.pomo_running = False
		self.pomo_start_btn.setText('Start')
		# if skipping from study, end DB session
		if self.pomo_phase == 'study' and self.pomo_session_id is not None:
			try:
				session_repo.stop_session(self.pomo_session_id)
			except Exception:
				pass
			self.pomo_session_id = None
			# update UI and graphs
			self._update_today_label()
			self._refresh_history()
			if hasattr(self, '_update_bar_chart'):
				self._update_bar_chart()
		# Advance to next phase
		if self.pomo_phase == 'study':
			self.pomo_cycle_count += 1
			# decide break length
			if self.pomo_cycle_count % self.POMO_CYCLES == 0:
				self._pomo_enter_phase('break', long=True)
			else:
				self._pomo_enter_phase('break', long=False)
		else:
			self._pomo_enter_phase('study')

	def _pomo_tick(self):
		self.pomo_elapsed += 1
		remaining = self._pomo_current_duration() - self.pomo_elapsed
		if remaining < 0:
			# phase finished
			if self.pomo_phase == 'study':
				# end DB session
				if self.pomo_session_id is not None:
					try:
						session_repo.stop_session(self.pomo_session_id)
					except Exception:
						pass
					self.pomo_session_id = None
					# update UI and graphs
					self._update_today_label()
					self._refresh_history()
					if hasattr(self, '_update_bar_chart'):
						self._update_bar_chart()
				self.pomo_cycle_count += 1
				# auto-enter break
				if self.pomo_cycle_count % self.POMO_CYCLES == 0:
					self._pomo_enter_phase('break', long=True)
				else:
					self._pomo_enter_phase('break', long=False)
			else:
				# break finished -> start next study
				self._pomo_enter_phase('study')
		else:
			# update label
			mins = remaining // 60
			secs = remaining % 60
			self.pomo_timer_label.setText(f"{mins:02d}:{secs:02d}")

	def _pomo_current_duration(self):
		if self.pomo_phase == 'study':
			return self.POMO_STUDY_SEC
		else:
			# break: long or short determined at entry by elapsed target stored in pomo_target
			return getattr(self, 'pomo_target', self.POMO_SHORT_BREAK_SEC)

	def _pomo_enter_phase(self, phase, long=False, autostart=True):
		# phase: 'study' or 'break'
		self.pomo_phase = phase
		self.pomo_elapsed = 0
		if phase == 'study':
			self.pomo_phase_label.setText('Study Session')
			self.pomo_target = self.POMO_STUDY_SEC
			self.pomo_timer_label.setText(f"{self.POMO_STUDY_SEC//60:02d}:00")
			# prepare DB session (only start when user presses start)
			self.pomo_session_id = None
		else:
			self.pomo_phase_label.setText('Break Session')
			self.pomo_target = self.POMO_LONG_BREAK_SEC if long else self.POMO_SHORT_BREAK_SEC
			self.pomo_timer_label.setText(f"{self.pomo_target//60:02d}:00")

		# autostart next phase if desired
		if autostart:
			# start timer automatically for smooth transitions
			self.pomo_running = True
			self.pomo_start_btn.setText('Pause')
			if phase == 'study':
				# start a DB session immediately for accurate study tracking
				self.pomo_session_id = session_repo.start_session(source='pomodoro')
			self.pomo_timer.start()
		else:
			self.pomo_running = False
			self.pomo_start_btn.setText('Start')

	def _update_bar_chart(self):
		import calendar
		import sqlite3
		from BackEnd.core.paths import db_path
		tf = self.timeframe_combo.currentText().lower()
		now = datetime.datetime.now()
		dbfile = db_path()
		conn = sqlite3.connect(dbfile)
		conn.row_factory = sqlite3.Row
		x = []
		y = []
		xlabel = ""
		# No 'Today' option; only handle 'week' and 'month'
		if tf == "week":
			# Show hours studied for each day of current week (Mon-Sun)
			# Find Monday of current week
			start_of_week = now - datetime.timedelta(days=now.weekday())
			days = [(start_of_week + datetime.timedelta(days=i)).date() for i in range(7)]
			x = [d.strftime("%a") for d in days]
			y = [0]*7
			day_strs = [d.isoformat() for d in days]
			cur = conn.execute(f"""
				SELECT local_date, SUM(duration_sec) as total_sec
				FROM sessions
				WHERE local_date IN ({','.join(['?']*7)}) AND duration_sec IS NOT NULL
				GROUP BY local_date
			""", day_strs)
			totals = {row["local_date"]: row["total_sec"] or 0 for row in cur.fetchall()}
			for i, d in enumerate(day_strs):
				y[i] = (totals.get(d, 0) or 0) / 3600
			xlabel = "Day of Week"
		else:
			# Show hours studied for each day of current month
			year = now.year
			month = now.month
			num_days = calendar.monthrange(year, month)[1]
			days = [datetime.date(year, month, i+1) for i in range(num_days)]
			x = [str(d.day) for d in days]
			y = [0]*num_days
			day_strs = [d.isoformat() for d in days]
			cur = conn.execute(f"""
				SELECT local_date, SUM(duration_sec) as total_sec
				FROM sessions
				WHERE local_date IN ({','.join(['?']*num_days)}) AND duration_sec IS NOT NULL
				GROUP BY local_date
			""", day_strs)
			totals = {row["local_date"]: row["total_sec"] or 0 for row in cur.fetchall()}
			for i, d in enumerate(day_strs):
				y[i] = (totals.get(d, 0) or 0) / 3600
			xlabel = "Day of Month"
		conn.close()
		self.figure.clear()
		ax = self.figure.add_subplot(111)
		ax.bar(x, y, color="#5EA1FF")
		ax.set_ylabel("Hours Studied")
		ax.set_xlabel(xlabel)
		ax.set_title(f"Study Time by {xlabel}")
		ax.set_ylim(bottom=0)
		self.figure.tight_layout()
		self.canvas.draw()


	def _on_tick(self, elapsed):
		self.timer_label.setText(fmt_hms(elapsed))
		# Optionally: pulse or brighten timer card when running

	def _on_state(self, state):
		self._set_buttons(state)
		if state in ("idle", "stopped"):
			self.timer_label.setText("00:00:00")
			self._update_today_label()
			self._refresh_history()


	def _set_buttons(self, state):
		# Only two buttons: Start/Pause and End
		if state == "idle":
			self.start_pause_btn.setEnabled(True)
			self.start_pause_btn.setText("Start Session")
			self.end_btn.setEnabled(False)
		elif state == "running":
			self.start_pause_btn.setEnabled(True)
			self.start_pause_btn.setText("Pause")
			self.end_btn.setEnabled(True)
		elif state == "paused":
			self.start_pause_btn.setEnabled(True)
			self.start_pause_btn.setText("Resume")
			self.end_btn.setEnabled(True)
		else:
			self.start_pause_btn.setEnabled(True)
			self.start_pause_btn.setText("Start Session")
			self.end_btn.setEnabled(False)

	def _start_pause(self):
		# Use running/paused attributes from TimerService
		if not self.timer_service.running:
			self.timer_service.start()
			self._set_buttons("running")
		elif self.timer_service.running and not self.timer_service.paused:
			self.timer_service.pause_resume()
			self._set_buttons("paused")
		elif self.timer_service.running and self.timer_service.paused:
			self.timer_service.pause_resume()
			self._set_buttons("running")

	def _end(self):
		self.timer_service.stop()
		self._set_buttons("idle")

	def _update_today_label(self):
		total_sec = session_repo.today_total_seconds()
		if hasattr(self, 'footer_today'):
			self.footer_today.set_today(f"Today: {total_sec // 60}m")

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
			# Source: 'timer' or 'pomodoro'
			self.history_table.setItem(row, 5, QTableWidgetItem(sess.get("source", "timer")))

	def _get_sessions(self):
		with session_repo.connect() as conn:
			cur = conn.execute(
				"SELECT local_date, start_utc, end_utc, duration_sec, subject, source FROM sessions ORDER BY start_utc DESC"
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


