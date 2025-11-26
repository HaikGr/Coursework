from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel,
    QLineEdit, QDialog, QDialogButtonBox
)

class InputTableNameWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Table Creation")
        self.setFixedSize(300,160)
        self.return_data = None
        self.name_label = QLabel("Table Name")
        self.input_field = QLineEdit()

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.name_label)
        layout.addWidget(self.input_field)
        layout.addWidget(self.buttons)

    def accept(self):
        table_name = self.input_field.text().strip()
        if not table_name:
            return
        self.return_data = table_name
        super().accept()

    def get_data(self):
        return self.return_data