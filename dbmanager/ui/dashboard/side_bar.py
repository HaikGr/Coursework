from functools import partial

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton, QToolButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget
)

from dbmanager.api import ApiError, describe_connection
from dbmanager.config import TABLE_PREVIEW_ROWS
from dbmanager.db import DatabaseError
from dbmanager.i18n import tr, trn
from dbmanager.model.change_script import build_change_script, references_to
from dbmanager.model.table_state import schema_column, schema_details
from dbmanager.model.sharing import describe_permissions
from dbmanager.sql import generator as sqlgen
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.live import bind, unbind
from dbmanager.ui.common.message_box import confirm, show_styled_message
from dbmanager.ui.common.style import MENU_STYLE
from dbmanager.ui.common.theme import color, qss, style
from dbmanager.ui.dialogs.database_dialog import InputDatabaseWindow
from dbmanager.ui.dialogs.table_name_dialog import InputTableNameWindow
from dbmanager.ui.table_editor.table_details_page import TableDetailsPage

ROLE = Qt.ItemDataRole.UserRole
NAME = Qt.ItemDataRole.UserRole + 1
CONNECTION_ID = Qt.ItemDataRole.UserRole + 2


# What the ⋮ menu of a database you own offers: (key, catalogue key of its text). There is no Test: opening a
# database (and ⟳) reads it, which offers to fix its settings when it cannot be reached, and Edit tests what it saves.
DATABASE_ACTIONS = [
    ("edit", "dashboard.sidebar.menu.edit"),
    ("share", "dashboard.sidebar.menu.share"),
    ("delete", "dashboard.sidebar.menu.delete"),
]


def _table_item_text(name, view=False, dropping=False):
    if dropping:
        return f"  ⊠  {name}  {tr('dashboard.sidebar.drop_mark')}"
    return f"  {'⊡' if view else '⊞'}  {name}"


def _rename_in_link(link, table_name, old_name, new_name):
    pk_table, pk_field, fk_table, fk_field = link
    if pk_table == table_name and pk_field == old_name:
        pk_field = new_name
    if fk_table == table_name and fk_field == old_name:
        fk_field = new_name
    return pk_table, pk_field, fk_table, fk_field


