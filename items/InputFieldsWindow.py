from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QDialog, QDialogButtonBox, QComboBox
)



class InputFieldsWindow(QDialog):
    def __init__(self, types_list=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Input Dialog")
        self.setFixedSize(300,160)
        self.return_data = None
        if types_list is None:
            types_list = ["Int", "Money", "String"]
        self.name_label = QLabel("Field_Name")
        self.input_field = QLineEdit()
        self.type_label = QLabel("Type:")
        self.type_combo = QComboBox()
        self.type_combo.addItems(types_list)
        self.null_label = QLabel("IsNull:")
        self.null_combo = QComboBox()
        self.null_combo.addItems(["Null", "Not Null"])
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.name_label)
        layout.addWidget(self.input_field)
        hlayout1 = QHBoxLayout()
        hlayout1.addWidget(self.type_label)
        hlayout1.addWidget(self.type_combo)
        layout.addLayout(hlayout1)
        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(self.null_label)
        hlayout2.addWidget(self.null_combo)
        layout.addLayout(hlayout2)
        layout.addWidget(self.buttons)

    def accept(self):
        field_name = self.input_field.text().strip()
        type_value = self.type_combo.currentText()
        isnull_value = self.null_combo.currentText()
        if not field_name:
            return
        self.return_data = [field_name, type_value, isnull_value]
        super().accept()

    def get_data(self):
        return self.return_data