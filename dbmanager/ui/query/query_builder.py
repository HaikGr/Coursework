from collections import deque

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QTextEdit, QVBoxLayout,
    QWidget
)

from dbmanager.api import ApiError
from dbmanager.sql.identifiers import quote_identifier
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.message_box import show_styled_message
from dbmanager.ui.query.field_tag import SelectedFieldTag
from dbmanager.ui.query.highlighter import SQLHighlighter
from dbmanager.ui.query.results_window import QueryResultsWindow


class SQLQueryBuilder(QWidget):
    # Signal emitted when a field is removed (for syncing with FieldRow visuals)
    field_removed = pyqtSignal(str, str)  # table_name, field_name
    fields_cleared = pyqtSignal()  # Emitted when all fields are cleared
    script_executed = pyqtSignal(list)  # one result per statement, after a successful Run
    discard_requested = pyqtSignal()  # the user wants the unsaved changes thrown away

    def __init__(self, api=None):
        super().__init__()
        self.api = api
        self.connection = None  # database the query runs against (set by the sidebar)
        self.change_statements = []  # SQL that saves the edits made in the table editor
        self.builder_query = ""  # SELECT built from the fields picked on the diagram
        self.selected_fields = []
        self.group_by_fields = []
        self.order_by_fields = []  # List of (table, field, direction)
        self.where_conditions = {}
        self.table_connections = []
        self.field_tags = {}
        self.current_aggregate = None

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)
        self.setFixedWidth(300)

        # Header
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:1 #1d4ed8);
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(10)

        icon_container = QFrame()
        icon_container.setFixedSize(32, 32)
        icon_container.setStyleSheet("QFrame { background-color: rgba(255,255,255,0.2); border-radius: 6px; }")
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel("</>")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold; background: transparent;")
        icon_layout.addWidget(icon_label)
        header_layout.addWidget(icon_container)

        text_container = QWidget()
        text_container.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        title = QLabel("SQL Query Builder")
        title.setStyleSheet("color: white; font-size: 13px; font-weight: 700; background: transparent;")
        text_layout.addWidget(title)
        subtitle = QLabel("Visual query construction")
        subtitle.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 9px; background: transparent;")
        text_layout.addWidget(subtitle)
        header_layout.addWidget(text_container)
        header_layout.addStretch()

        main_layout.addWidget(header)

        # Main content area
        content = QWidget()
        content.setStyleSheet("background-color: #0f172a;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        # Database the query will run against
        self.connection_label = QLabel()
        self.connection_label.setWordWrap(True)
        self.connection_label.setStyleSheet("color: #94a3b8; font-size: 10px; background: transparent;")
        content_layout.addWidget(self.connection_label)
        self.set_connection(None)

        # "N unsaved changes" with the way to throw them away next to it
        self.changes_bar = QWidget()
        self.changes_bar.setStyleSheet("background: transparent;")
        changes_layout = QHBoxLayout(self.changes_bar)
        changes_layout.setContentsMargins(0, 0, 0, 0)
        changes_layout.setSpacing(6)
        self.changes_label = QLabel()
        self.changes_label.setWordWrap(True)
        self.changes_label.setStyleSheet("color: #fbbf24; font-size: 10px; font-weight: 600; background: transparent;")
        changes_layout.addWidget(self.changes_label, stretch=1)
        self.discard_btn = QPushButton("Discard")
        self.discard_btn.setFixedHeight(22)
        self.discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discard_btn.setToolTip("Throw away every change that has not been run yet")
        self.discard_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: #fca5a5;
                border: none;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 0 8px;
            }
            QPushButton:hover { background-color: #991b1b; color: #fee2e2; }
        """)
        self.discard_btn.clicked.connect(self.discard_requested.emit)
        changes_layout.addWidget(self.discard_btn, alignment=Qt.AlignmentFlag.AlignTop)
        self.changes_bar.hide()
        content_layout.addWidget(self.changes_bar)

        # SQL Preview - Auto-scales with content (editable, so generated SQL can be adjusted before running)
        self.sql_editor = QTextEdit()
        self.sql_editor.setStyleSheet("""
            QTextEdit {
                background-color: #1e293b;
                color: #e2e8f0;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                border-radius: 8px;
                padding: 10px;
                border: 1px solid #334155;
            }
            QScrollBar:vertical { background: #1e293b; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #475569; border-radius: 3px; min-height: 20px; }
            QScrollBar:horizontal { background: #1e293b; height: 6px; border-radius: 3px; }
            QScrollBar::handle:horizontal { background: #475569; border-radius: 3px; min-width: 20px; }
            QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
        """)
        self.sql_editor.setPlaceholderText("Right-click fields in the diagram to build a query, or type SQL here")
        self.sql_editor.setAcceptRichText(False)
        self.sql_editor.setMinimumHeight(80)
        self.sql_editor.setMaximumHeight(300)
        # documentSizeChanged also fires when the text re-wraps to the editor's final width
        self.sql_editor.document().documentLayout().documentSizeChanged.connect(self._adjust_editor_height)
        self.highlighter = SQLHighlighter(self.sql_editor.document())
        content_layout.addWidget(self.sql_editor)

        # Selected Fields header
        fields_header = QFrame()
        fields_header.setStyleSheet("background: transparent;")
        fields_header_layout = QHBoxLayout(fields_header)
        fields_header_layout.setContentsMargins(0, 4, 0, 4)
        fields_header_layout.setSpacing(6)


        self.fields_count_label = QLabel("Selected Fields (0)")
        self.fields_count_label.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 700; background: transparent;")
        fields_header_layout.addWidget(self.fields_count_label)
        fields_header_layout.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(45, 20)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #94a3b8;
                border: none;
                border-radius: 4px;
                font-size: 9px;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        clear_btn.setToolTip("Clear the selected fields and the query.\n"
                             "Unsaved table changes stay - use Discard to drop them.")
        clear_btn.clicked.connect(self.clear_query)
        fields_header_layout.addWidget(clear_btn)

        content_layout.addWidget(fields_header)

        # Field tags container - scroll area for many fields
        fields_scroll = QScrollArea()
        fields_scroll.setWidgetResizable(True)
        fields_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #1e293b;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                height: 0px;
            }
        """)

        self.fields_container = QWidget()
        self.fields_container.setStyleSheet("background: transparent;")
        self.fields_layout = QVBoxLayout(self.fields_container)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(4)  # Tight spacing between field tags
        self.fields_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        fields_scroll.setWidget(self.fields_container)
        content_layout.addWidget(fields_scroll, stretch=3)

        # Copy button
        copy_btn = QPushButton("Copy Query")
        copy_btn.setFixedHeight(34)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #e2e8f0;
            }
        """)
        copy_btn.clicked.connect(self.copy_query)

        # Run button
        run_btn = QPushButton("▶  Run Query")
        run_btn.setFixedHeight(38)
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        run_btn.clicked.connect(self.run_query)
        content_layout.addWidget(run_btn)
        content_layout.addWidget(copy_btn)

        main_layout.addWidget(content)

    def _adjust_editor_height(self):
        """Auto-scale SQL editor height based on content"""
        doc_height = self.sql_editor.document().size().height()
        new_height = max(80, min(300, int(doc_height + 30)))
        self.sql_editor.setFixedHeight(new_height)

    def set_aggregate(self, agg_name):
        """Set the current aggregate function (called from Toolbar)"""
        self.current_aggregate = agg_name if agg_name else None

    def set_connection(self, connection):
        """Select the database (API connection dict, or None) the query runs against"""
        self.connection = connection
        if connection:
            self.connection_label.setText(f"Database: {connection['dbName']}  ({connection['dbType']})")
        else:
            self.connection_label.setText("No database selected - pick one in the sidebar")

    def set_connections(self, connections):
        self.table_connections = []
        for pk_field, fk_field, relation_type in connections:
            pk_table = pk_field.table_card.table_name
            pk_field_name = pk_field.field_data[0]
            fk_table = fk_field.table_card.table_name
            fk_field_name = fk_field.field_data[0]
            self.table_connections.append((pk_table, pk_field_name, fk_table, fk_field_name))
        # Only regenerate when the builder owns the text - keep SQL the user typed by hand
        if self.selected_fields:
            self._update_query()

    def add_field(self, table_name, field_name, field_type):
        for tbl, fld, ftype in self.selected_fields:
            if tbl == table_name and fld == field_name:
                return False  # Already exists

        self.selected_fields.append((table_name, field_name, field_type))
        self._add_field_tag(table_name, field_name)
        self._update_query()
        return True  # Added successfully

    def remove_field(self, table_name, field_name, emit_signal=True):
        """Remove a field from the query (with its GROUP BY, ORDER BY and WHERE parts)"""
        key = (table_name, field_name)
        if not self.is_field_selected(table_name, field_name):
            return False

        # Remove from selected fields
        self.selected_fields = [
            (t, f, ft) for t, f, ft in self.selected_fields
            if not (t == table_name and f == field_name)
        ]

        # Remove from group by
        if key in self.group_by_fields:
            self.group_by_fields.remove(key)

        # Remove from order by
        self.order_by_fields = [
            (t, f, d) for t, f, d in self.order_by_fields
            if not (t == table_name and f == field_name)
        ]

        # Remove condition
        if key in self.where_conditions:
            del self.where_conditions[key]

        # Remove tag widget
        if key in self.field_tags:
            tag = self.field_tags.pop(key)
            self.fields_layout.removeWidget(tag)
            tag.deleteLater()

        # Update count
        count = len(self.selected_fields)
        self.fields_count_label.setText(f"Selected Fields ({count})")

        self._update_query()

        # Emit signal to sync visual state
        if emit_signal:
            self.field_removed.emit(table_name, field_name)

        return True  # Removed successfully

    def toggle_field(self, table_name, field_name, field_type):
        """Add the field if it is not in the query, remove it otherwise; True when it was added"""
        if self.is_field_selected(table_name, field_name):
            self.remove_field(table_name, field_name)
            return False
        self.add_field(table_name, field_name, field_type)
        return True

    def is_field_selected(self, table_name, field_name):
        return any(t == table_name and f == field_name for t, f, _ in self.selected_fields)

    def add_condition(self, table_name, field_name, condition):
        key = (table_name, field_name)
        self.where_conditions[key] = condition
        self._update_query()

    def _add_field_tag(self, table_name, field_name):
        tag = SelectedFieldTag(table_name, field_name)
        tag.removed.connect(self._remove_field_tag)
        tag.group_by_toggled.connect(self._on_group_by_toggled)
        tag.order_by_toggled.connect(self._on_order_by_toggled)

        # Apply current aggregate if any
        if self.current_aggregate:
            tag.set_aggregate(self.current_aggregate)

        self.fields_layout.addWidget(tag)
        self.field_tags[(table_name, field_name)] = tag

        count = len(self.selected_fields)
        self.fields_count_label.setText(f"Selected Fields ({count})")

    def _remove_field_tag(self, tag):
        self.remove_field(tag.table_name, tag.field_name)

    def _on_group_by_toggled(self, tag):
        key = (tag.table_name, tag.field_name)
        if tag.is_grouped:
            if key not in self.group_by_fields:
                self.group_by_fields.append(key)
        else:
            if key in self.group_by_fields:
                self.group_by_fields.remove(key)
        self._update_query()

    def _on_order_by_toggled(self, tag, direction):
        key = (tag.table_name, tag.field_name)
        # Remove existing order for this field
        self.order_by_fields = [(t, f, d) for t, f, d in self.order_by_fields if not (t == key[0] and f == key[1])]
        # Add new order if direction is set
        if direction:
            self.order_by_fields.append((key[0], key[1], direction))
        self._update_query()

    def _q(self, name):
        """A name quoted for the selected database (bare when no database is selected)"""
        return quote_identifier(name, self.connection["dbType"]) if self.connection else name

    def _col(self, table, field):
        return f"{self._q(table)}.{self._q(field)}"

    def set_change_script(self, statements):
        """Show the SQL that saves the table editor's edits; Run executes it before any SELECT"""
        self.change_statements = list(statements)
        count = len(self.change_statements)
        self.changes_label.setText(f"{count} unsaved change{'s' if count != 1 else ''} - "
                                   "click Run Query to save them to the database")
        self.changes_bar.setVisible(count > 0)
        self._render_editor()

    def _render_editor(self):
        parts = [statement + ";" for statement in self.change_statements]
        if self.builder_query:
            parts.append(self.builder_query)
        self.sql_editor.setPlainText("\n\n".join(parts))

    def _update_query(self):
        if not self.selected_fields:
            self.builder_query = ""
            self._render_editor()
            return

        # Build SELECT clause with aggregates
        select_parts = []
        for t, f, _ in self.selected_fields:
            tag = self.field_tags.get((t, f))
            if tag and tag.aggregate:
                select_parts.append(f"{tag.aggregate}({self._col(t, f)})")
            else:
                select_parts.append(self._col(t, f))
        select_clause = "SELECT " + ",\n       ".join(select_parts)

        # Tables in the order their first field was picked (a set would reorder them between edits)
        tables = list(dict.fromkeys(t for t, _, _ in self.selected_fields))

        # Build FROM/JOIN
        if len(tables) == 1:
            from_clause = f"FROM {self._q(tables[0])}"
        else:
            from_clause = self._build_join_clause(tables)

        # WHERE
        where_clause = ""
        if self.where_conditions:
            conditions = [f"{self._col(t, f)} {cond}" for (t, f), cond in self.where_conditions.items()]
            where_clause = "\nWHERE " + "\n  AND ".join(conditions)

        # GROUP BY
        group_by_clause = ""
        if self.group_by_fields:
            group_parts = [self._col(t, f) for t, f in self.group_by_fields]
            group_by_clause = "\nGROUP BY " + ", ".join(group_parts)

        # ORDER BY
        order_by_clause = ""
        if self.order_by_fields:
            order_parts = [f"{self._col(t, f)} {d}" for t, f, d in self.order_by_fields]
            order_by_clause = "\nORDER BY " + ", ".join(order_parts)

        query = f"{select_clause}\n{from_clause}{where_clause}{group_by_clause}{order_by_clause}"
        self.builder_query = query
        self._render_editor()

    def _build_join_clause(self, tables):
        """
        Build JOIN clause with support for:
        - Direct relationships (A -> B)
        - Indirect relationships via intermediate tables (A -> C -> B)
        - Clear error messages when no relationship exists
        """
        if not tables:
            return ""

        if len(tables) == 1:
            return f"FROM {self._q(tables[0])}"

        # Build adjacency graph from connections
        graph = {}  # table -> [(connected_table, pk_table, pk_field, fk_table, fk_field)]
        for pk_t, pk_f, fk_t, fk_f in self.table_connections:
            if pk_t not in graph:
                graph[pk_t] = []
            if fk_t not in graph:
                graph[fk_t] = []
            # Add both directions for traversal
            graph[pk_t].append((fk_t, pk_t, pk_f, fk_t, fk_f))
            graph[fk_t].append((pk_t, pk_t, pk_f, fk_t, fk_f))

        result_tables = [tables[0]]
        joins = []
        remaining = set(tables[1:])
        unconnected_tables = []

        while remaining:
            found = False

            # Try to find direct connection first
            for r_table in list(remaining):
                for joined_table in result_tables:
                    # Check direct connection
                    connection = self._find_direct_connection(joined_table, r_table)
                    if connection:
                        pk_t, pk_f, fk_t, fk_f = connection
                        if pk_t == joined_table:
                            joins.append(f"JOIN {self._q(fk_t)} ON {self._col(pk_t, pk_f)} = {self._col(fk_t, fk_f)}")
                        else:
                            joins.append(f"JOIN {self._q(pk_t)} ON {self._col(fk_t, fk_f)} = {self._col(pk_t, pk_f)}")
                        result_tables.append(r_table)
                        remaining.remove(r_table)
                        found = True
                        break
                if found:
                    break

            if found:
                continue

            # Try to find indirect connection via intermediate tables
            for r_table in list(remaining):
                path = self._find_path(graph, result_tables, r_table)
                if path:
                    # Add intermediate tables and joins
                    for i in range(len(path) - 1):
                        from_t = path[i]
                        to_t = path[i + 1]

                        # Skip if already joined
                        if to_t in result_tables:
                            continue

                        connection = self._find_direct_connection(from_t, to_t)
                        if connection:
                            pk_t, pk_f, fk_t, fk_f = connection
                            if pk_t == from_t:
                                joins.append(f"JOIN {self._q(fk_t)} ON {self._col(pk_t, pk_f)} = {self._col(fk_t, fk_f)}")
                            else:
                                joins.append(f"JOIN {self._q(pk_t)} ON {self._col(fk_t, fk_f)} = {self._col(pk_t, pk_f)}")
                            result_tables.append(to_t)

                    if r_table in result_tables:
                        remaining.remove(r_table)
                        found = True
                        break

            if not found and remaining:
                # No relationship found - mark as unconnected
                next_table = remaining.pop()
                unconnected_tables.append(next_table)
                result_tables.append(next_table)

        # Build FROM clause
        from_clause = f"FROM {self._q(result_tables[0])}"
        if joins:
            from_clause += "\n" + "\n".join(joins)

        # Add warning comments for unconnected tables
        if unconnected_tables:
            from_clause += "\n-- ⚠️ WARNING: No relationship found for: " + ", ".join(unconnected_tables)
            from_clause += "\n-- Connect these tables in the diagram first!"

        return from_clause

    def _find_direct_connection(self, table1, table2):
        """Find direct connection between two tables"""
        for pk_t, pk_f, fk_t, fk_f in self.table_connections:
            if (pk_t == table1 and fk_t == table2) or (pk_t == table2 and fk_t == table1):
                return (pk_t, pk_f, fk_t, fk_f)
        return None

    def _find_path(self, graph, from_tables, to_table):
        """
        BFS to find shortest path from any of from_tables to to_table
        Returns the path including intermediate tables
        """
        # Start BFS from all currently joined tables
        queue = deque()
        visited = set()
        parent = {}

        for start in from_tables:
            if start in graph:
                queue.append(start)
                visited.add(start)
                parent[start] = None

        while queue:
            current = queue.popleft()

            if current == to_table:
                # Reconstruct path
                path = []
                node = current
                while node is not None:
                    path.append(node)
                    node = parent.get(node)
                return list(reversed(path))

            # Explore neighbors
            if current in graph:
                for neighbor, _, _, _, _ in graph[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        parent[neighbor] = current
                        queue.append(neighbor)

        return None  # No path found

    def clear_query(self):
        while self.fields_layout.count() > 0:
            item = self.fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.selected_fields.clear()
        self.group_by_fields.clear()
        self.order_by_fields.clear()
        self.where_conditions.clear()
        self.field_tags.clear()
        self.builder_query = ""
        self._render_editor()
        self.fields_count_label.setText("Selected Fields (0)")
        self.current_aggregate = None

        # Emit signal to sync all field rows
        self.fields_cleared.emit()

    def copy_query(self):
        query = self.sql_editor.toPlainText()
        if query:
            QApplication.clipboard().setText(query)

    def run_query(self):
        sql = self.sql_editor.toPlainText().strip()
        if not sql:
            show_styled_message(self, "Run Query", "There is no query to run yet.", QMessageBox.Icon.Warning)
            return
        if not self.api or not self.connection:
            show_styled_message(self, "Run Query", "Select a database in the sidebar first.",
                                QMessageBox.Icon.Warning)
            return
        connection = self.connection
        try:
            with busy_cursor():
                result = self.api.run_script(connection["id"], sql)
        except ApiError as error:
            show_styled_message(self, "Query Failed", str(error), QMessageBox.Icon.Critical)
            return
        result = result or {}
        results = result.get("results") or []
        QueryResultsWindow(results, result.get("durationMs", 0), connection["dbName"], self).exec()
        self.script_executed.emit(results)
