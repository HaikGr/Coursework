"""The database layer without a database: splitting scripts, planning guest logins, values, signing in."""

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest import mock

from dbmanager.db import guests
from dbmanager.db.client import DatabaseClient
from dbmanager.db.drivers import DatabaseError, error_message
from dbmanager.db.passwords import MemoryPasswords
from dbmanager.db.script import split_script, statement_type
from dbmanager.db.values import to_value


class SplitScriptTest(unittest.TestCase):
    def test_semicolons_inside_literals_identifiers_and_comments_do_not_split(self):
        sql = ("INSERT INTO t VALUES ('a;b', 'it''s');\n"
               '-- a comment; still a comment\n'
               'UPDATE "odd;name" SET x = 1 /* not ; here */;\n'
               ";;\n"
               "SELECT 1")
        self.assertEqual(split_script(sql, "POSTGRESQL"), [
            "INSERT INTO t VALUES ('a;b', 'it''s')",
            '-- a comment; still a comment\nUPDATE "odd;name" SET x = 1 /* not ; here */',
            "SELECT 1",
        ])

    def test_each_dialect_quotes_its_own_way(self):
        self.assertEqual(len(split_script("SELECT `a;b` FROM t; SELECT 'x\\';y'", "MYSQL")), 2)
        self.assertEqual(len(split_script("SELECT [a;b] FROM t; SELECT 2", "SQLSERVER")), 2)
        self.assertEqual(len(split_script("SELECT $tag$ ; $tag$; SELECT E'\\';'", "POSTGRESQL")), 2)
        # MySQL only opens a comment at "-- ": 1--1 is arithmetic, and # is a comment
        self.assertEqual(split_script("SELECT 1--1; # skip ; this\nSELECT 2", "MYSQL"),
                         ["SELECT 1--1", "# skip ; this\nSELECT 2"])

    def test_a_script_of_only_comments_has_no_statements(self):
        self.assertEqual(split_script("-- nothing\n/* at /* nested */ all; */", "POSTGRESQL"), [])

    def test_sql_server_go_lines_send_each_batch_whole(self):
        script = ("CREATE TABLE a (id int);\nGO\n"
                  "CREATE PROCEDURE p AS\nBEGIN\n  SELECT 1;\n  SELECT 2;\nEND\ngo -- the end\n"
                  "SELECT 'GO\n' AS x\n  GO 2\n")
        self.assertEqual(split_script(script, "SQLSERVER"), [
            "CREATE TABLE a (id int);",
            "CREATE PROCEDURE p AS\nBEGIN\n  SELECT 1;\n  SELECT 2;\nEND",
            "SELECT 'GO\n' AS x",
        ])
        # Without a GO line, statements end at ';' as everywhere else; a word that starts with go is no GO
        self.assertEqual(split_script("SELECT 1; SELECT 2", "SQLSERVER"), ["SELECT 1", "SELECT 2"])
        self.assertEqual(split_script("SELECT 1\ngo_live = 1", "SQLSERVER"), ["SELECT 1\ngo_live = 1"])
        # GO means nothing to the other databases
        self.assertEqual(len(split_script("SELECT 1;\nGO\nSELECT 2", "POSTGRESQL")), 2)

    def test_mysql_delimiter_lines_change_what_ends_a_statement(self):
        script = ("DELIMITER $$\n"
                  "CREATE TRIGGER t BEFORE INSERT ON a FOR EACH ROW BEGIN SET NEW.x = 1; SET NEW.y = 2; END$$\n"
                  "DELIMITER ;\n"
                  "INSERT INTO a () VALUES (); SELECT '$$'")
        self.assertEqual(split_script(script, "MYSQL"), [
            "CREATE TRIGGER t BEFORE INSERT ON a FOR EACH ROW BEGIN SET NEW.x = 1; SET NEW.y = 2; END",
            "INSERT INTO a () VALUES ()",
            "SELECT '$$'",
        ])

    def test_the_verb_after_with_names_the_statement(self):
        self.assertEqual(statement_type("with x as (select 1) select * from x", "POSTGRESQL"), "SELECT")
        self.assertEqual(statement_type("WITH x AS (SELECT 1) DELETE FROM t", "POSTGRESQL"), "DELETE")
        self.assertEqual(statement_type("  /* hi */ create table t (id int)", "MYSQL"), "CREATE")


