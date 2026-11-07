"""Forgot Password window: a code mailed to the account's address, then a new password."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from dbmanager.api import ApiClient, ApiError
from dbmanager.i18n import tr
from dbmanager.ui.auth.base import INPUT_STYLE, LINK_BUTTON_STYLE, AuthWindow, PasswordField, primary_button_style
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.live import bind
from dbmanager.ui.common.theme import style

MIN_PASSWORD_LENGTH = 8  # what the server asks of every password
ASK_FOR_EMAIL = "auth.forgot.ask_for_email"


class ForgotPasswordWindow(AuthWindow):
    """Two steps against the server: send a code to the account's address, then type it back with a new
    password - which signs in at once. The server answers the first step the same whether or not an account
    uses the address, so this window cannot tell either."""

    def __init__(self, parent_window, geometry):
        super().__init__("auth.forgot.window_title", card_height=600,
                         card_margins=(30, 40, 30, 30), card_spacing=16,
                         description="auth.forgot.description",
                         features=[], parent_window=parent_window, geometry=geometry)
        self.code_sent_to = None
        # Word-wrapped: the server's answer takes its place, and is longer
        self.subtitle = self.add_heading("auth.forgot.heading", 32, ASK_FOR_EMAIL)

        self.steps = QStackedWidget()
        style(self.steps, "QWidget { background: transparent; }")
        self.steps.addWidget(self._email_step())
        self.steps.addWidget(self._code_step())
        self.card_layout.addWidget(self.steps, stretch=1)

        back_btn = QPushButton()
        bind(back_btn.setText, "auth.forgot.back")
        style(back_btn, LINK_BUTTON_STYLE)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.go_back)
        self.card_layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    # ---------------- The two steps ----------------
    def _email_step(self):
        page, layout = self._page()
        self.email_input = QLineEdit()
        bind(self.email_input.setPlaceholderText, "auth.forgot.email")
        style(self.email_input, INPUT_STYLE)
        self.email_input.returnPressed.connect(self.send_code)
        layout.addWidget(self.email_input)
        layout.addSpacing(12)
        layout.addWidget(self._primary_button("auth.forgot.send_code", self.send_code),
                         alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        return page

    def _code_step(self):
        page, layout = self._page()
        self.code_input = QLineEdit()
        bind(self.code_input.setPlaceholderText, "auth.forgot.code")
        self.code_input.setMaxLength(6)
        style(self.code_input, INPUT_STYLE)
        self.code_input.returnPressed.connect(self.reset_password)
        layout.addWidget(self.code_input)
        self.new_password = PasswordField("auth.forgot.new_password", 320, 50, INPUT_STYLE,
                                          toggle_size=34, icon_size=22, min=MIN_PASSWORD_LENGTH)
        self.new_password.field.returnPressed.connect(self.reset_password)
        layout.addWidget(self.new_password)
        self.repeat_password = PasswordField("auth.forgot.repeat_password", 320, 50, INPUT_STYLE,
                                             toggle_size=34, icon_size=22)
        self.repeat_password.field.returnPressed.connect(self.reset_password)
        layout.addWidget(self.repeat_password)
        layout.addSpacing(6)
        layout.addWidget(self._primary_button("auth.forgot.reset", self.reset_password),
                         alignment=Qt.AlignmentFlag.AlignCenter)

        links = QHBoxLayout()
        resend_btn = QPushButton()
        bind(resend_btn.setText, "auth.forgot.resend")
        bind(resend_btn.setToolTip, "auth.forgot.resend_tip")
        other_btn = QPushButton()
        bind(other_btn.setText, "auth.forgot.other_email")
        for link, action in ((resend_btn, self.send_new_code), (other_btn, self.ask_for_email)):
            style(link, LINK_BUTTON_STYLE)
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
        button = QPushButton()
        bind(button.setText, text)
        button.setFixedSize(200, 50)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        style(button, primary_button_style(radius=25, font_size=16))
        button.clicked.connect(on_click)
        return button

    # ---------------- Actions ----------------
    def send_code(self):
        email = self.email_input.text().strip()
        if not email:
            QMessageBox.warning(self, tr("auth.forgot.input_error"), tr("auth.forgot.enter_email"))
            return
        local, _, domain = email.partition("@")
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            QMessageBox.warning(self, tr("auth.forgot.input_error"), tr("auth.forgot.invalid_email"))
            return
        self._send(email)

    def send_new_code(self):
        self._send(self.code_sent_to)

    def _send(self, email):
        try:
            with busy_cursor():
                message = ApiClient().request_password_reset(email)
        except ApiError as error:
            QMessageBox.warning(self, tr("auth.forgot.title"), str(error))
            return
        # The code goes to this address, even if the field is edited afterwards
        self.code_sent_to = email
        # The server's answer is in the language of the request, and stays in it
        if message:
            bind(self.subtitle.setText, lambda: message)
        else:
            bind(self.subtitle.setText, "auth.forgot.code_sent", email=email)
        self.steps.setCurrentIndex(1)
        self.code_input.clear()
        self.code_input.setFocus()

    def ask_for_email(self):
        bind(self.subtitle.setText, ASK_FOR_EMAIL)
        self.steps.setCurrentIndex(0)
        self.email_input.setFocus()

    def reset_password(self):
        code = self.code_input.text().strip()
        password = self.new_password.text()
        if not (code.isascii() and code.isdigit() and len(code) == 6):
            QMessageBox.warning(self, tr("auth.forgot.input_error"), tr("auth.forgot.bad_code"))
            self.code_input.setFocus()
            return
        if len(password) < MIN_PASSWORD_LENGTH:
            QMessageBox.warning(self, tr("auth.forgot.input_error"),
                                tr("auth.forgot.short_password", min=MIN_PASSWORD_LENGTH))
            self.new_password.field.setFocus()
            return
        if password != self.repeat_password.text():
            QMessageBox.warning(self, tr("auth.forgot.input_error"), tr("auth.forgot.mismatch"))
            self.repeat_password.field.setFocus()
            return

        api = ApiClient()
        try:
            with busy_cursor():
                username = api.reset_password(self.code_sent_to, code, password)
        except ApiError as error:
            QMessageBox.warning(self, tr("auth.forgot.title"), str(error))
            return
        try:
            with busy_cursor():
                api.login(username, password)
        except ApiError as error:
            # The password is changed all the same: signing in is left to the sign-in window
            QMessageBox.information(self, tr("auth.forgot.title"),
                                    tr("auth.forgot.sign_in_failed", error=error, username=username))
            self.parent_window.offer(username)
            self.go_back()
            return
        # The sign-in window owns the dashboard, so logging out lands there
        self.parent_window.open_dashboard(api, self.saveGeometry(), from_window=self)
