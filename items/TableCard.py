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
        header_container = QFrame()
        header_container.setStyleSheet("""
            QFrame {
                background-color: #2D3748;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
        """)
        layout = QHBoxLayout(header_container)
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

        self.main_layout.addWidget(header_container)

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


    # Inside _build_fk_section
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


    # Inside _build_main_section
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
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {background-color:#2D3748; border-bottom-left-radius:12px; border-bottom-right-radius:12px;}
        """)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(12,4,12,4)

        total_fields = len(self.fields)
        count_label = QLabel(f"{total_fields} field{'s' if total_fields != 1 else ''}")
        count_label.setStyleSheet("color:#A0AEC0; font-size:11px;")

        action_label = QLabel("Click to select")
        action_label.setStyleSheet("color:#718096; font-size:11px;")
        action_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(count_label)
        layout.addStretch()
        layout.addWidget(action_label)

        self.main_layout.addWidget(footer)

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
        self.fields = fields
        self.pk_fields = [f for f in fields if f[3]=="PK"]
        self.fk_fields = [f for f in fields if f[3]=="FK"]
        self.main_fields = [f for f in fields if f[3] not in ("PK","FK")]

        # Clear old rows and layout
        for row in self.pk_rows + self.fk_rows + self.main_rows:
            row.deleteLater()
        self.pk_rows.clear()
        self.fk_rows.clear()
        self.main_rows.clear()

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
        self.moved.emit()

    # ---------------- DRAG ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()
            self.raise_()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            self.move(int(new_pos.x()), int(new_pos.y()))
            self.moved.emit()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)
