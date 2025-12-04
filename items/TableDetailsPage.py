from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
    QMessageBox, QDialog, QScrollArea, QGraphicsDropShadowEffect,
    QLineEdit, QMenu, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QAction

from items.ToolBar import Toolbar
from items.InputFieldsWindow import InputFieldsWindow


def show_styled_message(parent, title, text, icon=QMessageBox.Icon.Information):
    """Show a styled message box with dark theme"""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon)
    msg.setStyleSheet("""
        QMessageBox {
            background-color: #1f2937;
        }
        QMessageBox QLabel {
            color: #f3f4f6;
            font-size: 14px;
            min-width: 250px;
        }
        QPushButton {
            background-color: #3777f0;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-size: 13px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #2563eb;
        }
    """)
    return msg.exec()


def show_styled_question(parent, title, text):
    """Show a styled question dialog with dark theme"""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    msg.setDefaultButton(QMessageBox.StandardButton.No)
    msg.setStyleSheet("""
        QMessageBox {
            background-color: #1f2937;
        }
        QMessageBox QLabel {
            color: #f3f4f6;
            font-size: 14px;
            min-width: 280px;
        }
        QPushButton {
            background-color: #4b5563;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-size: 13px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #6b7280;
        }
        QPushButton:focus {
            background-color: #3777f0;
        }
    """)
    return msg.exec()


