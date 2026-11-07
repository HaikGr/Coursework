"""
TableState - what the table editor knows about one table, and the SQL that saves its edits.

It holds no widgets, so the change tracking can be tested without a running UI.

A live table mirrors one that exists in the connected database; any other is a new table designed
in the editor. Edits are tracked against what the database holds:

  columns        [name, type, "Null"/"Not Null", "PK"/"FK"/"-", fk_table, fk_field(, "AUTO"/"-", default)]
  column_meta    per column: {"origin": its name in the database (None if added here), "was_nullable": as read,
                 "fill": the value its empty rows get before it requires one, "details": what the schema says
                 of it (sqlType, mysql - see db.schema)}
  dropped_columns  database names of columns deleted here
  constraints    the table's keys, indexes and other constraints, as read (see db.schema)
  rows           per row: one value per column (as read, or the text typed in a cell)
  row_origin     per row: {database column name: value} as read, None if added here
  deleted_rows   origins of rows deleted here

Its SQL comes in three parts, because the database checks a NOT NULL column when it is declared: schema
statements (constraints in the way of a drop, drops, new columns, renames, NULL allowed), then the row
statements, then the late statements (empty rows filled, NOT NULL required) - so that the values typed for
the existing rows of a new NOT NULL column are in place before the database is asked to require them.
problems() says beforehand what the database would still refuse, so a run does not stop halfway: MySQL
commits each CREATE/ALTER/DROP by itself, and a failure after one leaves the database half changed.
"""

from datetime import date

from dbmanager.i18n import join_list, tr
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


def schema_column(column):
    """A column as db.schema reads it -> the editor's list [name, type, Null/Not Null, PK/FK/-, fk_table, fk_field]"""
    referenced = column.get("referencedTable")
    flag = "PK" if column.get("primaryKey") else "FK" if referenced else "-"
    return [column["name"], column.get("type") or "", "Null" if column.get("nullable") else "Not Null", flag,
            referenced or "-", column.get("referencedColumn") or "-"]


def schema_details(column):
    """What else the editor keeps of a column read by db.schema: what changing it needs"""
    return {key: column[key] for key in ("sqlType", "mysql", "computed") if key in column}


def from_schema(table, db_type):
    """A TableState for a table as db.schema read it (its rows not loaded yet)"""
    state = TableState(table["name"], db_type, live=True, view="VIEW" in (table.get("type") or "").upper(),
                       constraints=table.get("constraints"))
    for column in table.get("columns") or []:
        state.add_column(schema_column(column), origin=column["name"], details=schema_details(column))
    return state


def _rows_text(numbers):
    """[1, 3] -> '1 and 3'; long lists are cut short"""
    shown = [str(number) for number in numbers[:5]]
    if len(numbers) > 5:
        shown.append(tr("model.table_state.more_rows", number=len(numbers) - 5))
    return join_list(shown)


