"""Delete the signed-in account, after typing its password again."""

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from dbmanager.api import ApiError
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, button, label, show_status
from dbmanager.ui.common.icons import app_icon

DANGER_STYLE = """
    QPushButton { background-color: #dc2626; color: white; font-weight: 600; }
    QPushButton:hover { background-color: #ef4444; }
"""


class DeleteAccountDialog(QDialog):
    """Says what goes with the account and asks for the password; api.delete_account does the rest.
    A wrong password keeps the dialog open. deleted is True once the account is gone."""

    def __init__(self, parent, api, databases=0):
        super().__init__(parent)
        self.api = api
        self.deleted = False
        self.setWindowTitle("Delete Account")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(480)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)

        layout.addWidget(label(f"Delete '{api.username}'?", "heading"))
        saved = (f"your {databases} saved database connection{'s' if databases != 1 else ''}"
                 if databases else "your saved database connections")
        layout.addWidget(label(
            f"This cannot be undone. Going with the account: {saved} and their passwords, every share you "
            "gave (those users lose access) or received, and premium.\n"
            "The databases themselves are not touched.", wrap=True))
        layout.addSpacing(8)

        layout.addWidget(label("Your password", "caption"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("To confirm it is you")
        self.password_input.returnPressed.connect(self.delete)
        layout.addWidget(self.password_input)

        self.status = label("", wrap=True)
        layout.addWidget(self.status)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(button("Cancel", on_click=self.reject))
        self.delete_button = button("Delete account", on_click=self.delete)
        self.delete_button.setStyleSheet(DANGER_STYLE)
        buttons.addWidget(self.delete_button)
        layout.addLayout(buttons)

        self.password_input.setFocus()

    def delete(self):
        password = self.password_input.text()
        if not password:
            show_status(self.status, "Type your password to confirm.", error=True)
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
