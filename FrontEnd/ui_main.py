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
		self.history_tab = self._build_history_tab()
		self.stack.addWidget(self.timer_tab)
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
		self.history_table.setColumnCount(5)
		self.history_table.setHorizontalHeaderLabels([
			"Date", "Start (UTC)", "End (UTC)", "Duration", "Subject"
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


	def _get_sessions(self):
		with session_repo.connect() as conn:
			cur = conn.execute(
				"SELECT local_date, start_utc, end_utc, duration_sec, subject FROM sessions ORDER BY start_utc DESC"
			)
			return [dict(row) for row in cur.fetchall()]
