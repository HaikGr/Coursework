from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from dbmanager.ui.common.icons import app_icon


class InputTableNameWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Table")
        self.setWindowIcon(app_icon())
        self.setFixedSize(350, 210)
        self.return_data = None
        
        # Dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("Create New Table")
        header.setStyleSheet("""
            color: #f1f5f9;
            font-size: 18px;
            font-weight: bold;
            background: transparent;
        """)
        layout.addWidget(header)
        
        # Label
        self.name_label = QLabel("Table Name")
        self.name_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 12px;
            font-weight: 600;
            background: transparent;
        """)
        layout.addWidget(self.name_label)
        
        # Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter table name...")
        self.input_field.setFixedHeight(44)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #0f172a;
                border: 2px solid #334155;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 14px;
                color: #f1f5f9;
            }
            QLineEdit:focus {
                border: 2px solid #0ea5e9;
            }
        """)
        self.input_field.returnPressed.connect(self.accept)
        layout.addWidget(self.input_field)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #94a3b8;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #475569;
                color: #f1f5f9;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        ok_btn = QPushButton("Create Table")
        ok_btn.setFixedHeight(40)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #0ea5e9;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 20px;
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
        table_name = self.input_field.text().strip()
        if not table_name:
            return
        self.return_data = table_name
        super().accept()

    def get_data(self):
        return self.return_data
