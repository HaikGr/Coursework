from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from items.FieldRow import FieldRow

class TableCard(QFrame):
    moved = pyqtSignal()

    def __init__(self, table_name, fields, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.fields = fields
        self.drag_pos = None

        self.setFixedSize(280, 360)

        # Separate fields
        self.pk_fields = [f for f in fields if f[3] == "PK"]
        self.fk_fields = [f for f in fields if f[3] == "FK"]
        self.main_fields = [f for f in fields if f[3] not in ("PK","FK")]

        self.pk_rows = []
        self.fk_rows = []
        self.main_rows = []

        self.setStyleSheet("""
            QFrame { background-color: #2E3641; border-radius: 10px; border: 1px solid #4A4F55; }
            QLabel { color: white; font-size: 14px; }
        """)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6,6,6,6)
        self.main_layout.setSpacing(6)

        self._build_header()
        self._build_pk_section()
        self._build_fk_section()
        self._build_main_fields_section()
        self.load_fields()

    def _build_header(self):
        header_layout = QHBoxLayout()
        title = QLabel(self.table_name)
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.main_layout.addLayout(header_layout)

    def _build_pk_section(self):
        self.pk_label = QLabel("Primary Keys")
        self.pk_label.setStyleSheet("font-weight: bold; color: #2ecc71;")
        self.main_layout.addWidget(self.pk_label)

        self.pk_container_widget = QWidget()
        self.pk_layout = QVBoxLayout(self.pk_container_widget)
        self.pk_layout.setContentsMargins(0,0,0,0)
        self.pk_layout.setSpacing(2)
        self.main_layout.addWidget(self.pk_container_widget)

    def _build_fk_section(self):
        self.fk_label = QLabel("Foreign Keys")
        self.fk_label.setStyleSheet("font-weight: bold; color: #FFD57F;")
        self.main_layout.addWidget(self.fk_label)

        self.fk_container_widget = QWidget()
        self.fk_layout = QVBoxLayout(self.fk_container_widget)
        self.fk_layout.setContentsMargins(0,0,0,0)
        self.fk_layout.setSpacing(2)
        self.main_layout.addWidget(self.fk_container_widget)

    def _build_main_fields_section(self):
        self.fields_label = QLabel("Fields")
        self.fields_label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
        self.main_layout.addWidget(self.fields_label)

        self.scroll = QScrollArea()
        self.scroll.setFixedHeight(180)
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background-color: #485262; border: none;")

        self.main_widget = QWidget()
        self.main_layout_scroll = QVBoxLayout(self.main_widget)
        self.main_layout_scroll.setContentsMargins(0,0,0,0)
        self.main_layout_scroll.setSpacing(2)
        self.main_layout_scroll.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.main_widget)
        self.main_layout.addWidget(self.scroll)

    def load_fields(self):
        for l in [self.pk_rows, self.fk_rows, self.main_rows]:
            for r in l:
                r.deleteLater()
        self.pk_rows.clear()
        self.fk_rows.clear()
        self.main_rows.clear()

        # PK
        for f in self.pk_fields:
            row = FieldRow(self, f)
            self.pk_layout.addWidget(row)
            self.pk_rows.append(row)

        # FK
        for f in self.fk_fields:
            row = FieldRow(self, f)
            self.fk_layout.addWidget(row)
            self.fk_rows.append(row)

        # Main fields
        for f in self.main_fields:
            row = FieldRow(self, f)
            self.main_layout_scroll.addWidget(row)
            self.main_rows.append(row)
        self.main_layout_scroll.addStretch()

    def update_fields(self, fields):
        self.fields = fields
        self.pk_fields = [f for f in fields if f[3] == "PK"]
        self.fk_fields = [f for f in fields if f[3] == "FK"]
        self.main_fields = [f for f in fields if f[3] not in ("PK","FK")]
        self.load_fields()
        self.moved.emit()

    # Dragging
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()
            self.raise_()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            self.move(int(new_pos.x()), int(new_pos.y()))
            self.moved.emit()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        super().mouseReleaseEvent(event)
