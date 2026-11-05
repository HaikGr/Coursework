"""Adding or changing one filter of the query: how a column is compared, and with what."""

from PyQt6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from dbmanager.model.query import AGGREGATES, LIST, OPERATOR_BY_KEY, Filter, operators_for
from dbmanager.sql.generator import is_numeric_type
from dbmanager.sql.identifiers import quote_identifier
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, ERROR_COLOR, button, label
from dbmanager.ui.common.style import COMBO_ARROW, MONOSPACE

_STYLE = DIALOG_STYLE + f"""
    QComboBox {{
        background-color: #0f172a;
        color: #f1f5f9;
        border: 2px solid #334155;
        border-radius: 10px;
        padding: 8px 14px;
        font-size: 14px;
    }}
    QComboBox:focus {{ border: 2px solid #0ea5e9; }}
    QComboBox QAbstractItemView {{
        background-color: #0f172a;
        color: #f1f5f9;
        selection-background-color: #0ea5e9;
        border: 1px solid #334155;
        outline: none;
    }}
    QLabel#preview {{
        color: #a5f3fc;
        background-color: #0f172a;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 8px 10px;
        font-family: {MONOSPACE};
        font-size: 12px;
    }}
    QPushButton#danger {{ background-color: transparent; color: #fca5a5; padding: 8px 4px; }}
    QPushButton#danger:hover {{ color: #fecaca; text-decoration: underline; }}
""" + COMBO_ARROW

_HINTS = {
    "SQL": "Written after the column exactly as typed, for example  > 100 OR {column} IS NULL",
    "CONTAINS": "Finds the text anywhere in the value. Type it as it is - no quotes, no % signs.",
    "STARTS": "Type the beginning as it is - no quotes, no % signs.",
    "ENDS": "Type the end as it is - no quotes, no % signs.",
}


def _placeholder(operator, type_name):
    if operator == "SQL":
        return "> 100"
    if OPERATOR_BY_KEY[operator].values == LIST:
        return "1, 2, 3" if is_numeric_type(type_name) else "Ann, Bob, Zoe"
    if is_numeric_type(type_name):
        return "100"
    lowered = (type_name or "").lower()
    if "date" in lowered or "time" in lowered:
        return "2024-12-31"
    return "text"


