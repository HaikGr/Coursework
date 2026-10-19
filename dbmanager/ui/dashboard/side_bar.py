from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget
)

from dbmanager.api import ApiError, describe_connection
from dbmanager.config import TABLE_PREVIEW_ROWS
from dbmanager.model.change_script import build_change_script
from dbmanager.sql.identifiers import quote_identifier
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.message_box import confirm, show_styled_message
from dbmanager.ui.dialogs.database_dialog import InputDatabaseWindow
from dbmanager.ui.dialogs.table_name_dialog import InputTableNameWindow
from dbmanager.ui.table_editor.table_details_page import TableDetailsPage

ROLE = Qt.ItemDataRole.UserRole
NAME = Qt.ItemDataRole.UserRole + 1
CONNECTION_ID = Qt.ItemDataRole.UserRole + 2


def _table_item_text(name, view=False, dropping=False):
    if dropping:
        return f"  ⊠  {name}  (drop)"
    return f"  {'⊡' if view else '⊞'}  {name}"


def _rename_in_link(link, table_name, old_name, new_name):
    pk_table, pk_field, fk_table, fk_field = link
    if pk_table == table_name and pk_field == old_name:
        pk_field = new_name
    if fk_table == table_name and fk_field == old_name:
        fk_field = new_name
    return pk_table, pk_field, fk_table, fk_field


