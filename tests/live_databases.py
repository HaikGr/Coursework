"""
The database layer against real servers: the owner's queries, reading the schema, and sharing through
guest logins that the database itself holds to their permissions. Not part of the unit tests (it needs
the servers). Each type runs when its variables are set, as user@host:port/database with the owner's
password - a user that may create users and grant (postgres, root, sa):

    LIVE_POSTGRESQL=postgres:secret@127.0.0.1:5432/scratch \
    LIVE_MYSQL=root:secret@127.0.0.1:3306/scratch \
    LIVE_MARIADB=root:secret@127.0.0.1:3307/scratch \
    LIVE_SQLSERVER='sa:Secret-pw-1@127.0.0.1:1433/master' \
    python -m unittest tests.live_databases -v

It creates and drops its own tables (live_*) and guest logins (dbm_u8_c<n>). Use scratch databases.
"""

import os
import re
import unittest
import uuid
from decimal import Decimal

from dbmanager.db.client import DatabaseClient
from dbmanager.db.drivers import DatabaseError
from dbmanager.db.passwords import MemoryPasswords
from dbmanager.model.change_script import build_change_script
from dbmanager.model.query import Join, QueryModel
from dbmanager.model.table_state import from_schema

OWNER_ID, GUEST_ID = 7, 8


def _target(db_type):
    value = os.environ.get(f"LIVE_{db_type}")
    if not value:
        return None
    match = re.fullmatch(r"(?P<user>[^:]+):(?P<password>.*)@(?P<host>[^:@]+):(?P<port>\d+)/(?P<db>.+)", value)
    if not match:
        raise ValueError(f"LIVE_{db_type} must look like user:password@host:port/database")
    return match.groupdict()


class FakeServer:
    """What the backend keeps: invitations, guest accounts and the audit log, shared by both apps."""

    def __init__(self):
        self.invitations = []
        self.accounts = {}  # (connection id, user id) -> (login, password)
        self.audit = []


class FakeApi:
    base_url = "http://live-test"

    def __init__(self, server, user_id):
        self.server = server
        self.user_id = user_id

    def list_invitations(self):
        return list(self.server.invitations)

    def list_guest_accounts(self, connection_id):
        return [{"userId": user_id, "dbUsername": login} for (cid, user_id), (login, _) in self.server.accounts.items()
                if cid == connection_id]

    def save_guest_account(self, connection_id, user_id, db_username, db_password):
        self.server.accounts[(connection_id, user_id)] = (db_username, db_password)

    def delete_guest_account(self, connection_id, user_id):
        self.server.accounts.pop((connection_id, user_id), None)

    def guest_credentials(self, connection_id):
        accepted = any(i["toUserId"] == self.user_id and i["dbConnectionId"] == connection_id
                       and i["status"] == "ACCEPTED" for i in self.server.invitations)
        login = self.server.accounts.get((connection_id, self.user_id))
        if not accepted or not login:
            from dbmanager.api import ApiError
            raise ApiError(403 if not accepted else 404, "no login for you")
        return {"dbUsername": login[0], "dbPassword": login[1]}

    def record_audit(self, connection_id, action, detail, success):
        self.server.audit.append((self.user_id, connection_id, action, success))


