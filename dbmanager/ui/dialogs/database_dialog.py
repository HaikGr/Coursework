from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from dbmanager.api import DB_TYPES, DEFAULT_PORTS, ApiError, parse_port
from dbmanager.db import DatabaseError
from dbmanager.i18n import tr
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.message_box import confirm, show_styled_message
from dbmanager.ui.common.dark_dialog import settle_enter_key
from dbmanager.ui.common.style import COMBO_ARROW
from dbmanager.ui.common.theme import qss


class InputDatabaseWindow(QDialog):
    """Dialog for registering or editing a database connection, in the current theme.

    on_submit(details) is called when the user confirms; if it raises ApiError the
    message is shown and the dialog stays open so the input can be corrected.

    on_test(details) connects to the database from this computer with these details, returning what
    answered or raising DatabaseError. With it the dialog gets a Test button, and settings nothing answers
    on are only saved when the user insists.

    The password goes into details as dbPassword; the server stores it encrypted.

    title and button_text are shown as given (already translated); left out, they say New Database and Connect.
    """

    def __init__(self, parent=None, title=None, connection=None, button_text=None, on_submit=None,
                 on_test=None):
        super().__init__(parent)
        title = title or tr("dialogs.database.new_title")
        button_text = button_text or tr("dialogs.database.connect")
        self.setWindowTitle(title)
        self.setWindowIcon(app_icon())
        self.setFixedSize(420, 580)
        self.return_data = None
        self.on_submit = on_submit
        self.on_test = on_test
        self.editing = connection is not None

        # Remove window frame for cleaner look
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Theme styling
        self.setStyleSheet(qss(COMBO_ARROW + """
            QDialog {
                background-color: @surface;
                border: 2px solid @accent;
                border-radius: 16px;
            }
            QLabel {
                color: @text_secondary;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }
            QLineEdit, QComboBox {
                background-color: @sunken;
                border: 2px solid @border_strong;
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 14px;
                color: @text;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid @focus;
            }
            QComboBox QAbstractItemView {
                background-color: @sunken;
                color: @text;
                selection-background-color: @selection;
                selection-color: @on_selection;
            }
        """))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        # Header
        header = QLabel(f"{title}")
        header.setStyleSheet(qss("""
            QLabel {
                color: @text;
                font-size: 20px;
                font-weight: bold;
                background: transparent;
            }
        """))
        layout.addWidget(header)
        layout.addSpacing(8)

        # Type
        self.type_combo = QComboBox()
        for value, label, _ in DB_TYPES:
            self.type_combo.addItem(label, value)
        self.type_combo.setFixedHeight(40)
        self._add_field(layout, tr("dialogs.database.type"), self.type_combo)

        # Host + Port
        self.host_input = self._line_edit("localhost")
        self.port_input = self._line_edit("")
        self.port_input.setFixedWidth(110)
        host_col = QVBoxLayout()
        host_col.setSpacing(6)
        host_col.addWidget(QLabel(tr("dialogs.database.host")))
        host_col.addWidget(self.host_input)
        port_col = QVBoxLayout()
        port_col.setSpacing(6)
        port_col.addWidget(QLabel(tr("dialogs.database.port")))
        port_col.addWidget(self.port_input)
        host_row = QHBoxLayout()
        host_row.setSpacing(12)
        host_row.addLayout(host_col)
        host_row.addLayout(port_col)
        layout.addLayout(host_row)
        layout.addSpacing(4)

        self.name_input = self._line_edit("my_database")
        self._add_field(layout, tr("dialogs.database.name"), self.name_input)

        self.user_input = self._line_edit(tr("dialogs.database.user_placeholder"))
        self._add_field(layout, tr("dialogs.database.username"), self.user_input)

        self.password_input = self._line_edit(tr("dialogs.database.keep_password") if self.editing
                                              else tr("dialogs.database.password_placeholder"))
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._add_field(layout, tr("dialogs.database.password"), self.password_input)

        if connection:
            index = self.type_combo.findData(connection.get("dbType"))
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
            self.host_input.setText(connection.get("host", ""))
            self.port_input.setText(str(connection.get("port", "")))
            self.name_input.setText(connection.get("dbName", ""))
            self.user_input.setText(connection.get("dbUsername", ""))
        else:
            self.port_input.setText(str(DEFAULT_PORTS[self.type_combo.currentData()]))
        self._last_default_port = str(DEFAULT_PORTS[self.type_combo.currentData()])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)

        layout.addStretch()

        # What the last connection test said
        self.test_status = QLabel("")
        self.test_status.setWordWrap(True)
        layout.addWidget(self.test_status)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        if on_test:
            test_btn = QPushButton(tr("dialogs.database.test"))
            test_btn.setToolTip(tr("dialogs.database.test_tip"))
            test_btn.setFixedSize(90, 42)
            test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            test_btn.setStyleSheet(qss("""
                QPushButton {
                    background-color: transparent;
                    color: @accent_text;
                    border: 2px solid @accent;
                    border-radius: 10px;
                    font-size: 14px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: @accent_subtle;
                    color: @text;
                }
            """))
            test_btn.clicked.connect(self.test_connection)
            btn_layout.addWidget(test_btn)

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setFixedSize(100, 42)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(qss("""
            QPushButton {
                background-color: @surface_raised;
                color: @text_secondary;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: @surface_pressed;
                color: @text;
            }
        """))
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton(button_text)
        ok_btn.setFixedSize(140, 42)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet(qss("""
            QPushButton {
                background-color: @accent;
                color: @on_accent;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: @accent_hover;
            }
        """))
        ok_btn.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        settle_enter_key(self, default=ok_btn)  # Enter in any field connects (not Test, not twice)
        layout.addLayout(btn_layout)

        self.host_input.setFocus()

    @staticmethod
    def _line_edit(placeholder):
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setFixedHeight(40)
        return field

    @staticmethod
    def _add_field(layout, label_text, widget):
        layout.addWidget(QLabel(label_text))
        layout.addWidget(widget)
        layout.addSpacing(4)

    def _on_type_changed(self):
        # Follow the default port of the chosen type unless the user typed their own
        new_default = str(DEFAULT_PORTS[self.type_combo.currentData()])
        if self.port_input.text().strip() in ("", self._last_default_port):
            self.port_input.setText(new_default)
        self._last_default_port = new_default

    def _error(self, text):
        show_styled_message(self, tr("dialogs.database.error_title"), text, QMessageBox.Icon.Warning)

    def _details(self):
        """The form as API details, or None (after saying why) when something is missing"""
        host = self.host_input.text().strip()
        port = self.port_input.text().strip()
        name = self.name_input.text().strip()
        user = self.user_input.text().strip()
        password = self.password_input.text()

        if not host or not name or not user:
            self._error(tr("dialogs.database.missing"))
            return None
        port = parse_port(port)
        if port is None:
            self._error(tr("dialogs.database.bad_port"))
            return None
        if not password and not self.editing:
            self._error(tr("dialogs.database.no_password"))
            return None

        details = {
            "host": host,
            "port": port,
            "dbName": name,
            "dbUsername": user,
            "dbType": self.type_combo.currentData(),
        }
        if password:
            details["dbPassword"] = password
        return details

    def _test(self, details):
        """Connect with these details. Returns the error, or None when it worked; either way the outcome
        is shown above the buttons."""
        try:
            with busy_cursor():
                message = self.on_test(details)
        except (DatabaseError, ApiError) as error:
            self.test_status.setText(f"✗ {error}")
            self.test_status.setStyleSheet(qss("QLabel { color: @danger_text; font-size: 12px; font-weight: 500; "
                                               "background: transparent; }"))
            return error
        self.test_status.setText(f"✓ {message or tr('dialogs.database.connected')}")
        self.test_status.setStyleSheet(qss("QLabel { color: @success_text; font-size: 12px; font-weight: 500; "
                                           "background: transparent; }"))
        return None

    def test_connection(self):
        details = self._details()
        if details is not None:
            self._test(details)

    def accept(self):
        details = self._details()
        if details is None:
            return

        if self.on_test:
            error = self._test(details)
            # Nothing answered: perhaps only for now (the database is off, or not on this network).
            # Anything else (a database type this app cannot open, a lost session) would fail the save too.
            if error is not None and (not getattr(error, "unreachable", False) or not confirm(
                    self, tr("dialogs.database.unreachable_title"),
                    tr("dialogs.database.unreachable", error=error))):
                return

        if self.on_submit:
            try:
                with busy_cursor():
                    self.on_submit(details)
            except ApiError as error:
                self._error(str(error))
                return

        self.return_data = details
        super().accept()

    def get_data(self):
        return self.return_data