class GuestPlanTest(unittest.TestCase):
    INVITATIONS = [
        {"fromUserId": 7, "toUserId": 8, "dbConnectionId": 3, "permission": "INSERT_ROLE", "status": "ACCEPTED"},
        {"fromUserId": 7, "toUserId": 8, "dbConnectionId": 3, "permission": "SELECT_ROLE", "status": "PENDING"},
        {"fromUserId": 7, "toUserId": 9, "dbConnectionId": 3, "permission": "DELETE_ROLE", "status": "DECLINED"},
        {"fromUserId": 7, "toUserId": 9, "dbConnectionId": 4, "permission": "SELECT_ROLE", "status": "ACCEPTED"},
        {"fromUserId": 9, "toUserId": 7, "dbConnectionId": 3, "permission": "SELECT_ROLE", "status": "ACCEPTED"},
    ]

    def test_only_this_owners_active_invitations_on_this_database_count(self):
        self.assertEqual(guests.desired_privileges(self.INVITATIONS, 7, 3), {8: ["SELECT", "INSERT"]})

    def test_missing_logins_are_made_unknown_ones_get_a_password_and_old_ones_go(self):
        actions = guests.plan(3, {8: ["SELECT"], 10: ["SELECT", "UPDATE"]},
                              existing_logins={"dbm_u10_c3", "dbm_u9_c3", "dbm_u8_c4", "app_user"},
                              saved_accounts={9: "dbm_u9_c3", 12: "dbm_u12_c3"})
        self.assertEqual(actions["create"], [8])
        self.assertEqual(actions["new_password"], [10], "it exists, but the server has no password for it")
        self.assertEqual(actions["grant"], {8: ["SELECT"], 10: ["SELECT", "UPDATE"]})
        self.assertEqual(actions["drop"], ["dbm_u9_c3"], "logins of other connections are not this one's")
        self.assertEqual(actions["forget"], [9, 12])

    def test_nothing_to_do_once_in_line(self):
        actions = guests.plan(3, {8: ["SELECT"]}, {"dbm_u8_c3"}, {8: "dbm_u8_c3"})
        self.assertEqual((actions["create"], actions["new_password"], actions["drop"], actions["forget"]),
                         ([], [], [], []))

    def test_passwords_meet_the_usual_policies_and_need_no_quoting(self):
        for _ in range(50):
            password = guests.new_password()
            self.assertEqual(len(password), 24)
            self.assertTrue(any(c.isupper() for c in password) and any(c.islower() for c in password)
                            and any(c.isdigit() for c in password) and any(c in "-_." for c in password))
            self.assertNotIn("'", password)

    def test_logins_are_named_after_the_guest_and_the_connection(self):
        self.assertEqual(guests.login_name(8, 3), "dbm_u8_c3")
        self.assertEqual(guests.parse_login("dbm_u8_c3"), (8, 3))
        self.assertIsNone(guests.parse_login("dbm_u8_c3; DROP ROLE x"))

    def test_each_permission_becomes_the_matching_grant(self):
        statements = guests.Postgres().grant("dbm_u8_c3", ["SELECT", "INSERT"], ("shop", "public"))
        self.assertIn("GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO dbm_u8_c3", statements)
        self.assertIn("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO dbm_u8_c3", statements)
        self.assertEqual(guests.MySql().grant("dbm_u8_c3", ["SELECT"], ("my shop", None))[-1],
                         "GRANT SELECT ON `my shop`.* TO 'dbm_u8_c3'@'%'")
        self.assertEqual(guests.SqlServer().grant("dbm_u8_c3", ["DELETE"], ("shop", "dbo"))[-1],
                         "GRANT DELETE ON SCHEMA::dbo TO [dbm_u8_c3]")


class ValueTest(unittest.TestCase):
    def test_values_come_out_as_the_editor_expects(self):
        self.assertEqual(to_value(1.5), Decimal("1.5"))
        self.assertEqual(to_value(b"\x01\xff"), "0x01ff")
        self.assertEqual(to_value(date(2026, 1, 2)), "2026-01-02")
        self.assertEqual(to_value(datetime(2026, 1, 2, 3, 4, 5, 120000)), "2026-01-02 03:04:05.12")
        self.assertEqual(to_value(datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)), "2026-01-02 03:04:05+00:00")
        self.assertEqual(to_value({"a": [1, 2]}), '{"a": [1, 2]}')
        for kept in (None, True, 3, Decimal("2.50"), "text"):
            self.assertEqual(to_value(kept), kept)

    def test_driver_errors_read_as_the_servers_own_words(self):
        self.assertEqual(error_message(Exception(1045, "Access denied for user 'x'@'y'")), "Access denied for user 'x'@'y'")
        freetds = Exception((18456, b"Login failed for user 'x'.DB-Lib error message 20018, severity 14:\n"
                                    b"General SQL Server error"))
        self.assertEqual(error_message(freetds), "Login failed for user 'x'. General SQL Server error")


class FakeApi:
    base_url = "http://server"
    user_id = 7

    def __init__(self, sign_in_passwords=None):
        self.created = []
        self.updated = []
        self.reported = []
        self.credentials = {"dbUsername": "dbm_u7_c5", "dbPassword": "guest-pw-1"}
        self.sign_in_passwords = sign_in_passwords or {}

    def take_sign_in_passwords(self):
        passwords, self.sign_in_passwords = self.sign_in_passwords, {}
        return passwords

    def create_connection(self, details):
        self.created.append(details)
        return {**details, "id": 1, "ownerUserId": self.user_id}

    def update_connection(self, connection_id, details):
        self.updated.append((connection_id, details))
        return {**details, "id": connection_id, "ownerUserId": self.user_id}

    def guest_credentials(self, connection_id):
        return dict(self.credentials)

    def record_audit(self, connection_id, action, detail, success):
        self.reported.append((connection_id, action, success))


