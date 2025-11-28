from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor

class DiagramCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connections = []  # PK->FK
        self.cards = []
        self.selected_field = None
        self.drag_preview = None  # (start_pos, current_pos)

    def add_card(self, card):
        card.canvas = self
        self.cards.append(card)
        card.moved.connect(self.update)

        for row in card.pk_rows:
            row.clicked.connect(self.on_field_clicked)
        for row in card.fk_rows:
            row.clicked.connect(self.on_field_clicked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw saved connections (solid blue)
        pen = QPen(QColor("#69a7ff"))
        pen.setWidth(3)
        painter.setPen(pen)
        for pk_card, pk_field, fk_card, fk_field in self.connections:
            start = self.get_field_center(pk_field, left=False)
            end = self.get_field_center(fk_field, left=True)
            painter.drawLine(QPoint(*start), QPoint(*end))

        # Draw drag-preview line (dashed orange)
        if self.drag_preview:
            pen = QPen(QColor("#FFD57F"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            start, end = self.drag_preview
            painter.drawLine(QPoint(*start), QPoint(int(end[0]), int(end[1])))

    def get_field_center(self, field_row, left=False):
        w = field_row.width()
        h = field_row.height()
        pos = field_row.mapTo(self, field_row.rect().topLeft())
        x = pos.x() + (0 if left else w)
        y = pos.y() + h // 2
        return (int(x), int(y))  # ensure integers

    def on_field_clicked(self, field_row):
        if self.selected_field is None:
            self.selected_field = field_row
            self.drag_preview = (self.get_field_center(field_row, left=False),
                                 self.get_field_center(field_row, left=False))
            self.update()
        else:
            # Only allow PK->FK connection
            if field_row in field_row.table_card.fk_rows:
                self.connections.append((self.selected_field.table_card, self.selected_field,
                                         field_row.table_card, field_row))
            self.selected_field = None
            self.drag_preview = None
            self.update()

    def mouseMoveEvent(self, event):
        if self.selected_field:
            start = self.get_field_center(self.selected_field, left=False)
            end = (event.position().x(), event.position().y())
            self.drag_preview = (start, (int(end[0]), int(end[1])))
            self.update()
        super().mouseMoveEvent(event)

    def remove_card(self, card):
        """Remove a TableCard from the canvas."""
        if card in self.cards:
            self.cards.remove(card)
        # Remove any connections that involve this card
        self.connections = [
            (pk_card, pk_field, fk_card, fk_field)
            for pk_card, pk_field, fk_card, fk_field in self.connections
            if pk_card != card and fk_card != card
        ]
        self.update()