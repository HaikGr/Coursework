"""Database types the backend can connect to - mirrors its DbType enum."""

# (value sent to the API, label shown in the UI, default port)
DB_TYPES = [
    ("POSTGRESQL", "PostgreSQL", 5432),
    ("MYSQL", "MySQL", 3306),
    ("SQLSERVER", "SQL Server", 1433),
    ("MARIADB", "MariaDB", 3306),
    ("H2", "H2 (server mode)", 9092),
    ("ORACLE", "Oracle", 1521),
]
DEFAULT_PORTS = {value: port for value, _, port in DB_TYPES}


def parse_port(text):
    """The port typed by the user as an int, or None when it is not a number from 1 to 65535."""
    text = (text or "").strip()
    # isascii(): str.isdigit() also accepts characters such as '²' that int() rejects
    if not (text.isascii() and text.isdigit()):
        return None
    port = int(text)
    return port if 1 <= port <= 65535 else None


def describe_connection(connection):
    """One-line summary of a connection returned by the API."""
    return (f"{connection['dbType']}  {connection['dbUsername']}@"
            f"{connection['host']}:{connection['port']}/{connection['dbName']}")
