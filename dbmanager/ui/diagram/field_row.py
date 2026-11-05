from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from dbmanager.sql.generator import base_type
from dbmanager.ui.common.elided_label import ElidedLabel

# Every state keeps the line between rows; the card does not style its rows itself, so a row looks
# the same before and after the mouse first passes over it.
ROW_SEPARATOR = "FieldRow { border-bottom: 1px solid #4A5568; }\n"
_ROW_STATES = {
    "selected": "FieldRow { background-color: rgba(34, 197, 94, 0.16); border-left: 3px solid #22c55e; }",
    "source": "FieldRow { background-color: rgba(59, 130, 246, 0.25); border-left: 3px solid #3b82f6; }",
    "target": "FieldRow { background-color: rgba(245, 158, 11, 0.25); border-left: 3px solid #f59e0b; }",
    "hover": "FieldRow { background-color: rgba(100, 116, 139, 0.4); }",
    "plain": "FieldRow { background-color: transparent; }",
}
_KEY_COLORS = {"PK": "#f6c344", "FK": "#60a5fa"}


def key_flag(field_data):
    """'PK', 'FK' or '-' for a field [name, type, null, flag, ...]"""
    return field_data[3] if len(field_data) > 3 else ""


class QueryToggle(QWidget):
    """The circle at the end of a row: empty while the field is not in the query, a green tick once it is.
    Painted rather than drawn with a glyph, so it looks the same with every system font."""
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.checked = False
        self.hovered = False
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_checked(self, checked):
        self.checked = checked
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        circle = QRectF(2, 2, 14, 14)
        if self.checked:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#4ade80" if self.hovered else "#22c55e"))
            painter.drawEllipse(circle)
            painter.setPen(QPen(QColor("white"), 2, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
            painter.drawPolyline(QPolygonF([QPointF(5.5, 9.2), QPointF(8, 11.6), QPointF(12.6, 6.6)]))
        else:
            painter.setPen(QPen(QColor("#E2E8F0" if self.hovered else "#8A95A5"), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(circle)
            if self.hovered:
                painter.drawLine(QPointF(9, 5.5), QPointF(9, 12.5))
                painter.drawLine(QPointF(5.5, 9), QPointF(12.5, 9))
        painter.end()

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        # Taken here, so it does not reach the row and start a link
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class FilterMark(QWidget):
    """A small funnel, shown on a field the query filters by"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#fbbf24"))
        painter.drawPolygon(QPolygonF([QPointF(1.5, 2.5), QPointF(12.5, 2.5), QPointF(8.2, 7.5),
                                       QPointF(8.2, 12), QPointF(5.8, 10.8), QPointF(5.8, 7.5)]))
        painter.end()


class FieldRow(QFrame):
    """One field of a table card.

    Left button on the row: drag onto a field of another table to link the two (or click one, then the
    other) - the canvas decides. The circle at the end: put the field in the query or take it out. Right
    button (Ctrl-click or a two-finger click on a Mac, or the menu key): the field's menu, which the diagram
    page builds. The row passes the mouse on in screen coordinates: while a drag lasts, every move and the
    release come to the row it started on, wherever the mouse is."""
    link_pressed = pyqtSignal(object, object)  # row, global QPointF
    link_moved = pyqtSignal(object, bool)  # global QPointF, whether the left button is held
    link_released = pyqtSignal(object)  # global QPointF
    query_toggle_requested = pyqtSignal(object)  # row
    menu_requested = pyqtSignal(object, object)  # row, global QPoint

    def __init__(self, table_card, field_data):
        super().__init__(table_card)
        self.table_card = table_card
        self.field_data = field_data
        self.connection_count = 0
        self.is_connection_source = False
        self.is_connection_target = False
        self.is_selected_for_query = False
        self.is_filtered = False
        self.is_mouse_over = False

        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 8, 2)
        layout.setSpacing(6)

        flag = key_flag(field_data)
        self.key_badge = None
        if flag in _KEY_COLORS:
            self.key_badge = QLabel(flag)
            self.key_badge.setFixedSize(22, 14)
            self.key_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.key_badge)

        field_name = field_data[0]
        type_name = field_data[1] if len(field_data) > 1 and field_data[1] not in (None, "-") else ""
        self.label = ElidedLabel(field_name)
        layout.addWidget(self.label, stretch=1)

        self.type_label = QLabel(base_type(type_name))
        self.type_label.setStyleSheet("QLabel { color: #A0AEC0; font-size: 10px; background: transparent; "
                                      "border: none; }")
        layout.addWidget(self.type_label)

        self.filter_mark = FilterMark()
        self.filter_mark.hide()
        layout.addWidget(self.filter_mark)

        self.toggle = QueryToggle()
        self.toggle.clicked.connect(lambda: self.query_toggle_requested.emit(self))
        layout.addWidget(self.toggle)

        about = f"{table_card.table_name}.{field_name}" + (f"  ({type_name})" if type_name else "")
        self.setToolTip(f"{about}\nDrag onto a field of another table to link them (or click one, then the other)."
                        "\nRight-click: query, links, filters")
        self.toggle.setToolTip(f"Add {field_name} to the query")

        self._update_style()
        self._update_badge()
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)

    def dispose(self):
        """Kept for the card: nothing outlives the row any more (the WHERE popup used to)"""

    # ---------------- Looks ----------------
    def _state(self):
        if self.is_connection_source:
            return "source"
        if self.is_connection_target:
            return "target"
        if self.is_mouse_over:
            return "hover"
        if self.is_selected_for_query:
            return "selected"
        return "plain"

    def _update_style(self):
        state = self._state()
        self.setStyleSheet(ROW_SEPARATOR + _ROW_STATES[state])
        bright = state != "plain" or self.is_selected_for_query
        self.label.setStyleSheet(f"QLabel {{ color: {'#FFFFFF' if bright else '#E0E0E0'}; font-size: 12px; "
                                 f"font-weight: {600 if self.is_selected_for_query else 400}; "
                                 "background: transparent; border: none; }")

    def _update_badge(self):
        """A key's badge is filled once a link is drawn to it, outlined until then"""
        if self.key_badge is None:
            return
        color = _KEY_COLORS[key_flag(self.field_data)]
        if self.connection_count > 0:
            style = f"background-color: {color}; color: #1A202C; border: 1px solid {color};"
            self.key_badge.setToolTip("A key, linked to another table")
        else:
            style = f"background-color: transparent; color: {color}; border: 1px solid {color};"
            self.key_badge.setToolTip("Primary key" if key_flag(self.field_data) == "PK" else "Foreign key")
        self.key_badge.setStyleSheet(f"QLabel {{ {style} border-radius: 3px; font-size: 8px; font-weight: 700; }}")

    # ---------------- Links ----------------
    def set_connection_role(self, is_source=False, is_target=False):
        self.is_connection_source = is_source
        self.is_connection_target = is_target
        self._update_style()

    def add_connection(self):
        self.connection_count += 1
        self._update_badge()

    def remove_connection(self):
        self.connection_count = max(0, self.connection_count - 1)
        if self.connection_count == 0:
            self.is_connection_source = False
            self.is_connection_target = False
        self._update_style()
        self._update_badge()

    # ---------------- The query ----------------
    def set_query_selection(self, selected):
        self.is_selected_for_query = selected
        self.toggle.set_checked(selected)
        self.toggle.setToolTip(f"{'Take' if selected else 'Add'} {self.field_data[0]} "
                               f"{'out of' if selected else 'to'} the query")
        self._update_style()

    def set_filtered(self, descriptions):
        """descriptions: the filters on this field, in words ([] when there are none)"""
        self.is_filtered = bool(descriptions)
        self.filter_mark.setVisible(self.is_filtered)
        self.filter_mark.setToolTip("Filtered: " + "; ".join(descriptions) if descriptions else "")

    # ---------------- Mouse ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.link_pressed.emit(self, event.globalPosition())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.link_moved.emit(event.globalPosition(), bool(event.buttons() & Qt.MouseButton.LeftButton))
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.link_released.emit(event.globalPosition())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        self.menu_requested.emit(self, event.globalPos())
        event.accept()

    def enterEvent(self, event):
        self.is_mouse_over = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_mouse_over = False
        self._update_style()
        super().leaveEvent(event)
