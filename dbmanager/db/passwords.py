"""The passwords of the user's own databases, for this session.

The server keeps them (encrypted) and hands them over when the user signs in; they are kept here, in
memory only, until sign-out. A password typed during the session (a new database, or one the database
refused) is saved back to the server by DatabaseClient, so the next sign-in knows it."""


class MemoryPasswords:
    """Passwords for this session only."""

    def __init__(self):
        self._values = {}

    def get(self, key):
        return self._values.get(key)

    def set(self, key, password):
        self._values[key] = password

    def delete(self, key):
        self._values.pop(key, None)

    def clear_session(self):
        self._values.clear()


_default = MemoryPasswords()


def default_passwords():
    """The one store the whole app shares, so a password typed at sign-up is known to the dashboard."""
    return _default
