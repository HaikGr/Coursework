"""Share one of your databases: invite a user with the permissions they need, see and revoke access.

Each guest gets a login of their own in the database, holding exactly the permissions ticked here, so the
database itself enforces them (see dbmanager.db.guests). This dialog makes and changes those logins right
after the invitations change, from this computer - the owner's - which is the one that can reach it."""

from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLineEdit, QTableWidget, QTableWidgetItem,
    QVBoxLayout
)

from dbmanager.api import ApiError, describe_connection
from dbmanager.db import DatabaseError
from dbmanager.i18n import tr
from dbmanager.model.sharing import PERMISSIONS, describe_permissions, permission_label, sent_for_connection
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.message_box import confirm
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, button, cell, label, show_status
from dbmanager.ui.common.theme import qss

# What each status is called in the list (catalogue keys)
STATUS_TEXT = {"PENDING": "sharing.share.status.pending", "ACCEPTED": "sharing.share.status.accepted",
               "DECLINED": "sharing.share.status.declined"}


class ShareDatabaseDialog(QDialog):
    """One invitation per ticked permission (that is how the server grants them); the recipient accepts
    them under Invitations. The table below lists who has, or was offered, access.

    db (a DatabaseClient) brings the guest logins in the database in line after every change."""

    def __init__(self, parent, api, connection, db=None):
        super().__init__(parent)
        self.api = api
        self.db = db
        self.connection = connection
        self.permission_ids = {}
        self.setWindowTitle(tr("sharing.share.window_title", name=connection['dbName']))
        self.setWindowIcon(app_icon())
        self.resize(560, 680)
        self.setStyleSheet(qss(DIALOG_STYLE))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)

        layout.addWidget(label(tr("sharing.share.heading", name=connection['dbName']), "heading"))
        layout.addWidget(label(describe_connection(connection), "note"))
        layout.addSpacing(8)

        layout.addWidget(label(tr("sharing.share.username"), "caption"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText(tr("sharing.share.username_placeholder"))
        self.username_input.returnPressed.connect(self.send)
        layout.addWidget(self.username_input)

        layout.addWidget(label(tr("sharing.share.they_may"), "caption"))
        self.checkboxes = {}
        for name, allows in PERMISSIONS:
            box = QCheckBox(tr("sharing.share.permission_option", permission=permission_label(name), allows=allows))
            box.setChecked(name == "SELECT_ROLE")
            self.checkboxes[name] = box
            layout.addWidget(box)
        layout.addWidget(label(tr("sharing.share.permissions_note"), "note", wrap=True))

        send_row = QHBoxLayout()
        self.status = label("", wrap=True)
        send_row.addWidget(self.status, 1)
        self.send_button = button(tr("sharing.share.send"), "primary", self.send)
        send_row.addWidget(self.send_button)
        layout.addLayout(send_row)
        layout.addSpacing(10)

        layout.addWidget(label(tr("sharing.share.who_has_access"), "caption"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([tr("sharing.share.column.user"), tr("sharing.share.column.permission"),
                                              tr("sharing.share.column.status"), ""])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)
        self.nobody = label(tr("sharing.share.nobody"), "note")
        layout.addWidget(self.nobody)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(button(tr("common.close"), on_click=self.reject))
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
            show_status(self.status, tr("sharing.share.load_failed", error=error), error=True)
            invitations = []
        self._fill(invitations)

    def _reload_list(self):
        try:
            with busy_cursor():
                invitations = self.api.list_invitations()
        except ApiError as error:
            show_status(self.status, tr("sharing.share.reload_failed", error=error), error=True)
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
            status = invitation.get("status")
            self.table.setItem(row, 2, QTableWidgetItem(tr(STATUS_TEXT[status]) if status in STATUS_TEXT else ""))
            if status in ("PENDING", "ACCEPTED"):
                revoke = button(tr("sharing.share.revoke"), "small", lambda _=False, i=invitation: self.revoke(i))
                self.table.setCellWidget(row, 3, cell(revoke))
        self.table.setVisible(bool(rows))
        self.nobody.setVisible(not rows)

    def send(self):
        username = self.username_input.text().strip()
        chosen = [name for name, box in self.checkboxes.items() if box.isChecked()]
        if not username:
            show_status(self.status, tr("sharing.share.no_username"), error=True)
            return
        if not chosen:
            show_status(self.status, tr("sharing.share.no_permission"), error=True)
            return

        sent, problems = [], []
        with busy_cursor():
            for name in chosen:
                try:
                    invitation = self.api.invite(self.connection["id"], username, self.permission_ids[name])
                    sent.append((name, invitation["id"]))
                except ApiError as error:
                    if error.status != 400:
                        problems.append(str(error))
                        break  # an unknown user or a lost connection fails every permission the same way
                    problems.append(f"{permission_label(name)}: {error}")

        if sent:
            failure = self._update_logins()
            if failure is not None:
                # A share the database cannot carry out is no share: take the invitations back
                for _, invitation_id in sent:
                    try:
                        self.api.delete_invitation(invitation_id)
                    except ApiError:
                        pass
                show_status(self.status, tr("sharing.share.not_shared", username=username, error=failure), error=True)
                self._reload_list()
                return

        lines = []
        if sent:
            lines.append(tr("sharing.share.invited", username=username,
                            permissions=describe_permissions(name for name, _ in sent)))
            self.username_input.clear()
        lines.extend(problems)
        show_status(self.status, "\n".join(lines), error=bool(problems))
        if sent:
            self._reload_list()

    def _update_logins(self):
        """Make, re-grant or drop the guest logins in the database; None when it worked, else why not."""
        if self.db is None:
            return None
        try:
            with busy_cursor():
                self.db.sync_guests(self.connection)
        except (DatabaseError, ApiError) as error:
            return str(error)
        return None

    def revoke(self, invitation):
        who = invitation.get("toUsername")
        what = permission_label(invitation.get("permission"))
        if not confirm(self, tr("sharing.share.revoke_title"),
                       tr("sharing.share.revoke_question", permission=what, name=self.connection['dbName'],
                          username=who)):
            return
        try:
            with busy_cursor():
                self.api.set_invitation_status(invitation["id"], "REVOKED")
        except ApiError as error:
            show_status(self.status, str(error), error=True)
            return
        failure = self._update_logins()
        if failure is None:
            show_status(self.status, tr("sharing.share.revoked", username=who, permission=what))
        else:
            show_status(self.status, tr("sharing.share.revoked_not_in_database", username=who, permission=what,
                                        error=failure), error=True)
        self._reload_list()
