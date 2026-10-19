"""Sign Up window - creates an account and, optionally, registers a first database."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

from dbmanager.api import DB_TYPES, DEFAULT_PORTS, ApiClient, ApiError, parse_port
from dbmanager.ui.auth.base import LINK_BUTTON_STYLE, AuthWindow, PasswordField, primary_button_style
from dbmanager.ui.common.busy import busy_cursor

INPUT_STYLE = """
    QLineEdit, QComboBox {
        background: white;
        border: 2px solid transparent;
        border-radius: 20px;
        padding: 8px 16px;
        font-size: 14px;
        color: #4B5563;
    }
    QLineEdit:focus, QComboBox:focus { border: 2px solid #93B9E8; }
    QComboBox::drop-down { border: none; width: 24px; }
    QComboBox QAbstractItemView {
        background: white;
        color: #4B5563;
        selection-background-color: #93B9E8;
    }
"""


class SignUpWindow(AuthWindow):
    def __init__(self, parent_window, geometry):
        super().__init__("Database Management - Sign Up", card_height=600, card_margins=(25, 20, 25, 20),
                         card_spacing=8, parent_window=parent_window, geometry=geometry)
        self.add_heading("Create Account", 30)

        # Account
        self.username = self._line_edit("Username")
        self.card_layout.addWidget(self.username)
        # Only needed to sign in with it: becoming premium verifies an address of its own
        self.email = self._line_edit("Email (optional)")
        self.card_layout.addWidget(self.email)
        self.password = PasswordField("Password (min. 8 characters)", 330, 40, INPUT_STYLE,
                                      toggle_size=28, icon_size=20)
        self.card_layout.addWidget(self.password)

        # Database connection (optional)
        database_text = QLabel("Connect a database (optional)")
        database_text.setStyleSheet("font-size: 14px; color: #838b99;")
        database_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_layout.addSpacing(4)
        self.card_layout.addWidget(database_text)

        self.host = self._line_edit("Host (e.g., localhost)")
        self.port = self._line_edit("")
        self.port.setFixedWidth(120)
        self.card_layout.addLayout(self._row(self.host, self.port))

        self.database_name = self._line_edit("Database Name")
        self.db_type = QComboBox()
        for value, label, _ in DB_TYPES:
            self.db_type.addItem(label, value)
        self.db_type.setStyleSheet(INPUT_STYLE)
        self.db_type.setFixedWidth(150)
        self.db_type.currentIndexChanged.connect(self._update_port_placeholder)
        self.card_layout.addLayout(self._row(self.database_name, self.db_type))
        self._update_port_placeholder()

        self.db_username = self._line_edit("DB Username")
        self.db_password = PasswordField("DB Password", 160, 40, INPUT_STYLE, toggle_size=28, icon_size=20)
        self.db_password.field.returnPressed.connect(self.attempt_signup)
        self.card_layout.addLayout(self._row(self.db_username, self.db_password))

        self.card_layout.addSpacing(6)

        signup_btn = QPushButton("Sign Up")
        signup_btn.setFixedSize(100, 100)
        signup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        signup_btn.setStyleSheet(primary_button_style(radius=50, font_size=17))
        signup_btn.clicked.connect(self.attempt_signup)
        self.card_layout.addWidget(signup_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        signin_btn = QPushButton("SIGN IN")
        signin_btn.setStyleSheet(LINK_BUTTON_STYLE)
        signin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        signin_btn.clicked.connect(self.go_back)
        self.card_layout.addWidget(signin_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    @staticmethod
    def _line_edit(placeholder):
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setStyleSheet(INPUT_STYLE)
        return field

    @staticmethod
    def _row(*widgets):
        row = QHBoxLayout()
        row.setSpacing(10)
        for widget in widgets:
            row.addWidget(widget)
        return row

    def _update_port_placeholder(self):
        self.port.setPlaceholderText(f"Port {DEFAULT_PORTS[self.db_type.currentData()]}")

    def _connection_details(self):
        """The optional database as API details: None when left empty, False when half filled in."""
        db_fields = [self.host.text().strip(), self.database_name.text().strip(),
                     self.db_username.text().strip(), self.db_password.text()]
        if not any(db_fields) and not self.port.text().strip():
            return None
        if not all(db_fields):
            QMessageBox.warning(self, "Sign Up Error",
                                "To connect a database, fill in host, database name, DB username and "
                                "DB password - or leave them all empty and add it later.")
            return False
        port = parse_port(self.port.text() or str(DEFAULT_PORTS[self.db_type.currentData()]))
        if port is None:
            QMessageBox.warning(self, "Sign Up Error", "Port must be a number between 1 and 65535.")
            return False
        return {
            "host": db_fields[0],
            "port": port,
            "dbName": db_fields[1],
            "dbUsername": db_fields[2],
            "dbPassword": db_fields[3],
            "dbType": self.db_type.currentData(),
        }

    def _still_wanted(self, api, connection):
        """Test the database before adding it: one the server cannot reach is only added if the user says so"""
        try:
            with busy_cursor():
                api.test_new_connection(connection)
            return True
        except ApiError as error:
            if error.status != 502:
                QMessageBox.warning(self, "Database Not Added",
                                    f"Your account was created, but the database could not be added:\n{error}\n\n"
                                    "You can add it from the dashboard with \"+ Add Database\".")
                return False
            answer = QMessageBox.question(
                self, "Database Not Reachable",
                f"Your account was created, but the server could not connect to the database:\n{error}\n\n"
                "Add it anyway? You can fix its settings later with ⋮ → Edit connection.\n"
                "No skips it; add it later with \"+ Add Database\".")
            return answer == QMessageBox.StandardButton.Yes

    def attempt_signup(self):
        username = self.username.text().strip()
        email = self.email.text().strip()
        password = self.password.text()
        if not username or not password:
            QMessageBox.warning(self, "Sign Up Error", "Please enter a username and a password.")
            return

        connection = self._connection_details()
        if connection is False:
            return

        api = ApiClient()
        try:
            with busy_cursor():
                api.register(username, email, password)
        except ApiError as error:
            QMessageBox.warning(self, "Sign Up Error", str(error))
            return

        if connection and self._still_wanted(api, connection):
            try:
                with busy_cursor():
                    api.create_connection(connection)
            except ApiError as error:
                QMessageBox.warning(self, "Database Not Added",
                                    f"Your account was created, but the database could not be added:\n{error}\n\n"
                                    "You can add it from the dashboard with \"+ Add Database\".")

        # The sign-in window owns the dashboard, so logging out lands there
        self.parent_window.open_dashboard(api, self.saveGeometry(), from_window=self)
