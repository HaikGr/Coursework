"""The frame shared by the sign-in, sign-up and forgot-password windows."""

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QVBoxLayout,
    QWidget
)

from dbmanager.ui.common.animated_background import AnimatedBackground
from dbmanager.ui.common.icons import EYE_CLOSED, EYE_OPEN, app_icon, svg_icon
from dbmanager.ui.common.live import bind
from dbmanager.ui.common.preferences import PreferencesButtons, changes
from dbmanager.ui.common.theme import color, style, value
from dbmanager.ui.common.transitions import WindowTransition

APP_DESCRIPTION = "auth.description"
APP_FEATURES = ["auth.feature_erd", "auth.feature_relationships"]

# theme.qss templates
INPUT_STYLE = """
    QLineEdit {
        background: @auth_input;
        border: 2px solid transparent;
        border-radius: 24px;
        padding: 12px 20px;
        font-size: 16px;
        color: @auth_input_text;
        selection-background-color: @selection;
        selection-color: @on_selection;
    }
    QLineEdit:focus { border: 2px solid @focus; }
"""

LINK_BUTTON_STYLE = "QPushButton { color: @accent_text; background: transparent; border: none; }"


def primary_button_style(radius, font_size):
    return f"""
        QPushButton {{
            background-color: @accent;
            color: @on_accent;
            font-size: {font_size}px;
            border-radius: {radius}px;
            font-weight: bold;
        }}
        QPushButton:hover {{ background-color: @accent_hover; }}
    """


