import json
import socket
import threading
import unittest
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dbmanager.api.client import ApiClient, ApiError


class FakeBackend(BaseHTTPRequestHandler):
    """Answers by path; records what it was sent."""
    requests = []

    def log_message(self, *args):
        pass

    def _reply(self, status, body=None, raw=None):
        payload = raw if raw is not None else (json.dumps(body).encode() if body is not None else b"")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        FakeBackend.requests.append((self.command, self.path, self.headers.get("Authorization"), body))
        if self.path == "/api/auth/login":
            if body["password"] == "right":
                self._reply(200, {"token": "t0k3n", "userId": 7, "username": "ann", "roles": ["USER"]})
            else:
                self._reply(401, {"status": 401, "message": "Invalid username or password"})
        elif self.path == "/api/auth/register":
            self._reply(400, {"status": 400, "message": "Validation failed",
                              "fieldErrors": {"password": "size must be between 8 and 100"}})
        elif self.path == "/api/db-connections/1/query":
            self._reply(200, raw=b'{"columns":["price"],"rows":[[19.99]],"truncated":false}')
        elif self.path == "/api/db-connections/2/query":
            self._reply(200, raw=b"<html>proxy error</html>")
        elif self.path == "/api/db-connections/3/query":
            self.connection.shutdown(socket.SHUT_RDWR)  # the server goes away mid-request
        elif self.path == "/api/db-connections/test":
            self._reply(502, {"status": 502, "message": "Could not connect to POSTGRESQL localhost:5439/db"})
        elif self.path == "/api/db-connections/5/test":
            self._reply(200, {"message": "Connected to PostgreSQL 16.4 in 9 ms"})
        elif self.path == "/api/db-connections":
            self._reply(401, {"status": 401, "message": "Full authentication is required"})
        elif self.path == "/api/auth/logout":
            self._reply(200, {"message": "Logged out"})
        elif self.path == "/api/users/7" and self.command == "GET":
            self._reply(200, {"id": 7, "username": "ann", "email": None})
        elif self.path == "/api/users/7" and self.command == "DELETE":
            self._reply(204)
        elif self.path == "/api/premium-users":
            self._reply(200, [])
        elif self.path == "/api/invitations":
            self._reply(201, {"id": 5, "status": "PENDING", **body})
        elif self.path == "/api/invitations/5":
            self._reply(200, {"id": 5, **body})
        else:
            self._reply(404, {"status": 404, "message": "No such thing"})

    do_GET = do_POST = do_PUT = do_DELETE = _handle


class ApiClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeBackend)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeBackend.requests.clear()
        self.api = ApiClient(self.url, timeout=5)

    def test_login_stores_the_session_and_sends_the_token_afterwards(self):
        self.api.login("ann", "right")
        self.assertEqual((self.api.token, self.api.user_id, self.api.username), ("t0k3n", 7, "ann"))
        self.api.logout()
        self.assertEqual(FakeBackend.requests[-1][2], "Bearer t0k3n")
        self.assertFalse(self.api.signed_in)

    def test_a_failed_login_shows_the_server_message_not_session_expired(self):
        with self.assertRaises(ApiError) as caught:
            self.api.login("ann", "wrong")
        self.assertEqual((caught.exception.status, str(caught.exception)), (401, "Invalid username or password"))

    def test_401_with_a_token_means_the_session_expired(self):
        self.api.login("ann", "right")
        with self.assertRaises(ApiError) as caught:
            self.api.list_connections()
        self.assertIn("session has expired", str(caught.exception))

    def test_field_errors_are_listed(self):
        with self.assertRaises(ApiError) as caught:
            self.api.register("ann", "a@b.c", "short")
        self.assertEqual(caught.exception.field_errors, {"password": "size must be between 8 and 100"})
        self.assertIn("• password: size must be between 8 and 100", str(caught.exception))

    def test_registering_without_an_email_leaves_it_out(self):
        with self.assertRaises(ApiError):  # the fake turns every registration down
            self.api.register("ann", "", "password123")
        self.assertEqual(FakeBackend.requests[-1][3], {"username": "ann", "password": "password123"})

    def test_deleting_the_account_sends_the_password_and_ends_the_session(self):
        self.api.login("ann", "right")
        self.assertIsNone(self.api.account()["email"])
        self.api.delete_account("right")
        self.assertEqual(FakeBackend.requests[-1][:2] + FakeBackend.requests[-1][3:],
                         ("DELETE", "/api/users/7", {"password": "right"}))
        self.assertEqual(FakeBackend.requests[-1][2], "Bearer t0k3n")
        self.assertFalse(self.api.signed_in)

    def test_no_premium_link_means_not_premium(self):
        self.assertIsNone(self.api.premium_status())

    def test_an_invitation_names_the_user_and_an_answer_is_only_the_status(self):
        self.api.invite(4, "bob", 2)
        self.api.set_invitation_status(5, "ACCEPTED")
        self.assertEqual([request[:2] + request[3:] for request in FakeBackend.requests], [
            ("POST", "/api/invitations", {"toUsername": "bob", "dbConnectionId": 4, "additionalRoleId": 2}),
            ("PUT", "/api/invitations/5", {"status": "ACCEPTED"}),
        ])

    def test_a_saved_database_is_tested_as_saved_unless_details_are_given(self):
        self.assertEqual(self.api.test_connection(5), "Connected to PostgreSQL 16.4 in 9 ms")
        with self.assertRaises(ApiError) as caught:
            self.api.test_new_connection({"host": "localhost", "port": 5439})
        self.assertEqual(caught.exception.status, 502)
        self.assertEqual([request[:2] + request[3:] for request in FakeBackend.requests], [
            ("POST", "/api/db-connections/5/test", None),
            ("POST", "/api/db-connections/test", {"host": "localhost", "port": 5439}),
        ])

    def test_numbers_with_a_fraction_stay_exact(self):
        result = self.api.run_query(1, "SELECT price FROM items")
        self.assertEqual(result["rows"], [[Decimal("19.99")]])

    def test_an_answer_that_is_not_json_is_an_api_error(self):
        with self.assertRaises(ApiError) as caught:
            self.api.run_query(2, "SELECT 1")
        self.assertEqual(caught.exception.status, 0)

    def test_a_dropped_connection_is_an_api_error(self):
        with self.assertRaises(ApiError) as caught:
            self.api.run_query(3, "SELECT 1")
        self.assertEqual(caught.exception.status, 0)

    def test_an_unreachable_server_is_an_api_error(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            free_port = probe.getsockname()[1]
        with self.assertRaises(ApiError) as caught:
            ApiClient(f"http://127.0.0.1:{free_port}", timeout=2).list_connections()
        self.assertIn("Cannot reach the server", str(caught.exception))

    def test_a_malformed_server_address_is_an_api_error(self):
        with self.assertRaises(ApiError) as caught:
            ApiClient("localhost:8080").list_connections()
        self.assertIn("not a valid server address", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
