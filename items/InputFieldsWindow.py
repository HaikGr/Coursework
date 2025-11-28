from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QDialog, QDialogButtonBox, QComboBox, QCheckBox
)


class InputFieldsWindow(QDialog):
    def __init__(self, types_list=None, table_names=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Field")
        self.setFixedSize(350, 250)
        self.return_data = None

        if types_list is None:
            types_list = ["Int", "Money", "String"]
        if table_names is None:
            table_names = []

        self.table_schemas = {}  # e.g., {"Users": ["id", "name"]}

        # Field Name
        self.name_label = QLabel("Field Name:")
        self.input_field = QLineEdit()

        # Type
        self.type_label = QLabel("Type:")
        self.type_combo = QComboBox()
        self.type_combo.addItems(types_list)

        # Nullability
        self.null_label = QLabel("Is Null:")
        self.null_combo = QComboBox()
        self.null_combo.addItems(["Null", "Not Null"])

        # PK / FK
        self.pk_checkbox = QCheckBox("Primary Key")
        self.fk_checkbox = QCheckBox("Foreign Key")
        self.fk_checkbox.stateChanged.connect(self.toggle_fk_options)

        self.fk_table_label = QLabel("Reference Table:")
        self.fk_table_combo = QComboBox()
        self.fk_table_combo.addItems(table_names)
        self.fk_field_label = QLabel("Reference Field:")
        self.fk_field_combo = QComboBox()
        self.fk_table_combo.currentIndexChanged.connect(self.load_fk_fields)

        self.fk_table_label.hide()
        self.fk_table_combo.hide()
        self.fk_field_label.hide()
        self.fk_field_combo.hide()

        # Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.name_label)
        layout.addWidget(self.input_field)

        hl1 = QHBoxLayout()
        hl1.addWidget(self.type_label)
        hl1.addWidget(self.type_combo)
        layout.addLayout(hl1)

        hl2 = QHBoxLayout()
        hl2.addWidget(self.null_label)
        hl2.addWidget(self.null_combo)
        layout.addLayout(hl2)

        layout.addWidget(self.pk_checkbox)
        layout.addWidget(self.fk_checkbox)
        layout.addWidget(self.fk_table_label)
        layout.addWidget(self.fk_table_combo)
        layout.addWidget(self.fk_field_label)
        layout.addWidget(self.fk_field_combo)
        layout.addWidget(self.buttons)

    def toggle_fk_options(self):
        show = self.fk_checkbox.isChecked()
        self.fk_table_label.setVisible(show)
        self.fk_table_combo.setVisible(show)
        self.fk_field_label.setVisible(show)
        self.fk_field_combo.setVisible(show)
        if show:
            self.pk_checkbox.setChecked(False)

    def load_fk_fields(self):
        table = self.fk_table_combo.currentText()
        self.fk_field_combo.clear()
        if table in self.table_schemas:
            self.fk_field_combo.addItems(self.table_schemas[table])

    def accept(self):
        field_name = self.input_field.text().strip()
        if not field_name:
            return

        type_value = self.type_combo.currentText()
        isnull_value = self.null_combo.currentText()

        if self.pk_checkbox.isChecked():
            pk_flag = "PK"
            fk_table = "-"
            fk_field = "-"
        elif self.fk_checkbox.isChecked():
            pk_flag = "FK"
            fk_table = self.fk_table_combo.currentText()
            fk_field = self.fk_field_combo.currentText()
        else:
            pk_flag = "-"
            fk_table = "-"
            fk_field = "-"

        self.return_data = [field_name, type_value, isnull_value, pk_flag, fk_table, fk_field]
        super().accept()

    def get_data(self):
        return self.return_data
