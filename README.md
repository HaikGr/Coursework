# Database Management - desktop client

A PyQt6 desktop app for the Database Management backend (Spring Boot, `database-management`).
Register or sign in, connect your databases, see their tables as an ER diagram, edit schema and rows,
build queries visually, and share a database with other users. Every edit becomes SQL in the side panel;
**Run Query** runs it on your database.

## How it reaches your databases

Your databases run on your own computer or local network, and the backend runs on a server somewhere
else, which cannot reach them. So **this app connects to your databases itself**, and the backend only
keeps accounts, where each database is, and who may use it.

```
 this computer ──HTTP──▶ backend          accounts, database list, invitations, guest logins, audit log
      │
      └──── directly ──▶ your database    tables, rows, queries (PostgreSQL, MySQL, MariaDB, SQL Server)
```

- **Your passwords come with your sign-in.** The backend stores each database's password encrypted and
  hands your own databases' passwords to the app when you sign in - nowhere else - so any computer you
  sign in on can open them. The app keeps them in memory until you sign out. A password you type in the
  app (a new database, or one the database refused) is saved back to the backend.
- **Sharing gives the other person a login of their own** in your database, made by your app with
  exactly the permissions you tick (SELECT, INSERT, UPDATE, DELETE), so the database itself refuses
  anything else - whatever tool they connect with. Your password is never handed out. Their app collects
  that login from the backend once they accept, and connects to your database directly, so they must be
  on a network that reaches it. Your app keeps the logins in line with the invitations whenever you open
  the database or change a share, and drops them when you revoke or delete.
- **What runs is reported** to the backend's audit log, so the owner's trail shows what guests ran.

## Run

Python 3.10 or newer, on Linux, macOS or Windows:

```bash
# Linux / macOS
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python main.py            # or: .venv/bin/python -m dbmanager
```

