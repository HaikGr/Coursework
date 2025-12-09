from PyQt6.QtWidgets import QFrame, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint

from items.ConditionPopup import ConditionPopup


class FieldRow(QFrame):
    clicked = pyqtSignal(object)
    selected_for_query = pyqtSignal(str, str, str)  # table_name, field_name, field_type
    condition_added = pyqtSignal(str, str, str)  # table_name, field_name, condition

    def __init__(self, table_card, field_data):
        super().__init__(table_card)
        self.table_card = table_card
        self.field_data = field_data
        self.connection_count = 0
        self.is_connection_source = False
        self.is_connection_target = False
        self.is_selected_for_query = False
        
        # Popup for WHERE conditions
        self.popup = None
        self.hover_timer = QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self._show_popup)
        self.is_mouse_over = False

        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        # Field type icon (PK/FK)
        field_type = field_data[3] if len(field_data) > 3 else ""
        if field_type == "PK":
            type_icon = QLabel("🔑")
            type_icon.setStyleSheet("font-size: 10px; background: transparent;")
            type_icon.setFixedWidth(16)
            layout.addWidget(type_icon)

        # Field name
        field_name = field_data[0]
        self.label = QLabel(field_name)
        self.label.setStyleSheet("color: #E0E0E0; font-size: 12px; background: transparent;")
        layout.addWidget(self.label)
        layout.addStretch()

        # Selection indicator (green glowing circle)
        self.select_indicator = QLabel("●")
        self.select_indicator.setFixedWidth(20)
        self.select_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.select_indicator.setStyleSheet("color: transparent; font-size: 12px; background: transparent;")
        layout.addWidget(self.select_indicator)

        # Now apply initial style after all widgets are created
        self._update_style()

        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)

    def _update_indicator(self):
        """Update the selection indicator style"""
        if self.is_selected_for_query:
            # Bright green glowing circle when selected for query
            self.select_indicator.setText("●")
            self.select_indicator.setStyleSheet("""
                QLabel {
                    color: #22c55e;
                    font-size: 16px;
                    background: transparent;
                }
            """)
        elif self.connection_count > 0:
            # Show connection indicator
            field_type = self.field_data[3] if len(self.field_data) > 3 else ''
            self.select_indicator.setText("●")
            if field_type == 'PK':
                self.select_indicator.setStyleSheet("QLabel { color: #3b82f6; font-size: 12px; background: transparent; }")
            elif field_type == 'FK':
                self.select_indicator.setStyleSheet("QLabel { color: #f59e0b; font-size: 12px; background: transparent; }")
            else:
                self.select_indicator.setStyleSheet("QLabel { color: transparent; font-size: 12px; background: transparent; }")
        else:
            # Hidden when not selected
            self.select_indicator.setText("●")
            self.select_indicator.setStyleSheet("QLabel { color: transparent; font-size: 12px; background: transparent; }")

    def _update_style(self):
        if self.is_selected_for_query:
            # Matching SQL Query Builder style - dark tag with green accent
            self.setStyleSheet("""
                QFrame {
                    background-color: #1e293b;
                    border-radius: 6px;
                    border: 1px solid #22c55e;
                }
            """)
            if hasattr(self, 'label'):
                self.label.setStyleSheet("color: #e2e8f0; font-size: 12px; background: transparent; font-weight: 600;")
        elif self.is_connection_source:
            self.setStyleSheet("""
                QFrame {
                    background-color: rgba(59, 130, 246, 0.25);
                    border-radius: 4px;
                    border-left: 3px solid #3b82f6;
                }
            """)
            if hasattr(self, 'label'):
                self.label.setStyleSheet("color: #FFFFFF; font-size: 12px; background: transparent;")
        elif self.is_connection_target:
            self.setStyleSheet("""
                QFrame {
                    background-color: rgba(245, 158, 11, 0.25);
                    border-radius: 4px;
                    border-left: 3px solid #f59e0b;
                }
            """)
            if hasattr(self, 'label'):
                self.label.setStyleSheet("color: #FFFFFF; font-size: 12px; background: transparent;")
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: transparent;
                    border-radius: 4px;
                }
            """)
            if hasattr(self, 'label'):
                self.label.setStyleSheet("color: #E0E0E0; font-size: 12px; background: transparent;")

    def set_connection_role(self, is_source=False, is_target=False):
        self.is_connection_source = is_source
        self.is_connection_target = is_target
        self._update_style()
        self._update_indicator()

    def add_connection(self):
        self.connection_count += 1
        self._update_indicator()

    def remove_connection(self):
        self.connection_count = max(0, self.connection_count - 1)
        if self.connection_count == 0:
            self.is_connection_source = False
            self.is_connection_target = False
        self._update_style()
        self._update_indicator()

    def _show_popup(self):
        if not self.is_mouse_over:
            return
            
        table_name = self.table_card.table_name
        field_name = self.field_data[0]
        
        if self.popup is None:
            main_window = self.window()
            self.popup = ConditionPopup(main_window, table_name, field_name)
            self.popup.condition_submitted.connect(self._on_condition_submitted)
        
        # Position popup to the right of the field
        global_pos = self.mapToGlobal(QPoint(self.width() + 5, -10))
        self.popup.showAt(global_pos)

    def _on_condition_submitted(self, table_name, field_name, condition):
        self.condition_added.emit(table_name, field_name, condition)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
            event.accept()
            return
        elif event.button() == Qt.MouseButton.RightButton:
            table_name = self.table_card.table_name
            field_name = self.field_data[0]
            field_type = self.field_data[3] if len(self.field_data) > 3 else ''
            
            # Emit signal - let DiagramPage handle the toggle and sync
            self.selected_for_query.emit(table_name, field_name, field_type)
            event.accept()
            return
        super().mousePressEvent(event)

    def set_query_selection(self, selected):
        self.is_selected_for_query = selected
        self._update_style()
        self._update_indicator()

    def enterEvent(self, event):
        self.is_mouse_over = True
        # Fast popup - 200ms delay
        self.hover_timer.start(200)
        
        if not self.is_connection_source and not self.is_connection_target and not self.is_selected_for_query:
            self.setStyleSheet("""
                QFrame {
                    background-color: rgba(100, 116, 139, 0.4);
                    border-radius: 4px;
                }
            """)
            self.label.setStyleSheet("color: #FFFFFF; font-size: 12px; background: transparent;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_mouse_over = False
        self.hover_timer.stop()
        
        if self.popup and self.popup.isVisible():
            self.popup.scheduleHide()
        
        self._update_style()
        super().leaveEvent(event)
