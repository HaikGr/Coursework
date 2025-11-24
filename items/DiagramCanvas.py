from PyQt6.QtWidgets import (
    QWidget 
)
from PyQt6.QtCore import (
    QPoint, QRect, QTimer
)
from PyQt6.QtGui import ( QPainter, QPen, QColor, QCursor )

from items.ConditionPopup import ConditionPopup

class DiagramCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connections = []  
        self.cards = []
        self.selected_field = None
        self.popup = None

    def add_card(self, card):
        card.canvas = self
        self.cards.append(card)
        card.moved.connect(self.update) 

        # register all field click events
        for fr in card.field_rows:
            fr.clicked.connect(self.on_field_clicked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#69a7ff"))
        pen.setWidth(3)
        painter.setPen(pen)

        for A, fieldA, B, fieldB in self.connections:
            # fieldA and fieldB are FieldRow instances
            # compute coordinates in canvas space
            ax = A.x() + A.width()
            ay = A.y() + fieldA.y() + fieldA.height() // 2

            bx = B.x()
            by = B.y() + fieldB.y() + fieldB.height() // 2

            # draw a simple bezier-ish polyline (or straight)
            painter.drawLine(int(ax), int(ay), int(bx), int(by))

    def on_field_clicked(self, field_row):
        # field_row is FieldRow
        if self.selected_field is None:
            self.selected_field = field_row
            # show popup for first selection
            self.show_condition_popup(field_row)
        else:
            # create connection between selected_field and clicked field_row
            A = self.selected_field.table_card
            B = field_row.table_card
            # Avoid self-connection same field
            if A is field_row.table_card and self.selected_field is field_row:
                self.selected_field = None
                self.hide_condition_popup()
                return

            self.connections.append((self.selected_field.table_card, self.selected_field, B, field_row))
            self.selected_field = None
            self.hide_condition_popup()
            self.update()

    def show_condition_popup(self, field_row):
        # ensure a single popup anchored near the field_row
        if self.popup:
            self.popup.hide()
            self.popup.deleteLater()
            self.popup = None

        self.popup = ConditionPopup(self, field_row.table_card.table_name, field_row.field_name)
        # position popup to the right of the field row (in canvas coords)
        pos_in_canvas = field_row.mapTo(self, QPoint(field_row.width(), 0))
        x = field_row.table_card.x() + field_row.width() + 10
        y = field_row.table_card.y() + field_row.y() - 5
        self.popup.move(int(x), int(y))
        self.popup.show()

        # Connect popup hide timer control
        # if mouse leaves both field and popup, hide after 300ms
        def maybe_hide():
            # check if cursor is over popup or field
            global_pos = QCursor.pos()
            rect_popup = self.popup.rect()
            top_left = self.popup.mapToGlobal(rect_popup.topLeft())
            bottom_right = self.popup.mapToGlobal(rect_popup.bottomRight())
            popup_global_rect = QRect(top_left, bottom_right)

            rect_field = field_row.rect()
            field_tl = field_row.mapToGlobal(rect_field.topLeft())
            field_br = field_row.mapToGlobal(rect_field.bottomRight())
            field_global_rect = QRect(field_tl, field_br)

            if not (popup_global_rect.contains(global_pos) or field_global_rect.contains(global_pos)):
                if self.popup:
                    self.popup.hide()

        # install event listeners to keep popup visible while hovering
        # use singleShot timer to check after short delay to avoid flicker
        field_row.entered_callback = lambda: None
        field_row.left_callback = lambda: QTimer.singleShot(160, maybe_hide)
        self.popup.entered_callback = lambda: None
        self.popup.left_callback = lambda: QTimer.singleShot(160, maybe_hide)

    def hide_condition_popup(self):
        if self.popup:
            self.popup.hide()
            self.popup.deleteLater()
            self.popup = None