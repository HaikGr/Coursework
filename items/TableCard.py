from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from items.FieldRow import FieldRow


class TableCard(QFrame):
    moved = pyqtSignal()

    def __init__(self, table_name, fields, parent=None):
        super().__init__(parent)

        self.table_name = table_name
        self.fields = fields
        self.drag_pos = None

        self.setFixedSize(240, 260)   # slightly taller to allow scroll
        self.setStyleSheet("""
            QFrame {
                background-color: #2E3641;
                border-radius: 10px;
                border: 1px solid #4A4F55;
            }
            QLabel { color: white; font-size: 14px; }
        """)

        # MAIN LAYOUT
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 12, 0, 15)
        self.main_layout.setSpacing(6)

        # Build UI
        self._build_header()
        self._build_scroll_area()
        self.load_fields()

    # -------------------------
    # HEADER
    # -------------------------
    def _build_header(self):
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

        # right-side arrow
        self.arrow = QLabel(self)
        arrow_pix = QPixmap(22, 22)
        arrow_pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(arrow_pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#A6B0BD"))
        p.drawPolygon(QPoint(5, 5), QPoint(17, 11), QPoint(5, 17))
        p.end()
        self.arrow.setPixmap(arrow_pix)
        self.arrow.move(self.width() - 28, self.height() // 2 - 10)
        self.arrow.show()

    # -------------------------
    # SCROLL AREA + FIELD CONTAINER
    # -------------------------
    def _build_scroll_area(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("border: none; background-color: #485262;")

        # content widget inside scroll
        self.content_widget = QWidget()
        self.fields_layout = QVBoxLayout(self.content_widget)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(5)

        self.scroll.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll)
        

    # -------------------------
    # LOAD / RELOAD FIELDS
    # -------------------------
    def load_fields(self):
        # remove old rows
        while self.fields_layout.count():
            item = self.fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.field_rows = []  

        # add rows
        for f in self.fields:
            row = FieldRow(self, f)

            pill = QFrame()
            pill.setStyleSheet("background-color: #576476; border-radius: 8px;")
            p_layout = QVBoxLayout(pill)
            p_layout.setContentsMargins(4, 3, 4, 3)
            p_layout.addWidget(row)

            self.fields_layout.addWidget(pill)

        self.fields_layout.addStretch()

    # -------------------------
    # FIELD UPDATE
    # -------------------------
    def update_fields(self, new_fields):
        self.fields = new_fields
        self.load_fields()
        self.moved.emit()

    # -------------------------
    # DRAGGING
    # -------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()
            self.raise_()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            self.move(int(new_pos.x()), int(new_pos.y()))
            self.moved.emit()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        super().mouseReleaseEvent(event)
