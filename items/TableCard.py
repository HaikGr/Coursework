from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from items.FieldRow import FieldRow

class TableCard(QFrame):
    moved = pyqtSignal()

    def __init__(self, table_name, fields, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.fields = fields
        self.drag_pos = None
        self.is_dragging = False
        self.setFixedSize(200, 300)

        # Separate fields
        self.pk_fields = [f for f in fields if f[3] == "PK"]
        self.fk_fields = [f for f in fields if f[3] == "FK"]
        self.main_fields = [f for f in fields if f[3] not in ("PK","FK")]

        # Row containers
        self.pk_rows = []
        self.fk_rows = []
        self.main_rows = []

        # Card style
        self.setMinimumSize(220, 280)
        self.setMaximumWidth(250)
        self.setStyleSheet("""
            TableCard {
                background-color: #4A5568;
                border-radius: 12px;
                border: none;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0,0,0,120))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)
        self.main_layout.setSpacing(0)

        # Build card sections
        self._build_header()
        self._build_pk_section()
        self._build_fk_section()
        self._build_main_section()
        self._build_footer()
        self._adjust_height()

    # ---------------- HEADER ----------------
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

        status = QLabel("●")
        status.setStyleSheet("color: #48BB78; font-size:16px;")

        layout.addWidget(drag_icon)
        layout.addWidget(table_label)
        layout.addStretch()
        layout.addWidget(status)

        self.main_layout.addWidget(self.header_container)

    def _build_pk_section(self):
        container = QWidget()
        container.setStyleSheet("background-color: #5A6C7D;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)

        if self.pk_fields:
            for field in self.pk_fields:
                row = FieldRow(self, field)
                row.setStyleSheet("""
                    FieldRow {padding:6px 12px; border-bottom:1px solid #4A5568;}
                    FieldRow:hover {background-color:#6B7D8E;}
                """)
                layout.addWidget(row)
                self.pk_rows.append(row)
        else:
            # Hint if empty
            hint = QLabel("No primary keys")
            hint.setStyleSheet("color:#A0AEC0; font-size:11px; padding:6px 12px;")
            layout.addWidget(hint)

        self.main_layout.addWidget(container)

    def _build_fk_section(self):
        container = QWidget()
        container.setStyleSheet("background-color: #5A6C7D;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)

        if self.fk_fields:
            for field in self.fk_fields:
                row = FieldRow(self, field)
                row.setStyleSheet("""
                    FieldRow {padding:6px 12px; border-bottom:1px solid #4A5568;}
                    FieldRow:hover {background-color:#6B7D8E;}
                """)
                layout.addWidget(row)
                self.fk_rows.append(row)
        else:
            # Hint if empty
            hint = QLabel("No foreign keys")
            hint.setStyleSheet("color:#A0AEC0; font-size:11px; padding:6px 12px;")
            layout.addWidget(hint)

        self.main_layout.addWidget(container)

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
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)

        if self.main_fields:
            for field in self.main_fields:
                row = FieldRow(self, field)
                row.setStyleSheet("""
                    FieldRow {padding:6px 12px; border-bottom:1px solid #4A5568;}
                    FieldRow:hover {background-color:#6B7D8E;}
                """)
                layout.addWidget(row)
                self.main_rows.append(row)
        else:
            hint = QLabel("No additional fields")
            hint.setStyleSheet("color:#A0AEC0; font-size:11px; padding:6px 12px;")
            layout.addWidget(hint)

        layout.addStretch()
        scroll.setWidget(content)
        self.main_layout.addWidget(scroll)

    # ---------------- FOOTER ----------------
    def _build_footer(self):
        self.footer = QFrame()
        self.footer.setStyleSheet("""
            QFrame {background-color:#2D3748; border-bottom-left-radius:12px; border-bottom-right-radius:12px;}
        """)
        layout = QHBoxLayout(self.footer)
        layout.setContentsMargins(12,4,12,4)

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

    # ---------------- HEIGHT ADJUST ----------------
    def _adjust_height(self):
        header_h = 40
        footer_h = 30
        pk_h = len(self.pk_fields)*30 if self.pk_fields else 0
        fk_h = len(self.fk_fields)*30 if self.fk_fields else 0
        main_h = min(len(self.main_fields)*30, 180) if self.main_fields else 0
        total_h = header_h + footer_h + pk_h + fk_h + main_h
        self.setFixedHeight(max(total_h, 220))

    # ---------------- UPDATE ----------------
    def update_fields(self, fields):
        # Store old field references and their connections
        old_field_map = {}
        for row in self.pk_rows + self.fk_rows + self.main_rows:
            field_name = row.field_data[0]
            field_type = row.field_data[3] if len(row.field_data) > 3 else ''
            old_field_map[(field_name, field_type)] = row
        
        self.fields = fields
        self.pk_fields = [f for f in fields if f[3]=="PK"]
        self.fk_fields = [f for f in fields if f[3]=="FK"]
        self.main_fields = [f for f in fields if f[3] not in ("PK","FK")]

        # Update connections in canvas before deleting rows
        if hasattr(self, 'canvas') and self.canvas:
            new_connections = []
            for pk_field, fk_field, relation in list(self.canvas.connections):
                # Skip connections from this card's old fields
                if pk_field.table_card == self or fk_field.table_card == self:
                    # Try to find matching new field
                    if pk_field.table_card == self:
                        pk_name = pk_field.field_data[0]
                        pk_type = pk_field.field_data[3] if len(pk_field.field_data) > 3 else ''
                        # Check if field still exists in new fields
                        field_exists = any(f[0] == pk_name and f[3] == pk_type for f in fields)
                        if not field_exists:
                            # Remove connection count from fk_field
                            fk_field.remove_connection()
                            continue
                    
                    if fk_field.table_card == self:
                        fk_name = fk_field.field_data[0]
                        fk_type = fk_field.field_data[3] if len(fk_field.field_data) > 3 else ''
                        # Check if field still exists in new fields
                        field_exists = any(f[0] == fk_name and f[3] == fk_type for f in fields)
                        if not field_exists:
                            # Remove connection count from pk_field
                            pk_field.remove_connection()
                            continue
                
                new_connections.append((pk_field, fk_field, relation))
            
            self.canvas.connections = new_connections

        # Clear old rows
        for row in self.pk_rows + self.fk_rows + self.main_rows:
            row.deleteLater()
        self.pk_rows.clear()
        self.fk_rows.clear()
        self.main_rows.clear()

        # Clear layout
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Rebuild card
        self._build_header()
        self._build_pk_section()
        self._build_fk_section()
        self._build_main_section()
        self._build_footer()
        self._adjust_height()
        
        # Reconnect new fields to canvas
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.update_card_fields(self)
            
            # Restore connections with new field references
            updated_connections = []
            for pk_field, fk_field, relation in self.canvas.connections:
                new_pk = pk_field
                new_fk = fk_field
                
                # If pk_field is from this card, find new reference
                if pk_field.table_card == self:
                    pk_name = pk_field.field_data[0]
                    pk_type = pk_field.field_data[3] if len(pk_field.field_data) > 3 else ''
                    # Find new field row with same name and type
                    for row in self.pk_rows + self.fk_rows + self.main_rows:
                        if (row.field_data[0] == pk_name and 
                            (row.field_data[3] if len(row.field_data) > 3 else '') == pk_type):
                            new_pk = row
                            row.connection_count = pk_field.connection_count
                            row.add_connection()
                            break
                
                # If fk_field is from this card, find new reference
                if fk_field.table_card == self:
                    fk_name = fk_field.field_data[0]
                    fk_type = fk_field.field_data[3] if len(fk_field.field_data) > 3 else ''
                    # Find new field row with same name and type
                    for row in self.pk_rows + self.fk_rows + self.main_rows:
                        if (row.field_data[0] == fk_name and 
                            (row.field_data[3] if len(row.field_data) > 3 else '') == fk_type):
                            new_fk = row
                            row.connection_count = fk_field.connection_count
                            row.add_connection()
                            break
                
                updated_connections.append((new_pk, new_fk, relation))
            
            self.canvas.connections = updated_connections
            self.canvas.update()
        
        self.moved.emit()

    # ---------------- DRAG - ONLY FROM HEADER/FOOTER ----------------
    def is_click_on_draggable_area(self, pos):
        """Check if click is on header or footer (draggable areas)"""
        # Check if click is on header
        if hasattr(self, 'header_container'):
            header_rect = self.header_container.geometry()
            if header_rect.contains(pos):
                return True
        
        # Check if click is on footer
        if hasattr(self, 'footer'):
            footer_rect = self.footer.geometry()
            if footer_rect.contains(pos):
                return True
        
        return False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Only start dragging if clicked on header or footer
            if self.is_click_on_draggable_area(event.pos()):
                self.drag_pos = event.globalPosition().toPoint() - self.pos()
                self.is_dragging = True
                self.raise_()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        
        # Let the event propagate to child widgets (FieldRows)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_dragging and self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            self.move(int(new_pos.x()), int(new_pos.y()))
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