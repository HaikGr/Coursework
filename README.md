# Database Management - desktop client

A PyQt6 desktop app for the Database Management backend (Spring Boot, `database-management`).
Register or sign in, connect your databases, see their tables as an ER diagram, edit schema and rows,
and build queries visually. Every edit becomes SQL in the side panel; **Run Query** sends it to the backend,
which runs it against your database.

## Run

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python main.py            # or: .venv/bin/python -m dbmanager
```

The backend must be running. Its address comes from `DB_MANAGER_API_URL` (default `http://localhost:8080`).

## Project layout

```
main.py                     entry point
dbmanager/
  app.py                    QApplication set-up, first window
  config.py                 server address, timeouts, paths, preview size
  api/                      the backend: ApiClient / ApiError, database types
  sql/                      identifier quoting and SQL generation per dialect (no Qt)
  model/                    editor state without widgets (no Qt):
    table_state.py            what changed in one table, and its CREATE/ALTER/INSERT/UPDATE/DELETE
    change_script.py          all edits of a database as one script, in an order the database accepts
  ui/
    common/                 icons, message boxes, busy cursor, animated background, window transitions
    auth/                   sign in, sign up, forgot password (share auth/base.py)
    dashboard/              main window, top bar, aggregate toolbar, database sidebar
    diagram/                ER canvas, table cards, field rows, WHERE popup
    table_editor/           schema + rows page of one table
    query/                  SQL panel, highlighter, field tags, results dialog
    dialogs/                database connection, new table, new field, rename
  resources/                app icon
tests/                      unit and offscreen widget tests, plus an end-to-end smoke test
```

`sql/` and `model/` do not import Qt, so the logic that decides what SQL to run is tested without a UI.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -t .
```

Widget tests run offscreen (`QT_QPA_PLATFORM=offscreen` is set for you). No extra packages are needed.

`tests/e2e_smoke.py` drives the real widgets against a running backend and an empty PostgreSQL
database (it creates, edits and drops its own tables). See the docstring at the top of the file for the variables.

## Using it

- **Diagram**: drag a PK field onto an FK field of another table to link them (a JOIN for queries, a
  FOREIGN KEY when saved). Right-click a field to add it to the query; hover it to type a WHERE condition.
  Pick an aggregate (SUM, AVG, ...) in the toolbar before adding a field to wrap it.
- **Tables**: click a table in the sidebar. Double-click a cell to edit it, type `NULL` for no value,
  select rows and press Delete to remove them. Right-click a field in the schema to rename or delete it.
  Views are shown read-only.
- **Sidebar**: `+ Add Table` designs a new table, Delete on a table marks it to be dropped,
  double-click a database to edit its connection, Delete on it removes the saved connection.
- Nothing reaches the database until **Run Query**. The script runs in one transaction, then the
  database is read back.
- Changed your mind? **Discard** next to "unsaved changes" in the SQL panel throws away every unsaved
  change to the database; **Discard** on a table page does it for that table only. **Clear** only empties
  the query built from the diagram.