class LiveDatabaseTests:
    """Mixed into one TestCase per database type."""
    db_type = None
    serial_pk = None   # an auto-numbered primary key column, in this dialect

    @classmethod
    def setUpClass(cls):
        target = _target(cls.db_type)
        if target is None:
            raise unittest.SkipTest(f"LIVE_{cls.db_type} is not set")
        # A connection id of its own per run: guest logins are named after it
        cls.connection_id = 1000 + uuid.uuid4().int % 9000
        cls.connection = {"id": cls.connection_id, "ownerUserId": OWNER_ID, "host": target["host"],
                          "port": int(target["port"]), "dbName": target["db"], "dbUsername": target["user"],
                          "dbType": cls.db_type}
        cls.server = FakeServer()
        passwords = MemoryPasswords()
        cls.owner = DatabaseClient(FakeApi(cls.server, OWNER_ID), passwords)
        passwords.set(cls.owner._key(cls.connection_id), target["password"])
        cls.guest = DatabaseClient(FakeApi(cls.server, GUEST_ID), MemoryPasswords())
        cls.suffix = uuid.uuid4().hex[:6]
        cls.customers, cls.orders = f"live_customers_{cls.suffix}", f"live_orders_{cls.suffix}"

    @classmethod
    def tearDownClass(cls):
        for table in (cls.orders, cls.customers, f"live_later_{cls.suffix}"):
            try:
                cls.owner.run_script(cls.connection, f"DROP TABLE {table}")
            except DatabaseError:
                pass
        cls.owner.drop_guest_logins(cls.connection)

    def owner_rows(self, sql):
        return self.owner.run_query(self.connection, sql)["rows"]

    def guest_query(self, sql):
        return self.guest.run_query(self.connection, sql)

    def invite(self, *permissions, status="ACCEPTED"):
        self.server.invitations = [
            {"fromUserId": OWNER_ID, "toUserId": GUEST_ID, "dbConnectionId": self.connection_id,
             "permission": permission, "status": status} for permission in permissions]
        return self.owner.sync_guests(self.connection)

    def test_1_the_owner_designs_fills_and_reads_tables(self):
        self.assertRegex(self.owner.test_saved(self.connection), r"^Connected to .+ in \d+ ms$")
        result = self.owner.run_script(self.connection, f"""
            CREATE TABLE {self.customers} (id {self.serial_pk}, name VARCHAR(100) NOT NULL, balance DECIMAL(10,2),
                                          born DATE);
            CREATE TABLE {self.orders} (id INT PRIMARY KEY, customer_id INT,
                                       FOREIGN KEY (customer_id) REFERENCES {self.customers} (id));
            INSERT INTO {self.customers} (name, balance, born) VALUES ('O''Brien; Jr', 10.5, '2001-02-03');
            INSERT INTO {self.customers} (name) VALUES ('100%');
            INSERT INTO {self.orders} (id, customer_id) VALUES (1, 1)""")
        self.assertEqual([r["statementType"] for r in result["results"]],
                         ["CREATE", "CREATE", "INSERT", "INSERT", "INSERT"])
        self.assertEqual(result["results"][2]["updateCount"], 1)

        rows = self.owner_rows(f"SELECT id, name, balance, born FROM {self.customers} ORDER BY id")
        self.assertEqual(rows, [[1, "O'Brien; Jr", Decimal("10.50"), "2001-02-03"], [2, "100%", None, None]])

        tables = {table["name"]: table for table in self.owner.schema(self.connection)}
        self.assertIn(self.customers, tables)
        columns = {column["name"]: column for column in tables[self.orders]["columns"]}
        self.assertTrue(columns["id"]["primaryKey"])
        self.assertEqual((columns["customer_id"]["referencedTable"], columns["customer_id"]["referencedColumn"]),
                         (self.customers, "id"))
        self.assertFalse(columns["id"]["nullable"])
        self.assertTrue(any(action == "QUERY_SCRIPT" for _, _, action, _ in self.server.audit))

    def test_2_a_failing_statement_undoes_the_whole_script(self):
        with self.assertRaises(DatabaseError) as raised:
            self.owner.run_script(self.connection, f"UPDATE {self.customers} SET name = 'changed' WHERE id = 1;"
                                                   f"INSERT INTO {self.orders} (id, customer_id) VALUES (1, 1)")
        self.assertIn("statement 2 of 2 (INSERT) - nothing was saved", str(raised.exception))
        self.assertEqual(self.server.audit[-1][2:], ("QUERY_FAILED", False))
        self.assertEqual(self.owner_rows(f"SELECT name FROM {self.customers} WHERE id = 1"), [["O'Brien; Jr"]])

    def test_3_a_guest_may_do_exactly_what_they_accepted(self):
        summary = self.invite("SELECT_ROLE", "INSERT_ROLE")
        self.assertEqual(summary["created"], [GUEST_ID])
        login, password = self.server.accounts[(self.connection_id, GUEST_ID)]
        self.assertEqual(login, f"dbm_u{GUEST_ID}_c{self.connection_id}")
        self.assertNotEqual(password, _target(self.db_type)["password"], "never the owner's password")

        self.assertEqual(len(self.guest_query(f"SELECT * FROM {self.customers}")["rows"]), 2)
        self.guest.run_script(self.connection, f"INSERT INTO {self.customers} (name) VALUES ('from guest')")
        for forbidden in (f"UPDATE {self.customers} SET name = 'x' WHERE id = 1",
                          f"DELETE FROM {self.customers} WHERE id = 1",
                          f"DROP TABLE {self.orders}"):
            with self.subTest(forbidden=forbidden), self.assertRaises(DatabaseError) as raised:
                self.guest.run_script(self.connection, forbidden)
            self.assertRegex(str(raised.exception).lower(), r"denied|permission|not have|must be owner")
        self.assertEqual(self.owner_rows(f"SELECT count(*) FROM {self.orders}"), [[1]], "nothing was dropped")
        names = {table["name"] for table in self.guest.schema(self.connection)}
        self.assertIn(self.customers, names)

    def test_4_tables_made_later_are_shared_too(self):
        self.invite("SELECT_ROLE")
        later = f"live_later_{self.suffix}"
        self.owner.run_script(self.connection, f"CREATE TABLE {later} (id INT PRIMARY KEY); "
                                               f"INSERT INTO {later} (id) VALUES (42)")
        self.assertEqual(self.guest_query(f"SELECT id FROM {later}")["rows"], [[42]])

    def test_5_taking_a_permission_away_takes_it_from_the_database(self):
        self.invite("SELECT_ROLE", "INSERT_ROLE")
        self.invite("SELECT_ROLE")
        self.guest_query(f"SELECT * FROM {self.customers}")
        with self.assertRaises(DatabaseError):
            self.guest.run_script(self.connection, f"INSERT INTO {self.customers} (name) VALUES ('no')")

    def test_6_revoking_everything_drops_the_login_and_inviting_again_makes_a_new_one(self):
        self.invite("SELECT_ROLE")
        self.guest_query(f"SELECT * FROM {self.customers}")  # the guest app now holds the login
        summary = self.invite("SELECT_ROLE", status="REVOKED")
        self.assertEqual(summary["dropped"], [f"dbm_u{GUEST_ID}_c{self.connection_id}"])
        self.assertNotIn((self.connection_id, GUEST_ID), self.server.accounts)
        with self.assertRaises(Exception):
            self.guest_query(f"SELECT * FROM {self.customers}")

        self.invite("SELECT_ROLE")
        self.assertEqual(len(self.guest_query(f"SELECT * FROM {self.customers}")["rows"]), 3,
                         "the new password is collected again")

    def test_7_the_logins_go_with_the_database(self):
        self.invite("SELECT_ROLE")
        self.assertEqual(self.owner.drop_guest_logins(self.connection), [f"dbm_u{GUEST_ID}_c{self.connection_id}"])
        self.assertEqual(self.owner.drop_guest_logins(self.connection), [])


