"""Reading the tables of a database: names, columns, keys and the other constraints.

The result has the shape the sidebar builds its pages from:
    [{"name", "type": "TABLE"/"VIEW",
      "columns": [{"name", "type", "nullable", "primaryKey", "referencedTable", "referencedColumn",
                   "sqlType", ("mysql": {...})}],
      "constraints": [{"kind", "name", "columns", "refTable", "refColumns"}]}]
Only the current schema is read (public, the MySQL database, dbo), and only what the signed-in login may
use: a guest sees the tables their permissions cover, not the rest.

Type names follow what the database calls them (int4, varchar(255), int identity, ...): the editor keeps
them as they are and only looks at their base name. sqlType is the type as it is declared again - with its
length - which SQL Server's ALTER COLUMN and MySQL's MODIFY need to change a column's NULL without changing
anything else about it; "mysql" holds the rest a MODIFY has to repeat (default, AUTO_INCREMENT, ...).

The constraints are what dropping a column or a table has to deal with first: the foreign keys that point
at it, and on SQL Server (and for foreign keys on MySQL) the constraints and indexes of the column itself.
kind is PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK, DEFAULT or INDEX."""

import re

_KINDS = {"p": "PRIMARY KEY", "f": "FOREIGN KEY", "u": "UNIQUE", "c": "CHECK", "d": "DEFAULT", "i": "INDEX"}


def read_schema(db_connection, db_type):
    cursor = db_connection.cursor()
    try:
        if db_type == "POSTGRESQL":
            tables, columns, keys = _postgres(cursor)
        elif db_type in ("MYSQL", "MARIADB"):
            tables, columns, keys = _mysql(cursor)
        else:
            tables, columns, keys = _sqlserver(cursor)
    finally:
        cursor.close()
    return _assemble(tables, columns, keys)


def _assemble(tables, columns, keys):
    """tables: [(name, TABLE/VIEW)]; columns: [(table, column, type, nullable, details)] in order;
    keys: [(kind p/f/u/c/d/i, constraint name, table, column, referenced table, referenced column)],
    one row per column of a constraint, in the constraint's column order"""
    primary = {(table, column) for kind, _, table, column, _, _ in keys if kind == "p"}
    foreign = {}
    constraints = {}
    for kind, name, table, column, ref_table, ref_column in keys:
        if kind == "f":
            foreign.setdefault((table, column), (ref_table, ref_column))  # the first key on a column wins
        entry = constraints.setdefault((table, kind, name), {
            "kind": _KINDS[kind], "name": name, "columns": [], "refTable": ref_table, "refColumns": []})
        entry["columns"].append(column)
        if ref_column is not None:
            entry["refColumns"].append(ref_column)

    by_table = {name: {"name": name, "type": kind, "columns": [], "constraints": []} for name, kind in tables}
    for table, column, type_name, nullable, details in columns:
        if table not in by_table:
            continue
        reference = foreign.get((table, column))
        by_table[table]["columns"].append({
            "name": column,
            "type": type_name,
            "nullable": bool(nullable),
            "primaryKey": (table, column) in primary,
            "referencedTable": reference[0] if reference else None,
            "referencedColumn": reference[1] if reference else None,
            **details,
        })
    for (table, _, _), entry in constraints.items():
        if table in by_table:
            by_table[table]["constraints"].append(entry)
    return list(by_table.values())


