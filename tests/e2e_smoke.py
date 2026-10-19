"""
End-to-end smoke test: the real widgets against a running backend and a real PostgreSQL database.
Not part of the unit tests (it needs both servers). Run it with:

    DB_MANAGER_API_URL=http://localhost:8080 \
    E2E_PG_HOST=localhost E2E_PG_PORT=5432 E2E_PG_DB=shop E2E_PG_USER=postgres E2E_PG_PASSWORD=... \
    python -m tests.e2e_smoke

It registers a fresh user, designs two related tables in the editor, fills, edits and drops them through
Run Query, and checks after every step what PostgreSQL really holds. Use an empty scratch database.
"""

import os
import time
from decimal import Decimal
import uuid
from unittest import mock

from tests import qt

from dbmanager.api import ApiClient, ApiError  # noqa: E402
from dbmanager.ui.dashboard.dashboard_window import DashboardWindow  # noqa: E402

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


def rows(api, connection_id, sql):
    return api.run_query(connection_id, sql)["rows"]


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
    created = api.create_connection({
        "host": os.environ.get("E2E_PG_HOST", "localhost"),
        "port": int(os.environ.get("E2E_PG_PORT", "5432")),
        "dbName": os.environ.get("E2E_PG_DB", "shop"),
        "dbUsername": os.environ.get("E2E_PG_USER", "postgres"),
        "dbPassword": os.environ["E2E_PG_PASSWORD"],
        "dbType": "POSTGRESQL",
    })
    cid = created["id"]
    customers, orders = f"customers_{suffix}", f"Orders_{suffix}"  # mixed case: must be quoted

    window = DashboardWindow(api)
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
    check(rows(api, cid, f"SELECT id, name, balance FROM {customers} ORDER BY id") ==
          [[1, "Ann", Decimal("10.5000")], [2, "O'Brien", None]],
          "customers were inserted (identity ids, quote escaped, money without '$')")
    check(rows(api, cid, f'SELECT id, customer_id FROM "{orders}"') == [[1, 1]], "the order was inserted")
    check(links_of(diagram, customers, orders) == [(customers, "id", orders, "customer_id")],
          "after the reload the link is read back from the database's foreign key")
    check(builder.change_statements == [], "nothing is left to save")

    print("2. edit a cell of a live table")
    page = sidebar.page_map[(cid, customers)]
    sidebar._load_rows(cid, page)
    page.table.item(1, 2).setText("$3")
    check(builder.change_statements == [f"UPDATE {customers} SET balance = 3 WHERE id = 2"], "one UPDATE by primary key")
    run(builder)
    check(rows(api, cid, f"SELECT balance FROM {customers} WHERE id = 2") == [[Decimal("3.0000")]], "the value was saved")

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
    check(rows(api, cid, f'SELECT buyer_id, note FROM "{orders}"') == [[1, "first order"]], "rename + new column saved")
    check(links_of(diagram, customers, orders) == [(customers, "id", orders, "buyer_id")],
          "the link follows the renamed column")

    page = sidebar.page_map[(cid, customers)]
    sidebar._load_rows(cid, page)
    page.table.selectRow(1)
    with mock.patch("dbmanager.ui.table_editor.table_details_page.confirm", return_value=True):
        page.keyPressEvent(_delete_key())
    check(builder.change_statements == [f"DELETE FROM {customers} WHERE id = 2"], "one DELETE by primary key")
    run(builder)
    check(rows(api, cid, f"SELECT count(*) FROM {customers}") == [[1]], "the row was deleted")

    print("4. build a JOIN in the query builder")
    diagram._on_field_selected_for_query(customers, "name", "-")
    diagram._on_field_selected_for_query(orders, "note", "-")
    diagram._on_condition_added(orders, "buyer_id", "= 1")
    with mock.patch("dbmanager.ui.query.query_builder.QueryResultsWindow") as results_window:
        builder.run_query()
    results = results_window.call_args[0][0]
    check(results[-1]["rows"] == [["Ann", "first order", 1]], "the generated JOIN returns the joined row")
    builder.clear_query()

    print("5. drop both tables")
    for name in (orders, customers):
        item = next(sidebar.databases[cid]["item"].child(i) for i in range(sidebar.databases[cid]["item"].childCount())
                    if sidebar.databases[cid]["item"].child(i).data(0, 257) == name)
        with mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True):
            sidebar._toggle_drop(cid, item, sidebar.page_map[(cid, name)])
    check(builder.change_statements == [f'DROP TABLE "{orders}"', f"DROP TABLE {customers}"],
          "the child table is dropped before its parent")
    run(builder)
    remaining = [table["name"] for table in api.get_schema(cid)]
    check(customers not in remaining and orders not in remaining, "both tables are gone")

    window.close()
    check(not api.signed_in, "closing the dashboard logged out")
    print("END-TO-END OK")


def _delete_key():
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeyEvent
    return QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)


if __name__ == "__main__":
    main()
