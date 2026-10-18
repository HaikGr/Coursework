from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton,
    QFrame, QTreeWidget, QTreeWidgetItem, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from items.TableDetailsPage import TableDetailsPage, show_styled_question, show_styled_message
from items.InputTableNameWindow import InputTableNameWindow
from items.InputDatabaseWindow import InputDatabaseWindow
from api_client import ApiError, busy_cursor, quote_identifier, describe_connection
import sql_generator as sqlgen

# Rows shown in a table's "Data Records" panel
TABLE_PREVIEW_ROWS = 200

ROLE = Qt.ItemDataRole.UserRole
NAME = Qt.ItemDataRole.UserRole + 1
CONNECTION_ID = Qt.ItemDataRole.UserRole + 2


class SideBar(QWidget):
    """Databases of the signed-in user (from the server) and their tables.

    The diagram shows the tables of one database at a time - the active one. Each database keeps
    its own table pages and PK-FK links, so switching back and forth loses nothing.

    Edits made in the table pages are collected here into one SQL script per database and shown
    in the SQL panel; Run Query sends it, and the database is then read back.
    """

    def __init__(self, stack_widget, api=None, sql_builder=None):
        super().__init__()
        self.stacked_center = stack_widget
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

        # Add Database button
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

        # Logout button
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
        logout_button.clicked.connect(self.logout)

        sidebar_layout.addWidget(databases_text)
        sidebar_layout.addWidget(self.db_tree, 1)
        sidebar_layout.addWidget(self.add_db_button)
        sidebar_layout.addWidget(logout_button)

        if self.sql_builder:
            self.sql_builder.script_executed.connect(self._on_script_executed)
        self.diagram_page().table_area.connections_changed.connect(
            lambda: self._refresh_change_script(self.active_db))

        self.reload_databases()

    # ---------------- Databases ----------------
    def diagram_page(self):
        return self.stacked_center.widget(0)

    def refresh(self):
        """Reload the database list, and the tables of the selected database"""
        if self.active_db in self.databases and self._pending_statements(self.active_db):
            confirm = show_styled_question(self, "Reload", "Discard the changes that have not been run yet?")
            if confirm != QMessageBox.StandardButton.Yes:
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

        # Create database item
        db_item = QTreeWidgetItem([f"☰  {name}"])
        db_item.setData(0, ROLE, "database")
        db_item.setData(0, NAME, name)
        db_item.setData(0, CONNECTION_ID, connection["id"])
        db_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
        db_item.setForeground(0, Qt.GlobalColor.white)
        db_item.setBackground(0, Qt.GlobalColor.transparent)

        self.db_tree.addTopLevelItem(db_item)

        # Style the database item with blue background
        self.db_tree.setItemWidget(db_item, 0, self._create_db_widget(connection))

        # Add "Add Table" child
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
        """Create a styled widget for database item"""
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

        diagram = self.diagram_page()
        if self.active_db in self.databases:
            self.databases[self.active_db]["links"] = diagram.export_links()
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
        diagram = self.diagram_page()
        diagram.clear_diagram()
        entry = self.databases.get(self.active_db)
        if entry is None:
            return
        for (connection_id, table_name), page in self.page_map.items():
            if connection_id == self.active_db and page.columns and not page.pending_drop:
                diagram.add_table_card(table_name, page.columns)
        diagram.restore_links(entry["links"])

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

            db_item.insertChild(db_item.childCount() - 1, self._create_table_item(table_name))
            self.create_table_page(connection_id, table_name, columns=columns, live=True)
        db_item.setExpanded(True)

    def _reload_database(self, connection_id):
        """Throw away what was read from (or edited for) this database and read it again"""
        entry = self.databases[connection_id]
        current_name = next((name for (key, name), page in self.page_map.items()
                             if key == connection_id and page is self.stacked_center.currentWidget()), None)

        if connection_id == self.active_db:
            self.diagram_page().clear_diagram()
        for key, page in list(self.page_map.items()):
            # An empty new table was never sent anywhere - keep it so the design is not lost
            if key[0] != connection_id or (not page.live and not page.columns):
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
            if page.live:
                self._load_rows(connection_id, page)
            self.stacked_center.setCurrentWidget(page)
        else:
            self.stacked_center.setCurrentIndex(0)

    def _on_script_executed(self, results):
        """After a successful Run: anything other than a SELECT may have changed the database"""
        if self.active_db in self.databases and any(r.get("statementType") != "SELECT" for r in results):
            self._reload_database(self.active_db)

    def _refresh_change_script(self, connection_id):
        if self.sql_builder and connection_id is not None and connection_id == self.active_db:
            self.sql_builder.set_change_script(self._pending_statements(connection_id))

    def _pending_statements(self, connection_id):
        """The SQL that saves every edit made for this database, in an order the database accepts:
        dropped tables (children first), column changes, new tables (referenced ones first),
        new foreign keys, then row changes (parents before children)."""
        entry = self.databases[connection_id]
        db_type = entry["connection"]["dbType"]
        pages = {name: page for (key, name), page in self.page_map.items() if key == connection_id}
        links = self.diagram_page().export_links() if connection_id == self.active_db else entry["links"]
        links = [link for link in links if link[0] in pages and link[2] in pages]

        order = self._parents_first(list(pages), links)
        schema, foreign_keys, data = [], [], []
        for name in reversed(order):
            if pages[name].live and pages[name].pending_drop:
                schema.extend(pages[name].pending_schema_statements([]))
        for name in order:
            page = pages[name]
            if page.live and not page.pending_drop:
                schema.extend(page.pending_schema_statements([]))
        for name in order:
            page = pages[name]
            if not page.live:
                references = [(fk_field, pk_table, pk_field)
                              for pk_table, pk_field, fk_table, fk_field in links
                              if fk_table == name and not pages[pk_table].pending_drop]
                schema.extend(page.pending_schema_statements(references))
        for pk_table, pk_field, fk_table, fk_field in links:
            child, parent = pages[fk_table], pages[pk_table]
            if (child.live and not child.pending_drop and not parent.pending_drop
                    and (pk_table, pk_field, fk_table, fk_field) not in entry["db_links"]):
                foreign_keys.append(sqlgen.add_foreign_key(fk_table, fk_field, pk_table, pk_field, db_type))
        for name in order:
            data.extend(pages[name].pending_data_statements())
        return schema + foreign_keys + data

    @staticmethod
    def _parents_first(names, links):
        """Order tables so a referenced table comes before the tables pointing at it (cycles keep their order)"""
        parents = {name: {pk for pk, _, fk, _ in links if fk == name and pk != name} for name in names}
        ordered, visiting = [], set()

        def visit(name):
            if name in ordered or name in visiting:
                return
            visiting.add(name)
            for parent in parents[name]:
                visit(parent)
            visiting.discard(name)
            ordered.append(name)

        for name in names:
            visit(name)
        return ordered

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
            self.diagram_page().clear_diagram()
            if self.sql_builder:
                self.sql_builder.clear_query()
                self.sql_builder.set_connection(None)
            self.stacked_center.setCurrentIndex(0)

    # ---------------- Tables ----------------
    def _create_table_item(self, table_name):
        """Create a styled table item"""
        table_item = QTreeWidgetItem([f"  ⊞  {table_name}"])
        table_item.setData(0, ROLE, "table")
        table_item.setData(0, NAME, table_name)
        return table_item

    def _remove_table_item(self, db_item, table_name):
        for i in range(db_item.childCount()):
            child = db_item.child(i)
            if child.data(0, ROLE) == "table" and child.data(0, NAME) == table_name:
                db_item.removeChild(child)
                return

    def create_table_page(self, connection_id, table_name, columns=None, live=False):
        db_type = self.databases[connection_id]["connection"]["dbType"]
        page = TableDetailsPage(table_name, self.stacked_center, columns=columns, live=live, db_type=db_type)
        page.changes_made.connect(lambda key=connection_id: self._refresh_change_script(key))
        page.table_data_ready.connect(
            lambda name, cols, key=connection_id: self._on_table_data_ready(key, name, cols))
        page.field_deleted.connect(
            lambda name, cols, key=connection_id: self._on_field_deleted(key, name, cols))
        self.stacked_center.addWidget(page)
        self.page_map[(connection_id, table_name)] = page
        return page

    def _on_table_data_ready(self, connection_id, table_name, columns):
        if connection_id == self.active_db:
            self.diagram_page().add_table_card(table_name, columns)

    def _on_field_deleted(self, connection_id, table_name, columns):
        if connection_id == self.active_db:
            self.diagram_page().remove_field_from_card(table_name, columns)

    def _remove_table_page(self, key):
        page = self.page_map.pop(key, None)
        if page is None:
            return
        self.stacked_center.removeWidget(page)
        page.deleteLater()
        if key[0] == self.active_db:
            self.diagram_page().remove_table_card(key[1])

    def _load_rows(self, connection_id, page):
        """Fill a live table page with the first rows of the real table"""
        connection = self.databases[connection_id]["connection"]
        sql = f"SELECT * FROM {quote_identifier(page.table_name, connection['dbType'])}"
        try:
            with busy_cursor():
                result = self.api.run_query(connection_id, sql, max_rows=TABLE_PREVIEW_ROWS)
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
            self.stacked_center.setCurrentIndex(0)
            return

        parent = item.parent()
        if parent is None:
            return
        connection_id = parent.data(0, CONNECTION_ID)
        self.activate_database(connection_id)

        if role == "add_table":
            input_field = InputTableNameWindow()
            result = input_field.exec()

            if result != QDialog.DialogCode.Accepted:
                return

            table_name_received = input_field.get_data()
            if not table_name_received:
                return

            existing_names = set()
            for i in range(parent.childCount()):
                child = parent.child(i)
                child_role = child.data(0, ROLE)
                if child_role == "table":
                    existing_names.add(child.data(0, NAME))

            if table_name_received in existing_names:
                show_styled_message(self, "Duplicate Table", f"Table '{table_name_received}' already exists!", QMessageBox.Icon.Warning)
                return

            new_table_item = self._create_table_item(table_name_received)
            parent.insertChild(parent.childCount() - 1, new_table_item)

            # A table designed here exists only in this editor until it is created in the database
            page = self.create_table_page(connection_id, table_name_received)
            self.stacked_center.setCurrentWidget(page)

        elif role == "table":
            table_name = item.data(0, NAME)
            page = self.page_map.get((connection_id, table_name))
            if page is None:
                page = self.create_table_page(connection_id, table_name)
            if page.live and not page.rows_loaded:
                self._load_rows(connection_id, page)
            self.stacked_center.setCurrentWidget(page)

    def on_tree_double_click(self, item):
        """Handle double click - edit the database connection"""
        role = item.data(0, ROLE)

        if role == "database":
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
            for key in [key for key, page in self.page_map.items() if key[0] == connection_id and page.live]:
                self._remove_table_page(key)
                self._remove_table_item(item, key[1])
            entry["schema_loaded"] = False
            entry["links"] = []
            entry["db_links"] = set()
            if connection_id == self.active_db:
                self.activate_database(connection_id)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            item = self.db_tree.currentItem()
            if not item:
                return

            role = item.data(0, ROLE)

            if role == "table":
                connection_id = item.parent().data(0, CONNECTION_ID)
                table_name = item.data(0, NAME)
                page = self.page_map.get((connection_id, table_name))
                if page is not None and page.live:
                    self._toggle_drop(connection_id, item, page)
                    return
                confirm = show_styled_question(self, "Delete Table", f"Are you sure you want to delete '{table_name}'?")

                if confirm == QMessageBox.StandardButton.Yes:
                    item.parent().removeChild(item)
                    self._remove_table_page((connection_id, table_name))
                    self.stacked_center.setCurrentIndex(0)
                    self._refresh_change_script(connection_id)

            elif role == "database":
                connection_id = item.data(0, CONNECTION_ID)
                connection = self.databases[connection_id]["connection"]
                if not self._is_owner(connection):
                    show_styled_message(self, "Delete Database",
                                        "This database is shared with you - only its owner can remove it.",
                                        QMessageBox.Icon.Warning)
                    return
                confirm = show_styled_question(
                    self, "Delete Database",
                    f"Remove '{connection['dbName']}' from your account?\n"
                    "The database itself is not touched, only the saved connection.")

                if confirm == QMessageBox.StandardButton.Yes:
                    try:
                        with busy_cursor():
                            self.api.delete_connection(connection_id)
                    except ApiError as error:
                        show_styled_message(self, "Delete Database", str(error), QMessageBox.Icon.Warning)
                        return
                    self._remove_database(connection_id)

    def _toggle_drop(self, connection_id, item, page):
        """Mark a table that exists in the database to be dropped on the next Run (or unmark it)"""
        if page.pending_drop:
            confirm = show_styled_question(self, "Keep Table", f"Keep '{page.table_name}' after all?")
            if confirm != QMessageBox.StandardButton.Yes:
                return
            page.pending_drop = False
            item.setText(0, f"  ⊞  {page.table_name}")
            item.setData(0, Qt.ItemDataRole.ForegroundRole, None)
            if connection_id == self.active_db and page.columns:
                self.diagram_page().add_table_card(page.table_name, page.columns)
        else:
            confirm = show_styled_question(
                self, "Drop Table",
                f"Drop '{page.table_name}' and all its rows from the database?\n"
                "It is dropped when you click Run Query.")
            if confirm != QMessageBox.StandardButton.Yes:
                return
            page.pending_drop = True
            item.setText(0, f"  ⊠  {page.table_name}  (drop)")
            item.setForeground(0, Qt.GlobalColor.red)
            if connection_id == self.active_db:
                self.diagram_page().remove_table_card(page.table_name)
            self.stacked_center.setCurrentIndex(0)
        self._refresh_change_script(connection_id)

    def logout(self):
        """Trigger logout by finding the main window and calling its log_out method"""
        main_window = self.window()
        if hasattr(main_window, 'log_out'):
            main_window.log_out()
