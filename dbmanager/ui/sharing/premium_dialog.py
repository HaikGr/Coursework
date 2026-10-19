"""Premium upgrade: prove an email address with a code sent to it. Sharing a database needs premium."""

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from dbmanager.api import ApiError
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.message_box import show_styled_message
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, button, label, show_status


class PremiumDialog(QDialog):
    """Two steps against the server: send a code to an address, then type the code back.

    current is the account's premium link (api.premium_status()) or None; email is the address the
    account was registered with, offered first. After a confirmed code upgraded is True and the dialog
    closes."""

    def __init__(self, parent, api, current=None, email=None):
        super().__init__(parent)
        self.api = api
        self.upgraded = False
        self.code_sent_to = None
        self.setWindowTitle("Premium")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(480)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)

        layout.addWidget(label("Premium", "heading"))
        if current:
            intro = (f"Premium is active, verified with {current.get('connectedEmail')}.\n"
                     "To connect a different address, verify it below.")
        elif email:
            intro = ("Premium lets you share your databases with other users.\n"
                     "Send a code to the address you registered with - or type another one.")
        else:
            intro = ("Premium lets you share your databases with other users.\n"
                     "Verify an email address to upgrade - it is not used for anything else.")
        layout.addWidget(label(intro, wrap=True))
        layout.addSpacing(10)

        layout.addWidget(label("Email address", "caption"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("you@example.com")
        if email and not current:
            self.email_input.setText(email)
        self.email_input.returnPressed.connect(self.send_code)
        self.send_button = button("Send code", on_click=self.send_code)
        layout.addLayout(self._row(self.email_input, self.send_button))

        layout.addWidget(label("Verification code", "caption"))
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("6 digits from the email")
        self.code_input.setMaxLength(6)
        self.code_input.setEnabled(False)
        self.code_input.returnPressed.connect(self.confirm_code)
        self.confirm_button = button("Confirm", "primary", self.confirm_code)
        self.confirm_button.setEnabled(False)
        layout.addLayout(self._row(self.code_input, self.confirm_button))

        self.status = label("", wrap=True)
        layout.addWidget(self.status)
        layout.addStretch()

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(button("Close", on_click=self.reject))
        layout.addLayout(close_row)

        self.email_input.setFocus()

    @staticmethod
    def _row(field, action):
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(field, 1)
        action.setFixedWidth(110)
        row.addWidget(action)
        return row

    def send_code(self):
        email = self.email_input.text().strip()
        if "@" not in email:  # the server checks it properly
            show_status(self.status, "Please enter an email address.", error=True)
            return
        try:
            with busy_cursor():
                message = self.api.request_premium_code(email)
        except ApiError as error:
            show_status(self.status, str(error), error=True)
            return
        self.code_sent_to = email
        self.code_input.setEnabled(True)
        self.confirm_button.setEnabled(True)
        self.code_input.setFocus()
        show_status(self.status, message or f"A code was sent to {email}.")

    def confirm_code(self):
        code = self.code_input.text().strip()
        if not (code.isascii() and code.isdigit() and len(code) == 6):
            show_status(self.status, "The code is the six digits from the email.", error=True)
            return
        try:
            with busy_cursor():
                # The address the code went to, even if the field was edited since
                self.api.confirm_premium(self.code_sent_to, code)
        except ApiError as error:
            show_status(self.status, str(error), error=True)
            return
        self.upgraded = True
        show_styled_message(self, "Premium", "Your account is premium now.\n"
                                             "Use Share next to one of your databases to invite someone.")
        self.accept()
