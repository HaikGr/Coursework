"""
SQL Generator - turns edits made in the table editor into SQL for the connected database.

The backend only runs what it is sent; every CREATE/ALTER/INSERT/UPDATE/DELETE the app
executes is written here, in the dialect of the database type (PostgreSQL, MySQL, SQL Server...).

Column specs are the editor's lists:
    [name, type, "Null"/"Not Null", "PK"/"FK"/"-", fk_table, fk_field, "AUTO"/"-", default value or None]
The default value is typed like a cell (no quotes) and written as a literal of the column's type.
"""

import re

from dbmanager.sql.identifiers import quote_identifier

# Types offered by the "Add Field" dialog -> (PostgreSQL/H2, MySQL/MariaDB, SQL Server)
_TYPE_MAP = {
    "int": ("integer", "INT", "INT"),
    "bigint": ("bigint", "BIGINT", "BIGINT"),
    "smallint": ("smallint", "SMALLINT", "SMALLINT"),
    "tinyint": ("smallint", "TINYINT", "TINYINT"),
    "decimal": ("decimal(18,2)", "DECIMAL(18,2)", "DECIMAL(18,2)"),
    "numeric": ("numeric(18,2)", "NUMERIC(18,2)", "NUMERIC(18,2)"),
    "money": ("numeric(19,4)", "DECIMAL(19,4)", "MONEY"),
    "smallmoney": ("numeric(10,4)", "DECIMAL(10,4)", "SMALLMONEY"),
    "float": ("double precision", "DOUBLE", "FLOAT"),
    "real": ("real", "FLOAT", "REAL"),
    "char": ("char(1)", "CHAR(1)", "CHAR(1)"),
    "varchar": ("varchar(255)", "VARCHAR(255)", "VARCHAR(255)"),
    "nchar": ("char(1)", "NCHAR(1)", "NCHAR(1)"),
    "nvarchar": ("varchar(255)", "NVARCHAR(255)", "NVARCHAR(255)"),
    "text": ("text", "TEXT", "NVARCHAR(MAX)"),
    "ntext": ("text", "TEXT", "NVARCHAR(MAX)"),
    "date": ("date", "DATE", "DATE"),
    "datetime": ("timestamp", "DATETIME", "DATETIME"),
    "datetime2": ("timestamp", "DATETIME(6)", "DATETIME2"),
    "time": ("time", "TIME", "TIME"),
    "timestamp": ("timestamp", "TIMESTAMP", "DATETIME2"),
    "bit": ("boolean", "BOOLEAN", "BIT"),
    "binary": ("bytea", "BLOB", "VARBINARY(MAX)"),
    "varbinary": ("bytea", "BLOB", "VARBINARY(MAX)"),
    "image": ("bytea", "LONGBLOB", "VARBINARY(MAX)"),
    "uniqueidentifier": ("uuid", "CHAR(36)", "UNIQUEIDENTIFIER"),
}
# H2 understands the PostgreSQL spelling except for these
_H2_OVERRIDES = {"text": "clob", "ntext": "clob", "binary": "blob", "varbinary": "blob", "image": "blob"}

_INTEGER = {
    "int", "integer", "bigint", "smallint", "tinyint", "mediumint", "int2", "int4", "int8",
    "serial", "bigserial", "smallserial", "serial4", "serial8",
}
_EXACT_DECIMAL = {"decimal", "dec", "numeric", "number", "money", "smallmoney"}
_NUMERIC = _INTEGER | _EXACT_DECIMAL | {"float", "float4", "float8", "real", "double"}
_BOOLEAN = {"bit", "bool", "boolean"}
_TRUE = {"1", "true", "t", "yes", "y", "on"}
_FALSE = {"0", "false", "f", "no", "n", "off"}
_NUMBER = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")


def _dialect(db_type):
    if db_type in ("MYSQL", "MARIADB"):
        return 1
    if db_type == "SQLSERVER":
        return 2
    return 0


def base_type(type_name):
    """'varchar(255)' -> 'varchar', 'int unsigned' -> 'int'"""
    return re.split(r"[\s(]", (type_name or "").strip().lower(), maxsplit=1)[0]


