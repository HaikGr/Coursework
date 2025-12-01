from PyQt6.QtWidgets import QFrame, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

class FieldRow(QFrame):
    clicked = pyqtSignal(object)
    selected_for_query = pyqtSignal(str, str, str)  # table_name, field_name, field_type

    def __init__(self, table_card, field_data):
        super().__init__(table_card)
        self.table_card = table_card
        self.field_data = field_data
        self.connection_count = 0  # Track number of connections
        self.is_connection_source = False
        self.is_connection_target = False
        self.is_selected_for_query = False

        self.setFixedHeight(28)
        self._update_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)

        # Connection dot indicator
        self.dot_label = QLabel("●")
        self.dot_label.setFixedWidth(12)
        self.dot_label.setStyleSheet("color: transparent; font-size: 10px; background: transparent;")
        layout.addWidget(self.dot_label)

        # Field name
        field_name = field_data[0]
        self.label = QLabel(field_name)
        layout.addWidget(self.label)
        layout.addStretch()

        # Field type indicator
        field_type = field_data[3] if len(field_data) > 3 else ""
        if field_type == "PK":
            type_label = QLabel("🔑")
            type_label.setStyleSheet("font-size: 11px; background: transparent;")
            layout.addWidget(type_label)
        elif field_type == "FK":
            type_label = QLabel("🔗")
            type_label.setStyleSheet("font-size: 11px; background: transparent;")
            layout.addWidget(type_label)

        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)

    def _update_style(self):
        base_style = """
            QFrame { background-color: transparent; border-radius: 4px; }
            QLabel { color: #E0E0E0; padding-left: 4px; font-size: 12px; background: transparent; }
        """

        if self.is_selected_for_query:
            base_style = """
                QFrame {
                    background-color: rgba(124, 58, 237, 0.4);
                    border-radius: 4px;
                    border-left: 3px solid #7C3AED;
                }
                QLabel { color: #FFFFFF; padding-left: 4px; font-size: 12px; background: transparent; }
            """
        elif self.is_connection_source:
            base_style = """
                QFrame {
                    background-color: rgba(106, 167, 255, 0.3);
                    border-radius: 4px;
                    border-left: 3px solid #69a7ff;
                }
                QLabel { color: #FFFFFF; padding-left: 4px; font-size: 12px; background: transparent; }
            """
        elif self.is_connection_target:
            base_style = """
                QFrame {
                    background-color: rgba(255, 213, 127, 0.3);
                    border-radius: 4px;
                    border-left: 3px solid #FFD57F;
                }
                QLabel { color: #FFFFFF; padding-left: 4px; font-size: 12px; background: transparent; }
            """

        self.setStyleSheet(base_style)

    def set_connection_role(self, is_source=False, is_target=False):
        """Set the visual connection role (for temporary selection during drag)"""
        self.is_connection_source = is_source
        self.is_connection_target = is_target

        if is_source:
            self.dot_label.setStyleSheet("color: #69a7ff; font-size: 10px; background: transparent;")
        elif is_target:
            self.dot_label.setStyleSheet("color: #FFD57F; font-size: 10px; background: transparent;")
        else:
            # Only clear dot if no connections exist
            if self.connection_count == 0:
                self.dot_label.setStyleSheet("color: transparent; font-size: 10px; background: transparent;")

        self._update_style()

    def add_connection(self):
        """Increment connection count and update visuals"""
        self.connection_count += 1
        field_type = self.field_data[3] if len(self.field_data) > 3 else ''
        
        if field_type == 'PK':
            self.dot_label.setStyleSheet("color: #69a7ff; font-size: 10px; background: transparent;")
        elif field_type == 'FK':
            self.dot_label.setStyleSheet("color: #FFD57F; font-size: 10px; background: transparent;")

    def remove_connection(self):
        """Decrement connection count and update visuals"""
        self.connection_count = max(0, self.connection_count - 1)
        
        if self.connection_count == 0:
            self.dot_label.setStyleSheet("color: transparent; font-size: 10px; background: transparent;")
            self.is_connection_source = False
            self.is_connection_target = False
            self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Left click - for connections
            self.clicked.emit(self)
            event.accept()
            return
        elif event.button() == Qt.MouseButton.RightButton:
            # Right click - for SQL query builder
            table_name = self.table_card.table_name
            field_name = self.field_data[0]
            field_type = self.field_data[3] if len(self.field_data) > 3 else ''
            
            self.is_selected_for_query = not self.is_selected_for_query
            self._update_style()
            
            self.selected_for_query.emit(table_name, field_name, field_type)
            event.accept()
            return
        super().mousePressEvent(event)

    def set_query_selection(self, selected):
        """Set whether this field is selected for query building"""
        self.is_selected_for_query = selected
        self._update_style()

    def enterEvent(self, event):
        if not self.is_connection_source and not self.is_connection_target:
            self.setStyleSheet("""
                QFrame {
                    background-color: rgba(107, 125, 142, 0.5);
                    border-radius: 4px;
                }
                QLabel { color: #FFFFFF; padding-left: 4px; font-size: 12px; background: transparent; }
            """)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_connection_source and not self.is_connection_target:
            self._update_style()
        super().leaveEvent(event)