from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QPushButton

from dbmanager.model.query import AGGREGATES, aggregate_problem
from dbmanager.ui.common.elided_label import ElidedLabel
from dbmanager.ui.common.style import MENU_STYLE

_SMALL_BUTTON = """
    QPushButton {{
        background-color: {background};
        color: {color};
        border: none;
        border-radius: 4px;
        font-size: {size}px;
        font-weight: 700;
        padding: 0px;
    }}
    QPushButton:hover {{ background-color: {hover}; }}
"""
_PILL_COLORS = {  # (background, text, hover)
    "summary": ("#f59e0b", "#1c1917", "#fbbf24"),
    "group": ("#166534", "#bbf7d0", "#15803d"),
    "plain": ("#334155", "#94a3b8", "#475569"),
}
_SORT_TEXT = {None: "↕", "ASC": "↑", "DESC": "↓"}
_PILL_NAMES = {"COUNT_DISTINCT": "UNIQUE"}  # COUNT UNIQUE does not fit the pill


def _small_button(text, tooltip, width, colors, size=11):
    widget = QPushButton(text)
    widget.setFixedSize(width, 20)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setToolTip(tooltip)
    background, color, hover = colors
    widget.setStyleSheet(_SMALL_BUTTON.format(background=background, color=color, hover=hover, size=size))
    return widget


def aggregate_menu(parent, label, type_name, current):
    """Show as it is, or one of the aggregates; each says what it gives back. Those that cannot work on the
    column's type are disabled, saying why. The chosen key (None: as it is) is the action's data."""
    menu = QMenu(parent)
    menu.setStyleSheet(MENU_STYLE)
    entries = [(None, "Show each value as it is")]
    entries += [(key, f"{name}  -  {meaning}") for key, (name, meaning) in AGGREGATES.items()]
    for key, text in entries:
        action = QAction(text, menu)
        action.setData(key)
        action.setCheckable(True)
        action.setChecked(key == current)
        problem = aggregate_problem(key, label, type_name)
        if problem:
            action.setEnabled(False)
            action.setToolTip(problem)
        menu.addAction(action)
    menu.setToolTipsVisible(True)
    return menu


class ColumnTag(QFrame):
    """One column of the query, in the side panel. The pill on the left says how the column is shown - as it
    is (—), as a group (GROUP), or summarised (SUM, ...) - and changes it; the arrow sorts by it; × takes it
    out. Clicking the tag selects it: the toolbar's aggregate buttons act on the selected column."""
    selected = pyqtSignal(object)  # (table, column)
    aggregate_chosen = pyqtSignal(object, object)  # (table, column), aggregate key or None
    sort_clicked = pyqtSignal(object)
    remove_clicked = pyqtSignal(object)

    def __init__(self, entry, grouped=False, rank=None, is_selected=False, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.key = entry.key
        self.is_selected = is_selected
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "ColumnTag { background-color: %s; border: 1px solid %s; border-radius: 6px; }"
            % (("#1e3a5f", "#3b82f6") if is_selected else ("#1e293b", "#334155")))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        if entry.aggregate:
            pill_text, colors = _PILL_NAMES.get(entry.aggregate, AGGREGATES[entry.aggregate][0]), "summary"
            pill_tip = f"Shows {AGGREGATES[entry.aggregate][1]}. Click to change."
        elif grouped:
            pill_text, colors = "GROUP", "group"
            pill_tip = ("Another column is summarised, so the rows are grouped by this one (GROUP BY).\n"
                        "Click to summarise this column too.")
        else:
            pill_text, colors = "—", "plain"
            pill_tip = "Shown as it is. Click to summarise it: SUM, AVG, COUNT, MIN, MAX…"
        self.pill = _small_button(pill_text, pill_tip, 52, _PILL_COLORS[colors], size=9)
        self.pill.clicked.connect(self._open_aggregate_menu)
        layout.addWidget(self.pill)

        type_note = f"  ({entry.type_name})" if entry.type_name else ""
        self.name_label = ElidedLabel(f"{entry.table}.{entry.column}")
        self.name_label.setToolTip(f"{entry.label()}{type_note}\nClick to select it for the toolbar.")
        self.name_label.setStyleSheet("QLabel { color: #e2e8f0; font-size: 11px; background: transparent; "
                                      "border: none; }")
        layout.addWidget(self.name_label, stretch=1)

        sort_text = _SORT_TEXT[entry.sort] + (str(rank) if rank else "")
        sort_colors = {None: _PILL_COLORS["plain"], "ASC": ("#0e7490", "#cffafe", "#0891b2"),
                       "DESC": ("#7c3aed", "#ede9fe", "#8b5cf6")}[entry.sort]
        sort_tip = {None: "Not sorted. Click: smallest first (ASC)",
                    "ASC": "Smallest first (ASC). Click: largest first (DESC)",
                    "DESC": "Largest first (DESC). Click: not sorted"}[entry.sort]
        if rank:
            sort_tip += f"\nSort {rank}: the sort set first decides first"
        self.sort_btn = _small_button(sort_text, sort_tip, 28 if rank else 22, sort_colors)
        self.sort_btn.clicked.connect(lambda: self.sort_clicked.emit(self.key))
        layout.addWidget(self.sort_btn)

        self.remove_btn = _small_button("×", "Take it out of the query", 22, ("#7f1d1d", "#fca5a5", "#991b1b"), 13)
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.key))
        layout.addWidget(self.remove_btn)

    def _open_aggregate_menu(self):
        self.selected.emit(self.key)
        menu = aggregate_menu(self, f"{self.entry.table}.{self.entry.column}", self.entry.type_name,
                              self.entry.aggregate)
        chosen = menu.exec(self.pill.mapToGlobal(QPoint(0, self.pill.height())))
        if chosen is not None:
            self.aggregate_chosen.emit(self.key, chosen.data())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.key)
            event.accept()
            return
        super().mousePressEvent(event)