def is_text_type(type_name):
    base = base_type(type_name)
    return "char" in base or "text" in base or base in ("clob", "string", "citext")


def is_money_type(type_name):
    return "money" in base_type(type_name)


def is_integer_type(type_name):
    return base_type(type_name) in _INTEGER


def is_numeric_type(type_name):
    return base_type(type_name) in _NUMERIC


def looks_like_number(text):
    """'12', '-3.5', '$1 200.50': what literal() writes as a number for a numeric column"""
    return bool(_NUMBER.fullmatch((text or "").strip().replace("$", "").replace(" ", "")))


def value_problem(text, type_name):
    """Why a value typed for a column of this type would be refused, to follow the column's name
    ("holds numbers (int), not "abc""); None when it can go.
    Only numbers and true/false are checked: text, dates and the rest are left to the database."""
    stripped = (text or "").strip()
    if not stripped or stripped.upper() == "NULL":
        return None
    if base_type(type_name) in _BOOLEAN or (type_name or "").lower().replace(" ", "") == "tinyint(1)":
        if stripped.lower() in _TRUE | _FALSE:
            return None
        return f"holds true or false ({type_name}; also 1/0, yes/no), not \"{stripped}\""
    if base_type(type_name) in _NUMERIC and not looks_like_number(stripped):
        return f"holds numbers ({type_name}), not \"{stripped}\""
    return None


def is_exact_decimal_type(type_name):
    """decimal/numeric/money: shown highlighted in the table editor"""
    return base_type(type_name) in _EXACT_DECIMAL


def column_type_sql(type_name, db_type, auto=False):
    """The column type to write in CREATE/ALTER, mapped from the editor's type names."""
    base = base_type(type_name)
    mapped = _TYPE_MAP.get(base) if base == (type_name or "").strip().lower() else None
    if mapped is None:
        sql_type = type_name  # a type read from the database itself: keep it as it is
    elif db_type == "H2" and base in _H2_OVERRIDES:
        sql_type = _H2_OVERRIDES[base]
    else:
        sql_type = mapped[_dialect(db_type)]

    if auto:
        dialect = _dialect(db_type)
        if dialect == 1:
            sql_type += " AUTO_INCREMENT"
        elif dialect == 2:
            sql_type += " IDENTITY(1,1)"
        else:
            sql_type += " GENERATED BY DEFAULT AS IDENTITY"
    return sql_type


