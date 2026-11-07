"""Joining two tables in the query on fields of your choice - without changing the database."""

from PyQt6.QtWidgets import QComboBox, QDialog, QGridLayout, QHBoxLayout, QVBoxLayout

from dbmanager.i18n import tr
from dbmanager.model.links import same_family
from dbmanager.model.query import JOIN_KINDS, Join
from dbmanager.sql.identifiers import quote_identifier
from dbmanager.ui.common.dark_dialog import DIALOG_STYLE, ERROR_COLOR, button, label
from dbmanager.ui.common.style import COMBO_ARROW, MONOSPACE
from dbmanager.ui.common.theme import qss

# A theme.qss template: the dialog is modal, so it takes the theme as it is when made
_STYLE = DIALOG_STYLE + COMBO_ARROW + f"""
    QComboBox {{
        background-color: @sunken; color: @text; border: 2px solid @border_strong; border-radius: 10px;
        padding: 8px 14px; font-size: 14px;
    }}
    QComboBox:focus {{ border: 2px solid @focus; }}
    QComboBox QAbstractItemView {{
        background-color: @sunken; color: @text; selection-background-color: @selection;
        selection-color: @on_selection; border: 1px solid @border_strong; outline: none;
    }}
    QLabel#preview {{
        color: @code_text; background-color: @code_background; border: 1px solid @border; border-radius: 8px;
        padding: 8px 10px; font-family: {MONOSPACE}; font-size: 12px;
    }}
    QPushButton#danger {{ background-color: transparent; color: @danger_text; padding: 8px 4px; }}
    QPushButton#danger:hover {{ color: @danger_text; text-decoration: underline; }}
"""


def _singular(name):
    lowered = name.lower()
    return lowered[:-1] if lowered.endswith("s") else lowered


def guess_fields(left_table, left_columns, right_table, right_columns):
    """The two fields two tables most likely join on: orders.customer_id with customers.id, then two fields
    of the same name (other than id) and kind; else the first of each. columns: [(name, type)]."""
    def find(columns, *names):
        wanted = {name.lower() for name in names}
        return next((column for column in columns if column[0].lower() in wanted), None)

    for one, one_columns, other, other_columns, swap in ((left_table, left_columns, right_table, right_columns, False),
                                                         (right_table, right_columns, left_table, left_columns, True)):
        key = find(one_columns, "id")
        pointer = find(other_columns, f"{_singular(one)}_id", f"{one.lower()}_id", f"{_singular(one)}id")
        if key and pointer:
            return (pointer[0], key[0]) if swap else (key[0], pointer[0])
    for name, type_name in left_columns:
        match = find(right_columns, name)
        if name.lower() != "id" and match and same_family(type_name, match[1]):
            return name, match[0]
    return (left_columns[0][0] if left_columns else ""), (right_columns[0][0] if right_columns else "")


