from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QFrame, QPushButton, QScrollArea, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QSyntaxHighlighter
import re


class SQLHighlighter(QSyntaxHighlighter):
    """SQL syntax highlighter for the query editor"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # SQL Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#C792EA"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT",
            "ON", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "DISTINCT",
            "AS", "AND", "OR", "NOT", "IN", "LIKE", "BETWEEN", "IS", "NULL"
        ]
        for word in keywords:
            self.highlighting_rules.append((f"\\b{word}\\b", keyword_format))

        # Table names
        table_format = QTextCharFormat()
        table_format.setForeground(QColor("#82AAFF"))
        self.highlighting_rules.append(("Table_\\w+", table_format))

        # Field names (after dot)
        field_format = QTextCharFormat()
        field_format.setForeground(QColor("#C3E88D"))
        self.highlighting_rules.append(("\\.\\w+", field_format))

        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#F78C6C"))
        self.highlighting_rules.append(("\\b[0-9]+\\b", number_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                self.setFormat(match.start(), match.end() - match.start(), format)


class SelectedFieldTag(QFrame):
    """A tag widget showing a selected field with GROUP BY button"""
    removed = pyqtSignal(object)
    group_by_toggled = pyqtSignal(object)

    def __init__(self, table_name, field_name, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.field_name = field_name
        self.is_grouped = False

        self.setStyleSheet("""
            QFrame {
                background-color: #2D3748;
                border-radius: 6px;
                padding: 2px;
            }
        """)
        self.setFixedHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 6, 4)
        layout.setSpacing(8)

        # Field info container
        field_container = QWidget()
        field_container.setStyleSheet("background: transparent;")
        field_layout = QVBoxLayout(field_container)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(0)

        # Table label (small, gray)
        table_lbl = QLabel(f"Table {table_name}")
        table_lbl.setStyleSheet("color: #718096; font-size: 9px; background: transparent;")
        field_layout.addWidget(table_lbl)

        # Field label (larger, white)
        field_lbl = QLabel(field_name)
        field_lbl.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: 600; background: transparent;")
        field_layout.addWidget(field_lbl)

        layout.addWidget(field_container)
        layout.addStretch()

        # GROUP BY button
        self.group_btn = QPushButton("GROUP BY")
        self.group_btn.setFixedHeight(22)
        self.group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.group_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A5568;
                color: #A0AEC0;
                border: none;
                border-radius: 4px;
                font-size: 9px;
                font-weight: 600;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #5A6778;
            }
        """)
        self.group_btn.clicked.connect(self.toggle_group_by)
        layout.addWidget(self.group_btn)

        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #B91C1C;
            }
        """)
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(remove_btn)

    def toggle_group_by(self):
        """Toggle GROUP BY styling"""
        self.is_grouped = not self.is_grouped
        if self.is_grouped:
            self.group_btn.setStyleSheet("""
                QPushButton {
                    background-color: #7C3AED;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 9px;
                    font-weight: 600;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #6D28D9;
                }
            """)
        else:
            self.group_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4A5568;
                    color: #A0AEC0;
                    border: none;
                    border-radius: 4px;
                    font-size: 9px;
                    font-weight: 600;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #5A6778;
                }
            """)
        self.group_by_toggled.emit(self)