def literal(value, type_name, db_type):
    """A value from the editor as an SQL literal for a column of the given type."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        value = "1" if value else "0"
    text = str(value)
    stripped = text.strip()
    if stripped.upper() == "NULL":
        return "NULL"

    base = base_type(type_name)
    if base in _BOOLEAN or (type_name or "").lower().replace(" ", "") == "tinyint(1)":
        lowered = stripped.lower()
        if lowered in _TRUE or lowered in _FALSE:
            truth = lowered in _TRUE
            if db_type == "SQLSERVER":
                return "1" if truth else "0"
            return "TRUE" if truth else "FALSE"
    if base in _NUMERIC:
        number = stripped.replace("$", "").replace(" ", "")
        if _NUMBER.fullmatch(number):
            return number
    if stripped == "" and not is_text_type(type_name):
        return "NULL"

    escaped = text.replace("'", "''")
    if db_type in ("MYSQL", "MARIADB"):
        escaped = escaped.replace("\\", "\\\\")
    if db_type == "SQLSERVER":
        return f"N'{escaped}'"
    return f"'{escaped}'"


def column_default(column):
    """The default value of a column spec, as typed; None when it has none"""
    value = column[7] if len(column) > 7 else None
    return None if value is None or str(value) == "" else str(value)


def _default_clause(table, column, db_type):
    """ DEFAULT <value>, or "" - on SQL Server a named constraint, so that it can be dropped by name later"""
    value = column_default(column)
    if value is None:
        return ""
    clause = f" DEFAULT {literal(value, column[1], db_type)}"
    if db_type == "SQLSERVER":
        name = f"DF_{table}_{column[0]}"[:128]
        clause = f" CONSTRAINT {quote_identifier(name, db_type)}{clause}"
    return clause


def create_table(table, columns, foreign_keys, db_type):
    """foreign_keys: [(fk_column, referenced_table, referenced_column)]"""
    q = lambda name: quote_identifier(name, db_type)
    parts = []
    for column in columns:
        name, type_name, nullable, flag = column[0], column[1], column[2], column[3]
        auto = len(column) > 6 and column[6] == "AUTO"
        definition = f"{q(name)} {column_type_sql(type_name, db_type, auto)}"
        if nullable == "Not Null" or flag == "PK":
            definition += " NOT NULL"
        definition += _default_clause(table, column, db_type)
        parts.append(definition)
    primary_keys = [column[0] for column in columns if column[3] == "PK"]
    if primary_keys:
        parts.append(f"PRIMARY KEY ({', '.join(q(name) for name in primary_keys)})")
    for fk_column, ref_table, ref_column in foreign_keys:
        parts.append(f"FOREIGN KEY ({q(fk_column)}) REFERENCES {q(ref_table)} ({q(ref_column)})")
    return f"CREATE TABLE {q(table)} (\n    " + ",\n    ".join(parts) + "\n)"


def preview(table, rows, db_type):
    """The first rows of a table - and one more, which tells that there are more. Limited in the SQL itself:
    the drivers would otherwise bring every row of a big table over just to show the first ones."""
    if db_type == "SQLSERVER":
        return f"SELECT TOP ({rows + 1}) * FROM {quote_identifier(table, db_type)}"
    return f"SELECT * FROM {quote_identifier(table, db_type)} LIMIT {rows + 1}"


def drop_table(table, db_type, view=False):
    return f"DROP {'VIEW' if view else 'TABLE'} {quote_identifier(table, db_type)}"


def add_column(table, column, db_type, allow_null=False):
    """ALTER TABLE ... ADD. With a default, the rows already there get it. allow_null adds a NOT NULL column
    allowing NULL for now: the first step when its values for the existing rows are written afterwards
    (see set_nullable), since the database refuses a NOT NULL column that the existing rows leave empty."""
    q = lambda name: quote_identifier(name, db_type)
    auto = len(column) > 6 and column[6] == "AUTO"
    definition = f"{q(column[0])} {column_type_sql(column[1], db_type, auto)}"
    if column[3] == "PK":
        definition += " NOT NULL PRIMARY KEY"
    elif column[2] == "Not Null" and not allow_null:
        definition += " NOT NULL"
    definition += _default_clause(table, column, db_type)
    if db_type == "SQLSERVER" and column_default(column) is not None and "NOT NULL" not in definition:
        definition += " WITH VALUES"  # as everywhere else: a nullable column's default fills the existing rows
    keyword = "ADD" if db_type == "SQLSERVER" else "ADD COLUMN"
    return f"ALTER TABLE {q(table)} {keyword} {definition}"


def mysql_column_definition(sql_type, nullable, details):
    """A MySQL/MariaDB column as MODIFY COLUMN must state it: everything it does not repeat is lost
    (the default, AUTO_INCREMENT, ON UPDATE, the comment, a character set of its own)."""
    parts = [sql_type]
    if details.get("charset") and details.get("collation"):
        parts.append(f"CHARACTER SET {details['charset']} COLLATE {details['collation']}")
    parts.append("NULL" if nullable else "NOT NULL")
    if details.get("default") is not None:
        parts.append(f"DEFAULT {details['default']}")
    parts.extend(details.get("attributes") or [])
    if details.get("comment"):
        parts.append("COMMENT '" + details["comment"].replace("\\", "\\\\").replace("'", "''") + "'")
    return " ".join(parts)


def set_nullable(table, column_name, nullable, db_type, sql_type=None, mysql=None):
    """Allow NULL in a column, or require a value. SQL Server and MySQL restate the column to do so, so they
    need its declared type (sql_type, with its length) and, on MySQL, the rest of it (mysql, see the schema)."""
    q = lambda name: quote_identifier(name, db_type)
    if db_type in ("MYSQL", "MARIADB"):
        definition = mysql_column_definition(sql_type, nullable, mysql or {})
        return f"ALTER TABLE {q(table)} MODIFY COLUMN {q(column_name)} {definition}"
    if db_type == "SQLSERVER":
        return f"ALTER TABLE {q(table)} ALTER COLUMN {q(column_name)} {sql_type} {'NULL' if nullable else 'NOT NULL'}"
    return f"ALTER TABLE {q(table)} ALTER COLUMN {q(column_name)} {'DROP' if nullable else 'SET'} NOT NULL"


def fill_nulls(table, column_name, value_sql, db_type):
    """Give the rows that have no value in a column this one (before the column requires one)"""
    q = lambda name: quote_identifier(name, db_type)
    return f"UPDATE {q(table)} SET {q(column_name)} = {value_sql} WHERE {q(column_name)} IS NULL"


def drop_constraint(table, constraint, db_type):
    """Drop a constraint or index read from the schema ({"kind", "name", ...}), as each database spells it"""
    q = lambda name: quote_identifier(name, db_type)
    kind, name = constraint["kind"], constraint["name"]
    if db_type in ("MYSQL", "MARIADB"):
        if kind == "FOREIGN KEY":
            return f"ALTER TABLE {q(table)} DROP FOREIGN KEY {q(name)}"
        if kind == "PRIMARY KEY":
            return f"ALTER TABLE {q(table)} DROP PRIMARY KEY"
        if kind in ("UNIQUE", "INDEX"):
            return f"ALTER TABLE {q(table)} DROP INDEX {q(name)}"
    if db_type == "SQLSERVER" and kind == "INDEX":
        return f"DROP INDEX {q(name)} ON {q(table)}"
    return f"ALTER TABLE {q(table)} DROP CONSTRAINT {q(name)}"


def rename_column(table, old_name, new_name, db_type):
    q = lambda name: quote_identifier(name, db_type)
    if db_type == "SQLSERVER":
        # sp_rename takes the old name as an object path (bracketed parts) and the new one as is
        target = f"{q(table)}.{q(old_name)}".replace("'", "''")
        return f"EXEC sp_rename N'{target}', N'{new_name.replace(chr(39), chr(39) * 2)}', N'COLUMN'"
    return f"ALTER TABLE {q(table)} RENAME COLUMN {q(old_name)} TO {q(new_name)}"


def drop_column(table, column_name, db_type):
    q = lambda name: quote_identifier(name, db_type)
    return f"ALTER TABLE {q(table)} DROP COLUMN {q(column_name)}"


def add_foreign_key(table, column, ref_table, ref_column, db_type):
    q = lambda name: quote_identifier(name, db_type)
    return (f"ALTER TABLE {q(table)} ADD FOREIGN KEY ({q(column)}) "
            f"REFERENCES {q(ref_table)} ({q(ref_column)})")


def insert(table, assignments, db_type):
    """assignments: [(column, sql_literal)]; an empty list inserts a row of defaults"""
    q = lambda name: quote_identifier(name, db_type)
    if not assignments:
        if db_type in ("MYSQL", "MARIADB"):
            return f"INSERT INTO {q(table)} () VALUES ()"
        return f"INSERT INTO {q(table)} DEFAULT VALUES"
    names = ", ".join(q(name) for name, _ in assignments)
    values = ", ".join(value for _, value in assignments)
    return f"INSERT INTO {q(table)} ({names}) VALUES ({values})"


def update(table, assignments, where, db_type):
    q = lambda name: quote_identifier(name, db_type)
    sets = ", ".join(f"{q(name)} = {value}" for name, value in assignments)
    return f"UPDATE {q(table)} SET {sets} WHERE {_where(where, db_type)}"


def delete(table, where, db_type):
    return f"DELETE FROM {quote_identifier(table, db_type)} WHERE {_where(where, db_type)}"


def _where(conditions, db_type):
    q = lambda name: quote_identifier(name, db_type)
    return " AND ".join(
        f"{q(name)} IS NULL" if value == "NULL" else f"{q(name)} = {value}"
        for name, value in conditions
    )
