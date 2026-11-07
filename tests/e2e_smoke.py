"""
End-to-end smoke test: the real widgets against a running backend and a real PostgreSQL database, which
this computer connects to itself (the backend never does). Not part of the unit tests (it needs both
servers). Run it with:

    DB_MANAGER_API_URL=http://localhost:8080 \
    E2E_PG_HOST=localhost E2E_PG_PORT=5432 E2E_PG_DB=shop E2E_PG_USER=postgres E2E_PG_PASSWORD=... \
    python -m tests.e2e_smoke

It registers a fresh user, designs two related tables in the editor, fills, edits and drops them through
Run Query, and checks after every step what PostgreSQL really holds. Use an empty scratch database, and
a database user that may create users (postgres, or one with CREATEROLE).

It also changes tables that have rows (a required field, a required value) and drops a table another one
points at. With E2E_BACKEND_LOG naming the backend's log file (mail off, so the codes are written there), it
also shares the database with a second user through the Share dialog and checks that the database itself
holds that user to SELECT - for that, E2E_PG_HOST must be a network address, not localhost or 127.0.0.1
(a Docker container's own address will do: docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' pg).
"""

import os
import re
import time
from decimal import Decimal
import uuid
from unittest import mock

from tests import qt

from dbmanager.api import ApiClient, ApiError  # noqa: E402
from dbmanager.db import DatabaseClient, DatabaseError  # noqa: E402
from dbmanager.db.passwords import MemoryPasswords  # noqa: E402
from dbmanager.model.query import Filter  # noqa: E402
from dbmanager.ui.dashboard.dashboard_window import DashboardWindow  # noqa: E402
from dbmanager.ui.sharing.share_dialog import ShareDatabaseDialog  # noqa: E402

APP = qt.app()
API_URL = os.environ.get("DB_MANAGER_API_URL", "http://localhost:8080")


def wait_for_backend(api, seconds=90):
    deadline = time.time() + seconds
    while True:
        try:
            api.login("nobody", "nothing-at-all")
        except ApiError as error:
            if error.status:  # the server answered
                return
            if time.time() > deadline:
                raise
        time.sleep(1)


def check(condition, message):
    qt.raise_slot_errors()
    if not condition:
        raise AssertionError(message)
    print(f"  ok  {message}")


def links_of(diagram, *tables):
    return [link for link in diagram.export_links() if link[0] in tables and link[2] in tables]


def rows(db, connection, sql):
    return db.run_query(connection, sql)["rows"]


def run(builder):
    """Click Run Query; the results dialog is replaced so the script does not block on it."""
    with mock.patch("dbmanager.ui.query.query_builder.QueryResultsWindow"), \
            mock.patch("dbmanager.ui.query.query_builder.show_styled_message") as message:
        sql = builder.sql_editor.toPlainText()
        builder.run_query()
        if message.called:
            raise AssertionError(f"Run failed: {message.call_args[0][2]}\n--- script ---\n{sql}")
    qt.raise_slot_errors()


