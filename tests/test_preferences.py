"""Switching the language and the theme: every open window follows at once, and the choice outlives the session."""

import gc
import unittest
from unittest import mock

from tests import qt

from PyQt6.QtCore import QCoreApplication, QEvent, QSettings, Qt  # noqa: E402
from PyQt6.QtGui import QPalette  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractButton, QApplication, QLabel, QTableWidget, QTreeWidget, QWidget
)

from dbmanager import i18n  # noqa: E402
from dbmanager.i18n import catalogue  # noqa: E402
from dbmanager.config import SETTINGS_APPLICATION, SETTINGS_ORGANIZATION  # noqa: E402
from dbmanager.ui.auth.sign_in import SignInWindow  # noqa: E402
from dbmanager.ui.common import preferences, theme  # noqa: E402
from dbmanager.ui.dashboard.dashboard_window import DashboardWindow  # noqa: E402
from tests.test_ui import FakeApi, FakeDb  # noqa: E402

APP = qt.app()


def visible_texts(window):
    """What the user can read: texts and tooltips of visible widgets, tree items and table headers"""
    texts = []
    for widget in [window] + window.findChildren(QWidget):
        if not widget.isVisible():
            continue
        if isinstance(widget, (QLabel, QAbstractButton)):
            texts.append(widget.text())
        texts.append(widget.toolTip())
        if isinstance(widget, QTreeWidget):
            items = [widget.topLevelItem(i) for i in range(widget.topLevelItemCount())]
            while items:
                item = items.pop()
                texts += [item.text(0), item.toolTip(0)]
                items += [item.child(i) for i in range(item.childCount())]
        if isinstance(widget, QTableWidget):
            texts += [widget.horizontalHeaderItem(i).text() for i in range(widget.columnCount())
                      if widget.horizontalHeaderItem(i) is not None]
    return [text.strip() for text in texts if text.strip()]


def unresolved_tokens(window):
    """Widgets whose style sheet still names a theme token: a template set without theme.qss()"""
    return [f"{type(widget).__name__}: {widget.styleSheet().strip()[:80]}"
            for widget in [window] + window.findChildren(QWidget) if "@" in widget.styleSheet()]


class PreferencesTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(self._restore)
        api = FakeApi()
        self.sign_in = SignInWindow()
        self.dashboard = DashboardWindow(api, db=FakeDb(api))
        self.dashboard.sidebar_widget.activate_database(1)

    def _restore(self):
        preferences.set_language("en")
        preferences.set_theme("light")
        with mock.patch("dbmanager.ui.dashboard.dashboard_window.confirm", return_value=True):
            self.dashboard.close()
        self.sign_in.close()
        QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION).clear()

    def test_open_windows_switch_language_at_once(self):
        preferences.set_language("ru")
        self.assertEqual(self.sign_in.username.placeholderText(), "Имя пользователя или email")
        self.assertEqual(self.dashboard.top_bar.premium_button.text(), "☆  Перейти на Премиум")
        self.assertEqual(self.dashboard.top_bar.title.text(), "Система управления базами данных")
        preferences.set_language("hy")
        self.assertEqual(self.sign_in.username.placeholderText(), "Օգտանուն կամ էլ. փոստ")
        preferences.set_language("en")
        self.assertEqual(self.dashboard.top_bar.premium_button.text(), "☆  Go Premium")

    def test_nothing_on_the_dashboard_stays_english_after_a_switch(self):
        """Every text on screen - labels, buttons, tooltips, the database tree, table headers - follows a switch,
        on the diagram and on a table's page"""
        english = set()
        for value in catalogue("en").values():
            english.update(value.values() if isinstance(value, dict) else [value])
        english = {text for text in english if "{" not in text and len(text) > 2}
        for code in ("ru", "hy"):  # the same in every language (SQL words, "OK"): not a sign of anything
            english -= {value for value in catalogue(code).values() if isinstance(value, str)}
        self.dashboard.resize(1500, 900)
        self.dashboard.show()
        self.dashboard.sql_builder.add_field("customers", "name", "text")
        APP.processEvents()
        preferences.set_language("hy")
        self.assertEqual([text for text in visible_texts(self.dashboard) if text in english], [])

        database = self.dashboard.sidebar_widget.databases[1]["item"]
        self.dashboard.sidebar_widget.on_tree_click(next(
            database.child(i) for i in range(database.childCount()) if database.child(i).data(0, 257) == "customers"))
        APP.processEvents()
        preferences.set_language("ru")
        self.assertEqual([text for text in visible_texts(self.dashboard) if text in english], [])

    def test_a_window_that_is_gone_does_not_break_the_next_switch(self):
        """A slot left connected to a deleted window would raise in it - and an error in a slot ends the app"""
        for make in (SignInWindow, lambda: DashboardWindow(FakeApi(), db=FakeDb(FakeApi()))):
            window = make()
            window.show()
            QTest.qWait(120)  # it has faded in: its own timer must not outlive it either
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            del window
            gc.collect()
        preferences.set_language("hy")
        preferences.set_theme("dark")
        qt.raise_slot_errors()

    def test_open_windows_switch_theme_at_once(self):
        preferences.set_theme("dark")
        self.assertIn(theme.DARK.colors["brand"], self.dashboard.top_bar.styleSheet())
        self.assertEqual(APP.palette().color(QPalette.ColorRole.Window).name().upper(), theme.DARK.colors["surface"])
        preferences.set_theme("light")
        self.assertIn(theme.LIGHT.colors["brand"], self.dashboard.top_bar.styleSheet())

    def test_every_style_sheet_is_resolved_in_both_themes(self):
        for name in ("light", "dark"):
            preferences.set_theme(name)
            for window in (self.sign_in, self.dashboard):
                self.assertEqual(unresolved_tokens(window), [], f"{name}: {type(window).__name__}")

    def test_the_choice_is_remembered_and_applied_at_the_next_start(self):
        preferences.set_language("hy")
        preferences.set_theme("dark")
        settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        self.assertEqual((settings.value("language"), settings.value("theme")), ("hy", "dark"))
        i18n.set_language("en")
        theme.set_theme("light")
        preferences.load(APP)  # what the next start does before its first window
        self.assertEqual((i18n.language().code, theme.current().name), ("hy", "dark"))

    def test_without_a_choice_the_system_decides(self):
        QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION).clear()
        hints = mock.Mock()
        hints.colorScheme.return_value = Qt.ColorScheme.Dark
        with mock.patch.object(APP, "styleHints", return_value=hints), \
                mock.patch("dbmanager.ui.common.preferences.QLocale") as locale:
            locale.system.return_value.name.return_value = "ru_RU"
            preferences.load(APP)
        self.assertEqual((i18n.language().code, theme.current().name), ("ru", "dark"))
        hints.setColorScheme.assert_called_with(Qt.ColorScheme.Dark)

    def test_the_pickers_switch(self):
        buttons = self.sign_in.preferences
        next(action for action in buttons.language_button.menu().actions() if action.text() == "Русский").trigger()
        self.assertEqual(i18n.language().code, "ru")
        self.assertTrue(buttons.language_button.text().startswith("Русский"))
        dark = next(action for action in buttons.theme_button.menu().actions() if "Тёмная" in action.text())
        dark.trigger()
        self.assertEqual(theme.current().name, "dark")
        self.assertTrue(dark.isChecked())
        # The same pickers in the dashboard show the same choice
        self.assertTrue(self.dashboard.top_bar.preferences.theme_button.text().startswith("☾"))

    def test_qt_names_its_own_buttons_in_the_language(self):
        from PyQt6.QtWidgets import QMessageBox
        preferences.set_language("hy")
        box = QMessageBox()
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        self.assertEqual(sorted(button.text() for button in box.buttons()), ["&Այո", "&Ոչ"])