class LiveTables:
    """Tables of its own in the owner's database, made and dropped by the test, and read as the sidebar does"""
    db_type = None

    @classmethod
    def setUpClass(cls):
        target = _target(cls.db_type)
        if target is None:
            raise unittest.SkipTest(f"LIVE_{cls.db_type} is not set")
        cls.connection = {"id": 1, "ownerUserId": OWNER_ID, "host": target["host"], "port": int(target["port"]),
                          "dbName": target["db"], "dbUsername": target["user"], "dbType": cls.db_type}
        passwords = MemoryPasswords()
        cls.owner = DatabaseClient(FakeApi(FakeServer(), OWNER_ID), passwords)
        passwords.set(cls.owner._key(1), target["password"])
        cls.suffix = uuid.uuid4().hex[:6]
        cls.made = []

    @classmethod
    def tearDownClass(cls):
        for table in reversed(cls.made):  # children were made after their parents
            try:
                cls.owner.run_script(cls.connection, f"DROP TABLE {table}")
            except DatabaseError:
                pass

    def make(self, name, ddl, *rows):
        table = f"{name}_{self.suffix}"
        self.made.append(table)
        script = [f"CREATE TABLE {table} ({ddl.format(s=self.suffix)})"] + [f"INSERT INTO {table} VALUES ({row})"
                                                                            for row in rows]
        self.owner.run_script(self.connection, ";\n".join(script))
        return table

    def read(self, *names, rows=True):
        """TableStates of these tables as the sidebar builds them, with their rows loaded"""
        schema = {table["name"]: table for table in self.owner.schema(self.connection)}
        states = {name: from_schema(schema[name], self.db_type) for name in names}
        for name, state in states.items():
            if rows:
                result = self.owner.run_query(self.connection, f"SELECT * FROM {name}")
                state.load_rows(result["columns"], result["rows"])
        return states

    def save(self, tables):
        db_links = {(c["refTable"], c["refColumns"][0], name, c["columns"][0])
                    for name, state in tables.items() for c in state.references_to()}
        problems = [problem for state in tables.values() for problem in state.problems()]
        self.assertEqual(problems, [])
        script = build_change_script(tables, [], db_links, self.db_type)
        self.owner.run_script(self.connection, ";\n".join(script))
        return script

    def column_names(self, table):
        return self.read(table, rows=False)[table].column_names()

    def column(self, table, name):
        schema = {t["name"]: t for t in self.owner.schema(self.connection)}
        return next(c for c in schema[table]["columns"] if c["name"] == name)


