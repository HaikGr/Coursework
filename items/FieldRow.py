from PyQt6.QtWidgets import (
QHBoxLayout, QLabel, QFrame

)
from PyQt6.QtCore import (
    Qt, pyqtSignal
)


class FieldRow(QFrame):
    clicked = pyqtSignal(object)  # emits itself
    def __init__(self, table_card, field_name):
        super().__init__(table_card)
        self.table_card = table_card
        self.field_name = field_name
        self.setFixedHeight(36)
        self.setStyleSheet("""
            QFrame { background-color: transparent; border-radius: 6px; }
            QLabel { color: #E0E0E0; padding-left: 8px; font-size: 13px; }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        self.label = QLabel(field_name)
        layout.addWidget(self.label)
        layout.addStretch()

        # enable hover tracking
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        return super().mousePressEvent(event)

    def enterEvent(self, event):
        # show popup via canvas if available
        if hasattr(self.table_card, "canvas") and self.table_card.canvas:
            self.table_card.canvas.show_condition_popup(self)
        # optional callback integration
        if hasattr(self, "entered_callback"):
            try:
                self.entered_callback()
            except Exception:
                pass
        return super().enterEvent(event)

    def leaveEvent(self, event):
        # start a delayed hide check handled by canvas popup logic
        if hasattr(self, "left_callback"):
            try:
                self.left_callback()
            except Exception:
                pass
        return super().leaveEvent(event)