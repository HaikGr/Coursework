"""Shared set-up for tests that need widgets: an offscreen QApplication, and slot exceptions as failures."""

import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

_errors = []


def _collect(exc_type, exc, tb):
    # PyQt aborts the process on an exception escaping a slot unless a hook takes it.
    # Print it as well: an error outside any slot ends up here too and must not vanish.
    traceback.print_exception(exc_type, exc, tb)
    _errors.append(exc)


def app():
    sys.excepthook = _collect
    return QApplication.instance() or QApplication([])


def raise_slot_errors():
    """Re-raise the first exception that escaped a slot since the last call."""
    if _errors:
        error = _errors[0]
        _errors.clear()
        raise error