class LiveSchemaChangeTests(LiveTables):
    """Changing tables that have rows and keys, as the table editor does: the script it builds must run.
    Mixed into one TestCase per database type."""

    def test_a_not_null_field_gets_its_values_before_it_requires_them(self):
        table = self.make("nn_values", "id INT PRIMARY KEY, label VARCHAR(20)", "1, 'a'", "2, 'b'", "3, NULL")
        state = self.read(table)[table]
        state.add_column(["qty", "int", "Not Null", "-", "-", "-", "-"])
        self.assertIn("rows 1, 2 and 3 have none", state.problems()[0])
        for row, value in enumerate(("10", "20", "30")):
            state.set_cell(row, 2, value)
        self.save({table: state})
        self.assertFalse(self.column(table, "qty")["nullable"])
        self.assertEqual(self.owner.run_query(self.connection, f"SELECT qty FROM {table} ORDER BY id")["rows"],
                         [[10], [20], [30]])

    def test_a_default_value_fills_the_rows_already_there(self):
        table = self.make("nn_default", "id INT PRIMARY KEY", "1", "2")
        state = self.read(table)[table]
        state.add_column(["stock", "int", "Not Null", "-", "-", "-", "-", "5"])
        state.add_column(["note", "varchar", "Null", "-", "-", "-", "-", "n/a"])
        self.assertEqual(state.rows, [[1, "5", "n/a"], [2, "5", "n/a"]])
        self.save({table: state})
        self.assertFalse(self.column(table, "stock")["nullable"])
        self.assertEqual(self.owner.run_query(self.connection, f"SELECT stock, note FROM {table} ORDER BY id")["rows"],
                         [[5, "n/a"], [5, "n/a"]])

    def test_requiring_a_value_fills_the_empty_rows_first_and_keeps_the_rest_of_the_column(self):
        extra = " DEFAULT 'x' COMMENT 'kept'" if self.db_type in ("MYSQL", "MARIADB") else " DEFAULT 'x'"
        table = self.make("nn_tighten", "id INT PRIMARY KEY, code VARCHAR(30)" + extra,
                          "1, 'a'", "2, NULL", "3, NULL")
        state = self.read(table)[table]
        before = self.column(table, "code")
        state.set_nullable(1, False)
        self.assertIn("rows 2 and 3 have none", state.problems()[0])
        state.set_nullable(1, False, fill="none yet")
        self.save({table: state})
        after = self.column(table, "code")
        self.assertFalse(after["nullable"])
        self.assertEqual(after["sqlType"], before["sqlType"], "the length stays")
        if "mysql" in before:
            self.assertEqual(after["mysql"]["default"], before["mysql"]["default"])
            self.assertEqual(after["mysql"]["comment"], "kept")
        self.assertEqual(self.owner.run_query(self.connection, f"SELECT code FROM {table} ORDER BY id")["rows"],
                         [["a"], ["none yet"], ["none yet"]])

        state = self.read(table)[table]
        state.set_nullable(1, True)
        self.save({table: state})
        self.assertTrue(self.column(table, "code")["nullable"])

    def test_a_column_other_tables_point_at_can_be_dropped(self):
        parent = self.make("drop_parent", "id INT PRIMARY KEY, code VARCHAR(10) UNIQUE", "1, 'a'")
        child = self.make("drop_child", f"id INT PRIMARY KEY, parent_code VARCHAR(10), "
                                        f"CONSTRAINT fk_code_{{s}} FOREIGN KEY (parent_code) REFERENCES {parent} (code)",
                          "1, 'a'")
        tables = self.read(parent, child)
        tables[parent].delete_column(1)
        script = self.save(tables)
        self.assertTrue(any(f"fk_code_{self.suffix}" in statement for statement in script))
        self.assertEqual(self.column_names(parent), ["id"])
        self.assertEqual(self.read(child)[child].references_to(), [], "the foreign key went first")

    def test_a_table_other_tables_point_at_can_be_dropped(self):
        parent = self.make("gone_parent", "id INT PRIMARY KEY", "1")
        # a table-level FOREIGN KEY: MySQL ignores REFERENCES written on the column
        child = self.make("gone_child", f"id INT PRIMARY KEY, parent_id INT, FOREIGN KEY (parent_id) REFERENCES {parent} (id)",
                          "1, 1")
        tables = self.read(parent, child)
        self.assertEqual(len(tables[child].references_to()), 1)
        tables[parent].pending_drop = True
        self.save(tables)
        names = {table["name"] for table in self.owner.schema(self.connection)}
        self.assertNotIn(parent, names)
        self.assertIn(child, names)
        self.made.remove(parent)

    def test_a_column_with_keys_defaults_checks_and_indexes_of_its_own_can_be_dropped(self):
        parent = self.make("own_parent", "id INT PRIMARY KEY", "1")
        table = self.make("own_cols", "id INT PRIMARY KEY, parent_id INT, "
                                      "price DECIMAL(10,2) DEFAULT 0 CHECK (price >= 0), code VARCHAR(10) UNIQUE, "
                                      f"FOREIGN KEY (parent_id) REFERENCES {parent} (id)",
                          "1, 1, 2.5, 'a'")
        self.owner.run_script(self.connection, f"CREATE INDEX ix_price_{self.suffix} ON {table} (price)")
        tables = self.read(parent, table)
        self.assertEqual(len(tables[table].references_to("parent_id")), 1)
        for name in ("code", "price", "parent_id"):
            tables[table].delete_column(tables[table].column_names().index(name))
        self.save(tables)
        self.assertEqual(self.column_names(table), ["id"])


