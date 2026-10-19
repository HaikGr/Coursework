"""Sign In window - the first window of the app."""

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

from dbmanager.api import ApiClient, ApiError
from dbmanager.config import SETTINGS_APPLICATION, SETTINGS_ORGANIZATION
from dbmanager.ui.auth.base import (
    INPUT_STYLE, LINK_BUTTON_STYLE, AuthWindow, PasswordField, primary_button_style
)
from dbmanager.ui.auth.forgot_password import ForgotPasswordWindow
from dbmanager.ui.auth.sign_up import SignUpWindow
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.transitions import WindowTransition
from dbmanager.ui.dashboard.dashboard_window import DashboardWindow


class SignInWindow(AuthWindow):
    def __init__(self):
        super().__init__("Database Management", card_height=600, card_margins=(30, 50, 30, 30),
                         card_spacing=20, fade_duration=400)
        self.add_heading("Welcome Back", 40, "Sign in to continue to your database")

        self.username = QLineEdit()
        self.username.setPlaceholderText("Username or Email")
        self.username.setStyleSheet(INPUT_STYLE)
        self.username.returnPressed.connect(self.attempt_signin)
        self.card_layout.addWidget(self.username)

        self.password = PasswordField("Password", 320, 50, INPUT_STYLE, toggle_size=34, icon_size=22)
        self.password.field.returnPressed.connect(self.attempt_signin)
        self.card_layout.addWidget(self.password)

        # Remember + Forgot
        remember_layout = QHBoxLayout()
        remember_layout.setSpacing(10)
        self.remember = QCheckBox("Remember me")
        self.remember.setStyleSheet("color: #8691a0; font-size: 14px;")
        self.settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        remembered = self.settings.value("remembered_username", "")
        if remembered:
            self.username.setText(remembered)
            self.remember.setChecked(True)
        forgot = QPushButton("Forgot password?")
        forgot.setStyleSheet("color: #3B82F6; background: transparent; border: none;")
        forgot.setCursor(Qt.CursorShape.PointingHandCursor)
        forgot.clicked.connect(self.open_forgot_password)
        remember_layout.addWidget(self.remember)
        remember_layout.addStretch()
        remember_layout.addWidget(forgot)
        self.card_layout.addLayout(remember_layout)
        self.card_layout.addSpacing(30)

        connect_btn = QPushButton("Connect")
        connect_btn.setFixedSize(120, 120)
        connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        connect_btn.setStyleSheet(primary_button_style(radius=60, font_size=18))
        connect_btn.clicked.connect(self.attempt_signin)
        self.card_layout.addWidget(connect_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        signup_row = QHBoxLayout()
        lbl = QLabel("Don't have an account?")
        lbl.setStyleSheet("color:#4B5563; font-size:14px;")
        signup_row.addStretch()
        signup_row.addWidget(lbl)
        signup_btn = QPushButton("SIGN UP")
        signup_btn.setStyleSheet(LINK_BUTTON_STYLE)
        signup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        signup_btn.clicked.connect(self.switch_to_signup)
        signup_row.addWidget(signup_btn)
        signup_row.addStretch()
        self.card_layout.addLayout(signup_row)

        self.dashboard_window = None
        self.signup_window = None
        self.forgot_password_window = None

    def switch_to_signup(self):
        self.signup_window = SignUpWindow(self, self.saveGeometry())
        WindowTransition.cross_fade(self, self.signup_window, duration=450)

    def open_forgot_password(self):
        self.forgot_password_window = ForgotPasswordWindow(self, self.saveGeometry())
        WindowTransition.cross_fade(self, self.forgot_password_window, duration=450)

    def attempt_signin(self):
        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            QMessageBox.warning(self, "Sign In Error", "Please enter both username/email and password.")
            return

        api = ApiClient()
        try:
            with busy_cursor():
                api.login(username, password)
        except ApiError as error:
            QMessageBox.warning(self, "Sign In Error", str(error))
            return

        if self.remember.isChecked():
            self.settings.setValue("remembered_username", username)
        else:
            self.settings.remove("remembered_username")
        self.password.clear()
        self.open_dashboard(api, self.saveGeometry())

    def open_dashboard(self, api, geometry, from_window=None):
        """Show the dashboard for a signed-in session; logging out comes back here."""
        self.dashboard_window = DashboardWindow(api, self, geometry)
        WindowTransition.cross_fade(from_window or self, self.dashboard_window, duration=450)
