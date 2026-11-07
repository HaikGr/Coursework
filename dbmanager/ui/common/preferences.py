"""The language and the theme: remembered between sessions, applied at once when the user changes them.

Until the user picks one, the app follows the system - its language when the app has it (English
otherwise), and its light or dark mode. load() applies both before the first window is made, so no window
ever shows in the wrong theme or language, not even while it fades in.
"""

from PyQt6.QtCore import QLibraryInfo, QLocale, QObject, QSettings, Qt, QTranslator, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QMenu, QToolButton, QWidget

from dbmanager import i18n
from dbmanager.config import SETTINGS_APPLICATION, SETTINGS_ORGANIZATION
from dbmanager.i18n import tr
from dbmanager.ui.common import live, theme
from dbmanager.ui.common.style import MENU_STYLE

LANGUAGE_SETTING = "language"
THEME_SETTING = "theme"
THEME_ICONS = {"light": "☀", "dark": "☾"}


class _Changes(QObject):
    # After the language or the theme changed and every bound text and style was set again: for what is
    # drawn from data (a table's rows, the diagram) rather than bound
    changed = pyqtSignal()


changes = _Changes()
_qt_translators = []


def _settings():
    return QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)


def load(app):
    """Apply the saved language and theme - or the system's - to the application, before any window exists."""
    settings = _settings()
    code = (i18n.match_language(str(settings.value(LANGUAGE_SETTING, "") or ""))
            or i18n.match_language(QLocale.system().name()) or i18n.DEFAULT_LANGUAGE)
    i18n.set_language(code)
    _install_qt_translators(app)

    name = str(settings.value(THEME_SETTING, "") or "")
    if theme.theme_named(name) is None:
        # Asked before the app sets its own scheme, which the hints report from then on
        dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        name = theme.DARK.name if dark else theme.LIGHT.name
    theme.set_theme(name)
    _apply_theme(app)


def set_language(code):
    """Switch the language of every open window, and remember it."""
    if code == i18n.language().code:
        return
    i18n.set_language(code)
    _settings().setValue(LANGUAGE_SETTING, i18n.language().code)
    app = QApplication.instance()
    if app is not None:
        _install_qt_translators(app)
    _changed()


def set_theme(name):
    """Switch the theme of every open window, and remember it."""
    if name == theme.current().name or theme.theme_named(name) is None:
        return
    theme.set_theme(name)
    _settings().setValue(THEME_SETTING, name)
    app = QApplication.instance()
    if app is not None:
        _apply_theme(app)
    _changed()


def _apply_theme(app):
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):  # Qt 6.8: title bars and native dialogs follow it
        hints.setColorScheme(theme.current().scheme)
    app.setPalette(theme.palette())


class QtTexts(QTranslator):
    """The texts Qt shows by itself - the buttons of a message box, the menu of a text field - from the app's
    catalogue: Qt has no Armenian, and these few must match the rest of the app in every language."""

    _KEYS = {
        "OK": "ok", "&Yes": "yes", "&No": "no", "Cancel": "cancel", "Close": "close", "Save": "save",
        "Discard": "discard", "Apply": "apply", "&Undo": "undo", "&Redo": "redo", "Cu&t": "cut",
        "&Copy": "copy", "&Paste": "paste", "Delete": "delete", "Select All": "select_all",
    }

    def translate(self, context, source_text, disambiguation=None, n=-1):
        key = self._KEYS.get(source_text)
        if key is None or i18n.language().code == i18n.DEFAULT_LANGUAGE:
            return None  # not ours: Qt asks the next translator, or keeps its own text
        return tr(f"common.qt.{key}")

    def isEmpty(self):
        return False


def _install_qt_translators(app):
    """Qt's own texts in the language: QtTexts first, then what Qt ships (it has Russian, but no Armenian)."""
    global _qt_translators
    for translator in _qt_translators:
        app.removeTranslator(translator)
    shipped = QTranslator(app)
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    _qt_translators = [QtTexts(app)]
    if shipped.load(f"qtbase_{i18n.language().code}", path):
        _qt_translators.append(shipped)
        app.installTranslator(shipped)
    app.installTranslator(_qt_translators[0])  # the last installed is asked first


def _changed():
    live.refresh()
    changes.changed.emit()
    for widget in QApplication.allWidgets():
        widget.update()


class PreferencesButtons(QWidget):
    """The language and the theme pickers, for a bar in the brand colour (the top bar, the sign-in windows)."""

    _BUTTON_STYLE = """
        QToolButton {
            color: @on_brand; background: transparent; border: 1px solid @brand_border; border-radius: 6px;
            padding: 3px 10px; font-size: 13px; font-weight: 600;
        }
        QToolButton:hover { background-color: @brand_hover; }
        QToolButton::menu-indicator { image: none; width: 0px; }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        theme.style(self, "QWidget { background: transparent; }")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.language_button = self._picker("common.preferences.language_tip", layout)
        self._language_actions = {}
        for language in i18n.LANGUAGES:
            action = self._choice(self.language_button, language.name,
                                  lambda checked, code=language.code: set_language(code))
            self._language_actions[language.code] = action

        self.theme_button = self._picker("common.preferences.theme_tip", layout)
        self._theme_actions = {}
        for name in (theme.LIGHT.name, theme.DARK.name):
            action = self._choice(self.theme_button, "", lambda checked, value=name: set_theme(value))
            live.bind(action.setText, lambda value=name: f"{THEME_ICONS[value]}  {tr('common.preferences.' + value)}")
            self._theme_actions[name] = action

        live.bind(self.language_button.setText, lambda: f"{i18n.language().name} ▾")
        live.bind(self.theme_button.setText,
                  lambda: f"{THEME_ICONS[theme.current().name]} {tr('common.preferences.' + theme.current().name)} ▾")
        changes.changed.connect(self._sync)
        self._sync()

    def _picker(self, tooltip_key, layout):
        button = QToolButton()
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        theme.style(button, self._BUTTON_STYLE)
        live.bind(button.setToolTip, tooltip_key)
        menu = QMenu(button)
        theme.style(menu, MENU_STYLE)
        button.setMenu(menu)
        button.choices = QActionGroup(menu)  # one of them is checked
        layout.addWidget(button)
        return button

    @staticmethod
    def _choice(button, text, on_choose):
        action = QAction(text, button.menu())
        action.setCheckable(True)
        button.choices.addAction(action)
        action.triggered.connect(on_choose)
        button.menu().addAction(action)
        return action

    def _sync(self):
        for code, action in self._language_actions.items():
            action.setChecked(code == i18n.language().code)
        for name, action in self._theme_actions.items():
            action.setChecked(name == theme.current().name)
