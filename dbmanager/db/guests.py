"""Database logins for the people a database is shared with.

Sharing gives every guest a login of their own in the owner's database, holding exactly the permissions
their invitations name: SELECT_ROLE becomes GRANT SELECT, and so on. The database itself then refuses
anything else, whatever tool the guest connects with - the owner's password is never handed out.

The owner's app keeps these logins in line with the invitations (sync): it creates the missing ones with a
fresh random password, which it leaves on the server for the guest's app to collect once an invitation is
accepted, re-grants what each guest holds, and drops the logins nobody is invited with any more.

Logins are named dbm_u<guest user id>_c<connection id>, so one name cannot belong to two shares and the
app never touches a login it did not make.
"""

import re
import secrets
import string

from dbmanager.sql.identifiers import quote_identifier

PRIVILEGES = {"SELECT_ROLE": "SELECT", "INSERT_ROLE": "INSERT", "UPDATE_ROLE": "UPDATE", "DELETE_ROLE": "DELETE"}
_ORDER = list(PRIVILEGES.values())
# Invitations that keep a login: answered yes, or not answered yet (the password is only handed out
# once accepted, so a pending guest holds a login they cannot use yet - and can as soon as they say yes)
ACTIVE = ("PENDING", "ACCEPTED")
_LOGIN = re.compile(r"dbm_u(\d+)_c(\d+)")


def login_name(user_id, connection_id):
    return f"dbm_u{user_id}_c{connection_id}"


def parse_login(name):
    """(user id, connection id) of a login this app made, or None."""
    match = _LOGIN.fullmatch(name or "")
    return (int(match.group(1)), int(match.group(2))) if match else None


def new_password():
    """24 random characters, with every class that password policies ask for (SQL Server, MySQL plugins)."""
    alphabet = string.ascii_letters + string.digits
    while True:
        body = "".join(secrets.choice(alphabet) for _ in range(22))
        if any(c.islower() for c in body) and any(c.isupper() for c in body) and any(c.isdigit() for c in body):
            return body[:11] + secrets.choice("-_.") + body[11:] + secrets.choice("-_.")


def desired_privileges(invitations, owner_id, connection_id):
    """{guest user id: [SELECT, INSERT, ...]} that the owner's active invitations on this database grant."""
    wanted = {}
    for invitation in invitations:
        if (invitation.get("fromUserId") == owner_id and invitation.get("dbConnectionId") == connection_id
                and invitation.get("status") in ACTIVE and invitation.get("permission") in PRIVILEGES):
            wanted.setdefault(invitation["toUserId"], set()).add(PRIVILEGES[invitation["permission"]])
    return {user_id: sorted(privileges, key=_ORDER.index) for user_id, privileges in wanted.items()}


def plan(connection_id, desired, existing_logins, saved_accounts):
    """What it takes to bring a database's guest logins in line with the invitations.

    desired:         {guest user id: [privileges]}
    existing_logins: login names this app made that the database holds (any connection id)
    saved_accounts:  {guest user id: login name} the server keeps a password for
    Returns {"create": [user ids], "new_password": [user ids], "grant": {user id: [privileges]},
             "drop": [login names], "forget": [user ids]}
    """
    ours = {name for name in existing_logins if (parse_login(name) or (None, None))[1] == connection_id}
    actions = {"create": [], "new_password": [], "grant": {}, "drop": [], "forget": []}
    for user_id in sorted(desired):
        name = login_name(user_id, connection_id)
        if name not in ours:
            actions["create"].append(user_id)
        elif saved_accounts.get(user_id) != name:
            actions["new_password"].append(user_id)  # it exists, but nobody can tell the guest its password
        actions["grant"][user_id] = desired[user_id]
    wanted_names = {login_name(user_id, connection_id) for user_id in desired}
    actions["drop"] = sorted(ours - wanted_names)
    actions["forget"] = sorted(user_id for user_id in saved_accounts if user_id not in desired)
    return actions


def dialect(db_type):
    if db_type == "POSTGRESQL":
        return Postgres()
    if db_type in ("MYSQL", "MARIADB"):
        return MySql()
    if db_type == "SQLSERVER":
        return SqlServer()
    raise ValueError(f"Sharing is not supported for {db_type} databases")


def _literal(text):
    return "'" + text.replace("'", "''") + "'"


