"""Every test: a missing translation raises instead of showing its key, and the preferences the tests change
(language, theme, a remembered username) go to a scratch directory, not to the user's own settings."""

import os
import tempfile

os.environ.setdefault("DB_MANAGER_STRICT_I18N", "1")

from PyQt6.QtCore import QSettings  # noqa: E402

_SETTINGS_DIR = tempfile.mkdtemp(prefix="dbmanager-test-settings-")
for _format in (QSettings.Format.NativeFormat, QSettings.Format.IniFormat):
    QSettings.setPath(_format, QSettings.Scope.UserScope, _SETTINGS_DIR)
