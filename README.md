# Database Management - desktop client

A PyQt6 desktop app for the Database Management backend (Spring Boot, `database-management`).
Register or sign in, connect your databases, see their tables as an ER diagram, edit schema and rows,
build queries visually, and share a database with other users. Every edit becomes SQL in the side panel;
**Run Query** sends it to the backend, which runs it against your database.

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
    sharing.py                permissions, and invitations grouped per person and database
  ui/
    common/                 icons, message boxes, busy cursor, animated background, window transitions,
                            the dark dialog style
    auth/                   sign in, sign up, forgot password (share auth/base.py)
    dashboard/              main window, top bar, aggregate toolbar, database sidebar
    diagram/                ER canvas, table cards, field rows, WHERE popup
    table_editor/           schema + rows page of one table
    query/                  SQL panel, highlighter, field tags, results dialog
    dialogs/                database connection, new table, new field, rename, delete account
    sharing/                premium upgrade, share a database, answer invitations
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
- **Sidebar**: `+ Add Table` designs a new table, Delete on a table marks it to be dropped.
  **⋮** next to a database you own (or a right-click on it) edits its connection, tests it, shares it
  or deletes it - only the saved connection goes, the database itself is not touched. Double-click and
  the Delete key do the same as Edit and Delete.
- **Connection settings are tested** when you add or edit a database, and at sign-up: if the server
  cannot reach it, you are asked whether to save it anyway (**Test** in the dialog checks without
  saving). Clicking a database you own that cannot be reached offers to fix its settings.
- Nothing reaches the database until **Run Query**. The script runs in one transaction, then the
  database is read back.
- **Sharing**: **Share** next to a database you own invites another user by username, with the
  permissions you tick: SELECT (see the tables and rows), INSERT, UPDATE, DELETE. Changing the
  structure stays with the owner. The same dialog lists who has access and revokes it. Sharing is
  premium: the first time, the app asks you to verify an email address (**Go Premium** in the top bar
  does the same) - a six-digit code is sent to it. If you registered with an email, it is filled in for
  you. The backend only emails codes once its mail settings are given (see its README); until then it
  writes them to its log, and the dialog says so.
- **Invitations** in the top bar shows what other users offered you; the count is how many wait for
  an answer. Accepting adds the database to your sidebar, marked *shared*; its tooltip says who shared
  it and what you may do. ⟳ re-checks both.
- An email is optional when you sign up: it lets you sign in with it, and premium offers it first.
- **Connected User ▾** in the top bar logs out or deletes your account. Deleting asks for your password
  and is final: your saved databases (and every share of them), the shares you received and premium go
  with it. The databases themselves are not touched.
- Changed your mind? **Discard** next to "unsaved changes" in the SQL panel throws away every unsaved
  change to the database; **Discard** on a table page does it for that table only. **Clear** only empties
  the query built from the diagram.