def _postgres(cursor):
    # pg_catalog rather than information_schema: the latter hides the keys of tables a login may only read
    cursor.execute("""
        SELECT c.relname, CASE WHEN c.relkind IN ('v', 'm') THEN 'VIEW' ELSE 'TABLE' END
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema() AND c.relkind IN ('r', 'p', 'v', 'm')
          AND has_table_privilege(c.oid, 'SELECT, INSERT, UPDATE, DELETE')
        ORDER BY c.relname""")
    tables = cursor.fetchall()
    cursor.execute("""
        SELECT c.relname, a.attname, t.typname, NOT a.attnotnull, pg_catalog.pg_get_expr(d.adbin, d.adrelid),
               pg_catalog.format_type(a.atttypid, a.atttypmod)
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
        LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE n.nspname = current_schema() AND c.relkind IN ('r', 'p', 'v', 'm')
          AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY c.relname, a.attnum""")
    columns = [(table, column, _postgres_type(type_name, default), nullable, {"sqlType": declared})
               for table, column, type_name, nullable, default, declared in cursor.fetchall()]
    cursor.execute("""
        SELECT con.contype, con.conname, c.relname, a.attname, fc.relname, fa.attname
        FROM pg_catalog.pg_constraint con
        JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN LATERAL unnest(con.conkey, con.confkey) WITH ORDINALITY AS k(attnum, refnum, position)
        JOIN pg_catalog.pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
        LEFT JOIN pg_catalog.pg_class fc ON fc.oid = con.confrelid
        LEFT JOIN pg_catalog.pg_attribute fa ON fa.attrelid = con.confrelid AND fa.attnum = k.refnum
        WHERE n.nspname = current_schema() AND con.contype IN ('p', 'f', 'u')
        ORDER BY con.conname, k.position""")
    return tables, columns, cursor.fetchall()


def _postgres_type(type_name, default):
    """A column filled from a sequence reads as serial, the way it was most likely declared."""
    serials = {"int4": "serial", "int8": "bigserial", "int2": "smallserial"}
    if type_name in serials and (default or "").startswith("nextval("):
        return serials[type_name]
    return type_name


def _mysql(cursor):
    cursor.execute("SELECT VERSION()")
    mariadb = "mariadb" in str(cursor.fetchone()[0]).lower()
    cursor.execute("""
        SELECT TABLE_NAME, CASE WHEN TABLE_TYPE LIKE '%VIEW' THEN 'VIEW' ELSE 'TABLE' END
        FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME""")
    tables = cursor.fetchall()
    cursor.execute("""
        SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE = 'YES', COLUMN_DEFAULT, EXTRA,
               CHARACTER_SET_NAME, COLLATION_NAME, COLUMN_COMMENT
        FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, ORDINAL_POSITION""")
    columns = []
    for table, column, column_type, nullable, default, extra, charset, collation, comment in cursor.fetchall():
        columns.append((table, column, column_type, nullable, {
            "sqlType": column_type,
            "mysql": _mysql_details(default, extra or "", charset, collation, comment, mariadb),
        }))
    cursor.execute("""
        SELECT CASE tc.CONSTRAINT_TYPE WHEN 'PRIMARY KEY' THEN 'p' WHEN 'UNIQUE' THEN 'u' ELSE 'f' END,
               k.CONSTRAINT_NAME, k.TABLE_NAME, k.COLUMN_NAME, k.REFERENCED_TABLE_NAME, k.REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE k
        JOIN information_schema.TABLE_CONSTRAINTS tc
          ON tc.CONSTRAINT_SCHEMA = k.CONSTRAINT_SCHEMA AND tc.TABLE_NAME = k.TABLE_NAME
         AND tc.CONSTRAINT_NAME = k.CONSTRAINT_NAME
        WHERE k.TABLE_SCHEMA = DATABASE() AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY')
        ORDER BY k.CONSTRAINT_NAME, k.ORDINAL_POSITION""")
    return tables, columns, cursor.fetchall()


def _mysql_details(default, extra, charset, collation, comment, mariadb):
    """What a MODIFY COLUMN must say again, or it would drop it: default, AUTO_INCREMENT, ON UPDATE, ..."""
    attributes = []
    if "auto_increment" in extra.lower():
        attributes.append("AUTO_INCREMENT")
    on_update = re.search(r"on update (\S+)", extra, re.IGNORECASE)
    if on_update:
        attributes.append(f"ON UPDATE {on_update.group(1)}")
    if "invisible" in extra.lower():
        attributes.append("INVISIBLE")
    return {
        "default": _mysql_default(default, extra, mariadb),
        "attributes": attributes,
        "charset": charset,
        "collation": collation,
        "comment": comment or "",
        "generated": "generated" in extra.lower() and "default_generated" not in extra.lower(),
    }