class SideBar(QWidget):
    """Databases of the signed-in user (the list comes from the server) and their tables (read from each
    database itself, by db - a DatabaseClient).

    The diagram shows the tables of one database at a time - the active one. Each database keeps
    its own table pages and PK-FK links, so switching back and forth loses nothing.

    Edits made in the table pages are collected here into one SQL script per database and shown
    in the SQL panel; Run Query runs it on the database, which is then read back.

    A database you own has Share and a ⋮ menu (also on right-click): edit its connection, share it,
    delete it. Share asks the dashboard to share it (share_requested carries the connection).
    """
    logout_requested = pyqtSignal()
    share_requested = pyqtSignal(object)
    databases_reloaded = pyqtSignal()

    def __init__(self, stack_widget, diagram_page, api=None, sql_builder=None, db=None):
        super().__init__()
        self.stacked_center = stack_widget
        self.diagram = diagram_page
        self.api = api
        self.db = db
        self.sql_builder = sql_builder
        self.page_map = {}   # (connection_id, table_name) -> TableDetailsPage
        # connection_id -> {"item", "connection", "schema_loaded", "links", "db_links"}
        # links: PK-FK links drawn on the diagram; db_links: the foreign keys the database already has
        self.databases = {}
        self.active_db = None
        # connection_id -> (owner's username, [permission names]) for the databases shared with the user
        self.shares = {}
        # databases you own whose guest logins were brought in line with the invitations this session
        self.guests_checked = set()

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        self.setLayout(sidebar_layout)
        self.setFixedWidth(260)
        style(self, "QWidget { background-color: @surface; }")

        # Header
        databases_text = QFrame()
        databases_text.setFixedHeight(44)
        style(databases_text, """
            QFrame {
                background-color: @highlight;
                border: none;
            }
        """)
        dt_layout = QHBoxLayout(databases_text)
        dt_layout.setContentsMargins(16, 0, 16, 0)
        lbl_db = QLabel()
        bind(lbl_db.setText, "dashboard.sidebar.databases")
        style(lbl_db, "QLabel { color: @on_highlight; font-size: 16px; font-weight: 600; background: transparent; }")
        dt_layout.addWidget(lbl_db)
        dt_layout.addStretch()

        refresh_btn = QPushButton("⟳")
        bind(refresh_btn.setToolTip, "dashboard.sidebar.refresh_tip")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        style(refresh_btn, """
            QPushButton {
                color: @on_highlight; background: transparent; border: none; font-size: 16px; font-weight: bold;
            }
            QPushButton:hover { color: @accent_text; }
        """)
        refresh_btn.clicked.connect(self.refresh)
        dt_layout.addWidget(refresh_btn)

        # Tree widget for databases
        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderHidden(True)
        self.db_tree.setIndentation(16)
        self.db_tree.setAnimated(True)
        self.db_tree.setRootIsDecorated(False)
        style(self.db_tree, """
            QTreeWidget {
                background-color: @surface;
                border: none;
                outline: none;
                font-size: 13px;
            }
            QTreeWidget::item {
                height: 38px;
                padding-left: 0px;
                margin: 0px;
                color: @text;
                border: none;
            }
            QTreeWidget::item:hover {
                background-color: @surface_hover;
            }
            QTreeWidget::item:selected {
                background-color: @selection;
                color: @on_selection;
            }
            QTreeWidget::branch {
                background: transparent;
            }
        """)
        self.db_tree.itemClicked.connect(self.on_tree_click)
        self.db_tree.itemDoubleClicked.connect(self.on_tree_double_click)
        self.db_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.db_tree.customContextMenuRequested.connect(self._on_tree_menu)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.db_tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.add_db_button = QPushButton()
        bind(self.add_db_button.setText, "common.action.add_database")
        self.add_db_button.setCursor(Qt.CursorShape.PointingHandCursor)
        style(self.add_db_button, """
            QPushButton {
                background-color: @surface_alt;
                color: @text_secondary;
                font-size: 13px;
                font-weight: 500;
                border-radius: 6px;
                padding: 10px;
                margin: 10px;
                border: 1px dashed @border_strong;
            }
            QPushButton:hover {
                background-color: @accent_subtle;
                border: 1px dashed @accent;
                color: @accent_text;
            }
        """)
        self.add_db_button.clicked.connect(self.add_database)

        logout_button = QPushButton()
        bind(logout_button.setText, "dashboard.sidebar.log_out")
        logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        style(logout_button, """
            QPushButton {
                background-color: @danger;
                color: @on_danger;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px;
                margin: 0px 10px 10px 10px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: @danger_hover;
            }
        """)
        logout_button.clicked.connect(self.logout_requested.emit)

        sidebar_layout.addWidget(databases_text)
        sidebar_layout.addWidget(self.db_tree, 1)
        sidebar_layout.addWidget(self.add_db_button)
        sidebar_layout.addWidget(logout_button)

        if self.sql_builder:
            self.sql_builder.script_executed.connect(self._on_script_executed)
            self.sql_builder.discard_requested.connect(self.discard_changes)
            # Checked before anything runs: MySQL commits each ALTER at once, so a run must not stop halfway
            self.sql_builder.check_before_run = lambda: self.problems(self.active_db)
        self.diagram.table_area.connections_changed.connect(lambda: self._refresh_change_script(self.active_db))
        # A link the database already has as a foreign key cannot be taken back from the diagram
        self.diagram.is_saved_link = (
            lambda link: link in self.databases.get(self.active_db, {}).get("db_links", ()))
        self.diagram.open_table_requested.connect(self._open_from_diagram)
        self.diagram.drop_table_requested.connect(lambda name: self._drop_from_page(self.active_db, name))
        self.diagram.delete_field_requested.connect(self._delete_field_from_diagram)

        self.reload_databases()

    # ---------------- Databases ----------------
    def refresh(self):
        """Reload the database list, and the tables of the selected database"""
        if self.active_db in self.databases and self._pending_statements(self.active_db):
            if not confirm(self, tr("dashboard.sidebar.reload_title"), tr("dashboard.sidebar.reload_discard")):
                return
        self.reload_databases()
        if self.active_db in self.databases:
            self._reload_database(self.active_db)

    def reload_databases(self):
        """(Re)load the databases the user owns or that are shared with them"""
        if not self.api:
            return
        try:
            with busy_cursor():
                connections = self.api.list_connections()
        except ApiError as error:
            show_styled_message(self, tr("dashboard.sidebar.databases"),
                                tr("dashboard.sidebar.databases_failed", error=error), QMessageBox.Icon.Warning)
            return

        for connection in connections:
            entry = self.databases.get(connection["id"])
            if entry:
                self._update_database_item(entry, connection)
            else:
                self._add_database_item(connection)

        # Connections deleted elsewhere (or shares that were revoked) disappear
        current_ids = {connection["id"] for connection in connections}
        for connection_id in [key for key in self.databases if key not in current_ids]:
            self._remove_database(connection_id)
        self.databases_reloaded.emit()

    def describe_shares(self, shares):
        """Who shared each shared database, and what the user may do there (see shares_by_connection)"""
        self.shares = shares
        for entry in self.databases.values():
            widget = self.db_tree.itemWidget(entry["item"], 0)
            if widget is not None:
                bind(widget.setToolTip, lambda connection=entry["connection"]: self._db_tooltip(connection))

    def _is_owner(self, connection):
        return self.api is not None and connection.get("ownerUserId") == self.api.user_id

    def _add_database_item(self, connection):
        name = connection["dbName"]
        db_item = QTreeWidgetItem([f"☰  {name}"])
        db_item.setData(0, ROLE, "database")
        db_item.setData(0, NAME, name)
        db_item.setData(0, CONNECTION_ID, connection["id"])
        bold = QFont(self.db_tree.font())
        bold.setBold(True)
        db_item.setFont(0, bold)
        bind(partial(db_item.setForeground, 0), lambda: color("on_accent"))
        db_item.setBackground(0, Qt.GlobalColor.transparent)
        self.db_tree.addTopLevelItem(db_item)
        self.db_tree.setItemWidget(db_item, 0, self._create_db_widget(connection))

        add_item = QTreeWidgetItem()
        bind(partial(add_item.setText, 0), lambda: f"     {tr('dashboard.sidebar.add_table')}")
        add_item.setData(0, ROLE, "add_table")
        db_item.addChild(add_item)  # stays the last child: tables are inserted before it
        # Only the owner changes the structure of a database; a guest's login could not run a CREATE TABLE
        add_item.setHidden(not self._is_owner(connection))

        self.databases[connection["id"]] = {
            "item": db_item,
            "connection": connection,
            "schema_loaded": False,
            "links": [],
            "db_links": set(),
            "schema_info": {},  # table -> {"constraints", "details": {column: ...}}, as read (see db.schema)
        }
        return db_item

    def _update_database_item(self, entry, connection):
        entry["connection"] = connection
        entry["item"].setData(0, NAME, connection["dbName"])
        entry["item"].setText(0, f"☰  {connection['dbName']}")
        self.db_tree.setItemWidget(entry["item"], 0, self._create_db_widget(connection))
        if connection["id"] == self.active_db and self.sql_builder:
            self.sql_builder.set_connection(connection)

    def _db_tooltip(self, connection):
        if self._is_owner(connection):
            return (describe_connection(connection) + "\n"
                    + tr("dashboard.sidebar.owner_tip", share=tr("dashboard.sidebar.share")))
        owner, permissions = self.shares.get(connection["id"], (None, []))
        if permissions:
            allowed = describe_permissions(permissions)
            hint = (tr("dashboard.sidebar.shared_by_may", owner=owner, permissions=allowed) if owner
                    else tr("dashboard.sidebar.shared_may", permissions=allowed))
        else:
            hint = tr("dashboard.sidebar.shared_by", owner=owner) if owner else tr("dashboard.sidebar.shared")
        return describe_connection(connection) + "\n" + hint

    def _create_db_widget(self, connection):
        shared = not self._is_owner(connection)
        # Blue when it is yours, sky when it is shared with you; what is on it reads on that colour
        fill = "info" if shared else "accent"
        widget = QFrame()
        bind(widget.setToolTip, lambda: self._db_tooltip(connection))
        style(widget, f"""
            QFrame {{
                background-color: @{fill};
                border-radius: 6px;
                margin: 2px 8px 2px 0px;
            }}
        """)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        icon = QLabel("☰")
        style(icon, f"QLabel {{ color: @on_{fill}; font-size: 12px; background: transparent; }}")
        label = QLabel(connection["dbName"])
        style(label, f"QLabel {{ color: @on_{fill}; font-size: 13px; font-weight: 600; background: transparent; }}")
        label.setObjectName("db_name_label")
        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addStretch()
        if shared:
            badge = QLabel()
            bind(badge.setText, "dashboard.sidebar.shared_badge")
            style(badge, "QLabel { color: @on_info; font-size: 10px; background: transparent; }")
            layout.addWidget(badge)
        else:
            share = QPushButton()
            bind(share.setText, "dashboard.sidebar.share")
            bind(share.setToolTip, "dashboard.sidebar.share_tip")
            share.setCursor(Qt.CursorShape.PointingHandCursor)
            style(share, """
                QPushButton {
                    color: @on_accent;
                    background: transparent;
                    border: 1px solid @on_accent;
                    border-radius: 4px;
                    padding: 0px 6px;
                    margin: 0px;
                    font-size: 10px;
                }
                QPushButton:hover { background: @accent_hover; }
            """)
            share.clicked.connect(lambda: self.share_requested.emit(connection))
            layout.addWidget(share)

            more = QToolButton()
            more.setText("⋮")
            bind(more.setToolTip, "dashboard.sidebar.more_tip")
            more.setCursor(Qt.CursorShape.PointingHandCursor)
            style(more, """
                QToolButton {
                    color: @on_accent;
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                    padding: 0px 4px;
                    font-size: 15px;
                    font-weight: bold;
                }
                QToolButton:hover { background: @accent_hover; }
            """)
            more.clicked.connect(lambda: self._open_database_menu(
                connection["id"], more.mapToGlobal(more.rect().bottomLeft())))
            layout.addWidget(more)

            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(
                lambda pos: self._open_database_menu(connection["id"], widget.mapToGlobal(pos)))
        return widget

    def _database_menu(self):
        """The ⋮ menu of a database you own. Its parent is the sidebar, not the row: Delete removes the row."""
        menu = QMenu(self)
        menu.setStyleSheet(qss(MENU_STYLE))
        for key, text in DATABASE_ACTIONS:
            if key == "delete":
                menu.addSeparator()
            menu.addAction(tr(text, edit_connection=tr("common.action.edit_connection"))).setData(key)
        return menu

    def _open_database_menu(self, connection_id, global_pos):
        menu = self._database_menu()
        # Acted on after the menu has closed: the action may delete the row the menu was opened from
        chosen = menu.exec(global_pos)
        menu.deleteLater()
        if chosen is not None and connection_id in self.databases:
            self.run_database_action(connection_id, chosen.data())

    def run_database_action(self, connection_id, key):
        if key == "edit":
            self.edit_database(connection_id)
        elif key == "share":
            self.share_requested.emit(self.databases[connection_id]["connection"])
        elif key == "delete":
            self.delete_database(connection_id)

    def add_database(self):
        """Register a new database on the server (its password stays here) and add it to the tree"""
        if not self.api:
            return
        created = {}
        dialog = InputDatabaseWindow(
            self,
            on_submit=lambda details: created.update(self.db.create_connection(details)),
            on_test=self.db.test_new
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or not created:
            return

        db_item = self._add_database_item(created)
        self.db_tree.setCurrentItem(db_item)
        self.activate_database(created["id"])
        db_item.setExpanded(True)

    def activate_database(self, connection_id):
        """Show the tables of this database on the diagram and run queries against it"""
        entry = self.databases.get(connection_id)
        if entry is None:
            return
        if connection_id == self.active_db and entry["schema_loaded"]:
            return

        if self.active_db in self.databases:
            self.databases[self.active_db]["links"] = self.diagram.export_links()
        if connection_id != self.active_db:
            self.active_db = connection_id
            self.diagram.can_change_structure = self._is_owner(entry["connection"])
            if self.sql_builder:
                self.sql_builder.clear_query()
                self.sql_builder.set_connection(entry["connection"])

        if not entry["schema_loaded"]:
            self._load_schema(connection_id)
        self._render_active()
        self._refresh_change_script(connection_id)

    def _render_active(self):
        self.diagram.clear_diagram()
        entry = self.databases.get(self.active_db)
        if entry is None:
            return
        known = {}
        for (connection_id, table_name), page in self.page_map.items():
            if connection_id == self.active_db and page.state.columns and not page.state.pending_drop:
                self.diagram.add_table_card(table_name, page.state.columns)
                known[table_name] = {column[0] for column in page.state.columns}
        self.diagram.restore_links(entry["links"])
        if self.sql_builder and entry["schema_loaded"]:
            self.sql_builder.keep_only(known)  # a Run may have dropped a table or a column the query used

    def _load_schema(self, connection_id):
        """Read the tables of a database from the database itself and create a page per table"""
        entry = self.databases[connection_id]
        try:
            with busy_cursor():
                tables = self.db.schema(entry["connection"])
        except (DatabaseError, ApiError) as error:
            if getattr(error, "cancelled", False):
                return  # asked for the password, and none was given
            text = tr("dashboard.sidebar.tables_failed", name=entry["connection"]["dbName"], error=error)
            if getattr(error, "unreachable", False) and self._is_owner(entry["connection"]):
                # Nothing answered: most often a wrong host, port, name or password - offer to fix them
                if confirm(self, tr("dashboard.sidebar.unreachable_title"),
                           f"{text}\n\n{tr('dashboard.sidebar.edit_settings_now')}"):
                    self.edit_database(connection_id)
            else:
                show_styled_message(self, tr("dashboard.sidebar.tables_title"), text, QMessageBox.Icon.Warning)
            return

        entry["schema_loaded"] = True
        db_item = entry["item"]
        for table in tables:
            table_name = table["name"]
            if (connection_id, table_name) in self.page_map:
                continue
            view = "VIEW" in (table.get("type") or "").upper()
            columns = []
            entry["schema_info"][table_name] = {
                "constraints": table.get("constraints") or [],
                "details": {column["name"]: schema_details(column) for column in table.get("columns") or []},
            }
            for column in table.get("columns") or []:
                referenced_table = column.get("referencedTable")
                columns.append(schema_column(column))
                if referenced_table:
                    link = (referenced_table, column.get("referencedColumn"), table_name, column["name"])
                    entry["db_links"].add(link)
                    if link not in entry["links"]:
                        entry["links"].append(link)

            db_item.insertChild(db_item.childCount() - 1, self._create_table_item(table_name, view))
            self.create_table_page(connection_id, table_name, columns=columns, live=True, view=view)
        db_item.setExpanded(True)
        if self._is_owner(entry["connection"]):
            self._check_guest_logins(connection_id)

    def _check_guest_logins(self, connection_id):
        """Once a session, when a database you own opens: the people it is shared with get the logins their
        invitations call for (made, re-granted, or dropped once revoked) - see dbmanager.db.guests."""
        if connection_id in self.guests_checked:
            return
        self.guests_checked.add(connection_id)
        connection = self.databases[connection_id]["connection"]
        try:
            with busy_cursor():
                self.db.sync_guests(connection)
        except (DatabaseError, ApiError) as error:
            show_styled_message(self, tr("dashboard.sidebar.sharing_title"),
                                tr("dashboard.sidebar.guests_sync_failed", name=connection["dbName"], error=error),
                                QMessageBox.Icon.Warning)

    def _reload_database(self, connection_id):
        """Throw away what was read from (or edited for) this database and read it again"""
        entry = self.databases[connection_id]
        current_name = next((name for (key, name), page in self.page_map.items()
                             if key == connection_id and page is self.stacked_center.currentWidget()), None)

        if connection_id == self.active_db:
            self.diagram.clear_diagram()
        for key, page in list(self.page_map.items()):
            # An empty new table was never sent anywhere - keep it so the design is not lost
            if key[0] != connection_id or (not page.state.live and not page.state.columns):
                continue
            self._remove_table_page(key)
            self._remove_table_item(entry["item"], key[1])
        entry["links"] = []
        entry["db_links"] = set()
        entry["schema_info"] = {}
        entry["schema_loaded"] = False

        if connection_id == self.active_db:
            self.activate_database(connection_id)
        page = self.page_map.get((connection_id, current_name))
        if page is not None:
            if page.state.live:
                self._load_rows(connection_id, page)
            self.stacked_center.setCurrentWidget(page)
        else:
            self.stacked_center.setCurrentWidget(self.diagram)

    def discard_changes(self):
        """Throw away every unsaved change to the active database: it is read again as it is."""
        if self.active_db not in self.databases:
            return
        count = len(self._pending_statements(self.active_db))
        if not count:
            return
        name = self.databases[self.active_db]["connection"]["dbName"]
        if not confirm(self, tr("dashboard.sidebar.discard_changes_title"),
                       trn("dashboard.sidebar.discard_all", count, name=name)):
            return
        self._reload_database(self.active_db)

    def _discard_table_changes(self, connection_id, table_name):
        """Throw away the unsaved changes to one table (a table only designed here is removed)."""
        key = (connection_id, table_name)
        page = self.page_map.get(key)
        item = self._find_table_item(connection_id, table_name)
        if page is None:
            return
        state = page.state
        if not state.live:
            if not confirm(self, tr("dashboard.sidebar.discard_table_title"),
                           tr("dashboard.sidebar.discard_new_table", name=table_name)):
                return
            if item is not None:
                item.parent().removeChild(item)
            self._remove_table_page(key)
            self._refresh_change_script(connection_id)
            return
        if not confirm(self, tr("dashboard.sidebar.discard_changes_title"),
                       tr("dashboard.sidebar.discard_table_changes", name=table_name)):
            return

        # Renames were carried into the known foreign keys and the diagram: carry them back
        entry = self.databases[connection_id]
        back = {column[0]: origin for column, origin in zip(state.columns, state.column_origin)
                if origin is not None and origin != column[0]}
        for new_name, old_name in back.items():
            entry["db_links"] = {_rename_in_link(link, table_name, new_name, old_name) for link in entry["db_links"]}
            entry["links"] = [_rename_in_link(link, table_name, new_name, old_name) for link in entry["links"]]

        showing = self.stacked_center.currentWidget() is page
        self.page_map.pop(key)
        self.stacked_center.removeWidget(page)
        page.deleteLater()
        fresh = self.create_table_page(connection_id, table_name, columns=page.schema_columns, live=True,
                                       view=state.view)
        if state.rows_loaded:
            self._load_rows(connection_id, fresh)
        if item is not None and state.pending_drop:
            bind(partial(item.setText, 0), lambda view=state.view: _table_item_text(table_name, view))
            unbind(partial(item.setForeground, 0))
            item.setData(0, Qt.ItemDataRole.ForegroundRole, None)

        if connection_id == self.active_db:
            self.diagram.add_table_card(table_name, fresh.state.columns, renamed=back)
            # links to columns that were deleted here come back with them
            self.diagram.restore_links([link for link in entry["db_links"] if table_name in (link[0], link[2])])
        if showing:
            self.stacked_center.setCurrentWidget(fresh)
        self._refresh_change_script(connection_id)

    def _on_script_executed(self, results):
        """After a successful Run: anything other than a SELECT may have changed the database"""
        if self.active_db in self.databases and any(r.get("statementType") != "SELECT" for r in results):
            self._reload_database(self.active_db)

    def _refresh_change_script(self, connection_id):
        if self.sql_builder and connection_id is not None and connection_id == self.active_db:
            self.sql_builder.set_change_script(self._pending_statements(connection_id))

    def _table_states(self, connection_id):
        return {name: page.state for (key, name), page in self.page_map.items() if key == connection_id}

    def problems(self, connection_id):
        """What the database would refuse in the unsaved changes of a database, in words"""
        if connection_id not in self.databases:
            return []
        return [problem for state in self._table_states(connection_id).values() for problem in state.problems()]

    def _pending_statements(self, connection_id):
        """The SQL that saves every edit made for this database (see build_change_script)"""
        entry = self.databases[connection_id]
        tables = {name: page.state for (key, name), page in self.page_map.items() if key == connection_id}
        links = self.diagram.export_links() if connection_id == self.active_db else entry["links"]
        return build_change_script(tables, links, entry["db_links"], entry["connection"]["dbType"])

    def unsaved_changes(self):
        """How many statements wait for Run Query, over every database opened in this session"""
        return sum(len(self._pending_statements(connection_id))
                   for connection_id, entry in self.databases.items() if entry["schema_loaded"])

    def _remove_database(self, connection_id):
        """Drop a database and all its table pages from the UI"""
        entry = self.databases.pop(connection_id, None)
        if entry is None:
            return
        for key in [key for key in self.page_map if key[0] == connection_id]:
            self._remove_table_page(key)
        index = self.db_tree.indexOfTopLevelItem(entry["item"])
        if index >= 0:
            self.db_tree.takeTopLevelItem(index)
        if self.db:
            self.db.forget(connection_id)  # its password, or the login a share of it gave
        self.guests_checked.discard(connection_id)
        if self.active_db == connection_id:
            self.active_db = None
            self.diagram.clear_diagram()
            if self.sql_builder:
                self.sql_builder.clear_query()
                self.sql_builder.set_connection(None)
                self.sql_builder.set_change_script([])
            self.stacked_center.setCurrentWidget(self.diagram)

    # ---------------- Tables ----------------
    @staticmethod
    def _create_table_item(table_name, view=False):
        table_item = QTreeWidgetItem([_table_item_text(table_name, view)])
        table_item.setData(0, ROLE, "table")
        table_item.setData(0, NAME, table_name)
        if view:
            bind(partial(table_item.setToolTip, 0), "dashboard.sidebar.view_tip")
        return table_item

    def _find_table_item(self, connection_id, table_name):
        db_item = self.databases[connection_id]["item"]
        for i in range(db_item.childCount()):
            child = db_item.child(i)
            if child.data(0, ROLE) == "table" and child.data(0, NAME) == table_name:
                return child
        return None

    @staticmethod
    def _remove_table_item(db_item, table_name):
        for i in range(db_item.childCount()):
            child = db_item.child(i)
            if child.data(0, ROLE) == "table" and child.data(0, NAME) == table_name:
                db_item.removeChild(child)
                return

    def create_table_page(self, connection_id, table_name, columns=None, live=False, view=False):
        entry = self.databases[connection_id]
        info = entry["schema_info"].get(table_name, {}) if live else {}
        page = TableDetailsPage(table_name, self.stacked_center, columns=columns, live=live,
                                db_type=entry["connection"]["dbType"], view=view,
                                structure_locked=not self._is_owner(entry["connection"]),
                                constraints=info.get("constraints"), column_details=info.get("details"))
        page.describe_references = lambda column, key=connection_id, name=table_name: [
            f"{child}.{', '.join(constraint['columns'])}"
            for child, constraint in references_to(self._table_states(key), name, column)]
        page.drop_requested.connect(lambda name, key=connection_id: self._drop_from_page(key, name))
        page.changes_made.connect(lambda key=connection_id: self._refresh_change_script(key))
        page.table_data_ready.connect(
            lambda name, cols, key=connection_id: self._on_table_data_ready(key, name, cols))
        page.field_deleted.connect(
            lambda name, cols, key=connection_id: self._on_field_deleted(key, name, cols))
        page.field_renamed.connect(
            lambda name, old, new, cols, key=connection_id: self._on_field_renamed(key, name, old, new, cols))
        page.discard_requested.connect(lambda name, key=connection_id: self._discard_table_changes(key, name))
        self.stacked_center.addWidget(page)
        self.page_map[(connection_id, table_name)] = page
        return page

    def _on_table_data_ready(self, connection_id, table_name, columns):
        if connection_id == self.active_db:
            self.diagram.add_table_card(table_name, columns)

    def _on_field_deleted(self, connection_id, table_name, columns):
        if connection_id == self.active_db:
            self.diagram.remove_field_from_card(table_name, columns)

    def _on_field_renamed(self, connection_id, table_name, old_name, new_name, columns):
        entry = self.databases[connection_id]
        # The database renames a foreign key together with its column: it must not be added again
        entry["db_links"] = {_rename_in_link(link, table_name, old_name, new_name) for link in entry["db_links"]}
        entry["links"] = [_rename_in_link(link, table_name, old_name, new_name) for link in entry["links"]]
        if connection_id == self.active_db:
            self.diagram.rename_field(table_name, old_name, new_name, columns)

    def _remove_table_page(self, key):
        page = self.page_map.pop(key, None)
        if page is None:
            return
        if self.stacked_center.currentWidget() is page:
            self.stacked_center.setCurrentWidget(self.diagram)
        self.stacked_center.removeWidget(page)
        page.deleteLater()
        if key[0] == self.active_db:
            self.diagram.remove_table_card(key[1])

    def _load_rows(self, connection_id, page):
        """Fill a live table page with the first rows of the real table"""
        connection = self.databases[connection_id]["connection"]
        sql = sqlgen.preview(page.table_name, TABLE_PREVIEW_ROWS, connection["dbType"])
        try:
            with busy_cursor():
                result = self.db.run_query(connection, sql, max_rows=TABLE_PREVIEW_ROWS) or {}
        except (DatabaseError, ApiError) as error:
            if getattr(error, "cancelled", False):
                return
            show_styled_message(self, tr("dashboard.sidebar.rows_title"),
                                tr("dashboard.sidebar.rows_failed", name=page.table_name, error=error),
                                QMessageBox.Icon.Warning)
            return
        page.set_rows(result.get("columns") or [], result.get("rows") or [], truncated=result.get("truncated", False))

    def on_tree_click(self, item):
        role = item.data(0, ROLE)

        if role == "database":
            connection_id = item.data(0, CONNECTION_ID)
            if connection_id != self.active_db or not self.databases[connection_id]["schema_loaded"]:
                self.activate_database(connection_id)
                item.setExpanded(True)
            else:
                item.setExpanded(not item.isExpanded())
            self.stacked_center.setCurrentWidget(self.diagram)
            return

        parent = item.parent()
        if parent is None:
            return
        connection_id = parent.data(0, CONNECTION_ID)
        self.activate_database(connection_id)

        if role == "add_table":
            self._add_table(connection_id, parent)
        elif role == "table":
            table_name = item.data(0, NAME)
            page = self.page_map.get((connection_id, table_name))
            if page is None:
                page = self.create_table_page(connection_id, table_name)
            if page.state.live and not page.state.rows_loaded:
                self._load_rows(connection_id, page)
            self.stacked_center.setCurrentWidget(page)

    def _add_table(self, connection_id, db_item):
        dialog = InputTableNameWindow(self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.get_data():
            return
        table_name = dialog.get_data()

        existing = {db_item.child(i).data(0, NAME).lower() for i in range(db_item.childCount())
                    if db_item.child(i).data(0, ROLE) == "table"}
        if table_name.lower() in existing:
            show_styled_message(self, tr("dashboard.sidebar.duplicate_title"),
                                tr("dashboard.sidebar.duplicate", name=table_name), QMessageBox.Icon.Warning)
            return

        db_item.insertChild(db_item.childCount() - 1, self._create_table_item(table_name))
        # A table designed here exists only in this editor until it is created in the database
        page = self.create_table_page(connection_id, table_name)
        self.stacked_center.setCurrentWidget(page)

    def on_tree_double_click(self, item):
        """Double click on a database: edit its connection"""
        if item.data(0, ROLE) == "database":
            self.edit_database(item.data(0, CONNECTION_ID))

    def edit_database(self, connection_id):
        """Change where a database you own is, or how to sign in to it; the new settings are tested first"""
        entry = self.databases[connection_id]
        item = entry["item"]
        if not self._is_owner(entry["connection"]):
            show_styled_message(self, tr("dashboard.sidebar.edit_database_title"),
                                tr("dashboard.sidebar.edit_not_owner"), QMessageBox.Icon.Warning)
            return

        updated = {}
        dialog = InputDatabaseWindow(
            self,
            title=tr("dashboard.sidebar.edit_database_title"),
            connection=entry["connection"],
            button_text=tr("common.save"),
            on_submit=lambda details: updated.update(self.db.update_connection(connection_id, details)),
            on_test=lambda details: self.db.test_saved(entry["connection"], details)
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or not updated:
            return

        self._update_database_item(entry, updated)
        # The connection may now point somewhere else: forget the tables read from the old target
        for key in [key for key, page in self.page_map.items() if key[0] == connection_id and page.state.live]:
            self._remove_table_page(key)
            self._remove_table_item(item, key[1])
        entry["schema_loaded"] = False
        entry["links"] = []
        entry["db_links"] = set()
        entry["schema_info"] = {}
        if connection_id == self.active_db:
            self.activate_database(connection_id)

    def keyPressEvent(self, event):
        if event.key() not in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):  # a Mac's delete key is Backspace
            super().keyPressEvent(event)
            return
        item = self.db_tree.currentItem()
        if not item:
            return
        role = item.data(0, ROLE)
        if role == "table":
            self._delete_table(item)
        elif role == "database":
            self.delete_database(item.data(0, CONNECTION_ID))

    def _open_from_diagram(self, table_name):
        item = self._find_table_item(self.active_db, table_name)
        if item is not None:
            self.on_tree_click(item)

    def _delete_field_from_diagram(self, table_name, field_name):
        page = self.page_map.get((self.active_db, table_name))
        if page is not None and field_name in page.state.column_names():
            page.delete_field(page.state.column_names().index(field_name))

    def _drop_from_page(self, connection_id, table_name):
        item = self._find_table_item(connection_id, table_name)
        if item is not None:
            self._delete_table(item)

    def _on_tree_menu(self, pos):
        """Right-click on a table in the tree: open it, drop it (or keep it after all)"""
        item = self.db_tree.itemAt(pos)
        if item is None or item.data(0, ROLE) != "table":
            return
        connection_id = item.parent().data(0, CONNECTION_ID)
        page = self.page_map.get((connection_id, item.data(0, NAME)))
        menu = QMenu(self)
        menu.setStyleSheet(qss(MENU_STYLE))
        menu.addAction(tr("dashboard.sidebar.open")).triggered.connect(lambda: self.on_tree_click(item))
        if self._is_owner(self.databases[connection_id]["connection"]):
            view = page is not None and page.state.view
            if page is not None and page.state.pending_drop:
                text = tr("dashboard.sidebar.keep_view" if view else "dashboard.sidebar.keep_table")
            elif page is not None and not page.state.live:
                text = tr("dashboard.sidebar.delete_table")
            else:
                text = tr("dashboard.sidebar.drop_view" if view else "dashboard.sidebar.drop_table")
            menu.addSeparator()
            menu.addAction(text).triggered.connect(lambda: self._delete_table(item))
        menu.exec(self.db_tree.viewport().mapToGlobal(pos))

    def _delete_table(self, item):
        connection_id = item.parent().data(0, CONNECTION_ID)
        table_name = item.data(0, NAME)
        page = self.page_map.get((connection_id, table_name))
        if page is not None and page.state.live:
            self._toggle_drop(connection_id, item, page)
            return
        if not confirm(self, tr("dashboard.sidebar.delete_table_title"),
                       tr("dashboard.sidebar.delete_table_question", name=table_name)):
            return
        item.parent().removeChild(item)
        self._remove_table_page((connection_id, table_name))
        self.stacked_center.setCurrentWidget(self.diagram)
        self._refresh_change_script(connection_id)

    def delete_database(self, connection_id):
        """Remove a database you own from the account (⋮ → Delete, or the Delete key)"""
        connection = self.databases[connection_id]["connection"]
        if not self._is_owner(connection):
            show_styled_message(self, tr("dashboard.sidebar.delete_database_title"),
                                tr("dashboard.sidebar.delete_not_owner"), QMessageBox.Icon.Warning)
            return
        unsaved = len(self._pending_statements(connection_id))
        if not confirm(self, tr("dashboard.sidebar.delete_database_title"),
                       tr("dashboard.sidebar.delete_database_question", name=connection["dbName"])
                       + ("\n" + trn("dashboard.sidebar.unsaved_lost", unsaved) if unsaved else "")):
            return
        if not self._drop_guest_logins(connection):
            return
        try:
            with busy_cursor():
                self.db.delete_connection(connection_id)
        except ApiError as error:
            show_styled_message(self, tr("dashboard.sidebar.delete_database_title"), str(error),
                                QMessageBox.Icon.Warning)
            return
        self._remove_database(connection_id)

    def _drop_guest_logins(self, connection):
        """Before a shared database goes: its guests' logins go from the database. False to stop."""
        try:
            with busy_cursor():
                if not self.api.list_guest_accounts(connection["id"]):
                    return True  # never shared: nothing was made in the database
                self.db.drop_guest_logins(connection)
            return True
        except (DatabaseError, ApiError) as error:
            return confirm(self, tr("dashboard.sidebar.delete_database_title"),
                           tr("dashboard.sidebar.drop_guests_failed", name=connection["dbName"], error=error))

    def _toggle_drop(self, connection_id, item, page):
        """Mark a table that exists in the database to be dropped on the next Run (or unmark it)"""
        if not self._is_owner(self.databases[connection_id]["connection"]):
            show_styled_message(self, tr("dashboard.sidebar.shared_database_title"),
                                tr("dashboard.sidebar.owner_only_drop"))
            return
        state = page.state
        if state.pending_drop:
            if not confirm(self, tr("dashboard.sidebar.keep_view_title" if state.view
                                    else "dashboard.sidebar.keep_table_title"),
                           tr("dashboard.sidebar.keep_question", name=state.name)):
                return
            state.pending_drop = False
            bind(partial(item.setText, 0), lambda name=state.name, view=state.view: _table_item_text(name, view))
            unbind(partial(item.setForeground, 0))
            item.setData(0, Qt.ItemDataRole.ForegroundRole, None)
            if connection_id == self.active_db and state.columns:
                self.diagram.add_table_card(state.name, state.columns)
        else:
            text = tr("dashboard.sidebar.drop_view_question" if state.view else "dashboard.sidebar.drop_table_question",
                      name=state.name, run_query=tr("common.action.run_query"))
            pointing = [f"{child}.{', '.join(constraint['columns'])}"
                        for child, constraint in references_to(self._table_states(connection_id), state.name)
                        if not self._table_states(connection_id)[child].pending_drop]
            if pointing:
                text += "\n\n" + tr("dashboard.sidebar.referenced_by") + "\n  " + "\n  ".join(pointing)
            if not confirm(self, tr("dashboard.sidebar.drop_view_title" if state.view
                                    else "dashboard.sidebar.drop_table_title"), text):
                return
            state.pending_drop = True
            bind(partial(item.setText, 0), lambda name=state.name: _table_item_text(name, dropping=True))
            bind(partial(item.setForeground, 0), lambda: color("danger_text"))
            if connection_id == self.active_db:
                self.diagram.remove_table_card(state.name)
                if self.sql_builder:
                    self.sql_builder.drop_table(state.name)  # the query cannot read it once it is dropped
            self.stacked_center.setCurrentWidget(self.diagram)
        page.show_pending_drop(state.pending_drop)
        self._refresh_change_script(connection_id)
