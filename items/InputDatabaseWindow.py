from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QDialog, QPushButton
)
from PyQt6.QtCore import Qt


class InputDatabaseWindow(QDialog):
    """Dark themed dialog for creating/renaming databases"""
    
    def __init__(self, parent=None, title="New Database", default_name="", button_text="Create"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(380, 220)
        self.return_data = None
        
        # Remove window frame for cleaner look
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        # Dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #1e293b;
                border: 2px solid #0ea5e9;
                border-radius: 16px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        
        # Header
        header = QLabel(f"{title}")
        header.setStyleSheet("""
            color: #f1f5f9;
            font-size: 20px;
            font-weight: bold;
            background: transparent;
        """)
        layout.addWidget(header)
        
        # Label
        label = QLabel("Database Name")
        label.setStyleSheet("""
            color: #94a3b8;
            font-size: 12px;
            font-weight: 600;
            background: transparent;
        """)
        layout.addWidget(label)
        
        # Input field
        self.input_field = QLineEdit()
        self.input_field.setText(default_name)
        self.input_field.setPlaceholderText("Enter database name...")
        self.input_field.setFixedHeight(48)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #0f172a;
                border: 2px solid #334155;
                border-radius: 10px;
                padding: 12px 16px;
                font-size: 15px;
                color: #f1f5f9;
            }
            QLineEdit:focus {
                border: 2px solid #0ea5e9;
            }
            QLineEdit::placeholder {
                color: #64748b;
            }
        """)
        self.input_field.returnPressed.connect(self.accept)
        self.input_field.selectAll()
        layout.addWidget(self.input_field)
        
        layout.addSpacing(8)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 42)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #94a3b8;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #475569;
                color: #f1f5f9;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        ok_btn = QPushButton(button_text)
        ok_btn.setFixedSize(140, 42)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #0ea5e9;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #38bdf8;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def accept(self):
        name = self.input_field.text().strip()
        if not name:
            return
        self.return_data = name
        super().accept()

    def get_data(self):
        return self.return_data

