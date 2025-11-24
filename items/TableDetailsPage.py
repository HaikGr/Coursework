from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,  QLabel,
    QPushButton, 
    QFrame,
    QTableWidget, QTableWidgetItem, 
    QHeaderView, QSizePolicy, QMessageBox, QDialog
)
from PyQt6.QtCore import (
    Qt, pyqtSignal
)

from items.ToolBar import Toolbar
from items.InputFieldsWindow import InputFieldsWindow

class TableDetailsPage(QWidget):
    table_data_ready = pyqtSignal(str, list)

    def __init__(self, table_name, stacked):
        super().__init__()
        self.table_name = table_name
        self.columns = []
        self.rows = []
        self.stacked = stacked
        self.input_window = None

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background-color: #5a6b82;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        toolbar = Toolbar()
        layout.addWidget(toolbar)
        go_back = QPushButton("<- Back")
        go_back.clicked.connect(self.go_back)
        layout.addWidget(go_back)
        header = QLabel(f"Table: {table_name}")
        header.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(header)
        schema_frame = QFrame()
        sf_layout = QVBoxLayout(schema_frame)
        sf_layout.setContentsMargins(8, 8, 8, 8)
        sf_layout.addWidget(QLabel("Schema:"))
        self.scheme = QTableWidget()
        self.scheme.setRowCount(len(self.columns))
        scheme_columns = ["FieldName", "Type", "IsNull"]
        self.scheme.setColumnCount(len(scheme_columns))
        self.scheme.setHorizontalHeaderLabels(scheme_columns)
        self.scheme.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.scheme.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.scheme)
        self.add_fields = QPushButton("Add Field")
        self.add_fields.clicked.connect(self.add_field)
        layout.addWidget(self.add_fields)
        self.table = QTableWidget()
        self.table.setStyleSheet("border-radius: 10px;")
        self.table.setColumnCount(len(self.columns))
        self.table.setRowCount(len(self.rows))
        self.table.setHorizontalHeaderLabels([x[0] for x in self.columns])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.table.setFocus()
        layout.addWidget(self.table)
        add_rows = QPushButton("Add Row")
        add_rows.clicked.connect(self.add_rows)
        layout.addWidget(add_rows)

    def add_rows(self):
        new_row = ["Unknown" for i in range(len(self.columns))]
        self.rows.append(new_row)
        new_row_index = len(self.rows) - 1
        self.table.setRowCount(len(self.rows))
        for col, value in enumerate(new_row):
            self.table.setItem(new_row_index, col, QTableWidgetItem(str(value)))

    def add_field(self):
        field_info = InputFieldsWindow()
        result = field_info.exec()
        if result == QDialog.DialogCode.Accepted:
            new_data = field_info.get_data()
            if not new_data:
                return
            field_name, type_value, isnull_value = new_data
            current_columns = self.table.columnCount()
            self.table.insertColumn(current_columns)
            self.table.setHorizontalHeaderItem(current_columns, QTableWidgetItem(field_name))
            current_rows = self.scheme.rowCount()
            self.scheme.insertRow(current_rows)
            for col_index, value in enumerate(new_data):
                self.scheme.setItem(current_rows, col_index, QTableWidgetItem(value))
            self.columns.append(new_data)
            self.table_data_ready.emit(self.table_name, [x[0] for x in self.columns])

    def delete_selected_rows(self):
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        if not selected_rows:
            return
        for row in sorted(selected_rows, reverse=True):
            self.table.removeRow(row)
            del self.rows[row]

    def delete_selected_field(self):
        selected_items = self.scheme.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a field to delete.")
            return
        selected_row = selected_items[0].row()
        field_name = self.scheme.item(selected_row, 0).text()
        reply = QMessageBox.question(
            self,
            "Delete Field",
            f"Are you sure you want to delete the field '{field_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        column_index = selected_row
        self.table.removeColumn(column_index)
        self.scheme.removeRow(selected_row)
        del self.columns[selected_row]
        for row_data in self.rows:
            if column_index < len(row_data):
                del row_data[column_index]

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_rows = set()
            for item in self.table.selectedItems():
                selected_rows.add(item.row())
            if selected_rows:
                reply = QMessageBox.question(
                    self,
                    "Delete Row(s)",
                    "Do you want to delete the selected row(s)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    for row in sorted(selected_rows, reverse=True):
                        self.table.removeRow(row)
                        del self.rows[row]
                return
            selected_columns = set()
            for item in self.scheme.selectedItems():
                selected_columns.add(item.row())
            if selected_columns:
                reply = QMessageBox.question(
                    self,
                    "Delete Field(s)",
                    "Do you want to delete the selected field(s)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    for col_index in sorted(selected_columns, reverse=True):
                        self.table.removeColumn(col_index)
                        self.scheme.removeRow(col_index)
                        if col_index < len(self.columns):
                            del self.columns[col_index]
                        for row_data in self.rows:
                            if col_index < len(row_data):
                                del row_data[col_index]
        else:
            super().keyPressEvent(event)

    def go_back(self):
        self.stacked.setCurrentIndex(0)