"""Writing table and column names as SQL for each supported database."""

import re

_SIMPLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# Words reserved almost everywhere (and some that are only awkward as bare names)
_COMMON = {
    "all", "alter", "and", "any", "as", "asc", "between", "by", "case", "check", "column", "constraint",
    "create", "cross", "current_date", "current_time", "current_timestamp", "current_user", "database", "date",
    "day", "default", "delete", "desc", "distinct", "drop", "else", "end", "exists", "false", "fetch", "for",
    "foreign", "from", "full", "function", "grant", "group", "having", "hour", "in", "index", "inner", "insert",
    "interval", "into", "is", "join", "key", "left", "level", "like", "limit", "minute", "month", "natural",
    "not", "null", "offset", "on", "or", "order", "outer", "over", "partition", "primary", "range", "rank",
    "references", "right", "row", "rows", "schema", "second", "select", "session_user", "set", "some", "table",
    "then", "time", "timestamp", "to", "trigger", "true", "union", "unique", "update", "user", "using", "value",
    "values", "view", "when", "where", "window", "with", "year",
}
# PostgreSQL's reserved key words, beyond those
_POSTGRES = {
    "analyse", "analyze", "array", "asymmetric", "authorization", "bigint", "binary", "bit", "boolean", "both",
    "cast", "char", "character", "coalesce", "collate", "collation", "concurrently", "current_catalog",
    "current_role", "current_schema", "dec", "decimal", "deferrable", "do", "except", "extract", "float",
    "freeze", "grouping", "ilike", "initially", "inout", "int", "integer", "intersect", "isnull", "lateral",
    "leading", "localtime", "localtimestamp", "national", "nchar", "none", "notnull", "nullif", "numeric",
    "only", "out", "overlaps", "overlay", "placing", "position", "precision", "real", "returning", "setof",
    "similar", "smallint", "substring", "symmetric", "system_user", "tablesample", "trailing", "treat", "trim",
    "varchar", "variadic", "verbose",
}
# MySQL's and MariaDB's (a column called read, change or usage)
_MYSQL = {
    "accessible", "add", "analyze", "asensitive", "before", "bigint", "binary", "blob", "both", "call",
    "cascade", "change", "char", "character", "collate", "condition", "continue", "convert", "cube",
    "cume_dist", "cursor", "databases", "day_hour", "day_microsecond", "day_minute", "day_second", "dec",
    "decimal", "declare", "delayed", "dense_rank", "describe", "deterministic", "distinctrow", "div", "double",
    "dual", "each", "elseif", "empty", "enclosed", "escaped", "except", "exit", "explain", "first_value",
    "float", "float4", "float8", "force", "fulltext", "generated", "get", "grouping", "groups", "high_priority",
    "hour_microsecond", "hour_minute", "hour_second", "if", "ignore", "infile", "inout", "insensitive", "int",
    "int1", "int2", "int3", "int4", "int8", "integer", "intersect", "io_after_gtids", "io_before_gtids",
    "iterate", "json_table", "keys", "kill", "lag", "last_value", "lateral", "lead", "leading", "leave",
    "linear", "lines", "load", "localtime", "localtimestamp", "lock", "long", "longblob", "longtext", "loop",
    "low_priority", "master_bind", "master_ssl_verify_server_cert", "match", "maxvalue", "mediumblob",
    "mediumint", "mediumtext", "middleint", "minute_microsecond", "minute_second", "mod", "modifies",
    "no_write_to_binlog", "nth_value", "ntile", "numeric", "of", "optimize", "optimizer_costs", "option",
    "optionally", "out", "outfile", "percent_rank", "precision", "procedure", "purge", "read", "read_write",
    "reads", "real", "recursive", "regexp", "release", "rename", "repeat", "replace", "require", "resignal",
    "restrict", "return", "revoke", "rlike", "row_number", "schemas", "second_microsecond", "sensitive",
    "separator", "show", "signal", "smallint", "spatial", "specific", "sql", "sql_big_result",
    "sql_calc_found_rows", "sql_small_result", "sqlexception", "sqlstate", "sqlwarning", "ssl", "starting",
    "stored", "straight_join", "system", "terminated", "tinyblob", "tinyint", "tinytext", "trailing", "undo",
    "unlock", "unsigned", "usage", "use", "utc_date", "utc_time", "utc_timestamp", "varbinary", "varchar",
    "varcharacter", "varying", "virtual", "while", "write", "xor", "year_month", "zerofill",
}
# SQL Server's (a table called plan, file or open)
_SQLSERVER = {
    "add", "authorization", "backup", "begin", "break", "browse", "bulk", "cascade", "checkpoint", "close",
    "clustered", "coalesce", "collate", "commit", "compute", "contains", "containstable", "continue", "convert",
    "current", "cursor", "dbcc", "deallocate", "declare", "deny", "disk", "distributed", "double", "dump",
    "errlvl", "escape", "except", "exec", "execute", "exit", "external", "file", "fillfactor", "freetext",
    "freetexttable", "goto", "holdlock", "identity", "identity_insert", "identitycol", "if", "intersect",
    "kill", "lineno", "load", "merge", "national", "nocheck", "nonclustered", "nullif", "of", "off", "offsets",
    "open", "opendatasource", "openquery", "openrowset", "openxml", "option", "percent", "pivot", "plan",
    "precision", "print", "proc", "procedure", "public", "raiserror", "read", "readtext", "reconfigure",
    "replication", "restore", "restrict", "return", "revert", "revoke", "rollback", "rowcount", "rowguidcol",
    "rule", "save", "securityaudit", "semantickeyphrasetable", "semanticsimilaritydetailstable",
    "semanticsimilaritytable", "setuser", "shutdown", "statistics", "system_user", "tablesample", "textsize",
    "top", "tran", "transaction", "truncate", "try_convert", "tsequal", "unpivot", "updatetext", "use",
    "varying", "waitfor", "while", "writetext",
}
_RESERVED = {
    "POSTGRESQL": _COMMON | _POSTGRES,
    "MYSQL": _COMMON | _MYSQL,
    "MARIADB": _COMMON | _MYSQL,
    "SQLSERVER": _COMMON | _SQLSERVER,
}
_ANY = _COMMON | _POSTGRES | _MYSQL | _SQLSERVER  # a database of another type, or none yet


def quote_identifier(name, db_type):
    """A table/column name as SQL: left bare when the database reads it back unchanged,
    quoted (keeping its exact case) otherwise."""
    if _SIMPLE_NAME.fullmatch(name) and name.lower() not in _RESERVED.get(db_type, _ANY):
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
