import os
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDialog, 
    QPushButton, QComboBox, QCheckBox
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt


def get_app_icon():
    """Get the application icon path"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "icon", "sql_query_builder_icon.svg")


class InputFieldsWindow(QDialog):
    def __init__(self, types_list=None, table_names=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Field")
        self.setWindowIcon(QIcon(get_app_icon()))
        self.setFixedSize(360, 600)
        self.setModal(True)
        self.return_data = None

        if types_list is None:
            types_list = [
                "int", "bigint", "smallint", "tinyint",
                "decimal", "numeric", "money", "smallmoney",
                "float", "real",
                "char", "varchar", "nchar", "nvarchar", "text", "ntext",
                "date", "datetime", "datetime2", "time", "timestamp",
                "bit", "binary", "varbinary", "image",
                "uniqueidentifier"
            ]

        self.table_schemas = {} 

        self.setStyleSheet("""
            QDialog {
                background-color: #1e293b;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 14px;
                font-weight: 500;
            }
            QLineEdit {
                background-color: #334155;
                color: #f1f5f9;
                border: 2px solid #475569;
                border-radius: 8px;
                padding: 12px 14px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
            }
            QComboBox {
                background-color: #334155;
                color: #f1f5f9;
                border: 2px solid #475569;
                border-radius: 8px;
                padding: 12px 14px;
                font-size: 14px;
            }
            QComboBox:focus {
                border: 2px solid #3b82f6;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #94a3b8;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #334155;
                color: #f1f5f9;
                selection-background-color: #3b82f6;
                border: 1px solid #475569;
            }
            QCheckBox {
                color: #e2e8f0;
                font-size: 14px;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 22px;
                height: 22px;
                border-radius: 6px;
                border: 2px solid #475569;
                background-color: #334155;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border: 2px solid #3b82f6;
            }
            QCheckBox:disabled {
                color: #64748b;
            }
            QCheckBox::indicator:disabled {
                background-color: #1e293b;
                border: 2px solid #334155;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QLabel("Add New Field")
        header.setStyleSheet("font-size: 22px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(header)

        # Field Name
        name_label = QLabel("Field Name")
        layout.addWidget(name_label)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter field name")
        layout.addWidget(self.input_field)

        # Data Type row
        type_row = QHBoxLayout()
        type_row.setSpacing(12)
        
        type_col = QVBoxLayout()
        type_label = QLabel("Data Type")
        type_col.addWidget(type_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems(types_list)
        type_col.addWidget(self.type_combo)
        type_row.addLayout(type_col)
        
        layout.addLayout(type_row)

        # Checkboxes in a row
        check_row = QHBoxLayout()
        check_row.setSpacing(20)
        
        self.null_checkbox = QCheckBox("Nullable")
        self.null_checkbox.setChecked(True)
        check_row.addWidget(self.null_checkbox)
        
        self.auto_checkbox = QCheckBox("Auto Inc")
        self.auto_checkbox.stateChanged.connect(self._on_auto_changed)
        check_row.addWidget(self.auto_checkbox)
        
        check_row.addStretch()
        layout.addLayout(check_row)

        # Key checkboxes
        key_row = QHBoxLayout()
        key_row.setSpacing(20)
        
        self.pk_checkbox = QCheckBox("Primary Key")
        self.pk_checkbox.stateChanged.connect(self._on_pk_changed)
        key_row.addWidget(self.pk_checkbox)
        
        self.fk_checkbox = QCheckBox("Foreign Key")
        self.fk_checkbox.stateChanged.connect(self._on_fk_changed)
        key_row.addWidget(self.fk_checkbox)
        
        key_row.addStretch()
        layout.addLayout(key_row)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(44)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #475569;
                color: #e2e8f0;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 24px;
            }
            QPushButton:hover {
                background-color: #64748b;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        add_btn = QPushButton("Add Field")
        add_btn.setFixedHeight(44)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 24px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        add_btn.clicked.connect(self.accept)
        
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(add_btn)
        layout.addLayout(btn_row)

    def _on_auto_changed(self):
        if self.auto_checkbox.isChecked():
            self.null_checkbox.setChecked(False)
            self.null_checkbox.setEnabled(False)
            self.type_combo.setCurrentText("int")
        else:
            if not self.pk_checkbox.isChecked():
                self.null_checkbox.setEnabled(True)

    def _on_pk_changed(self):
        if self.pk_checkbox.isChecked():
            self.fk_checkbox.setChecked(False)
            self.fk_checkbox.setEnabled(False)
            self.null_checkbox.setChecked(False)
            self.null_checkbox.setEnabled(False)
        else:
            self.fk_checkbox.setEnabled(True)
            if not self.auto_checkbox.isChecked():
                self.null_checkbox.setEnabled(True)

    def _on_fk_changed(self):
        if self.fk_checkbox.isChecked():
            self.pk_checkbox.setChecked(False)
            self.pk_checkbox.setEnabled(False)
        else:
            self.pk_checkbox.setEnabled(True)

    def accept(self):
        field_name = self.input_field.text().strip()
        if not field_name:
            self.input_field.setFocus()
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #334155;
                    color: #f1f5f9;
                    border: 2px solid #ef4444;
                    border-radius: 8px;
                    padding: 12px 14px;
                    font-size: 14px;
                }
            """)
            return

        type_value = self.type_combo.currentText()

        isnull_value = "Null" if self.null_checkbox.isChecked() else "Not Null"

        if self.pk_checkbox.isChecked():
            pk_flag = "PK"
        elif self.fk_checkbox.isChecked():
            pk_flag = "FK"
        else:
            pk_flag = "-"

        self.return_data = [field_name, type_value, isnull_value, pk_flag, "-", "-"]
        super().accept()

    def get_data(self):
        return self.return_data

    def get_full_data(self):
        return self.return_data