class JoinDialog(QDialog):
    """table_columns: {table: [(field, type)]} of the tables on the diagram; query_tables: the tables the
    query reads, which the join starts from. existing: the Join being changed; right_table: the table to join
    (one the query has not joined yet). After exec(): result is the Join, or removed is True."""

    def __init__(self, parent, table_columns, query_tables, db_type=None, existing=None, right_table=None):
        super().__init__(parent)
        self.table_columns = table_columns
        self.db_type = db_type
        self.result = None
        self.removed = False
        self.setWindowTitle(tr("query.join.change_title" if existing else "query.join.title"))
        self.setStyleSheet(qss(_STYLE))
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(label(tr("query.join.heading"), "heading"))
        layout.addWidget(label(tr("query.join.note"), "note", wrap=True))

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self.left_table, self.left_field = QComboBox(), QComboBox()
        self.right_table, self.right_field = QComboBox(), QComboBox()
        grid.addWidget(label(tr("query.join.rows_of"), "caption"), 0, 0)
        grid.addWidget(self.left_table, 0, 1)
        grid.addWidget(self.left_field, 0, 2)
        grid.addWidget(label(tr("query.join.match"), "caption"), 1, 0)
        grid.addWidget(self.right_table, 1, 1)
        grid.addWidget(self.right_field, 1, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)

        self.kind = QComboBox()
        for key, meaning in JOIN_KINDS.items():
            self.kind.addItem(tr("query.join.keep", rows=meaning), key)
        layout.addWidget(self.kind)

        self.preview = label("", "preview", wrap=True)
        layout.addWidget(self.preview)
        self.status = label("", wrap=True)
        self.status.setStyleSheet(qss(f"QLabel {{ color: {ERROR_COLOR}; font-size: 12px; background: transparent; }}"))
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        if existing is not None:
            buttons.addWidget(button(tr("query.join.remove"), "danger", self._remove))
        buttons.addStretch()
        buttons.addWidget(button(tr("common.cancel"), on_click=self.reject))
        self.ok_btn = button(tr("query.dialog.apply" if existing else "query.join.join"), "primary", self._apply)
        self.ok_btn.setDefault(True)
        buttons.addWidget(self.ok_btn)
        layout.addLayout(buttons)

        lefts = [table for table in query_tables if table in table_columns] or list(table_columns)
        if existing is not None and existing.left_table not in lefts:
            lefts.insert(0, existing.left_table)
        if right_table in lefts and len(lefts) > 1:
            lefts.remove(right_table)
        self.left_table.addItems(lefts)
        self.left_table.currentTextChanged.connect(self._fill_right_tables)
        self.right_table.currentTextChanged.connect(self._fill_fields)
        for combo in (self.left_field, self.right_field, self.kind):
            combo.currentIndexChanged.connect(self._update)

        if existing is not None:
            self.left_table.setCurrentText(existing.left_table)
            self._fill_right_tables()
            self.right_table.setCurrentText(existing.right_table)
            self.left_field.setCurrentText(existing.left_column)
            self.right_field.setCurrentText(existing.right_column)
            self.kind.setCurrentIndex(max(0, self.kind.findData(existing.kind)))
        else:
            self._fill_right_tables()
            if right_table:
                self.right_table.setCurrentText(right_table)
        self._update()

    def _fill_right_tables(self):
        left = self.left_table.currentText()
        self.right_table.blockSignals(True)
        current = self.right_table.currentText()
        self.right_table.clear()
        self.right_table.addItems([table for table in self.table_columns if table != left])
        if current:
            self.right_table.setCurrentText(current)
        self.right_table.blockSignals(False)
        self._fill_fields()

    def _fill_fields(self):
        left, right = self.left_table.currentText(), self.right_table.currentText()
        left_columns, right_columns = self.table_columns.get(left, []), self.table_columns.get(right, [])
        for combo, columns in ((self.left_field, left_columns), (self.right_field, right_columns)):
            combo.blockSignals(True)
            combo.clear()
            for name, type_name in columns:
                combo.addItem(f"{name}  ({type_name})" if type_name else name, name)
            combo.blockSignals(False)
        left_guess, right_guess = guess_fields(left, left_columns, right, right_columns)
        self.left_field.setCurrentIndex(max(0, self.left_field.findData(left_guess)))
        self.right_field.setCurrentIndex(max(0, self.right_field.findData(right_guess)))
        self._update()

    def join(self):
        return Join(self.left_table.currentText(), self.left_field.currentData() or "",
                    self.right_table.currentText(), self.right_field.currentData() or "", self.kind.currentData())

    def _type(self, table, field):
        return dict(self.table_columns.get(table, [])).get(field, "")

    def _problem(self, join):
        if not join.right_table or not join.left_column or not join.right_column:
            return tr("query.join.no_other_table")
        left_type, right_type = self._type(join.left_table, join.left_column), self._type(join.right_table,
                                                                                         join.right_column)
        if not same_family(left_type, right_type):
            return tr("query.join.cannot_compare", left=f"{join.left_table}.{join.left_column}", left_type=left_type,
                      right=f"{join.right_table}.{join.right_column}", right_type=right_type)
        return None

    def _update(self):
        join = self.join()
        problem = self._problem(join)
        self.status.setText(problem or "")
        self.ok_btn.setEnabled(problem is None)

        def q(name):
            return quote_identifier(name, self.db_type) if self.db_type else name
        keyword = "LEFT JOIN" if join.kind == "LEFT" else "JOIN"
        self.preview.setText(f"FROM {q(join.left_table)}\n{keyword} {q(join.right_table)} ON "
                             f"{q(join.left_table)}.{q(join.left_column)} = {q(join.right_table)}.{q(join.right_column)}"
                             if problem is None else "…")

    def _apply(self):
        join = self.join()
        if self._problem(join) is None:
            self.result = join
            self.accept()

    def _remove(self):
        self.removed = True
        self.accept()
