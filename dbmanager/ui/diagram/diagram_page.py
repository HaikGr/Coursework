from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QLabel, QMenu, QScrollArea, QVBoxLayout, QWidget

from dbmanager.model.links import plan_link
from dbmanager.ui.common.style import MENU_STYLE
from dbmanager.ui.diagram.diagram_canvas import DiagramCanvas, link_end
from dbmanager.ui.diagram.table_card import TableCard
from dbmanager.ui.query.field_tag import aggregate_menu

FIRST_X, FIRST_Y = 120, 80
STEP_X, STEP_Y, LAST_X = 240, 320, 1000
_SORTS = [(None, "Not sorted"), ("ASC", "Smallest first (A → Z, 1 → 9)"), ("DESC", "Largest first (Z → A, 9 → 1)")]


def _type_of(row):
    return row.field_data[1] if len(row.field_data) > 1 and row.field_data[1] not in (None, "-") else ""


class DiagramPage(QWidget):
    """The tables of the active database as cards; links drawn here become JOINs and foreign keys.

    The query lives in the SQL builder; each field row shows whether it is in it or filtered by it, and its
    menu changes it. is_saved_link (set by the sidebar) tells a link the database already has as a foreign key
    from one only drawn so far; can_change_structure, whether the user may drop tables and fields here (the
    owner of the database) - the sidebar does that when asked."""
    open_table_requested = pyqtSignal(str)
    drop_table_requested = pyqtSignal(str)
    delete_field_requested = pyqtSignal(str, str)  # table, field

    def __init__(self, sql_builder=None):
        super().__init__()
        self.sql_builder = sql_builder
        self.is_saved_link = lambda link: False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self.sql_builder:
            self.sql_builder.query_changed.connect(self._sync_rows)
            self.sql_builder.table_columns = self.table_columns  # what Join… offers

        self.table_area = DiagramCanvas()
        self.table_area.reset_size()
        self.table_area.connections_changed.connect(self._on_connections_changed)
        self.table_area.link_message.connect(self.show_notice)

        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setWidget(self.table_area)
        canvas_scroll.setStyleSheet("QWidget { border: none; background-color: #f5f6f7; }")
        layout.addWidget(canvas_scroll)

        self.cards = {}
        self._x, self._y = FIRST_X, FIRST_Y
        self.can_change_structure = True

        # What happened to a link, over the top of the diagram for a few seconds
        self.notice = QLabel(self)
        self.notice.setWordWrap(True)
        self.notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notice.hide()
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.timeout.connect(self.notice.hide)

    @property
    def can_change_structure(self):
        return self.table_area.links_enabled

    @can_change_structure.setter
    def can_change_structure(self, allowed):
        """The owner may drop tables and fields, and link tables (which adds a foreign key); a guest may not"""
        self.table_area.links_enabled = allowed

    def show_notice(self, text, done=False):
        colors = ("#14532d", "#bbf7d0", "#22c55e") if done else ("#422006", "#fde68a", "#f59e0b")
        self.notice.setStyleSheet(f"QLabel {{ background-color: {colors[0]}; color: {colors[1]}; "
                                  f"border: 1px solid {colors[2]}; border-radius: 8px; padding: 8px 14px; "
                                  "font-size: 12px; }")
        self.notice.setText(text)
        self._place_notice()
        self.notice.show()
        self.notice.raise_()
        self._notice_timer.start(6000 if done else 9000)

    def _place_notice(self):
        width = min(620, self.width() - 40)
        self.notice.setFixedWidth(max(width, 200))
        self.notice.adjustSize()
        self.notice.move((self.width() - self.notice.width()) // 2, 14)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.notice.isVisible():
            self._place_notice()

    def table_columns(self):
        """{table: [(field, type), ...]} of the tables on the diagram"""
        return {name: [(field[0], field[1] if len(field) > 1 else "") for field in card.fields]
                for name, card in self.cards.items()}

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
            self._connect_card(card)
            return

        card = TableCard(table_name, columns, parent=self.table_area)
        card.menu_requested.connect(self._open_card_menu)
        self.cards[table_name] = card
        card.move(self._x, self._y)
        card.show()
        self.table_area.add_card(card)
        self._connect_card(card)

        self._x += STEP_X
        if self._x > LAST_X:
            self._x = FIRST_X
            self._y += STEP_Y

    def rename_field(self, table_name, old_name, new_name, columns):
        """Refresh a card after a field rename, keeping the links drawn to that field and its place in the query."""
        if self.sql_builder:
            self.sql_builder.rename_column(table_name, old_name, new_name)
        if table_name in self.cards:
            self.add_table_card(table_name, columns, renamed={old_name: new_name})

    def remove_field_from_card(self, table_name, columns):
        card = self.cards.get(table_name)
        if card is None:
            return
        if self.sql_builder:
            kept = {column[0] for column in columns}
            for field in card.fields:
                if field[0] not in kept:
                    self.sql_builder.drop_column(table_name, field[0])
        card.update_fields(columns)
        self._connect_card(card)
        self.table_area.update()

    def remove_table_card(self, table_name):
        """Take a card (and its links) off the diagram. The query is left alone: the table may only be
        drawn again - the sidebar tells the query builder when a table is really gone."""
        card = self.cards.pop(table_name, None)
        if card is None:
            return
        self.table_area.remove_card(card)
        card.dispose()
        card.setParent(None)
        card.deleteLater()
        self.table_area.update()

    def clear_diagram(self):
        """Remove every card (another database is selected, or this one is drawn again). The query stays:
        the sidebar clears it when the database changes."""
        for table_name in list(self.cards):
            self.remove_table_card(table_name)
        self._x, self._y = FIRST_X, FIRST_Y
        self.table_area.reset_size()

    # ---------------- Query builder sync ----------------
    def _connect_card(self, card):
        if not self.sql_builder:
            return
        for row in card.all_rows():
            for signal in (row.query_toggle_requested, row.menu_requested):
                try:
                    signal.disconnect()
                except TypeError:
                    pass  # nothing connected yet
            row.query_toggle_requested.connect(self._on_query_toggle)
            row.menu_requested.connect(self._open_field_menu)
        self._sync_card(card)

    def _sync_rows(self):
        for card in self.cards.values():
            self._sync_card(card)
        self._sync_query_joins()

    def _sync_query_joins(self):
        """Draw the joins made for the query only, between the rows they join"""
        joins = []
        for join in self.sql_builder.model.joins if self.sql_builder else []:
            left, right = self._find_row(join.left_table, join.left_column), self._find_row(join.right_table,
                                                                                           join.right_column)
            if left is not None and right is not None:
                joins.append((left, right))
        self.table_area.query_joins = joins
        self.table_area.update()

    def _sync_card(self, card):
        """Mark the rows the query uses: in it (green), filtered by it (funnel)"""
        if not self.sql_builder:
            return
        model = self.sql_builder.model
        for row in card.all_rows():
            name = row.field_data[0]
            row.set_query_selection(model.column(card.table_name, name) is not None)
            row.set_filtered([condition.describe() for condition in model.filters_on(card.table_name, name)])

    def _on_query_toggle(self, row):
        """The circle at the end of a row: put the field in the query, or take it out again."""
        if self.sql_builder:
            self.sql_builder.toggle_field(row.table_card.table_name, row.field_data[0], _type_of(row))

    def card_menu(self, card):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        menu.addAction("Open table").triggered.connect(lambda: self.open_table_requested.emit(card.table_name))
        if self.can_change_structure:
            menu.addSeparator()
            menu.addAction("Drop table…").triggered.connect(lambda: self.drop_table_requested.emit(card.table_name))
        return menu

    def _open_card_menu(self, card, position):
        self.card_menu(card).exec(position)

    def _open_field_menu(self, row, position):
        menu = self.field_menu(row)
        if menu is not None:
            menu.exec(position)

    def field_menu(self, row):
        """Everything the query can do with a field: add or remove it, summarise it, sort by it, filter by it;
        and the links drawn to it"""
        if not self.sql_builder:
            return None
        builder = self.sql_builder
        table, name, type_name = row.table_card.table_name, row.field_data[0], _type_of(row)
        entry = builder.model.column(table, name)

        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        menu.setToolTipsVisible(True)
        if entry is None:
            menu.addAction("Add to query").triggered.connect(lambda: builder.add_field(table, name, type_name))
        else:
            menu.addAction("Remove from query").triggered.connect(lambda: builder.remove_field(table, name))

        summarize = aggregate_menu(menu, f"{table}.{name}", type_name, entry.aggregate if entry else None)
        summarize.setTitle("Summarize")
        summarize.triggered.connect(
            lambda action: builder.set_column_aggregate(table, name, action.data(), type_name))
        menu.addMenu(summarize)

        sort = menu.addMenu("Sort")
        sort.setStyleSheet(MENU_STYLE)
        for direction, text in _SORTS:
            action = QAction(text, sort)
            action.setCheckable(True)
            action.setChecked((entry.sort if entry else None) == direction)
            action.triggered.connect(lambda checked=False, d=direction: builder.set_column_sort(table, name, d, type_name))
            sort.addAction(action)

        menu.addSeparator()
        menu.addAction("Add filter…").triggered.connect(lambda: builder.edit_filter(table, name, type_name))
        for index, condition in enumerate(builder.model.filters):
            if condition.key == (table, name):
                action = menu.addAction(f"Change filter: {condition.describe()}")
                action.triggered.connect(lambda checked=False, i=index: builder.edit_filter(table, name, type_name, i))
        if builder.model.filters_on(table, name):
            menu.addAction("Remove its filters").triggered.connect(lambda: builder.remove_filters_on(table, name))

        links = [connection for connection in self.table_area.connections if row in connection[:2]]
        if links:
            menu.addSeparator()
        for connection in links:
            pk, fk, _ = connection
            other = fk if pk is row else pk
            target = f"{other.table_card.table_name}.{other.field_data[0]}"
            link = (pk.table_card.table_name, pk.field_data[0], fk.table_card.table_name, fk.field_data[0])
            if self.is_saved_link(link):
                action = menu.addAction(f"Linked to {target} by a foreign key")
                action.setEnabled(False)
            else:
                action = menu.addAction(f"Remove link to {target}")
                action.setToolTip("Drawn but not saved yet: the FOREIGN KEY it would add goes too")
                action.triggered.connect(lambda checked=False, c=connection: self.table_area.remove_connection(c))
        if self.can_change_structure:
            link_to = self._link_menu(row)
            if link_to is not None:
                if not links:
                    menu.addSeparator()
                menu.addMenu(link_to)
            menu.addSeparator()
            menu.addAction("Delete field…").triggered.connect(lambda: self.delete_field_requested.emit(table, name))
        return menu

    def _link_menu(self, row):
        """Link to ▸ table ▸ field: the fields of the other tables this one can be linked to - without dragging"""
        menu = QMenu("Link to", self)
        menu.setStyleSheet(MENU_STYLE)
        source = link_end(row)
        for table_name, card in self.cards.items():
            if card is row.table_card:
                continue
            candidates = [other for other in card.all_rows()
                          if isinstance(plan_link(source, link_end(other)), tuple)
                          and not self.table_area.connection_exists(row, other)]
            if not candidates:
                continue
            submenu = menu.addMenu(table_name)
            submenu.setStyleSheet(MENU_STYLE)
            for other in candidates:
                end = link_end(other)
                text = f"{end.field}  ({'primary key' if end.primary else end.type_name or 'field'})"
                submenu.addAction(text).triggered.connect(
                    lambda checked=False, target=other: self.table_area.link(row, target))
        return menu if menu.actions() else None

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
