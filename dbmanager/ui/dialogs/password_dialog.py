"""Ask the owner of a database for its password when it is not known, or the database refused it."""

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from dbmanager.api import describe_connection
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, button, label, show_status
from dbmanager.ui.common.icons import app_icon


class DatabasePasswordDialog(QDialog):
    """password is what was typed once the dialog is accepted, None otherwise."""

    def __init__(self, parent, connection, problem=None):
        super().__init__(parent)
        self.password = None
        self.setWindowTitle("Database Password")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(480)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)

        layout.addWidget(label(f"Password for '{connection['dbName']}'", "heading"))
        layout.addWidget(label(describe_connection(connection), "note"))
        layout.addWidget(label("This app connects to your database itself. Once it works, the password is saved "
                               "with your account (encrypted), so you are not asked again.", wrap=True))
        layout.addSpacing(6)

        layout.addWidget(label(f"Password of {connection['dbUsername']}", "caption"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.accept)
        layout.addWidget(self.password_input)

        self.status = label("", wrap=True)
        layout.addWidget(self.status)
        if problem:
            show_status(self.status, problem, error=True)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(button("Cancel", on_click=self.reject))
        buttons.addWidget(button("Connect", "primary", self.accept))
        layout.addLayout(buttons)
        self.password_input.setFocus()

    def accept(self):
        if not self.password_input.text():
            show_status(self.status, "Type the password, or Cancel.", error=True)
            return
        self.password = self.password_input.text()
        super().accept()


def ask_database_password(parent, connection, problem=None):
    dialog = DatabasePasswordDialog(parent, connection, problem)
    dialog.exec()
    return dialog.password
