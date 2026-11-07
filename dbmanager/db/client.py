"""DatabaseClient - the user's databases, reached directly from this computer.

The server knows where each database is and who may use it; it never connects to one. Every database
runs on its owner's own computer or network, so only machines there can reach it: this app connects
itself, with one of two sign-ins.

- The owner signs in with their own database user and password. The server keeps the password
  (encrypted) and hands it over with the sign-in; it is kept in memory until sign-out (passwords.py), and
  asked for when it is not known or the database refuses it - then saved back to the server.
- A guest signs in with a login of their own that the owner's app made in the database (guests.py), holding
  exactly the permissions they accepted. Its password is collected from the server once an invitation is
  accepted, and only kept in memory.

Either way the database itself enforces what the user may do. Queries are reported to the server's audit
log afterwards, so the owner's trail still shows what was run.
"""

import logging

from dbmanager.api import ApiError
from dbmanager.config import QUERY_MAX_ROWS
from dbmanager.db import drivers, guests
from dbmanager.db.drivers import DatabaseError
from dbmanager.db.execute import run_statements
from dbmanager.db.passwords import default_passwords
from dbmanager.db.schema import read_schema
from dbmanager.db.script import split_script
from dbmanager.i18n import tr

log = logging.getLogger(__name__)


class DatabaseClient:
    """ask_password(connection, problem) -> password or None is how the owner is asked for a password this
    computer does not know (problem: why, when the last one was refused). Without it, nobody is asked."""

    def __init__(self, api, passwords=None, ask_password=None):
        self.api = api
        self.passwords = passwords if passwords is not None else default_passwords()
        self.ask_password = ask_password
        self._guest_logins = {}  # connection id -> (login, password) collected from the server
        take = getattr(api, "take_sign_in_passwords", None)
        for connection_id, password in (take() if take else {}).items():
            self.passwords.set(self._key(connection_id), password)

    # ---------------- Registering databases ----------------
    def create_connection(self, details):
        """Register a database on the server, password included (it keeps it encrypted), and keep the
        password for this session too."""
        created = self.api.create_connection(details)
        if details.get("dbPassword"):
            self.passwords.set(self._key(created["id"]), details["dbPassword"])
        return created

    def update_connection(self, connection_id, details):
        """Change a database on the server; leave dbPassword out to keep the stored one."""
        updated = self.api.update_connection(connection_id, details)
        if details.get("dbPassword"):
            self.passwords.set(self._key(connection_id), details["dbPassword"])
        return updated

    def delete_connection(self, connection_id):
        self.api.delete_connection(connection_id)
        self.forget(connection_id)

    def forget(self, connection_id):
        """Drop what this session knows about signing in to a database."""
        self.passwords.delete(self._key(connection_id))
        self._guest_logins.pop(connection_id, None)

    def end_session(self):
        """Signing out: the passwords and guest logins of this session go."""
        self._guest_logins.clear()
        self.passwords.clear_session()

    def is_owner(self, connection):
        return connection.get("ownerUserId") == self.api.user_id

    # ---------------- Talking to a database ----------------
    def test_new(self, details):
        """Can this computer reach a database that is not saved yet? Says what answered, or raises."""
        return drivers.test(details, details["dbUsername"], details.get("dbPassword") or "")

    def test_saved(self, connection, details=None):
        """The same for a saved database of yours - with the edited details when given; leave dbPassword out
        of them to use the password kept here."""
        target = {**connection, **(details or {})}
        if (details or {}).get("dbPassword"):
            return drivers.test(target, target["dbUsername"], details["dbPassword"])
        return drivers.test(target, target["dbUsername"], self._owner_password(connection))

    def schema(self, connection):
        db_connection = self._open(connection)
        try:
            return read_schema(db_connection, connection["dbType"])
        except Exception as error:  # noqa: BLE001
            raise DatabaseError(tr("db.client.tables_unreadable", database=connection["dbName"],
                                   reason=drivers.error_message(error))) from None
        finally:
            db_connection.close()

    def run_query(self, connection, sql, max_rows=None):
        """One statement; returns its result."""
        return self._run(connection, [sql.strip().rstrip(";")], max_rows, report=True)["results"][0]

    def run_script(self, connection, sql):
        """';'-separated statements in one transaction: {"results": [...], "durationMs": n}"""
        statements = split_script(sql, connection["dbType"])
        if not statements:
            raise DatabaseError(tr("db.client.nothing_to_run"))
        return self._run(connection, statements, None, report=True)

    def _run(self, connection, statements, max_rows, report):
        limit = min(max_rows or QUERY_MAX_ROWS, QUERY_MAX_ROWS)
        db_connection = self._open(connection)
        try:
            results, duration = run_statements(db_connection, connection["dbType"], statements, limit)
        except DatabaseError as error:
            if report:
                self._report(connection, "QUERY_FAILED", f"{error.record} | {'; '.join(statements)}", False)
            raise
        finally:
            db_connection.close()
        if report:
            kinds = {result["statementType"] for result in results}
            action = "QUERY_" + (kinds.pop() if len(kinds) == 1 else "SCRIPT")
            summary = ", ".join(_outcome(result) for result in results[:5]) + (" ..." if len(results) > 5 else "")
            self._report(connection, action, f"{summary}: {'; '.join(statements)}", True)
        return {"results": results, "durationMs": duration}

    def _report(self, connection, action, detail, success):
        """Best effort: a query that ran is not undone because the audit log could not be told."""
        try:
            self.api.record_audit(connection["id"], action, detail, success)
        except ApiError as error:
            log.info("Could not report %s on connection %s to the audit log: %s", action, connection["id"], error)

    # ---------------- Signing in ----------------
    def _open(self, connection):
        if self.is_owner(connection):
            return self._open_as_owner(connection)
        return self._open_as_guest(connection)

    def _open_as_owner(self, connection):
        key = self._key(connection["id"])
        password = self.passwords.get(key)
        typed = password is None
        if typed:
            password = self._ask(connection, None)
        try:
            db_connection = drivers.connect(connection, connection["dbUsername"], password)
        except DatabaseError as error:
            if not error.refused_login or self.ask_password is None:
                raise
            # The password kept here is out of date: ask once more
            self.passwords.delete(key)
            password, typed = self._ask(connection, str(error)), True
            db_connection = drivers.connect(connection, connection["dbUsername"], password)
        if typed:  # it worked: keep it, and give it to the server so the next sign-in knows it
            self.passwords.set(key, password)
            self._save_password(connection, password)
        return db_connection

    def _save_password(self, connection, password):
        fields = ("host", "port", "dbName", "dbUsername", "dbType")
        try:
            self.api.update_connection(connection["id"], {**{name: connection[name] for name in fields},
                                                          "dbPassword": password})
        except ApiError as error:  # it works for this session anyway; the next sign-in asks again
            log.info("Could not save the new password of connection %s: %s", connection["id"], error)

    def _owner_password(self, connection):
        password = self.passwords.get(self._key(connection["id"]))
        return password if password is not None else self._ask(connection, None)

    def _ask(self, connection, problem):
        password = self.ask_password(connection, problem) if self.ask_password else None
        if not password:
            raise DatabaseError(tr("db.client.password_unknown", database=connection["dbName"]),
                                cancelled=self.ask_password is not None)
        return password

    def _open_as_guest(self, connection):
        login = self._guest_logins.get(connection["id"]) or self._collect_guest_login(connection)
        try:
            return drivers.connect(connection, *login)
        except DatabaseError as error:
            if not error.refused_login:
                raise
        # The owner's app may have given the login a new password since: collect it again, once
        login = self._collect_guest_login(connection)
        try:
            return drivers.connect(connection, *login)
        except DatabaseError as error:
            if not error.refused_login:
                raise
            raise DatabaseError(tr("db.client.guest_login_refused", database=connection["dbName"]),
                                unreachable=True, refused_login=True) from None

    def _collect_guest_login(self, connection):
        credentials = self.api.guest_credentials(connection["id"])
        login = (credentials["dbUsername"], credentials["dbPassword"])
        self._guest_logins[connection["id"]] = login
        return login

    def _key(self, connection_id):
        """One entry per server and connection: two servers may both have a connection 1."""
        return f"{self.api.base_url}#connection-{connection_id}"

    # ---------------- Guest logins (owner only) ----------------
    def sync_guests(self, connection, invitations=None):
        """Bring the guest logins in the database in line with the invitations to it (see guests.py).

        Returns {"created": [user ids], "dropped": [login names]}. With nothing to do - nobody invited,
        nothing kept on the server - a database that cannot even list its logins is left alone."""
        if invitations is None:
            invitations = self.api.list_invitations()
        desired = guests.desired_privileges(invitations, self.api.user_id, connection["id"])
        saved = {account["userId"]: account["dbUsername"] for account in self.api.list_guest_accounts(connection["id"])}
        try:
            changed = self._apply_guest_plan(connection, desired, saved)
        except DatabaseError:
            if desired or saved:
                raise
            return {"created": [], "dropped": []}
        for user_id, name, password in changed["passwords"]:
            self.api.save_guest_account(connection["id"], user_id, name, password)
        for user_id in changed["forget"]:
            self.api.delete_guest_account(connection["id"], user_id)
        return {"created": changed["created"], "dropped": changed["dropped"]}

    def drop_guest_logins(self, connection):
        """Remove every guest login of this database from the database itself - before the database (or the
        whole account) goes. Needs no server: it only asks the database what this app made there."""
        return self._apply_guest_plan(connection, {}, {})["dropped"]

    def _apply_guest_plan(self, connection, desired, saved):
        db_type = connection["dbType"]
        try:
            sql = guests.dialect(db_type)
        except ValueError as error:
            raise DatabaseError(str(error)) from None
        db_connection = self._open_as_owner(connection)
        try:
            if not sql.transactional:
                _set_autocommit(db_connection, db_type)
            cursor = db_connection.cursor()
            try:
                scope = sql.scope(cursor)
                actions = guests.plan(connection["id"], desired, sql.logins(cursor), saved)
                passwords = []
                statements = []
                for user_id in actions["create"] + actions["new_password"]:
                    name, password = guests.login_name(user_id, connection["id"]), guests.new_password()
                    statements += (sql.create(name, password, scope) if user_id in actions["create"]
                                   else sql.set_password(name, password))
                    passwords.append((user_id, name, password))
                for user_id, privileges in actions["grant"].items():
                    statements += sql.grant(guests.login_name(user_id, connection["id"]), privileges, scope)
                for name in actions["drop"]:
                    statements += sql.drop(name, scope)
                for statement in statements:
                    cursor.execute(statement)
                if sql.transactional:
                    db_connection.commit()
            finally:
                cursor.close()
        except DatabaseError:
            raise
        except Exception as error:  # noqa: BLE001 - the driver's error: most often a missing right
            raise DatabaseError(tr("db.client.guest_logins_failed", database=connection["dbName"],
                                   reason=drivers.error_message(error))) from None
        finally:
            db_connection.close()
        return {"created": actions["create"], "dropped": actions["drop"], "passwords": passwords,
                "forget": actions["forget"]}


def _set_autocommit(db_connection, db_type):
    if db_type == "POSTGRESQL":
        db_connection.autocommit = True
    else:
        db_connection.autocommit(True)  # PyMySQL and pymssql: a method


def _outcome(result):
    if result.get("updateCount") is None:
        return f"{len(result.get('rows') or [])} row(s) returned"
    if result.get("statementType") in ("INSERT", "UPDATE", "DELETE"):
        return f"{result['updateCount']} row(s) affected"
    return result.get("statementType") or "done"
