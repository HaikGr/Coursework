from PyQt6.QtWidgets import (
    QHBoxLayout, 
    QPushButton,
    QFrame,
    QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal


class AggregateButton(QPushButton):
    """Button for aggregate functions"""
    def __init__(self, icon, text, parent=None):
        super().__init__(f"{icon} {text}", parent)
        self.agg_type = text
        self.is_active = False
        self.setFixedHeight(26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()
    
    def _update_style(self):
        if self.is_active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #2563eb;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #f8fafc;
                    color: #475569;
                    border: 1px solid #cbd5e1;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 500;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #e2e8f0;
                    border: 1px solid #94a3b8;
                }
            """)
    
    def set_active(self, active):
        self.is_active = active
        self._update_style()


class Toolbar(QFrame):
    aggregate_selected = pyqtSignal(str)  # Emits aggregate name or empty string
    
    def __init__(self):
        super().__init__()
        self.setFixedHeight(44)
        self.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border-bottom: 1px solid #e2e8f0;
            }
        """)
        
        toolbar_layout = QHBoxLayout(self)
        toolbar_layout.setContentsMargins(12, 6, 12, 6)
        toolbar_layout.setSpacing(8)
        
        # Aggregate Functions Section
        agg_label = QLabel("AGGREGATE\nFUNCTIONS")
        agg_label.setStyleSheet("""
            color: #64748b;
            font-size: 8px;
            font-weight: 700;
            background: transparent;
        """)
        toolbar_layout.addWidget(agg_label)
        
        self.agg_buttons = {}
        agg_funcs = [("Σ", "SUM"), ("∿", "AVG"), ("#", "COUNT"), ("↓", "MIN"), ("↑", "MAX")]
        
        for icon, name in agg_funcs:
            btn = AggregateButton(icon, name)
            btn.clicked.connect(lambda checked, n=name, b=btn: self._on_aggregate_clicked(n, b))
            toolbar_layout.addWidget(btn)
            self.agg_buttons[name] = btn
        
        toolbar_layout.addStretch()
        
        self.current_aggregate = None
    
    def _on_aggregate_clicked(self, agg_name, btn):
        if self.current_aggregate == agg_name:
            # Deselect
            self.current_aggregate = None
            btn.set_active(False)
            self.aggregate_selected.emit("")
        else:
            # Deactivate all others
            for name, b in self.agg_buttons.items():
                b.set_active(False)
            # Activate this one
            self.current_aggregate = agg_name
            btn.set_active(True)
            self.aggregate_selected.emit(agg_name)
    
    def reset_aggregate(self):
        """Reset aggregate selection"""
        self.current_aggregate = None
        for btn in self.agg_buttons.values():
            btn.set_active(False)
