"""
Sign Up Window - Original Blue Theme with Smooth Transitions
"""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox,
    QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtCore import Qt, QSize, QTimer

import animatedbackground as ab
from windowtransitions import WindowTransition
from api_client import ApiClient, ApiError, busy_cursor, DB_TYPES, DEFAULT_PORTS
from dashboard import DashboardWindow


def get_app_icon():
    """Get the application icon path"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "icon", "sql_query_builder_icon.svg")


class SignUpWindow(QMainWindow):
    def __init__(self, parent_window, geometry):
        super().__init__()
        self.setWindowTitle("Database Management - Sign Up")
        self.setWindowIcon(QIcon(get_app_icon()))
        self.setStyleSheet("background-color: #3B82F6;")
        self.parent_window = parent_window
        self.saved_geometry = geometry
        if geometry:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass
        self.setMinimumSize(1200, 700)

        # Animated background as central widget
        self.animated_bg = ab.AnimatedBackground(self)
        self.setCentralWidget(self.animated_bg)

        # Content container
        self.content_container = QWidget(self.animated_bg)
        self.content_container.setStyleSheet("background-color: transparent;")

        container_layout = QHBoxLayout(self.content_container)
        container_layout.setContentsMargins(60, 60, 60, 60)
        container_layout.setSpacing(50)

        # Left side
        left = QVBoxLayout()
        left.setContentsMargins(0, 160, 0, 0)
        left.setSpacing(25)

        title = QLabel("Database\nManagement")
        title.setStyleSheet("color: white; font-size: 48px; font-weight: bold;")
        desc = QLabel(
            "Visualize, manage, and optimize your databases\nwith powerful ERD tools and real-time collaboration"
        )
        desc.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 18px;")
        desc.setWordWrap(True)

        feat1 = QLabel("✔ Interactive ERD Builder")
        feat1.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 16px;")
        feat2 = QLabel("✔ Table Relationships")
        feat2.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 16px;")

        left.addWidget(title)
        left.addWidget(desc)
        left.addWidget(feat1)
        left.addWidget(feat2)
        left.addStretch()
        container_layout.addLayout(left, stretch=2)

        # Card
        card = QWidget()
        card.setFixedWidth(380)
        card.setFixedHeight(600)
        card.setStyleSheet("background-color: #C5D9F5; border-radius: 40px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(25, 20, 25, 20)
        card_layout.setSpacing(8)

        # Heading
        heading = QLabel("Create Account")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 30px; color: #4B5563; font-weight: bold;")
        card_layout.addWidget(heading)

        input_style = """
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

        # Account
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.username.setStyleSheet(input_style)
        card_layout.addWidget(self.username)

        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        self.email.setStyleSheet(input_style)
        card_layout.addWidget(self.email)

        password_container, self.password, self.password_btn = self._password_field(
            "Password (min. 8 characters)", 330, input_style)
        self.password_btn.clicked.connect(self.toggle_password_main)
        card_layout.addWidget(password_container)

        # Database connection (optional)
        databasetext = QLabel("Connect a database (optional)")
        databasetext.setStyleSheet("font-size: 14px; color: #838b99;")
        databasetext.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addSpacing(4)
        card_layout.addWidget(databasetext)

        self.host = QLineEdit()
        self.host.setPlaceholderText("Host (e.g., localhost)")
        self.host.setStyleSheet(input_style)
        self.port = QLineEdit()
        self.port.setStyleSheet(input_style)
        self.port.setFixedWidth(120)
        card_layout.addLayout(self._row(self.host, self.port))

        self.databasename = QLineEdit()
        self.databasename.setPlaceholderText("Database Name")
        self.databasename.setStyleSheet(input_style)
        self.db_type = QComboBox()
        for value, label, _ in DB_TYPES:
            self.db_type.addItem(label, value)
        self.db_type.setStyleSheet(input_style)
        self.db_type.setFixedWidth(150)
        self.db_type.currentIndexChanged.connect(self._update_port_placeholder)
        card_layout.addLayout(self._row(self.databasename, self.db_type))
        self._update_port_placeholder()

        self.db_username = QLineEdit()
        self.db_username.setPlaceholderText("DB Username")
        self.db_username.setStyleSheet(input_style)
        db_pwd_container, self.db_password, self.db_password_btn = self._password_field(
            "DB Password", 160, input_style)
        self.db_password_btn.clicked.connect(self.toggle_password_db)
        card_layout.addLayout(self._row(self.db_username, db_pwd_container))

        card_layout.addSpacing(6)

        # Circle Connect button
        connect_btn = QPushButton("Sign Up")
        connect_btn.setFixedSize(100, 100)
        connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #3479f3;
                color: white;
                font-size: 17px;
                border-radius: 50px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7BA3D0; }
        """)
        connect_btn.clicked.connect(self.attempt_signup)
        card_layout.addWidget(connect_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Sign in link
        signup = QPushButton("SIGN IN")
        signup.setStyleSheet("color:#3B82F6; background:transparent; border:none;")
        signup.clicked.connect(self.go_back)
        card_layout.addWidget(signup, alignment=Qt.AlignmentFlag.AlignCenter)

        container_layout.addWidget(card, stretch=1)

        # Main layout
        main_layout = QVBoxLayout(self.animated_bg)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.content_container)

        self._first_show = True

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.setWindowOpacity(0.0)
            QTimer.singleShot(50, lambda: WindowTransition.fade_in(self, duration=350))

    @staticmethod
    def _password_field(placeholder, width, style):
        """A password input with an eye button to show/hide the text."""
        container = QWidget()
        container.setFixedSize(width, 40)
        container.setStyleSheet("background: transparent;")

        field = QLineEdit(container)
        field.setGeometry(0, 0, width, 40)
        field.setPlaceholderText(placeholder)
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setStyleSheet(style)

        toggle = QPushButton(container)
        toggle.setGeometry(width - 38, 6, 28, 28)
        toggle.setIcon(ab.svg_icon(ab.EYE_CLOSED))
        toggle.setIconSize(QSize(20, 20))
        toggle.setStyleSheet("QPushButton { color: black; border: none; background: transparent; }")
        return container, field, toggle

    @staticmethod
    def _row(*widgets):
        row = QHBoxLayout()
        row.setSpacing(10)
        for widget in widgets:
            row.addWidget(widget)
        return row

    def _update_port_placeholder(self):
        self.port.setPlaceholderText(f"Port {DEFAULT_PORTS[self.db_type.currentData()]}")

    def attempt_signup(self):
        username = self.username.text().strip()
        email = self.email.text().strip()
        password = self.password.text()
        if not username or not email or not password:
            QMessageBox.warning(self, "Sign Up Error", "Please enter a username, an email and a password.")
            return

        db_fields = [self.host.text().strip(), self.databasename.text().strip(),
                     self.db_username.text().strip(), self.db_password.text()]
        wants_database = any(db_fields) or bool(self.port.text().strip())
        connection = None
        if wants_database:
            if not all(db_fields):
                QMessageBox.warning(self, "Sign Up Error",
                                    "To connect a database, fill in host, database name, DB username and "
                                    "DB password - or leave them all empty and add it later.")
                return
            port_text = self.port.text().strip() or str(DEFAULT_PORTS[self.db_type.currentData()])
            if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
                QMessageBox.warning(self, "Sign Up Error", "Port must be a number between 1 and 65535.")
                return
            connection = {
                "host": db_fields[0],
                "port": int(port_text),
                "dbName": db_fields[1],
                "dbUsername": db_fields[2],
                "dbPassword": db_fields[3],
                "dbType": self.db_type.currentData(),
            }

        api = ApiClient()
        try:
            with busy_cursor():
                api.register(username, email, password)
        except ApiError as error:
            QMessageBox.warning(self, "Sign Up Error", str(error))
            return

        if connection:
            try:
                with busy_cursor():
                    api.create_connection(connection)
            except ApiError as error:
                QMessageBox.warning(self, "Database Not Added",
                                    f"Your account was created, but the database could not be added:\n{error}\n\n"
                                    "You can add it from the dashboard with \"+ Add Database\".")

        self.dashboard_window = DashboardWindow(api, self.parent_window, self.saveGeometry())
        WindowTransition.cross_fade(self, self.dashboard_window, duration=450)

    def toggle_password_main(self):
        if self.password.echoMode() == QLineEdit.EchoMode.Password:
            self.password.setEchoMode(QLineEdit.EchoMode.Normal)
            self.password_btn.setIcon(ab.svg_icon(ab.EYE_OPEN))
        else:
            self.password.setEchoMode(QLineEdit.EchoMode.Password)
            self.password_btn.setIcon(ab.svg_icon(ab.EYE_CLOSED))

    def toggle_password_db(self):
        if self.db_password.echoMode() == QLineEdit.EchoMode.Password:
            self.db_password.setEchoMode(QLineEdit.EchoMode.Normal)
            self.db_password_btn.setIcon(ab.svg_icon(ab.EYE_OPEN))
        else:
            self.db_password.setEchoMode(QLineEdit.EchoMode.Password)
            self.db_password_btn.setIcon(ab.svg_icon(ab.EYE_CLOSED))

    def go_back(self):
        if self.parent_window:
            WindowTransition.cross_fade(self, self.parent_window, duration=450)
        else:
            self.close()