class Postgres:
    """Roles are server-wide in PostgreSQL; what one may do is granted per database and schema."""
    transactional = True

    def scope(self, cursor):
        cursor.execute("SELECT current_database(), current_schema()")
        return cursor.fetchone()

    def logins(self, cursor):
        cursor.execute("SELECT rolname FROM pg_catalog.pg_roles WHERE rolname LIKE 'dbm%'")
        return {row[0] for row in cursor.fetchall() if parse_login(row[0])}

    def create(self, name, password, scope):
        return [f"CREATE ROLE {name} LOGIN PASSWORD {_literal(password)}"]

    def set_password(self, name, password):
        return [f"ALTER ROLE {name} PASSWORD {_literal(password)}"]

    def grant(self, name, privileges, scope):
        database, schema = (quote_identifier(part, "POSTGRESQL") for part in scope)
        statements = self._revoke(name, schema) + [
            f"GRANT CONNECT ON DATABASE {database} TO {name}",
            f"GRANT USAGE ON SCHEMA {schema} TO {name}",
            f"GRANT {', '.join(privileges)} ON ALL TABLES IN SCHEMA {schema} TO {name}",
            # tables the owner creates later are covered too
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT {', '.join(privileges)} ON TABLES TO {name}",
        ]
        if "INSERT" in privileges:  # serial columns draw their numbers from sequences
            statements += [f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA {schema} TO {name}",
                           f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT USAGE ON SEQUENCES TO {name}"]
        return statements

    def drop(self, name, scope):
        database, schema = (quote_identifier(part, "POSTGRESQL") for part in scope)
        # Everything granted has to go before the role can: DROP OWNED would need the role's own rights
        return self._revoke(name, schema) + [
            f"REVOKE USAGE ON SCHEMA {schema} FROM {name}",
            f"REVOKE CONNECT ON DATABASE {database} FROM {name}",
            f"DROP ROLE {name}",
        ]

    @staticmethod
    def _revoke(name, schema):
        return [
            f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {name}",
            f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM {name}",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL ON TABLES FROM {name}",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL ON SEQUENCES FROM {name}",
        ]


class MySql:
    """MySQL and MariaDB: a user per guest, granted on this one database (database.* covers new tables too)."""
    transactional = False  # account statements commit by themselves

    def scope(self, cursor):
        cursor.execute("SELECT DATABASE()")
        return cursor.fetchone()[0], None

    def logins(self, cursor):
        cursor.execute("SELECT User FROM mysql.user WHERE Host = '%' AND User LIKE 'dbm%'")
        return {_text(row[0]) for row in cursor.fetchall() if parse_login(_text(row[0]))}

    def create(self, name, password, scope):
        return [f"CREATE USER '{name}'@'%' IDENTIFIED BY {_literal(password)}"]

    def set_password(self, name, password):
        return [f"ALTER USER '{name}'@'%' IDENTIFIED BY {_literal(password)}"]

    def grant(self, name, privileges, scope):
        database = "`" + scope[0].replace("`", "``") + "`"
        return [f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM '{name}'@'%'",
                f"GRANT {', '.join(privileges)} ON {database}.* TO '{name}'@'%'"]

    def drop(self, name, scope):
        return [f"DROP USER '{name}'@'%'"]


class SqlServer:
    """A server login per guest, mapped to a user in this database and granted on its schema."""
    transactional = False  # CREATE LOGIN may not run inside a transaction

    def scope(self, cursor):
        cursor.execute("SELECT DB_NAME(), SCHEMA_NAME()")
        return cursor.fetchone()

    def logins(self, cursor):
        cursor.execute("SELECT name FROM sys.server_principals WHERE type = 'S' AND name LIKE 'dbm%'")
        return {row[0] for row in cursor.fetchall() if parse_login(row[0])}

    def create(self, name, password, scope):
        schema = quote_identifier(scope[1], "SQLSERVER")
        return [f"CREATE LOGIN [{name}] WITH PASSWORD = N{_literal(password)}",
                f"IF USER_ID(N'{name}') IS NULL CREATE USER [{name}] FOR LOGIN [{name}] WITH DEFAULT_SCHEMA = {schema}"]

    def set_password(self, name, password):
        return [f"ALTER LOGIN [{name}] WITH PASSWORD = N{_literal(password)}"]

    def grant(self, name, privileges, scope):
        schema = quote_identifier(scope[1], "SQLSERVER")
        return [f"IF USER_ID(N'{name}') IS NULL CREATE USER [{name}] FOR LOGIN [{name}] WITH DEFAULT_SCHEMA = {schema}",
                f"REVOKE SELECT, INSERT, UPDATE, DELETE ON SCHEMA::{schema} FROM [{name}]",
                f"GRANT {', '.join(privileges)} ON SCHEMA::{schema} TO [{name}]"]

    def drop(self, name, scope):
        return [f"IF USER_ID(N'{name}') IS NOT NULL DROP USER [{name}]", f"DROP LOGIN [{name}]"]


def _text(value):
    return value.decode() if isinstance(value, (bytes, bytearray)) else value
