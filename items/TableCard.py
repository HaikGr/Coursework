from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import (
    Qt, QPoint, pyqtSignal)
from PyQt6.QtGui import QColor, QPainter, QPixmap

from items.FieldRow import FieldRow

class TableCard(QFrame):
    moved = pyqtSignal()
    def __init__(self, table_name, fields):
        super().__init__()
        self.table_name = table_name
        self.fields = fields
        self.drag_pos = None
        self.condition_popup = None
        self.canvas = None 

        self.setFixedSize(240, 240)
        self.setStyleSheet("""
            QFrame {
                background-color: #2E3641;
                border-radius: 10px;
                border: 1px solid #4A4F55;
            }
            QLabel { color: white; font-size: 14px; }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.setGraphicsEffect(shadow)

        self.field_rows = []
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel(self.table_name)
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet("background-color: #2ecc71; border-radius: 5px;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(dot)
        layout.addLayout(header)

        # fields
        for f in self.fields:
            row = FieldRow(self, f)
            # row styling container to look like pill
            pill = QFrame()
            pill_layout = QVBoxLayout(pill)
            pill_layout.setContentsMargins(0, 0, 0, 0)
            pill_layout.addWidget(row)
            pill.setStyleSheet("background-color: #3A424F; border-radius: 8px;")
            layout.addWidget(pill)
            # keep reference to the actual row for geometry computations
            self.field_rows.append(row)

        layout.addStretch()

        # right-side small arrow drawn as label
        arrow = QLabel(self)
        arrow_pix = QPixmap(22, 22)
        arrow_pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(arrow_pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor("#A6B0BD"))
        p.setBrush(QColor("#A6B0BD"))
        # triangle
        p.drawPolygon(
            QPoint(5, 5), QPoint(17, 11), QPoint(5, 17)
        )
        p.end()
        arrow.setPixmap(arrow_pix)
        arrow.move(self.width() - 28, self.height() // 2 - 10)
        arrow.show()

    # dragging behavior (emit moved)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()
            self.raise_()
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            # ensure integer coords
            self.move(int(new_pos.x()), int(new_pos.y()))
            # notify canvas to repaint connections
            self.moved.emit()
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        return super().mouseReleaseEvent(event)
