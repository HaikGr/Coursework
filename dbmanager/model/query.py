"""The query built on the diagram, without widgets.

Which columns it shows, how each one is summarised (SUM, AVG, ...) and sorted; the filters that keep only
some rows (WHERE) or some groups (HAVING); and the SELECT that says all of it in the dialect of the database.
Tables are joined along the links drawn on the diagram (primary key - foreign key).

As soon as one column is summarised, the others are what the rows are grouped by: that is the only way the
database accepts them side by side, so the GROUP BY is written for the user rather than left to them.

Tables are joined along the links of the diagram (foreign keys, saved or about to be), and along the joins
made for the query alone (Join…): those change nothing in the database, may join on any two fields, and may
keep the rows that match nothing (LEFT JOIN). Where both connect two tables, the query's own join wins."""

import re
from collections import deque
from dataclasses import dataclass

from dbmanager.sql.generator import is_numeric_type, is_text_type, literal, looks_like_number
from dbmanager.sql.identifiers import quote_identifier

# key -> (name on buttons and in menus, what it gives back)
AGGREGATES = {
    "SUM": ("SUM", "the total of the values"),
    "AVG": ("AVG", "the average of the values"),
    "COUNT": ("COUNT", "how many rows have a value"),
    "COUNT_DISTINCT": ("COUNT UNIQUE", "how many different values there are"),
    "MIN": ("MIN", "the smallest value"),
    "MAX": ("MAX", "the largest value"),
}
_NUMBERS_ONLY = {"SUM", "AVG"}
_COUNTS = {"COUNT", "COUNT_DISTINCT"}
ROW_COUNT = "row_count"


def aggregate_sql(aggregate, expression):
    if aggregate is None:
        return expression
    if aggregate == "COUNT_DISTINCT":
        return f"COUNT(DISTINCT {expression})"
    return f"{aggregate}({expression})"


def aggregate_problem(aggregate, column_label, type_name):
    """Why this aggregate cannot summarise a column of this type, or None when it can.
    A column whose type is not known gets the benefit of the doubt."""
    if aggregate in _NUMBERS_ONLY and type_name and not is_numeric_type(type_name):
        return f"{AGGREGATES[aggregate][0]} works on numbers, and {column_label} holds {type_name} values"
    return None


# ---------------- Filters ----------------
LIST = -1  # an operator that takes a comma separated list of values


@dataclass(frozen=True)
class Operator:
    key: str
    label: str
    values: int  # how many values it takes: 0, 1, 2 or LIST
    text_only: bool = False


OPERATORS = [
    Operator("=", "equals", 1),
    Operator("<>", "does not equal", 1),
    Operator(">", "is greater than", 1),
    Operator(">=", "is at least", 1),
    Operator("<", "is less than", 1),
    Operator("<=", "is at most", 1),
    Operator("BETWEEN", "is between", 2),
    Operator("IN", "is one of", LIST),
    Operator("NOT IN", "is none of", LIST),
    Operator("CONTAINS", "contains", 1, text_only=True),
    Operator("STARTS", "starts with", 1, text_only=True),
    Operator("ENDS", "ends with", 1, text_only=True),
    Operator("IS NULL", "is empty (NULL)", 0),
    Operator("IS NOT NULL", "is not empty", 0),
    Operator("SQL", "custom SQL", 1),
]
OPERATOR_BY_KEY = {operator.key: operator for operator in OPERATORS}
_SYMBOLS = {"=", "<>", ">", ">=", "<", "<="}


def operators_for(type_name):
    """The operators that make sense for values of this type (all of them when it is not known)"""
    text = not type_name or is_text_type(type_name)
    return [operator for operator in OPERATORS if text or not operator.text_only]


def split_list(text):
    """'Ann, Bob ,, Zoe' -> ['Ann', 'Bob', 'Zoe']"""
    return [part.strip() for part in (text or "").split(",") if part.strip()]