class SQLQueryBuilder(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_fields = []  # List of (table_name, field_name, field_type)
        self.group_by_fields = []  # List of (table_name, field_name)
        self.field_tags = {}  # Map (table, field) -> tag widget

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)
        self.setFixedWidth(280)

        # Header with icon
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet("background-color: #3B82F6; border-top-left-radius: 12px; border-top-right-radius: 12px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)

        # Icon
        icon_label = QLabel("⚡")
        icon_label.setStyleSheet("color: white; font-size: 24px; background: transparent;")
        header_layout.addWidget(icon_label)

        # Text container
        text_container = QWidget()
        text_container.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        title = QLabel("SQL Query Builder")
        title.setStyleSheet("color: white; font-size: 15px; font-weight: 700; background: transparent;")
        text_layout.addWidget(title)

        subtitle = QLabel("Visual query construction")
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.75); font-size: 10px; background: transparent;")
        text_layout.addWidget(subtitle)

        header_layout.addWidget(text_container)
        header_layout.addStretch()

        main_layout.addWidget(header)

        # Main content area
        content = QWidget()
        content.setStyleSheet("background-color: #1A202C;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)

        # SQL Preview (at top)
        self.sql_editor = QTextEdit()
        self.sql_editor.setStyleSheet("""
            QTextEdit {
                background-color: #0F1419;
                color: #E2E8F0;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 11px;
                border-radius: 6px;
                padding: 10px;
                border: 1px solid #2D3748;
            }
        """)
        self.sql_editor.setReadOnly(True)
        self.sql_editor.setFixedHeight(100)
        self.highlighter = SQLHighlighter(self.sql_editor.document())
        content_layout.addWidget(self.sql_editor)

        # Selected Fields header
        fields_header_layout = QHBoxLayout()
        fields_icon = QLabel("⚡")
        fields_icon.setStyleSheet("color: #FFA500; font-size: 14px; background: transparent;")
        fields_header_layout.addWidget(fields_icon)

        self.fields_count_label = QLabel("Selected Fields (0)")
        self.fields_count_label.setStyleSheet("color: #FFA500; font-size: 12px; font-weight: 700; background: transparent;")
        fields_header_layout.addWidget(self.fields_count_label)
        fields_header_layout.addStretch()

        content_layout.addLayout(fields_header_layout)

        # Scrollable field tags area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #4A5568;
                border-radius: 3px;
            }
        """)

        self.fields_container = QWidget()
        self.fields_container.setStyleSheet("background: transparent;")
        self.fields_layout = QVBoxLayout(self.fields_container)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(8)
        self.fields_layout.addStretch()

        scroll_area.setWidget(self.fields_container)
        content_layout.addWidget(scroll_area, stretch=1)

        main_layout.addWidget(content)

    def add_field(self, table_name, field_name, field_type):
        """Add a field to the query builder"""
        print(f"SQLBuilder.add_field called: {table_name}.{field_name}")  # Debug
        
        # Check if already exists
        for tbl, fld, ftype in self.selected_fields:
            if tbl == table_name and fld == field_name:
                print(f"  -> Field already exists, skipping")  # Debug
                return

        self.selected_fields.append((table_name, field_name, field_type))
        print(f"  -> Field added. Total fields: {len(self.selected_fields)}")  # Debug
        self._add_field_tag(table_name, field_name)
        self._update_query()

    def _add_field_tag(self, table_name, field_name):
        """Add a visual tag for the selected field"""
        # Remove stretch
        if self.fields_layout.count() > 0:
            item = self.fields_layout.takeAt(self.fields_layout.count() - 1)
            if item and item.spacerItem():
                del item

        tag = SelectedFieldTag(table_name, field_name)
        tag.removed.connect(self._remove_field_tag)
        tag.group_by_toggled.connect(self._on_group_by_toggled)
        self.fields_layout.addWidget(tag)
        self.fields_layout.addStretch()

        # Store reference
        self.field_tags[(table_name, field_name)] = tag

        # Update count
        count = len(self.selected_fields)
        self.fields_count_label.setText(f"Selected Fields ({count})")

    def _remove_field_tag(self, tag):
        """Remove a field tag and update query"""
        # Remove from selected fields
        self.selected_fields = [
            (t, f, ft) for t, f, ft in self.selected_fields
            if not (t == tag.table_name and f == tag.field_name)
        ]

        # Remove from group by if present
        key = (tag.table_name, tag.field_name)
        if key in self.group_by_fields:
            self.group_by_fields.remove(key)

        # Remove from field tags dict
        if key in self.field_tags:
            del self.field_tags[key]

        # Remove widget
        self.fields_layout.removeWidget(tag)
        tag.deleteLater()

        # Update count
        count = len(self.selected_fields)
        self.fields_count_label.setText(f"Selected Fields ({count})")

        self._update_query()

    def _on_group_by_toggled(self, tag):
        """Handle GROUP BY toggle"""
        key = (tag.table_name, tag.field_name)
        if tag.is_grouped:
            if key not in self.group_by_fields:
                self.group_by_fields.append(key)
        else:
            if key in self.group_by_fields:
                self.group_by_fields.remove(key)
        self._update_query()

    def _update_query(self):
        """Generate and display the SQL query"""
        if not self.selected_fields:
            self.sql_editor.clear()
            return

        # Build SELECT clause
        select_parts = []
        for table_name, field_name, field_type in self.selected_fields:
            select_parts.append(f"Table_{table_name}.{field_name}")

        select_clause = "SELECT " + ", ".join(select_parts)

        # Build FROM clause
        tables = list(set(t for t, _, _ in self.selected_fields))
        from_clause = "FROM " + ", ".join([f"Table_{t}" for t in tables])

        # Build GROUP BY clause
        group_by_clause = ""
        if self.group_by_fields:
            group_by_parts = [f"Table_{t}.{f}" for t, f in self.group_by_fields]
            group_by_clause = "\nGROUP BY " + ", ".join(group_by_parts)

        # Combine query
        query = f"{select_clause}\n{from_clause}{group_by_clause}"

        self.sql_editor.setPlainText(query)

    def clear_query(self):
        """Clear all selected fields and query"""
        while self.fields_layout.count() > 0:
            item = self.fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.selected_fields.clear()
        self.group_by_fields.clear()
        self.field_tags.clear()
        self.sql_editor.clear()
        self.fields_count_label.setText("Selected Fields (0)")
        self.fields_layout.addStretch()

    def copy_query(self):
        """Copy the generated query to clipboard"""
        query = self.sql_editor.toPlainText()
        if query:
            QApplication.clipboard().setText(query)