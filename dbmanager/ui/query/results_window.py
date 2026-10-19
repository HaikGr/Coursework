from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt

from dbmanager.model.table_state import cell_text


class QueryResultsWindow(QDialog):
    """Dark themed dialog showing the results of a script run on the server.
    The last statement that returned rows is shown as a table; the others are summarised."""

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
        title.setStyleSheet("color: #fbbf24; font-size: 13px; font-weight: 700;")
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
        summary.setStyleSheet("color: #cbd5e1; font-size: 12px; font-family: 'Consolas', monospace;")
        summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(summary)

        if columns:
            table = QTableWidget(len(rows), len(columns))
            table.setHorizontalHeaderLabels(columns)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            table.horizontalHeader().setStretchLastSection(True)
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
                    item = QTableWidgetItem(cell_text(value))
                    if value is None:
                        item.setForeground(Qt.GlobalColor.gray)
                    table.setItem(row_idx, col_idx, item)
            table.resizeColumnsToContents()
            layout.addWidget(table)
        else:
            layout.addStretch()

        btn_row = QHBoxLayout()
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
