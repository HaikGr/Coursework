"""How the query is built on the diagram, in one page."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, button, label
from dbmanager.ui.common.style import shortcut_text


def _steps():
    run_keys = shortcut_text("Ctrl+Return")
    return [
        ("1", "Pick columns",
         "Click the circle at the end of a field on the diagram, or right-click the field and choose "
         "<b>Add to query</b>. Fields of several tables are joined along the links between them."),
        ("2", "Join tables",
         "Drag a primary key (<b>PK</b>) onto the field of another table that refers to it - or click one, then "
         "the other, or right-click the field → <b>Link to</b>. Queries join the tables on the link, and it is "
         "saved as a foreign key at the next Run. To join on other fields, or keep the rows without a match "
         "(<b>LEFT JOIN</b>), use <b>+ Join</b> in the query panel: that changes nothing in the database."),
        ("3", "Summarize",
         "Click a column in the query panel, then <b>SUM</b>, <b>AVG</b>, <b>COUNT</b>, <b>COUNT UNIQUE</b>, "
         "<b>MIN</b> or <b>MAX</b> in the toolbar (or use the pill on the column). Every column you do not "
         "summarize becomes a group - <b>GROUP BY</b> is written for you. <b>Count rows</b> adds how many rows "
         "each group has."),
        ("4", "Filter",
         "Right-click a field and choose <b>Add filter…</b>, pick how to compare and type the value as it is - "
         "no quotes. A filter on a summarized column can test each group instead of each row (<b>HAVING</b>). "
         "Click a filter in the panel to change it."),
        ("5", "Sort and limit",
         "The arrow on a column sorts by it: smallest first, largest first, off. <b>Limit</b> keeps the first "
         "rows; <b>Distinct</b> shows each different row once."),
        ("6", "Run",
         f"<b>Run Query</b> or <b>{run_keys}</b>. The SQL can be edited by hand before it runs; it is only "
         "written over when you change the query on the diagram."),
    ]


class QueryHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("How to Build a Query")
        self.setStyleSheet(DIALOG_STYLE + """
            QLabel#number {
                background-color: #0ea5e9; color: white; border-radius: 12px;
                font-size: 12px; font-weight: 700;
            }
            QLabel#step { color: #f1f5f9; font-size: 14px; font-weight: 600; }
        """)
        self.setFixedWidth(600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(14)
        layout.addWidget(label("How to build a query", "heading"))
        layout.addWidget(label("Everything you pick becomes SQL in the panel on the right.", "note"))

        for number, title, text in _steps():
            row = QHBoxLayout()
            row.setSpacing(12)
            badge = QLabel(number)
            badge.setObjectName("number")
            badge.setFixedSize(24, 24)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
            column = QVBoxLayout()
            column.setSpacing(2)
            column.addWidget(label(title, "step"))
            body = label(text, wrap=True)
            body.setFixedWidth(500)
            body.setParent(self)
            body.ensurePolished()  # measured in the dialog's style sheet font, not the default one
            body.setMinimumHeight(body.heightForWidth(500))  # nested layouts do not ask a wrapped label
            column.addWidget(body)
            row.addLayout(column, stretch=1)
            layout.addLayout(row)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("QFrame { background-color: #334155; }")
        layout.addWidget(line)
        buttons = QHBoxLayout()
        buttons.addStretch()
        close = button("Got it", "primary", self.accept)
        close.setDefault(True)
        buttons.addWidget(close)
        layout.addLayout(buttons)
