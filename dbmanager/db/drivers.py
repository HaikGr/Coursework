"""Opening a connection to one of the user's databases from this computer, for each supported type.

A driver is imported only when a database of its type is opened, so a missing one costs only that type.
Every failure becomes a DatabaseError whose text is ready to show."""

import importlib
import re
import time

from dbmanager.config import DB_CONNECT_TIMEOUT_SECONDS, DB_STATEMENT_TIMEOUT_SECONDS
from dbmanager.i18n import tr

# The types this app can open: (module, what to pip install)
_DRIVERS = {
    "POSTGRESQL": ("psycopg", "psycopg[binary]"),
    "MYSQL": ("pymysql", "PyMySQL[rsa]"),
    "MARIADB": ("pymysql", "PyMySQL[rsa]"),
    "SQLSERVER": ("pymssql", "pymssql"),
}
SUPPORTED_TYPES = tuple(_DRIVERS)

# What the servers answer when they do not accept the user name and password
_REFUSED_LOGIN = re.compile(
    r"password authentication failed|authentication failed for user|access denied for user|login failed for user",
    re.IGNORECASE)
_SQLSERVER_ANSWERED = re.compile(r"check messages from the sql server", re.IGNORECASE)
_SQLSERVER_SILENT = re.compile(r"unable to connect|connection refused|unavailable or does not exist", re.IGNORECASE)


class DatabaseError(Exception):
    """A user's database could not be opened, or refused a statement. str(error) is ready to show.

    unreachable:   nothing could be opened at all (wrong address, name or sign-in, or the server is down)
    refused_login: of those, the server answered but did not accept the user name and password
    cancelled:     the user was asked for a password and gave none
    record:        the text in English, for the audit log (the message itself when not given)
    """

    def __init__(self, message, unreachable=False, refused_login=False, cancelled=False, record=None):
        super().__init__(message)
        self.unreachable = unreachable
        self.refused_login = refused_login
        self.cancelled = cancelled
        self.record = record if record is not None else message


def driver_module(db_type):
    if db_type not in _DRIVERS:
        raise DatabaseError(tr("db.drivers.not_supported", db_type=db_type, types=", ".join(SUPPORTED_TYPES)))
    module, package = _DRIVERS[db_type]
    try:
        return importlib.import_module(module)
    except ImportError:
        raise DatabaseError(tr("db.drivers.not_installed", db_type=db_type, package=package)) from None


def describe_target(connection):
    return f"{connection['dbType']} {connection['host']}:{connection['port']}/{connection['dbName']}"


def connect(connection, user, password):
    """An open DB-API connection (not in autocommit) to the database a connection dict describes."""
    db_type = connection["dbType"]
    module = driver_module(db_type)
    try:
        if db_type == "POSTGRESQL":
            return _connect_postgres(module, connection, user, password)
        if db_type in ("MYSQL", "MARIADB"):
            return _connect_mysql(module, connection, user, password)
        return _connect_sqlserver(module, connection, user, password)
    except module.Error as error:
        message = error_message(error)
        refused = bool(_REFUSED_LOGIN.search(message))
        if db_type == "SQLSERVER" and _SQLSERVER_ANSWERED.search(message) and not _SQLSERVER_SILENT.search(message):
            # FreeTDS often reports only that the server "sent messages": it answered, and refused the login
            refused = True
            if "login failed" not in message.lower():
                message = tr("db.drivers.login_refused")
        raise DatabaseError(tr("db.drivers.connect_failed", target=describe_target(connection), reason=message),
                            unreachable=True, refused_login=refused) from None
    except OSError as error:  # a name that does not resolve can surface as a plain socket error
        raise DatabaseError(tr("db.drivers.connect_failed", target=describe_target(connection), reason=error),
                            unreachable=True) from None


def server_version(db_connection, db_type):
    """'PostgreSQL 16.8', 'MariaDB 11.4.4', ... as the open connection reports it."""
    cursor = db_connection.cursor()
    try:
        if db_type == "POSTGRESQL":
            cursor.execute("SHOW server_version")
            return "PostgreSQL " + cursor.fetchone()[0].split()[0]
        if db_type in ("MYSQL", "MARIADB"):
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            return ("MariaDB " if "mariadb" in version.lower() else "MySQL ") + version.split("-")[0]
        cursor.execute("SELECT CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(128))")
        return "SQL Server " + cursor.fetchone()[0]
    finally:
        cursor.close()


def test(connection, user, password):
    """Connect, say what answered and how fast, and close again."""
    started = time.monotonic()
    db_connection = connect(connection, user, password)
    try:
        version = server_version(db_connection, connection["dbType"])
    except Exception as error:  # noqa: BLE001 - whatever the driver raises, the database did answer
        version = tr("db.drivers.version_unknown", db_type=connection["dbType"], reason=error_message(error))
    finally:
        db_connection.close()
    return tr("db.drivers.connected", server=version, ms=round((time.monotonic() - started) * 1000))


def error_message(error):
    """The server's own words from a driver exception, without the driver's wrapping."""
    args = getattr(error, "args", ())
    # PyMySQL: (code, message); pymssql: ((code, b"message"), ...) or (code, b"message")
    if args and isinstance(args[0], tuple):
        args = args[0]
    if len(args) >= 2 and isinstance(args[0], int):
        text = args[1].decode("utf-8", "replace") if isinstance(args[1], bytes) else str(args[1])
    else:
        text = str(error)
    # FreeTDS (pymssql) puts "DB-Lib error message 20009, severity 9:" before each line, and repeats lines
    text = re.sub(r"DB-Lib error message \d+, severity \d+:", "\n", text)
    lines = []
    for line in (line.strip() for line in text.splitlines()):
        if line and line not in lines:
            lines.append(line)
    return " ".join(lines) or error.__class__.__name__


def _connect_postgres(psycopg, connection, user, password):
    from dbmanager.db.values import postgres_text_context
    return psycopg.connect(
        host=connection["host"], port=connection["port"], dbname=connection["dbName"],
        user=user, password=password,
        connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
        options=f"-c statement_timeout={DB_STATEMENT_TIMEOUT_SECONDS * 1000}",
        application_name="Database Management",
        context=postgres_text_context(),
    )


def _connect_mysql(pymysql, connection, user, password):
    from dbmanager.db.values import mysql_conversions
    return pymysql.connect(
        host=connection["host"], port=connection["port"], database=connection["dbName"],
        user=user, password=password,
        connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
        # MySQL cannot cap every statement's run time from the client; a socket that stays silent this
        # long ends the wait instead
        read_timeout=DB_STATEMENT_TIMEOUT_SECONDS, write_timeout=DB_STATEMENT_TIMEOUT_SECONDS,
        charset="utf8mb4", autocommit=False, local_infile=False,
        conv=mysql_conversions(),
    )


def _connect_sqlserver(pymssql, connection, user, password):
    host = connection["host"]
    options = {}
    if "\\" not in host:  # a named instance (host\SQLEXPRESS) finds its own port
        options["port"] = str(connection["port"])
    return pymssql.connect(
        server=host, database=connection["dbName"], user=user, password=password,
        login_timeout=DB_CONNECT_TIMEOUT_SECONDS, timeout=DB_STATEMENT_TIMEOUT_SECONDS,
        autocommit=False, appname="Database Management", **options,
    )