def _like(operator, value, db_type):
    """(LIKE or ILIKE, the pattern) matching the value as typed: its own % and _ match only themselves.
    ILIKE where the database has it, so "contains" ignores case everywhere, as it does in MySQL and SQL Server."""
    if db_type == "SQLSERVER":
        escaped = re.sub(r"([\[%_])", r"[\1]", value)
    else:
        escaped = re.sub(r"([\\%_])", r"\\\1", value)
    pattern = {"CONTAINS": f"%{escaped}%", "STARTS": f"{escaped}%", "ENDS": f"%{escaped}"}[operator]
    return ("ILIKE" if db_type in ("POSTGRESQL", "H2") else "LIKE"), pattern


@dataclass
class Filter:
    """One condition on a column. With an aggregate it tests that aggregate of each group (HAVING)
    rather than each row (WHERE). Values are kept as the user typed them; quoting is done here."""
    table: str
    column: str
    type_name: str = ""
    operator: str = "="
    values: tuple = ()
    aggregate: str = None

    @property
    def key(self):
        return self.table, self.column

    def value_type(self):
        """The type the values are compared as: a count is a number whatever it counts"""
        return "bigint" if self.aggregate in _COUNTS else self.type_name

    def target_label(self):
        return aggregate_sql(self.aggregate, f"{self.table}.{self.column}")

    def _values(self):
        operator = OPERATOR_BY_KEY[self.operator]
        values = [str(value).strip() for value in self.values]
        if operator.values == LIST:
            return split_list(values[0] if values else "")
        return (values + ["", ""])[:operator.values]

    def problem(self):
        """What keeps the filter from being used, or None"""
        operator = OPERATOR_BY_KEY.get(self.operator)
        if operator is None:
            return "Pick a way to compare"
        values = self._values()
        if self.operator == "SQL":
            return None if values[0] else "Type the rest of the condition, for example > 100"
        if operator.values == LIST and not values:
            return "Type at least one value - separate several with commas"
        if operator.values == 2 and not all(values):
            return "Type both values"
        if operator.values == 1 and not values[0]:
            return "Type a value"
        if self.operator in ("=", "<>") and values[0].upper() == "NULL":
            return "To find missing values, choose \"is empty (NULL)\""
        if operator.values and not operator.text_only and is_numeric_type(self.value_type()):
            for value in values:
                if not looks_like_number(value):
                    return f"{self.target_label()} holds numbers, and \"{value}\" is not one"
        return None

    def sql(self, column_sql, db_type):
        """The condition as SQL; column_sql is the column, already quoted for the database"""
        operator = OPERATOR_BY_KEY[self.operator]
        target = aggregate_sql(self.aggregate, column_sql)
        values = self._values()
        if self.operator == "SQL":
            return f"{target} {values[0]}"
        if operator.values == 0:
            return f"{target} {self.operator}"
        if operator.text_only:
            keyword, pattern = _like(self.operator, values[0], db_type)
            return f"{target} {keyword} {literal(pattern, 'text', db_type)}"

        def as_sql(value):
            return literal(value, self.value_type(), db_type)
        if operator.values == 2:
            return f"{target} BETWEEN {as_sql(values[0])} AND {as_sql(values[1])}"
        if operator.values == LIST:
            return f"{target} {self.operator} ({', '.join(as_sql(value) for value in values)})"
        return f"{target} {self.operator} {as_sql(values[0])}"

    def describe(self):
        """The filter in words, for the query panel: orders.total > 100, customers.name contains "an" """
        operator = OPERATOR_BY_KEY[self.operator]
        target = self.target_label()
        values = self._values()
        if self.operator == "SQL":
            return f"{target} {values[0]}"
        if operator.values == 0:
            return f"{target} {operator.label}"
        shown = [value if looks_like_number(value) else f'"{value}"' for value in values]
        if operator.values == 2:
            return f"{target} between {shown[0]} and {shown[1]}"
        if operator.values == LIST:
            return f"{target} {operator.label} {', '.join(shown)}"
        return f"{target} {self.operator if self.operator in _SYMBOLS else operator.label} {shown[0]}"


# ---------------- Joins made for the query ----------------
JOIN_KINDS = {"INNER": "only the rows that match in both tables",
              "LEFT": "every row of the first table, with or without a match"}


@dataclass
class Join:
    """left_table.left_column = right_table.right_column. LEFT keeps every row of the left table."""
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    kind: str = "INNER"

    def tables(self):
        return self.left_table, self.right_table

    def describe(self):
        keyword = "LEFT JOIN" if self.kind == "LEFT" else "JOIN"
        return (f"{self.left_table} {keyword} {self.right_table} ON {self.left_table}.{self.left_column} = "
                f"{self.right_table}.{self.right_column}")


