"""Running statements on an open connection, with results in the shape the screens use:

    {"statementType", "columns", "rows", "updateCount", "truncated", "durationMs"}

updateCount is None for a statement that returned rows. All statements run in one transaction: if one
fails, the others are rolled back (MySQL commits CREATE/ALTER/DROP by itself, so those stay)."""

import time

from dbmanager.db.drivers import DatabaseError, error_message
from dbmanager.db.script import statement_type
from dbmanager.db.values import bit_to_int, to_value

_MYSQL_BIT = 16  # pymysql.constants.FIELD_TYPE.BIT


def run_statements(db_connection, db_type, statements, max_rows):
    """Runs every statement and commits; returns (results, duration in ms)."""
    started = time.monotonic()
    kinds = [statement_type(statement, db_type) for statement in statements]
    _begin(db_connection, db_type, read_only=all(kind == "SELECT" for kind in kinds))
    results = []
    cursor = db_connection.cursor()
    try:
        for number, (statement, kind) in enumerate(zip(statements, kinds), start=1):
            try:
                results.append(_run_one(cursor, db_type, statement, kind, max_rows))
            except Exception as error:  # noqa: BLE001 - the driver's error, whatever its class
                _rollback(db_connection)
                which = (f"statement {number} of {len(statements)} ({kind}) - nothing was saved"
                         if len(statements) > 1 else "the statement")
                raise DatabaseError(f"The database rejected {which}: {error_message(error)}") from None
        db_connection.commit()
    finally:
        cursor.close()
    return results, round((time.monotonic() - started) * 1000)


def _run_one(cursor, db_type, statement, kind, max_rows):
    started = time.monotonic()
    cursor.execute(statement)  # no parameters: the text goes to the database exactly as written
    result = {"statementType": kind}
    if cursor.description is not None:
        bits = {i for i, column in enumerate(cursor.description)
                if db_type in ("MYSQL", "MARIADB") and column[1] == _MYSQL_BIT}
        fetched = cursor.fetchmany(max_rows + 1)
        rows = [[to_value(bit_to_int(value) if i in bits else value) for i, value in enumerate(row)]
                for row in fetched[:max_rows]]
        result.update(columns=[column[0] for column in cursor.description], rows=rows,
                      updateCount=None, truncated=len(fetched) > max_rows)
        if db_type == "SQLSERVER":
            _drain(cursor)  # pymssql cannot run the next statement while rows are still waiting
    else:
        # CREATE/ALTER report -1 on some drivers: "nothing counted" reads better as 0
        result.update(columns=[], rows=[], updateCount=max(0, cursor.rowcount or 0), truncated=False)
    result["durationMs"] = round((time.monotonic() - started) * 1000)
    return result


def _begin(db_connection, db_type, read_only):
    """SELECT-only work runs read-only where the database offers it, so a function cannot write either."""
    if db_type == "POSTGRESQL":
        db_connection.read_only = read_only
    elif db_type in ("MYSQL", "MARIADB") and read_only:
        cursor = db_connection.cursor()
        try:
            cursor.execute("START TRANSACTION READ ONLY")
        finally:
            cursor.close()


def _drain(cursor):
    while cursor.fetchmany(1000):
        pass
    while cursor.nextset():
        while cursor.fetchmany(1000):
            pass


def _rollback(db_connection):
    try:
        db_connection.rollback()
    except Exception:  # noqa: BLE001 - the connection is closed right after anyway
        pass
