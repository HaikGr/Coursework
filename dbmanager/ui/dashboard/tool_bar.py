from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget
)

from dbmanager.i18n import tr
from dbmanager.model.query import AGGREGATES, aggregate_problem
from dbmanager.ui.common.elided_label import ElidedLabel
from dbmanager.ui.common.live import bind, unbind
from dbmanager.ui.common.theme import style
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
    QPushButton:disabled {{ background-color: @surface_alt; color: @text_disabled; border: 1px solid @border; }}
"""
_ACTIVE = {"background": "@accent", "color": "@on_accent", "border": "@accent", "weight": 600, "hover": "@accent_hover"}
_OPTION_ACTIVE = {"background": "@option", "color": "@on_option", "border": "@option", "weight": 600,
                  "hover": "@option_hover"}
_IDLE = {"background": "@surface", "color": "@text_secondary", "border": "@border_strong", "weight": 500,
         "hover": "@surface_pressed"}
_CAPTION = "QLabel { color: @text_muted; font-size: 9px; font-weight: 700; background: transparent; border: none; }"


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
        style(self, _BUTTON_STYLE.format(**(self._active_colors if self.is_active else _IDLE)))

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
        style(self, "QFrame#toolbar { background-color: @surface_alt; border-bottom: 1px solid @border; }")
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
        caption = QLabel()
        bind(caption.setText, "dashboard.tool_bar.summarize_column")
        style(caption, _CAPTION)
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

        self.count_btn = AggregateButton("", _OPTION_ACTIVE)
        bind(self.count_btn.setText, "dashboard.tool_bar.count_rows")
        bind(self.count_btn.setToolTip, "dashboard.tool_bar.count_rows_tip")
        self.count_btn.clicked.connect(lambda: self.count_rows_toggled.emit(not self.count_btn.is_active))
        options_row.addWidget(self.count_btn)

        self.distinct_btn = AggregateButton("", _OPTION_ACTIVE)
        bind(self.distinct_btn.setText, "dashboard.tool_bar.distinct")
        bind(self.distinct_btn.setToolTip, "dashboard.tool_bar.distinct_tip")
        self.distinct_btn.clicked.connect(lambda: self.distinct_toggled.emit(not self.distinct_btn.is_active))
        options_row.addWidget(self.distinct_btn)

        limit_label = QLabel()
        bind(limit_label.setText, "dashboard.tool_bar.limit")
        style(limit_label, "QLabel { color: @text_secondary; font-size: 11px; background: transparent; border: none; }")
        options_row.addWidget(limit_label)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 1_000_000)
        bind(self.limit_spin.setSpecialValueText, "dashboard.tool_bar.all_rows")
        self.limit_spin.setSingleStep(10)
        self.limit_spin.setFixedSize(70, 26)
        self.limit_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)  # typed, or wheel/arrow keys
        self.limit_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bind(self.limit_spin.setToolTip, "dashboard.tool_bar.limit_tip")
        style(self.limit_spin, """
            QSpinBox {
                background-color: @sunken; color: @text; border: 1px solid @border_strong;
                border-radius: 5px; padding: 0 2px; font-size: 11px;
            }
            QSpinBox:focus { border: 1px solid @focus; }
        """)
        self.limit_spin.valueChanged.connect(self.limit_changed.emit)
        options_row.addWidget(self.limit_spin)

        help_btn = QPushButton()
        bind(help_btn.setText, "dashboard.tool_bar.help")
        help_btn.setFixedHeight(26)
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bind(help_btn.setToolTip, "dashboard.tool_bar.help_tip")
        style(help_btn, _BUTTON_STYLE.format(**{**_IDLE, "color": "@accent_text", "weight": 600}))
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
            bind(self.target_label.setText, "dashboard.tool_bar.pick_column")
            style(self.target_label, "QLabel { color: @placeholder; font-size: 11px; background: transparent; "
                                     "border: none; }")
        else:
            unbind(self.target_label.setText)
            self.target_label.setText(f"{selected.table}.{selected.column}")
            style(self.target_label, "QLabel { color: @text; font-size: 12px; font-weight: 600; "
                                     "background: transparent; border: none; }")

        # AGGREGATES gives the meaning in the current language: it is looked up again on every change of it
        for key, btn in self.agg_buttons.items():
            if selected is None:
                btn.setEnabled(False)
                btn.set_active(False)
                bind(btn.setToolTip, lambda key=key: tr("dashboard.tool_bar.aggregate_unselected_tip",
                                                        name=AGGREGATES[key][0], meaning=AGGREGATES[key][1]))
                continue
            label = f"{selected.table}.{selected.column}"
            problem = aggregate_problem(key, label, selected.type_name)
            btn.setEnabled(problem is None)
            btn.set_active(selected.aggregate == key)
            if problem:
                bind(btn.setToolTip, lambda key=key, label=label, type_name=selected.type_name:
                     aggregate_problem(key, label, type_name))
            elif selected.aggregate == key:
                bind(btn.setToolTip, lambda key=key, label=label: tr("dashboard.tool_bar.aggregate_active_tip",
                                                                     label=label, meaning=AGGREGATES[key][1]))
            else:
                bind(btn.setToolTip, lambda key=key, label=label: tr("dashboard.tool_bar.aggregate_tip",
                                                                     label=label, meaning=AGGREGATES[key][1]))

        self.count_btn.set_active(bool(model and model.count_rows))
        self.distinct_btn.set_active(bool(model and model.distinct))
        self.limit_spin.blockSignals(True)
        self.limit_spin.setValue(model.limit if model else 0)
        self.limit_spin.blockSignals(False)
