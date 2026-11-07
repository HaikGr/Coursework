"""How the query is built on the diagram, in one page."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from dbmanager.i18n import tr
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, button, label
from dbmanager.ui.common.style import shortcut_text
from dbmanager.ui.common.theme import qss


def _steps():
    # The buttons the steps name, as they are called in the language
    add_join, run_query = tr("query.builder.add_join"), tr("common.action.run_query")
    run_keys = shortcut_text("Ctrl+Return")
    return [
        ("1", tr("query.help.columns_title"), tr("query.help.columns_text")),
        ("2", tr("query.help.join_title"), tr("query.help.join_text", add_join=add_join)),
        ("3", tr("query.help.summarize_title"), tr("query.help.summarize_text")),
        ("4", tr("query.help.filter_title"), tr("query.help.filter_text")),
        ("5", tr("query.help.sort_title"), tr("query.help.sort_text")),
        ("6", tr("query.help.run_title"), tr("query.help.run_text", run_query=run_query, keys=run_keys)),
    ]


class QueryHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("query.help.window_title"))
        self.setStyleSheet(qss(DIALOG_STYLE + """
            QLabel#number {
                background-color: @accent; color: @on_accent; border-radius: 12px;
                font-size: 12px; font-weight: 700;
            }
            QLabel#step { color: @text; font-size: 14px; font-weight: 600; }
        """))
        self.setFixedWidth(600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(14)
        layout.addWidget(label(tr("query.help.heading"), "heading"))
        layout.addWidget(label(tr("query.help.intro"), "note"))

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
        line.setStyleSheet(qss("QFrame { background-color: @border; }"))
        layout.addWidget(line)
        buttons = QHBoxLayout()
        buttons.addStretch()
        close = button(tr("query.help.got_it"), "primary", self.accept)
        close.setDefault(True)
        buttons.addWidget(close)
        layout.addLayout(buttons)
