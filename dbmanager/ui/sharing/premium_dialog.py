"""Premium upgrade: prove an email address with a code sent to it. Sharing a database needs premium."""

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from dbmanager.api import ApiError
from dbmanager.i18n import tr
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.message_box import show_styled_message
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, button, label, show_status
from dbmanager.ui.common.theme import qss


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
        self.setWindowTitle(tr("sharing.premium.title"))
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(480)
        self.setStyleSheet(qss(DIALOG_STYLE))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)

        layout.addWidget(label(tr("sharing.premium.title"), "heading"))
        if current:
            intro = tr("sharing.premium.intro_active", email=current.get('connectedEmail'))
        elif email:
            intro = tr("sharing.premium.intro_registered")
        else:
            intro = tr("sharing.premium.intro_new")
        layout.addWidget(label(intro, wrap=True))
        layout.addSpacing(10)

        layout.addWidget(label(tr("sharing.premium.email"), "caption"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText(tr("sharing.premium.email_placeholder"))
        if email and not current:
            self.email_input.setText(email)
        self.email_input.returnPressed.connect(self.send_code)
        self.send_button = button(tr("sharing.premium.send_code"), on_click=self.send_code)
        layout.addLayout(self._row(self.email_input, self.send_button))

        layout.addWidget(label(tr("sharing.premium.code"), "caption"))
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText(tr("sharing.premium.code_placeholder"))
        self.code_input.setMaxLength(6)
        self.code_input.setEnabled(False)
        self.code_input.returnPressed.connect(self.confirm_code)
        self.confirm_button = button(tr("sharing.premium.confirm"), "primary", self.confirm_code)
        self.confirm_button.setEnabled(False)
        layout.addLayout(self._row(self.code_input, self.confirm_button))

        self.status = label("", wrap=True)
        layout.addWidget(self.status)
        layout.addStretch()

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(button(tr("common.close"), on_click=self.reject))
        layout.addLayout(close_row)

        self.email_input.setFocus()

    @staticmethod
    def _row(field, action):
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(field, 1)
        action.setMinimumWidth(110)  # wider only for a longer translation
        row.addWidget(action)
        return row

    def send_code(self):
        email = self.email_input.text().strip()
        if "@" not in email:  # the server checks it properly
            show_status(self.status, tr("sharing.premium.no_email"), error=True)
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
        show_status(self.status, message or tr("sharing.premium.code_sent", email=email))

    def confirm_code(self):
        code = self.code_input.text().strip()
        if not (code.isascii() and code.isdigit() and len(code) == 6):
            show_status(self.status, tr("sharing.premium.bad_code"), error=True)
            return
        try:
            with busy_cursor():
                # The address the code went to, even if the field was edited since
                self.api.confirm_premium(self.code_sent_to, code)
        except ApiError as error:
            show_status(self.status, str(error), error=True)
            return
        self.upgraded = True
        show_styled_message(self, tr("sharing.premium.title"), tr("sharing.premium.upgraded"))
        self.accept()
