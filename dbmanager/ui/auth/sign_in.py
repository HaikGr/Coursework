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
from dbmanager.i18n import tr
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.live import bind
from dbmanager.ui.common.theme import style
from dbmanager.ui.common.transitions import WindowTransition
from dbmanager.ui.dashboard.dashboard_window import DashboardWindow


class SignInWindow(AuthWindow):
    def __init__(self):
        super().__init__("auth.app_title", card_height=600, card_margins=(30, 50, 30, 30),
                         card_spacing=20, fade_duration=400)
        self.add_heading("auth.sign_in.heading", 40, "auth.sign_in.subtitle")

        self.username = QLineEdit()
        bind(self.username.setPlaceholderText, "auth.sign_in.username")
        style(self.username, INPUT_STYLE)
        self.username.returnPressed.connect(self.attempt_signin)
        self.card_layout.addWidget(self.username)

        self.password = PasswordField("auth.sign_in.password", 320, 50, INPUT_STYLE, toggle_size=34, icon_size=22)
        self.password.field.returnPressed.connect(self.attempt_signin)
        self.card_layout.addWidget(self.password)

        # Remember + Forgot
        remember_layout = QHBoxLayout()
        remember_layout.setSpacing(10)
        self.remember = QCheckBox()
        bind(self.remember.setText, "auth.sign_in.remember")
        style(self.remember, "QCheckBox { color: @auth_text; font-size: 14px; }")
        self.settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        remembered = self.settings.value("remembered_username", "")
        if remembered:
            self.username.setText(remembered)
            self.remember.setChecked(True)
        forgot = QPushButton()
        bind(forgot.setText, "auth.sign_in.forgot")
        style(forgot, LINK_BUTTON_STYLE)
        forgot.setCursor(Qt.CursorShape.PointingHandCursor)
        forgot.clicked.connect(self.open_forgot_password)
        remember_layout.addWidget(self.remember)
        remember_layout.addStretch()
        remember_layout.addWidget(forgot)
        self.card_layout.addLayout(remember_layout)
        self.card_layout.addSpacing(30)

        connect_btn = QPushButton()
        bind(connect_btn.setText, "auth.sign_in.connect")
        connect_btn.setFixedSize(120, 120)
        connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        style(connect_btn, primary_button_style(radius=60, font_size=18))
        connect_btn.clicked.connect(self.attempt_signin)
        self.card_layout.addWidget(connect_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        signup_row = QHBoxLayout()
        lbl = QLabel()
        bind(lbl.setText, "auth.sign_in.no_account")
        style(lbl, "QLabel { color: @auth_text; font-size: 14px; }")
        signup_row.addStretch()
        signup_row.addWidget(lbl)
        signup_btn = QPushButton()
        bind(signup_btn.setText, "auth.sign_in.sign_up")
        style(signup_btn, LINK_BUTTON_STYLE)
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
            QMessageBox.warning(self, tr("auth.sign_in.error_title"), tr("auth.sign_in.missing"))
            return

        api = ApiClient()
        try:
            with busy_cursor():
                api.login(username, password)
        except ApiError as error:
            QMessageBox.warning(self, tr("auth.sign_in.error_title"), str(error))
            return

        if self.remember.isChecked():
            self.settings.setValue("remembered_username", username)
        else:
            self.settings.remove("remembered_username")
        self.password.clear()
        self.open_dashboard(api, self.saveGeometry())

    def offer(self, username):
        """The account whose password was just reset, to sign in to"""
        self.username.setText(username)
        self.password.clear()
        self.password.field.setFocus()

    def forget(self, username):
        """A deleted account is not offered again"""
        if self.settings.value("remembered_username", "") == username:
            self.settings.remove("remembered_username")
            self.remember.setChecked(False)
        if self.username.text().strip() == username:
            self.username.clear()

    def open_dashboard(self, api, geometry, from_window=None):
        """Show the dashboard for a signed-in session; logging out comes back here."""
        self.dashboard_window = DashboardWindow(api, self, geometry)
        WindowTransition.cross_fade(from_window or self, self.dashboard_window, duration=450)
