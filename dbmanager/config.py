"""
Settings shared across the app.

The server address comes from the DB_MANAGER_API_URL environment variable
(default http://localhost:8080). The server keeps accounts and sharing; the user's
databases are reached from this computer (see dbmanager.db).
"""

import os
from pathlib import Path

API_URL = os.environ.get("DB_MANAGER_API_URL", "http://localhost:8080").rstrip("/")
API_TIMEOUT_SECONDS = 60
# Logging out happens while a window closes, so it must not hang on an unreachable server
LOGOUT_TIMEOUT_SECONDS = 5

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
APP_ICON_PATH = RESOURCES_DIR / "sql_query_builder_icon.svg"

# QSettings location (kept as before so a remembered username survives the update)
SETTINGS_ORGANIZATION = "DatabaseManagement"
SETTINGS_APPLICATION = "Coursework"

# Rows shown in a table's "Data Records" panel
TABLE_PREVIEW_ROWS = 200

# Talking to the user's databases directly
DB_CONNECT_TIMEOUT_SECONDS = 10
DB_STATEMENT_TIMEOUT_SECONDS = 30
QUERY_MAX_ROWS = 500   # the most rows one statement returns; the result says when there were more
