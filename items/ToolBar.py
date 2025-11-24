from PyQt6.QtWidgets import (
    QHBoxLayout, 
    QPushButton,
    QFrame
)

class Toolbar(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.setStyleSheet("background-color: #eeeff1; border-bottom: 1px solid #E0E0E0;")
        toolbar_layout = QHBoxLayout(self)
        toolbar_layout.setContentsMargins(12, 0, 12, 0)
        toolbar_layout.addWidget(QPushButton("New"))
        toolbar_layout.addWidget(QPushButton("Open"))
        toolbar_layout.addWidget(QPushButton("Save"))
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(QPushButton("Run Query"))