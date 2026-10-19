"""
TableState - what the table editor knows about one table, and the SQL that saves its edits.

It holds no widgets, so the change tracking can be tested without a running UI.

A live table mirrors one that exists in the connected database; any other is a new table designed
in the editor. Edits are tracked against what the database holds:

  columns        [name, type, "Null"/"Not Null", "PK"/"FK"/"-", fk_table, fk_field(, "AUTO"/"-")]
  column_origin  per column: its name in the database, None if added here
  dropped_columns  database names of columns deleted here
  rows           per row: one value per column (as read, or the text typed in a cell)
  row_origin     per row: {database column name: value} as read, None if added here
  deleted_rows   origins of rows deleted here
"""

from datetime import date

from dbmanager.sql import generator as sqlgen

NULL_TEXT = "NULL"


def cell_text(value):
    """A value as the editor shows it and compares it: NULL for None, everything else as text."""
    return NULL_TEXT if value is None else str(value)


def is_primary_key(column):
    return len(column) > 3 and column[3] == "PK"


def is_foreign_key(column):
    return len(column) > 3 and column[3] == "FK"


def is_auto_increment(column):
    return len(column) > 6 and column[6] == "AUTO"


class TableState:
    def __init__(self, name, db_type, live=False, view=False):
        self.name = name
        self.db_type = db_type
        self.live = live
        self.view = view               # a database view: shown, but neither its schema nor rows are edited
        self.columns = []
        self.column_origin = []
        self.dropped_columns = []
        self.rows = []
        self.row_origin = []
        self.deleted_rows = []
        self.rows_loaded = False
        self.pending_drop = False      # the table is to be dropped on the next run

    @property
    def editable(self):
        return not self.view

    # ---------------- Columns ----------------
    def column_names(self):
        return [column[0] for column in self.columns]

    def has_column(self, name, ignore_index=None):
        """Column names clash regardless of case: most databases treat them case-insensitively."""
        wanted = name.lower()
        return any(column[0].lower() == wanted for i, column in enumerate(self.columns) if i != ignore_index)

    def add_column(self, column, origin=None):
        """Add a column; returns the value each existing row gets for it."""
        column = list(column)
        self.columns.append(column)
        self.column_origin.append(origin)
        defaults = []
        for row_index, row in enumerate(self.rows):
            value = self._new_column_default(column, row_index)
            row.append(value)
            defaults.append(value)
        return defaults

    def _new_column_default(self, column, row_index):
        # A foreign key starts empty: a made-up number would point at a row that may not exist
        if self.live or is_foreign_key(column):
            return ""  # existing rows get the database default; type a value to set one
        if sqlgen.is_integer_type(column[1]):
            return row_index + 1
        if sqlgen.is_money_type(column[1]):
            return "0"
        return ""

    def rename_column(self, index, new_name):
        self.columns[index][0] = new_name

    def delete_column(self, index):
        del self.columns[index]
        origin = self.column_origin.pop(index)
        if origin is not None:
            self.dropped_columns.append(origin)
        for row in self.rows:
            if index < len(row):
                del row[index]

    # ---------------- Rows ----------------
    def add_row(self):
        """Append a row of starting values and return it."""
        row = [self._new_row_default(column) for column in self.columns]
        self.rows.append(row)
        self.row_origin.append(None)
        return row

    def _new_row_default(self, column):
        type_name = column[1]
        if self.live or is_auto_increment(column):
            return ""  # the database fills empty cells with defaults (identity, serial, ...)
        if is_foreign_key(column):
            return ""  # a made-up number would point at a row that may not exist
        if is_primary_key(column) or sqlgen.is_integer_type(type_name):
            return len(self.rows) + 1
        if sqlgen.is_exact_decimal_type(type_name):
            return "0"
        if "date" in sqlgen.base_type(type_name):
            return date.today().isoformat()
        return ""

    def set_cell(self, row, column, value):
        self.rows[row][column] = value

    def delete_rows(self, indexes):
        for index in sorted(set(indexes), reverse=True):
            del self.rows[index]
            origin = self.row_origin.pop(index)
            if origin is not None:
                self.deleted_rows.append(origin)

    def load_rows(self, result_columns, rows):
        """Rows read from the database (values already JSON-decoded), matched to columns by name."""
        position = {name: i for i, name in enumerate(result_columns)}
        self.rows = []
        self.row_origin = []
        for row in rows:
            self.rows.append([row[position[origin]] if origin in position else ""
                              for origin in self.column_origin])
            self.row_origin.append({name: row[i] for name, i in position.items()})
        self.deleted_rows = []
        self.rows_loaded = True

    # ---------------- Changes -> SQL ----------------
    def has_changes(self):
        return bool(self.schema_statements([]) or self.data_statements())

    def schema_statements(self, foreign_keys):
        """CREATE/ALTER/DROP needed to bring the database in line with this table.
        foreign_keys: [(column, referenced_table, referenced_column)] used when creating the table."""
        if self.pending_drop:
            return [sqlgen.drop_table(self.name, self.db_type, view=self.view)] if self.live else []
        if self.view:
            return []
        if not self.live:
            if not self.columns:
                return []
            return [sqlgen.create_table(self.name, self.columns, foreign_keys, self.db_type)]

        statements = [sqlgen.drop_column(self.name, name, self.db_type) for name in self.dropped_columns]
        for column, origin in zip(self.columns, self.column_origin):
            if origin is None:
                statements.append(sqlgen.add_column(self.name, column, self.db_type))
            elif origin != column[0]:
                statements.append(sqlgen.rename_column(self.name, origin, column[0], self.db_type))
        return statements

    def data_statements(self):
        """DELETE/UPDATE/INSERT for the rows changed here (run after the schema statements)."""
        if self.pending_drop or self.view or not self.columns:
            return []
        statements = []
        for origin in self.deleted_rows:
            where = self._row_identity(origin)
            if where:
                statements.append(sqlgen.delete(self.name, where, self.db_type))

        for row, origin in zip(self.rows, self.row_origin):
            if origin is None:
                assignments = [
                    (column[0], sqlgen.literal(cell_text(value), column[1], self.db_type))
                    for column, value in zip(self.columns, row)
                    if value is not None and str(value).strip() != ""
                ]
                statements.append(sqlgen.insert(self.name, assignments, self.db_type))
                continue

            assignments = []
            for column, value, column_origin in zip(self.columns, row, self.column_origin):
                before = cell_text(origin.get(column_origin)) if column_origin is not None else ""
                if cell_text(value) != before:
                    assignments.append((column[0], sqlgen.literal(cell_text(value), column[1], self.db_type)))
            where = self._row_identity(origin)
            if assignments and where:
                statements.append(sqlgen.update(self.name, assignments, where, self.db_type))
        return statements

    def _row_identity(self, origin):
        """WHERE conditions that find a row as it was read: its primary key, or every column if there is none.
        Columns use their current names: schema statements (renames included) run before row statements."""
        known = [(column, column_origin) for column, column_origin in zip(self.columns, self.column_origin)
                 if column_origin is not None and column_origin in origin]
        keys = [entry for entry in known if is_primary_key(entry[0])] or known
        return [(column[0], sqlgen.literal(origin[column_origin], column[1], self.db_type))
                for column, column_origin in keys]
