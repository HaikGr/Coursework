from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from dbmanager.i18n import tr
from dbmanager.sql.generator import base_type
from dbmanager.ui.common.elided_label import ElidedLabel
from dbmanager.ui.common.live import bind
from dbmanager.ui.common.theme import color, style

# theme.qss templates. Every state keeps the line between rows; the card does not style its rows itself, so a
# row looks the same before and after the mouse first passes over it.
ROW_SEPARATOR = "FieldRow { border-bottom: 1px solid @border; }\n"
_ROW_STATES = {
    "selected": "FieldRow { background-color: @success_subtle; border-left: 3px solid @success; }",
    "source": "FieldRow { background-color: @accent_subtle; border-left: 3px solid @accent; }",
    "target": "FieldRow { background-color: @warning_subtle; border-left: 3px solid @warning; }",
    "hover": "FieldRow { background-color: @surface_hover; }",
    "plain": "FieldRow { background-color: transparent; }",
}
# A key's badge: (fill, text on the fill, outline and text while it is not linked yet)
_KEY_COLORS = {"PK": ("@pk", "@on_pk", "@warning_text"), "FK": ("@fk", "@on_fk", "@accent_text")}


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
            painter.setBrush(color("success_hover" if self.hovered else "success"))
            painter.drawEllipse(circle)
            painter.setPen(QPen(color("on_success"), 2, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
            painter.drawPolyline(QPolygonF([QPointF(5.5, 9.2), QPointF(8, 11.6), QPointF(12.6, 6.6)]))
        else:
            painter.setPen(QPen(color("text" if self.hovered else "text_muted"), 1.5))
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
        painter.setBrush(color("warning"))
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
        style(self.type_label, "QLabel { color: @text_muted; font-size: 10px; background: transparent; border: none; }")
        layout.addWidget(self.type_label)

        self.filter_mark = FilterMark()
        self.filter_mark.hide()
        layout.addWidget(self.filter_mark)

        self.toggle = QueryToggle()
        self.toggle.clicked.connect(lambda: self.query_toggle_requested.emit(self))
        layout.addWidget(self.toggle)

        about = f"{table_card.table_name}.{field_name}" + (f"  ({type_name})" if type_name else "")
        bind(self.setToolTip, "diagram.field_row.tip", field=about)
        bind(self.toggle.setToolTip, "diagram.field_row.add_to_query", field=field_name)

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
        style(self, ROW_SEPARATOR + _ROW_STATES[state])
        bright = state != "plain" or self.is_selected_for_query
        style(self.label, f"QLabel {{ color: {'@text' if bright else '@text_secondary'}; font-size: 12px; "
                          f"font-weight: {600 if self.is_selected_for_query else 400}; "
                          "background: transparent; border: none; }")

    def _update_badge(self):
        """A key's badge is filled once a link is drawn to it, outlined until then"""
        if self.key_badge is None:
            return
        fill, on_fill, outline = _KEY_COLORS[key_flag(self.field_data)]
        if self.connection_count > 0:
            look = f"background-color: {fill}; color: {on_fill}; border: 1px solid {fill};"
            bind(self.key_badge.setToolTip, "diagram.field_row.linked_key")
        else:
            look = f"background-color: transparent; color: {outline}; border: 1px solid {outline};"
            bind(self.key_badge.setToolTip, "diagram.field_row.primary_key" if key_flag(self.field_data) == "PK"
                 else "diagram.field_row.foreign_key")
        style(self.key_badge, f"QLabel {{ {look} border-radius: 3px; font-size: 8px; font-weight: 700; }}")

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
        bind(self.toggle.setToolTip, "diagram.field_row.take_out_of_query" if selected
             else "diagram.field_row.add_to_query", field=self.field_data[0])
        self._update_style()

    def set_filtered(self, descriptions):
        """descriptions: the filters on this field, in words ([] when there are none)"""
        self.is_filtered = bool(descriptions)
        self.filter_mark.setVisible(self.is_filtered)
        bind(self.filter_mark.setToolTip,
             lambda: tr("diagram.field_row.filtered", filters="; ".join(descriptions)) if descriptions else "")

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
