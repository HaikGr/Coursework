"""How the data grids (a table's rows, a query's results) show values.

A column is as wide as its name and its values, within limits: a longer value is cut short with … rather than
pushing the other columns out of sight, and many columns scroll sideways instead of being squeezed until no
value shows at all. The whole of a cut value is in its tooltip and in the value panel (see value_panel).
"""

import html

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QStyle, QStyleOptionViewItem, QStyledItemDelegate, QToolTip

MIN_COLUMN_WIDTH = 80
MAX_COLUMN_WIDTH = 300
# A cell's whole value, when its text in the grid is not all of it (the lines of a value are shown on one)
FULL_TEXT_ROLE = Qt.ItemDataRole.UserRole + 1
# A tooltip is a glance: past this the value panel shows the rest
TOOLTIP_MAX_CHARS = 1500

# The scroll bars of a grid and of the value panel under it: a theme.qss template
SCROLLBAR_STYLE = """
    QScrollBar:vertical { background: @surface; width: 10px; }
    QScrollBar:horizontal { background: @surface; height: 10px; }
    QScrollBar::handle:vertical { background: @scrollbar; border-radius: 3px; min-height: 32px; margin: 2px; }
    QScrollBar::handle:horizontal { background: @scrollbar; border-radius: 3px; min-width: 32px; margin: 2px; }
    QScrollBar::handle:hover { background: @scrollbar_hover; }
    QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
    QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""


def one_line(text):
    """A value as a grid cell shows it: its lines joined by ↵, where a one-line cell would show only the first"""
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ↵ ")


def set_cell_text(item, text):
    """Show a value's text in a grid cell; when the cell cannot show it as it is, the whole of it stays with it"""
    shown = one_line(text)
    item.setText(shown)
    item.setData(FULL_TEXT_ROLE, text if shown != text else None)


def prepare_grid(table):
    """Columns the user can widen, a grid that scrolls sideways smoothly, and tooltips for the values it cuts"""
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(True)  # columns that fit leave no empty strip on the right
    header.setTextElideMode(Qt.TextElideMode.ElideRight)  # a header does not elide by itself: it clips
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setItemDelegate(CutValueTooltips(table))


def fit_columns(table, columns=None):
    """Size columns (all, or these) to their names and values, between MIN_COLUMN_WIDTH and MAX_COLUMN_WIDTH"""
    table.ensurePolished()  # the item padding of the style sheet counts
    header = table.horizontalHeader()
    for column in range(table.columnCount()) if columns is None else columns:
        table.resizeColumnToContents(column)
        header.resizeSection(column, max(MIN_COLUMN_WIDTH, min(header.sectionSize(column), MAX_COLUMN_WIDTH)))


def tooltip_html(text):
    """A value for a tooltip, as rich text that shows it as it is - a value may look like HTML - with its lines
    kept and long lines wrapped, where plain text would run off the screen"""
    if len(text) > TOOLTIP_MAX_CHARS:
        text = text[:TOOLTIP_MAX_CHARS] + " …"
    return f"<p style='white-space:pre-wrap'>{html.escape(text)}</p>"


class CutValueTooltips(QStyledItemDelegate):
    """A cell whose value its column cuts short shows the whole of it as a tooltip; one that fits shows none."""

    def helpEvent(self, event, view, option, index):
        if event is None or event.type() != QEvent.Type.ToolTip or not index.isValid():
            return super().helpEvent(event, view, option, index)
        whole = self.cut_value(view, option, index)
        if whole is None:
            QToolTip.hideText()
        else:
            QToolTip.showText(event.globalPos(), tooltip_html(whole), view)
        return True

    def cut_value(self, view, option, index):
        """The whole value of a cell when the grid does not show all of it, else None"""
        whole = index.data(FULL_TEXT_ROLE)
        if whole is not None:
            return whole
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        room = view.style().subElementRect(QStyle.SubElement.SE_ItemViewItemText, styled, view).width()
        return styled.text if styled.fontMetrics.horizontalAdvance(styled.text) > room else None