class TableState:
    def __init__(self, name, db_type, live=False, view=False, constraints=None):
        self.name = name
        self.db_type = db_type
        self.live = live
        self.view = view               # a database view: shown, but neither its schema nor rows are edited
        self.columns = []
        self.column_meta = []
        self.dropped_columns = []
        self.constraints = [dict(constraint) for constraint in constraints or []]
        self.rows = []
        self.row_origin = []
        self.deleted_rows = []
        self.rows_loaded = False
        self.rows_truncated = False    # the table has more rows than were read
        self.pending_drop = False      # the table is to be dropped on the next run

    @property
    def column_origin(self):
        """Per column: its name in the database, None if added here"""
        return [meta["origin"] for meta in self.column_meta]

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

    def add_column(self, column, origin=None, details=None):
        """Add a column; returns the value each existing row gets for it.
        details: what the schema says about a column read from the database (see db.schema)."""
        column = list(column)
        self.columns.append(column)
        self.column_meta.append({"origin": origin, "was_nullable": column[2] == "Null" if origin else None,
                                 "fill": None, "details": dict(details or {})})
        defaults = []
        for row_index, row in enumerate(self.rows):
            value = self._new_column_default(column, row_index)
            row.append(value)
            defaults.append(value)
        return defaults

    def _new_column_default(self, column, row_index):
        if sqlgen.column_default(column) is not None:
            return sqlgen.column_default(column)  # what the database gives the rows already there
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
        origin = self.column_meta.pop(index)["origin"]
        if origin is not None:
            self.dropped_columns.append(origin)
        for row in self.rows:
            if index < len(row):
                del row[index]

    def set_nullable(self, index, nullable, fill=None):
        """Allow NULL in a column, or require a value. fill: what the rows without a value get first
        (for a column the database has; "" or None for none)."""
        self.columns[index][2] = "Null" if nullable else "Not Null"
        self.column_meta[index]["fill"] = None if nullable or fill in (None, "") else str(fill)

    def set_default(self, index, value):
        """Give a column added here a default value ("" or None for none). The rows already there whose cell is
        still empty show it: that is what the database gives them. Returns [(row, value)] changed."""
        column = self.columns[index]
        while len(column) < 8:  # [name, type, null, key, fk_table, fk_field, auto, default]
            column.append("-" if len(column) < 7 else None)
        column[7] = value if value not in (None, "") else None
        changed = []
        if column[7] is not None:
            for number, (row, origin) in enumerate(zip(self.rows, self.row_origin)):
                if origin is not None and str(row[index]).strip() == "":
                    row[index] = column[7]
                    changed.append((number, column[7]))
        return changed

    def rows_without_value(self, index):
        """Numbers (from 1) of the rows that would hold NULL in this column once saved"""
        column, meta = self.columns[index], self.column_meta[index]
        missing = []
        for number, (row, origin) in enumerate(zip(self.rows, self.row_origin), start=1):
            value = row[index] if index < len(row) else None
            if value is None or str(value).strip().upper() == NULL_TEXT:
                missing.append(number)
            elif str(value).strip() == "" and origin is None and sqlgen.column_default(column) is not None:
                continue  # left out of the INSERT: the database gives the row the default
            elif str(value).strip() == "":
                # an empty cell is left out of an INSERT and of a new column's UPDATE; elsewhere it is '' in text
                if origin is None or meta["origin"] is None or not sqlgen.is_text_type(column[1]):
                    missing.append(number)
        return missing

    def references_to(self, column_origin=None):
        """This table's foreign keys, as read: [{"name", "columns", "refTable", "refColumns", ...}]"""
        return [constraint for constraint in self.constraints if constraint["kind"] == "FOREIGN KEY"
                and (column_origin is None or column_origin in constraint["columns"])]

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

    def load_rows(self, result_columns, rows, truncated=False):
        """Rows read from the database (values already JSON-decoded), matched to columns by name.
        truncated: the table has more rows than these."""
        position = {name: i for i, name in enumerate(result_columns)}
        self.rows = []
        self.row_origin = []
        for row in rows:
            self.rows.append([row[position[origin]] if origin in position else ""
                              for origin in self.column_origin])
            self.row_origin.append({name: row[i] for name, i in position.items()})
        self.deleted_rows = []
        self.rows_loaded = True
        self.rows_truncated = truncated

    # ---------------- Changes -> SQL ----------------
    def has_changes(self):
        return bool(self.schema_statements([]) or self.data_statements() or self.late_statements())

    def _loosened(self, column, meta):
        return meta["origin"] is not None and meta["was_nullable"] is False and column[2] == "Null"

    def _tightened(self, column, meta):
        return meta["origin"] is not None and meta["was_nullable"] and column[2] == "Not Null"

    def _added_then_required(self, column, meta):
        """A new NOT NULL column without a default, in a table that exists: added allowing NULL, and
        required once its rows have their values"""
        return (self.live and meta["origin"] is None and column[2] == "Not Null" and not is_primary_key(column)
                and not is_auto_increment(column) and sqlgen.column_default(column) is None)

    def _nullability(self, column, meta, nullable):
        if meta["origin"] is None:  # added here: its type is the one ADD wrote
            sql_type, mysql = sqlgen.column_type_sql(column[1], self.db_type, is_auto_increment(column)), {}
        else:
            sql_type, mysql = meta["details"].get("sqlType"), meta["details"].get("mysql")
        return sqlgen.set_nullable(self.name, column[0], nullable, self.db_type, sql_type, mysql)

    def constraints_in_the_way(self, column_origin):
        """What the database will not drop together with this column, so it goes first. PostgreSQL drops a
        column's own keys and indexes with it; MySQL refuses while a foreign key uses the column; SQL Server
        while any constraint or index does. (Keys of other tables that point here: see change_script.)"""
        if self.db_type == "SQLSERVER":
            kinds = ("FOREIGN KEY", "PRIMARY KEY", "UNIQUE", "CHECK", "DEFAULT", "INDEX")
        elif self.db_type in ("MYSQL", "MARIADB"):
            kinds = ("FOREIGN KEY",)
        else:
            kinds = ()
        found = [constraint for constraint in self.constraints
                 if constraint["kind"] in kinds and column_origin in constraint["columns"]]
        return sorted(found, key=lambda constraint: constraint["kind"] != "FOREIGN KEY")

    def schema_statements(self, foreign_keys, dropped_constraints=None):
        """CREATE/ALTER/DROP needed to bring the database in line with this table, before the rows change.
        foreign_keys: [(column, referenced_table, referenced_column)] used when creating the table.
        dropped_constraints: {(table, constraint name)} dropped already in this script; added to."""
        if self.pending_drop:
            return [sqlgen.drop_table(self.name, self.db_type, view=self.view)] if self.live else []
        if self.view:
            return []
        if not self.live:
            if not self.columns:
                return []
            return [sqlgen.create_table(self.name, self.columns, foreign_keys, self.db_type)]

        dropped = dropped_constraints if dropped_constraints is not None else set()
        statements = []
        for name in self.dropped_columns:
            for constraint in self.constraints_in_the_way(name):
                if (self.name, constraint["name"]) not in dropped:
                    dropped.add((self.name, constraint["name"]))
                    statements.append(sqlgen.drop_constraint(self.name, constraint, self.db_type))
            statements.append(sqlgen.drop_column(self.name, name, self.db_type))
        for column, meta in zip(self.columns, self.column_meta):
            if meta["origin"] is None:
                statements.append(sqlgen.add_column(self.name, column, self.db_type,
                                                    allow_null=self._added_then_required(column, meta)))
            elif meta["origin"] != column[0]:
                statements.append(sqlgen.rename_column(self.name, meta["origin"], column[0], self.db_type))
        for column, meta in zip(self.columns, self.column_meta):
            if self._loosened(column, meta):
                statements.append(self._nullability(column, meta, True))
        return statements

    def late_statements(self):
        """After the rows: the rows still without a value get the chosen one, then the column requires one"""
        if not self.live or self.view or self.pending_drop:
            return []
        statements = []
        for column, meta in zip(self.columns, self.column_meta):
            if self._tightened(column, meta):
                if meta["fill"] is not None:
                    value = sqlgen.literal(meta["fill"], column[1], self.db_type)
                    statements.append(sqlgen.fill_nulls(self.name, column[0], value, self.db_type))
                statements.append(self._nullability(column, meta, False))
            elif self._added_then_required(column, meta):
                statements.append(self._nullability(column, meta, False))
        return statements

    def problems(self):
        """What the database would refuse in these changes, in words - to be fixed before running.
        [] when nothing is known to be wrong."""
        if not self.live or self.view or self.pending_drop:
            return []
        found = []
        for index, (column, meta) in enumerate(zip(self.columns, self.column_meta)):
            field = f"{self.name}.{column[0]}"
            # a new required column: without a default it waits for its values; with one, a row cleared again
            # would be set to NULL
            added = meta["origin"] is None and column[2] == "Not Null" and not is_primary_key(column) \
                and not is_auto_increment(column)
            tightened = self._tightened(column, meta) and meta["fill"] is None
            changes_null = self._loosened(column, meta) or self._tightened(column, meta)
            if changes_null and self.db_type != "POSTGRESQL" and not meta["details"].get("sqlType"):
                found.append(tr("model.table_state.type_unknown", field=field))
                continue
            if changes_null and (meta["details"].get("mysql") or {}).get("generated"):
                found.append(tr("model.table_state.computed", field=field))
                continue
            if not (added or tightened):
                continue
            remedy = tr("model.table_state.remedy_default" if added else "model.table_state.remedy_fill")
            if self.rows_truncated or not self.rows_loaded:
                if added and sqlgen.column_default(column) is not None:
                    continue  # the default reaches the rows that are not shown
                found.append(tr("model.table_state.rows_not_shown", field=field, table=self.name, remedy=remedy))
                continue
            missing = self.rows_without_value(index)
            if missing:
                # "row 2" or "rows 1 and 3": a list of row numbers rather than a count, so no plural form
                key = "rows_without_value" if len(missing) > 1 else "row_without_value"
                found.append(tr(f"model.table_state.{key}", field=field, rows=_rows_text(missing), remedy=remedy))
        return found

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
                # a new column holds its default (or nothing) until a value is typed
                before = (cell_text(origin.get(column_origin)) if column_origin is not None
                          else sqlgen.column_default(column) or "")
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
