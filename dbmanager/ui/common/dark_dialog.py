"""The look of the account and sharing dialogs, in the current theme.

DIALOG_STYLE is a theme.qss template: a dialog sets qss(DIALOG_STYLE) when it is made (it is modal, so the
theme cannot change while it is open). Every child sets its own background: a dialog inherits the style
sheet of the window it opens over, and the page background behind it would otherwise show through."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from dbmanager.ui.common.theme import qss

DIALOG_STYLE = """
    QDialog { background-color: @surface; }
    QWidget#cell { background: transparent; }
    QLabel { color: @text_secondary; font-size: 13px; background: transparent; }
    /* Captions and notes are small: they keep the body's colour and differ in size and weight instead */
    QLabel#heading { color: @text; font-size: 20px; font-weight: bold; }
    QLabel#caption { color: @text_secondary; font-size: 12px; font-weight: 600; }
    QLabel#note { color: @text_secondary; font-size: 12px; }
    QLineEdit {
        background-color: @sunken;
        border: 2px solid @border_strong;
        border-radius: 10px;
        padding: 8px 14px;
        font-size: 14px;
        color: @text;
        selection-background-color: @selection;
        selection-color: @on_selection;
    }
    QLineEdit:focus { border: 2px solid @focus; }
    QLineEdit:disabled { color: @text_disabled; background-color: @surface_alt; }
    QCheckBox { color: @text; font-size: 13px; background: transparent; spacing: 10px; }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 2px solid @border_strong;
        background-color: @sunken;
    }
    QCheckBox::indicator:checked { background-color: @accent; border: 2px solid @accent; }
    QTableWidget {
        background-color: @sunken;
        color: @text;
        gridline-color: @grid_line;
        border: 1px solid @border;
        border-radius: 8px;
        font-size: 13px;
        selection-background-color: @accent_subtle;
        selection-color: @text;
    }
    QScrollBar { background: @surface_alt; width: 10px; height: 10px; margin: 0px; }
    QScrollBar::handle { background: @scrollbar; border-radius: 5px; min-height: 24px; min-width: 24px; }
    QScrollBar::handle:hover { background: @scrollbar_hover; }
    QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
    QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
    QHeaderView::section {
        background-color: @surface_alt;
        color: @text_muted;
        border: none;
        border-bottom: 1px solid @border;
        padding: 6px 8px;
        font-weight: 600;
    }
    QPushButton {
        background-color: @surface_raised;
        color: @text;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: @surface_pressed; color: @text; }
    QPushButton:focus { border: 2px solid @focus; }
    QPushButton:disabled { background-color: @surface_alt; color: @text_disabled; }
    QPushButton#primary { background-color: @accent; color: @on_accent; font-weight: 600; }
    QPushButton#primary:hover { background-color: @accent_hover; }
    QPushButton#primary:disabled { background-color: @surface_alt; color: @text_disabled; }
    QPushButton#small { padding: 4px 10px; font-size: 12px; }
    QPushButton#small_primary {
        background-color: @accent;
        color: @on_accent;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 600;
    }
    QPushButton#small_primary:hover { background-color: @accent_hover; }
"""

# Tokens for inline messages: wrap a style sheet that uses them in qss()
ERROR_COLOR = "@danger_text"
SUCCESS_COLOR = "@success_text"


def label(text, kind=None, wrap=False):
    """A label styled as kind: "heading", "caption", "note" or plain body text."""
    widget = QLabel(text)
    if kind:
        widget.setObjectName(kind)
    widget.setWordWrap(wrap)
    return widget


def button(text, kind=None, on_click=None):
    """A button styled as kind: "primary", "small", "small_primary" or the neutral default."""
    widget = QPushButton(text)
    if kind:
        widget.setObjectName(kind)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setAutoDefault(False)  # see settle_enter_key
    if on_click:
        widget.clicked.connect(on_click)
    return widget


def settle_enter_key(dialog, default=None):
    """Make Enter do one thing. In a QDialog it presses the default button - which, unless one is named, is
    the first button made (often Cancel) - on top of whatever a line edit's own returnPressed does. Here only
    `default` answers Enter, if given; line edits that act on Enter themselves keep doing so, alone."""
    for widget in dialog.findChildren(QPushButton):
        widget.setAutoDefault(False)
        widget.setDefault(False)
    if default is not None:
        default.setDefault(True)


def cell(*widgets):
    """Widgets side by side, to sit in one table cell."""
    holder = QWidget()
    holder.setObjectName("cell")
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(6, 2, 6, 2)
    layout.setSpacing(6)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch()
    return holder


def show_status(widget, text, error=False):
    """An inline message under a form: red for a problem, green when something worked."""
    widget.setText(text)
    widget.setStyleSheet(qss(f"QLabel {{ color: {ERROR_COLOR if error else SUCCESS_COLOR}; font-size: 12px; "
                             "background: transparent; }"))