OWN = {"id": 1, "ownerUserId": 7, "host": "192.168.1.20", "port": 5432, "dbName": "shop", "dbUsername": "ann",
       "dbType": "POSTGRESQL"}
SHARED = {**OWN, "id": 5, "ownerUserId": 9, "dbName": "crm"}


def refused(connection, user, password):
    raise DatabaseError("Could not connect: password authentication failed for user", unreachable=True,
                        refused_login=True)


class SigningInTest(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.passwords = MemoryPasswords()
        self.asked = []
        self.client = DatabaseClient(self.api, self.passwords, ask_password=self._ask)
        self.answer = "typed-pw"

    def _ask(self, connection, problem):
        self.asked.append(problem)
        return self.answer

    def test_the_passwords_from_the_sign_in_open_the_owners_databases(self):
        passwords = MemoryPasswords()
        api = FakeApi(sign_in_passwords={1: "from-sign-in"})
        client = DatabaseClient(api, passwords, ask_password=self._ask)
        with mock.patch("dbmanager.db.client.drivers.connect") as connect:
            client._open(OWN)
        self.assertEqual(connect.call_args[0][1:], ("ann", "from-sign-in"))
        self.assertEqual(self.asked, [], "nobody is asked")
        self.assertEqual(api.updated, [], "nothing new to save")
        self.assertEqual(api.take_sign_in_passwords(), {}, "taken once, not left with the API client")

    def test_a_new_databases_password_goes_to_the_server_and_is_kept_for_the_session(self):
        self.client.create_connection({**OWN, "dbPassword": "secret"})
        self.assertEqual(self.api.created[0]["dbPassword"], "secret")
        self.assertEqual(self.passwords.get("http://server#connection-1"), "secret")

    def test_the_owner_is_asked_for_a_password_once_and_again_when_it_is_refused(self):
        with mock.patch("dbmanager.db.client.drivers.connect") as connect:
            self.client._open(OWN)
            self.assertEqual(self.asked, [None])
            self.assertEqual(connect.call_args[0][1:], ("ann", "typed-pw"))
            self.client._open(OWN)
            self.assertEqual(len(self.asked), 1, "remembered")

            connect.side_effect = [DatabaseError("x", unreachable=True, refused_login=True), mock.DEFAULT]
            self.answer = "new-pw"
            self.client._open(OWN)
        self.assertEqual(len(self.asked), 2)
        self.assertIn("x", self.asked[1])
        self.assertEqual(self.passwords.get("http://server#connection-1"), "new-pw")
        self.assertEqual([details["dbPassword"] for _, details in self.api.updated], ["typed-pw", "new-pw"],
                         "a password that worked is saved for the next sign-in")
        self.assertEqual(self.api.updated[-1][1]["host"], "192.168.1.20", "with the rest of the connection")

    def test_giving_no_password_opens_nothing(self):
        self.answer = None
        with mock.patch("dbmanager.db.client.drivers.connect") as connect, self.assertRaises(DatabaseError) as raised:
            self.client._open(OWN)
        connect.assert_not_called()
        self.assertTrue(raised.exception.cancelled)

    def test_a_guest_signs_in_with_their_own_login_and_collects_a_new_one_when_refused(self):
        with mock.patch("dbmanager.db.client.drivers.connect") as connect:
            self.client._open(SHARED)
            self.assertEqual(connect.call_args[0][1:], ("dbm_u7_c5", "guest-pw-1"))
            self.api.credentials["dbPassword"] = "guest-pw-2"
            connect.side_effect = [DatabaseError("refused", unreachable=True, refused_login=True), mock.DEFAULT]
            self.client._open(SHARED)
            self.assertEqual(connect.call_args[0][1:], ("dbm_u7_c5", "guest-pw-2"))
        self.assertEqual(self.asked, [], "a guest is never asked for the owner's password")

    def test_a_guest_login_that_stays_refused_says_who_can_fix_it(self):
        with mock.patch("dbmanager.db.client.drivers.connect", side_effect=refused), \
                self.assertRaises(DatabaseError) as raised:
            self.client._open(SHARED)
        self.assertIn("owner's app", str(raised.exception))

    def test_what_ran_is_reported_to_the_audit_log(self):
        with mock.patch("dbmanager.db.client.drivers.connect"), \
                mock.patch("dbmanager.db.client.run_statements", return_value=(
                    [{"statementType": "UPDATE", "updateCount": 1, "columns": [], "rows": []}], 4)):
            self.client.passwords.set("http://server#connection-1", "pw")
            result = self.client.run_script(OWN, "UPDATE t SET x = 1;")
        self.assertEqual(result["durationMs"], 4)
        self.assertEqual(self.api.reported, [(1, "QUERY_UPDATE", True)])


if __name__ == "__main__":
    unittest.main()
