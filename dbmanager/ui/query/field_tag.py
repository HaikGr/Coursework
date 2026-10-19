from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class SelectedFieldTag(QFrame):
    """A compact tag widget showing a selected field"""
    removed = pyqtSignal(object)
    group_by_toggled = pyqtSignal(object)
    order_by_toggled = pyqtSignal(object, str)  # tag, direction (ASC/DESC/None)

    def __init__(self, table_name, field_name, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.field_name = field_name
        self.is_grouped = False
        self.order_direction = None  # None, "ASC", "DESC"
        self.aggregate = None  # None, "SUM", "AVG", etc.

        self.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 6px;
                border: 1px solid #334155;
            }
        """)
        self.setFixedHeight(34)  # More compact

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 6, 4)
        layout.setSpacing(4)

        # Field label
        self.field_text = QLabel(f"{table_name}.<b>{field_name}</b>")
        self.field_text.setStyleSheet("color: #e2e8f0; font-size: 11px; background: transparent;")
        layout.addWidget(self.field_text)
        layout.addStretch()

        # GROUP BY button
        self.group_btn = QPushButton("GRP")
        self.group_btn.setFixedSize(32, 20)
        self.group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.group_btn.setToolTip("Toggle GROUP BY")
        self._update_group_style()
        self.group_btn.clicked.connect(self.toggle_group_by)
        layout.addWidget(self.group_btn)

        # ORDER BY button
        self.order_btn = QPushButton("↕")
        self.order_btn.setFixedSize(20, 20)
        self.order_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.order_btn.setToolTip("Toggle ORDER BY (ASC/DESC)")
        self._update_order_style()
        self.order_btn.clicked.connect(self.toggle_order_by)
        layout.addWidget(self.order_btn)

        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setToolTip("Remove field")
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: #fca5a5;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #991b1b;
            }
        """)
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(remove_btn)

    def _update_group_style(self):
        if self.is_grouped:
            self.group_btn.setStyleSheet("""
                QPushButton {
                    background-color: #22c55e;
                    color: #052e16;
                    border: none;
                    border-radius: 3px;
                    font-size: 9px;
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #16a34a; }
            """)
        else:
            self.group_btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    color: #94a3b8;
                    border: none;
                    border-radius: 3px;
                    font-size: 9px;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #475569; }
            """)

    def _update_order_style(self):
        if self.order_direction == "ASC":
            self.order_btn.setText("↑")
            self.order_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f59e0b;
                    color: #451a03;
                    border: none;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #d97706; }
            """)
        elif self.order_direction == "DESC":
            self.order_btn.setText("↓")
            self.order_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #dc2626; }
            """)
        else:
            self.order_btn.setText("↕")
            self.order_btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    color: #94a3b8;
                    border: none;
                    border-radius: 3px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #475569; }
            """)

    def toggle_group_by(self):
        self.is_grouped = not self.is_grouped
        self._update_group_style()
        self.group_by_toggled.emit(self)

    def toggle_order_by(self):
        # Cycle: None -> ASC -> DESC -> None
        if self.order_direction is None:
            self.order_direction = "ASC"
        elif self.order_direction == "ASC":
            self.order_direction = "DESC"
        else:
            self.order_direction = None
        self._update_order_style()
        self.order_by_toggled.emit(self, self.order_direction)

    def set_aggregate(self, agg_type):
        """Set aggregate function for this field"""
        self.aggregate = agg_type
        if agg_type:
            self.field_text.setText(f"<span style='color:#fbbf24;'>{agg_type}</span>({self.table_name}.<b>{self.field_name}</b>)")
        else:
            self.field_text.setText(f"{self.table_name}.<b>{self.field_name}</b>")
