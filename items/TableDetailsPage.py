from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
    QMessageBox, QDialog, QLineEdit, QDialogButtonBox, QComboBox, QCheckBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal

from items.ToolBar import Toolbar
from items.InputFieldsWindow import InputFieldsWindow


class TableDetailsPage(QWidget):
    table_data_ready = pyqtSignal(str, list)
    field_deleted = pyqtSignal(str, list)

    def __init__(self, table_name, stacked, all_table_schemas=None):
        super().__init__()
        self.table_name = table_name
        self.columns = []  # stores lists like [field_name, type, isnull, pk, fk_table, fk_field]
        self.rows = []
        self.stacked = stacked
        self.all_table_schemas = all_table_schemas or {}

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background-color: #5a6b82;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Toolbar
        layout.addWidget(Toolbar())

        # Back button
        go_back = QPushButton("<- Back")
        go_back.clicked.connect(self.go_back)
        layout.addWidget(go_back)

        # Header
        layout.addWidget(QLabel(f"Table: {table_name}", styleSheet="font-size: 18px; font-weight: 600;"))

        # Schema Table
        self.scheme = QTableWidget()
        self.scheme.setColumnCount(6)
        self.scheme.setHorizontalHeaderLabels(["FieldName", "Type", "IsNull", "Primary Key", "FK Table", "FK Field"])
        self.scheme.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.scheme.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.scheme)

        # Add Field button
        add_field_btn = QPushButton("Add Field")
        add_field_btn.clicked.connect(self.add_field)
        layout.addWidget(add_field_btn)

        # Data Table
        self.table = QTableWidget()
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        layout.addWidget(self.table)

        # Add Row button
        add_rows = QPushButton("Add Row")
        add_rows.clicked.connect(self.add_rows)
        layout.addWidget(add_rows)

    def add_rows(self):
        new_row = ["Unknown" for _ in range(len(self.columns))]
        self.rows.append(new_row)
        new_index = len(self.rows) - 1
        self.table.setRowCount(len(self.rows))
        for col, value in enumerate(new_row):
            self.table.setItem(new_index, col, QTableWidgetItem(str(value)))

    def add_field(self):
        field_info = InputFieldsWindow(table_names=list(self.all_table_schemas.keys()))
        field_info.table_schemas = self.all_table_schemas
        result = field_info.exec()
        if result != QDialog.DialogCode.Accepted:
            return

        new_data = field_info.get_data()  # returns 6 values now
        if not new_data:
            return

        field_name, type_value, isnull_value, pk_flag, fk_table, fk_field = new_data

        # Add column to data table
        col_index = self.table.columnCount()
        self.table.insertColumn(col_index)
        self.table.setHorizontalHeaderItem(col_index, QTableWidgetItem(field_name))

        # Add row to schema table
        row_index = self.scheme.rowCount()
        self.scheme.insertRow(row_index)
        for i, val in enumerate(new_data):
            self.scheme.setItem(row_index, i, QTableWidgetItem(val))

        self.columns.append(new_data)
        self.table_data_ready.emit(self.table_name, self.columns)

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
