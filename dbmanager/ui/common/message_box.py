"""The app's message boxes, in the current theme and language.

Every child sets its own background: a box inherits the style sheets of the window it belongs to, and
the dashboard's page background would otherwise turn up behind the text. Qt names the buttons, in the
current language (see preferences.QtTexts).

A box is modal and made for one question, so it takes the theme and the language as they are when it opens."""

from PyQt6.QtWidgets import QMessageBox

from dbmanager.ui.common.theme import qss

_MESSAGE_STYLE = """
    QMessageBox {
        background-color: @surface;
    }
    QMessageBox QLabel {
        color: @text;
        font-size: 14px;
        min-width: 250px;
        background: transparent;
    }
    QPushButton {
        background-color: @accent;
        color: @on_accent;
        border: none;
        border-radius: 6px;
        padding: 8px 20px;
        font-size: 13px;
        min-width: 80px;
    }
    QPushButton:hover {
        background-color: @accent_hover;
    }
"""

_QUESTION_STYLE = """
    QMessageBox {
        background-color: @surface;
    }
    QMessageBox QLabel {
        color: @text;
        font-size: 14px;
        min-width: 280px;
        background: transparent;
    }
    QPushButton {
        background-color: @surface_raised;
        color: @text;
        border: none;
        border-radius: 6px;
        padding: 8px 20px;
        font-size: 13px;
        min-width: 80px;
    }
    QPushButton:hover {
        background-color: @surface_pressed;
        color: @text;
    }
    QPushButton:focus {
        background-color: @accent;
        color: @on_accent;
    }
"""


def styled_message_box(parent, title, text, icon=QMessageBox.Icon.Information):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon)
    msg.setStyleSheet(qss(_MESSAGE_STYLE))
    return msg


def styled_question_box(parent, title, text):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    msg.setDefaultButton(QMessageBox.StandardButton.No)
    msg.setStyleSheet(qss(_QUESTION_STYLE))
    return msg


def show_styled_message(parent, title, text, icon=QMessageBox.Icon.Information):
    """Show a message box in the app's theme."""
    return styled_message_box(parent, title, text, icon).exec()


def show_styled_question(parent, title, text):
    """Ask a Yes/No question (No is the default) in the app's theme."""
    return styled_question_box(parent, title, text).exec()


def confirm(parent, title, text):
    """True when the user answers Yes."""
    return show_styled_question(parent, title, text) == QMessageBox.StandardButton.Yes

