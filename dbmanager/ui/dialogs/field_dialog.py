from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from dbmanager.i18n import tr, trn
from dbmanager.sql.generator import is_integer_type, is_numeric_type, looks_like_number
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.dark_dialog import settle_enter_key
from dbmanager.ui.common.style import COMBO_ARROW
from dbmanager.ui.common.theme import qss

# A theme.qss template once formatted with the border colours (tokens)
NAME_INPUT_STYLE = """
    QLineEdit {{
        background-color: @sunken;
        color: @text;
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
        self.setWindowTitle(tr("dialogs.field.add"))
        self.setWindowIcon(app_icon())
        # Wider than 380 only when a translation needs it (the key check boxes share a row)
        self.setFixedHeight(660)
        self.setMinimumWidth(380)
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

        self.setStyleSheet(qss(COMBO_ARROW + """
            QDialog {
                background-color: @surface;
            }
            QLabel {
                color: @text;
                font-size: 14px;
                font-weight: 500;
                background: transparent;
            }
            QLineEdit {
                background-color: @sunken;
                color: @text;
                border: 2px solid @border_strong;
                border-radius: 8px;
                padding: 12px 14px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid @focus;
            }
            QComboBox {
                background-color: @sunken;
                color: @text;
                border: 2px solid @border_strong;
                border-radius: 8px;
                padding: 12px 14px;
                font-size: 14px;
            }
            QComboBox:focus {
                border: 2px solid @focus;
            }
            QComboBox QAbstractItemView {
                background-color: @sunken;
                color: @text;
                selection-background-color: @selection;
                selection-color: @on_selection;
                border: 1px solid @border_strong;
            }
            QCheckBox {
                color: @text;
                font-size: 14px;
                spacing: 10px;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 22px;
                height: 22px;
                border-radius: 6px;
                border: 2px solid @border_strong;
                background-color: @sunken;
            }
            QCheckBox::indicator:checked {
                background-color: @accent;
                border: 2px solid @accent;
            }
            QCheckBox:disabled {
                color: @text_disabled;
            }
            QCheckBox::indicator:disabled {
                background-color: @surface_alt;
                border: 2px solid @border;
            }
        """))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QLabel(tr("dialogs.field.heading"))
        header.setStyleSheet(qss("QLabel { font-size: 22px; font-weight: 700; color: @text; }"))
        layout.addWidget(header)

        # Field Name
        name_label = QLabel(tr("dialogs.field.name"))
        layout.addWidget(name_label)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(tr("dialogs.field.name_placeholder"))
        self.input_field.textChanged.connect(lambda: self._show_name_error(None))
        layout.addWidget(self.input_field)
        self.name_error = QLabel()
        self.name_error.setStyleSheet(qss("QLabel { color: @danger_text; font-size: 12px; }"))
        self.name_error.hide()
        layout.addWidget(self.name_error)

        # Data Type row
        type_row = QHBoxLayout()
        type_row.setSpacing(12)
        
        type_col = QVBoxLayout()
        type_label = QLabel(tr("dialogs.field.type"))
        type_col.addWidget(type_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems(types_list)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_col.addWidget(self.type_combo)
        type_row.addLayout(type_col)
        
        layout.addLayout(type_row)

        # Default value
        layout.addWidget(QLabel(tr("dialogs.field.default")))
        self.default_input = QLineEdit()
        self.default_input.setPlaceholderText(tr("dialogs.field.default_placeholder"))
        self.default_input.setToolTip(tr("dialogs.field.default_tip"))
        self.default_input.textChanged.connect(self._update_rows_note)
        layout.addWidget(self.default_input)

        # Checkboxes in a row
        check_row = QHBoxLayout()
        check_row.setSpacing(20)
        
        self.null_checkbox = QCheckBox(tr("dialogs.field.nullable"))
        self.null_checkbox.setChecked(True)
        check_row.addWidget(self.null_checkbox)
        
        self.auto_checkbox = QCheckBox(tr("dialogs.field.auto_increment"))
        self.auto_checkbox.stateChanged.connect(self._on_auto_changed)
        check_row.addWidget(self.auto_checkbox)
        
        check_row.addStretch()
        layout.addLayout(check_row)

        # Key checkboxes
        key_row = QHBoxLayout()
        key_row.setSpacing(20)
        
        self.pk_checkbox = QCheckBox(tr("dialogs.field.primary_key"))
        self.pk_checkbox.stateChanged.connect(self._on_pk_changed)
        key_row.addWidget(self.pk_checkbox)
        
        self.fk_checkbox = QCheckBox(tr("dialogs.field.foreign_key"))
        self.fk_checkbox.stateChanged.connect(self._on_fk_changed)
        key_row.addWidget(self.fk_checkbox)
        
        key_row.addStretch()
        layout.addLayout(key_row)

        # What the rows already in the table get - the reason a NOT NULL field may be refused
        self.rows_note = QLabel()
        self.rows_note.setWordWrap(True)
        self.rows_note.setStyleSheet(qss("QLabel { color: @warning_text; font-size: 12px; font-weight: 400; "
                                         "background: transparent; }"))
        layout.addWidget(self.rows_note)
        self.null_checkbox.stateChanged.connect(self._update_rows_note)
        self.type_combo.currentTextChanged.connect(self._update_rows_note)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        
        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setFixedHeight(44)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(qss("""
            QPushButton {
                background-color: @surface_raised;
                color: @text;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 24px;
            }
            QPushButton:hover {
                background-color: @surface_pressed;
            }
        """))
        cancel_btn.clicked.connect(self.reject)
        
        add_btn = QPushButton(tr("dialogs.field.add"))
        add_btn.setFixedHeight(44)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(qss("""
            QPushButton {
                background-color: @accent;
                color: @on_accent;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 24px;
            }
            QPushButton:hover {
                background-color: @accent_hover;
            }
        """))
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
            note = tr("dialogs.field.rows_get_default")
        elif required:
            note = tr("dialogs.field.rows_need_value") if rows is None else \
                trn("dialogs.field.rows_need_value_count", rows)
        else:
            note = tr("dialogs.field.rows_get_null")
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
            self.input_field.setStyleSheet(qss(NAME_INPUT_STYLE.format(border="@danger", focus="@danger")))
            self.input_field.setFocus()
        else:
            self.input_field.setStyleSheet(qss(NAME_INPUT_STYLE.format(border="@border_strong", focus="@focus")))
        self.name_error.setVisible(bool(message))

    def accept(self):
        field_name = self.input_field.text().strip()
        if not field_name:
            self._show_name_error(tr("dialogs.field.no_name"))
            return
        if field_name.lower() in self.existing_names:
            self._show_name_error(tr("dialogs.field.name_taken", name=field_name))
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
            self.rows_note.setText(tr("dialogs.field.default_not_number", type=type_value))
            self.rows_note.setVisible(True)
            return
        self.return_data = [field_name, type_value, isnull_value, pk_flag, "-", "-", auto_flag, default]
        super().accept()

    def get_data(self):
        return self.return_data