class TableDetailsPage(QWidget):
    table_data_ready = pyqtSignal(str, list)
    field_deleted = pyqtSignal(str, list)

    def __init__(self, table_name, stacked, all_table_schemas=None):
        super().__init__()
        self.table_name = table_name
        self.columns = []
        self.rows = []
        self.stacked = stacked
        self.all_table_schemas = all_table_schemas or {}
        self.schema_rows = []

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background-color: #f5f6f7;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toolbar
        main_layout.addWidget(Toolbar())

        # Content area
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #f5f6f7;")
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)

        # Left Panel - Schema
        self.schema_panel = self._build_schema_panel()
        content_layout.addWidget(self.schema_panel, stretch=2)

        # Right Panel - Data Records
        self.data_panel = self._build_data_panel()
        content_layout.addWidget(self.data_panel, stretch=3)

        main_layout.addWidget(content_widget)

    def _create_panel_shadow(self, widget):
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
        
        table_icon = QLabel("⊞")
        table_icon.setStyleSheet("font-size: 14px; color: #A0AEC0; background: transparent;")
        
        table_label = QLabel(self.table_name)
        table_label.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 600; background: transparent;")
        
        header_layout.addWidget(back_btn)
        header_layout.addSpacing(10)
        header_layout.addWidget(table_icon)
        header_layout.addSpacing(4)
        header_layout.addWidget(table_label)
        header_layout.addStretch()
        
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
        
        col_label = QLabel("Column")
        col_label.setStyleSheet("color: #718096; font-size: 11px; font-weight: 600; background: transparent;")
        col_label.setFixedWidth(90)
        
        type_label = QLabel("Type")
        type_label.setStyleSheet("color: #718096; font-size: 11px; font-weight: 600; background: transparent;")
        type_label.setFixedWidth(90)
        
        null_label = QLabel("Null")
        null_label.setStyleSheet("color: #718096; font-size: 11px; font-weight: 600; background: transparent;")
        null_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        col_header_layout.addWidget(col_label)
        col_header_layout.addWidget(type_label)
        col_header_layout.addStretch()
        col_header_layout.addWidget(null_label)
        
        layout.addWidget(col_header)

        # Schema scroll area
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

        # Hidden table
        self.scheme = QTableWidget()
        self.scheme.setColumnCount(3)
        self.scheme.setHorizontalHeaderLabels(["Column", "Type", "Null"])
        self.scheme.hide()

        # Add Field button
        add_field_btn = QPushButton("+ Add Field")
        add_field_btn.setFixedHeight(38)
        add_field_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_field_btn.clicked.connect(self.add_field)
        add_field_btn.setStyleSheet("""
            QPushButton { background-color: #252D3A; color: #A0AEC0; border: none; border-bottom-left-radius: 10px; border-bottom-right-radius: 10px; font-size: 12px; }
            QPushButton:hover { background-color: #2D3748; color: #E2E8F0; }
        """)
        
        layout.addWidget(add_field_btn)

        return panel

    def _create_schema_row(self, field_name, type_value, is_nullable, is_pk=False, is_fk=False, col_index=0):
        row_frame = QFrame()
        row_frame.setFixedHeight(42)
        row_frame.setProperty("col_index", col_index)
        row_frame.setProperty("field_name", field_name)
        row_frame.setStyleSheet("""
            QFrame { background-color: #2D3748; border-bottom: 1px solid #3D4852; }
            QFrame:hover { background-color: #3D4A5C; }
        """)
        row_frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        row_frame.customContextMenuRequested.connect(lambda pos, f=row_frame: self._show_schema_context_menu(pos, f))
        
        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(12, 0, 12, 0)
        row_layout.setSpacing(6)
        
        name_container = QWidget()
        name_container.setStyleSheet("background: transparent;")
        name_layout = QHBoxLayout(name_container)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(4)
        
        if is_pk:
            icon = QLabel("🔑")
            icon.setStyleSheet("font-size: 11px; background: transparent;")
            name_layout.addWidget(icon)
        elif is_fk:
            icon = QLabel("🔗")
            icon.setStyleSheet("font-size: 11px; background: transparent;")
            name_layout.addWidget(icon)
        
        name_label = QLabel(field_name)
        name_label.setObjectName("field_name_label")
        name_label.setStyleSheet("color: #E2E8F0; font-size: 12px; background: transparent;")
        name_layout.addWidget(name_label)
        name_layout.addStretch()
        
        name_container.setFixedWidth(90)
        
        type_badge = QLabel(type_value)
        type_badge.setObjectName("field_type_label")
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
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #1f2937; border: 1px solid #374151; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 8px 16px; color: #f3f4f6; border-radius: 4px; }
            QMenu::item:selected { background-color: #374151; }
        """)
        
        col_index = row_frame.property("col_index")
        
        rename_action = QAction("Rename Field", self)
        rename_action.triggered.connect(lambda: self._rename_field(col_index))
        menu.addAction(rename_action)
        
        delete_action = QAction("Delete Field", self)
        delete_action.triggered.connect(lambda: self._delete_field(col_index))
        menu.addAction(delete_action)
        
        menu.exec(row_frame.mapToGlobal(pos))

    def _rename_field(self, col_index):
        if col_index >= len(self.columns):
            return
        
        old_name = self.columns[col_index][0]
        
        # Create styled input dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Rename Field")
        dialog.setFixedSize(350, 150)
        dialog.setStyleSheet("""
            QDialog { background-color: #1f2937; }
            QLabel { color: #f3f4f6; font-size: 14px; }
            QLineEdit {
                background-color: #374151;
                color: #f3f4f6;
                border: 2px solid #4b5563;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus { border: 2px solid #3777f0; }
            QPushButton {
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                min-width: 80px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        label = QLabel("Enter new field name:")
        layout.addWidget(label)
        
        line_edit = QLineEdit(old_name)
        line_edit.selectAll()
        layout.addWidget(line_edit)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("QPushButton { background-color: #4b5563; color: white; } QPushButton:hover { background-color: #6b7280; }")
        cancel_btn.clicked.connect(dialog.reject)
        
        ok_btn = QPushButton("Rename")
        ok_btn.setStyleSheet("QPushButton { background-color: #3777f0; color: white; } QPushButton:hover { background-color: #2563eb; }")
        ok_btn.clicked.connect(dialog.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = line_edit.text().strip()
            if new_name and new_name != old_name:
                # Update column data - convert tuple to list, modify, convert back
                col_data = list(self.columns[col_index])
                col_data[0] = new_name
                self.columns[col_index] = tuple(col_data)
                
                # Update schema row label
                if col_index < len(self.schema_rows):
                    row_frame = self.schema_rows[col_index]
                    name_label = row_frame.findChild(QLabel, "field_name_label")
                    if name_label:
                        name_label.setText(new_name)
                    row_frame.setProperty("field_name", new_name)
                
                # Update data table header
                header_item = self.table.horizontalHeaderItem(col_index)
                if header_item:
                    header_item.setText(new_name)
                
                # Emit signal to update diagram
                self.table_data_ready.emit(self.table_name, self.columns)

    def _delete_field(self, col_index):
        if col_index >= len(self.columns):
            return
        
        field_name = self.columns[col_index][0]
        reply = show_styled_question(self, "Delete Field", f"Are you sure you want to delete '{field_name}'?")
        
        if reply == QMessageBox.StandardButton.Yes:
            self.table.removeColumn(col_index)
            
            if col_index < len(self.schema_rows):
                row_widget = self.schema_rows.pop(col_index)
                row_widget.deleteLater()
            
            # Update indices for remaining rows
            for i, row in enumerate(self.schema_rows):
                row.setProperty("col_index", i)
            
            del self.columns[col_index]
            
            for row_data in self.rows:
                if col_index < len(row_data):
                    del row_data[col_index]
            
            self.field_deleted.emit(self.table_name, self.columns)

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
        self.table.setStyleSheet("""
            QTableWidget { background-color: #2D3748; alternate-background-color: #323D4D; border: none; color: #E2E8F0; font-size: 12px; }
            QTableWidget::item { padding: 10px 12px; border-bottom: 1px solid #3D4852; }
            QTableWidget::item:selected { background-color: #3777f0; color: #FFFFFF; }
            QHeaderView::section { background-color: #252D3A; color: #718096; padding: 10px 12px; border: none; font-weight: 600; font-size: 11px; }
            QScrollBar:vertical { background: #2D3748; width: 6px; }
            QScrollBar::handle:vertical { background: #4A5568; border-radius: 3px; }
            QScrollBar:horizontal { background: #2D3748; height: 6px; }
            QScrollBar::handle:horizontal { background: #4A5568; border-radius: 3px; }
        """)
        
        layout.addWidget(self.table)

        # Add Row button
        add_row_btn = QPushButton("+ Add Row")
        add_row_btn.setFixedHeight(38)
        add_row_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_row_btn.clicked.connect(self.add_rows)
        add_row_btn.setStyleSheet("""
            QPushButton { background-color: #252D3A; color: #A0AEC0; border: none; border-bottom-left-radius: 10px; border-bottom-right-radius: 10px; font-size: 12px; }
            QPushButton:hover { background-color: #2D3748; color: #E2E8F0; }
        """)
        
        layout.addWidget(add_row_btn)

        return panel

    def _on_cell_changed(self, row, col):
        if row < len(self.rows) and col < len(self.rows[row]):
            item = self.table.item(row, col)
            if item:
                new_value = item.text()
                self.rows[row][col] = new_value
                self._update_data_cell(row, col, new_value)

    def _is_id_column(self, col_index):
        if col_index < len(self.columns):
            field_name = self.columns[col_index][0].lower()
            pk_flag = self.columns[col_index][3] if len(self.columns[col_index]) > 3 else ""
            return pk_flag == "PK" or field_name == "id"
        return False

    def _is_money_column(self, col_index):
        if col_index < len(self.columns):
            col_type = self.columns[col_index][1].lower()
            return "money" in col_type or "decimal" in col_type
        return False

    def _update_data_cell(self, row, col, value):
        self.table.blockSignals(True)
        
        item = self.table.item(row, col)
        if not item:
            item = QTableWidgetItem(str(value))
            self.table.setItem(row, col, item)
        else:
            item.setText(str(value))
        
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if self._is_id_column(col):
            item.setForeground(QColor("#63B3ED"))
            item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        elif self._is_money_column(col):
            display_val = str(value)
            if not display_val.startswith("$") and display_val.replace(".", "").replace("-", "").isdigit():
                display_val = f"${value}"
                item.setText(display_val)
            item.setForeground(QColor("#48BB78"))
            item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        else:
            item.setForeground(QColor("#E2E8F0"))
            item.setFont(QFont("Segoe UI", 10))
        
        self.table.blockSignals(False)

    def add_rows(self):
        if not self.columns:
            show_styled_message(self, "No Fields", "Please add at least one field before adding rows.", QMessageBox.Icon.Warning)
            return
        
        new_row = []
        for i, col_data in enumerate(self.columns):
            col_type = col_data[1].lower()
            pk_flag = col_data[3] if len(col_data) > 3 else ""
            
            if pk_flag == "PK" or "int" in col_type:
                new_row.append(len(self.rows) + 1)
            elif "money" in col_type or "decimal" in col_type:
                new_row.append("0")
            elif "date" in col_type:
                from datetime import date
                new_row.append(date.today().isoformat())
            else:
                new_row.append("")
        
        self.rows.append(new_row)
        new_index = len(self.rows) - 1
        self.table.setRowCount(len(self.rows))
        self.table.setRowHeight(new_index, 42)
        
        for col, value in enumerate(new_row):
            self._update_data_cell(new_index, col, value)
        
        self._update_row_count()

    def add_field(self):
        field_info = InputFieldsWindow(table_names=list(self.all_table_schemas.keys()))
        field_info.table_schemas = self.all_table_schemas
        result = field_info.exec()
        if result != QDialog.DialogCode.Accepted:
            return

        new_data = field_info.get_data()
        if not new_data:
            return

        field_name, type_value, isnull_value, pk_flag, fk_table, fk_field = new_data

        col_index = self.table.columnCount()
        self.table.insertColumn(col_index)
        header_item = QTableWidgetItem(field_name)
        self.table.setHorizontalHeaderItem(col_index, header_item)

        is_pk = pk_flag == "PK"
        is_fk = pk_flag == "FK"
        is_nullable = isnull_value == "Null"
        
        schema_row = self._create_schema_row(field_name, type_value, is_nullable, is_pk, is_fk, col_index)
        self.schema_rows.append(schema_row)
        
        self.schema_layout.insertWidget(self.schema_layout.count() - 1, schema_row)

        row_index = self.scheme.rowCount()
        self.scheme.insertRow(row_index)
        
        name_item = QTableWidgetItem(field_name)
        if pk_flag == "PK":
            name_item.setText(f"🔑 {field_name}")
        elif pk_flag == "FK":
            name_item.setText(f"🔗 {field_name}")
        self.scheme.setItem(row_index, 0, name_item)
        
        type_item = QTableWidgetItem(type_value)
        self.scheme.setItem(row_index, 1, type_item)
        
        null_item = QTableWidgetItem("●" if isnull_value == "Null" else "")
        if isnull_value == "Null":
            null_item.setForeground(Qt.GlobalColor.green)
        self.scheme.setItem(row_index, 2, null_item)

        self.columns.append(new_data)
        
        for row_idx, row_data in enumerate(self.rows):
            default_val = ""
            if "int" in type_value.lower():
                default_val = row_idx + 1
            elif "money" in type_value.lower():
                default_val = "0"
            row_data.append(default_val)
            self._update_data_cell(row_idx, col_index, default_val)
        
        self.table_data_ready.emit(self.table_name, self.columns)

    def _update_row_count(self):
        count = len(self.rows)
        self.row_count_label.setText(f"{count} row{'s' if count != 1 else ''}")

    def keyPressEvent(self, event):
        if event.key() != Qt.Key.Key_Delete:
            super().keyPressEvent(event)
            return

        selected_rows = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        if selected_rows:
            reply = show_styled_question(self, "Delete Row(s)", "Do you want to delete the selected row(s)?")
            if reply == QMessageBox.StandardButton.Yes:
                for row in selected_rows:
                    self.table.removeRow(row)
                    if row < len(self.rows):
                        del self.rows[row]
                self._update_row_count()
            return

    def go_back(self):
        self.stacked.setCurrentIndex(0)