class FilterDialog(QDialog):
    """aggregate: how the column is summarised in the query now, if it is - the filter may then test each
    group (HAVING) instead of each row. existing: the filter being changed. After exec(): result is the new
    Filter, or removed is True when the user took the existing one away."""

    def __init__(self, parent, table, column, type_name="", db_type=None, existing=None, aggregate=None):
        super().__init__(parent)
        self.table, self.column, self.type_name, self.db_type = table, column, type_name or "", db_type
        self.result = None
        self.removed = False
        self.setWindowTitle("Edit Filter" if existing else "Add Filter")
        self.setStyleSheet(_STYLE)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        self.heading = label("", "heading")
        layout.addWidget(self.heading)
        about = f"{table}.{column}" + (f"   ·   {type_name}" if type_name else "")
        layout.addWidget(label(about, "caption"))

        # Rows or groups: offered while the column is summarised, or when the filter already tests groups
        self.target_combo = QComboBox()
        self.target_combo.addItem(f"each row's {column}", None)
        group_aggregate = aggregate or (existing.aggregate if existing else None)
        if group_aggregate:
            name = AGGREGATES[group_aggregate][0]
            self.target_combo.addItem(f"{name} of {column} for each group", group_aggregate)
        self.target_combo.setVisible(self.target_combo.count() > 1)
        layout.addWidget(self.target_combo)

        self.operator_combo = QComboBox()
        layout.addWidget(self.operator_combo)

        values = QHBoxLayout()
        values.setSpacing(8)
        self.value_edit = QLineEdit()
        self.and_label = label("and")
        self.second_edit = QLineEdit()
        values.addWidget(self.value_edit, stretch=1)
        values.addWidget(self.and_label)
        values.addWidget(self.second_edit, stretch=1)
        layout.addLayout(values)

        self.hint = label("", "note", wrap=True)
        layout.addWidget(self.hint)
        self.preview = label("", "preview", wrap=True)
        layout.addWidget(self.preview)
        self.status = label("", wrap=True)
        self.status.setStyleSheet(f"QLabel {{ color: {ERROR_COLOR}; font-size: 12px; background: transparent; }}")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        if existing is not None:
            buttons.addWidget(button("Remove filter", "danger", self._remove))
        buttons.addStretch()
        buttons.addWidget(button("Cancel", on_click=self.reject))
        self.apply_btn = button("Apply" if existing else "Add Filter", "primary", self._apply)
        self.apply_btn.setDefault(True)
        buttons.addWidget(self.apply_btn)
        layout.addLayout(buttons)

        if existing is not None:
            self.target_combo.setCurrentIndex(max(0, self.target_combo.findData(existing.aggregate)))
        self._fill_operators(existing.operator if existing else None)
        if existing is not None:
            stored = list(existing.values) + ["", ""]
            self.value_edit.setText(stored[0])
            self.second_edit.setText(stored[1])

        self.target_combo.currentIndexChanged.connect(lambda: self._fill_operators(self._operator()))
        self.operator_combo.currentIndexChanged.connect(self._update)
        for edit in (self.value_edit, self.second_edit):
            edit.textChanged.connect(self._update)  # Enter presses the default button: Add Filter / Apply
        self._update()
        self.value_edit.setFocus()

    # ---------------- State ----------------
    def _operator(self):
        return self.operator_combo.currentData()

    def filter(self):
        """The filter as the dialog shows it now"""
        operator = self._operator()
        values = (self.value_edit.text(), self.second_edit.text())[:max(OPERATOR_BY_KEY[operator].values, 1)]
        if OPERATOR_BY_KEY[operator].values == 0:
            values = ()
        return Filter(self.table, self.column, self.type_name, operator, tuple(values),
                      aggregate=self.target_combo.currentData())

    def _fill_operators(self, keep):
        value_type = Filter(self.table, self.column, self.type_name,
                            aggregate=self.target_combo.currentData()).value_type()
        self.operator_combo.blockSignals(True)
        self.operator_combo.clear()
        for operator in operators_for(value_type):
            self.operator_combo.addItem(operator.label, operator.key)
        self.operator_combo.setCurrentIndex(max(0, self.operator_combo.findData(keep)))
        self.operator_combo.blockSignals(False)
        self._update()

    def _update(self):
        operator = OPERATOR_BY_KEY[self._operator()]
        condition = self.filter()
        count = operator.values
        self.value_edit.setVisible(count != 0)
        self.and_label.setVisible(count == 2)
        self.second_edit.setVisible(count == 2)
        placeholder = _placeholder(operator.key, condition.value_type())
        self.value_edit.setPlaceholderText(placeholder)
        self.second_edit.setPlaceholderText(placeholder)

        if count == 0:
            hint = "No value needed."
        elif count == LIST:
            hint = "Separate the values with commas. Type them as they are - no quotes needed."
        else:
            hint = _HINTS.get(operator.key, "Type the value as it is - no quotes needed.")
        self.hint.setText(hint.format(column=self.column))

        self.heading.setText(f"Keep only the {'groups' if condition.aggregate else 'rows'} where…")
        problem = condition.problem()
        shown = {0: [], 2: [self.value_edit, self.second_edit]}.get(count, [self.value_edit])
        typed = any(edit.text().strip() for edit in shown)
        self.status.setText(problem if problem and typed else "")
        self.apply_btn.setEnabled(problem is None)
        if problem is None:
            column_sql = (f"{quote_identifier(self.table, self.db_type)}.{quote_identifier(self.column, self.db_type)}"
                          if self.db_type else f"{self.table}.{self.column}")
            clause = "HAVING" if condition.aggregate else "WHERE"
            self.preview.setText(f"{clause} {condition.sql(column_sql, self.db_type)}")
        else:
            self.preview.setText("…")

    # ---------------- Buttons ----------------
    def _apply(self):
        condition = self.filter()
        if condition.problem() is not None:
            return
        self.result = condition
        self.accept()

    def _remove(self):
        self.removed = True
        self.accept()