class PasswordField(QWidget):
    """A password input with an eye button that shows/hides the text."""

    def __init__(self, placeholder, width, height, field_style, toggle_size, icon_size, parent=None, **params):
        """placeholder: a catalogue key, its placeholders in params; field_style: a theme.qss template"""
        super().__init__(parent)
        style(self, "QWidget { background: transparent; }")

        self.field = QLineEdit(self)
        bind(self.field.setPlaceholderText, placeholder, **params)
        self.field.setEchoMode(QLineEdit.EchoMode.Password)
        style(self.field, field_style)
        self.field.setTextMargins(0, 0, toggle_size, 0)  # what is typed stops before the eye button
        # At least as tall as the style makes a line edit, like the plain fields next to it
        self.field.ensurePolished()
        height = max(height, self.field.sizeHint().height())
        self.setFixedSize(width, height)
        self.field.setGeometry(0, 0, width, height)

        self.toggle = QPushButton(self)
        self.toggle.setGeometry(width - toggle_size - 12, (height - toggle_size) // 2, toggle_size, toggle_size)
        self._show_eye()
        self.toggle.setIconSize(QSize(icon_size, icon_size))
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        bind(self.toggle.setToolTip, "auth.show_hide_password")
        style(self.toggle, "QPushButton { border: none; background: transparent; }")
        self.toggle.clicked.connect(self.toggle_visibility)

    def toggle_visibility(self):
        hidden = self.field.echoMode() == QLineEdit.EchoMode.Password
        self.field.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self._show_eye()

    def _show_eye(self):
        """An open eye while the password shows, in the colour of the text; a faint closed one otherwise."""
        shown = self.field.echoMode() == QLineEdit.EchoMode.Normal
        bind(self.toggle.setIcon, lambda: svg_icon(EYE_OPEN.format(stroke=value("auth_input_text")) if shown
                                                   else EYE_CLOSED.format(stroke=value("text_disabled"))))

    def text(self):
        return self.field.text()

    def clear(self):
        self.field.clear()


class AuthWindow(QMainWindow):
    """Animated background, the app description on the left and a card on the right, the language and theme
    pickers in the corner. Subclasses fill self.card_layout. Texts are catalogue keys."""

    def __init__(self, window_title, card_height, card_margins, card_spacing,
                 description=APP_DESCRIPTION, features=APP_FEATURES,
                 parent_window=None, geometry=None, fade_duration=350):
        super().__init__()
        bind(self.setWindowTitle, window_title)
        self.setWindowIcon(app_icon())
        style(self, "QWidget { background-color: @auth_background; }")
        self.parent_window = parent_window
        self.fade_duration = fade_duration
        if geometry:
            self.restoreGeometry(geometry)
        self.setMinimumSize(1000, 660)  # fits a 1366x768 laptop, and 1920x1080 at 150% scaling

        self.animated_bg = AnimatedBackground(self)
        self.setCentralWidget(self.animated_bg)

        content = QWidget(self.animated_bg)
        style(content, "QWidget { background-color: transparent; }")
        container_layout = QHBoxLayout(content)
        container_layout.setContentsMargins(60, 20, 60, 20)  # the card is centred: this only matters when small
        container_layout.setSpacing(50)
        container_layout.addLayout(self._build_info(description, features), stretch=2)
        container_layout.addWidget(self._build_card(card_height, card_margins, card_spacing), stretch=1)

        main_layout = QVBoxLayout(self.animated_bg)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(content)

        # Over the background in the top right corner, where it takes no room from the card
        self.preferences = PreferencesButtons(self.animated_bg)
        self.preferences.raise_()
        self._headings = []  # (label, largest font size), fitted again when the language changes
        changes.changed.connect(self._place_preferences)  # a language's names are wider or narrower
        changes.changed.connect(self._fit_headings)

        self._first_show = True

    @staticmethod
    def _build_info(description, features):
        left = QVBoxLayout()
        left.setContentsMargins(0, 160, 0, 0)
        left.setSpacing(25)

        title = QLabel()
        bind(title.setText, "auth.brand_title")
        style(title, "QLabel { color: @on_brand; font-size: 48px; font-weight: bold; }")
        left.addWidget(title)

        desc = QLabel()
        bind(desc.setText, description)
        style(desc, "QLabel { color: @on_brand_muted; font-size: 18px; }")
        desc.setWordWrap(True)
        left.addWidget(desc)

        for feature in features:
            label = QLabel()
            bind(label.setText, feature)
            style(label, "QLabel { color: @on_brand_muted; font-size: 16px; }")
            left.addWidget(label)
        left.addStretch()
        return left

    def _build_card(self, height, margins, spacing):
        card = QWidget()
        card.setFixedSize(380, height)
        style(card, "QWidget { background-color: @auth_card; border-radius: 40px; }")

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        bind(shadow.setColor, lambda: color("shadow", alpha=120))
        card.setGraphicsEffect(shadow)

        self.card_layout = QVBoxLayout(card)
        self.card_layout.setContentsMargins(*margins)
        self.card_layout.setSpacing(spacing)
        return card

    def add_heading(self, text, font_size, subtitle=None):
        """The card's title, and the subtitle under it if one is given (catalogue keys): returns the subtitle's
        label, word-wrapped - a translation may be longer than the card is wide"""
        heading = QLabel()
        bind(heading.setText, text)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._headings.append((heading, font_size))
        self._fit_heading(heading, font_size)
        self.card_layout.addWidget(heading)
        if subtitle:
            plain_text = QLabel()
            bind(plain_text.setText, subtitle)
            plain_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            plain_text.setWordWrap(True)
            style(plain_text, "QLabel { font-size: 15px; color: @auth_text; }")
            self.card_layout.addWidget(plain_text)
            return plain_text
        return None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_preferences()

    def _place_preferences(self):
        self.preferences.adjustSize()
        self.preferences.move(self.animated_bg.width() - self.preferences.width() - 20, 14)

    def _fit_headings(self):
        for heading, font_size in self._headings:
            self._fit_heading(heading, font_size)

    def _fit_heading(self, heading, font_size):
        """The heading on one line: at font_size, or smaller where a language's words are longer"""
        margins = self.card_layout.contentsMargins()
        room = self.card_layout.parentWidget().width() - margins.left() - margins.right()
        font = QFont(heading.font())
        font.setBold(True)
        size = font_size
        while size > 18:
            font.setPixelSize(size)
            if QFontMetrics(font).horizontalAdvance(heading.text()) <= room:
                break
            size -= 2
        style(heading, f"QLabel {{ font-size: {size}px; color: @auth_heading; font-weight: bold; }}")

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.setWindowOpacity(0.0)
            QTimer.singleShot(50, self._fade_in)

    def _fade_in(self):
        # fade_in shows the window: not again if it was closed in the meantime
        if self.isVisible():
            WindowTransition.fade_in(self, duration=self.fade_duration)

    def go_back(self):
        if self.parent_window:
            WindowTransition.cross_fade(self, self.parent_window, duration=450)
        else:
            self.close()
