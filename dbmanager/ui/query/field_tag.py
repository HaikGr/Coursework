from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QPushButton

from dbmanager.i18n import tr
from dbmanager.model.query import AGGREGATES, aggregate_problem
from dbmanager.ui.common.elided_label import ElidedLabel
from dbmanager.ui.common.style import MENU_STYLE
from dbmanager.ui.common.theme import qss

# The tags and chips are made again whenever the language or the theme changes (see SQLQueryBuilder), so they
# take both as they are when made
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
    QPushButton:hover {{ background-color: {hover}; color: {hover_color}; }}
"""
_PILL_COLORS = {  # (background, text, hover background, hover text)
    "summary": ("@warning", "@on_warning", "@warning_hover", "@on_warning"),
    "group": ("@success", "@on_success", "@success_hover", "@on_success"),
    "plain": ("@surface_raised", "@text_secondary", "@surface_pressed", "@text"),
}
_SORT_TEXT = {None: "↕", "ASC": "↑", "DESC": "↓"}
_PILL_NAMES = {"COUNT_DISTINCT": "UNIQUE"}  # COUNT UNIQUE does not fit the pill


def _small_button(text, tooltip, width, colors, size=11):
    widget = QPushButton(text)
    widget.setFixedSize(width, 20)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setToolTip(tooltip)
    background, color, hover, hover_color = colors
    widget.setStyleSheet(qss(_SMALL_BUTTON.format(background=background, color=color, hover=hover,
                                                  hover_color=hover_color, size=size)))
    return widget


def aggregate_menu(parent, label, type_name, current):
    """Show as it is, or one of the aggregates; each says what it gives back. Those that cannot work on the
    column's type are disabled, saying why. The chosen key (None: as it is) is the action's data.
    Made for one showing, so it takes the language and the theme as they are."""
    menu = QMenu(parent)
    menu.setStyleSheet(qss(MENU_STYLE))
    entries = [(None, tr("query.aggregate_menu.as_it_is"))]
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
        self.setStyleSheet(qss(
            "ColumnTag { background-color: %s; border: 1px solid %s; border-radius: 6px; }"
            % (("@accent_subtle", "@accent") if is_selected else ("@surface_alt", "@border"))))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        if entry.aggregate:
            pill_text, colors = _PILL_NAMES.get(entry.aggregate, AGGREGATES[entry.aggregate][0]), "summary"
            pill_tip = tr("query.column_tag.summary_tip", meaning=AGGREGATES[entry.aggregate][1])
        elif grouped:
            pill_text, colors = "GROUP", "group"
            pill_tip = tr("query.column_tag.group_tip")
        else:
            pill_text, colors = "—", "plain"
            pill_tip = tr("query.column_tag.plain_tip")
        self.pill = _small_button(pill_text, pill_tip, 52, _PILL_COLORS[colors], size=9)
        self.pill.clicked.connect(self._open_aggregate_menu)
        layout.addWidget(self.pill)

        type_note = f"  ({entry.type_name})" if entry.type_name else ""
        self.name_label = ElidedLabel(f"{entry.table}.{entry.column}")
        self.name_label.setToolTip(tr("query.column_tag.name_tip", column=f"{entry.label()}{type_note}"))
        self.name_label.setStyleSheet(qss("QLabel { color: @text; font-size: 11px; background: transparent; "
                                          "border: none; }"))
        layout.addWidget(self.name_label, stretch=1)

        sort_text = _SORT_TEXT[entry.sort] + (str(rank) if rank else "")
        # The theme has no on_purple: white reads on its violet in both themes
        sort_colors = {None: _PILL_COLORS["plain"], "ASC": ("@info", "@on_info", "@info_hover", "@on_info"),
                       "DESC": ("@purple", "@on_accent", "@purple_text", "@purple_subtle")}[entry.sort]
        sort_tip = tr({None: "query.column_tag.sort_none",
                       "ASC": "query.column_tag.sort_asc",
                       "DESC": "query.column_tag.sort_desc"}[entry.sort])
        if rank:
            sort_tip += "\n" + tr("query.column_tag.sort_rank", rank=rank)
        self.sort_btn = _small_button(sort_text, sort_tip, 28 if rank else 22, sort_colors)
        self.sort_btn.clicked.connect(lambda: self.sort_clicked.emit(self.key))
        layout.addWidget(self.sort_btn)

        self.remove_btn = _small_button("×", tr("query.column_tag.remove_tip"), 22,
                                        ("@danger_subtle", "@danger_text", "@danger", "@on_danger"), 13)
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
    Click it to change it; × removes it. color: the theme token of its badge and edge."""
    edit_clicked = pyqtSignal(int)
    remove_clicked = pyqtSignal(int)

    def __init__(self, index, badge, badge_tip, text, color, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("chip")
        self.setStyleSheet(qss(f"QFrame#chip {{ background-color: @surface_alt; border: 1px solid @border; "
                               f"border-left: 3px solid {color}; border-radius: 6px; }}"
                               f"QFrame#chip:hover {{ border-color: {color}; }}"))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 6, 3)
        layout.setSpacing(6)

        kind = QLabel(badge)
        kind.setToolTip(badge_tip)
        kind.setStyleSheet(qss(f"QLabel {{ color: {color}; font-size: 8px; font-weight: 700; "
                               "background: transparent; border: none; }"))
        layout.addWidget(kind)

        self.text_label = ElidedLabel(text)
        self.text_label.setToolTip(tr("query.chip.text_tip", text=text))
        self.text_label.setStyleSheet(qss("QLabel { color: @text; font-size: 11px; background: transparent; "
                                          "border: none; }"))
        layout.addWidget(self.text_label, stretch=1)

        remove_btn = _small_button("×", tr("query.chip.remove_tip"), 22,
                                   ("@danger_subtle", "@danger_text", "@danger", "@on_danger"), 13)
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
        return ListChip(index, tr("query.chip.groups"), tr("query.chip.groups_tip"), condition.describe(),
                        "@warning_text", parent)
    return ListChip(index, tr("query.chip.rows"), tr("query.chip.rows_tip"), condition.describe(),
                    "@warning_text", parent)


def join_chip(index, join, parent=None):
    """A join made for the query only"""
    tip = tr("query.chip.left_join_tip" if join.kind == "LEFT" else "query.chip.join_tip")
    return ListChip(index, "LEFT" if join.kind == "LEFT" else "JOIN", tip, join.describe(), "@link_join", parent)
