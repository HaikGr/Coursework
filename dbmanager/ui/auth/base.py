"""The frame shared by the sign-in, sign-up and forgot-password windows."""

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QVBoxLayout,
    QWidget
)

from dbmanager.ui.common.animated_background import AnimatedBackground
from dbmanager.ui.common.icons import EYE_CLOSED, EYE_OPEN, app_icon, svg_icon
from dbmanager.ui.common.transitions import WindowTransition

APP_DESCRIPTION = "Visualize, manage, and optimize your databases\nwith powerful ERD tools and real-time collaboration"
APP_FEATURES = ["✔ Interactive ERD Builder", "✔ Table Relationships"]

INPUT_STYLE = """
    QLineEdit {
        background: white;
        border: 2px solid transparent;
        border-radius: 24px;
        padding: 12px 20px;
        font-size: 16px;
        color: #4B5563;
    }
    QLineEdit:focus { border: 2px solid #93B9E8; }
"""

LINK_BUTTON_STYLE = "color:#3B82F6; background:transparent; border:none;"


def primary_button_style(radius, font_size):
    return f"""
        QPushButton {{
            background-color: #3479f3;
            color: white;
            font-size: {font_size}px;
            border-radius: {radius}px;
            font-weight: bold;
        }}
        QPushButton:hover {{ background-color: #7BA3D0; }}
    """


class PasswordField(QWidget):
    """A password input with an eye button that shows/hides the text."""

    def __init__(self, placeholder, width, height, style, toggle_size, icon_size, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setStyleSheet("background: transparent;")

        self.field = QLineEdit(self)
        self.field.setGeometry(0, 0, width, height)
        self.field.setPlaceholderText(placeholder)
        self.field.setEchoMode(QLineEdit.EchoMode.Password)
        self.field.setStyleSheet(style)

        self.toggle = QPushButton(self)
        self.toggle.setGeometry(width - toggle_size - 12, (height - toggle_size) // 2, toggle_size, toggle_size)
        self.toggle.setIcon(svg_icon(EYE_CLOSED))
        self.toggle.setIconSize(QSize(icon_size, icon_size))
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggle.setToolTip("Show / hide password")
        self.toggle.setStyleSheet("QPushButton { color: black; border: none; background: transparent; }")
        self.toggle.clicked.connect(self.toggle_visibility)

    def toggle_visibility(self):
        hidden = self.field.echoMode() == QLineEdit.EchoMode.Password
        self.field.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self.toggle.setIcon(svg_icon(EYE_OPEN if hidden else EYE_CLOSED))

    def text(self):
        return self.field.text()

    def clear(self):
        self.field.clear()


class AuthWindow(QMainWindow):
    """Animated blue background, the app description on the left and a card on the right.
    Subclasses fill self.card_layout."""

    def __init__(self, window_title, card_height, card_margins, card_spacing,
                 description=APP_DESCRIPTION, features=APP_FEATURES,
                 parent_window=None, geometry=None, fade_duration=350):
        super().__init__()
        self.setWindowTitle(window_title)
        self.setWindowIcon(app_icon())
        self.setStyleSheet("background-color: #3B82F6;")
        self.parent_window = parent_window
        self.fade_duration = fade_duration
        if geometry:
            self.restoreGeometry(geometry)
        self.setMinimumSize(1200, 700)

        self.animated_bg = AnimatedBackground(self)
        self.setCentralWidget(self.animated_bg)

        content = QWidget(self.animated_bg)
        content.setStyleSheet("background-color: transparent;")
        container_layout = QHBoxLayout(content)
        container_layout.setContentsMargins(60, 60, 60, 60)
        container_layout.setSpacing(50)
        container_layout.addLayout(self._build_info(description, features), stretch=2)
        container_layout.addWidget(self._build_card(card_height, card_margins, card_spacing), stretch=1)

        main_layout = QVBoxLayout(self.animated_bg)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(content)

        self._first_show = True

    @staticmethod
    def _build_info(description, features):
        left = QVBoxLayout()
        left.setContentsMargins(0, 160, 0, 0)
        left.setSpacing(25)

        title = QLabel("Database\nManagement")
        title.setStyleSheet("color: white; font-size: 48px; font-weight: bold;")
        left.addWidget(title)

        desc = QLabel(description)
        desc.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 18px;")
        desc.setWordWrap(True)
        left.addWidget(desc)

        for feature in features:
            label = QLabel(feature)
            label.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 16px;")
            left.addWidget(label)
        left.addStretch()
        return left

    def _build_card(self, height, margins, spacing):
        card = QWidget()
        card.setFixedSize(380, height)
        card.setStyleSheet("background-color: #C5D9F5; border-radius: 40px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        self.card_layout = QVBoxLayout(card)
        self.card_layout.setContentsMargins(*margins)
        self.card_layout.setSpacing(spacing)
        return card

    def add_heading(self, text, font_size, subtitle=None):
        heading = QLabel(text)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet(f"font-size: {font_size}px; color: #4B5563; font-weight: bold;")
        self.card_layout.addWidget(heading)
        if subtitle:
            plain_text = QLabel(subtitle)
            plain_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            plain_text.setStyleSheet("font-size: 15px; color: #838b99;")
            self.card_layout.addWidget(plain_text)

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.setWindowOpacity(0.0)
            QTimer.singleShot(50, lambda: WindowTransition.fade_in(self, duration=self.fade_duration))

    def go_back(self):
        if self.parent_window:
            WindowTransition.cross_fade(self, self.parent_window, duration=450)
        else:
            self.close()
