"""Share one of your databases: invite a user with the permissions they need, see and revoke access."""

from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLineEdit, QTableWidget, QTableWidgetItem,
    QVBoxLayout
)

from dbmanager.api import ApiError, describe_connection
from dbmanager.model.sharing import PERMISSIONS, describe_permissions, permission_label, sent_for_connection
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.message_box import confirm
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, button, cell, label, show_status

STATUS_TEXT = {"PENDING": "waiting for an answer", "ACCEPTED": "has access", "DECLINED": "declined"}


class ShareDatabaseDialog(QDialog):
    """One invitation per ticked permission (that is how the server grants them); the recipient accepts
    them under Invitations. The table below lists who has, or was offered, access."""

    def __init__(self, parent, api, connection):
        super().__init__(parent)
        self.api = api
        self.connection = connection
        self.permission_ids = {}
        self.setWindowTitle(f"Share {connection['dbName']}")
        self.setWindowIcon(app_icon())
        self.resize(560, 680)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)

        layout.addWidget(label(f"Share '{connection['dbName']}'", "heading"))
        layout.addWidget(label(describe_connection(connection), "note"))
        layout.addSpacing(8)

        layout.addWidget(label("Username", "caption"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Who should get access?")
        self.username_input.returnPressed.connect(self.send)
        layout.addWidget(self.username_input)

        layout.addWidget(label("They may", "caption"))
        self.checkboxes = {}
        for name, allows in PERMISSIONS:
            box = QCheckBox(f"{permission_label(name)}  -  {allows}")
            box.setChecked(name == "SELECT_ROLE")
            self.checkboxes[name] = box
            layout.addWidget(box)
        layout.addWidget(label("Without SELECT they cannot see the tables at all. Changing the structure "
                               "(CREATE, ALTER, DROP) stays with you.", "note", wrap=True))

        send_row = QHBoxLayout()
        self.status = label("", wrap=True)
        send_row.addWidget(self.status, 1)
        self.send_button = button("Send invitation", "primary", self.send)
        send_row.addWidget(self.send_button)
        layout.addLayout(send_row)
        layout.addSpacing(10)

        layout.addWidget(label("Who has access", "caption"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["User", "Permission", "Status", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)
        self.nobody = label("Nobody yet.", "note")
        layout.addWidget(self.nobody)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(button("Close", on_click=self.reject))
        layout.addLayout(close_row)

        self._load()
        self.username_input.setFocus()

    def _load(self):
        try:
            with busy_cursor():
                self.permission_ids = {permission["name"]: permission["id"]
                                       for permission in self.api.list_permissions()}
                invitations = self.api.list_invitations()
        except ApiError as error:
            self.send_button.setEnabled(False)
            show_status(self.status, f"Could not load the sharing details:\n{error}", error=True)
            invitations = []
        self._fill(invitations)

    def _reload_list(self):
        try:
            with busy_cursor():
                invitations = self.api.list_invitations()
        except ApiError as error:
            show_status(self.status, f"Could not reload who has access:\n{error}", error=True)
            return
        self._fill(invitations)

    def _fill(self, invitations):
        rows = sent_for_connection(invitations, self.api.user_id, self.connection["id"])
        self.table.setRowCount(0)
        for invitation in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(invitation.get("toUsername") or ""))
            self.table.setItem(row, 1, QTableWidgetItem(permission_label(invitation.get("permission"))))
            self.table.setItem(row, 2, QTableWidgetItem(STATUS_TEXT.get(invitation.get("status"), "")))
            if invitation.get("status") in ("PENDING", "ACCEPTED"):
                revoke = button("Revoke", "small", lambda _=False, i=invitation: self.revoke(i))
                self.table.setCellWidget(row, 3, cell(revoke))
        self.table.setVisible(bool(rows))
        self.nobody.setVisible(not rows)

    def send(self):
        username = self.username_input.text().strip()
        chosen = [name for name, box in self.checkboxes.items() if box.isChecked()]
        if not username:
            show_status(self.status, "Enter the username of the person to invite.", error=True)
            return
        if not chosen:
            show_status(self.status, "Tick at least one permission.", error=True)
            return

        sent, problems = [], []
        with busy_cursor():
            for name in chosen:
                try:
                    self.api.invite(self.connection["id"], username, self.permission_ids[name])
                    sent.append(name)
                except ApiError as error:
                    if error.status != 400:
                        problems.append(str(error))
                        break  # an unknown user or a lost connection fails every permission the same way
                    problems.append(f"{permission_label(name)}: {error}")

        lines = []
        if sent:
            lines.append(f"Invited {username} to {describe_permissions(sent)}. "
                         "They accept it under Invitations.")
            self.username_input.clear()
        lines.extend(problems)
        show_status(self.status, "\n".join(lines), error=bool(problems))
        if sent:
            self._reload_list()

    def revoke(self, invitation):
        who = invitation.get("toUsername")
        what = permission_label(invitation.get("permission"))
        if not confirm(self, "Revoke Access", f"Take {what} on '{self.connection['dbName']}' away from {who}?"):
            return
        try:
            with busy_cursor():
                self.api.set_invitation_status(invitation["id"], "REVOKED")
        except ApiError as error:
            show_status(self.status, str(error), error=True)
            return
        show_status(self.status, f"{who} no longer has {what}.")
        self._reload_list()