class SideBar(QWidget):
    """Databases of the signed-in user (from the server) and their tables.

    The diagram shows the tables of one database at a time - the active one. Each database keeps
    its own table pages and PK-FK links, so switching back and forth loses nothing.

    Edits made in the table pages are collected here into one SQL script per database and shown
    in the SQL panel; Run Query sends it, and the database is then read back.
    """
    logout_requested = pyqtSignal()

    def __init__(self, stack_widget, diagram_page, api=None, sql_builder=None):
        super().__init__()
        self.stacked_center = stack_widget
        self.diagram = diagram_page
        self.api = api
        self.sql_builder = sql_builder
        self.page_map = {}   # (connection_id, table_name) -> TableDetailsPage
        # connection_id -> {"item", "connection", "schema_loaded", "links", "db_links"}
        # links: PK-FK links drawn on the diagram; db_links: the foreign keys the database already has
        self.databases = {}
        self.active_db = None

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        self.setLayout(sidebar_layout)
        self.setFixedWidth(260)
        self.setStyleSheet("background-color: #FFFFFF;")

        # Header
        databases_text = QFrame()
        databases_text.setFixedHeight(44)
        databases_text.setStyleSheet("""
            QFrame {
                background-color: #fbc840;
                border: none;
            }
        """)
        dt_layout = QHBoxLayout(databases_text)
        dt_layout.setContentsMargins(16, 0, 16, 0)
        lbl_db = QLabel("Databases")
        lbl_db.setStyleSheet("color: #744210; font-size: 16px; font-weight: 600; background: transparent;")
        dt_layout.addWidget(lbl_db)
        dt_layout.addStretch()

        refresh_btn = QPushButton("⟳")
        refresh_btn.setToolTip("Reload databases and tables from the server")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton { color: #744210; background: transparent; border: none; font-size: 16px; font-weight: bold; }
            QPushButton:hover { color: #3777f0; }
        """)
        refresh_btn.clicked.connect(self.refresh)
        dt_layout.addWidget(refresh_btn)

        # Tree widget for databases
        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderHidden(True)
        self.db_tree.setIndentation(16)
        self.db_tree.setAnimated(True)
        self.db_tree.setRootIsDecorated(False)
        self.db_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #FFFFFF;
                border: none;
                outline: none;
                font-size: 13px;
            }
            QTreeWidget::item {
                height: 38px;
                padding-left: 0px;
                margin: 0px;
                color: #2D3748;
                border: none;
            }
            QTreeWidget::item:hover {
                background-color: #F0F4F8;
            }
            QTreeWidget::item:selected {
                background-color: #3777f0;
                color: white;
            }
            QTreeWidget::branch {
                background: transparent;
            }
        """)
        self.db_tree.itemClicked.connect(self.on_tree_click)
        self.db_tree.itemDoubleClicked.connect(self.on_tree_double_click)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.db_tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.add_db_button = QPushButton("+ Add Database")
        self.add_db_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_db_button.setStyleSheet("""
            QPushButton {
                background-color: #F0F4F8;
                color: #4A5568;
                font-size: 13px;
                font-weight: 500;
                border-radius: 6px;
                padding: 10px;
                margin: 10px;
                border: 1px dashed #C6C6C6;
            }
            QPushButton:hover {
                background-color: #E2ECFF;
                border: 1px dashed #3777f0;
                color: #3777f0;
            }
        """)
        self.add_db_button.clicked.connect(self.add_database)

        logout_button = QPushButton("LOG OUT")
        logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_button.setStyleSheet("""
            QPushButton {
                background-color: #E34A4A;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px;
                margin: 0px 10px 10px 10px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #D33A3A;
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
        self.diagram.table_area.connections_changed.connect(lambda: self._refresh_change_script(self.active_db))

        self.reload_databases()

    # ---------------- Databases ----------------
    def refresh(self):
        """Reload the database list, and the tables of the selected database"""
        if self.active_db in self.databases and self._pending_statements(self.active_db):
            if not confirm(self, "Reload", "Discard the changes that have not been run yet?"):
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
            show_styled_message(self, "Databases", f"Could not load your databases:\n{error}",
                                QMessageBox.Icon.Warning)
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

    def _is_owner(self, connection):
        return self.api is not None and connection.get("ownerUserId") == self.api.user_id

    def _add_database_item(self, connection):
        name = connection["dbName"]
        db_item = QTreeWidgetItem([f"☰  {name}"])
        db_item.setData(0, ROLE, "database")
        db_item.setData(0, NAME, name)
        db_item.setData(0, CONNECTION_ID, connection["id"])
        db_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
        db_item.setForeground(0, Qt.GlobalColor.white)
        db_item.setBackground(0, Qt.GlobalColor.transparent)
        self.db_tree.addTopLevelItem(db_item)
        self.db_tree.setItemWidget(db_item, 0, self._create_db_widget(connection))

        add_item = QTreeWidgetItem(["     + Add Table"])
        add_item.setData(0, ROLE, "add_table")
        db_item.addChild(add_item)

        self.databases[connection["id"]] = {
            "item": db_item,
            "connection": connection,
            "schema_loaded": False,
            "links": [],
            "db_links": set(),
        }
        return db_item

    def _update_database_item(self, entry, connection):
        entry["connection"] = connection
        entry["item"].setData(0, NAME, connection["dbName"])
        entry["item"].setText(0, f"☰  {connection['dbName']}")
        self.db_tree.setItemWidget(entry["item"], 0, self._create_db_widget(connection))
        if connection["id"] == self.active_db and self.sql_builder:
            self.sql_builder.set_connection(connection)

    def _create_db_widget(self, connection):
        shared = not self._is_owner(connection)
        widget = QFrame()
        widget.setToolTip(describe_connection(connection) + ("\nShared with you" if shared else
                                                             "\nDouble-click to edit, Delete to remove"))
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: {'#0ea5e9' if shared else '#3777f0'};
                border-radius: 6px;
                margin: 2px 8px 2px 0px;
            }}
        """)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        icon = QLabel("☰")
        icon.setStyleSheet("color: white; font-size: 12px; background: transparent;")
        label = QLabel(connection["dbName"])
        label.setStyleSheet("color: white; font-size: 13px; font-weight: 600; background: transparent;")
        label.setObjectName("db_name_label")
        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addStretch()
        if shared:
            badge = QLabel("shared")
            badge.setStyleSheet("color: white; font-size: 10px; background: transparent;")
            layout.addWidget(badge)
        return widget

    def add_database(self):
        """Register a new database on the server and add it to the tree"""
        if not self.api:
            return
        created = {}
        dialog = InputDatabaseWindow(
            self,
            title="New Database",
            button_text="Connect",
            on_submit=lambda details: created.update(self.api.create_connection(details))
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
        for (connection_id, table_name), page in self.page_map.items():
            if connection_id == self.active_db and page.state.columns and not page.state.pending_drop:
                self.diagram.add_table_card(table_name, page.state.columns)
        self.diagram.restore_links(entry["links"])

    def _load_schema(self, connection_id):
        """Read the tables of a database from the server and create a page per table"""
        entry = self.databases[connection_id]
        try:
            with busy_cursor():
                tables = self.api.get_schema(connection_id)
        except ApiError as error:
            show_styled_message(self, "Database Tables",
                                f"Could not read the tables of '{entry['connection']['dbName']}':\n{error}",
                                QMessageBox.Icon.Warning)
            return

        entry["schema_loaded"] = True
        db_item = entry["item"]
        for table in tables:
            table_name = table["name"]
            if (connection_id, table_name) in self.page_map:
                continue
            view = "VIEW" in (table.get("type") or "").upper()
            columns = []
            for column in table.get("columns") or []:
                referenced_table = column.get("referencedTable")
                if column.get("primaryKey"):
                    flag = "PK"
                elif referenced_table:
                    flag = "FK"
                else:
                    flag = "-"
                columns.append([
                    column["name"],
                    column.get("type") or "",
                    "Null" if column.get("nullable") else "Not Null",
                    flag,
                    referenced_table or "-",
                    column.get("referencedColumn") or "-",
                ])
                if referenced_table:
                    link = (referenced_table, column.get("referencedColumn"), table_name, column["name"])
                    entry["db_links"].add(link)
                    if link not in entry["links"]:
                        entry["links"].append(link)

            db_item.insertChild(db_item.childCount() - 1, self._create_table_item(table_name, view))
            self.create_table_page(connection_id, table_name, columns=columns, live=True, view=view)
        db_item.setExpanded(True)

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
        if not confirm(self, "Discard Changes",
                       f"Discard {'the' if count == 1 else 'all ' + str(count)} unsaved "
                       f"change{'s' if count != 1 else ''} to '{name}'?\n"
                       "Tables and rows go back to what the database holds."):
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
            if not confirm(self, "Discard Table", f"Remove the new table '{table_name}'? It was never saved."):
                return
            if item is not None:
                item.parent().removeChild(item)
            self._remove_table_page(key)
            self._refresh_change_script(connection_id)
            return
        if not confirm(self, "Discard Changes", f"Discard the unsaved changes to '{table_name}'?"):
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
            item.setText(0, _table_item_text(table_name, state.view))
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

    def _pending_statements(self, connection_id):
        """The SQL that saves every edit made for this database (see build_change_script)"""
        entry = self.databases[connection_id]
        tables = {name: page.state for (key, name), page in self.page_map.items() if key == connection_id}
        links = self.diagram.export_links() if connection_id == self.active_db else entry["links"]
        return build_change_script(tables, links, entry["db_links"], entry["connection"]["dbType"])

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
            table_item.setToolTip(0, "View - read-only")
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
        db_type = self.databases[connection_id]["connection"]["dbType"]
        page = TableDetailsPage(table_name, self.stacked_center, columns=columns, live=live,
                                db_type=db_type, view=view)
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
        sql = f"SELECT * FROM {quote_identifier(page.table_name, connection['dbType'])}"
        try:
            with busy_cursor():
                result = self.api.run_query(connection_id, sql, max_rows=TABLE_PREVIEW_ROWS) or {}
        except ApiError as error:
            show_styled_message(self, "Table Data", f"Could not read the rows of '{page.table_name}':\n{error}",
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
            show_styled_message(self, "Duplicate Table", f"Table '{table_name}' already exists!",
                                QMessageBox.Icon.Warning)
            return

        db_item.insertChild(db_item.childCount() - 1, self._create_table_item(table_name))
        # A table designed here exists only in this editor until it is created in the database
        page = self.create_table_page(connection_id, table_name)
        self.stacked_center.setCurrentWidget(page)

    def on_tree_double_click(self, item):
        """Double click on a database: edit its connection"""
        if item.data(0, ROLE) != "database":
            return
        connection_id = item.data(0, CONNECTION_ID)
        entry = self.databases[connection_id]
        if not self._is_owner(entry["connection"]):
            show_styled_message(self, "Edit Database",
                                "This database is shared with you - only its owner can change it.",
                                QMessageBox.Icon.Warning)
            return

        updated = {}
        dialog = InputDatabaseWindow(
            self,
            title="Edit Database",
            connection=entry["connection"],
            button_text="Save",
            on_submit=lambda details: updated.update(self.api.update_connection(connection_id, details))
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
        if connection_id == self.active_db:
            self.activate_database(connection_id)

    def keyPressEvent(self, event):
        if event.key() != Qt.Key.Key_Delete:
            super().keyPressEvent(event)
            return
        item = self.db_tree.currentItem()
        if not item:
            return
        role = item.data(0, ROLE)
        if role == "table":
            self._delete_table(item)
        elif role == "database":
            self._delete_database(item)

    def _delete_table(self, item):
        connection_id = item.parent().data(0, CONNECTION_ID)
        table_name = item.data(0, NAME)
        page = self.page_map.get((connection_id, table_name))
        if page is not None and page.state.live:
            self._toggle_drop(connection_id, item, page)
            return
        if not confirm(self, "Delete Table", f"Are you sure you want to delete '{table_name}'?"):
            return
        item.parent().removeChild(item)
        self._remove_table_page((connection_id, table_name))
        self.stacked_center.setCurrentWidget(self.diagram)
        self._refresh_change_script(connection_id)

    def _delete_database(self, item):
        connection_id = item.data(0, CONNECTION_ID)
        connection = self.databases[connection_id]["connection"]
        if not self._is_owner(connection):
            show_styled_message(self, "Delete Database",
                                "This database is shared with you - only its owner can remove it.",
                                QMessageBox.Icon.Warning)
            return
        if not confirm(self, "Delete Database",
                       f"Remove '{connection['dbName']}' from your account?\n"
                       "The database itself is not touched, only the saved connection."):
            return
        try:
            with busy_cursor():
                self.api.delete_connection(connection_id)
        except ApiError as error:
            show_styled_message(self, "Delete Database", str(error), QMessageBox.Icon.Warning)
            return
        self._remove_database(connection_id)

    def _toggle_drop(self, connection_id, item, page):
        """Mark a table that exists in the database to be dropped on the next Run (or unmark it)"""
        state = page.state
        kind = "view" if state.view else "table"
        if state.pending_drop:
            if not confirm(self, f"Keep {kind.title()}", f"Keep '{state.name}' after all?"):
                return
            state.pending_drop = False
            item.setText(0, _table_item_text(state.name, state.view))
            item.setData(0, Qt.ItemDataRole.ForegroundRole, None)
            if connection_id == self.active_db and state.columns:
                self.diagram.add_table_card(state.name, state.columns)
        else:
            details = "" if state.view else " and all its rows"
            if not confirm(self, f"Drop {kind.title()}",
                           f"Drop '{state.name}'{details} from the database?\n"
                           "It is dropped when you click Run Query."):
                return
            state.pending_drop = True
            item.setText(0, _table_item_text(state.name, dropping=True))
            item.setForeground(0, Qt.GlobalColor.red)
            if connection_id == self.active_db:
                self.diagram.remove_table_card(state.name)
            self.stacked_center.setCurrentWidget(self.diagram)
        self._refresh_change_script(connection_id)
