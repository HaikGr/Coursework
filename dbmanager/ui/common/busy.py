from contextlib import contextmanager

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication


@contextmanager
def busy_cursor():
    """Show a wait cursor while a (blocking) API call runs."""
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    QApplication.processEvents()
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()
