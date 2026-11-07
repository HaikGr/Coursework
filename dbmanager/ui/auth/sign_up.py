"""Sign Up window - creates an account and, optionally, registers a first database."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

from dbmanager.api import DB_TYPES, DEFAULT_PORTS, ApiClient, ApiError, parse_port
from dbmanager.db import DatabaseClient, DatabaseError
from dbmanager.i18n import tr
from dbmanager.ui.auth.base import LINK_BUTTON_STYLE, AuthWindow, PasswordField, primary_button_style
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.live import bind
from dbmanager.ui.common.theme import style

INPUT_STYLE = """
    QLineEdit, QComboBox {
        background: @auth_input;
        border: 2px solid transparent;
        border-radius: 20px;
        padding: 8px 16px;
        font-size: 14px;
        color: @auth_input_text;
        selection-background-color: @selection;
        selection-color: @on_selection;
    }
    QLineEdit:focus, QComboBox:focus { border: 2px solid @focus; }
    QComboBox::drop-down { border: none; width: 24px; }
    QComboBox QAbstractItemView {
        background: @auth_input;
        color: @auth_input_text;
        selection-background-color: @accent_subtle;
        selection-color: @text;
    }
"""


class SignUpWindow(AuthWindow):
    def __init__(self, parent_window, geometry):
        super().__init__("auth.sign_up.window_title", card_height=600, card_margins=(25, 20, 25, 20),
                         card_spacing=8, parent_window=parent_window, geometry=geometry)
        self.add_heading("auth.sign_up.heading", 30)

        # Account
        self.username = self._line_edit("auth.sign_up.username")
        self.card_layout.addWidget(self.username)
        # Only needed to sign in with it: becoming premium verifies an address of its own
        self.email = self._line_edit("auth.sign_up.email")
        self.card_layout.addWidget(self.email)
        self.password = PasswordField("auth.sign_up.password", 330, 40, INPUT_STYLE,
                                      toggle_size=28, icon_size=20)
        self.card_layout.addWidget(self.password)

        # Database connection (optional)
        database_text = QLabel()
        bind(database_text.setText, "auth.sign_up.database")
        style(database_text, "QLabel { font-size: 14px; color: @auth_text; }")
        database_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_layout.addSpacing(4)
        self.card_layout.addWidget(database_text)

        self.host = self._line_edit("auth.sign_up.host")
        self.port = self._line_edit(None)
        self.port.setFixedWidth(130)  # room for 'Port 5432' in every language
        self.card_layout.addLayout(self._row(self.host, self.port))

        self.database_name = self._line_edit("auth.sign_up.database_name")
        self.db_type = QComboBox()
        for value, label, _ in DB_TYPES:
            self.db_type.addItem(label, value)
        style(self.db_type, INPUT_STYLE)
        self.db_type.setFixedWidth(150)
        self.db_type.currentIndexChanged.connect(self._update_port_placeholder)
        self.card_layout.addLayout(self._row(self.database_name, self.db_type))
        self._update_port_placeholder()

        self.db_username = self._line_edit("auth.sign_up.db_username")
        self.db_password = PasswordField("auth.sign_up.db_password", 186, 40, INPUT_STYLE, toggle_size=28, icon_size=20)
        self.db_password.field.returnPressed.connect(self.attempt_signup)
        self.card_layout.addLayout(self._row(self.db_username, self.db_password))

        self.card_layout.addSpacing(6)

        signup_btn = QPushButton()
        bind(signup_btn.setText, "auth.sign_up.submit")
        signup_btn.setFixedSize(100, 100)
        signup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        style(signup_btn, primary_button_style(radius=50, font_size=17))
        signup_btn.clicked.connect(self.attempt_signup)
        self.card_layout.addWidget(signup_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        signin_btn = QPushButton()
        bind(signin_btn.setText, "auth.sign_up.sign_in")
        style(signin_btn, LINK_BUTTON_STYLE)
        signin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        signin_btn.clicked.connect(self.go_back)
        self.card_layout.addWidget(signin_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    @staticmethod
    def _line_edit(placeholder):
        """placeholder: a catalogue key, or None for one set later"""
        field = QLineEdit()
        if placeholder:
            bind(field.setPlaceholderText, placeholder)
        style(field, INPUT_STYLE)
        return field

    @staticmethod
    def _row(*widgets):
        row = QHBoxLayout()
        row.setSpacing(10)
        for widget in widgets:
            row.addWidget(widget)
        return row

    def _update_port_placeholder(self):
        bind(self.port.setPlaceholderText, "auth.sign_up.port", port=DEFAULT_PORTS[self.db_type.currentData()])

    def _connection_details(self):
        """The optional database as API details: None when left empty, False when half filled in."""
        db_fields = [self.host.text().strip(), self.database_name.text().strip(),
                     self.db_username.text().strip(), self.db_password.text()]
        if not any(db_fields) and not self.port.text().strip():
            return None
        if not all(db_fields):
            QMessageBox.warning(self, tr("auth.sign_up.error_title"), tr("auth.sign_up.incomplete_database"))
            return False
        port = parse_port(self.port.text() or str(DEFAULT_PORTS[self.db_type.currentData()]))
        if port is None:
            QMessageBox.warning(self, tr("auth.sign_up.error_title"), tr("auth.sign_up.bad_port"))
            return False
        return {
            "host": db_fields[0],
            "port": port,
            "dbName": db_fields[1],
            "dbUsername": db_fields[2],
            "dbPassword": db_fields[3],
            "dbType": self.db_type.currentData(),
        }

    def _still_wanted(self, db, connection):
        """Test the database before adding it: one this computer cannot reach is only added if the user says so"""
        try:
            with busy_cursor():
                db.test_new(connection)
            return True
        except DatabaseError as error:
            if not error.unreachable:
                self._not_added(error)
                return False
            answer = QMessageBox.question(
                self, tr("auth.sign_up.unreachable_title"),
                tr("auth.sign_up.unreachable", error=error, add_database=tr("common.action.add_database"),
                   edit_connection=tr("common.action.edit_connection")))
            return answer == QMessageBox.StandardButton.Yes

    def _not_added(self, error):
        QMessageBox.warning(self, tr("auth.sign_up.not_added_title"),
                            tr("auth.sign_up.not_added", error=error, add_database=tr("common.action.add_database")))

    def attempt_signup(self):
        username = self.username.text().strip()
        email = self.email.text().strip()
        password = self.password.text()
        if not username or not password:
            QMessageBox.warning(self, tr("auth.sign_up.error_title"), tr("auth.sign_up.missing"))
            return

        connection = self._connection_details()
        if connection is False:
            return

        api = ApiClient()
        try:
            with busy_cursor():
                api.register(username, email, password)
        except ApiError as error:
            QMessageBox.warning(self, tr("auth.sign_up.error_title"), str(error))
            return

        db = DatabaseClient(api)  # keeps the password for the dashboard this session opens
        if connection and self._still_wanted(db, connection):
            try:
                with busy_cursor():
                    db.create_connection(connection)
            except ApiError as error:
                self._not_added(error)

        # The sign-in window owns the dashboard, so logging out lands there
        self.parent_window.open_dashboard(api, self.saveGeometry(), from_window=self)
