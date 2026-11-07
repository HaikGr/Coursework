"""Delete the signed-in account, after typing its password again."""

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from dbmanager.api import ApiError
from dbmanager.i18n import tr, trn
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, button, label, show_status
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.theme import qss

# A theme.qss template
DANGER_STYLE = """
    QPushButton { background-color: @danger; color: @on_danger; font-weight: 600; }
    QPushButton:hover { background-color: @danger_hover; }
"""


class DeleteAccountDialog(QDialog):
    """Says what goes with the account and asks for the password; api.delete_account does the rest.
    A wrong password keeps the dialog open. deleted is True once the account is gone."""

    def __init__(self, parent, api, databases=0):
        super().__init__(parent)
        self.api = api
        self.deleted = False
        self.setWindowTitle(tr("dialogs.delete_account.title"))
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(480)
        self.setStyleSheet(qss(DIALOG_STYLE))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)

        layout.addWidget(label(tr("dialogs.delete_account.heading", username=api.username), "heading"))
        saved = (trn("dialogs.delete_account.saved_count", databases)
                 if databases else tr("dialogs.delete_account.saved_all"))
        layout.addWidget(label(tr("dialogs.delete_account.consequences", saved=saved), wrap=True))
        layout.addSpacing(8)

        layout.addWidget(label(tr("dialogs.delete_account.password"), "caption"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText(tr("dialogs.delete_account.password_placeholder"))
        self.password_input.returnPressed.connect(self.delete)
        layout.addWidget(self.password_input)

        self.status = label("", wrap=True)
        layout.addWidget(self.status)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(button(tr("common.cancel"), on_click=self.reject))
        self.delete_button = button(tr("dialogs.delete_account.delete"), on_click=self.delete)
        self.delete_button.setStyleSheet(qss(DANGER_STYLE))
        buttons.addWidget(self.delete_button)
        layout.addLayout(buttons)

        self.password_input.setFocus()

    def delete(self):
        password = self.password_input.text()
        if not password:
            show_status(self.status, tr("dialogs.delete_account.no_password"), error=True)
            return
        try:
            with busy_cursor():
                self.api.delete_account(password)
        except ApiError as error:
            show_status(self.status, str(error), error=True)
            self.password_input.selectAll()
            return
        self.deleted = True
        self.accept()
