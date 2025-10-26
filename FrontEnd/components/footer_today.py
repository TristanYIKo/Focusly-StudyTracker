from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from FrontEnd.styles.design_tokens import COLORS, FONTS

class FooterToday(QWidget):
    def __init__(self, today_text):
        super().__init__()
        layout = QHBoxLayout()
        layout.addStretch()
        self.label = QLabel(today_text)
        self.label.setObjectName("TodayLabel")
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.setStyleSheet(f"background: {COLORS['footer_bg']}; border-radius: 16px; padding: 8px 24px; margin: 0 32px 32px 0; color: {COLORS['footer_text']}; font-size: 16px; font-weight: 500;")
    def set_today(self, text):
        self.label.setText(text)
