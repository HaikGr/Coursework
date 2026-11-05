from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from dbmanager.sql.generator import is_integer_type, is_numeric_type, looks_like_number
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.dark_dialog import settle_enter_key
from dbmanager.ui.common.style import COMBO_ARROW

NAME_INPUT_STYLE = """
    QLineEdit {{
        background-color: #334155;
        color: #f1f5f9;
        border: 2px solid {border};
        border-radius: 8px;
        padding: 12px 14px;
        font-size: 14px;
    }}
    QLineEdit:focus {{
        border: 2px solid {focus};
    }}
"""


class InputFieldsWindow(QDialog):
    """Asks for one new column. get_data() returns
    [name, type, "Null"/"Not Null", "PK"/"FK"/"-", "-", "-", "AUTO"/"-", default value or None] once accepted.

    existing_rows: how many rows the table already has in the database (0 for a new table; None when it is
    not known) - they are what a NOT NULL field needs a value for."""

    def __init__(self, types_list=None, existing_names=(), parent=None, existing_rows=0):
        super().__init__(parent)
        self.setWindowTitle("Add Field")
        self.setWindowIcon(app_icon())
        self.setFixedSize(380, 660)
        self.setModal(True)
        self.return_data = None
        self.existing_names = {name.lower() for name in existing_names}
        self.existing_rows = existing_rows

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

        self.setStyleSheet(COMBO_ARROW + """
            QDialog {
                background-color: #1e293b;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 14px;
                font-weight: 500;
                background: transparent;
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
                background: transparent;
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
        header.setStyleSheet("QLabel { font-size: 22px; font-weight: 700; color: #f8fafc; }")
        layout.addWidget(header)

        # Field Name
        name_label = QLabel("Field Name")
        layout.addWidget(name_label)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter field name")
        self.input_field.textChanged.connect(lambda: self._show_name_error(None))
        layout.addWidget(self.input_field)
        self.name_error = QLabel()
        self.name_error.setStyleSheet("QLabel { color: #f87171; font-size: 12px; }")
        self.name_error.hide()
        layout.addWidget(self.name_error)

        # Data Type row
        type_row = QHBoxLayout()
        type_row.setSpacing(12)
        
        type_col = QVBoxLayout()
        type_label = QLabel("Data Type")
        type_col.addWidget(type_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems(types_list)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_col.addWidget(self.type_combo)
        type_row.addLayout(type_col)
        
        layout.addLayout(type_row)

        # Default value
        layout.addWidget(QLabel("Default value"))
        self.default_input = QLineEdit()
        self.default_input.setPlaceholderText("none - optional")
        self.default_input.setToolTip("What a row gets when no value is given for this field - the rows already\n"
                                      "in the table too. Typed as it is, without quotes.")
        self.default_input.textChanged.connect(self._update_rows_note)
        layout.addWidget(self.default_input)

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

        # What the rows already in the table get - the reason a NOT NULL field may be refused
        self.rows_note = QLabel()
        self.rows_note.setWordWrap(True)
        self.rows_note.setStyleSheet("QLabel { color: #fbbf24; font-size: 12px; font-weight: 400; "
                                     "background: transparent; }")
        layout.addWidget(self.rows_note)
        self.null_checkbox.stateChanged.connect(self._update_rows_note)
        self.type_combo.currentTextChanged.connect(self._update_rows_note)

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
        settle_enter_key(self, default=add_btn)  # Enter adds the field (Cancel used to answer it)
        layout.addLayout(btn_row)
        self._update_rows_note()

    def _update_rows_note(self):
        """Say what the rows already there will hold - and what a NOT NULL field needs for them"""
        rows = self.existing_rows
        default = self.default_input.text().strip()
        required = not self.null_checkbox.isChecked() and not self.auto_checkbox.isChecked()
        if rows == 0:
            note = ""
        elif default:
            note = "The rows already in the table get the default value."
        elif required:
            count = "The rows already in the table" if rows is None else \
                f"The {rows} row{'s' if rows != 1 else ''} already in the table"
            note = (f"{count} need a value for a required field: give a default value, or type one in each "
                    "row before you run.")
        else:
            note = "The rows already in the table get no value (NULL)."
        self.rows_note.setText(note)
        self.rows_note.setVisible(bool(note))
    def _on_auto_changed(self):
        if self.auto_checkbox.isChecked():
            self.null_checkbox.setChecked(False)
            self.null_checkbox.setEnabled(False)
            self.type_combo.setCurrentText("int")
        else:
            if not self.pk_checkbox.isChecked():
                self.null_checkbox.setEnabled(True)

    def _on_type_changed(self, type_name):
        # Only whole numbers can count up by themselves
        if self.auto_checkbox.isChecked() and not is_integer_type(type_name):
            self.auto_checkbox.setChecked(False)

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

    def _show_name_error(self, message):
        if message:
            self.name_error.setText(message)
            self.input_field.setStyleSheet(NAME_INPUT_STYLE.format(border="#ef4444", focus="#ef4444"))
            self.input_field.setFocus()
        else:
            self.input_field.setStyleSheet(NAME_INPUT_STYLE.format(border="#475569", focus="#3b82f6"))
        self.name_error.setVisible(bool(message))

    def accept(self):
        field_name = self.input_field.text().strip()
        if not field_name:
            self._show_name_error("Enter a field name.")
            return
        if field_name.lower() in self.existing_names:
            self._show_name_error(f"This table already has a field named '{field_name}'.")
            return

        type_value = self.type_combo.currentText()

        isnull_value = "Null" if self.null_checkbox.isChecked() else "Not Null"

        if self.pk_checkbox.isChecked():
            pk_flag = "PK"
        elif self.fk_checkbox.isChecked():
            pk_flag = "FK"
        else:
            pk_flag = "-"

        auto_flag = "AUTO" if self.auto_checkbox.isChecked() else "-"
        default = self.default_input.text().strip() or None
        if default is not None and auto_flag == "AUTO":
            default = None  # the database numbers it
        if default is not None and is_numeric_type(type_value) and not looks_like_number(default):
            self.default_input.setFocus()
            self.rows_note.setText(f"The default must be a number for a {type_value} field.")
            self.rows_note.setVisible(True)
            return
        self.return_data = [field_name, type_value, isnull_value, pk_flag, "-", "-", auto_flag, default]
        super().accept()

    def get_data(self):
        return self.return_data
