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
        """Add a card to the canvas and connect its field rows"""
        card.canvas = self
        self.cards.append(card)
        card.moved.connect(self.update)

        # Connect existing field rows
        self._connect_card_fields(card)

    def _connect_card_fields(self, card):
        """Connect all field rows in a card to the click handler"""
        all_rows = []
        if hasattr(card, 'pk_rows'):
            all_rows.extend(card.pk_rows)
        if hasattr(card, 'fk_rows'):
            all_rows.extend(card.fk_rows)
        if hasattr(card, 'main_rows'):
            all_rows.extend(card.main_rows)
        
        for row in all_rows:
            # Disconnect first to avoid duplicate connections
            try:
                row.clicked.disconnect(self.on_field_clicked)
            except:
                pass
            row.clicked.connect(self.on_field_clicked)

    def update_card_fields(self, card):
        """Re-connect field rows after card update"""
        self._connect_card_fields(card)

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

    def connection_exists(self, field1, field2):
        """Check if a connection already exists between two fields"""
        for _, pk_field, _, fk_field, _ in self.connections:
            if (pk_field == field1 and fk_field == field2) or \
               (pk_field == field2 and fk_field == field1):
                return True
        return False

    def on_field_clicked(self, field_row):
        """Handle field click for creating connections"""
        print(f"Field clicked: {field_row.field_data[0]} from table {field_row.table_card.table_name}")
        
        if self.selected_field is None:
            # Start connection
            self.selected_field = field_row
            field_row.set_connection_role(is_source=True)
            
            start = self.get_field_center(field_row, left=False)
            self.drag_preview = (start, start)
            self.update()
            print(f"Started connection from: {field_row.field_data[0]}")
        else:
            # Complete connection
            if self.selected_field == field_row:
                # Clicked same field - cancel
                print("Cancelled - same field clicked")
                self.selected_field.set_connection_role(is_source=False)
                self.selected_field = None
                self.drag_preview = None
                self.update()
                return
            
            # Don't allow connecting fields from the same table
            if self.selected_field.table_card == field_row.table_card:
                print("Cancelled - same table")
                self.selected_field.set_connection_role(is_source=False)
                self.selected_field = None
                self.drag_preview = None
                self.update()
                return
            
            # Check if connection already exists
            if self.connection_exists(self.selected_field, field_row):
                print("Cancelled - connection already exists")
                self.selected_field.set_connection_role(is_source=False)
                self.selected_field = None
                self.drag_preview = None
                self.update()
                return
            
            # Get field types
            source_type = self.selected_field.field_data[3] if len(self.selected_field.field_data) > 3 else ""
            target_type = field_row.field_data[3] if len(field_row.field_data) > 3 else ""
            
            print(f"Attempting connection: {source_type} -> {target_type}")
            
            # Allow PK->FK or FK->PK connections (bidirectional)
            if (source_type == "PK" and target_type == "FK") or \
               (source_type == "FK" and target_type == "PK"):
                
                # Ensure PK is always source, FK is always target
                if source_type == "PK":
                    pk_field = self.selected_field
                    fk_field = field_row
                else:
                    pk_field = field_row
                    fk_field = self.selected_field
                
                relation = "one-to-many"
                
                # Add connection
                self.connections.append((
                    pk_field.table_card, 
                    pk_field,
                    fk_field.table_card, 
                    fk_field,
                    relation
                ))
                
                print(f"Created connection: {pk_field.field_data[0]} (PK) -> {fk_field.field_data[0]} (FK)")
                
                # Update visual indicators
                pk_field.set_connection_role(is_source=True)
                fk_field.set_connection_role(is_target=True)
            else:
                print(f"Connection not allowed: {source_type} -> {target_type}")
            
            # Always reset selection
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
        
        # Clear connection roles and collect connections to remove
        connections_to_remove = []
        for pk_card, pk_field, fk_card, fk_field, relation in self.connections:
            if pk_card == card or fk_card == card:
                connections_to_remove.append((pk_card, pk_field, fk_card, fk_field, relation))
                if pk_card == card:
                    pk_field.set_connection_role(is_source=False)
                if fk_card == card:
                    fk_field.set_connection_role(is_target=False)
        
        # Remove connections
        for conn in connections_to_remove:
            self.connections.remove(conn)
        
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