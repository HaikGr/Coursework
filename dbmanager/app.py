"""Application start-up."""

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from dbmanager.ui.auth.sign_in import SignInWindow
from dbmanager.ui.common.icons import app_icon


def create_application(argv=None):
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Database Management")
    app.setWindowIcon(app_icon())
    # Every screen is designed with its own fixed colours. A dark system theme would otherwise
    # leak light text into the places that do not set one, and it becomes unreadable.
    if hasattr(app.styleHints(), "setColorScheme"):
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    return app


def main():
    app = create_application()
    window = SignInWindow()
    window.show()
    return app.exec()
