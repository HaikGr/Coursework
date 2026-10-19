from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout


class RenameDialog(QDialog):
    """Dark themed one-line input."""

    def __init__(self, parent, title, prompt, current):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(350, 150)
        # QLabel sets its own background: the dialog inherits the style sheet of the page it opens over
        self.setStyleSheet("""
            QDialog { background-color: #1f2937; }
            QLabel { color: #f3f4f6; font-size: 14px; background: transparent; }
            QLineEdit {
                background-color: #374151;
                color: #f3f4f6;
                border: 2px solid #4b5563;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
                selection-background-color: #3777f0;
                selection-color: #FFFFFF;
            }
            QLineEdit:focus { border: 2px solid #3777f0; }
            QPushButton {
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                min-width: 80px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        layout.addWidget(QLabel(prompt))

        self.line_edit = QLineEdit(current)
        self.line_edit.selectAll()
        self.line_edit.returnPressed.connect(self.accept)
        layout.addWidget(self.line_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("QPushButton { background-color: #4b5563; color: white; } "
                                 "QPushButton:hover { background-color: #6b7280; }")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Rename")
        ok_btn.setDefault(True)
        ok_btn.setStyleSheet("QPushButton { background-color: #3777f0; color: white; } "
                             "QPushButton:hover { background-color: #2563eb; }")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)


def ask_new_name(parent, title, prompt, current):
    """Returns the trimmed text, or None when cancelled."""
    dialog = RenameDialog(parent, title, prompt, current)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.line_edit.text().strip()
