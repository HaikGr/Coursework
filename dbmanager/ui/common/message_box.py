"""Dark themed message boxes used by the dashboard and its dialogs.

Every child sets its own background: a box inherits the style sheets of the window it belongs to, and
the dashboard's page background would otherwise turn up behind the light text."""

from PyQt6.QtWidgets import QMessageBox

_MESSAGE_STYLE = """
    QMessageBox {
        background-color: #1f2937;
    }
    QMessageBox QLabel {
        color: #f3f4f6;
        font-size: 14px;
        min-width: 250px;
        background: transparent;
    }
    QPushButton {
        background-color: #3777f0;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 20px;
        font-size: 13px;
        min-width: 80px;
    }
    QPushButton:hover {
        background-color: #2563eb;
    }
"""

_QUESTION_STYLE = """
    QMessageBox {
        background-color: #1f2937;
    }
    QMessageBox QLabel {
        color: #f3f4f6;
        font-size: 14px;
        min-width: 280px;
        background: transparent;
    }
    QPushButton {
        background-color: #4b5563;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 20px;
        font-size: 13px;
        min-width: 80px;
    }
    QPushButton:hover {
        background-color: #6b7280;
    }
    QPushButton:focus {
        background-color: #3777f0;
    }
"""


def styled_message_box(parent, title, text, icon=QMessageBox.Icon.Information):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon)
    msg.setStyleSheet(_MESSAGE_STYLE)
    return msg


def styled_question_box(parent, title, text):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    msg.setDefaultButton(QMessageBox.StandardButton.No)
    msg.setStyleSheet(_QUESTION_STYLE)
    return msg


def show_styled_message(parent, title, text, icon=QMessageBox.Icon.Information):
    """Show a message box with the dark theme."""
    return styled_message_box(parent, title, text, icon).exec()


def show_styled_question(parent, title, text):
    """Ask a Yes/No question (No is the default) with the dark theme."""
    return styled_question_box(parent, title, text).exec()


def confirm(parent, title, text):
    """True when the user answers Yes."""
    return show_styled_question(parent, title, text) == QMessageBox.StandardButton.Yes
