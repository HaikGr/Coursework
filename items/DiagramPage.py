from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea,
)
from items.DiagramCanvas import DiagramCanvas
from items.TableCard import TableCard


class DiagramPage(QWidget):
    def __init__(self, sql_builder=None):
        super().__init__()
        self.sql_builder = sql_builder  # Reference to the SQL builder from dashboard
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar (if exists)
        try:
            from items.ToolBar import Toolbar
            toolbar = Toolbar()
            layout.addWidget(toolbar)
        except Exception:
            pass

        # Canvas
        self.table_area = DiagramCanvas()
        self.table_area.setMinimumSize(1400, 900)

        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setWidget(self.table_area)
        canvas_scroll.setStyleSheet("border: none; background-color: #f5f6f7;")

        layout.addWidget(canvas_scroll)

        self.cards = {}
        self._x, self._y = 120, 80

    def add_table_card(self, table_name, columns):
        """Add or update a table card"""
        if table_name in self.cards:
            # Update existing card
            self.cards[table_name].update_fields(columns)
            self.table_area.update_card_fields(self.cards[table_name])
            # Reconnect to SQL builder
            if self.sql_builder:
                self._connect_card_to_sql_builder(self.cards[table_name])
        else:
            # Create new card
            new_card = TableCard(table_name, columns, parent=self.table_area)
            self.cards[table_name] = new_card
            new_card.show()
            new_card.move(self._x, self._y)
            self.table_area.add_card(new_card)
            
            # Connect field signals to SQL builder
            if self.sql_builder:
                self._connect_card_to_sql_builder(new_card)
            
            self._x += 240
            if self._x > 1000:
                self._x = 120
                self._y += 320

    def _connect_card_to_sql_builder(self, card):
        """Connect all field rows in a card to the SQL builder"""
        if not self.sql_builder:
            return
            
        all_rows = []
        all_rows.extend(getattr(card, 'pk_rows', []))
        all_rows.extend(getattr(card, 'fk_rows', []))
        all_rows.extend(getattr(card, 'main_rows', []))

        for row in all_rows:
            # Disconnect any existing connections
            try:
                row.selected_for_query.disconnect()
            except:
                pass
            # Connect to SQL builder
            row.selected_for_query.connect(self._on_field_selected_for_query)

    def _on_field_selected_for_query(self, table_name, field_name, field_type):
        """Handle field selection for query building (triggered by RIGHT-CLICK)"""
        print(f"Field selected: {table_name}.{field_name} ({field_type})")  # Debug
        if self.sql_builder:
            self.sql_builder.add_field(table_name, field_name, field_type)

    def remove_field_from_card(self, table_name, columns):
        """Remove fields from a card"""
        if table_name in self.cards:
            self.cards[table_name].update_fields(columns)
            # Reconnect after update
            if self.sql_builder:
                self._connect_card_to_sql_builder(self.cards[table_name])
            self.table_area.update()

    def remove_table_card(self, table_name):
        """Remove a table card completely"""
        if table_name not in self.cards:
            return
        card = self.cards.pop(table_name)
        self.table_area.remove_card(card)
        card.setParent(None)
        card.deleteLater()
        self.table_area.update()