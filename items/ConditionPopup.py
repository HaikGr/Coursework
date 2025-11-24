from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit
)
from PyQt6.QtCore import (
    Qt
)

class ConditionPopup(QWidget):
    """Floating condition input like your second screenshot"""
    def __init__(self, parent, table_name, field_name):
        super().__init__(parent)
        self.setFixedSize(260, 72)
        self.setStyleSheet("""
            QWidget {
                background-color: #101827;
                border: 1px solid #2E3A4A;
                border-radius: 10px;
            }
            QLineEdit {
                background-color: #0D121A;
                border: 1px solid #3B4757;
                border-radius: 6px;
                padding: 6px;
                color: white;
                font-size: 14px;
            }
            QLabel {
                color: #7C8A99;
                font-size: 12px;
                padding-left: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        title = QLabel(f"{table_name}.{field_name}")
        title.setStyleSheet("color: #9FB6D7; font-size: 12px;")
        self.input = QLineEdit()
        self.input.setPlaceholderText("e.g. >100   (Press Enter to add)")

        layout.addWidget(title)
        layout.addWidget(self.input)

        # allow hover detection
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def enterEvent(self, event):
        # keep visible; optional callback if set
        if hasattr(self, "entered_callback"):
            try:
                self.entered_callback()
            except Exception:
                pass
        return super().enterEvent(event)

    def leaveEvent(self, event):
        if hasattr(self, "left_callback"):
            try:
                self.left_callback()
            except Exception:
                pass
        return super().leaveEvent(event)