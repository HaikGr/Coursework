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
                self._reply(200, {"token": "t0k3n", "userId": 7, "username": "ann", "roles": ["USER"],
                                  "connections": [{"id": 3, "dbName": "shop", "dbPassword": "db-secret"}]})
            else:
                self._reply(401, {"status": 401, "message": "Invalid username or password"})
        elif self.path == "/api/auth/register":
            self._reply(400, {"status": 400, "message": "Validation failed",
                              "fieldErrors": {"password": "size must be between 8 and 100"}})
        elif self.path == "/api/auth/password-reset/request":
            self._reply(200, {"message": f"If an account uses {body['email']}, a code was sent there."})
        elif self.path == "/api/auth/password-reset/confirm":
            if body["code"] == "123456":
                self._reply(200, {"username": "ann", "message": "Your password was changed"})
            else:
                self._reply(400, {"status": 400, "message": "That code is not correct — 4 attempt(s) left"})
        elif self.path == "/api/premium-users/confirm":
            self._reply(200, raw=b'{"connectedEmail":"a@b.c","score":19.99}')
        elif self.path == "/api/db-connections/2/credentials":
            self._reply(200, raw=b"<html>proxy error</html>")
        elif self.path == "/api/db-connections/3/credentials":
            self.connection.shutdown(socket.SHUT_RDWR)  # the server goes away mid-request
        elif self.path == "/api/db-connections/5/credentials":
            self._reply(200, {"dbConnectionId": 5, "dbUsername": "dbm_u7_c5", "dbPassword": "guest-pw"})
        elif self.path.startswith("/api/db-connections/5/guest-accounts"):
            self._reply(204 if self.command == "DELETE" else 200, None if self.command == "DELETE" else [])
        elif self.path == "/api/audit-logs":
            self._reply(201, {"id": 1, **body})
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

    def test_the_sign_in_hands_over_the_database_passwords_once(self):
        self.api.login("ann", "right")
        self.assertEqual(self.api.take_sign_in_passwords(), {3: "db-secret"})
        self.assertEqual(self.api.take_sign_in_passwords(), {})

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

    def test_a_forgotten_password_is_reset_without_a_session(self):
        self.assertIn("a code was sent", self.api.request_password_reset("ann@example.com"))
        self.assertEqual(self.api.reset_password("ann@example.com", "123456", "brand-new-pw"), "ann")
        self.assertEqual([request[1:] for request in FakeBackend.requests], [
            ("/api/auth/password-reset/request", None, {"email": "ann@example.com"}),
            ("/api/auth/password-reset/confirm", None,
             {"email": "ann@example.com", "code": "123456", "newPassword": "brand-new-pw"})])
        with self.assertRaises(ApiError) as caught:
            self.api.reset_password("ann@example.com", "000000", "brand-new-pw")
        self.assertEqual((caught.exception.status, str(caught.exception)),
                         (400, "That code is not correct — 4 attempt(s) left"))

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

    def test_guest_logins_and_audit_entries_go_where_the_server_expects_them(self):
        self.assertEqual(self.api.guest_credentials(5)["dbUsername"], "dbm_u7_c5")
        self.api.list_guest_accounts(5)
        self.api.save_guest_account(5, 8, "dbm_u8_c5", "Gx7rT2pQ9vLm4sWz8kYb")
        self.api.delete_guest_account(5, 8)
        self.api.record_audit(5, "QUERY_SELECT", "1 row(s) returned: SELECT 1", True)
        self.assertEqual([request[:2] + request[3:] for request in FakeBackend.requests], [
            ("GET", "/api/db-connections/5/credentials", None),
            ("GET", "/api/db-connections/5/guest-accounts", None),
            ("PUT", "/api/db-connections/5/guest-accounts/8", {"dbUsername": "dbm_u8_c5",
                                                               "dbPassword": "Gx7rT2pQ9vLm4sWz8kYb"}),
            ("DELETE", "/api/db-connections/5/guest-accounts/8", None),
            ("POST", "/api/audit-logs", {"dbConnectionId": 5, "action": "QUERY_SELECT",
                                         "detail": "1 row(s) returned: SELECT 1", "success": True}),
        ])

    def test_numbers_with_a_fraction_stay_exact(self):
        self.assertEqual(self.api.confirm_premium("a@b.c", "123456")["score"], Decimal("19.99"))

    def test_an_answer_that_is_not_json_is_an_api_error(self):
        with self.assertRaises(ApiError) as caught:
            self.api.guest_credentials(2)
        self.assertEqual(caught.exception.status, 0)

    def test_a_dropped_connection_is_an_api_error(self):
        with self.assertRaises(ApiError) as caught:
            self.api.guest_credentials(3)
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
