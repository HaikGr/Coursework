from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget
)

from dbmanager.model.query import AGGREGATES, aggregate_problem
from dbmanager.ui.common.elided_label import ElidedLabel
from dbmanager.ui.common.wrap_layout import WrapLayout

_BUTTON_STYLE = """
    QPushButton {{
        background-color: {background};
        color: {color};
        border: 1px solid {border};
        border-radius: 5px;
        font-size: 11px;
        font-weight: {weight};
        padding: 4px 8px;
    }}
    QPushButton:hover {{ background-color: {hover}; }}
    QPushButton:disabled {{ background-color: #f8fafc; color: #cbd5e1; border: 1px solid #e2e8f0; }}
"""
_ACTIVE = {"background": "#3b82f6", "color": "white", "border": "#3b82f6", "weight": 600, "hover": "#2563eb"}
_OPTION_ACTIVE = {"background": "#0f766e", "color": "white", "border": "#0f766e", "weight": 600, "hover": "#115e59"}
_IDLE = {"background": "#ffffff", "color": "#475569", "border": "#cbd5e1", "weight": 500, "hover": "#e2e8f0"}
_CAPTION = "QLabel { color: #64748b; font-size: 9px; font-weight: 700; background: transparent; border: none; }"


class AggregateButton(QPushButton):
    """A button that stays lit while what it stands for is on"""

    def __init__(self, text, active_colors=None, parent=None):
        super().__init__(text, parent)
        self.is_active = False
        self._active_colors = active_colors or _ACTIVE
        self.setFixedHeight(26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

    def _update_style(self):
        self.setStyleSheet(_BUTTON_STYLE.format(**(self._active_colors if self.is_active else _IDLE)))

    def set_active(self, active):
        if active != self.is_active:
            self.is_active = active
            self._update_style()


def _group(layout, spacing=6):
    """A row of widgets that wraps as one piece"""
    group = QWidget()
    group.setStyleSheet("QWidget { background: transparent; }")
    row = QHBoxLayout(group)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(spacing)
    layout.addWidget(group)
    return row


class Toolbar(QFrame):
    """Shapes the query, above the diagram and the table pages.

    The aggregate buttons act on the column selected in the query panel - as a Bold button acts on selected
    text - and the one that column uses is lit. Count rows, Distinct and Limit act on the whole query.
    On a narrow window the groups go on to a second line rather than out of sight."""
    aggregate_selected = pyqtSignal(str)  # aggregate key, or "" to show the column as it is
    count_rows_toggled = pyqtSignal(bool)
    distinct_toggled = pyqtSignal(bool)
    limit_changed = pyqtSignal(int)
    help_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("toolbar")
        self.setStyleSheet("QFrame#toolbar { background-color: #f8fafc; border-bottom: 1px solid #e2e8f0; }")
        self.target = None  # the selected QueryColumn

        layout = WrapLayout(self, spacing=14)
        layout.setContentsMargins(12, 7, 12, 7)
        target_row = _group(layout)
        summary_row = _group(layout)
        options_row = _group(layout)
        help_row = _group(layout)

        # What the aggregate buttons will change
        target_box = QWidget()
        target_box.setFixedSize(132, 30)
        target_box.setStyleSheet("QWidget { background: transparent; }")
        target_layout = QVBoxLayout(target_box)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.setSpacing(0)
        caption = QLabel("SUMMARIZE COLUMN")
        caption.setStyleSheet(_CAPTION)
        target_layout.addWidget(caption)
        self.target_label = ElidedLabel()
        target_layout.addWidget(self.target_label)
        target_row.addWidget(target_box)

        self.agg_buttons = {}
        for key, (name, meaning) in AGGREGATES.items():
            btn = AggregateButton(name)
            btn.clicked.connect(lambda checked=False, k=key: self._on_aggregate_clicked(k))
            summary_row.addWidget(btn)
            self.agg_buttons[key] = btn

        self.count_btn = AggregateButton("Count rows", _OPTION_ACTIVE)
        self.count_btn.setToolTip("Add a column with the number of rows - of each group, when some columns\n"
                                  "are shown as they are (COUNT(*) ... GROUP BY)")
        self.count_btn.clicked.connect(lambda: self.count_rows_toggled.emit(not self.count_btn.is_active))
        options_row.addWidget(self.count_btn)

        self.distinct_btn = AggregateButton("Distinct", _OPTION_ACTIVE)
        self.distinct_btn.setToolTip("Show each different row once (SELECT DISTINCT)")
        self.distinct_btn.clicked.connect(lambda: self.distinct_toggled.emit(not self.distinct_btn.is_active))
        options_row.addWidget(self.distinct_btn)

        limit_label = QLabel("Limit")
        limit_label.setStyleSheet("QLabel { color: #475569; font-size: 11px; background: transparent; border: none; }")
        options_row.addWidget(limit_label)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 1_000_000)
        self.limit_spin.setSpecialValueText("all rows")
        self.limit_spin.setSingleStep(10)
        self.limit_spin.setFixedSize(70, 26)
        self.limit_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)  # typed, or wheel/arrow keys
        self.limit_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.limit_spin.setToolTip("Keep only the first rows (LIMIT, or TOP on SQL Server). Sort first to pick "
                                   "which ones.")
        self.limit_spin.setStyleSheet("""
            QSpinBox {
                background-color: #ffffff; color: #334155; border: 1px solid #cbd5e1;
                border-radius: 5px; padding: 0 2px; font-size: 11px;
            }
            QSpinBox:focus { border: 1px solid #3b82f6; }
        """)
        self.limit_spin.valueChanged.connect(self.limit_changed.emit)
        options_row.addWidget(self.limit_spin)

        help_btn = QPushButton("?  Help")
        help_btn.setFixedHeight(26)
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setToolTip("How to build a query on the diagram")
        help_btn.setStyleSheet(_BUTTON_STYLE.format(**{**_IDLE, "color": "#2563eb", "weight": 600}))
        help_btn.clicked.connect(self.help_requested.emit)
        help_row.addWidget(help_btn)

        self.sync(None, None)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        height = self.layout().heightForWidth(self.width())
        if height != self.height():
            self.setFixedHeight(height)  # one line, or two on a narrow window

    def _on_aggregate_clicked(self, key):
        # The lit button turns the aggregate off again
        if self.target is not None:
            self.aggregate_selected.emit("" if self.target.aggregate == key else key)

    def sync(self, model, selected):
        """Show the query as it is now: the selected column (a QueryColumn or None) and the options"""
        self.target = selected
        if selected is None:
            self.target_label.setText("pick one in the query  →")
            self.target_label.setStyleSheet("QLabel { color: #94a3b8; font-size: 11px; background: transparent; "
                                            "border: none; }")
        else:
            self.target_label.setText(f"{selected.table}.{selected.column}")
            self.target_label.setStyleSheet("QLabel { color: #1e293b; font-size: 12px; font-weight: 600; "
                                            "background: transparent; border: none; }")

        for key, btn in self.agg_buttons.items():
            name, meaning = AGGREGATES[key]
            if selected is None:
                btn.setEnabled(False)
                btn.set_active(False)
                btn.setToolTip(f"{name}: {meaning}.\nSelect a column in the query panel first - click it there.")
                continue
            label = f"{selected.table}.{selected.column}"
            problem = aggregate_problem(key, label, selected.type_name)
            btn.setEnabled(problem is None)
            btn.set_active(selected.aggregate == key)
            if problem:
                btn.setToolTip(problem)
            elif selected.aggregate == key:
                btn.setToolTip(f"{label} shows {meaning}. Click to show each value again.")
            else:
                btn.setToolTip(f"Show {meaning} of {label}")

        self.count_btn.set_active(bool(model and model.count_rows))
        self.distinct_btn.set_active(bool(model and model.distinct))
        self.limit_spin.blockSignals(True)
        self.limit_spin.setValue(model.limit if model else 0)
        self.limit_spin.blockSignals(False)
