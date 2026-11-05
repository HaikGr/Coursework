"""Database types the app can open - mirrors the backend's DbType enum, less the ones it cannot open."""

# (value sent to the API, label shown in the UI, default port). ORACLE and H2 exist on the server too,
# but there is no driver here for them, so they are not offered.
DB_TYPES = [
    ("POSTGRESQL", "PostgreSQL", 5432),
    ("MYSQL", "MySQL", 3306),
    ("SQLSERVER", "SQL Server", 1433),
    ("MARIADB", "MariaDB", 3306),
]
DEFAULT_PORTS = {value: port for value, _, port in DB_TYPES}

# Host names that mean "this very computer": nobody else reaches a database through them
_THIS_COMPUTER = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ".", "(local)"}


def parse_port(text):
    """The port typed by the user as an int, or None when it is not a number from 1 to 65535."""
    text = (text or "").strip()
    # isascii(): str.isdigit() also accepts characters such as '²' that int() rejects
    if not (text.isascii() and text.isdigit()):
        return None
    port = int(text)
    return port if 1 <= port <= 65535 else None


def only_this_computer(host):
    """True for localhost and its kin (also as localhost\\SQLEXPRESS): a share needs an address others can use."""
    name = (host or "").strip().lower().split("\\", 1)[0]
    return name in _THIS_COMPUTER or name.startswith("127.")


def describe_connection(connection):
    """One-line summary of a connection returned by the API."""
    return (f"{connection['dbType']}  {connection['dbUsername']}@"
            f"{connection['host']}:{connection['port']}/{connection['dbName']}")
