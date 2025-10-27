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
		painter.setRenderHint(QPainter.Antialiasing)
		pen = QPen(QColor("#1E3A56"))
		pen.setWidth(3)
		pen.setCapStyle(Qt.RoundCap)
		painter.setPen(pen)
		# draw three centered horizontal lines with small vertical padding
		for y in [14, 25, 36]:
			painter.drawLine(10, y, 40, y)
		painter.end()
		self.menu_btn.setIcon(QIcon(icon_pixmap))
		self.menu_btn.setIconSize(icon_pixmap.size())

		# --- Sidebar (hidden by default) ---
		self.sidebar = QListWidget()
		self.sidebar.setFixedWidth(240)
		# vertical spacing between items
		self.sidebar.setSpacing(16)
		self.sidebar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.sidebar.addItem(QListWidgetItem("Timer"))
		self.sidebar.addItem(QListWidgetItem("Pomodoro"))
		self.sidebar.addItem(QListWidgetItem("Study History"))
		self.sidebar.addItem(QListWidgetItem("To-Do"))
		self.sidebar.setCurrentRow(0)
		self.sidebar.setMaximumWidth(0)
		self.sidebar.setVisible(False)
		self._sidebar_open = False

		# Ensure the sidebar items start below the fixed Menu Button so they
		# don't overlap. Compute top padding based on the menu button height
		# so the first tab visually aligns with the bottom edge of the button.
		try:
			menu_h = self.menu_btn.height() if hasattr(self, 'menu_btn') else 50
			# small extra gap so items don't touch the button
			top_padding = menu_h + 8
			# Apply widget-local stylesheet so we don't override global theme
			self.sidebar.setStyleSheet(
				f"QListWidget {{ padding-top: {top_padding}px; }}"
				+ "QListWidget::item { padding: 12px 0 12px 32px; margin: 0 0 12px 0; }"
			)
		except Exception:
			# Fallback: small padding
			self.sidebar.setStyleSheet("QListWidget { padding-top: 64px; }")

		# --- Sidebar Animation ---
		from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QTimer
		self.sidebar_anim = QPropertyAnimation(self.sidebar, b"maximumWidth")
		# smooth slide duration for open/close
		self.sidebar_anim.setDuration(220)
		self.sidebar_anim.setEasingCurve(QEasingCurve.InOutCubic)

		# --- Layout ---
		from PySide6.QtWidgets import QSpacerItem, QSizePolicy
		topbar = QHBoxLayout()
		topbar.setContentsMargins(0, 0, 0, 0)
		topbar.setSpacing(0)
		# Reserve horizontal space for the fixed-position Menu Button so the
		# topbar content aligns correctly while the button remains anchored.
		topbar.addSpacing(self.menu_btn.width())
		topbar.addStretch()
		topbar_frame = QWidget()
		topbar_frame.setLayout(topbar)
		
		# Build main content: sidebar on left (full height) and a right-side
		# content widget that contains the topbar and the stacked pages.
		self.stack = QStackedWidget()
		self.timer_tab = self._build_timer_tab()
		self.pomodoro_tab = self._build_pomodoro_tab()
		self.history_tab = self._build_history_tab()
		self.todo_tab = self._build_todo_tab()
		self.stack.addWidget(self.timer_tab)
		self.stack.addWidget(self.pomodoro_tab)
		self.stack.addWidget(self.history_tab)
		self.stack.addWidget(self.todo_tab)

		main_layout = QHBoxLayout()
		main_layout.setContentsMargins(0, 0, 0, 0)
		main_layout.setSpacing(0)

		# Right-side container holds topbar at the very top and the pages below it
		content_widget = QWidget()
		content_layout = QVBoxLayout()
		content_layout.setContentsMargins(0, 0, 0, 0)
		content_layout.setSpacing(0)
		content_layout.addWidget(topbar_frame)
		content_layout.addWidget(self.stack)
		content_widget.setLayout(content_layout)

		main_layout.addWidget(self.sidebar)
		main_layout.addWidget(content_widget)

		container = QWidget()
		container.setLayout(main_layout)
		self.setCentralWidget(container)

		self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
		self.menu_btn.clicked.connect(self._toggle_sidebar)

		# Make the menu button a fixed-position child so it stays anchored
		# at the top-left regardless of layout changes.
		self.menu_btn.setParent(container)
		self.menu_btn.move(0, 0)
		self.menu_btn.raise_()

		# Install event filters for hover interactions
		from PySide6.QtCore import QEvent, QTimer
		self.menu_btn.installEventFilter(self)
		self.sidebar.installEventFilter(self)

		# Close timer: short delay to allow mouse moving between button and sidebar
		self._sidebar_close_timer = QTimer(self)
		self._sidebar_close_timer.setSingleShot(True)
		self._sidebar_close_timer.setInterval(200)
		self._sidebar_close_timer.timeout.connect(self._maybe_close_sidebar)

		# Opacity effect for subtle fade during open/close
		from PySide6.QtWidgets import QGraphicsOpacityEffect
		from PySide6.QtCore import QPropertyAnimation
		self._sidebar_opacity = QGraphicsOpacityEffect(self.sidebar)
		self.sidebar.setGraphicsEffect(self._sidebar_opacity)
		self._sidebar_op_anim = QPropertyAnimation(self._sidebar_opacity, b"opacity")
		self._sidebar_op_anim.setDuration(180)
		# start hidden
		self._sidebar_opacity.setOpacity(0.0)

	def closeEvent(self, event):
		# On close: detect running or paused timers (main timer and pomodoro),
		# persist their elapsed seconds to the DB and mark sessions stopped so
		# they aren't treated as active on next start. Also save a lightweight
		# Pomodoro UI snapshot for informational purposes (no auto-resume).
		try:
			from BackEnd.repos import session_repo
			# ---- Main timer handling ----
			svc = getattr(self, 'timer_service', None)
			if svc is not None:
				try:
					running = bool(getattr(svc, 'running', False))
					paused = bool(getattr(svc, 'paused', False))
					elapsed = int(getattr(svc, 'elapsed_sec', 0) or 0)
					sid = getattr(svc, 'session_id', None)
					# If timer is running, pause it first to stop QTimer
					if running and not paused:
						try:
							svc.pause_resume()
						except Exception:
							pass
					# Persist elapsed and stop session (if any)
					if sid is not None:
						try:
							session_repo.update_elapsed(sid, elapsed)
							session_repo.stop_session(sid)
						except Exception:
							pass
					else:
						# No session id - but there is elapsed time: create+finalize a session
						if elapsed > 0:
							try:
								new_id = session_repo.start_session(source='timer')
								session_repo.update_elapsed(new_id, elapsed)
								session_repo.stop_session(new_id)
							except Exception:
								pass
				except Exception:
					pass
			# ---- Pomodoro handling ----
			try:
				p_sid = getattr(self, 'pomo_session_id', None)
				p_elapsed = int(getattr(self, 'pomo_elapsed', 0) or 0)
				# If there's an open pomodoro DB session, persist and stop it
				if p_sid is not None:
					try:
						session_repo.update_elapsed(p_sid, p_elapsed)
						session_repo.stop_session(p_sid)
					except Exception:
						pass
			except Exception:
				pass
		except Exception:
			# If the repo import or DB ops fail, don't block closing
			pass
		# Save Pomodoro UI snapshot for informational display on next start
		try:
			if hasattr(self, '_save_pomodoro_state'):
				self._save_pomodoro_state()
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
		# On startup, load any saved pomodoro UI snapshot so the user can
		# see the previous state, but do not prompt or auto-resume.
		state = self._load_pomodoro_state()
		if not state:
			return
		# Restore values into the UI but keep timers stopped.
		self.pomo_phase = state.get('pomo_phase', 'study')
		self.pomo_elapsed = int(state.get('pomo_elapsed', 0) or 0)
		self.pomo_cycle_count = int(state.get('pomo_cycle_count', 0) or 0)
		self.pomo_session_id = state.get('pomo_session_id')
		# determine target for phase
		if self.pomo_phase == 'study':
			self.pomo_target = self.POMO_STUDY_SEC
		else:
			self.pomo_target = state.get('pomo_target', self.POMO_SHORT_BREAK_SEC)
		# update timer label to reflect saved elapsed but do NOT start
		remaining = max(0, self.pomo_target - self.pomo_elapsed)
		mins = remaining // 60
		secs = remaining % 60
		self.pomo_timer_label.setText(f"{mins:02d}:{secs:02d}")
		self.pomo_phase_label.setText('Study Session' if self.pomo_phase == 'study' else 'Break Session')
		self.pomo_running = False
		self.pomo_start_btn.setText('Start')
		# remove saved snapshot now that we've reflected it in the UI
		try:
			path = self._pomodoro_state_path()
			if path.exists():
				path.unlink()
		except Exception:
			pass

	def _toggle_sidebar(self):
		# Toggle using the centralized open/close helpers so opacity and
		# delayed close behavior are consistent.
		if not self._sidebar_open:
			self._open_sidebar()
		else:
			self._close_sidebar()

	def _hide_sidebar(self):
		self.sidebar.setVisible(False)
		# Only disconnect if we connected
		if getattr(self, '_sidebar_anim_connected', False):
			try:
				self.sidebar_anim.finished.disconnect(self._hide_sidebar)
			except TypeError:
				pass
			self._sidebar_anim_connected = False

	def _open_sidebar(self):
		if not self._sidebar_open:
			self.sidebar.setVisible(True)
			# slide open
			self.sidebar_anim.stop()
			self.sidebar_anim.setStartValue(self.sidebar.maximumWidth())
			self.sidebar_anim.setEndValue(240)
			# fade in
			self._sidebar_op_anim.stop()
			self._sidebar_op_anim.setStartValue(self._sidebar_opacity.opacity())
			self._sidebar_op_anim.setEndValue(1.0)
			self._sidebar_op_anim.start()
			self.sidebar_anim.start()
			self._sidebar_open = True

	def _close_sidebar(self):
		if self._sidebar_open:
			# slide closed
			self.sidebar_anim.stop()
			self.sidebar_anim.setStartValue(self.sidebar.maximumWidth())
			self.sidebar_anim.setEndValue(0)
			# fade out
			self._sidebar_op_anim.stop()
			self._sidebar_op_anim.setStartValue(self._sidebar_opacity.opacity())
			self._sidebar_op_anim.setEndValue(0.0)
			self._sidebar_op_anim.start()
			if not getattr(self, '_sidebar_anim_connected', False):
				self.sidebar_anim.finished.connect(self._hide_sidebar)
				self._sidebar_anim_connected = True
			self.sidebar_anim.start()
			self._sidebar_open = False

	def _maybe_close_sidebar(self):
		# only close if mouse isn't over the menu button or the sidebar
		try:
			if not (self.menu_btn.underMouse() or self.sidebar.underMouse()):
				self._close_sidebar()
		except Exception:
			self._close_sidebar()

	def eventFilter(self, obj, event):
		from PySide6.QtCore import QEvent
		# Hover enter on menu button -> open sidebar
		if obj is self.menu_btn:
			if event.type() == QEvent.Enter:
				self._sidebar_close_timer.stop()
				self._open_sidebar()
				return False
			if event.type() == QEvent.Leave:
				self._sidebar_close_timer.start()
				return False
		# Hover enter/leave on sidebar: cancel/start close timer
		if obj is self.sidebar:
			if event.type() == QEvent.Enter:
				self._sidebar_close_timer.stop()
				return False
			if event.type() == QEvent.Leave:
				self._sidebar_close_timer.start()
				return False
		# Resize on the todo_list viewport -> update item widths
		if hasattr(self, 'todo_list') and obj is self.todo_list.viewport():
			if event.type() == QEvent.Resize:
				# keep items sized to viewport
				try:
					self._update_todo_item_widths()
				except Exception:
					pass
				return False
		return super().eventFilter(obj, event)

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

		# Removed Today footer for a minimal Timer page (layout remains centered)

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
		# Do not prompt to resume previous sessions; previous timer/pomodoro
		# data is persisted on close but we will not offer to continue it.
		# Leave timers idle on startup.

		return w

	def _build_history_tab(self):
		w = QWidget()
		layout = QVBoxLayout()
		layout.setAlignment(Qt.AlignmentFlag.AlignTop)
		# Match margins used elsewhere for consistent visual rhythm
		layout.setContentsMargins(32, 32, 32, 32)

		# Time frame selector - place it at the right side for better balance.
		timeframe_layout = QHBoxLayout()
		# Push widgets to the right
		timeframe_layout.addStretch()
		timeframe_label = QLabel("Show study time for:")
		self.timeframe_combo = QComboBox()
		self.timeframe_combo.addItems(["Week", "Month"])
		self.timeframe_combo.setCurrentIndex(0)  # Default to Week
		self.timeframe_combo.setMinimumWidth(140)
		# Avoid hard-coded colors here so the global Calm theme controls text color
		# Add widgets (label first, then combo) so they appear right-aligned.
		timeframe_layout.addWidget(timeframe_label)
		timeframe_layout.addWidget(self.timeframe_combo)
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

	def _build_todo_tab(self):
		from PySide6.QtWidgets import QListWidget, QListWidgetItem, QHBoxLayout, QLineEdit, QMenu, QInputDialog
		from PySide6.QtGui import QIcon
		from PySide6.QtCore import Qt

		w = QWidget()
		outer = QVBoxLayout()
		outer.setContentsMargins(32, 32, 32, 32)
		outer.setSpacing(12)

		# Title
		title = QLabel("To-Do")
		title.setStyleSheet("font-size:20px; font-weight:600; color: #1E3A56;")
		# Center the title horizontally above the list
		outer.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)

		# Task list (QListWidget with custom widgets)
		self.todo_list = QListWidget()
		self.todo_list.setObjectName("TodoList")
		self.todo_list.setSpacing(8)
		self.todo_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
		self.todo_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		# Watch the viewport for resize so we can update item widths
		self.todo_list.viewport().installEventFilter(self)

		# Container that will host the list and the Add box; this is the
		# single visible box centered on the page (rounded + shadow).
		list_container = QWidget()
		list_container.setObjectName("TodoContainer")
		list_container_layout = QVBoxLayout()
		list_container_layout.setContentsMargins(12, 12, 12, 12)
		list_container_layout.setSpacing(8)
		list_container.setLayout(list_container_layout)

		# Ensure moderate width (~65% of initial window width)
		try:
			list_container.setMaximumWidth(int(self.width() * 0.65))
		except Exception:
			list_container.setMaximumWidth(700)

		list_container_layout.addWidget(self.todo_list)
		def make_task_widget(text, checked=False):
			container = QWidget()
			container.setObjectName("TodoItem")
			lay = QHBoxLayout()
			lay.setContentsMargins(12, 12, 12, 12)
			lay.setSpacing(12)

			# Check circle
			check_btn = QPushButton()
			check_btn.setCheckable(True)
			check_btn.setFixedSize(20, 20)
			check_btn.setObjectName("TodoCheck")
			check_btn.setChecked(bool(checked))

			# Make each task item a bit taller so items read as "length > height"
			container.setMinimumHeight(64)

			# Label
			lbl = QLabel(text)
			lbl.setWordWrap(True)
			lbl.setObjectName("TodoLabel")
			font = lbl.font()
			font.setPointSize(14)
			lbl.setFont(font)
			if checked:
				f = lbl.font()
				f.setStrikeOut(True)
				lbl.setFont(f)

			# Spacer and menu
			lay.addWidget(check_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
			lay.addWidget(lbl)
			lay.addStretch()
			menu_btn = QPushButton("\u22EE")
			menu_btn.setObjectName("TodoMenuBtn")
			menu_btn.setCursor(Qt.PointingHandCursor)
			menu_btn.setFixedSize(28, 28)
			lay.addWidget(menu_btn, alignment=Qt.AlignmentFlag.AlignTop)

			container.setLayout(lay)

			# connect check toggle
			def on_toggle(checked_state):
				fnt = lbl.font()
				fnt.setStrikeOut(bool(checked_state))
				lbl.setFont(fnt)
				# dim completed items a bit
				if checked_state:
					lbl.setStyleSheet("color: rgba(30,58,86,0.45);")
				else:
					lbl.setStyleSheet("color: #1E3A56;")

			check_btn.toggled.connect(on_toggle)

			# menu actions
			menu = QMenu()
			edit_act = menu.addAction("Edit Task")
			del_act = menu.addAction("Delete Task")

			def on_menu_clicked():
				action = menu.exec_(menu_btn.mapToGlobal(menu_btn.rect().bottomLeft()))
				if action == edit_act:
					new_text, ok = QInputDialog.getText(self, "Edit Task", "Task:", text=lbl.text())
					if ok and new_text.strip():
						lbl.setText(new_text.strip())
				elif action == del_act:
					# find and remove the corresponding QListWidgetItem
					for i in range(self.todo_list.count()):
						item = self.todo_list.item(i)
						iw = self.todo_list.itemWidget(item)
						# itemWidget may be a wrapper; check wrapper or its child
						if iw is container or (iw is not None and iw.findChild(QWidget, 'TodoItem') is container):
							self.todo_list.takeItem(i)
							break

			menu_btn.clicked.connect(on_menu_clicked)

			return container

		# Clickable Add Task box (placed inside the list container)
		self.todo_add_box = QLineEdit()
		self.todo_add_box.setObjectName("TodoAddBox")
		self.todo_add_box.setPlaceholderText("Add task")
		self.todo_add_box.setFixedHeight(48)
		# Make the Add box a reasonable width (centered). We'll size tasks
		# to match this box so they are not cut off.
		try:
			add_w = int(list_container.maximumWidth() * 0.5)
		except Exception:
			add_w = 320
		self.todo_add_box.setFixedWidth(add_w)
		list_container_layout.addWidget(self.todo_add_box, alignment=Qt.AlignmentFlag.AlignHCenter)
		# When user presses Enter, add task
		def add_task_from_box():
			text = self.todo_add_box.text().strip()
			if not text:
				return
			item = QListWidgetItem()
			widget = make_task_widget(text, checked=False)
			# Size the task widget to match the Add box / viewport width so it won't be cut off
			# Prefer the Add box width but don't exceed viewport
			try:
				avail_w = min(self.todo_add_box.width(), self.todo_list.viewport().width())
			except Exception:
				avail_w = self.todo_add_box.width()
			# set maximum width so the widget layout doesn't overflow the viewport
			widget.setMaximumWidth(max(100, avail_w))
			# Wrap the task widget in a centered wrapper so it aligns with Add box
			wrapper = QWidget()
			wrap_layout = QHBoxLayout()
			wrap_layout.setContentsMargins(0, 0, 0, 0)
			wrap_layout.addStretch()
			wrap_layout.addWidget(widget)
			wrap_layout.addStretch()
			wrapper.setLayout(wrap_layout)
			from PySide6.QtCore import QSize
			item.setSizeHint(QSize(max(100, avail_w), max(96, widget.sizeHint().height())))
			self.todo_list.addItem(item)
			self.todo_list.setItemWidget(item, wrapper)
			self._update_todo_item_widths()
			self.todo_add_box.clear()

		self.todo_add_box.returnPressed.connect(add_task_from_box)

		# Center the list container vertically and horizontally
		outer.addStretch()
		outer.addWidget(list_container, alignment=Qt.AlignmentFlag.AlignHCenter)
		outer.addStretch()

		w.setLayout(outer)
		# Start with an empty task list by default (no starter tasks)

		return w

	def _update_todo_item_widths(self):
		# Ensure all task widgets match the Add box width (and viewport) so
		# they are never visually cut off.
		try:
			avail = min(self.todo_add_box.width(), self.todo_list.viewport().width())
		except Exception:
			return
		for i in range(self.todo_list.count()):
			item = self.todo_list.item(i)
			wrapper = self.todo_list.itemWidget(item)
			if wrapper is None:
				continue
			# find the actual TodoItem child
			inner = None
			if wrapper.objectName() == 'TodoItem':
				inner = wrapper
			else:
				inner = wrapper.findChild(QWidget, 'TodoItem')
			if inner is None:
				# fallback: adjust wrapper size
				inner = wrapper
			inner.setMaximumWidth(max(100, avail))
			from PySide6.QtCore import QSize
			item.setSizeHint(QSize(max(100, avail), max(96, inner.sizeHint().height())))


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
		# Resume prompts are disabled. Previously unfinished sessions are
		# persisted on close; we will not offer to resume them here.
		return