def main():
    api = ApiClient(API_URL, timeout=30)
    wait_for_backend(api)
    suffix = uuid.uuid4().hex[:8]
    api.register(f"e2e_{suffix}", f"e2e_{suffix}@example.com", "e2e-password")
    db = DatabaseClient(api, MemoryPasswords())  # a store of its own, not the app's shared one
    created = db.create_connection({
        "host": os.environ.get("E2E_PG_HOST", "localhost"),
        "port": int(os.environ.get("E2E_PG_PORT", "5432")),
        "dbName": os.environ.get("E2E_PG_DB", "shop"),
        "dbUsername": os.environ.get("E2E_PG_USER", "postgres"),
        "dbPassword": os.environ["E2E_PG_PASSWORD"],
        "dbType": "POSTGRESQL",
    })
    cid = created["id"]
    check("dbPassword" not in str(api.list_connections()), "the database list carries no password")
    again = ApiClient(API_URL, timeout=30)
    again.login(f"e2e_{suffix}", "e2e-password")
    check(again.take_sign_in_passwords() == {cid: os.environ["E2E_PG_PASSWORD"]},
          "signing in again hands the password back")
    again.logout()
    customers, orders = f"customers_{suffix}", f"Orders_{suffix}"  # mixed case: must be quoted

    window = DashboardWindow(api, db=db)
    sidebar, builder, diagram = window.sidebar_widget, window.sql_builder, window.diagram_page
    sidebar.activate_database(cid)
    print("1. design two tables, link them on the diagram, add rows")
    customer_page = sidebar.create_table_page(cid, customers)
    for column in (["id", "int", "Not Null", "PK", "-", "-", "AUTO"], ["name", "varchar", "Not Null", "-", "-", "-", "-"],
                   ["balance", "money", "Null", "-", "-", "-", "-"]):
        customer_page._append_column(column)
        customer_page.table_data_ready.emit(customers, customer_page.state.columns)
    for name, balance in (("Ann", "$10.50"), ("O'Brien", "")):
        customer_page.add_rows()
        row = customer_page.table.rowCount() - 1
        customer_page.table.item(row, 1).setText(name)
        customer_page.table.item(row, 2).setText(balance)

    order_page = sidebar.create_table_page(cid, orders)
    for column in (["id", "int", "Not Null", "PK", "-", "-", "-"], ["customer_id", "int", "Null", "FK", "-", "-", "-"],
                   ["placed", "date", "Null", "-", "-", "-", "-"]):
        order_page._append_column(column)
        order_page.table_data_ready.emit(orders, order_page.state.columns)
    diagram.restore_links([(customers, "id", orders, "customer_id")])  # what dragging PK -> FK does
    order_page.add_rows()
    order_page.table.item(0, 1).setText("1")

    script = builder.change_statements
    check(script[0].startswith(f"CREATE TABLE {customers}") and script[1].startswith(f'CREATE TABLE "{orders}"'),
          "the referenced table is created first")
    check(f"REFERENCES {customers} (id)" in script[1], "the drawn link becomes a foreign key")
    run(builder)
    check(rows(db, created, f"SELECT id, name, balance FROM {customers} ORDER BY id") ==
          [[1, "Ann", Decimal("10.5000")], [2, "O'Brien", None]],
          "customers were inserted (identity ids, quote escaped, money without '$')")
    check(rows(db, created, f'SELECT id, customer_id FROM "{orders}"') == [[1, 1]], "the order was inserted")
    check(links_of(diagram, customers, orders) == [(customers, "id", orders, "customer_id")],
          "after the reload the link is read back from the database's foreign key")
    check(builder.change_statements == [], "nothing is left to save")

    print("2. edit a cell of a live table")
    page = sidebar.page_map[(cid, customers)]
    sidebar._load_rows(cid, page)
    page.table.item(1, 2).setText("$3")
    check(builder.change_statements == [f"UPDATE {customers} SET balance = 3 WHERE id = 2"], "one UPDATE by primary key")
    run(builder)
    check(rows(db, created, f"SELECT balance FROM {customers} WHERE id = 2") == [[Decimal("3.0000")]], "the value was saved")

    print("3. rename the foreign key column, delete a row, add a column")
    page = sidebar.page_map[(cid, orders)]
    sidebar._load_rows(cid, page)
    with mock.patch("dbmanager.ui.table_editor.table_details_page.ask_new_name", return_value="buyer_id"):
        page._rename_field(1)
    page._append_column(["note", "text", "Null", "-", "-", "-", "-"])
    page.table_data_ready.emit(orders, page.state.columns)
    page.table.item(0, 3).setText("first order")
    check(not any("ADD FOREIGN KEY" in statement for statement in builder.change_statements),
          "a renamed foreign key is not added a second time")
    run(builder)
    check(rows(db, created, f'SELECT buyer_id, note FROM "{orders}"') == [[1, "first order"]], "rename + new column saved")
    check(links_of(diagram, customers, orders) == [(customers, "id", orders, "buyer_id")],
          "the link follows the renamed column")

    page = sidebar.page_map[(cid, customers)]
    sidebar._load_rows(cid, page)
    page.table.selectRow(1)
    with mock.patch("dbmanager.ui.table_editor.table_details_page.confirm", return_value=True):
        page.keyPressEvent(_delete_key())
    check(builder.change_statements == [f"DELETE FROM {customers} WHERE id = 2"], "one DELETE by primary key")
    run(builder)
    check(rows(db, created, f"SELECT count(*) FROM {customers}") == [[1]], "the row was deleted")

    print("4. build a JOIN in the query builder")
    for table, field in ((customers, "name"), (orders, "note"), (orders, "buyer_id")):
        diagram._on_query_toggle(diagram.cards[table].find_row(field))  # the circle at the end of the row
    builder.add_filter(Filter(orders, "buyer_id", "int", "=", ("1",)))
    with mock.patch("dbmanager.ui.query.query_builder.QueryResultsWindow") as results_window:
        builder.run_query()
    results = results_window.call_args[0][0]
    check(results[-1]["rows"] == [["Ann", "first order", 1]], "the generated JOIN returns the joined row")
    builder.clear_query()

    print("5. a required field and a required value, in tables that have rows")
    page = sidebar.page_map[(cid, customers)]
    sidebar._load_rows(cid, page)
    page._append_column(["tier", "int", "Not Null", "-", "-", "-", "-"])
    page.table_data_ready.emit(customers, page.state.columns)
    with mock.patch("dbmanager.ui.query.query_builder.show_styled_message") as told:
        builder.run_query()
    check(told.call_args[0][1] == "Not Run Yet" and "has none" in told.call_args[0][2],
          "a required field without values for the rows is not run")
    page.table.item(0, 3).setText("2")
    check(builder.change_statements[-1] == f"ALTER TABLE {customers} ALTER COLUMN tier SET NOT NULL",
          "NOT NULL comes after the rows got their value")
    run(builder)
    tier = next(c for t in db.schema(created) if t["name"] == customers for c in t["columns"] if c["name"] == "tier")
    check(not tier["nullable"] and rows(db, created, f"SELECT tier FROM {customers}") == [[2]],
          "the field is NOT NULL and the row kept its value")

    page = sidebar.page_map[(cid, orders)]
    sidebar._load_rows(cid, page)
    page.table.item(0, 2).setText("NULL")  # placed: cleared here, in the same run
    with mock.patch("dbmanager.ui.table_editor.table_details_page.ask_fill_value", return_value="2024-12-31"):
        page._require_value(2)
    check(builder.change_statements == [f'UPDATE "{orders}" SET placed = NULL WHERE id = 1',
                                        f"UPDATE \"{orders}\" SET placed = '2024-12-31' WHERE placed IS NULL",
                                        f'ALTER TABLE "{orders}" ALTER COLUMN placed SET NOT NULL'],
          "the edit, then the fill, then NOT NULL")
    run(builder)
    check(rows(db, created, f'SELECT placed FROM "{orders}"') == [["2024-12-31"]],
          "the empty rows got the value, then the field was made NOT NULL")

    print("6. drop the table the other one points at, then the other one")
    item = next(sidebar.databases[cid]["item"].child(i) for i in range(sidebar.databases[cid]["item"].childCount())
                if sidebar.databases[cid]["item"].child(i).data(0, 257) == customers)
    with mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True) as asked:
        sidebar._toggle_drop(cid, item, sidebar.page_map[(cid, customers)])
    check(f"{orders}.buyer_id" in asked.call_args[0][2], "the warning names the field that points at it")
    check(builder.change_statements[0].startswith(f'ALTER TABLE "{orders}" DROP CONSTRAINT')
          and builder.change_statements[1] == f"DROP TABLE {customers}", "its foreign key is dropped first")
    run(builder)
    remaining = [table["name"] for table in db.schema(created)]
    check(customers not in remaining and orders in remaining, "the table is gone, the other one stays")
    page = sidebar.page_map[(cid, orders)]
    with mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True):
        page.drop_requested.emit(orders)  # the Drop table button on its page
    run(builder)
    check(orders not in [table["name"] for table in db.schema(created)], "and the other one too")

    if os.environ.get("E2E_BACKEND_LOG"):
        share(api, db, created, window, suffix)

    window.close()
    check(not api.signed_in, "closing the dashboard logged out")
    print("END-TO-END OK")


