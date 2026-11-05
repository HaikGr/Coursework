"""Forgot Password window: a code mailed to the account's address, then a new password."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from dbmanager.api import ApiClient, ApiError
from dbmanager.ui.auth.base import INPUT_STYLE, LINK_BUTTON_STYLE, AuthWindow, PasswordField, primary_button_style
from dbmanager.ui.common.busy import busy_cursor

MIN_PASSWORD_LENGTH = 8  # what the server asks of every password
ASK_FOR_EMAIL = "Enter the email of your account\nto receive a code"


class ForgotPasswordWindow(AuthWindow):
    """Two steps against the server: send a code to the account's address, then type it back with a new
    password - which signs in at once. The server answers the first step the same whether or not an account
    uses the address, so this window cannot tell either."""

    def __init__(self, parent_window, geometry):
        super().__init__("Database Management - Forgot Password", card_height=600,
                         card_margins=(30, 40, 30, 30), card_spacing=16,
                         description="Enter your email to reset your password\nand regain access to your database",
                         features=[], parent_window=parent_window, geometry=geometry)
        self.code_sent_to = None
        self.subtitle = self.add_heading("Forgot Password?", 32, ASK_FOR_EMAIL)
        self.subtitle.setWordWrap(True)  # the server's answer takes its place, and is longer

        self.steps = QStackedWidget()
        self.steps.setStyleSheet("QWidget { background: transparent; }")
        self.steps.addWidget(self._email_step())
        self.steps.addWidget(self._code_step())
        self.card_layout.addWidget(self.steps, stretch=1)

        back_btn = QPushButton("Back to Sign In")
        back_btn.setStyleSheet(LINK_BUTTON_STYLE)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.go_back)
        self.card_layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    # ---------------- The two steps ----------------
    def _email_step(self):
        page, layout = self._page()
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email Address")
        self.email_input.setStyleSheet(INPUT_STYLE)
        self.email_input.returnPressed.connect(self.send_code)
        layout.addWidget(self.email_input)
        layout.addSpacing(12)
        layout.addWidget(self._primary_button("Send Code", self.send_code), alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        return page

    def _code_step(self):
        page, layout = self._page()
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("6-digit code from the email")
        self.code_input.setMaxLength(6)
        self.code_input.setStyleSheet(INPUT_STYLE)
        self.code_input.returnPressed.connect(self.reset_password)
        layout.addWidget(self.code_input)
        self.new_password = PasswordField(f"New password ({MIN_PASSWORD_LENGTH}+ characters)", 320, 50,
                                          INPUT_STYLE, toggle_size=34, icon_size=22)
        self.new_password.field.returnPressed.connect(self.reset_password)
        layout.addWidget(self.new_password)
        self.repeat_password = PasswordField("Repeat the new password", 320, 50, INPUT_STYLE,
                                             toggle_size=34, icon_size=22)
        self.repeat_password.field.returnPressed.connect(self.reset_password)
        layout.addWidget(self.repeat_password)
        layout.addSpacing(6)
        layout.addWidget(self._primary_button("Reset Password", self.reset_password),
                         alignment=Qt.AlignmentFlag.AlignCenter)

        links = QHBoxLayout()
        resend_btn = QPushButton("Send a new code")
        resend_btn.setToolTip("A new code can go out once a minute, a few times a day")
        other_btn = QPushButton("Use another email")
        for link, action in ((resend_btn, self.send_new_code), (other_btn, self.ask_for_email)):
            link.setStyleSheet(LINK_BUTTON_STYLE)
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.clicked.connect(action)
            links.addWidget(link)
        layout.addLayout(links)
        layout.addStretch()
        return page

    @staticmethod
    def _page():
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        return page, layout

    @staticmethod
    def _primary_button(text, on_click):
        button = QPushButton(text)
        button.setFixedSize(200, 50)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(primary_button_style(radius=25, font_size=16))
        button.clicked.connect(on_click)
        return button

    # ---------------- Actions ----------------
    def send_code(self):
        email = self.email_input.text().strip()
        if not email:
            QMessageBox.warning(self, "Input Error", "Please enter your email address.")
            return
        local, _, domain = email.partition("@")
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            QMessageBox.warning(self, "Input Error", "Please enter a valid email address.")
            return
        self._send(email)

    def send_new_code(self):
        self._send(self.code_sent_to)

    def _send(self, email):
        try:
            with busy_cursor():
                message = ApiClient().request_password_reset(email)
        except ApiError as error:
            QMessageBox.warning(self, "Password Reset", str(error))
            return
        # The code goes to this address, even if the field is edited afterwards
        self.code_sent_to = email
        self.subtitle.setText(message or f"If an account uses {email}, a code was sent there.")
        self.steps.setCurrentIndex(1)
        self.code_input.clear()
        self.code_input.setFocus()

    def ask_for_email(self):
        self.subtitle.setText(ASK_FOR_EMAIL)
        self.steps.setCurrentIndex(0)
        self.email_input.setFocus()

    def reset_password(self):
        code = self.code_input.text().strip()
        password = self.new_password.text()
        if not (code.isascii() and code.isdigit() and len(code) == 6):
            QMessageBox.warning(self, "Input Error", "The code is the six digits from the email.")
            self.code_input.setFocus()
            return
        if len(password) < MIN_PASSWORD_LENGTH:
            QMessageBox.warning(self, "Input Error",
                                f"The new password needs at least {MIN_PASSWORD_LENGTH} characters.")
            self.new_password.field.setFocus()
            return
        if password != self.repeat_password.text():
            QMessageBox.warning(self, "Input Error", "The two passwords are not the same.")
            self.repeat_password.field.setFocus()
            return

        api = ApiClient()
        try:
            with busy_cursor():
                username = api.reset_password(self.code_sent_to, code, password)
        except ApiError as error:
            QMessageBox.warning(self, "Password Reset", str(error))
            return
        try:
            with busy_cursor():
                api.login(username, password)
        except ApiError as error:
            # The password is changed all the same: signing in is left to the sign-in window
            QMessageBox.information(self, "Password Reset",
                                    f"Your password was changed, but signing in failed:\n{error}\n\n"
                                    f"Sign in as {username} with the new password.")
            self.parent_window.offer(username)
            self.go_back()
            return
        # The sign-in window owns the dashboard, so logging out lands there
        self.parent_window.open_dashboard(api, self.saveGeometry(), from_window=self)