def _mysql_default(value, extra, mariadb):
    """The column's default as SQL, or None. MariaDB reports it as SQL already ('text', 42, NULL,
    current_timestamp()); MySQL reports the bare value, and marks an expression DEFAULT_GENERATED."""
    if value is None:
        return None
    if mariadb:
        return None if value.upper() == "NULL" else value
    if "default_generated" in extra.lower():
        return value if value.upper().startswith("CURRENT_TIMESTAMP") else f"({value})"
    if re.fullmatch(r"b'[01]*'", value):
        return value  # a BIT default
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _sqlserver(cursor):
    cursor.execute("""
        SELECT o.name, CASE o.type WHEN 'V' THEN 'VIEW' ELSE 'TABLE' END
        FROM sys.objects o WHERE o.schema_id = SCHEMA_ID() AND o.type IN ('U', 'V') ORDER BY o.name""")
    tables = cursor.fetchall()
    cursor.execute("""
        SELECT o.name, c.name, ty.name + CASE WHEN c.is_identity = 1 THEN ' identity' ELSE '' END, c.is_nullable,
               ty.name, c.max_length, c.precision, c.scale, c.is_computed
        FROM sys.columns c
        JOIN sys.objects o ON o.object_id = c.object_id
        JOIN sys.types ty ON ty.user_type_id = c.user_type_id
        WHERE o.schema_id = SCHEMA_ID() AND o.type IN ('U', 'V')
        ORDER BY o.name, c.column_id""")
    columns = [(table, column, shown, nullable,
                {"sqlType": _sqlserver_type(type_name, length, precision, scale), "computed": bool(computed)})
               for table, column, shown, nullable, type_name, length, precision, scale, computed in cursor.fetchall()]
    cursor.execute("""
        SELECT CASE kc.type WHEN 'PK' THEN 'p' ELSE 'u' END, kc.name, o.name, c.name, NULL, NULL
        FROM sys.key_constraints kc
        JOIN sys.objects o ON o.object_id = kc.parent_object_id
        JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE o.schema_id = SCHEMA_ID()
        UNION ALL
        SELECT 'f', fk.name, po.name, pc.name, ro.name, rc.name
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns f ON f.constraint_object_id = fk.object_id
        JOIN sys.objects po ON po.object_id = f.parent_object_id
        JOIN sys.columns pc ON pc.object_id = f.parent_object_id AND pc.column_id = f.parent_column_id
        JOIN sys.objects ro ON ro.object_id = f.referenced_object_id
        JOIN sys.columns rc ON rc.object_id = f.referenced_object_id AND rc.column_id = f.referenced_column_id
        WHERE po.schema_id = SCHEMA_ID()
        UNION ALL
        SELECT 'd', dc.name, o.name, c.name, NULL, NULL
        FROM sys.default_constraints dc
        JOIN sys.objects o ON o.object_id = dc.parent_object_id
        JOIN sys.columns c ON c.object_id = dc.parent_object_id AND c.column_id = dc.parent_column_id
        WHERE o.schema_id = SCHEMA_ID()
        UNION ALL
        SELECT 'c', cc.name, o.name, c.name, NULL, NULL
        FROM sys.check_constraints cc
        JOIN sys.objects o ON o.object_id = cc.parent_object_id
        JOIN sys.columns c ON c.object_id = cc.parent_object_id AND c.column_id = cc.parent_column_id
        WHERE o.schema_id = SCHEMA_ID() AND cc.parent_column_id > 0
        UNION ALL
        SELECT 'i', i.name, o.name, c.name, NULL, NULL
        FROM sys.indexes i
        JOIN sys.objects o ON o.object_id = i.object_id
        JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE o.schema_id = SCHEMA_ID() AND o.type = 'U' AND i.type > 0
          AND i.is_primary_key = 0 AND i.is_unique_constraint = 0""")
    return tables, columns, cursor.fetchall()


def _sqlserver_type(type_name, max_length, precision, scale):
    """The type as declared, with its length: ALTER COLUMN without it would make nvarchar(80) an nvarchar(1)."""
    lowered = type_name.lower()
    if lowered in ("varchar", "char", "varbinary", "binary"):
        return f"{type_name}({'max' if max_length == -1 else max_length})"
    if lowered in ("nvarchar", "nchar"):
        return f"{type_name}({'max' if max_length == -1 else max_length // 2})"
    if lowered in ("decimal", "numeric"):
        return f"{type_name}({precision}, {scale})"
    if lowered in ("datetime2", "time", "datetimeoffset"):
        return f"{type_name}({scale})"
    return type_name
