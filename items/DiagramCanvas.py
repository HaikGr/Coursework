from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, QPoint, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath
import math

class DiagramCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connections = []  # [(pk_card, pk_field, fk_card, fk_field, relation_type)]
        self.cards = []
        self.selected_field = None
        self.drag_preview = None
        self.setMouseTracking(True)
        
        self.setStyleSheet("background-color: #1A1F2E;")

    def add_card(self, card):
        card.canvas = self
        self.cards.append(card)
        card.moved.connect(self.update)

        # Connect all field rows for potential connections
        all_rows = []
        if hasattr(card, 'pk_rows'):
            all_rows.extend(card.pk_rows)
        if hasattr(card, 'fk_rows'):
            all_rows.extend(card.fk_rows)
        if hasattr(card, 'main_rows'):
            all_rows.extend(card.main_rows)
        
        for row in all_rows:
            row.clicked.connect(self.on_field_clicked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw saved connections with arrows
        for pk_card, pk_field, fk_card, fk_field, relation_type in self.connections:
            start = self.get_field_center(pk_field, left=False)
            end = self.get_field_center(fk_field, left=True)
            self.draw_connection_arrow(painter, start, end, QColor("#69a7ff"), relation_type)

        # Draw drag-preview line
        if self.drag_preview:
            pen = QPen(QColor("#FFD57F"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            start, end = self.drag_preview
            painter.drawLine(QPoint(*start), QPoint(int(end[0]), int(end[1])))
            
            # Draw small circle at cursor
            painter.setBrush(QColor("#FFD57F"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(end[0], end[1]), 4, 4)

    def draw_connection_arrow(self, painter, start, end, color, relation_type="one-to-many"):
        """Draw a database-style connection arrow with crow's foot notation"""
        painter.setPen(QPen(color, 2))
        
        start_point = QPointF(start[0], start[1])
        end_point = QPointF(end[0], end[1])
        
        # Calculate control points for curved line
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        
        # Create bezier curve for smoother connections
        path = QPainterPath(start_point)
        
        # Control points for smooth curve
        ctrl1_x = start_point.x() + dx * 0.3
        ctrl2_x = end_point.x() - dx * 0.3
        
        path.cubicTo(
            ctrl1_x, start_point.y(),
            ctrl2_x, end_point.y(),
            end_point.x(), end_point.y()
        )
        
        painter.drawPath(path)
        
        # Draw "one" indicator at start (circle)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(start_point, 4, 4)
        
        # Draw "many" indicator at end (crow's foot)
        self.draw_crows_foot(painter, end_point, start_point, color)

    def draw_crows_foot(self, painter, end_point, start_point, color):
        """Draw crow's foot notation at the end of the line"""
        painter.setPen(QPen(color, 2))
        
        # Calculate angle
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        angle = math.atan2(dy, dx)
        
        # Crow's foot size
        foot_length = 12
        foot_width = 8
        
        # Calculate the three lines of the crow's foot
        base_angle1 = angle + math.pi / 6
        base_angle2 = angle - math.pi / 6
        
        # Top line
        top_end = QPointF(
            end_point.x() - foot_length * math.cos(base_angle1),
            end_point.y() - foot_length * math.sin(base_angle1)
        )
        painter.drawLine(end_point, top_end)
        
        # Bottom line
        bottom_end = QPointF(
            end_point.x() - foot_length * math.cos(base_angle2),
            end_point.y() - foot_length * math.sin(base_angle2)
        )
        painter.drawLine(end_point, bottom_end)
        
        # Middle line
        middle_end = QPointF(
            end_point.x() - foot_length * math.cos(angle),
            end_point.y() - foot_length * math.sin(angle)
        )
        painter.drawLine(end_point, middle_end)

    def get_field_center(self, field_row, left=False):
        """Get the center point of a field row for connection"""
        if not field_row or not field_row.isVisible():
            return (0, 0)
            
        w = field_row.width()
        h = field_row.height()
        pos = field_row.mapTo(self, field_row.rect().topLeft())
        x = pos.x() + (10 if left else w - 10)
        y = pos.y() + h // 2
        return (int(x), int(y))

    def on_field_clicked(self, field_row):
        """Handle field click for creating connections"""
        if self.selected_field is None:
            # Start connection
            self.selected_field = field_row
            field_row.set_connection_role(is_source=True)

            start = self.get_field_center(field_row, left=False)
            self.drag_preview = (start, start)
            self.update()
        else:
            # Complete connection
            if self.selected_field == field_row:
                # Clicked same field - cancel
                self.selected_field.set_connection_role(is_source=False)
                self.selected_field = None
                self.drag_preview = None
                self.update()
                return

            # Determine connection type based on field types
            source_type = self.selected_field.field_data[3] if len(self.selected_field.field_data) > 3 else ""
            target_type = field_row.field_data[3] if len(field_row.field_data) > 3 else ""

            # **Allow PK->FK only**
            if source_type == "PK" and target_type == "FK":
                relation = "one-to-many"

                # Add connection to list
                self.connections.append((
                    self.selected_field.table_card,
                    self.selected_field,
                    field_row.table_card,
                    field_row,
                    relation
                ))

                # Update visual indicators
                self.selected_field.set_connection_role(is_source=True)
                field_row.set_connection_role(is_target=True)

            # Reset selection
            self.selected_field.set_connection_role(is_source=False)
            self.selected_field = None
            self.drag_preview = None
            self.update()

    def mouseMoveEvent(self, event):
        """Update drag preview line while dragging"""
        if self.selected_field and self.drag_preview:
            start = self.drag_preview[0]
            end = (event.position().x(), event.position().y())
            self.drag_preview = (start, (int(end[0]), int(end[1])))
            self.update()
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        """Cancel connection on Escape key"""
        if event.key() == Qt.Key.Key_Escape and self.selected_field:
            self.selected_field.set_connection_role(is_source=False)
            self.selected_field = None
            self.drag_preview = None
            self.update()
        super().keyPressEvent(event)

    def remove_card(self, card):
        """Remove a TableCard and its connections"""
        if card in self.cards:
            self.cards.remove(card)
        
        # Clear connection roles
        for pk_card, pk_field, fk_card, fk_field, _ in self.connections:
            if pk_card == card or fk_card == card:
                if pk_card == card:
                    pk_field.set_connection_role(is_source=False)
                if fk_card == card:
                    fk_field.set_connection_role(is_target=False)
        
        # Remove connections
        self.connections = [
            conn for conn in self.connections
            if conn[0] != card and conn[2] != card
        ]
        self.update()

    def remove_connection(self, connection):
        """Remove a specific connection"""
        if connection in self.connections:
            pk_card, pk_field, fk_card, fk_field, _ = connection
            
            # Check if field is still used in other connections
            pk_used = any(c[1] == pk_field for c in self.connections if c != connection)
            fk_used = any(c[3] == fk_field for c in self.connections if c != connection)
            
            if not pk_used:
                pk_field.set_connection_role(is_source=False)
            if not fk_used:
                fk_field.set_connection_role(is_target=False)
            
            self.connections.remove(connection)
            self.update()

    def clear_all_connections(self):
        """Clear all connections"""
        for pk_card, pk_field, fk_card, fk_field, _ in self.connections:
            pk_field.set_connection_role(is_source=False)
            fk_field.set_connection_role(is_target=False)
        
        self.connections.clear()
        self.update()