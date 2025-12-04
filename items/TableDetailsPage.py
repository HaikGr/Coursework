from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
    QMessageBox, QDialog, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from items.ToolBar import Toolbar
from items.InputFieldsWindow import InputFieldsWindow


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

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background-color: #2C3E50;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toolbar
        main_layout.addWidget(Toolbar())

        # Content area with horizontal split
        content_widget = QWidget()
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

    def _build_schema_panel(self):
        """Build the left schema panel"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #34495E;
                border-radius: 12px;
            }
        """)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #2C3E50;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                padding: 12px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        # Back button
        back_btn = QPushButton("← Back")
        back_btn.setFixedSize(80, 32)
        back_btn.clicked.connect(self.go_back)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #5A6C82;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #6B7D8E;
            }
            QPushButton:pressed {
                background-color: #4A5C72;
            }
        """)
        
        # Table name with icon
        table_icon = QLabel("📊")
        table_icon.setStyleSheet("font-size: 18px; background: transparent;")
        
        table_label = QLabel(self.table_name)
        table_label.setStyleSheet("""
            color: #FFFFFF;
            font-size: 16px;
            font-weight: 600;
            background: transparent;
        """)
        
        header_layout.addWidget(back_btn)
        header_layout.addSpacing(10)
        header_layout.addWidget(table_icon)
        header_layout.addWidget(table_label)
        header_layout.addStretch()
        
        layout.addWidget(header)

        # Schema section header
        schema_header = QFrame()
        schema_header.setStyleSheet("""
            QFrame {
                background-color: #F39C12;
                padding: 8px;
            }
        """)
        schema_header_layout = QHBoxLayout(schema_header)
        schema_header_layout.setContentsMargins(15, 8, 15, 8)
        
        schema_icon = QLabel("📋")
        schema_icon.setStyleSheet("font-size: 14px; background: transparent;")
        
        schema_title = QLabel("Schema")
        schema_title.setStyleSheet("""
            color: #FFFFFF;
            font-size: 14px;
            font-weight: 600;
            background: transparent;
        """)
        
        schema_header_layout.addWidget(schema_icon)
        schema_header_layout.addWidget(schema_title)
        schema_header_layout.addStretch()
        
        layout.addWidget(schema_header)

        # Schema table
        self.scheme = QTableWidget()
        self.scheme.setColumnCount(3)
        self.scheme.setHorizontalHeaderLabels(["Column", "Type", "Null"])
        self.scheme.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.scheme.verticalHeader().setVisible(False)
        self.scheme.setStyleSheet("""
            QTableWidget {
                background-color: #34495E;
                border: none;
                gridline-color: #2C3E50;
                color: #ECF0F1;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2C3E50;
            }
            QTableWidget::item:selected {
                background-color: #4A6278;
            }
            QHeaderView::section {
                background-color: #2C3E50;
                color: #BDC3C7;
                padding: 10px;
                border: none;
                font-weight: 600;
                font-size: 12px;
            }
            QScrollBar:vertical {
                background: #2C3E50;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #5A6C82;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6B7D8E;
            }
        """)
        
        layout.addWidget(self.scheme)

        # Add Field button
        add_field_btn = QPushButton("+ Add Field")
        add_field_btn.setFixedHeight(40)
        add_field_btn.clicked.connect(self.add_field)
        add_field_btn.setStyleSheet("""
            QPushButton {
                background-color: #2C3E50;
                color: #ECF0F1;
                border: none;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3A4F65;
            }
            QPushButton:pressed {
                background-color: #243342;
            }
        """)
        
        layout.addWidget(add_field_btn)

        return panel

    def _build_data_panel(self):
        """Build the right data records panel"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #34495E;
                border-radius: 12px;
            }
        """)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with table name and row count
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #2C3E50;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        table_icon = QLabel("📊")
        table_icon.setStyleSheet("font-size: 18px; background: transparent;")
        
        table_label = QLabel(self.table_name)
        table_label.setStyleSheet("""
            color: #FFFFFF;
            font-size: 16px;
            font-weight: 600;
            background: transparent;
        """)
        
        self.row_count_label = QLabel("0 rows")
        self.row_count_label.setStyleSheet("""
            background-color: #5A6C82;
            color: white;
            padding: 5px 12px;
            border-radius: 10px;
            font-size: 12px;
            font-weight: 500;
        """)
        
        header_layout.addWidget(table_icon)
        header_layout.addWidget(table_label)
        header_layout.addStretch()
        header_layout.addWidget(self.row_count_label)
        
        layout.addWidget(header)

        # Data Records section header
        data_header = QFrame()
        data_header.setStyleSheet("""
            QFrame {
                background-color: #27AE60;
                padding: 8px;
            }
        """)
        data_header_layout = QHBoxLayout(data_header)
        data_header_layout.setContentsMargins(15, 8, 15, 8)
        
        data_icon = QLabel("📁")
        data_icon.setStyleSheet("font-size: 14px; background: transparent;")
        
        data_title = QLabel("Data Records")
        data_title.setStyleSheet("""
            color: #FFFFFF;
            font-size: 14px;
            font-weight: 600;
            background: transparent;
        """)
        
        data_header_layout.addWidget(data_icon)
        data_header_layout.addWidget(data_title)
        data_header_layout.addStretch()
        
        layout.addWidget(data_header)

        # Data table
        self.table = QTableWidget()
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(True)
        self.table.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #445566;
                border: none;
                gridline-color: #34495E;
                color: #ECF0F1;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #34495E;
            }
            QTableWidget::item:selected {
                background-color: #4A6278;
            }
            QHeaderView::section {
                background-color: #34495E;
                color: #ECF0F1;
                padding: 10px;
                border: none;
                font-weight: 600;
                font-size: 13px;
            }
            QHeaderView::section:horizontal {
                border-right: 1px solid #2C3E50;
            }
            QTableWidget::item:alternate-row {
                background-color: #3E5060;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: #2C3E50;
                width: 10px;
                height: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #5A6C82;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
                background: #6B7D8E;
            }
        """)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)

        # Add Row button
        add_row_btn = QPushButton("+ Add Row")
        add_row_btn.setFixedHeight(40)
        add_row_btn.clicked.connect(self.add_rows)
        add_row_btn.setStyleSheet("""
            QPushButton {
                background-color: #2C3E50;
                color: #ECF0F1;
                border: none;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3A4F65;
            }
            QPushButton:pressed {
                background-color: #243342;
            }
        """)
        
        layout.addWidget(add_row_btn)

        return panel

    def add_rows(self):
        new_row = ["Unknown" for _ in range(len(self.columns))]
        self.rows.append(new_row)
        new_index = len(self.rows) - 1
        self.table.setRowCount(len(self.rows))
        
        for col, value in enumerate(new_row):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(new_index, col, item)
        
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

        # Add column to data table
        col_index = self.table.columnCount()
        self.table.insertColumn(col_index)
        self.table.setHorizontalHeaderItem(col_index, QTableWidgetItem(field_name))

        # Add row to schema table (only show 3 columns visually)
        row_index = self.scheme.rowCount()
        self.scheme.insertRow(row_index)
        
        # Column name with icon
        name_item = QTableWidgetItem(field_name)
        if pk_flag == "PK":
            name_item.setText(f"🔑 {field_name}")
        elif pk_flag == "FK":
            name_item.setText(f"🔗 {field_name}")
        name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.scheme.setItem(row_index, 0, name_item)
        
        # Type with badge style
        type_item = QTableWidgetItem(type_value)
        type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scheme.setItem(row_index, 1, type_item)
        
        # Null indicator
        null_item = QTableWidgetItem("●" if isnull_value == "Null" else "")
        null_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if isnull_value == "Null":
            null_item.setForeground(Qt.GlobalColor.green)
        self.scheme.setItem(row_index, 2, null_item)

        self.columns.append(new_data)
        self.table_data_ready.emit(self.table_name, self.columns)

    def _update_row_count(self):
        """Update the row count badge"""
        count = len(self.rows)
        self.row_count_label.setText(f"{count} row{'s' if count != 1 else ''}")

    def keyPressEvent(self, event):
        if event.key() != Qt.Key.Key_Delete:
            super().keyPressEvent(event)
            return

        # Delete selected rows
        rows_to_delete = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        if rows_to_delete:
            reply = QMessageBox.question(self, "Delete Row(s)", "Do you want to delete the selected row(s)?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                for row in rows_to_delete:
                    self.table.removeRow(row)
                    del self.rows[row]
                self._update_row_count()
            return

        # Delete selected fields
        fields_to_delete = sorted({item.row() for item in self.scheme.selectedItems()}, reverse=True)
        if fields_to_delete:
            reply = QMessageBox.question(self, "Delete Field(s)", "Do you want to delete the selected field(s)?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                for col in fields_to_delete:
                    self.table.removeColumn(col)
                    self.scheme.removeRow(col)
                    if col < len(self.columns):
                        del self.columns[col]
                    for row_data in self.rows:
                        if col < len(row_data):
                            del row_data[col]
                self.field_deleted.emit(self.table_name, self.columns)

    def go_back(self):
        self.stacked.setCurrentIndex(0)