class LiveJoinTests(LiveTables):
    """The joins the query panel writes return the rows they promise"""

    def rows(self, model):
        sql, warnings = model.build(self.db_type)
        self.assertEqual(warnings, [])
        return sorted(self.owner.run_query(self.connection, sql)["rows"], key=str)

    def test_inner_left_and_right_joins(self):
        customers = self.make("j_customers", "id INT PRIMARY KEY, name VARCHAR(20)", "1, 'Ann'", "2, 'Bob'")
        orders = self.make("j_orders", "id INT PRIMARY KEY, customer_id INT, total INT", "10, 1, 5")
        model = QueryModel()
        model.add_column(customers, "name")
        model.add_column(orders, "total")
        model.add_join(Join(customers, "id", orders, "customer_id"))
        self.assertEqual(self.rows(model), [["Ann", 5]], "JOIN: only the customer with an order")
        model.joins[0].kind = "LEFT"
        self.assertEqual(self.rows(model), [["Ann", 5], ["Bob", None]], "LEFT JOIN: every customer")

        reverse = QueryModel()  # orders first: the same LEFT join is reached from its right side
        reverse.add_column(orders, "total")
        reverse.add_column(customers, "name")
        reverse.add_join(Join(customers, "id", orders, "customer_id", "LEFT"))
        self.assertIn("RIGHT JOIN", reverse.build(self.db_type)[0])
        self.assertEqual(self.rows(reverse), [[5, "Ann"], [None, "Bob"]])

        linked = QueryModel()  # a link of the diagram joins too
        linked.links = [(customers, "id", orders, "customer_id")]
        linked.add_column(customers, "name")
        linked.add_column(orders, "total")
        self.assertEqual(self.rows(linked), [["Ann", 5]])


class PostgresSchemaChangeTest(LiveSchemaChangeTests, unittest.TestCase):
    db_type = "POSTGRESQL"


class MySqlSchemaChangeTest(LiveSchemaChangeTests, unittest.TestCase):
    db_type = "MYSQL"


class MariaDbSchemaChangeTest(LiveSchemaChangeTests, unittest.TestCase):
    db_type = "MARIADB"


class SqlServerSchemaChangeTest(LiveSchemaChangeTests, unittest.TestCase):
    db_type = "SQLSERVER"


class PostgresLiveTest(LiveDatabaseTests, unittest.TestCase):
    db_type = "POSTGRESQL"
    serial_pk = "SERIAL PRIMARY KEY"


class MySqlLiveTest(LiveDatabaseTests, unittest.TestCase):
    db_type = "MYSQL"
    serial_pk = "INT AUTO_INCREMENT PRIMARY KEY"


class MariaDbLiveTest(LiveDatabaseTests, unittest.TestCase):
    db_type = "MARIADB"
    serial_pk = "INT AUTO_INCREMENT PRIMARY KEY"


class SqlServerLiveTest(LiveDatabaseTests, unittest.TestCase):
    db_type = "SQLSERVER"
    serial_pk = "INT IDENTITY(1,1) PRIMARY KEY"


if __name__ == "__main__":
    unittest.main()


class PostgresJoinTest(LiveJoinTests, unittest.TestCase):
    db_type = "POSTGRESQL"


class MySqlJoinTest(LiveJoinTests, unittest.TestCase):
    db_type = "MYSQL"


class MariaDbJoinTest(LiveJoinTests, unittest.TestCase):
    db_type = "MARIADB"


class SqlServerJoinTest(LiveJoinTests, unittest.TestCase):
    db_type = "SQLSERVER"
