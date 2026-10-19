import math

from PyQt6 import sip
from PyQt6.QtCore import QPoint, QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from dbmanager.ui.diagram.field_row import FieldRow, key_flag

MIN_WIDTH, MIN_HEIGHT = 1400, 900
EDGE_MARGIN = 60


class DiagramCanvas(QWidget):
    """Canvas that holds TableCard widgets and draws connections between FieldRows.

    Workflow: Click source field -> drag -> release on target field
    """
    connections_changed = pyqtSignal()  # Emitted when connections are modified

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connections = []  # list of tuples: (pk_field_row, fk_field_row, relation_type)
        self.cards = []
        self.selected_field = None
        self.drag_preview = None  # (start_point, end_point)
        self.is_dragging_connection = False
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #1A1F2E;")

    def add_card(self, card):
        card.canvas = self
        self.cards.append(card)
        card.moved.connect(lambda c=card: self._on_card_moved(c))
        self._connect_card_fields(card)
        self.grow_to_fit(card)

    def _on_card_moved(self, card):
        self.grow_to_fit(card)
        self.update()

    def grow_to_fit(self, card):
        """Enlarge the canvas so a card placed or dragged near its edge stays reachable by scrolling."""
        width = max(self.minimumWidth(), MIN_WIDTH, card.x() + card.width() + EDGE_MARGIN)
        height = max(self.minimumHeight(), MIN_HEIGHT, card.y() + card.height() + EDGE_MARGIN)
        if (width, height) != (self.minimumWidth(), self.minimumHeight()):
            self.setMinimumSize(width, height)

    def reset_size(self):
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

    def _connect_card_fields(self, card):
        for row in card.all_rows():
            try:
                row.clicked.disconnect(self.on_field_clicked)
            except TypeError:
                pass  # was not connected yet
            row.clicked.connect(self.on_field_clicked)

    def update_card_fields(self, card):
        self._connect_card_fields(card)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._drop_dead_connections()

        # Group connections by source field AND by target field
        source_groups = {}
        target_groups = {}
        for idx, (pk_field, fk_field, relation) in enumerate(self.connections):
            if pk_field not in source_groups:
                source_groups[pk_field] = []
            source_groups[pk_field].append(idx)

            if fk_field not in target_groups:
                target_groups[fk_field] = []
            target_groups[fk_field].append(idx)

        # Draw each connection independently
        for idx, (pk_field, fk_field, relation) in enumerate(self.connections):
            # Save painter state for clean drawing
            painter.save()

            start = self.get_field_center(pk_field, left=False)
            end = self.get_field_center(fk_field, left=True)

            # Skip invalid coordinates
            if start == (0, 0) or end == (0, 0):
                painter.restore()
                continue

            # Calculate control point offset for visual separation (not endpoint offset)
            control_offset = 0
            source_group = source_groups.get(pk_field, [idx])
            if len(source_group) > 1:
                position_in_group = source_group.index(idx)
                total_in_group = len(source_group)
                # Offset control points, not endpoints - keeps curves attached to fields
                control_offset = (position_in_group - (total_in_group - 1) / 2) * 40

            # All connections use the same color for consistency
            color = QColor('#69a7ff')

            self.draw_connection_arrow(painter, start, end, color, relation, control_offset)

            # Restore painter state
            painter.restore()

        # Draw drag-preview line
        if self.drag_preview and self.is_dragging_connection:
            pen = QPen(QColor('#FFD57F'), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            start, end = self.drag_preview
            painter.drawLine(QPoint(int(start[0]), int(start[1])), QPoint(int(end[0]), int(end[1])))

            painter.setBrush(QColor('#FFD57F'))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(end[0], end[1]), 4, 4)

    def draw_connection_arrow(self, painter, start, end, color, relation_type='one-to-many', control_offset=0):
        painter.setPen(QPen(color, 2))
        start_point = QPointF(start[0], start[1])
        end_point = QPointF(end[0], end[1])

        # Build a cubic bezier curve
        path = QPainterPath(start_point)

        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()

        # Calculate horizontal offset based on distance
        # Use a larger offset when tables are far apart
        distance = math.sqrt(dx * dx + dy * dy)
        horizontal_offset = max(min(abs(dx) * 0.5, distance * 0.4), 60)

        # For connections where target is to the left of source, adjust control points
        if dx < 0:
            # Target is to the left - curve needs to go around
            horizontal_offset = max(abs(dx) * 0.3 + 80, 100)

        # Create control points for smooth bezier curve
        ctrl1 = QPointF(start_point.x() + horizontal_offset, start_point.y() + control_offset)
        ctrl2 = QPointF(end_point.x() - horizontal_offset, end_point.y() + control_offset)

        path.cubicTo(ctrl1, ctrl2, end_point)
        painter.drawPath(path)

        # "One" indicator at start
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(start_point, 4, 4)

        # Crow's foot for "many" - use ctrl2 for correct curve tangent direction
        self.draw_crows_foot(painter, end_point, ctrl2, color)

    def draw_crows_foot(self, painter, end_point, ctrl2_point, color):
        """Draw crow's foot using the curve's tangent direction at end point"""
        painter.setPen(QPen(color, 2))

        # Use control point 2 to get the actual curve direction at the end
        dx = end_point.x() - ctrl2_point.x()
        dy = end_point.y() - ctrl2_point.y()

        # Fallback to horizontal if control point is same as end
        if abs(dx) < 1 and abs(dy) < 1:
            angle = 0
        else:
            angle = math.atan2(dy, dx)

        foot_length = 12
        base_angle1 = angle + math.pi / 6
        base_angle2 = angle - math.pi / 6

        top_end = QPointF(end_point.x() - foot_length * math.cos(base_angle1),
                          end_point.y() - foot_length * math.sin(base_angle1))
        bottom_end = QPointF(end_point.x() - foot_length * math.cos(base_angle2),
                             end_point.y() - foot_length * math.sin(base_angle2))
        middle_end = QPointF(end_point.x() - foot_length * math.cos(angle),
                             end_point.y() - foot_length * math.sin(angle))

        painter.drawLine(end_point, top_end)
        painter.drawLine(end_point, bottom_end)
        painter.drawLine(end_point, middle_end)

    def _drop_dead_connections(self):
        """A safety net: forget links whose field rows no longer exist (and tell the listeners, later -
        this runs while painting)."""
        dead = [connection for connection in self.connections
                if sip.isdeleted(connection[0]) or sip.isdeleted(connection[1])]
        if not dead:
            return
        for pk_field, fk_field, _ in dead:
            for row in (pk_field, fk_field):
                if not sip.isdeleted(row):
                    row.remove_connection()
        self.connections = [connection for connection in self.connections
                            if not any(connection is gone for gone in dead)]
        QTimer.singleShot(0, self.connections_changed.emit)

    def get_field_center(self, field_row, left=False):
        if field_row is None or sip.isdeleted(field_row) or not field_row.isVisible():
            return (0, 0)
        w = field_row.width()
        h = field_row.height()
        pos = field_row.mapTo(self, field_row.rect().topLeft())
        x = pos.x() + (10 if left else w - 10)
        y = pos.y() + h // 2
        return (int(x), int(y))

    def connection_exists(self, field1, field2):
        for pk, fk, _ in self.connections:
            if (pk == field1 and fk == field2) or (pk == field2 and fk == field1):
                return True
        return False

    def on_field_clicked(self, field_row):
        """Handle field click to start or complete connection"""
        # If no field selected, start connection
        if self.selected_field is None:
            self.selected_field = field_row
            field_row.set_connection_role(is_source=True)
            start = self.get_field_center(field_row, left=False)
            self.drag_preview = (start, start)
            self.is_dragging_connection = True
            self.update()
            return

        # Clicking same field cancels
        if self.selected_field == field_row:
            self.cancel_connection()
            return

        # Try to complete connection
        self.try_complete_connection(field_row)

    def try_complete_connection(self, target_field):
        """Attempt to create a connection to the target field"""
        if not self.selected_field:
            return

        # Prevent connecting within same table
        if self.selected_field.table_card == target_field.table_card:
            self.cancel_connection()
            return

        # Check if connection already exists
        if self.connection_exists(self.selected_field, target_field):
            self.cancel_connection()
            return

        # Validate PK-FK connection
        source_type = key_flag(self.selected_field.field_data)
        target_type = key_flag(target_field.field_data)

        if (source_type == 'PK' and target_type == 'FK') or (source_type == 'FK' and target_type == 'PK'):
            if source_type == 'PK':
                pk_field = self.selected_field
                fk_field = target_field
            else:
                pk_field = target_field
                fk_field = self.selected_field

            relation = 'one-to-many'
            self.connections.append((pk_field, fk_field, relation))

            # Update connection counts
            pk_field.add_connection()
            fk_field.add_connection()

            # Notify listeners that connections changed
            self.connections_changed.emit()

        # Reset selection
        self.cancel_connection()

    def cancel_connection(self):
        """Cancel the current connection operation"""
        if self.selected_field:
            self.selected_field.set_connection_role(is_source=False)
        self.selected_field = None
        self.drag_preview = None
        self.is_dragging_connection = False
        self.update()

    def mouseMoveEvent(self, event):
        """Update drag preview while dragging"""
        if self.selected_field and self.drag_preview and self.is_dragging_connection:
            start = self.drag_preview[0]
            pos = event.position()
            end = (int(pos.x()), int(pos.y()))
            self.drag_preview = (start, end)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Try to complete connection on mouse release"""
        if self.selected_field and self.is_dragging_connection:
            # Find field under cursor
            pos = event.position().toPoint()
            widget = self.childAt(pos)

            # The widget under the cursor may be a label inside a field row
            field_row = None
            while widget is not None and widget is not self:
                if isinstance(widget, FieldRow):
                    field_row = widget
                    break
                widget = widget.parentWidget()

            # If valid field found, try to complete connection
            if field_row and field_row != self.selected_field:
                self.try_complete_connection(field_row)
            else:
                self.cancel_connection()

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        """Cancel connection on Escape key"""
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_connection()
        super().keyPressEvent(event)

    def remove_card(self, card):
        """Remove a table card and its connections"""
        if card in self.cards:
            self.cards.remove(card)

        connections_to_remove = []
        for conn in list(self.connections):
            pk_field, fk_field, _ = conn
            if pk_field.table_card == card or fk_field.table_card == card:
                connections_to_remove.append(conn)
                # Decrement connection counts
                pk_field.remove_connection()
                fk_field.remove_connection()

        for conn in connections_to_remove:
            if conn in self.connections:
                self.connections.remove(conn)

        if connections_to_remove:
            self.connections_changed.emit()
        self.update()

    def remove_connection(self, connection):
        """Remove a specific connection"""
        if connection in self.connections:
            pk_field, fk_field, _ = connection

            # Decrement connection counts
            pk_field.remove_connection()
            fk_field.remove_connection()

            self.connections.remove(connection)
            self.connections_changed.emit()
            self.update()

    def clear_all_connections(self):
        """Clear all connections"""
        had_connections = len(self.connections) > 0
        for pk_field, fk_field, _ in list(self.connections):
            pk_field.remove_connection()
            fk_field.remove_connection()
        self.connections.clear()
        if had_connections:
            self.connections_changed.emit()
        self.update()
