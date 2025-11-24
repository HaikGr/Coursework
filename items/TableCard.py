from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import (
    Qt, QPoint, pyqtSignal)
from PyQt6.QtGui import QColor, QPainter, QPixmap

from items.FieldRow import FieldRow # Assuming FieldRow is available

class TableCard(QFrame):
    moved = pyqtSignal()
    
    def __init__(self, table_name, fields, parent=None):
        # 1. Initialize with parent
        super().__init__(parent) 
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
        # 2. Store layout as instance member for easy clearing
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(8)
        
        # Initial UI build
        self._build_ui()

    def _clear_layout(self, layout):
        """Helper to remove all items from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
                item.layout().deleteLater()
        self.field_rows = [] # Clear field row references


    def _build_ui(self):
        """Rebuilds the UI based on self.fields."""
        # 1. Clear existing content
        self._clear_layout(self.main_layout) 

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
        self.main_layout.addLayout(header)

        # fields
        for f in self.fields:
            row = FieldRow(self, f)
            # row styling container to look like pill
            pill = QFrame()
            pill_layout = QVBoxLayout(pill)
            pill_layout.setContentsMargins(0, 0, 0, 0)
            pill_layout.addWidget(row)
            pill.setStyleSheet("background-color: #3A424F; border-radius: 8px;")
            self.main_layout.addWidget(pill)
            # keep reference to the actual row for geometry computations
            self.field_rows.append(row)

        self.main_layout.addStretch()

        # right-side small arrow drawn as label
        # We must re-add this component every time _build_ui is called
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
        # Position the arrow relative to the card size
        arrow.move(self.width() - 28, self.height() // 2 - 10)
        arrow.show()
        
    def update_fields(self, new_fields):
        """Public method to update the card's fields and refresh the UI."""
        self.fields = new_fields
        self._build_ui()
        self.moved.emit() # Notify system that content changed
        # Recalculate size hints if necessary after content change
        self.updateGeometry()


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