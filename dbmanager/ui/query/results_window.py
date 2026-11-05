from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt

from dbmanager.model.table_state import cell_text
from dbmanager.ui.common.data_grid import fit_columns, prepare_grid, set_cell_text
from dbmanager.ui.common.value_panel import ValuePanel


class QueryResultsWindow(QDialog):
    """Dark themed dialog showing the results of a script run on the database.
    The last statement that returned rows is shown as a table; the others are summarised.
    A double-click on a value (or Value) shows the whole of it under the table."""

    def __init__(self, results, duration, database_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Query Results - {database_name}")
        self.resize(860, 520)
        self.setStyleSheet("""
            QDialog { background-color: #0f172a; }
            QLabel { color: #e2e8f0; background: transparent; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        with_rows = [result for result in results if result.get("updateCount") is None]
        shown = with_rows[-1] if with_rows else {}
        columns = shown.get("columns") or []
        rows = shown.get("rows") or []

        title = QLabel(f"{len(results)} statement{'s' if len(results) != 1 else ''} executed   ·   {duration} ms")
        title.setStyleSheet("QLabel { color: #fbbf24; font-size: 13px; font-weight: 700; }")
        layout.addWidget(title)

        lines = []
        for number, result in enumerate(results, start=1):
            kind = result.get("statementType", "")
            if result.get("updateCount") is None:
                text = f"{len(result.get('rows') or [])} row(s) returned"
                if result.get("truncated"):
                    text += " (more rows exist, only the first ones are shown)"
            elif kind in ("INSERT", "UPDATE", "DELETE"):
                text = f"{result['updateCount']} row(s) affected"
            else:
                text = "done"
            lines.append(f"{number}. {kind}: {text}")
        summary = QLabel("\n".join(lines[-12:]) if len(lines) <= 12 else
                         f"... {len(lines) - 12} earlier statement(s)\n" + "\n".join(lines[-12:]))
        summary.setStyleSheet("QLabel { color: #cbd5e1; font-size: 12px; font-family: 'Consolas', monospace; }")
        summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(summary)

        self.table = None
        self.value_panel = None
        self.value_btn = None
        if columns:
            table = self.table = QTableWidget(len(rows), len(columns))
            table.setHorizontalHeaderLabels(columns)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            prepare_grid(table)
            table.setStyleSheet("""
                QTableWidget {
                    background-color: #1e293b;
                    alternate-background-color: #243247;
                    color: #e2e8f0;
                    gridline-color: #334155;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    font-size: 12px;
                }
                QTableWidget::item:selected { background-color: #3b82f6; color: white; }
                QHeaderView::section {
                    background-color: #334155;
                    color: #cbd5e1;
                    padding: 6px 10px;
                    border: none;
                    font-weight: 600;
                }
            """)
            for row_idx, row in enumerate(rows):
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem()
                    set_cell_text(item, cell_text(value))
                    if value is None:
                        item.setForeground(Qt.GlobalColor.gray)
                    table.setItem(row_idx, col_idx, item)
            fit_columns(table)

            self.value_panel = ValuePanel()
            self.value_panel.hide()
            self.value_panel.leave_requested.connect(table.setFocus)
            self.value_panel.closed.connect(lambda: self.value_btn.setChecked(False))
            table.currentCellChanged.connect(lambda *_: self._show_current_value(columns, rows))
            table.cellDoubleClicked.connect(lambda *_: self.value_btn.setChecked(True))
            split = QSplitter(Qt.Orientation.Vertical)
            split.setStyleSheet("QSplitter::handle { background-color: #334155; }")
            split.setHandleWidth(3)
            split.setChildrenCollapsible(False)
            split.addWidget(table)
            split.addWidget(self.value_panel)
            split.setStretchFactor(0, 1)
            split.setStretchFactor(1, 0)
            layout.addWidget(split, 1)
        else:
            layout.addStretch()

        btn_row = QHBoxLayout()
        if columns:
            self.value_btn = QPushButton("⊟  Value")
            self.value_btn.setCheckable(True)
            self.value_btn.setFixedHeight(36)
            self.value_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.value_btn.setToolTip("Show the whole value of the selected cell under the table (or double-click it)")
            self.value_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent; color: #cbd5e1; border: 1px solid #475569;
                    border-radius: 8px; font-size: 13px; font-weight: 600; padding: 0px 14px;
                }
                QPushButton:hover { background-color: #1e293b; }
                QPushButton:checked { background-color: #334155; color: #FFFFFF; border-color: #64748b; }
            """)
            self.value_btn.toggled.connect(lambda shown: self._show_value_panel(shown, columns, rows))
            btn_row.addWidget(self.value_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedSize(100, 36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; color: white; border: none;
                border-radius: 8px; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _show_value_panel(self, shown, columns, rows):
        if not shown:
            self.value_panel.hide()
            return
        self.value_panel.reveal()
        self._show_current_value(columns, rows)

    def _show_current_value(self, columns, rows):
        if self.value_panel.isHidden():
            return
        row, col = self.table.currentRow(), self.table.currentColumn()
        if 0 <= row < len(rows) and 0 <= col < len(columns):
            self.value_panel.show_value(columns[col], "", rows[row][col], where=f"row {row + 1}")
        else:
            self.value_panel.show_nothing()
