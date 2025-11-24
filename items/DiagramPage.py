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

        # large scrollable canvas area
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # We'll use a DiagramCanvas inside the scroll area
        self.table_area = DiagramCanvas()
        self.table_area.setMinimumSize(1400, 900)
        self.table_area.setStyleSheet("background-color: #f5f6f7;")

        container_layout.addWidget(self.table_area)

        # Add example cards
        card1 = TableCard("Users", ["user_id (PK)", "username", "email", "created_at"])
        card1.move(120, 80)
        card1.setParent(self.table_area)
        self.table_area.add_card(card1)

        card2 = TableCard("Orders", ["order_id (PK)", "user_fk", "order_date", "total_amount"])
        card2.move(420, 220)
        card2.setParent(self.table_area)
        self.table_area.add_card(card2)

        card3 = TableCard("Products", ["product_id (PK)", "name", "price", "category"])
        card3.move(760, 120)
        card3.setParent(self.table_area)
        self.table_area.add_card(card3)

        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setWidget(self.table_area)
        canvas_scroll.setStyleSheet("border: none;")
        layout.addWidget(canvas_scroll)
