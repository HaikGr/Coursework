from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout, QScrollArea,
)
from items.ToolBar import Toolbar
from items.DiagramCanvas import DiagramCanvas
from items.TableCard import TableCard
# ---------------------------
# Diagram Page (draggable cards)
# ---------------------------
class DiagramPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = Toolbar()
        layout.addWidget(toolbar)

        self.table_area = DiagramCanvas()
        self.table_area.setMinimumSize(1400, 900)
        self.table_area.setStyleSheet("background-color: #f5f6f7;")
        layout.addWidget(self.table_area)

        self.cards = {}
        self._x, self._y = 120, 80

        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setWidget(self.table_area)
        canvas_scroll.setStyleSheet("border: none;")
        layout.addWidget(canvas_scroll)

    def add_table_card(self, table_name, columns):
        if table_name in self.cards:
            self.cards[table_name].update_fields(columns)
        else:
            new_card = TableCard(table_name, columns, parent=self.table_area)
            self.cards[table_name] = new_card
            new_card.show()
            new_card.move(self._x, self._y)
            self.table_area.add_card(new_card)
            self._x += 200
            self._y += 200

    def remove_field_from_card(self, table_name, columns):
        if table_name in self.cards:
            self.cards[table_name].update_fields(columns)
            self.table_area.update()

    def remove_table_card(self, table_name):
        if table_name not in self.cards:
            return
        card = self.cards.pop(table_name)
        self.table_area.remove_card(card)
        card.setParent(None)
        card.deleteLater()
        self.table_area.update()