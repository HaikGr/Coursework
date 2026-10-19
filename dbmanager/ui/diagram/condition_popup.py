from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


class ConditionPopup(QWidget):
    """Fast floating popup for WHERE conditions"""
    condition_submitted = pyqtSignal(str, str, str)  # table_name, field_name, condition

    def __init__(self, parent, table_name, field_name):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.table_name = table_name
        self.field_name = field_name
        self.setFixedSize(250, 120)

        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                border: 2px solid #22c55e;
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Title
        title = QLabel(f"{table_name}.{field_name}")
        title.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600; border: none; background: transparent;")
        layout.addWidget(title)

        # Input field
        self.input = QLineEdit()
        self.input.setPlaceholderText(">100")
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                border: 2px solid #22c55e;
                border-radius: 6px;
                padding: 6px 10px;
                color: #22c55e;
                font-size: 14px;
                font-weight: 600;
            }
            QLineEdit:focus {
                border: 2px solid #4ade80;
                background-color: #0f172a;
            }
        """)
        self.input.returnPressed.connect(self._on_enter)
        layout.addWidget(self.input)

        # Hint
        hint = QLabel("Press Enter to add condition")
        hint.setStyleSheet("color: #475569; font-size: 9px; border: none; background: transparent;")
        layout.addWidget(hint)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Fast hide timer
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._do_hide)

        self.mouse_inside = False

    def _on_enter(self):
        condition = self.input.text().strip()
        if condition:
            self.condition_submitted.emit(self.table_name, self.field_name, condition)
            self.input.clear()
            self.hide()

    def showAt(self, global_pos):
        """Show popup instantly at position"""
        self.move(global_pos)
        self.show()
        self.raise_()
        self.input.setFocus()
        self.input.selectAll()

    def enterEvent(self, event):
        self.mouse_inside = True
        self.hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.mouse_inside = False
        self.hide_timer.start(150)  # Fast hide - 150ms
        super().leaveEvent(event)

    def _do_hide(self):
        if not self.mouse_inside:
            self.hide()

    def scheduleHide(self):
        """Called when mouse leaves the field row"""
        if not self.mouse_inside:
            self.hide_timer.start(200)
