"""The look of the account and sharing dialogs: the dark theme of the database dialog.

Every child sets its own background: a dialog inherits the style sheet of the window it opens over, and
the dashboard's light page background would otherwise show up behind the light text."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

DIALOG_STYLE = """
    QDialog { background-color: #1e293b; }
    QWidget#cell { background: transparent; }
    QLabel { color: #cbd5e1; font-size: 13px; background: transparent; }
    QLabel#heading { color: #f1f5f9; font-size: 20px; font-weight: bold; }
    QLabel#caption { color: #94a3b8; font-size: 12px; font-weight: 600; }
    QLabel#note { color: #94a3b8; font-size: 12px; }
    QLineEdit {
        background-color: #0f172a;
        border: 2px solid #334155;
        border-radius: 10px;
        padding: 8px 14px;
        font-size: 14px;
        color: #f1f5f9;
    }
    QLineEdit:focus { border: 2px solid #0ea5e9; }
    QLineEdit:disabled { color: #64748b; }
    QCheckBox { color: #e2e8f0; font-size: 13px; background: transparent; spacing: 10px; }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 2px solid #475569;
        background-color: #334155;
    }
    QCheckBox::indicator:checked { background-color: #0ea5e9; border: 2px solid #0ea5e9; }
    QTableWidget {
        background-color: #0f172a;
        color: #e2e8f0;
        gridline-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        font-size: 13px;
    }
    QScrollBar { background: #0f172a; width: 10px; height: 10px; margin: 0px; }
    QScrollBar::handle { background: #334155; border-radius: 5px; min-height: 24px; min-width: 24px; }
    QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
    QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
    QHeaderView::section {
        background-color: #1e293b;
        color: #94a3b8;
        border: none;
        padding: 6px 8px;
        font-weight: 600;
    }
    QPushButton {
        background-color: #334155;
        color: #e2e8f0;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #475569; color: #f1f5f9; }
    QPushButton:disabled { background-color: #273449; color: #64748b; }
    QPushButton#primary { background-color: #0ea5e9; color: white; font-weight: 600; }
    QPushButton#primary:hover { background-color: #38bdf8; }
    QPushButton#primary:disabled { background-color: #273449; color: #64748b; }
    QPushButton#small { padding: 4px 10px; font-size: 12px; }
    QPushButton#small_primary {
        background-color: #0ea5e9;
        color: white;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 600;
    }
    QPushButton#small_primary:hover { background-color: #38bdf8; }
"""

ERROR_COLOR = "#fca5a5"
SUCCESS_COLOR = "#86efac"


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
    if on_click:
        widget.clicked.connect(on_click)
    return widget


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
    widget.setStyleSheet(f"color: {ERROR_COLOR if error else SUCCESS_COLOR}; font-size: 12px; background: transparent;")
