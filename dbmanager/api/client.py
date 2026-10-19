"""
API Client - talks to the Database Management backend (Spring Boot REST API).

Uses only the standard library, so the app needs nothing beyond PyQt6.
"""

import http.client
import json
import urllib.error
import urllib.request
from decimal import Decimal

from dbmanager.config import API_TIMEOUT_SECONDS, API_URL, LOGOUT_TIMEOUT_SECONDS


class ApiError(Exception):
    """A failed API call. str(error) is a message ready to show to the user.
    status is the HTTP status, or 0 when the server could not be reached at all."""

    def __init__(self, status, message, field_errors=None):
        self.status = status
        self.field_errors = field_errors if isinstance(field_errors, dict) else {}
        if self.field_errors:
            details = "\n".join(f"• {field}: {error}" for field, error in self.field_errors.items())
            message = f"{message}\n{details}"
        super().__init__(message)


class ApiClient:
    """Holds the session (JWT) of the signed-in user and wraps every backend call."""

    def __init__(self, base_url=API_URL, timeout=API_TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = None
        self.user_id = None
        self.username = None
        self.roles = []

    @property
    def signed_in(self):
        return self.token is not None

    # ---------------- Auth ----------------
    def login(self, username_or_email, password):
        data = self._request("POST", "/api/auth/login",
                             {"username": username_or_email, "password": password})
        self._store_session(data)
        return data

    def register(self, username, email, password):
        """email is optional (None or empty): an account needs one only to become premium."""
        body = {"username": username, "password": password}
        if email:
            body["email"] = email
        data = self._request("POST", "/api/auth/register", body)
        self._store_session(data)
        return data

    def logout(self):
        """Revoke the token on the server; the local session is dropped either way."""
        if not self.token:
            return
        try:
            self._request("POST", "/api/auth/logout", timeout=LOGOUT_TIMEOUT_SECONDS)
        finally:
            self._clear_session()

    # ---------------- Account ----------------
    def account(self):
        """The signed-in account: {"id", "username", "email" (None when registered without one), ...}"""
        return self._request("GET", f"/api/users/{self.user_id}")

    def delete_account(self, password):
        """Delete the signed-in account for good (the password is asked again). The session ends with it."""
        self._request("DELETE", f"/api/users/{self.user_id}", {"password": password})
        self._clear_session()

    # ---------------- Databases ----------------
    def list_connections(self):
        return self._request("GET", "/api/db-connections") or []

    def create_connection(self, details):
        return self._request("POST", "/api/db-connections", details)

    def update_connection(self, connection_id, details):
        return self._request("PUT", f"/api/db-connections/{connection_id}", details)

    def delete_connection(self, connection_id):
        self._request("DELETE", f"/api/db-connections/{connection_id}")

    def test_new_connection(self, details):
        """Can the server reach a database that is not saved yet? Returns what answered; a database
        it cannot reach raises ApiError with status 502."""
        return (self._request("POST", "/api/db-connections/test", details) or {}).get("message", "")

    def test_connection(self, connection_id, details=None):
        """The same for a saved database (owner only): as saved, or with the edited details - leave
        dbPassword out of them to use the stored password."""
        data = self._request("POST", f"/api/db-connections/{connection_id}/test", details)
        return (data or {}).get("message", "")

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

    # ---------------- Premium ----------------
    def premium_status(self):
        """The premium link of the signed-in user ({"connectedEmail", "activatedAt", ...}), or None.
        Asked every time: an upgrade made after signing in is not in the token's roles."""
        links = self._request("GET", "/api/premium-users") or []
        return links[0] if links else None

    def request_premium_code(self, email):
        """Step 1 of 2: the server mails a six-digit code to this address. Returns its message."""
        data = self._request("POST", "/api/premium-users/request-code", {"connectedEmail": email})
        return (data or {}).get("message", "")

    def confirm_premium(self, email, code):
        """Step 2 of 2: the code that came back makes the account premium."""
        return self._request("POST", "/api/premium-users/confirm", {"connectedEmail": email, "code": code})

    # ---------------- Sharing ----------------
    def list_permissions(self):
        """What an invitation can grant: [{"id", "name": "SELECT_ROLE", "description"}, ...]"""
        return self._request("GET", "/api/additional-roles") or []

    def list_invitations(self):
        """Invitations the signed-in user sent or received, newest first."""
        return self._request("GET", "/api/invitations") or []

    def invite(self, connection_id, username, permission_id):
        """Offer one permission on one of your databases to another user (premium only)."""
        return self._request("POST", "/api/invitations", {
            "toUsername": username, "dbConnectionId": connection_id, "additionalRoleId": permission_id})

    def set_invitation_status(self, invitation_id, status):
        """ACCEPTED or DECLINED by the recipient, REVOKED by the sender."""
        return self._request("PUT", f"/api/invitations/{invitation_id}", {"status": status})

    # ---------------- Plumbing ----------------
    def _store_session(self, data):
        if not isinstance(data, dict) or not data.get("token"):
            raise ApiError(0, "The server did not return a session token.")
        self.token = data["token"]
        self.user_id = data.get("userId")
        self.username = data.get("username")
        self.roles = data.get("roles") or []

    def _clear_session(self):
        self.token = None
        self.user_id = None
        self.username = None
        self.roles = []

    def _request(self, method, path, body=None, timeout=None):
        if not self.base_url.startswith(("http://", "https://")):
            raise ApiError(0, f"'{self.base_url}' is not a valid server address - it must start with "
                              "http:// or https:// (check DB_MANAGER_API_URL).")
        data = json.dumps(body, default=str).encode("utf-8") if body is not None else None
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")

        # HTTPError is a URLError, and both (like TimeoutError) are OSErrors: most specific first
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise self._to_api_error(error, sent_token=self.token is not None) from None
        except urllib.error.URLError as error:
            raise ApiError(0, f"Cannot reach the server at {self.base_url}.\n"
                              f"Is the backend running? ({error.reason})") from None
        except TimeoutError:
            raise ApiError(0, "The server took too long to answer.") from None
        except (OSError, http.client.HTTPException) as error:
            # e.g. the connection was reset because the server restarted mid-request
            raise ApiError(0, f"The connection to the server was lost ({error}).") from None

        if not raw:
            return None
        try:
            # Decimal keeps money/numeric columns exact instead of turning them into floats
            return json.loads(raw, parse_float=Decimal)
        except ValueError:
            raise ApiError(0, "The server sent an answer that is not JSON.") from None

    @staticmethod
    def _to_api_error(error, sent_token):
        try:
            payload = json.loads(error.read() or b"{}")
        except (ValueError, OSError, http.client.HTTPException):
            payload = {}
        finally:
            error.close()
        if not isinstance(payload, dict):
            payload = {}
        message = payload.get("message") or error.reason or f"HTTP {error.code}"
        if error.code == 401 and sent_token:
            message = "Your session has expired. Please sign in again."
        return ApiError(error.code, message, payload.get("fieldErrors"))
