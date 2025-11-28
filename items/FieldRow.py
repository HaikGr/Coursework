from PyQt6.QtWidgets import QFrame, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

class FieldRow(QFrame):
    clicked = pyqtSignal(object)
    
    def __init__(self, table_card, field_data):
        super().__init__(table_card)
        self.table_card = table_card
        self.field_data = field_data
        self.is_connection_source = False
        self.is_connection_target = False

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

    def _update_style(self):
        base_style = """
            QFrame { background-color: transparent; border-radius: 4px; }
            QLabel { color: #E0E0E0; padding-left: 4px; font-size: 12px; background: transparent; }
        """
        
        if self.is_connection_source:
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
        self.is_connection_source = is_source
        self.is_connection_target = is_target
        
        if is_source:
            self.dot_label.setStyleSheet("color: #69a7ff; font-size: 10px; background: transparent;")
        elif is_target:
            self.dot_label.setStyleSheet("color: #FFD57F; font-size: 10px; background: transparent;")
        else:
            self.dot_label.setStyleSheet("color: transparent; font-size: 10px; background: transparent;")
        
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

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
