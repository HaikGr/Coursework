from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from dbmanager.i18n import tr
from dbmanager.ui.common.dark_dialog import settle_enter_key
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.theme import qss


class InputTableNameWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialogs.table_name.title"))
        self.setWindowIcon(app_icon())
        self.setFixedSize(350, 210)
        self.return_data = None
        
        # Theme styling
        self.setStyleSheet(qss("""
            QDialog {
                background-color: @surface;
                border: 1px solid @border;
                border-radius: 12px;
            }
        """))
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        
        # Header
        header = QLabel(tr("dialogs.table_name.title"))
        header.setStyleSheet(qss("""
            QLabel {
                color: @text;
                font-size: 18px;
                font-weight: bold;
                background: transparent;
            }
        """))
        layout.addWidget(header)
        
        # Label
        self.name_label = QLabel(tr("dialogs.table_name.name"))
        self.name_label.setStyleSheet(qss("""
            QLabel {
                color: @text_secondary;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }
        """))
        layout.addWidget(self.name_label)
        
        # Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(tr("dialogs.table_name.placeholder"))
        self.input_field.setFixedHeight(44)
        self.input_field.setStyleSheet(qss("""
            QLineEdit {
                background-color: @sunken;
                border: 2px solid @border_strong;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 14px;
                color: @text;
            }
            QLineEdit:focus {
                border: 2px solid @focus;
            }
        """))
        self.input_field.returnPressed.connect(self.accept)
        layout.addWidget(self.input_field)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setFixedHeight(40)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(qss("""
            QPushButton {
                background-color: @surface_raised;
                color: @text_secondary;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: @surface_pressed;
                color: @text;
            }
        """))
        cancel_btn.clicked.connect(self.reject)
        
        ok_btn = QPushButton(tr("dialogs.table_name.create"))
        ok_btn.setFixedHeight(40)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet(qss("""
            QPushButton {
                background-color: @accent;
                color: @on_accent;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: @accent_hover;
            }
        """))
        ok_btn.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        settle_enter_key(self)  # Enter in the name field creates the table, nothing else
        layout.addLayout(btn_layout)

    def accept(self):
        table_name = self.input_field.text().strip()
        if not table_name:
            return
        self.return_data = table_name
        super().accept()

    def get_data(self):
        return self.return_data