# ---------------- Columns and the query ----------------
@dataclass
class QueryColumn:
    table: str
    column: str
    type_name: str = ""
    aggregate: str = None
    sort: str = None  # "ASC", "DESC" or None

    @property
    def key(self):
        return self.table, self.column

    def label(self):
        return aggregate_sql(self.aggregate, f"{self.table}.{self.column}")


def _path(graph, start_tables, goal):
    """The shortest chain of links from any of start_tables to goal: [(from, to, link)], or None"""
    parent = {table: None for table in start_tables}
    queue = deque(start_tables)
    while queue:
        current = queue.popleft()
        if current == goal:
            steps = []
            while parent[current] is not None:
                previous, link = parent[current]
                steps.append((previous, current, link))
                current = previous
            return steps[::-1]
        for neighbour, link in graph.get(current, []):
            if neighbour not in parent:
                parent[neighbour] = (current, link)
                queue.append(neighbour)
    return None


def _alias(text):
    return re.sub(r"\W+", "_", text).strip("_").lower() or "value"


class QueryModel:
    def __init__(self):
        self.columns = []
        self.filters = []
        self.links = []  # (pk_table, pk_column, fk_table, fk_column), as drawn on the diagram
        self.joins = []  # Join: made for this query only
        self.unjoined = []  # after build(): the tables nothing joins to the others (cross-joined)
        self.distinct = False
        self.count_rows = False
        self.limit = 0  # 0: every row
        self.match_any = False  # filters joined with OR instead of AND
        self._sort_order = []  # keys of the sorted columns: the first one sorts first

    def clear(self):
        """Forget everything picked; the links stay, they belong to the diagram"""
        self.columns.clear()
        self.filters.clear()
        self.joins.clear()
        self._sort_order.clear()
        self.distinct = self.count_rows = self.match_any = False
        self.limit = 0

    def is_empty(self):
        return not (self.columns or self.filters)

    # ---------------- Columns ----------------
    def column(self, table, column):
        return next((entry for entry in self.columns if entry.key == (table, column)), None)

    def add_column(self, table, column, type_name=""):
        """The column, added at the end; None when it is in the query already"""
        if self.column(table, column) is not None:
            return None
        entry = QueryColumn(table, column, type_name)
        self.columns.append(entry)
        return entry

    def remove_column(self, table, column):
        entry = self.column(table, column)
        if entry is None:
            return False
        self.columns.remove(entry)
        if entry.key in self._sort_order:
            self._sort_order.remove(entry.key)
        return True

    def set_aggregate(self, table, column, aggregate):
        self.column(table, column).aggregate = aggregate or None

    def set_sort(self, table, column, direction):
        entry = self.column(table, column)
        entry.sort = direction or None
        if entry.key in self._sort_order:
            self._sort_order.remove(entry.key)
        if entry.sort:
            self._sort_order.append(entry.key)

    def sort_rank(self, table, column):
        """1, 2, ... when several columns are sorted (the first one decides first); None otherwise"""
        if len(self._sort_order) < 2 or (table, column) not in self._sort_order:
            return None
        return self._sort_order.index((table, column)) + 1

    def is_grouped(self):
        """True when the rows are summarised: the columns shown as they are become the groups"""
        return (self.count_rows or any(entry.aggregate for entry in self.columns)
                or any(entry.aggregate for entry in self.filters))

    def is_group_key(self, table, column):
        entry = self.column(table, column)
        return entry is not None and entry.aggregate is None and self.is_grouped()

    # ---------------- Filters ----------------
    def add_filter(self, condition):
        self.filters.append(condition)
        return len(self.filters) - 1

    def replace_filter(self, index, condition):
        self.filters[index] = condition

    def remove_filter(self, index):
        del self.filters[index]

    def filters_on(self, table, column):
        return [condition for condition in self.filters if condition.key == (table, column)]

    def remove_filters_on(self, table, column):
        self.filters = [condition for condition in self.filters if condition.key != (table, column)]

    # ---------------- Joins ----------------
    def add_join(self, join):
        self.joins.append(join)
        return len(self.joins) - 1

    def replace_join(self, index, join):
        self.joins[index] = join

    def remove_join(self, index):
        del self.joins[index]

    # ---------------- The schema changed ----------------
    def rename_column(self, table, old_name, new_name):
        for entry in self.columns + self.filters:
            if entry.key == (table, old_name):
                entry.column = new_name
        for join in self.joins:
            if (join.left_table, join.left_column) == (table, old_name):
                join.left_column = new_name
            if (join.right_table, join.right_column) == (table, old_name):
                join.right_column = new_name
        self._sort_order = [(table, new_name) if key == (table, old_name) else key for key in self._sort_order]

    def drop_column(self, table, column):
        self.remove_column(table, column)
        self.remove_filters_on(table, column)
        self.joins = [join for join in self.joins
                      if (table, column) not in ((join.left_table, join.left_column),
                                                 (join.right_table, join.right_column))]

    def drop_table(self, table):
        for entry in [entry for entry in self.columns if entry.table == table]:
            self.remove_column(*entry.key)
        self.filters = [condition for condition in self.filters if condition.table != table]
        self.joins = [join for join in self.joins if table not in join.tables()]

    def keep_only(self, known):
        """Forget the columns and filters the database no longer has. known: {table: {column, ...}}.
        True when something was forgotten."""
        def exists(entry):
            return entry.column in known.get(entry.table, ())
        gone = [entry for entry in self.columns if not exists(entry)]
        for entry in gone:
            self.remove_column(*entry.key)
        kept = [condition for condition in self.filters if exists(condition)]
        joins = [join for join in self.joins if join.left_column in known.get(join.left_table, ())
                 and join.right_column in known.get(join.right_table, ())]
        changed = bool(gone) or len(kept) != len(self.filters) or len(joins) != len(self.joins)
        self.filters, self.joins = kept, joins
        return changed

    # ---------------- SQL ----------------
    def tables(self):
        """Every table the query reads, in the order it was first used"""
        return list(dict.fromkeys(entry.table for entry in self.columns + self.filters))

    def _needs_row_count(self):
        return self.count_rows or (self.is_grouped() and not self.columns)

    def _output_names(self):
        """The name of each column of the result. A summary is named after what it computes (sum_total);
        a column whose name another one has too is prefixed with its table (orders_id)."""
        wanted = {entry.key: entry.column if entry.aggregate is None else f"{entry.aggregate}_{entry.column}"
                  for entry in self.columns}
        if self._needs_row_count():
            wanted[ROW_COUNT] = ROW_COUNT
        taken = [name.lower() for name in wanted.values()]
        names, used = {}, set()
        for key, name in wanted.items():
            if key != ROW_COUNT and taken.count(name.lower()) > 1:
                entry = self.column(*key)
                name = f"{entry.table}_{entry.column}" if entry.aggregate is None else \
                    f"{entry.aggregate}_{entry.table}_{entry.column}"
            if key == ROW_COUNT or self.column(*key).aggregate or name != key[1]:
                name = _alias(name)
            unique, number = name, 2
            while unique.lower() in used:
                unique, number = f"{name}_{number}", number + 1
            used.add(unique.lower())
            names[key] = unique
        return names

    def build(self, db_type=None):
        """(the SELECT, warnings about it). The SELECT is "" while nothing is picked.
        Without a database type names are left bare, as they are typed."""
        tables = self.tables()
        if not tables:
            return "", []

        def q(name):
            return quote_identifier(name, db_type) if db_type else name

        def col(table, column):
            return f"{q(table)}.{q(column)}"

        warnings = []
        names = self._output_names()
        select = []
        for entry in self.columns:
            expression = aggregate_sql(entry.aggregate, col(entry.table, entry.column))
            if names[entry.key] != entry.column:
                expression += f" AS {q(names[entry.key])}"
            select.append(expression)
            problem = aggregate_problem(entry.aggregate, f"{entry.table}.{entry.column}", entry.type_name)
            if problem:
                warnings.append(problem)
        if self._needs_row_count():
            select.append(f"COUNT(*) AS {q(names[ROW_COUNT])}")

        head = "SELECT DISTINCT" if self.distinct else "SELECT"
        if self.limit and db_type == "SQLSERVER":
            head += f" TOP ({self.limit})"
        lines = [f"{head} " + ",\n       ".join(select or ["*"])]

        from_lines, join_warnings = self._from(tables, q, col)
        lines += from_lines
        warnings += join_warnings

        usable = []
        for condition in self.filters:
            problem = condition.problem()
            if problem:
                warnings.append(f"The filter on {condition.target_label()} is left out: {problem}")
            else:
                usable.append(condition)
        where = self._conditions([c for c in usable if not c.aggregate], col, db_type)
        having = self._conditions([c for c in usable if c.aggregate], col, db_type)
        if where:
            lines.append(f"WHERE {where}")
        if self.is_grouped():
            keys = [col(entry.table, entry.column) for entry in self.columns if entry.aggregate is None]
            if keys:
                lines.append("GROUP BY " + ", ".join(keys))
        if having:
            lines.append(f"HAVING {having}")

        order = []
        for key in self._sort_order:
            entry = self.column(*key)
            order.append(f"{aggregate_sql(entry.aggregate, col(*key))} {entry.sort}")
        if order:
            lines.append("ORDER BY " + ", ".join(order))
        if self.limit and db_type != "SQLSERVER":
            lines.append(f"LIMIT {self.limit}")
        return "\n".join(lines), warnings

    def _conditions(self, conditions, col, db_type):
        parts = [condition.sql(col(condition.table, condition.column), db_type) for condition in conditions]
        if len(parts) > 1:
            # A custom condition may hold an OR of its own: brackets keep it whole
            parts = [f"({part})" if condition.operator == "SQL" else part
                     for condition, part in zip(conditions, parts)]
        return ("\n   OR " if self.match_any else "\n  AND ").join(parts)

    def _from(self, tables, q, col):
        """FROM the first table, JOIN the others along the shortest chain of joins and links. A table with no
        chain to the others is still read, by a CROSS JOIN, and a warning says how to join it."""
        graph = {}
        for join in self.joins:  # first: where both connect two tables, the query's own join is taken
            graph.setdefault(join.left_table, []).append((join.right_table, join))
            graph.setdefault(join.right_table, []).append((join.left_table, join))
        for link in self.links:
            pk_table, _, fk_table, _ = link
            graph.setdefault(pk_table, []).append((fk_table, link))
            graph.setdefault(fk_table, []).append((pk_table, link))

        joined, lines, warnings = [tables[0]], [f"FROM {q(tables[0])}"], []
        self.unjoined = []
        remaining = tables[1:]
        while remaining:
            path = None
            for table in remaining:
                path = _path(graph, joined, table)
                if path:
                    break
            if not path:
                table = remaining.pop(0)
                lines.append(f"CROSS JOIN {q(table)}")
                warnings.append(f"{table} is not joined to {', '.join(joined)}, so every row of it is paired with "
                                "every row of the others. Choose the fields to join it on with Join… below - or "
                                "link it on the diagram.")
                self.unjoined.append(table)
                joined.append(table)
                continue
            for from_table, to_table, edge in path:
                lines.append(self._join_line(from_table, to_table, edge, q, col))
                joined.append(to_table)
                if to_table in remaining:
                    remaining.remove(to_table)
        return lines, warnings

    @staticmethod
    def _join_line(from_table, to_table, edge, q, col):
        """JOIN to_table ON ..., the side already in the query first"""
        if isinstance(edge, Join):
            near, far = ((edge.left_table, edge.left_column), (edge.right_table, edge.right_column))
            if edge.left_table != from_table:
                near, far = far, near
            keyword = "JOIN"
            if edge.kind == "LEFT":
                # the left table keeps all its rows: reached from the right, that is a RIGHT JOIN
                keyword = "LEFT JOIN" if edge.left_table == from_table else "RIGHT JOIN"
            return f"{keyword} {q(to_table)} ON {col(*near)} = {col(*far)}"
        pk_table, pk_column, fk_table, fk_column = edge
        pk, fk = col(pk_table, pk_column), col(fk_table, fk_column)
        return f"JOIN {q(to_table)} ON {pk} = {fk}" if pk_table == from_table else f"JOIN {q(to_table)} ON {fk} = {pk}"
