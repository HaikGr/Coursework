"""Writing table and column names as SQL for each supported database."""

import re

_SIMPLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_RESERVED = {
    "all", "alter", "and", "any", "as", "asc", "between", "by", "case", "check", "column", "constraint",
    "create", "cross", "current_date", "current_time", "current_timestamp", "current_user", "database",
    "date", "day", "default", "delete", "desc", "distinct", "drop", "else", "end", "exists", "false",
    "fetch", "for", "foreign", "from", "full", "function", "grant", "group", "having", "hour", "in",
    "index", "inner", "insert", "interval", "into", "is", "join", "key", "left", "level", "like", "limit",
    "minute", "month", "natural", "not", "null", "offset", "on", "or", "order", "outer", "over",
    "partition", "primary", "range", "rank", "references", "right", "row", "rows", "schema", "second",
    "select", "session_user", "set", "some", "table", "then", "time", "timestamp", "to", "trigger",
    "true", "union", "unique", "update", "user", "using", "value", "values", "view", "when", "where",
    "window", "with", "year",
}


def quote_identifier(name, db_type):
    """A table/column name as SQL: left bare when the database reads it back unchanged,
    quoted (keeping its exact case) otherwise."""
    if _SIMPLE_NAME.fullmatch(name) and name.lower() not in _RESERVED:
        if db_type == "POSTGRESQL" and name == name.lower():
            return name  # PostgreSQL folds bare names to lower case
        if db_type in ("H2", "ORACLE") and name == name.upper():
            return name  # these fold bare names to upper case
        if db_type in ("MYSQL", "MARIADB", "SQLSERVER"):
            return name  # quoting does not change case handling here
    if db_type in ("MYSQL", "MARIADB"):
        return "`" + name.replace("`", "``") + "`"
    if db_type == "SQLSERVER":
        return "[" + name.replace("]", "]]") + "]"
    return '"' + name.replace('"', '""') + '"'
