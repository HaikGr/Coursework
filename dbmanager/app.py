"""Application start-up."""

import sys

from PyQt6.QtWidgets import QApplication

from dbmanager.ui.auth.sign_in import SignInWindow
from dbmanager.ui.common import preferences
from dbmanager.ui.common.icons import app_icon


def create_application(argv=None):
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Database Management")
    app.setWindowIcon(app_icon())
    # Every screen is styled by the app itself. Fusion draws what the style sheets leave to the style the
    # same way on Windows, macOS and Linux - native styles each combine with style sheets differently.
    app.setStyle("Fusion")
    # The language and the theme - the user's, or the system's until they pick one - before any window is
    # made: every screen takes its colours from the app's theme, never from the system's palette, which would
    # leak light text into the places that do not set one.
    preferences.load(app)
    return app


def main():
    app = create_application()
    window = SignInWindow()
    window.show()
    return app.exec()
