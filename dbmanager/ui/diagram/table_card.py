from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from dbmanager.ui.diagram.field_row import FieldRow, key_flag

HINT_STYLE = "color:#A0AEC0; font-size:11px; padding:6px 12px;"


class TableCard(QFrame):
    """A table on the diagram: header, primary keys, foreign keys, the other fields, footer.
    Dragged by its header or footer."""
    moved = pyqtSignal()

    def __init__(self, table_name, fields, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.canvas = None  # set by DiagramCanvas.add_card
        self.drag_pos = None
        self.is_dragging = False
        self.pk_rows = []
        self.fk_rows = []
        self.main_rows = []
        self._set_fields(fields)

        self.setFixedSize(200, 300)
        self.setMinimumSize(220, 280)
        self.setMaximumWidth(250)
        self.setStyleSheet("""
            TableCard {
                background-color: #4A5568;
                border-radius: 12px;
                border: none;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self._build()

    def _set_fields(self, fields):
        self.fields = fields
        self.pk_fields = [f for f in fields if key_flag(f) == "PK"]
        self.fk_fields = [f for f in fields if key_flag(f) == "FK"]
        self.main_fields = [f for f in fields if key_flag(f) not in ("PK", "FK")]

    def all_rows(self):
        return self.pk_rows + self.fk_rows + self.main_rows

    def find_row(self, field_name):
        return next((row for row in self.all_rows() if row.field_data[0] == field_name), None)

    # ---------------- Building ----------------
    def _build(self):
        self._build_header()
        self.pk_rows = self._build_rows_section(self.pk_fields, "No primary keys")
        self.fk_rows = self._build_rows_section(self.fk_fields, "No foreign keys")
        self.main_rows = self._build_main_section()
        self._build_footer()
        self._adjust_height()

    def _build_header(self):
        self.header_container = QFrame()
        self.header_container.setStyleSheet("""
            QFrame {
                background-color: #2D3748;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
        """)
        layout = QHBoxLayout(self.header_container)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        drag_icon = QLabel("⋮⋮")
        drag_icon.setStyleSheet("color: #718096; font-weight:bold; font-size:14px;")
        table_label = QLabel(self.table_name)
        table_label.setStyleSheet("color: #FFFFFF; font-weight:600; font-size:13px;")
        table_label.setToolTip(self.table_name)
        status = QLabel("●")
        status.setStyleSheet("color: #48BB78; font-size:16px;")

        layout.addWidget(drag_icon)
        layout.addWidget(table_label)
        layout.addStretch()
        layout.addWidget(status)
        self.main_layout.addWidget(self.header_container)

    def _add_rows(self, layout, fields, empty_hint):
        rows = []
        for field in fields:
            row = FieldRow(self, field)
            layout.addWidget(row)
            rows.append(row)
        if not fields:
            hint = QLabel(empty_hint)
            hint.setStyleSheet(HINT_STYLE)
            layout.addWidget(hint)
        return rows

    def _build_rows_section(self, fields, empty_hint):
        container = QWidget()
        container.setStyleSheet("background-color: #5A6C7D;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        rows = self._add_rows(layout, fields, empty_hint)
        self.main_layout.addWidget(container)
        return rows

    def _build_main_section(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(60)
        scroll.setMaximumHeight(180)
        scroll.setStyleSheet("""
            QScrollArea {border:none; background-color:#5A6C7D;}
            QScrollBar:vertical {width:6px; background:transparent; margin:0px;}
            QScrollBar::handle:vertical {background:#718096; border-radius:3px; min-height:20px;}
            QScrollBar::handle:vertical:hover {background:#8A95A5;}
        """)
        content = QWidget()
        content.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        rows = self._add_rows(layout, self.main_fields, "No additional fields")
        layout.addStretch()
        scroll.setWidget(content)
        self.main_layout.addWidget(scroll)
        return rows

    def _build_footer(self):
        self.footer = QFrame()
        self.footer.setStyleSheet("""
            QFrame {background-color:#2D3748; border-bottom-left-radius:12px; border-bottom-right-radius:12px;}
        """)
        layout = QHBoxLayout(self.footer)
        layout.setContentsMargins(12, 4, 12, 4)

        total_fields = len(self.fields)
        count_label = QLabel(f"{total_fields} field{'s' if total_fields != 1 else ''}")
        count_label.setStyleSheet("color:#A0AEC0; font-size:11px;")
        action_label = QLabel("Drag here to move")
        action_label.setStyleSheet("color:#718096; font-size:11px;")
        action_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(count_label)
        layout.addStretch()
        layout.addWidget(action_label)
        self.main_layout.addWidget(self.footer)

    def _adjust_height(self):
        header_h, footer_h = 40, 30
        pk_h = len(self.pk_fields) * 30
        fk_h = len(self.fk_fields) * 30
        main_h = min(len(self.main_fields) * 30, 180)
        self.setFixedHeight(max(header_h + footer_h + pk_h + fk_h + main_h, 220))

    # ---------------- Update ----------------
    def update_fields(self, fields, renamed=None):
        """Rebuild the rows for a new list of fields. Links drawn to fields that still exist (by name and
        key flag) are kept, as is their "selected for query" mark; links to removed fields are dropped.
        renamed: {old name: new name} for fields renamed since the last update."""
        renamed = renamed or {}

        def key_after(row):
            name = row.field_data[0]
            return renamed.get(name, name), key_flag(row.field_data)

        new_keys = {(field[0], key_flag(field)) for field in fields}
        old_rows = self.all_rows()
        old_state = {key_after(row): (row.connection_count, row.is_selected_for_query) for row in old_rows}

        kept, touched = [], False
        if self.canvas:
            for pk_row, fk_row, relation in self.canvas.connections:
                own = [row for row in (pk_row, fk_row) if row.table_card is self]
                if not own:
                    kept.append((pk_row, fk_row, relation))
                    continue
                touched = True
                if all(key_after(row) in new_keys for row in own):
                    kept.append((key_after(pk_row) if pk_row.table_card is self else pk_row,
                                 key_after(fk_row) if fk_row.table_card is self else fk_row, relation))
                else:
                    for row in (pk_row, fk_row):
                        if row.table_card is not self:
                            row.remove_connection()

        # Throw the old widgets away and build new ones
        for row in old_rows:
            row.dispose()
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._set_fields(fields)
        self._build()

        new_rows = {(row.field_data[0], key_flag(row.field_data)): row for row in self.all_rows()}
        for key, (count, selected) in old_state.items():
            row = new_rows.get(key)
            if row is not None:
                row.connection_count = count
                row.set_query_selection(selected)

        if self.canvas:
            # kept entries hold a (name, flag) key in place of this card's old rows
            self.canvas.connections = [
                (new_rows[pk] if isinstance(pk, tuple) else pk, new_rows[fk] if isinstance(fk, tuple) else fk, rel)
                for pk, fk, rel in kept
            ]
            self.canvas.update_card_fields(self)
            if touched:
                self.canvas.connections_changed.emit()
            self.canvas.update()
        self.moved.emit()

    def dispose(self):
        for row in self.all_rows():
            row.dispose()

    # ---------------- Drag - only from header/footer ----------------
    def is_click_on_draggable_area(self, pos):
        return self.header_container.geometry().contains(pos) or self.footer.geometry().contains(pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_click_on_draggable_area(event.pos()):
            self.drag_pos = event.globalPosition().toPoint() - self.pos()
            self.is_dragging = True
            self.raise_()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        # Let the event reach the field rows
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_dragging and self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            # Keep the card on the canvas: one dragged past the top/left edge could not be reached again
            self.move(max(0, new_pos.x()), max(0, new_pos.y()))
            self.moved.emit()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_dragging:
            self.is_dragging = False
            self.drag_pos = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
