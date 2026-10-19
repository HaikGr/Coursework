"""
TableDetailsPage - the schema and the rows of one table, side by side.

What changed is tracked by a TableState (dbmanager.model); this page only shows it and turns
clicks and typing into calls on it.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QHeaderView, QLabel, QMenu, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from dbmanager.model.table_state import NULL_TEXT, TableState, cell_text, is_primary_key
from dbmanager.sql import generator as sqlgen
from dbmanager.ui.common.message_box import confirm, show_styled_message
from dbmanager.ui.dialogs.field_dialog import InputFieldsWindow
from dbmanager.ui.dialogs.rename_dialog import ask_new_name

ROW_HEIGHT = 42

# The cell editor is a QLineEdit inside the table. It must get its colours here: otherwise it takes
# the dashboard's light background together with the table's light text and what you type is invisible.
DATA_TABLE_STYLE = """
    QTableWidget { background-color: #2D3748; alternate-background-color: #323D4D; border: none; color: #E2E8F0; font-size: 12px; }
    QTableWidget::item { padding: 0px 12px; border-bottom: 1px solid #3D4852; }
    QTableWidget::item:selected { background-color: #3777f0; color: #FFFFFF; }
    QTableWidget QLineEdit {
        background-color: #1A202C;
        color: #F7FAFC;
        border: 2px solid #3777f0;
        border-radius: 4px;
        padding: 0px 6px;
        font-size: 12px;
        selection-background-color: #3777f0;
        selection-color: #FFFFFF;
    }
    QHeaderView::section { background-color: #252D3A; color: #718096; padding: 10px 12px; border: none; font-weight: 600; font-size: 11px; }
    QScrollBar:vertical { background: #2D3748; width: 6px; }
    QScrollBar::handle:vertical { background: #4A5568; border-radius: 3px; }
    QScrollBar:horizontal { background: #2D3748; height: 6px; }
    QScrollBar::handle:horizontal { background: #4A5568; border-radius: 3px; }
"""

BOTTOM_BUTTON_STYLE = """
    QPushButton { background-color: #252D3A; color: #A0AEC0; border: none; border-bottom-left-radius: 10px; border-bottom-right-radius: 10px; font-size: 12px; }
    QPushButton:hover { background-color: #2D3748; color: #E2E8F0; }
    QPushButton:disabled { color: #4A5568; }
"""


class TableDetailsPage(QWidget):
    table_data_ready = pyqtSignal(str, list)    # columns added: refresh the diagram card
    field_deleted = pyqtSignal(str, list)       # table name, remaining columns
    field_renamed = pyqtSignal(str, str, str, list)  # table name, old name, new name, columns
    changes_made = pyqtSignal()                 # something here now differs from the database
    discard_requested = pyqtSignal(str)         # table name: throw this table's unsaved changes away

    def __init__(self, table_name, stacked, columns=None, live=False, db_type="POSTGRESQL", view=False):
        super().__init__()
        self.state = TableState(table_name, db_type, live=live, view=view)
        # The columns as the database has them, to come back to when the changes are discarded
        self.schema_columns = [list(column) for column in columns or []]
        self.stacked = stacked
        self.schema_rows = []

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background-color: #f5f6f7;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #f5f6f7;")
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        content_layout.addWidget(self._build_schema_panel(), stretch=2)
        content_layout.addWidget(self._build_data_panel(), stretch=3)
        main_layout.addWidget(content_widget)

        for column in columns or []:
            self._append_column(column, origin=column[0])

        if not self.state.editable:
            self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            for button in (self.add_field_btn, self.add_row_btn):
                button.setEnabled(False)
                button.setToolTip("Views are read-only here")

    @property
    def table_name(self):
        return self.state.name

    # ---------------- Schema panel ----------------
    @staticmethod
    def _create_panel_shadow(widget):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 2)
        widget.setGraphicsEffect(shadow)

    def _build_schema_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background-color: #2D3748; border-radius: 10px; }")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._create_panel_shadow(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("QFrame { background-color: #2D3748; border-top-left-radius: 10px; border-top-right-radius: 10px; }")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)

        back_btn = QPushButton("← Back")
        back_btn.setFixedHeight(30)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.go_back)
        back_btn.setStyleSheet("""
            QPushButton { background-color: #4A5568; color: #E2E8F0; border: none; border-radius: 5px; font-size: 12px; padding: 0 10px; }
            QPushButton:hover { background-color: #5A6A7D; }
        """)

        table_icon = QLabel("⊡" if self.state.view else "⊞")
        table_icon.setStyleSheet("font-size: 14px; color: #A0AEC0; background: transparent;")
        table_label = QLabel(self.table_name)
        table_label.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 600; background: transparent;")

        header_layout.addWidget(back_btn)
        header_layout.addSpacing(10)
        header_layout.addWidget(table_icon)
        header_layout.addSpacing(4)
        header_layout.addWidget(table_label)
        header_layout.addStretch()
        if self.state.view:
            view_badge = QLabel("view · read-only")
            view_badge.setStyleSheet("color: #A0AEC0; font-size: 11px; background: transparent;")
            header_layout.addWidget(view_badge)
        layout.addWidget(header)

        # Schema header
        schema_header = QFrame()
        schema_header.setFixedHeight(32)
        schema_header.setStyleSheet("QFrame { background-color: #fbc840; }")
        schema_header_layout = QHBoxLayout(schema_header)
        schema_header_layout.setContentsMargins(12, 0, 12, 0)
        schema_icon = QLabel("⊞")
        schema_icon.setStyleSheet("font-size: 12px; color: #744210; background: transparent;")
        schema_title = QLabel("Schema")
        schema_title.setStyleSheet("color: #744210; font-size: 12px; font-weight: 600; background: transparent;")
        schema_header_layout.addWidget(schema_icon)
        schema_header_layout.addSpacing(4)
        schema_header_layout.addWidget(schema_title)
        schema_header_layout.addStretch()
        layout.addWidget(schema_header)

        # Column headers
        col_header = QFrame()
        col_header.setFixedHeight(36)
        col_header.setStyleSheet("QFrame { background-color: #252D3A; }")
        col_header_layout = QHBoxLayout(col_header)
        col_header_layout.setContentsMargins(12, 0, 12, 0)
        header_style = "color: #718096; font-size: 11px; font-weight: 600; background: transparent;"
        col_label = QLabel("Column")
        col_label.setStyleSheet(header_style)
        col_label.setFixedWidth(90)
        type_label = QLabel("Type")
        type_label.setStyleSheet(header_style)
        type_label.setFixedWidth(90)
        null_label = QLabel("Null")
        null_label.setStyleSheet(header_style)
        null_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        col_header_layout.addWidget(col_label)
        col_header_layout.addWidget(type_label)
        col_header_layout.addStretch()
        col_header_layout.addWidget(null_label)
        layout.addWidget(col_header)

        # Schema rows
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea { background-color: #2D3748; border: none; }
            QWidget { background-color: #2D3748; }
            QScrollBar:vertical { background: #2D3748; width: 6px; }
            QScrollBar::handle:vertical { background: #4A5568; border-radius: 3px; }
        """)
        self.schema_container = QWidget()
        self.schema_container.setStyleSheet("background-color: #2D3748;")
        self.schema_layout = QVBoxLayout(self.schema_container)
        self.schema_layout.setContentsMargins(0, 0, 0, 0)
        self.schema_layout.setSpacing(0)
        self.schema_layout.addStretch()
        scroll_area.setWidget(self.schema_container)
        layout.addWidget(scroll_area)

        self.add_field_btn = QPushButton("+ Add Field")
        self.add_field_btn.setFixedHeight(38)
        self.add_field_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_field_btn.clicked.connect(self.add_field)
        self.add_field_btn.setStyleSheet(BOTTOM_BUTTON_STYLE)
        layout.addWidget(self.add_field_btn)
        return panel

    def _create_schema_row(self, field_name, type_value, is_nullable, is_pk=False, is_fk=False):
        row_frame = QFrame()
        row_frame.setFixedHeight(42)
        row_frame.setStyleSheet("""
            QFrame { background-color: #2D3748; border-bottom: 1px solid #3D4852; }
            QFrame:hover { background-color: #3D4A5C; }
        """)
        if self.state.editable:
            row_frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            row_frame.setToolTip("Right-click to rename or delete")
            row_frame.customContextMenuRequested.connect(
                lambda pos, f=row_frame: self._show_schema_context_menu(pos, f))

        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(12, 0, 12, 0)
        row_layout.setSpacing(6)

        name_container = QWidget()
        name_container.setStyleSheet("background: transparent;")
        name_layout = QHBoxLayout(name_container)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(4)
        if is_pk or is_fk:
            icon = QLabel("🔑" if is_pk else "🔗")
            icon.setStyleSheet("font-size: 11px; background: transparent;")
            name_layout.addWidget(icon)
        name_label = QLabel(field_name)
        name_label.setObjectName("field_name_label")
        name_label.setStyleSheet("color: #E2E8F0; font-size: 12px; background: transparent;")
        name_layout.addWidget(name_label)
        name_layout.addStretch()
        name_container.setFixedWidth(90)

        type_badge = QLabel(type_value)
        type_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        type_badge.setFixedHeight(22)
        type_badge.setMinimumWidth(70)
        type_badge.setStyleSheet("QLabel { background-color: #4A5568; color: #E2E8F0; border-radius: 4px; font-size: 10px; padding: 0 8px; }")

        null_container = QWidget()
        null_container.setStyleSheet("background: transparent;")
        null_container.setFixedWidth(50)
        null_layout = QHBoxLayout(null_container)
        null_layout.setContentsMargins(0, 0, 0, 0)
        null_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if is_nullable:
            null_dot = QLabel("●")
            null_dot.setStyleSheet("color: #48BB78; font-size: 12px; background: transparent;")
            null_layout.addWidget(null_dot)
        checkbox_frame = QFrame()
        checkbox_frame.setFixedSize(14, 14)
        if is_nullable:
            checkbox_frame.setStyleSheet("QFrame { background-color: rgba(72, 187, 120, 0.3); border: 2px solid #48BB78; border-radius: 3px; }")
        else:
            checkbox_frame.setStyleSheet("QFrame { background-color: transparent; border: 2px solid #4A5568; border-radius: 3px; }")
        null_layout.addWidget(checkbox_frame)

        row_layout.addWidget(name_container)
        row_layout.addWidget(type_badge)
        row_layout.addStretch()
        row_layout.addWidget(null_container)
        return row_frame

    def _show_schema_context_menu(self, pos, row_frame):
        if row_frame not in self.schema_rows:
            return
        col_index = self.schema_rows.index(row_frame)
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #1f2937; border: 1px solid #374151; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 8px 16px; color: #f3f4f6; border-radius: 4px; }
            QMenu::item:selected { background-color: #374151; }
        """)
        rename_action = QAction("Rename Field", self)
        rename_action.triggered.connect(lambda: self._rename_field(col_index))
        menu.addAction(rename_action)
        delete_action = QAction("Delete Field", self)
        delete_action.triggered.connect(lambda: self._delete_field(col_index))
        menu.addAction(delete_action)
        menu.exec(row_frame.mapToGlobal(pos))

    def _rename_field(self, col_index):
        if col_index >= len(self.state.columns):
            return
        old_name = self.state.columns[col_index][0]
        new_name = ask_new_name(self, "Rename Field", "Enter new field name:", old_name)
        if not new_name or new_name == old_name:
            return
        if self.state.has_column(new_name, ignore_index=col_index):
            show_styled_message(self, "Rename Field", f"'{self.table_name}' already has a field named '{new_name}'.",
                                QMessageBox.Icon.Warning)
            return

        self.state.rename_column(col_index, new_name)
        name_label = self.schema_rows[col_index].findChild(QLabel, "field_name_label")
        if name_label:
            name_label.setText(new_name)
        header_item = self.table.horizontalHeaderItem(col_index)
        if header_item:
            header_item.setText(new_name)
        self.field_renamed.emit(self.table_name, old_name, new_name, self.state.columns)
        self._changed()

    def _delete_field(self, col_index):
        if col_index >= len(self.state.columns):
            return
        field_name = self.state.columns[col_index][0]
        if not confirm(self, "Delete Field", f"Are you sure you want to delete '{field_name}'?"):
            return

        self.state.delete_column(col_index)
        self.table.removeColumn(col_index)
        self.schema_rows.pop(col_index).deleteLater()
        self.field_deleted.emit(self.table_name, self.state.columns)
        self._changed()

    def add_field(self):
        dialog = InputFieldsWindow(existing_names=self.state.column_names(), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.get_data():
            return
        self._append_column(dialog.get_data())
        self.table_data_ready.emit(self.table_name, self.state.columns)
        self._changed()

    def _append_column(self, column, origin=None):
        """Add one column (name, type, Null/Not Null, PK/FK/-, fk_table, fk_field[, AUTO]) to both panels.
        origin is the column's name in the database, or None for a column added here."""
        field_name, type_value, null_flag, key_flag = column[:4]
        col_index = len(self.state.columns)
        defaults = self.state.add_column(column, origin)

        self.table.insertColumn(col_index)
        self.table.setHorizontalHeaderItem(col_index, QTableWidgetItem(field_name))
        schema_row = self._create_schema_row(field_name, type_value, null_flag == "Null",
                                             key_flag == "PK", key_flag == "FK")
        self.schema_rows.append(schema_row)
        self.schema_layout.insertWidget(self.schema_layout.count() - 1, schema_row)
        for row_index, value in enumerate(defaults):
            self._show_cell(row_index, col_index, value)

    # ---------------- Data panel ----------------
    def _build_data_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background-color: #2D3748; border-radius: 10px; }")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._create_panel_shadow(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("QFrame { background-color: #2D3748; border-top-left-radius: 10px; border-top-right-radius: 10px; }")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        table_icon = QLabel("⊞")
        table_icon.setStyleSheet("font-size: 14px; color: #A0AEC0; background: transparent;")
        table_label = QLabel(self.table_name)
        table_label.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 600; background: transparent;")
        self.row_count_label = QLabel("0 rows")
        self.row_count_label.setStyleSheet("background-color: #4A5568; color: #E2E8F0; padding: 4px 10px; border-radius: 10px; font-size: 11px;")
        header_layout.addWidget(table_icon)
        header_layout.addSpacing(4)
        header_layout.addWidget(table_label)
        header_layout.addStretch()

        self.pending_label = QLabel("● unsaved - Run to save")
        self.pending_label.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 600; background: transparent;")
        self.pending_label.setToolTip("These changes are in the SQL panel. Click Run Query to save them to the database.")
        self.pending_label.hide()
        header_layout.addWidget(self.pending_label)
        self.discard_btn = QPushButton("Discard")
        self.discard_btn.setFixedHeight(22)
        self.discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discard_btn.setToolTip("Throw away this table's changes that have not been run yet")
        self.discard_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: #fca5a5;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 8px;
            }
            QPushButton:hover { background-color: #991b1b; color: #fee2e2; }
        """)
        self.discard_btn.clicked.connect(lambda: self.discard_requested.emit(self.table_name))
        self.discard_btn.hide()
        header_layout.addWidget(self.discard_btn)
        header_layout.addSpacing(8)
        header_layout.addWidget(self.row_count_label)
        layout.addWidget(header)

        # Data header
        data_header = QFrame()
        data_header.setFixedHeight(32)
        data_header.setStyleSheet("QFrame { background-color: #48BB78; }")
        data_header_layout = QHBoxLayout(data_header)
        data_header_layout.setContentsMargins(12, 0, 12, 0)
        data_icon = QLabel("≡")
        data_icon.setStyleSheet("font-size: 12px; color: #FFFFFF; background: transparent;")
        data_title = QLabel("Data Records")
        data_title.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 600; background: transparent;")
        data_header_layout.addWidget(data_icon)
        data_header_layout.addSpacing(4)
        data_header_layout.addWidget(data_title)
        data_header_layout.addStretch()
        layout.addWidget(data_header)

        # Data table
        self.table = QTableWidget()
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.setStyleSheet(DATA_TABLE_STYLE)
        layout.addWidget(self.table)

        self.add_row_btn = QPushButton("+ Add Row")
        self.add_row_btn.setFixedHeight(38)
        self.add_row_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_row_btn.clicked.connect(self.add_rows)
        self.add_row_btn.setStyleSheet(BOTTOM_BUTTON_STYLE)
        layout.addWidget(self.add_row_btn)
        return panel

    def _column_type(self, col_index):
        return self.state.columns[col_index][1] if col_index < len(self.state.columns) else ""

    def _is_id_column(self, col_index):
        if col_index >= len(self.state.columns):
            return False
        column = self.state.columns[col_index]
        return is_primary_key(column) or column[0].lower() == "id"

    def _on_cell_changed(self, row, col):
        item = self.table.item(row, col)
        if item is None or row >= len(self.state.rows) or col >= len(self.state.columns):
            return
        text = item.text()
        if sqlgen.is_money_type(self._column_type(col)) and text.strip().startswith("$"):
            text = text.strip()[1:]  # the '$' is only how money is shown
        self.state.set_cell(row, col, text)
        self._show_cell(row, col, text)
        self._changed()

    def _show_cell(self, row, col, value):
        """Show one value in the data table, styled by its column."""
        self.table.blockSignals(True)
        try:
            text = cell_text(value)
            column_type = self._column_type(col)
            if sqlgen.is_money_type(column_type) and value is not None and _looks_numeric(text):
                text = f"${text}"

            item = self.table.item(row, col)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(row, col, item)
            item.setText(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if not self.state.editable:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if value is None or (isinstance(value, str) and value.strip().upper() == NULL_TEXT):
                item.setForeground(QColor("#718096"))
                font = QFont("Segoe UI", 10)
                font.setItalic(True)
                item.setFont(font)
            elif self._is_id_column(col):
                item.setForeground(QColor("#63B3ED"))
                item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            elif sqlgen.is_exact_decimal_type(column_type):
                item.setForeground(QColor("#48BB78"))
                item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            else:
                item.setForeground(QColor("#E2E8F0"))
                item.setFont(QFont("Segoe UI", 10))
        finally:
            self.table.blockSignals(False)

    def add_rows(self):
        if not self.state.editable:
            return
        if not self.state.columns:
            show_styled_message(self, "No Fields", "Please add at least one field before adding rows.",
                                QMessageBox.Icon.Warning)
            return
        row = self.state.add_row()
        new_index = len(self.state.rows) - 1
        self.table.setRowCount(len(self.state.rows))
        self.table.setRowHeight(new_index, ROW_HEIGHT)
        for col, value in enumerate(row):
            self._show_cell(new_index, col, value)
        self.table.scrollToBottom()
        self._update_row_count()
        self._changed()

    def set_rows(self, result_columns, rows, truncated=False):
        """Show rows read from the database (values already JSON-decoded), matched to columns by name."""
        self.state.load_rows(result_columns, rows)
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.state.rows))
        for row_index, row in enumerate(self.state.rows):
            self.table.setRowHeight(row_index, ROW_HEIGHT)
            for col_index, value in enumerate(row):
                self._show_cell(row_index, col_index, value)
        self._update_row_count(truncated)
        self._show_pending(self.state.has_changes())

    # ---------------- Changes ----------------
    def _changed(self):
        self._show_pending(self.state.has_changes())
        self.changes_made.emit()

    def _show_pending(self, pending):
        self.pending_label.setVisible(pending)
        self.discard_btn.setVisible(pending)

    def _update_row_count(self, truncated=False):
        count = len(self.state.rows)
        if truncated:
            self.row_count_label.setText(f"first {count} rows")
        else:
            self.row_count_label.setText(f"{count} row{'s' if count != 1 else ''}")

    def keyPressEvent(self, event):
        if event.key() != Qt.Key.Key_Delete:
            super().keyPressEvent(event)
            return
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if not selected_rows or not self.state.editable:
            return
        if not confirm(self, "Delete Row(s)", "Do you want to delete the selected row(s)?"):
            return
        self.state.delete_rows(selected_rows)
        for row in reversed(selected_rows):
            self.table.removeRow(row)
        self._update_row_count()
        self._changed()

    def go_back(self):
        self.stacked.setCurrentIndex(0)


def _looks_numeric(text):
    return text.replace(".", "", 1).lstrip("-").isdigit()
