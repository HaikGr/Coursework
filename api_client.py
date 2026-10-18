"""
API Client - talks to the Database Management backend (Spring Boot REST API).

Uses only the standard library, so the app needs nothing beyond PyQt6.
The server address comes from the DB_MANAGER_API_URL environment variable
(default http://localhost:8080).
"""

import json
import os
import re
import urllib.error
import urllib.request
from contextlib import contextmanager
from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

API_URL = os.environ.get("DB_MANAGER_API_URL", "http://localhost:8080").rstrip("/")

# Mirrors the backend's DbType enum: (value sent to the API, label shown in the UI, default port)
DB_TYPES = [
    ("POSTGRESQL", "PostgreSQL", 5432),
    ("MYSQL", "MySQL", 3306),
    ("SQLSERVER", "SQL Server", 1433),
    ("MARIADB", "MariaDB", 3306),
    ("H2", "H2 (server mode)", 9092),
    ("ORACLE", "Oracle", 1521),
]
DEFAULT_PORTS = {value: port for value, _, port in DB_TYPES}


class ApiError(Exception):
    """A failed API call. str(error) is a message ready to show to the user."""

    def __init__(self, status, message, field_errors=None):
        self.status = status
        self.field_errors = field_errors or {}
        if self.field_errors:
            details = "\n".join(f"• {field}: {error}" for field, error in self.field_errors.items())
            message = f"{message}\n{details}"
        super().__init__(message)


@contextmanager
def busy_cursor():
    """Show a wait cursor while a (blocking) API call runs."""
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    QApplication.processEvents()
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


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


def describe_connection(connection):
    """One-line summary of a connection returned by the API."""
    return (f"{connection['dbType']}  {connection['dbUsername']}@"
            f"{connection['host']}:{connection['port']}/{connection['dbName']}")


class ApiClient:
    """Holds the session (JWT) of the signed-in user and wraps every backend call."""

    def __init__(self, base_url=API_URL, timeout=60):
        self.base_url = base_url
        self.timeout = timeout
        self.token = None
        self.user_id = None
        self.username = None
        self.roles = []

    # ---------------- Auth ----------------
    def login(self, username_or_email, password):
        data = self._request("POST", "/api/auth/login",
                             {"username": username_or_email, "password": password})
        self._store_session(data)
        return data

    def register(self, username, email, password):
        data = self._request("POST", "/api/auth/register",
                             {"username": username, "email": email, "password": password})
        self._store_session(data)
        return data

    def logout(self):
        """Revoke the token on the server; the local session is dropped either way."""
        if not self.token:
            return
        try:
            self._request("POST", "/api/auth/logout")
        finally:
            self.token = None
            self.user_id = None
            self.username = None
            self.roles = []

    # ---------------- Databases ----------------
    def list_connections(self):
        return self._request("GET", "/api/db-connections") or []

    def create_connection(self, details):
        return self._request("POST", "/api/db-connections", details)

    def update_connection(self, connection_id, details):
        return self._request("PUT", f"/api/db-connections/{connection_id}", details)

    def delete_connection(self, connection_id):
        self._request("DELETE", f"/api/db-connections/{connection_id}")

    def get_schema(self, connection_id):
        return self._request("GET", f"/api/db-connections/{connection_id}/schema") or []

    def run_query(self, connection_id, sql, max_rows=None):
        body = {"sql": sql}
        if max_rows:
            body["maxRows"] = max_rows
        return self._request("POST", f"/api/db-connections/{connection_id}/query", body)

    def run_script(self, connection_id, sql):
        """Run ';'-separated statements in one transaction; returns {"results": [...], "durationMs": n}"""
        return self._request("POST", f"/api/db-connections/{connection_id}/script", {"sql": sql})

    # ---------------- Plumbing ----------------
    def _store_session(self, data):
        self.token = data["token"]
        self.user_id = data.get("userId")
        self.username = data.get("username")
        self.roles = data.get("roles") or []

    def _request(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                # Decimal keeps money/numeric columns exact instead of turning them into floats
                return json.loads(raw, parse_float=Decimal) if raw else None
        except urllib.error.HTTPError as error:
            raise self._to_api_error(error) from None
        except urllib.error.URLError as error:
            raise ApiError(0, f"Cannot reach the server at {self.base_url}.\n"
                              f"Is the backend running? ({error.reason})") from None
        except TimeoutError:
            raise ApiError(0, "The server took too long to answer.") from None

    @staticmethod
    def _to_api_error(error):
        try:
            payload = json.loads(error.read() or b"{}")
        except ValueError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        message = payload.get("message") or error.reason or f"HTTP {error.code}"
        if error.code == 401 and "/api/auth/login" not in error.url:
            message = "Your session has expired. Please sign in again."
        return ApiError(error.code, message, payload.get("fieldErrors"))
