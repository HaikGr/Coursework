import math

from PyQt6 import sip
from PyQt6.QtCore import QPoint, QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from dbmanager.i18n import tr
from dbmanager.model.links import End, plan_link
from dbmanager.ui.common.theme import color, style
from dbmanager.ui.diagram.field_row import FieldRow, key_flag


def link_end(row):
    """A field row as one end of a link"""
    data = row.field_data
    return End(row.table_card.table_name, data[0], data[1] if len(data) > 1 and data[1] != "-" else "",
               key_flag(data) == "PK")

MIN_WIDTH, MIN_HEIGHT = 1400, 900
EDGE_MARGIN = 60


class DiagramCanvas(QWidget):
    """Canvas that holds TableCard widgets and draws the links between their fields.

    A link is made by dragging from one field onto a field of another table - or by clicking one, then the
    other (Esc, or a click on the empty canvas, gives up). One of the two must be a primary key: the other
    field points at it, and becomes a foreign key when the changes are run. link_message says how it went.
    query_joins (set by the diagram page) are joins of the query only, drawn dashed."""
    connections_changed = pyqtSignal()  # Emitted when connections are modified
    link_message = pyqtSignal(str, bool)  # text, True when the link was made

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connections = []  # list of tuples: (pk_field_row, fk_field_row, relation_type)
        self.cards = []
        self.query_joins = []  # (row, row) of joins made for the query only
        self.links_enabled = True  # False where the user may not change the structure (a shared database)
        self.source = None  # the row a link is being made from
        self.pressed = None  # (row, global position) of a press that may become a drag
        self.dragging = False
        self.press_handled = False  # the press finished a click-click link: its release does nothing
        self.preview_end = None  # where the link being made ends now, in canvas coordinates
        self.hover_target = None  # the row it would go to, lit while valid
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)  # for Esc
        style(self, "QWidget { background-color: @canvas; }")

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
            for signal, slot in ((row.link_pressed, self._on_link_pressed), (row.link_moved, self._on_link_moved),
                                 (row.link_released, self._on_link_released)):
                try:
                    signal.disconnect(slot)
                except TypeError:
                    pass  # was not connected yet
                signal.connect(slot)

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
            self.draw_connection_arrow(painter, start, end, color("link"), relation, control_offset)

            # Restore painter state
            painter.restore()

        # Joins of the query only: dashed, they change nothing in the database
        for left, right in self.query_joins:
            start, end = self.get_field_center(left, left=False), self.get_field_center(right, left=True)
            if start != (0, 0) and end != (0, 0):
                painter.save()
                painter.setPen(QPen(color("link_join"), 2, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                path = QPainterPath(QPointF(*start))
                dx = max(abs(end[0] - start[0]) * 0.5, 60)
                path.cubicTo(QPointF(start[0] + dx, start[1]), QPointF(end[0] - dx, end[1]), QPointF(*end))
                painter.drawPath(path)
                painter.restore()

        # The link being made
        if self.source is not None and self.preview_end is not None:
            start = self.get_field_center(self.source, left=False)
            if start != (0, 0):
                line = color("link_ok" if self.hover_target is not None else "link_draft")
                painter.setPen(QPen(line, 2, Qt.PenStyle.DashLine))
                painter.drawLine(QPoint(*start), self.preview_end)
                painter.setBrush(line)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(self.preview_end), 4, 4)

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

    # ---------------- Making a link ----------------
    def row_at(self, global_pos):
        """The field row under a point of the screen, or None"""
        widget = self.childAt(self.mapFromGlobal(global_pos.toPoint()))
        while widget is not None and widget is not self:
            if isinstance(widget, FieldRow):
                return widget
            widget = widget.parentWidget()
        return None

    def _on_link_pressed(self, row, global_pos):
        self.press_handled = False
        if self.source is not None and not self.dragging:
            # The second click of click-then-click
            self.press_handled = True
            if row is self.source:
                self.cancel_connection()
            else:
                self.complete_link(row)
            return
        self.pressed = (row, global_pos)

    def _on_link_moved(self, global_pos, buttons_held):
        if buttons_held and self.pressed is not None and not self.dragging:
            row, start = self.pressed
            if (global_pos - start).manhattanLength() >= QApplication.startDragDistance():
                if self._start_link(row):
                    self.dragging = True
        if self.source is not None:
            self._follow(global_pos)

    def _on_link_released(self, global_pos):
        pressed, self.pressed = self.pressed, None
        if self.press_handled:
            self.press_handled = False
            return
        if self.dragging:
            self.dragging = False
            target = self.row_at(global_pos)
            if target is None or target is self.source:
                self.cancel_connection()
            else:
                self.complete_link(target)
        elif pressed is not None and self._start_link(pressed[0]):
            # A click: the link waits for a click on the other field
            self.link_message.emit(tr("diagram.link.click_other", source=link_end(self.source)), False)
            self._follow(global_pos)

    def _start_link(self, row):
        if not self.links_enabled:
            self.link_message.emit(tr("diagram.link.owner_only"), False)
            return False
        self.cancel_connection()
        self.source = row
        row.set_connection_role(is_source=True)
        self.setFocus()
        return True

    def _follow(self, global_pos):
        """The link being made follows the mouse; a field it could go to lights up"""
        self.preview_end = self.mapFromGlobal(global_pos.toPoint())
        target = self.row_at(global_pos)
        valid = target if target is not None and target is not self.source and \
            isinstance(plan_link(link_end(self.source), link_end(target)), tuple) else None
        if valid is not self.hover_target:
            if self.hover_target is not None and not sip.isdeleted(self.hover_target):
                self.hover_target.set_connection_role(is_target=False)
            self.hover_target = valid
            if valid is not None:
                valid.set_connection_role(is_target=True)
        self.update()

    def complete_link(self, target):
        """Link the field the link was started from to this one, or say why not"""
        source = self.source
        self.cancel_connection()
        if source is not None:
            self.link(source, target)

    def link(self, source, target):
        """Link two field rows (the first is the parent when both are keys). True when linked; otherwise
        link_message says why not."""
        plan = plan_link(link_end(source), link_end(target))
        if isinstance(plan, str):
            self.link_message.emit(plan, False)
            return False
        parent, child = (source, target) if plan[0] == link_end(source) else (target, source)
        if self.connection_exists(parent, child):
            self.link_message.emit(tr("diagram.link.already_linked", child=plan[1], parent=plan[0]), False)
            return False
        current = next((pk for pk, fk, _ in self.connections if fk is child), None)
        if current is not None:
            self.link_message.emit(tr("diagram.link.points_elsewhere", child=plan[1], parent=link_end(current)), False)
            return False
        self.connections.append((parent, child, 'one-to-many'))
        parent.add_connection()
        child.add_connection()
        self.connections_changed.emit()
        self.update()
        self.link_message.emit(tr("diagram.link.linked", child=plan[1], parent=plan[0],
                                  run_query=tr("common.action.run_query")), True)
        return True

    def cancel_connection(self):
        """Give up the link being made"""
        if self.source is not None and not sip.isdeleted(self.source):
            self.source.set_connection_role(is_source=False)
        if self.hover_target is not None and not sip.isdeleted(self.hover_target):
            self.hover_target.set_connection_role(is_target=False)
        self.source = self.hover_target = self.preview_end = None
        self.dragging = False
        self.update()

    def mousePressEvent(self, event):
        if self.source is not None:
            self.cancel_connection()  # a click on the empty canvas gives up
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.source is not None:
            self._follow(event.globalPosition())
        super().mouseMoveEvent(event)

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