```powershell
# Windows (PowerShell or cmd)
py -m venv .venv; .venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

The backend must be running. Its address comes from `DB_MANAGER_API_URL` (default `http://localhost:8080`;
PowerShell: `$env:DB_MANAGER_API_URL="http://server:8080"`).
`requirements.txt` brings a driver for each database type (psycopg, PyMySQL, pymssql). Drivers are loaded
only when a database of their type is opened, so if one cannot be installed on your machine (pymssql on an
older Mac, psycopg's binary build on Windows on ARM), install the others alone - `pip install PyQt6
"psycopg[binary]" "PyMySQL[rsa]"` - and the app says which driver is missing when it needs it.

The app looks the same on every system: it draws its controls with Qt's Fusion style, in its own light
colours whatever the system theme. Shortcuts follow the system: **Ctrl+Enter** runs the query (**⌘↩** on a
Mac), and a Mac's delete key (Backspace) deletes like Delete.

## Project layout

```
main.py                     entry point
dbmanager/
  app.py                    QApplication set-up, first window
  config.py                 server address, timeouts, paths, preview size
  api/                      the backend: ApiClient / ApiError, database types
  db/                       your databases, reached from this computer (no Qt):
    client.py                 DatabaseClient: who signs in how, runs queries, keeps guest logins in line
    drivers.py                connecting per database type; DatabaseError
    script.py                 splitting a script into statements
    schema.py                 reading tables, columns (with their exact types), keys, and the constraints
                              and indexes a drop has to deal with first
    guests.py                 the logins made for the people a database is shared with
    passwords.py              the passwords of this session
  sql/                      identifier quoting and SQL generation per dialect (no Qt)
  model/                    editor state without widgets (no Qt):
    table_state.py            what changed in one table: schema, rows, then NOT NULL once rows are filled;
                              what the database would refuse (problems), checked before a run
    change_script.py          all edits of a database as one script, in an order the database accepts
                              (foreign keys in the way of a drop first)
    sharing.py                permissions, and invitations grouped per person and database
    query.py                  the query built on the diagram: columns, aggregates, sorts, filters, and its
                              SELECT per dialect (GROUP BY, HAVING, LIMIT/TOP and the JOINs written for you)
  ui/
    common/                 icons, message boxes, busy cursor, animated background, window transitions,
                            the dark dialog style, shared styles, an elided label, a wrapping layout,
                            how data grids size their columns, the value panel
    auth/                   sign in, sign up, forgot password (share auth/base.py)
    dashboard/              main window, top bar, query toolbar, database sidebar
    diagram/                ER canvas, table cards, field rows and their query menu
    table_editor/           schema + rows page of one table
    query/                  SQL panel, highlighter, column and filter tags, filter dialog, help, results
    dialogs/                database connection, new table, new field, rename, require a value,
                            delete account
    sharing/                premium upgrade, share a database, answer invitations
  resources/                app icon
tests/                      unit and offscreen widget tests, plus an end-to-end smoke test
```

`sql/`, `model/` and `db/` do not import Qt, so the logic that decides what SQL to run is tested without a UI.

Style sheets always name what they style (`QLabel { ... }`, `QWidget { ... }`). One without a selector
styles the tooltips of every widget inside it too, and a tooltip is a window of its own with nothing behind
it: a transparent background there is a black box, a dark one hides the tooltip's text. A `QWidget` selector
still reaches every widget inside, but no tooltip. Sizes follow from the content: a fixed size smaller than
a padded field cuts its text in half. `TooltipTest` and `TextRoomTest` check both on every screen.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -t .
```

Widget tests run offscreen (`QT_QPA_PLATFORM=offscreen` is set for you). No extra packages are needed.

`tests/e2e_smoke.py` drives the real widgets against a running backend and an empty PostgreSQL
database (it creates, edits and drops its own tables), and can share it with a second user. See the docstring
at the top of the file for the variables.

`tests/live_databases.py` runs the database layer against real PostgreSQL, MySQL, MariaDB and SQL Server
servers - queries, schema, guest logins held to their permissions by the database, and changes to
tables that have rows and keys (required fields, required values, drops that other tables point at). Throwaway servers:

```bash
docker run -d --rm --name pg -e POSTGRES_PASSWORD=pw -p 127.0.0.1:55432:5432 postgres:16
LIVE_POSTGRESQL=postgres:pw@127.0.0.1:55432/postgres .venv/bin/python -m unittest tests.live_databases -v
```

## Using it

- **Forgot password?** on the sign-in screen sends a six-digit code to the email address of your account
  (the one you sign in with, or your premium one) - while the server does not send email, the code is in
  its log. Type the code and a new password: the app signs you in, and every other session of the account
  ends. A new code can be asked for once a minute, a few times a day.
- **Diagram**: drag a primary key (PK) onto the field of another table that refers to it - or the other
  way round, or click one and then the other (Esc gives up), or right-click a field → **Link to ▸ table ▸
  field**. The field becomes a foreign key of that key at the next Run, and queries join the two tables on it.
  The field it would go to lights up while you point at it, and a notice says what happened - or why not
  (one of the two must be a key, both must hold the same kind of values, a field points at one key). A link
  drawn but not saved yet can be taken back from the field's right-click menu. Each field shows its type;
  **PK**/**FK** badges fill in once a link is drawn to them. In a database shared with you the structure is
  the owner's: join in the query panel instead.
- **Building a query** (**? Help** in the toolbar says the same):
  - *Columns* - click the circle at the end of a field (it turns into a green tick), or right-click the
    field and choose **Add to query**. Fields of several tables are joined along the links.
  - *Joins* - **+ Join** in the query panel joins two tables on any two fields of the same kind, and can keep
    the rows of the first table that match nothing (LEFT JOIN). It is for this query only: nothing changes
    in the database, so it works in a shared database too, and it wins over a link between the same tables.
    It is drawn dashed on the diagram and listed under JOINS (click it to change it). A table nothing joins
    to the others is paired with every row of them (CROSS JOIN): the panel warns, with a **Join …** button
    that suggests the likely fields (orders.customer_id with customers.id).
  - *Summarize* - select a column in the query panel (click it), then **SUM**, **AVG**, **COUNT**,
    **COUNT UNIQUE**, **MIN** or **MAX** in the toolbar; the lit button is the one the column uses, and
    clicking it again turns it off. The pill on the left of each column does the same. SUM and AVG are
    offered for numbers only. Every column you do not summarize becomes a group: the panel marks it
    **GROUP** and the GROUP BY is written for you. Summaries get readable names (`sum_total`).
  - *Filter* - right-click a field and choose **Add filter…**: pick how to compare (equals, greater than,
    between, is one of, contains, starts with, is empty, ... or custom SQL) and type the value as it is,
    without quotes - the dialog quotes it for the column's type, refuses text for a number column, and
    shows the SQL it will add. A filter on a summarized column can test each group (HAVING) instead of each
    row. Filters are listed in the panel (click one to change it) and marked with a funnel on the diagram;
    **Match all / Match any** joins them with AND or OR. Filtering by a field does not add it to the
    columns; with no columns, every column is shown (`SELECT *`).
  - *Sort and limit* - the arrow on a column sorts by it (smallest first, largest first, off; numbered when
    several sort). **Limit** keeps the first rows (LIMIT, or TOP on SQL Server), **Distinct** drops repeated
    rows, **Count rows** adds how many rows each group has.
  - The query stays when the diagram is drawn again after a Run; a column or table the Run dropped leaves
    it. The SQL can be edited by hand before it runs: it is only written over when the query changes.
- **Tables**: click a table in the sidebar. Double-click a cell to edit it, type `NULL` for no value,
  select rows and press Delete (Backspace on a Mac) to remove them. A value the column's type cannot hold
  (text in a number field) is not taken, and the page says why. Views are shown read-only; so is the
  structure of a database shared with you (its rows are yours to change as far as the share allows).
  - *Wide tables and long values*: each column is as wide as its name and values, up to a limit; drag a
    column's edge to change it. When the fields do not fit, the rows scroll sideways (Shift + the wheel
    scrolls too). A value cut short ends in …, and its tooltip shows the whole of it. Clicking a field in
    the schema scrolls the rows to it.
  - *Value panel*: **⊟ Value** (or Shift+Enter) opens it under the rows. It shows the whole value of the
    selected cell on all its lines, with its length, and follows the selection. What you type there goes
    into the cell as you type. **Set NULL** empties the cell, **Copy** copies the value and **Wrap** wraps
    long lines; drag its top edge for more room. It stays open from table to table. A value of several
    lines opens there on a double-click, since a cell edits one line. A value longer than the 10,000
    characters read of it cannot be changed (saving it would cut it). Query results have the panel too,
    read-only.
- **Fields**: **⋮** next to a field (or a right-click on it) renames it, makes it required or optional, or
  deletes it; **+ Add Field** adds one, with an optional **default value**.
  - *A required (NOT NULL) field in a table that has rows*: the database refuses one the existing rows leave
    empty. Give it a default value - the rows already there get it, and so do new rows without one - or type
    a value in each row. Without a default the field is added allowing NULL, the rows get their values, and
    only then is it made NOT NULL, in the same run. A field added here gets **Default value…** in its ⋮ menu
    too.
  - *Requiring a value in a field that has empty rows* asks what those rows get (`UPDATE … WHERE … IS NULL`,
    then NOT NULL); values you type in the rows before you run are kept. **Allow empty values** undoes it.
  - Until every row has a value the page says which rows lack one, and **Run Query** runs nothing: MySQL
    and MariaDB save each ALTER at once, so a run that stopped halfway would leave the table half changed.
    When more rows exist than are shown, a default (or a value for the empty rows) is required.
  - On SQL Server and MySQL a field's NULL setting is changed by stating the whole column again; its exact
    type (with its length) and, on MySQL, its default, AUTO_INCREMENT, ON UPDATE, character set and comment
    are read from the database and kept.
- **Dropping**: **Drop table** on a table's page, **Drop table…** when you right-click it in the sidebar or
  its card's header on the diagram, or the Delete key. **Delete field…** is in the field's menu, here and on
  the diagram. Both happen at the next Run; **Keep table** takes a drop back. Foreign keys of other tables
  that point at what you drop are named before you confirm and dropped first (the fields and their values
  stay). On SQL Server the field's own default, check, unique and index constraints go first too, and on
  MySQL its own foreign key - each database refuses the drop otherwise.
- **Sidebar**: `+ Add Table` designs a new table (in a database you own), Delete on a table marks it to be
  dropped.
  **⋮** next to a database you own (or a right-click on it) edits its connection, shares it or deletes
  it - only the saved connection goes, and the logins made in it for the people you shared it
  with; nothing else in the database is touched. Double-click and the Delete key do the same as Edit and
  Delete.
- **Connection settings are tested** when you add or edit a database, and at sign-up: if this computer
  cannot reach it, you are asked whether to save it anyway (**Test** in the dialog checks without
  saving). Clicking a database you own that cannot be reached offers to fix its settings. If the database
  refuses the saved password, the app asks for it and saves the new one.
- Nothing reaches the database until **Run Query** (Ctrl+Enter). The script runs in one transaction, then
  the database is read back. Logging out or closing the window with changes that were never run asks first.
  A script typed by hand may use SQL Server's `GO` lines (each batch is sent whole, as in SQL Server
  Management Studio) or MySQL's `DELIMITER` lines, to create procedures and triggers whose bodies hold `;`.
- **Sharing**: **Share** next to a database you own invites another user by username, with the
  permissions you tick: SELECT (see the tables and rows), INSERT, UPDATE, DELETE. Changing the
  structure stays with the owner. The same dialog lists who has access and revokes it. Before you share:
  - the connection must use the database's **network address** (for example `192.168.1.20`), not
    `localhost` - on the other person's computer, `localhost` is theirs;
  - the database must accept connections from your network (PostgreSQL: `listen_addresses` and a
    `pg_hba.conf` line; MySQL/MariaDB: `bind-address`; and the firewall);
  - your database user must be allowed to create users and grant (`postgres`/`root`/`sa`, or PostgreSQL's
    `CREATEROLE`). If it is not, the share is taken back and the dialog says why.

  Sharing is
  premium: the first time, the app asks you to verify an email address (**Go Premium** in the top bar
  does the same) - a six-digit code is sent to it. If you registered with an email, it is filled in for
  you. The backend only emails codes once its mail settings are given (see its README); until then it
  writes them to its log, and the dialog says so.
- **Invitations** in the top bar shows what other users offered you; the count is how many wait for
  an answer. Accepting adds the database to your sidebar, marked *shared*; its tooltip says who shared
  it and what you may do, and opening it signs in with the login made for you. ⟳ re-checks both.
- An email is optional when you sign up: it lets you sign in with it, and premium offers it first.
- **Connected User ▾** in the top bar logs out or deletes your account. Deleting asks for your password
  and is final: your saved databases (and every share of them, whose logins are removed from the databases),
  the shares you received and premium go with it. Nothing else in the databases is touched.
- Changed your mind? **Discard** next to "unsaved changes" in the SQL panel throws away every unsaved
  change to the database; **Discard** on a table page does it for that table only. **Clear** only starts
  the query built from the diagram again (columns, filters and options).
