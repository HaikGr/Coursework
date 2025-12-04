from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QFrame, QPushButton, QScrollArea, QApplication, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QSyntaxHighlighter
import re


class SQLHighlighter(QSyntaxHighlighter):
    """SQL syntax highlighter for the query editor"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # SQL Keywords - Purple
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#C792EA"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "OUTER",
            "ON", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "DISTINCT",
            "AS", "AND", "OR", "NOT", "IN", "LIKE", "BETWEEN", "IS", "NULL",
            "ASC", "DESC", "SUM", "AVG", "COUNT", "MIN", "MAX"
        ]
        for word in keywords:
            self.highlighting_rules.append((f"\\b{word}\\b", keyword_format))

        # Table names - Blue
        table_format = QTextCharFormat()
        table_format.setForeground(QColor("#82AAFF"))
        self.highlighting_rules.append(("\\b\\w+(?=\\.)", table_format))

        # Field names (after dot) - Green
        field_format = QTextCharFormat()
        field_format.setForeground(QColor("#C3E88D"))
        self.highlighting_rules.append(("\\.\\w+", field_format))

        # Numbers - Orange
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#F78C6C"))
        self.highlighting_rules.append(("\\b[0-9]+\\b", number_format))

        # Strings - Yellow
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#FFCB6B"))
        self.highlighting_rules.append(("'[^']*'", string_format))

        # Operators - Red
        operator_format = QTextCharFormat()
        operator_format.setForeground(QColor("#FF5370"))
        self.highlighting_rules.append(("[<>=!]+", operator_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class SelectedFieldTag(QFrame):
    """A tag widget showing a selected field"""
    removed = pyqtSignal(object)
    group_by_toggled = pyqtSignal(object)
    order_by_toggled = pyqtSignal(object, str)  # tag, direction (ASC/DESC/None)

    def __init__(self, table_name, field_name, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.field_name = field_name
        self.is_grouped = False
        self.order_direction = None  # None, "ASC", "DESC"
        self.aggregate = None  # None, "SUM", "AVG", etc.

        self.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 8px;
                border: 1px solid #334155;
            }
        """)
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(6)

        # Field label
        self.field_text = QLabel(f"{table_name}.<b>{field_name}</b>")
        self.field_text.setStyleSheet("color: #e2e8f0; font-size: 12px; background: transparent;")
        layout.addWidget(self.field_text)
        layout.addStretch()

        # GROUP BY button
        self.group_btn = QPushButton("GROUP BY")
        self.group_btn.setFixedSize(65, 22)
        self.group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_group_style()
        self.group_btn.clicked.connect(self.toggle_group_by)
        layout.addWidget(self.group_btn)

        # ORDER BY button
        self.order_btn = QPushButton("↕")
        self.order_btn.setFixedSize(24, 22)
        self.order_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_order_style()
        self.order_btn.clicked.connect(self.toggle_order_by)
        layout.addWidget(self.order_btn)

        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(22, 22)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: #fca5a5;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #991b1b;
            }
        """)
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(remove_btn)

    def _update_group_style(self):
        if self.is_grouped:
            self.group_btn.setStyleSheet("""
                QPushButton {
                    background-color: #22c55e;
                    color: #052e16;
                    border: none;
                    border-radius: 4px;
                    font-size: 8px;
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #16a34a; }
            """)
        else:
            self.group_btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    color: #94a3b8;
                    border: none;
                    border-radius: 4px;
                    font-size: 8px;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #475569; }
            """)

    def _update_order_style(self):
        if self.order_direction == "ASC":
            self.order_btn.setText("↑")
            self.order_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f59e0b;
                    color: #451a03;
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #d97706; }
            """)
        elif self.order_direction == "DESC":
            self.order_btn.setText("↓")
            self.order_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #dc2626; }
            """)
        else:
            self.order_btn.setText("↕")
            self.order_btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    color: #94a3b8;
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #475569; }
            """)

    def toggle_group_by(self):
        self.is_grouped = not self.is_grouped
        self._update_group_style()
        self.group_by_toggled.emit(self)

    def toggle_order_by(self):
        # Cycle: None -> ASC -> DESC -> None
        if self.order_direction is None:
            self.order_direction = "ASC"
        elif self.order_direction == "ASC":
            self.order_direction = "DESC"
        else:
            self.order_direction = None
        self._update_order_style()
        self.order_by_toggled.emit(self, self.order_direction)

    def set_aggregate(self, agg_type):
        """Set aggregate function for this field"""
        self.aggregate = agg_type
        if agg_type:
            self.field_text.setText(f"<span style='color:#fbbf24;'>{agg_type}</span>({self.table_name}.<b>{self.field_name}</b>)")
        else:
            self.field_text.setText(f"{self.table_name}.<b>{self.field_name}</b>")


class SQLQueryBuilder(QWidget):
    def __init__(self):
        super().__init__()
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

        # SQL Preview - Auto-scales with content
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
        """)
        self.sql_editor.setReadOnly(True)
        self.sql_editor.setMinimumHeight(80)
        self.sql_editor.setMaximumHeight(300)
        self.sql_editor.document().contentsChanged.connect(self._adjust_editor_height)
        self.highlighter = SQLHighlighter(self.sql_editor.document())
        content_layout.addWidget(self.sql_editor)

        # Selected Fields header
        fields_header = QFrame()
        fields_header.setStyleSheet("background: transparent;")
        fields_header_layout = QHBoxLayout(fields_header)
        fields_header_layout.setContentsMargins(0, 4, 0, 4)
        fields_header_layout.setSpacing(6)

        fields_icon = QLabel("⚡")
        fields_icon.setStyleSheet("color: #fbbf24; font-size: 12px; background: transparent;")
        fields_header_layout.addWidget(fields_icon)

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
        clear_btn.clicked.connect(self.clear_query)
        fields_header_layout.addWidget(clear_btn)

        content_layout.addWidget(fields_header)

        # Field tags container (no scroll - items stack)
        self.fields_container = QWidget()
        self.fields_container.setStyleSheet("background: transparent;")
        self.fields_layout = QVBoxLayout(self.fields_container)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(6)

        content_layout.addWidget(self.fields_container, stretch=3)

        # Copy button
        copy_btn = QPushButton("📋 Copy Query")
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

    def set_connections(self, connections):
        self.table_connections = []
        for pk_field, fk_field, relation_type in connections:
            pk_table = pk_field.table_card.table_name
            pk_field_name = pk_field.field_data[0]
            fk_table = fk_field.table_card.table_name
            fk_field_name = fk_field.field_data[0]
            self.table_connections.append((pk_table, pk_field_name, fk_table, fk_field_name))
        self._update_query()

    def add_field(self, table_name, field_name, field_type):
        for tbl, fld, ftype in self.selected_fields:
            if tbl == table_name and fld == field_name:
                return

        self.selected_fields.append((table_name, field_name, field_type))
        self._add_field_tag(table_name, field_name)
        self._update_query()

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
        self.selected_fields = [
            (t, f, ft) for t, f, ft in self.selected_fields
            if not (t == tag.table_name and f == tag.field_name)
        ]

        key = (tag.table_name, tag.field_name)
        if key in self.group_by_fields:
            self.group_by_fields.remove(key)
        self.order_by_fields = [(t, f, d) for t, f, d in self.order_by_fields if not (t == tag.table_name and f == tag.field_name)]
        if key in self.where_conditions:
            del self.where_conditions[key]
        if key in self.field_tags:
            del self.field_tags[key]

        self.fields_layout.removeWidget(tag)
        tag.deleteLater()

        count = len(self.selected_fields)
        self.fields_count_label.setText(f"Selected Fields ({count})")

        self._update_query()

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

    def _update_query(self):
        if not self.selected_fields:
            self.sql_editor.clear()
            return

        # Build SELECT clause with aggregates
        select_parts = []
        for t, f, _ in self.selected_fields:
            tag = self.field_tags.get((t, f))
            if tag and tag.aggregate:
                select_parts.append(f"{tag.aggregate}({t}.{f})")
            else:
                select_parts.append(f"{t}.{f}")
        select_clause = "SELECT " + ",\n       ".join(select_parts)

        # Get tables
        tables = list(set(t for t, _, _ in self.selected_fields))

        # Build FROM/JOIN
        if len(tables) == 1:
            from_clause = f"FROM {tables[0]}"
        else:
            from_clause = self._build_join_clause(tables)

        # WHERE
        where_clause = ""
        if self.where_conditions:
            conditions = [f"{t}.{f} {cond}" for (t, f), cond in self.where_conditions.items()]
            where_clause = "\nWHERE " + "\n  AND ".join(conditions)

        # GROUP BY
        group_by_clause = ""
        if self.group_by_fields:
            group_parts = [f"{t}.{f}" for t, f in self.group_by_fields]
            group_by_clause = "\nGROUP BY " + ", ".join(group_parts)

        # ORDER BY
        order_by_clause = ""
        if self.order_by_fields:
            order_parts = [f"{t}.{f} {d}" for t, f, d in self.order_by_fields]
            order_by_clause = "\nORDER BY " + ", ".join(order_parts)

        query = f"{select_clause}\n{from_clause}{where_clause}{group_by_clause}{order_by_clause}"
        self.sql_editor.setPlainText(query)

    def _build_join_clause(self, tables):
        if not tables:
            return ""

        result_tables = [tables[0]]
        joins = []
        remaining = set(tables[1:])

        while remaining:
            found = False
            for r_table in list(remaining):
                for pk_t, pk_f, fk_t, fk_f in self.table_connections:
                    if pk_t in result_tables and fk_t == r_table:
                        joins.append(f"JOIN {fk_t} ON {pk_t}.{pk_f} = {fk_t}.{fk_f}")
                        result_tables.append(r_table)
                        remaining.remove(r_table)
                        found = True
                        break
                    elif fk_t in result_tables and pk_t == r_table:
                        joins.append(f"JOIN {pk_t} ON {fk_t}.{fk_f} = {pk_t}.{pk_f}")
                        result_tables.append(r_table)
                        remaining.remove(r_table)
                        found = True
                        break
                if found:
                    break

            if not found and remaining:
                next_table = remaining.pop()
                result_tables.append(next_table)
                joins.append(f"-- No relationship for {next_table}")

        from_clause = f"FROM {result_tables[0]}"
        if joins:
            from_clause += "\n" + "\n".join(joins)
        return from_clause

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
        self.sql_editor.clear()
        self.fields_count_label.setText("Selected Fields (0)")
        self.current_aggregate = None

    def copy_query(self):
        query = self.sql_editor.toPlainText()
        if query:
            QApplication.clipboard().setText(query)