class ListChip(QFrame):
    """One entry of a list in the panel - a filter, a join - in words, with a small badge before it.
    Click it to change it; × removes it."""
    edit_clicked = pyqtSignal(int)
    remove_clicked = pyqtSignal(int)

    def __init__(self, index, badge, badge_tip, text, color, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("chip")
        self.setStyleSheet(f"QFrame#chip {{ background-color: #1e293b; border: 1px solid #334155; "
                           f"border-left: 3px solid {color}; border-radius: 6px; }}"
                           f"QFrame#chip:hover {{ border-color: {color}; }}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 6, 3)
        layout.setSpacing(6)

        kind = QLabel(badge)
        kind.setToolTip(badge_tip)
        kind.setStyleSheet(f"QLabel {{ color: {color}; font-size: 8px; font-weight: 700; background: transparent; "
                           "border: none; }")
        layout.addWidget(kind)

        self.text_label = ElidedLabel(text)
        self.text_label.setToolTip(f"{text}\nClick to change it.")
        self.text_label.setStyleSheet("QLabel { color: #e2e8f0; font-size: 11px; background: transparent; "
                                      "border: none; }")
        layout.addWidget(self.text_label, stretch=1)

        remove_btn = _small_button("×", "Remove it", 22, ("#7f1d1d", "#fca5a5", "#991b1b"), 13)
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.index))
        layout.addWidget(remove_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.edit_clicked.emit(self.index)
            event.accept()
            return
        super().mousePressEvent(event)


def filter_chip(index, condition, parent=None):
    """A filter of the query: ROWS (WHERE) or GROUPS (HAVING)"""
    if condition.aggregate:
        return ListChip(index, "GROUPS", "Tests each group (HAVING)", condition.describe(), "#f59e0b", parent)
    return ListChip(index, "ROWS", "Tests each row (WHERE)", condition.describe(), "#f59e0b", parent)


def join_chip(index, join, parent=None):
    """A join made for the query only"""
    tip = ("Keeps every row of the first table, matched or not (LEFT JOIN)" if join.kind == "LEFT"
           else "Keeps the rows that match in both tables (JOIN)")
    return ListChip(index, "LEFT" if join.kind == "LEFT" else "JOIN", tip, join.describe(), "#2dd4bf", parent)
