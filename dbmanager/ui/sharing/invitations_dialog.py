"""Invitations other users sent you: accept or decline what they offer on their databases."""

from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout
)

from dbmanager.api import DB_TYPES, ApiError
from dbmanager.model.sharing import describe_permissions, received_groups
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, button, cell, label, show_status

DB_TYPE_LABELS = {value: text for value, text, _ in DB_TYPES}


class InvitationsDialog(QDialog):
    """One row per database and sender: Accept or Decline answers all the permissions offered at once.
    changed is True once anything was answered, so the caller reloads the database list."""

    def __init__(self, parent, api):
        super().__init__(parent)
        self.api = api
        self.changed = False
        self.setWindowTitle("Invitations")
        self.setWindowIcon(app_icon())
        self.resize(640, 420)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)

        layout.addWidget(label("Invitations", "heading"))
        layout.addWidget(label("Databases other users share with you. Accepting adds the database to your list; "
                               "what you may do there is what its owner offered.", "note", wrap=True))
        layout.addSpacing(6)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["From", "Database", "You may", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (0, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)
        self.empty = label("No invitations right now.", "note")
        layout.addWidget(self.empty)

        self.status = label("", wrap=True)
        layout.addWidget(self.status)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(button("Close", on_click=self.reject))
        layout.addLayout(close_row)

        self._load()

    def _load(self):
        try:
            with busy_cursor():
                invitations = self.api.list_invitations()
        except ApiError as error:
            show_status(self.status, f"Could not load your invitations:\n{error}", error=True)
            invitations = []
        groups = received_groups(invitations, self.api.user_id)

        self.table.setRowCount(0)
        for group in groups:
            row = self.table.rowCount()
            self.table.insertRow(row)
            database = group["dbName"]
            if group["dbType"]:
                database += f"  ({DB_TYPE_LABELS.get(group['dbType'], group['dbType'])})"
            permissions = [invitation.get("permission") for invitation in group["invitations"]]
            self.table.setItem(row, 0, QTableWidgetItem(group["fromUsername"]))
            self.table.setItem(row, 1, QTableWidgetItem(database))
            self.table.setItem(row, 2, QTableWidgetItem(describe_permissions(permissions)))
            if group["status"] == "PENDING":
                self.table.setCellWidget(row, 3, cell(
                    button("Accept", "small_primary", lambda _=False, g=group: self.answer(g, "ACCEPTED")),
                    button("Decline", "small", lambda _=False, g=group: self.answer(g, "DECLINED"))))
            else:
                self.table.setItem(row, 3, QTableWidgetItem("accepted"))
        self.table.setVisible(bool(groups))
        self.empty.setVisible(not groups)

    def answer(self, group, status):
        try:
            with busy_cursor():
                for invitation in group["invitations"]:
                    self.api.set_invitation_status(invitation["id"], status)
        except ApiError as error:
            show_status(self.status, str(error), error=True)
        else:
            verb = "accepted" if status == "ACCEPTED" else "declined"
            show_status(self.status, f"You {verb} {group['fromUsername']}'s invitation to '{group['dbName']}'.")
        self.changed = True  # even a half-answered group changed something
        self._load()