class ThemeTest(unittest.TestCase):
    def test_both_themes_have_the_same_tokens(self):
        self.assertEqual(sorted(theme.LIGHT.colors), sorted(theme.DARK.colors))

    def test_an_unknown_token_is_an_error(self):
        with self.assertRaises(KeyError):
            theme.qss("QLabel { color: @no_such_colour; }")

    def test_text_tokens_read_on_their_backgrounds(self):
        from tests.test_ui import contrast
        pairs = [("text", "surface"), ("text", "window"), ("text_secondary", "surface"), ("text_muted", "surface"),
                 ("text", "sunken"), ("text", "surface_alt"), ("text", "surface_raised"),
                 ("on_accent", "accent"), ("accent_text", "surface"), ("on_danger", "danger"),
                 ("danger_text", "surface"), ("danger_text", "danger_subtle"), ("on_success", "success"),
                 ("success_text", "surface"), ("on_warning", "warning"), ("warning_text", "surface"),
                 ("on_highlight", "highlight"), ("on_brand", "brand"), ("on_tooltip", "tooltip"),
                 ("on_option", "option"), ("info_text", "info_subtle"), ("purple_text", "purple_subtle"),
                 ("on_pk", "pk"), ("on_fk", "fk"), ("auth_heading", "auth_card"), ("auth_text", "auth_card"),
                 ("auth_input_text", "auth_input"), ("code_text", "code_background"),
                 ("on_selection", "selection"), ("on_brand_muted", "brand"), ("on_brand", "auth_background"),
                 ("on_brand_muted", "auth_background"),
                 ("text_muted", "window"), ("text_muted", "canvas"), ("text_muted", "surface_raised"),
                 ("text_muted", "surface_alt"), ("on_accent", "purple"), ("text", "surface_pressed")]
        self.addCleanup(theme.set_theme, theme.current().name)
        for current in theme.THEMES:
            theme.set_theme(current.name)
            for foreground, background in pairs:
                ratio = contrast(theme.color(foreground), theme.color(background))
                self.assertGreaterEqual(ratio, 4.5, f"{current.name}: {foreground} on {background} is {ratio:.2f}")


if __name__ == "__main__":
    unittest.main()
