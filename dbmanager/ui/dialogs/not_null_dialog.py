"""Making a column of a table that exists require a value (NOT NULL)."""

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from dbmanager.sql.generator import is_numeric_type, looks_like_number
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, ERROR_COLOR, button, label


class RequireValueDialog(QDialog):
    """The database refuses NOT NULL while a row has no value, so the rows without one get a value first.
    missing: how many of the rows shown have none; truncated: there are more rows than shown.
    After exec(): fill is the value typed, or "" for none."""

    def __init__(self, parent, table, column, type_name, missing, truncated):
        super().__init__(parent)
        self.type_name = type_name
        self.fill = ""
        self.needed = missing > 0
        self.setWindowTitle("Require a Value")
        self.setStyleSheet(DIALOG_STYLE)
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(label(f"Require a value in {column}", "heading"))
        layout.addWidget(label(f"{table}.{column}   ·   {type_name}   ·   NOT NULL", "caption"))

        if missing:
            text = (f"{missing} of the rows shown {'have' if missing != 1 else 'has'} no value. "
                    "The database will not require one until every row has it - give them this value:")
        elif truncated:
            text = ("Every row shown has a value, but the table has more rows than are shown. "
                    "Rows without a value, if there are any, get this one (leave it empty to let the database "
                    "check, and refuse if it finds one):")
        else:
            text = "Every row has a value. New rows will need one too."
        layout.addWidget(label(text, wrap=True))

        self.fill_input = QLineEdit()
        self.fill_input.setPlaceholderText("value for the empty rows" if missing or truncated else "not needed")
        self.fill_input.setVisible(bool(missing or truncated))
        self.fill_input.textChanged.connect(self._check)
        layout.addWidget(self.fill_input)
        if missing or truncated:
            layout.addWidget(label("Typed as it is, without quotes. Values typed in the rows themselves before "
                                   "you run are kept.", "note", wrap=True))
        self.status = label("", wrap=True)
        self.status.setStyleSheet(f"QLabel {{ color: {ERROR_COLOR}; font-size: 12px; background: transparent; }}")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(button("Cancel", on_click=self.reject))
        self.ok_btn = button("Require a Value", "primary", self._accept)
        self.ok_btn.setDefault(True)
        buttons.addWidget(self.ok_btn)
        layout.addLayout(buttons)
        self._check()
        self.fill_input.setFocus()

    def _problem(self):
        text = self.fill_input.text().strip()
        if self.needed and not text:
            return "Type the value the empty rows get."
        if text and is_numeric_type(self.type_name) and not looks_like_number(text):
            return f"{self.type_name} holds numbers, and \"{text}\" is not one."
        return None

    def _check(self):
        problem = self._problem()
        self.ok_btn.setEnabled(problem is None)
        self.status.setText(problem if problem and self.fill_input.text().strip() else "")

    def _accept(self):
        if self._problem() is None:
            self.fill = self.fill_input.text().strip()
            self.accept()


def ask_fill_value(parent, table, column, type_name, missing, truncated):
    """The value for the rows without one ("" for none), or None when cancelled."""
    dialog = RequireValueDialog(parent, table, column, type_name, missing, truncated)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.fill
