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
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)

        # We'll use a DiagramCanvas inside the scroll area
        self.table_area = DiagramCanvas()
        self.table_area.setMinimumSize(1400, 900)
        self.table_area.setStyleSheet("background-color: #f5f6f7;")
        self.container_layout.addWidget(self.table_area)
        
        # CHANGED: Use a dictionary {table_name: TableCard} to track cards
        self.cards = {}
        
        global x, y
        x = 120
        y = 80

        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setWidget(self.table_area)
        canvas_scroll.setStyleSheet("border: none;")
        layout.addWidget(canvas_scroll)

    def add_table_card(self, table_name, columns):
        """
        Called when TableDetails emits data.
        Updates an existing card if table_name is present, otherwise creates a new one.
        """
        global x, y
        
        # 'columns' now contains the full list of fields (e.g., [('id', 'INT', 'No'), ('name', 'VARCHAR', 'Yes')])
        
        # Check if a card for this table already exists
        if table_name in self.cards:
            existing_card = self.cards[table_name]
            
            # 1. Card exists: Update its fields using the new method
            existing_card.update_fields(columns)
            
        else:
            # 2. Card does not exist: Create a new one
            new_card = TableCard(table_name, columns, parent=self.table_area)
            self.cards[table_name] = new_card # Store card in the dictionary
            
            # Positioning and display logic
            new_card.show()
            new_card.move(x, y)
            
            # Inform the canvas (DiagramCanvas) of the new card
            self.table_area.add_card(new_card)
            
            # Increment position for the next NEW card
            x += 200
            y += 200

    def remove_field_from_card(self, table_name, columns):
        """
        This is called when TableDetailsPage emits: 
            field_deleted.emit(table_name, updated_columns)
        """
        self.cards[table_name].update_fields(columns)
        self.table_area.update()