def share(api, db, connection, window, suffix):
    print("7. share the database with a second user, who may only read")
    table = f"shared_{suffix}"
    db.run_script(connection, f"CREATE TABLE {table} (id INT PRIMARY KEY); INSERT INTO {table} VALUES (1)")
    email = f"e2e_{suffix}@example.com"
    api.request_premium_code(email)
    api.confirm_premium(email, code_sent_to(email))
    guest_api = ApiClient(API_URL, timeout=30)
    guest_api.register(f"e2e_guest_{suffix}", None, "e2e-password")

    def invite(dialog):
        dialog.username_input.setText(f"e2e_guest_{suffix}")  # SELECT is ticked already
        dialog.send_button.click()
        check(dialog.status.text().startswith("Invited"), f"invited: {dialog.status.text()}")

    with mock.patch.object(ShareDatabaseDialog, "exec", new=invite):
        window.share_database(connection)
    login = f"dbm_u{guest_api.user_id}_c{connection['id']}"
    check(rows(db, connection, f"SELECT count(*) FROM pg_roles WHERE rolname = '{login}'") == [[1]],
          f"the owner's app made the login {login} in the database")

    guest = DatabaseClient(guest_api, MemoryPasswords())
    check(all(c["id"] != connection["id"] for c in guest_api.list_connections()),
          "nothing is shared before the invitation is accepted")
    for invitation in guest_api.list_invitations():
        guest_api.set_invitation_status(invitation["id"], "ACCEPTED")
    shared = next(c for c in guest_api.list_connections() if c["id"] == connection["id"])
    check(rows(guest, shared, f"SELECT id FROM {table}") == [[1]], "the guest reads the table with their own login")
    try:
        guest.run_script(shared, f"DELETE FROM {table}")
        raise AssertionError("the guest could delete rows")
    except DatabaseError as error:
        check("permission denied" in str(error), "the database itself refuses the guest a DELETE")
    check(rows(db, connection, f"SELECT count(*) FROM {table}") == [[1]], "the row is still there")

    for invitation in api.list_invitations():
        if invitation["dbConnectionId"] == connection["id"] and invitation["status"] == "ACCEPTED":
            api.set_invitation_status(invitation["id"], "REVOKED")
    db.sync_guests(connection)
    check(rows(db, connection, f"SELECT count(*) FROM pg_roles WHERE rolname = '{login}'") == [[0]],
          "revoking drops the login from the database")
    db.run_script(connection, f"DROP TABLE {table}")
    guest_api.logout()


def code_sent_to(email, seconds=10):
    """The six-digit code the backend wrote to its log instead of mailing it."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        with open(os.environ["E2E_BACKEND_LOG"], encoding="utf-8", errors="replace") as log:
            codes = re.findall(rf"{re.escape(email)}\D+(\d{{6}})", log.read())
        if codes:
            return codes[-1]
        time.sleep(0.5)
    raise AssertionError(f"no code for {email} in the backend log")


def _delete_key():
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeyEvent
    return QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)


if __name__ == "__main__":
    main()
