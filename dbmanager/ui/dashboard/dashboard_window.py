from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from dbmanager.api import ApiError, only_this_computer
from dbmanager.db import DatabaseClient, DatabaseError
from dbmanager.model.sharing import pending_count, shares_by_connection
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.message_box import confirm, show_styled_message
from dbmanager.ui.common.transitions import WindowTransition
from dbmanager.ui.dashboard.side_bar import SideBar
from dbmanager.ui.dashboard.tool_bar import Toolbar
from dbmanager.ui.dashboard.top_bar import TopBar
from dbmanager.ui.diagram.diagram_page import DiagramPage
from dbmanager.ui.dialogs.delete_account_dialog import DeleteAccountDialog
from dbmanager.ui.dialogs.password_dialog import ask_database_password
from dbmanager.ui.query.help_dialog import QueryHelpDialog
from dbmanager.ui.query.query_builder import SQLQueryBuilder
from dbmanager.ui.sharing.invitations_dialog import InvitationsDialog
from dbmanager.ui.sharing.premium_dialog import PremiumDialog
from dbmanager.ui.sharing.share_dialog import ShareDatabaseDialog


class DashboardWindow(QMainWindow):
    """Sidebar | toolbar over the diagram or a table page | SQL query builder.

    api talks to the server (accounts, the list of databases, sharing); db reaches the databases themselves
    from this computer, asking the owner for a password it does not know yet."""

    def __init__(self, api, parent_window=None, geometry=None, db=None):
        super().__init__()
        self.setWindowTitle("SQL Query Builder - Dashboard")
        self.setWindowIcon(app_icon())
        self.parent_window = parent_window
        self.api = api
        self.db = db if db is not None else DatabaseClient(api, ask_password=self._ask_password)
        self.username = api.username

        if geometry:
            self.restoreGeometry(geometry)

        self.setStyleSheet("QWidget { background-color: #f5f6f7; }")
        self.setMinimumSize(1000, 620)  # fits a 1366x768 laptop, and 1920x1080 at 150% scaling

        main_widget = QWidget()
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(main_widget)
        self.top_bar = TopBar(self.username)
        # The token's roles are a start; a later upgrade is only known by asking (see open_premium)
        self.top_bar.set_premium("PREMIUM" in (api.roles or []))
        self.top_bar.invitations_clicked.connect(self.open_invitations)
        self.top_bar.premium_clicked.connect(self.open_premium)
        self.top_bar.delete_account_clicked.connect(self.delete_account)
        self.top_bar.logout_clicked.connect(self.log_out)
        root_layout.addWidget(self.top_bar)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(0)
        body_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addLayout(body_layout)

        self.sql_builder = SQLQueryBuilder(self.db)

        # One toolbar for the diagram and every table page: it shapes the query builder's query
        self.toolbar = Toolbar()
        self.toolbar.aggregate_selected.connect(self.sql_builder.set_aggregate)
        self.toolbar.count_rows_toggled.connect(self.sql_builder.set_count_rows)
        self.toolbar.distinct_toggled.connect(self.sql_builder.set_distinct)
        self.toolbar.limit_changed.connect(self.sql_builder.set_limit)
        self.toolbar.help_requested.connect(lambda: QueryHelpDialog(self).exec())
        self.sql_builder.query_changed.connect(
            lambda: self.toolbar.sync(self.sql_builder.model, self.sql_builder.selected_column()))

        self.stacked_center = QStackedWidget()
        self.diagram_page = DiagramPage(sql_builder=self.sql_builder)
        self.stacked_center.addWidget(self.diagram_page)

        center = QWidget()
        center.setMinimumWidth(420)  # the toolbar wraps and the diagram scrolls
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(self.toolbar)
        center_layout.addWidget(self.stacked_center)

        # Created after the diagram page: it loads the user's databases from the server
        self.sidebar_widget = SideBar(self.stacked_center, self.diagram_page, api, self.sql_builder, db=self.db)
        self.sidebar_widget.logout_requested.connect(self.log_out)
        self.sidebar_widget.share_requested.connect(self.share_database)
        self.sidebar_widget.databases_reloaded.connect(self.refresh_invitations)
        self.refresh_invitations()  # the sidebar loaded its databases before it could say so

        body_layout.addWidget(self.sidebar_widget)
        body_layout.addWidget(center, stretch=3)
        body_layout.addWidget(self.sql_builder, stretch=1)

        self._first_show = True

    def _ask_password(self, connection, problem):
        return ask_database_password(self, connection, problem)

    # ---------------- Sharing ----------------
    def refresh_invitations(self):
        """Count the invitations waiting for an answer, and tell the sidebar who shared what"""
        try:
            invitations = self.api.list_invitations()
        except ApiError:
            return  # only the badge and the tooltips go stale; the databases loaded (or said why not)
        self.top_bar.set_pending_invitations(pending_count(invitations, self.api.user_id))
        self.sidebar_widget.describe_shares(shares_by_connection(invitations, self.api.user_id))

    def open_invitations(self):
        dialog = InvitationsDialog(self, self.api)
        dialog.exec()
        if dialog.changed:
            self.sidebar_widget.reload_databases()  # an accepted database appears; this also recounts
        else:
            self.refresh_invitations()

    def _premium_status(self):
        """(known, link): known is False when the server could not be asked (the user was told why)"""
        try:
            with busy_cursor():
                link = self.api.premium_status()
        except ApiError as error:
            show_styled_message(self, "Premium", f"Could not check your account:\n{error}", QMessageBox.Icon.Warning)
            return False, None
        self.top_bar.set_premium(link is not None)
        return True, link

    def _account_email(self):
        """The address the account was registered with, offered for premium; None without one"""
        try:
            return (self.api.account() or {}).get("email")
        except ApiError:
            return None  # the user can still type an address

    def open_premium(self):
        """Upgrade (or move premium to another address). True when the account is premium afterwards."""
        known, link = self._premium_status()
        if not known:
            return False
        dialog = PremiumDialog(self, self.api, link, email=None if link else self._account_email())
        dialog.exec()
        if dialog.upgraded:
            self.top_bar.set_premium(True)
        return dialog.upgraded or link is not None

    def share_database(self, connection):
        """Sharing is premium: an account that is not gets the chance to upgrade first"""
        if only_this_computer(connection["host"]):
            # A guest's app connects to the same host name - on their computer, localhost is theirs
            show_styled_message(self, "Share Database",
                                f"'{connection['dbName']}' is saved with the host '{connection['host']}', which "
                                "only means this computer. Other people reach it by its network address.\n\n"
                                "Edit the connection to use that address (for example 192.168.1.20), and make sure "
                                "the database accepts connections from your network, then share it.",
                                QMessageBox.Icon.Warning)
            return
        known, link = self._premium_status()
        if not known:
            return
        if link is None:
            if not confirm(self, "Share Database",
                           "Sharing a database is a premium feature.\n"
                           "Verify an email address now to upgrade?"):
                return
            dialog = PremiumDialog(self, self.api, email=self._account_email())
            dialog.exec()
            if not dialog.upgraded:
                return
            self.top_bar.set_premium(True)
        ShareDatabaseDialog(self, self.api, connection, self.db).exec()

    # ---------------- Account ----------------
    def delete_account(self):
        owned = [entry["connection"] for entry in self.sidebar_widget.databases.values()
                 if entry["connection"].get("ownerUserId") == self.api.user_id]
        dialog = DeleteAccountDialog(self, self.api, len(owned))
        shared = self._shared_databases(owned)  # asked before: the server forgets them with the account
        dialog.exec()
        if not dialog.deleted:
            return
        left = self._drop_guest_logins(shared)
        for connection in owned:
            self.db.forget(connection["id"])
        text = f"The account '{self.username}' was deleted."
        if left:
            text += ("\n\nThe logins made for your guests could not be removed from: " + ", ".join(left) +
                     ". Drop the users called dbm_u… there yourself.")
        show_styled_message(self, "Account Deleted", text)
        if self.parent_window:
            self.parent_window.forget(self.username)
        self._leave()  # the session ended with the account: this only goes back to signing in

    def _shared_databases(self, owned):
        """The databases among these that had guest logins made in them."""
        shared = []
        for connection in owned:
            try:
                if self.api.list_guest_accounts(connection["id"]):
                    shared.append(connection)
            except ApiError:
                pass
        return shared

    def _drop_guest_logins(self, connections):
        """After the account went: drop its guests' logins from its databases. Returns the names it could not."""
        self.db.ask_password = None  # only with a password already known: the session is over
        left = []
        with busy_cursor():
            for connection in connections:
                try:
                    self.db.drop_guest_logins(connection)
                except DatabaseError:
                    left.append(connection["dbName"])
        return left

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.setWindowOpacity(0.0)
            QTimer.singleShot(50, lambda: WindowTransition.fade_in(self, duration=400))

    def _end_session(self):
        self.db.end_session()
        try:
            self.api.logout()
        except ApiError:
            pass  # the token is dropped locally either way

    def _may_leave(self, action):
        """True when nothing waits for Run Query, or the user agrees to lose it"""
        count = self.sidebar_widget.unsaved_changes()
        if not count:
            return True
        return confirm(self, action, f"{count} change{'s are' if count != 1 else ' is'} not saved to the database "
                                     "yet - only Run Query saves them.\n\n"
                                     f"{action} anyway and lose {'them' if count != 1 else 'it'}?")

    def log_out(self):
        if self._may_leave("Log Out"):
            self._leave()

    def _leave(self):
        self._end_session()
        if self.parent_window:
            WindowTransition.cross_fade(self, self.parent_window, duration=400)
        else:
            self.close()

    def closeEvent(self, event):
        # Closing the window ends the app: revoke the token instead of leaving it valid until it expires
        if self.api.signed_in:
            if not self._may_leave("Quit"):
                event.ignore()
                return
            self._end_session()
        super().closeEvent(event)
