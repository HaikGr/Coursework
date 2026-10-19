from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from dbmanager.ui.diagram.diagram_canvas import DiagramCanvas
from dbmanager.ui.diagram.table_card import TableCard

FIRST_X, FIRST_Y = 120, 80
STEP_X, STEP_Y, LAST_X = 240, 320, 1000


class DiagramPage(QWidget):
    """The tables of the active database as cards; links drawn here become JOINs and foreign keys."""

    def __init__(self, sql_builder=None):
        super().__init__()
        self.sql_builder = sql_builder

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self.sql_builder:
            self.sql_builder.field_removed.connect(self._on_field_removed_from_query)
            self.sql_builder.fields_cleared.connect(self._on_all_fields_cleared)

        self.table_area = DiagramCanvas()
        self.table_area.reset_size()
        self.table_area.connections_changed.connect(self._on_connections_changed)

        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setWidget(self.table_area)
        canvas_scroll.setStyleSheet("border: none; background-color: #f5f6f7;")
        layout.addWidget(canvas_scroll)

        self.cards = {}
        self._x, self._y = FIRST_X, FIRST_Y

    def _on_connections_changed(self):
        if self.sql_builder:
            self.sql_builder.set_connections(self.table_area.connections)

    # ---------------- Cards ----------------
    def add_table_card(self, table_name, columns, renamed=None):
        """Add a card for a table, or refresh the card it already has.
        renamed: {old name: new name} of fields renamed since, so links drawn to them are kept."""
        card = self.cards.get(table_name)
        if card is not None:
            card.update_fields(columns, renamed=renamed)
            self._connect_card_to_sql_builder(card)
            return

        card = TableCard(table_name, columns, parent=self.table_area)
        self.cards[table_name] = card
        card.move(self._x, self._y)
        card.show()
        self.table_area.add_card(card)
        self._connect_card_to_sql_builder(card)

        self._x += STEP_X
        if self._x > LAST_X:
            self._x = FIRST_X
            self._y += STEP_Y

    def rename_field(self, table_name, old_name, new_name, columns):
        """Refresh a card after a field rename, keeping the links drawn to that field."""
        if table_name in self.cards:
            self.add_table_card(table_name, columns, renamed={old_name: new_name})

    def remove_field_from_card(self, table_name, columns):
        card = self.cards.get(table_name)
        if card is None:
            return
        card.update_fields(columns)
        self._connect_card_to_sql_builder(card)
        self.table_area.update()

    def remove_table_card(self, table_name):
        card = self.cards.pop(table_name, None)
        if card is None:
            return
        self.table_area.remove_card(card)
        card.dispose()
        card.setParent(None)
        card.deleteLater()
        self.table_area.update()

    def clear_diagram(self):
        """Remove every card (used when another database is selected)."""
        for table_name in list(self.cards):
            self.remove_table_card(table_name)
        self._x, self._y = FIRST_X, FIRST_Y
        self.table_area.reset_size()

    # ---------------- Query builder sync ----------------
    def _connect_card_to_sql_builder(self, card):
        if not self.sql_builder:
            return
        for row in card.all_rows():
            for signal in (row.selected_for_query, row.condition_added):
                try:
                    signal.disconnect()
                except TypeError:
                    pass  # nothing connected yet
            row.selected_for_query.connect(self._on_field_selected_for_query)
            row.condition_added.connect(self._on_condition_added)

    def _set_row_selected(self, table_name, field_name, selected):
        card = self.cards.get(table_name)
        row = card.find_row(field_name) if card else None
        if row is not None:
            row.set_query_selection(selected)

    def _on_field_selected_for_query(self, table_name, field_name, field_type):
        """Right-click on a field: add it to the query, or take it out again."""
        if self.sql_builder:
            added = self.sql_builder.toggle_field(table_name, field_name, field_type)
            self._set_row_selected(table_name, field_name, added)

    def _on_condition_added(self, table_name, field_name, condition):
        """A WHERE condition typed in a field's hover popup: the field joins the query too."""
        if self.sql_builder:
            self.sql_builder.add_field(table_name, field_name, "")
            self.sql_builder.add_condition(table_name, field_name, condition)
            self._set_row_selected(table_name, field_name, True)

    def _on_field_removed_from_query(self, table_name, field_name):
        self._set_row_selected(table_name, field_name, False)

    def _on_all_fields_cleared(self):
        for card in self.cards.values():
            for row in card.all_rows():
                row.set_query_selection(False)

    # ---------------- Links by name (kept per database while another one is shown) ----------------
    def export_links(self):
        """Current PK-FK connections as names: (pk_table, pk_field, fk_table, fk_field)"""
        return [
            (pk.table_card.table_name, pk.field_data[0], fk.table_card.table_name, fk.field_data[0])
            for pk, fk, _ in self.table_area.connections
        ]

    def restore_links(self, links):
        """Draw PK-FK connections given by name, skipping any whose fields are not on the diagram."""
        added = False
        for pk_table, pk_field, fk_table, fk_field in links:
            pk_row = self._find_row(pk_table, pk_field)
            fk_row = self._find_row(fk_table, fk_field)
            if pk_row is None or fk_row is None or pk_row.table_card is fk_row.table_card:
                continue
            if self.table_area.connection_exists(pk_row, fk_row):
                continue
            self.table_area.connections.append((pk_row, fk_row, 'one-to-many'))
            pk_row.add_connection()
            fk_row.add_connection()
            added = True
        if added:
            self.table_area.connections_changed.emit()
        self.table_area.update()

    def _find_row(self, table_name, field_name):
        card = self.cards.get(table_name)
        return card.find_row(field_name) if card else None
