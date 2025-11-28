from PyQt6.QtWidgets import QFrame, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

class FieldRow(QFrame):
    clicked = pyqtSignal(object)  # emits self

    def __init__(self, table_card, field_data):
        super().__init__(table_card)
        self.table_card = table_card
        self.field_data = field_data  # ['field_name', 'type', 'nullable', 'PK/FK', 'FK table', 'FK field']

        self.setFixedHeight(28)
        self.setStyleSheet("""
            QFrame { background-color: transparent; border-radius: 4px; }
            QLabel { color: #E0E0E0; padding-left: 8px; font-size: 13px; }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)

        field_name = field_data[0]
        self.label = QLabel(field_name)
        layout.addWidget(self.label)
        layout.addStretch()

        # hover tracking
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)
