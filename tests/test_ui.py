"""Widget tests, run offscreen. They drive the real widgets against a fake API."""

import unittest
from decimal import Decimal
from unittest import mock

from tests import qt

from PyQt6.QtGui import QColor, QPalette  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QCheckBox, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QToolButton, QVBoxLayout, QWidget
)

from dbmanager.api import ApiError  # noqa: E402
from dbmanager.model.sharing import PERMISSIONS  # noqa: E402
from dbmanager.ui.auth.sign_in import SignInWindow  # noqa: E402
from dbmanager.ui.auth.sign_up import SignUpWindow  # noqa: E402
from dbmanager.ui.common.message_box import styled_message_box, styled_question_box  # noqa: E402
from dbmanager.ui.dashboard.dashboard_window import DashboardWindow  # noqa: E402
from dbmanager.ui.dialogs.database_dialog import InputDatabaseWindow  # noqa: E402
from dbmanager.ui.dialogs.delete_account_dialog import DeleteAccountDialog  # noqa: E402
from dbmanager.ui.dialogs.field_dialog import InputFieldsWindow  # noqa: E402
from dbmanager.ui.dialogs.rename_dialog import RenameDialog  # noqa: E402
from dbmanager.ui.dialogs.table_name_dialog import InputTableNameWindow  # noqa: E402
from dbmanager.ui.diagram.diagram_page import DiagramPage  # noqa: E402
from dbmanager.ui.query.query_builder import SQLQueryBuilder  # noqa: E402
from dbmanager.ui.sharing.invitations_dialog import InvitationsDialog  # noqa: E402
from dbmanager.ui.sharing.premium_dialog import PremiumDialog  # noqa: E402
from dbmanager.ui.sharing.share_dialog import ShareDatabaseDialog  # noqa: E402
from dbmanager.ui.table_editor.table_details_page import TableDetailsPage  # noqa: E402

APP = qt.app()


def contrast(a, b):
    """WCAG contrast ratio of two QColors (1 = invisible, 21 = black on white)."""
    def luminance(color):
        channels = []
        for value in (color.redF(), color.greenF(), color.blueF()):
            channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def dark_system_palette():
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, "#202020"), (QPalette.ColorRole.Base, "#2a2a2a"),
                        (QPalette.ColorRole.Text, "#ffffff"), (QPalette.ColorRole.WindowText, "#ffffff")):
        palette.setColor(role, QColor(color))
    return palette


SHOP = {"id": 1, "ownerUserId": 7, "host": "localhost", "port": 5432, "dbName": "shop",
        "dbUsername": "postgres", "dbType": "POSTGRESQL"}


def offer(invitation_id, permission, status="PENDING"):
    """bob (user 9) offers ann (user 7) a permission on his database crm (connection 5)"""
    return {"id": invitation_id, "fromUserId": 9, "fromUsername": "bob", "toUserId": 7, "toUsername": "ann",
            "dbConnectionId": 5, "dbName": "crm", "dbType": "POSTGRESQL", "permission": permission,
            "status": status}


class FakeApi:
    username = "ann"
    user_id = 7
    roles = ["USER"]

    def __init__(self):
        self.scripts = []
        self.schema_reads = 0
        self.signed_in = True
        self.connections = [SHOP]
        self.invitations = []
        self.premium = None
        self.invited = []   # (connection id, username, permission id)
        self.answered = []  # (invitation id, status)
        self.updated = []   # (connection id, details)
        self.deleted = []   # connection ids
        self.email = None   # what ann registered with
        self.account_deleted = False

    def logout(self):
        self.signed_in = False

    def account(self):
        return {"id": self.user_id, "username": self.username, "email": self.email}

    def delete_account(self, password):
        if password != "password123":
            raise ApiError(403, "That is not the account's password - nothing was deleted")
        self.account_deleted = True
        self.signed_in = False

    def list_connections(self):
        return list(self.connections)

    def premium_status(self):
        return self.premium

    def request_premium_code(self, email):
        return f"A verification code was sent to {email}."

    def confirm_premium(self, email, code):
        self.premium = {"connectedEmail": email}
        return self.premium

    def list_permissions(self):
        return [{"id": number, "name": name} for number, (name, _) in enumerate(PERMISSIONS, start=1)]

    def list_invitations(self):
        return list(self.invitations)

    def invite(self, connection_id, username, permission_id):
        self.invited.append((connection_id, username, permission_id))
        invitation = {"id": 100 + len(self.invited), "fromUserId": self.user_id, "fromUsername": self.username,
                      "toUserId": 8, "toUsername": username, "dbConnectionId": connection_id,
                      "permission": PERMISSIONS[permission_id - 1][0], "status": "PENDING"}
        self.invitations.insert(0, invitation)
        return invitation

    def set_invitation_status(self, invitation_id, status):
        self.answered.append((invitation_id, status))
        for invitation in self.invitations:
            if invitation["id"] == invitation_id:
                invitation["status"] = status
                if status == "ACCEPTED" and all(c["id"] != invitation["dbConnectionId"] for c in self.connections):
                    self.connections.append({**SHOP, "id": invitation["dbConnectionId"],
                                             "ownerUserId": invitation["fromUserId"], "dbName": invitation["dbName"]})
                return invitation

    # Only port 5432 answers: anything else is a database the server cannot reach
    @staticmethod
    def _reach(details):
        if details["port"] != 5432:
            raise ApiError(502, f"Could not connect to POSTGRESQL {details['host']}:{details['port']}/"
                                f"{details['dbName']}: Connection refused.")
        return "Connected to PostgreSQL 16.4 in 9 ms"

    def _saved(self, connection_id):
        return next(c for c in self.connections if c["id"] == connection_id)

    def test_new_connection(self, details):
        return self._reach(details)

    def test_connection(self, connection_id, details=None):
        return self._reach(details or self._saved(connection_id))

    def update_connection(self, connection_id, details):
        self.updated.append((connection_id, details))
        index = self.connections.index(self._saved(connection_id))
        self.connections[index] = {**self.connections[index], **details}
        return self.connections[index]

    def delete_connection(self, connection_id):
        self.deleted.append(connection_id)
        self.connections.remove(self._saved(connection_id))

    def get_schema(self, connection_id):
        self._reach(self._saved(connection_id))
        self.schema_reads += 1
        return [
            {"name": "customers", "type": "TABLE", "columns": [
                {"name": "id", "type": "int4", "nullable": False, "primaryKey": True},
                {"name": "name", "type": "varchar", "nullable": True, "primaryKey": False}]},
            {"name": "orders", "type": "TABLE", "columns": [
                {"name": "id", "type": "int4", "nullable": False, "primaryKey": True},
                {"name": "customer_id", "type": "int4", "nullable": True, "primaryKey": False,
                 "referencedTable": "customers", "referencedColumn": "id"},
                {"name": "total", "type": "money", "nullable": True, "primaryKey": False}]},
            {"name": "big_orders", "type": "VIEW", "columns": [
                {"name": "id", "type": "int4", "nullable": True, "primaryKey": False}]},
        ]

    def run_query(self, connection_id, sql, max_rows=None):
        if "orders" in sql:
            return {"columns": ["id", "customer_id", "total"], "rows": [[10, 1, Decimal("5.00")]], "truncated": False}
        return {"columns": ["id", "name"], "rows": [[1, "Ann"], [2, None]], "truncated": False}

    def run_script(self, connection_id, sql):
        self.scripts.append(sql)
        return {"results": [{"statementType": "UPDATE", "updateCount": 1, "columns": [], "rows": []}],
                "durationMs": 3}


def glyph_contrast(blank, shown):
    """Contrast of text against what is behind it: the pixels that differ between a widget drawn
    without and with its text are the text."""
    ratios = []
    typed = shown
    for x in range(blank.width()):
        for y in range(blank.height()):
            if blank.pixel(x, y) != typed.pixel(x, y):
                ratios.append(contrast(QColor(typed.pixel(x, y)), QColor(blank.pixel(x, y))))
    if not ratios:
        return 1.0  # nothing visible changed: the text cannot be seen at all
    ratios.sort()
    return ratios[int(len(ratios) * 0.9)]  # the glyph cores, not their anti-aliased edges


def typed_text_contrast(editor, text="typed by user"):
    """Typed text against the editor background (read-only while drawn, so there is no cursor)."""
    editor.setReadOnly(True)
    editor.setText("")
    blank = editor.grab().toImage()
    editor.setText(text)
    editor.setCursorPosition(0)
    return glyph_contrast(blank, editor.grab().toImage())


def label_contrast(widget):
    """A label's or check box's text against what is behind it."""
    text = widget.text()
    shown = widget.grab().toImage()
    widget.setText("")
    blank = widget.grab().toImage()
    widget.setText(text)
    return glyph_contrast(blank, shown)


class CellEditorTest(unittest.TestCase):
    def setUp(self):
        self.system_palette = APP.palette()
        APP.setPalette(dark_system_palette())  # what a dark desktop theme does to every widget

    def tearDown(self):
        APP.setPalette(self.system_palette)

    def test_what_you_type_is_readable_even_with_a_dark_system_theme(self):
        window = QMainWindow()
        window.setStyleSheet("background-color: #f5f6f7;")  # what the dashboard sets
        page = TableDetailsPage("notes", None, columns=[["text", "varchar", "Null", "-", "-", "-"]], live=True)
        window.setCentralWidget(page)
        page.set_rows(["text"], [["hello"]])
        window.resize(1000, 600)
        window.show()
        APP.processEvents()

        page.table.editItem(page.table.item(0, 0))
        APP.processEvents()
        editor = page.table.findChild(QLineEdit)
        self.assertIsNotNone(editor)
        self.assertGreaterEqual(editor.height(), 30, "the editor is squeezed by the item padding")
        ratio = typed_text_contrast(editor)
        self.assertGreater(ratio, 4.5, f"typed text has a contrast of only {ratio:.2f} against the editor")
        window.close()


class DialogReadabilityTest(unittest.TestCase):
    """Dialogs open over pages that colour every child's background (the dashboard's grey, the sidebar's
    white); a dialog that does not set its own label backgrounds shows light text on a light strip."""

    def setUp(self):
        self.window = QMainWindow()
        self.window.setStyleSheet("background-color: #f5f6f7;")  # what the dashboard sets
        central = QWidget()
        layout = QVBoxLayout(central)
        self.page = TableDetailsPage("t", None)
        self.sidebar_like = QWidget()
        self.sidebar_like.setStyleSheet("background-color: #FFFFFF;")  # what the sidebar sets
        layout.addWidget(self.page)
        layout.addWidget(self.sidebar_like)
        self.window.setCentralWidget(central)
        self.window.show()

    def tearDown(self):
        self.window.close()

    def assert_readable(self, dialog, name):
        dialog.show()
        APP.processEvents()
        checked = 0
        for widget in dialog.findChildren((QLabel, QCheckBox)):
            if widget.isVisible() and widget.text().strip():
                ratio = label_contrast(widget)
                self.assertGreater(ratio, 4.5, f"{name}: '{widget.text()}' has a contrast of only {ratio:.2f}")
                checked += 1
        dialog.hide()
        self.assertGreater(checked, 0, f"{name}: no text found to check")

    def test_every_dialog_is_readable_over_the_dashboard(self):
        for parent, where in ((self.page, "page"), (self.sidebar_like, "sidebar")):
            self.assert_readable(InputFieldsWindow(parent=parent), f"Add Field over {where}")
            self.assert_readable(RenameDialog(parent, "Rename Field", "Enter new field name:", "x"),
                                 f"Rename over {where}")
            self.assert_readable(styled_message_box(parent, "Info", "Something happened."), f"message over {where}")
            self.assert_readable(styled_question_box(parent, "Question", "Delete it?"), f"question over {where}")
            self.assert_readable(InputTableNameWindow(parent), f"New Table over {where}")
            self.assert_readable(InputDatabaseWindow(parent), f"Database over {where}")
            self.assert_readable(PremiumDialog(parent, FakeApi()), f"Premium over {where}")
            api = FakeApi()
            api.invitations = [offer(11, "SELECT_ROLE")]
            api.invite(1, "carol", 1)
            self.assert_readable(ShareDatabaseDialog(parent, api, SHOP), f"Share over {where}")
            self.assert_readable(InvitationsDialog(parent, api), f"Invitations over {where}")
            self.assert_readable(DeleteAccountDialog(parent, api, 3), f"Delete Account over {where}")


class DiagramTest(unittest.TestCase):
    def setUp(self):
        self.builder = SQLQueryBuilder()
        self.page = DiagramPage(sql_builder=self.builder)
        self.page.add_table_card("customers", [["id", "int", "Not Null", "PK", "-", "-"]])
        self.orders = [["id", "int", "Not Null", "PK", "-", "-"], ["customer_id", "int", "Null", "FK", "-", "-"]]
        self.page.add_table_card("orders", self.orders)
        self.page.restore_links([("customers", "id", "orders", "customer_id")])

    def test_adding_a_field_to_a_linked_table_keeps_the_link(self):
        self.page.add_table_card("orders", self.orders + [["note", "text", "Null", "-", "-", "-"]])
        qt.raise_slot_errors()
        self.assertEqual(self.page.export_links(), [("customers", "id", "orders", "customer_id")])
        self.assertEqual(self.page.cards["orders"].find_row("customer_id").connection_count, 1)
        self.assertEqual(self.page.cards["customers"].find_row("id").connection_count, 1)

    def test_renaming_a_linked_field_keeps_the_link_and_the_join(self):
        renamed = [self.orders[0], ["cust_id", "int", "Null", "FK", "-", "-"]]
        self.page.rename_field("orders", "customer_id", "cust_id", renamed)
        qt.raise_slot_errors()
        self.assertEqual(self.page.export_links(), [("customers", "id", "orders", "cust_id")])
        self.assertEqual(self.builder.table_connections, [("customers", "id", "orders", "cust_id")])

    def test_deleting_a_linked_field_drops_the_link_everywhere(self):
        self.page.remove_field_from_card("orders", self.orders[:1])
        qt.raise_slot_errors()
        self.assertEqual(self.page.export_links(), [])
        self.assertEqual(self.builder.table_connections, [])
        self.assertEqual(self.page.cards["customers"].find_row("id").connection_count, 0)

    def test_the_query_selection_survives_a_card_refresh(self):
        self.page._on_field_selected_for_query("orders", "id", "PK")
        self.page.add_table_card("orders", self.orders + [["note", "text", "Null", "-", "-", "-"]])
        self.assertTrue(self.page.cards["orders"].find_row("id").is_selected_for_query)

    def test_a_where_condition_marks_its_field_as_selected(self):
        self.page._on_condition_added("customers", "id", "> 5")
        self.assertTrue(self.page.cards["customers"].find_row("id").is_selected_for_query)
        self.assertIn("WHERE customers.id > 5", self.builder.builder_query)

    def test_tables_appear_in_the_order_their_fields_were_picked(self):
        self.builder.add_field("orders", "id", "PK")
        self.builder.add_field("customers", "id", "PK")
        self.assertIn("FROM orders\nJOIN customers ON orders.customer_id = customers.id", self.builder.builder_query)


class DashboardTest(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.window = DashboardWindow(self.api)
        self.sidebar = self.window.sidebar_widget
        self.builder = self.window.sql_builder

    def tearDown(self):
        self.window.close()

    def _open_table(self, name):
        db_item = self.sidebar.databases[1]["item"]
        for i in range(db_item.childCount()):
            if db_item.child(i).data(0, 257) == name:  # NAME role
                self.sidebar.on_tree_click(db_item.child(i))
                return self.sidebar.page_map[(1, name)]
        self.fail(f"no tree item for {name}")

    def test_the_aggregate_button_resets_with_the_query(self):
        self.window.toolbar.agg_buttons["SUM"].click()
        self.assertEqual(self.builder.current_aggregate, "SUM")
        self.builder.clear_query()
        self.assertIsNone(self.window.toolbar.current_aggregate)
        self.assertFalse(self.window.toolbar.agg_buttons["SUM"].is_active)

    def test_edit_a_row_then_run_saves_it_and_reads_the_database_again(self):
        self.sidebar.activate_database(1)
        self.assertEqual(set(self.window.diagram_page.cards), {"customers", "orders", "big_orders"})
        self.assertEqual(self.window.diagram_page.export_links(), [("customers", "id", "orders", "customer_id")])

        page = self._open_table("customers")
        self.assertEqual(page.table.item(1, 1).text(), "NULL")
        page.table.item(1, 1).setText("Bob")
        qt.raise_slot_errors()
        self.assertEqual(self.builder.change_statements, ["UPDATE customers SET name = 'Bob' WHERE id = 2"])
        self.assertTrue(page.pending_label.isVisibleTo(page))

        with mock.patch("dbmanager.ui.query.query_builder.QueryResultsWindow"):
            self.builder.run_query()
        qt.raise_slot_errors()
        self.assertEqual(self.api.scripts, ["UPDATE customers SET name = 'Bob' WHERE id = 2;"])
        self.assertEqual(self.api.schema_reads, 2)  # read again after the change
        self.assertEqual(self.builder.change_statements, [])

    def test_money_is_shown_with_a_dollar_sign_but_saved_without(self):
        self.sidebar.activate_database(1)
        page = self._open_table("orders")
        self.assertEqual(page.table.item(0, 2).text(), "$5.00")
        page.table.item(0, 2).setText("$7.25")
        self.assertEqual(self.builder.change_statements, ["UPDATE orders SET total = 7.25 WHERE id = 10"])

    def test_renaming_a_foreign_key_column_does_not_add_the_key_again(self):
        self.sidebar.activate_database(1)
        page = self._open_table("orders")
        with mock.patch("dbmanager.ui.table_editor.table_details_page.ask_new_name", return_value="buyer_id"):
            page._rename_field(1)
        qt.raise_slot_errors()
        self.assertEqual(self.builder.change_statements, ["ALTER TABLE orders RENAME COLUMN customer_id TO buyer_id"])
        self.assertEqual(self.window.diagram_page.export_links(), [("customers", "id", "orders", "buyer_id")])

    def test_views_are_read_only_but_can_be_dropped(self):
        self.sidebar.activate_database(1)
        page = self._open_table("big_orders")
        self.assertFalse(page.add_row_btn.isEnabled())
        self.assertFalse(page.add_field_btn.isEnabled())
        db_item = self.sidebar.databases[1]["item"]
        view_item = next(db_item.child(i) for i in range(db_item.childCount())
                         if db_item.child(i).data(0, 257) == "big_orders")
        with mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True):
            self.sidebar._toggle_drop(1, view_item, page)
        self.assertEqual(self.builder.change_statements, ["DROP VIEW big_orders"])

    def _discard(self, button, answer=True):
        with mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=answer):
            button.click()
        qt.raise_slot_errors()

    def test_added_rows_can_be_discarded_from_the_sql_panel(self):
        self.sidebar.activate_database(1)
        page = self._open_table("customers")
        self.assertFalse(self.builder.discard_btn.isVisibleTo(self.builder))
        for _ in range(4):
            page.add_rows()
        self.assertEqual(self.builder.change_statements, ["INSERT INTO customers DEFAULT VALUES"] * 4)
        self.assertTrue(self.builder.discard_btn.isVisibleTo(self.builder))

        self._discard(self.builder.discard_btn, answer=False)  # "No" keeps everything
        self.assertEqual(len(self.builder.change_statements), 4)

        self._discard(self.builder.discard_btn)
        self.assertEqual(self.builder.change_statements, [])
        self.assertFalse(self.builder.discard_btn.isVisibleTo(self.builder))
        fresh = self.sidebar.page_map[(1, "customers")]
        self.assertEqual(fresh.table.rowCount(), 2)
        self.assertIs(self.window.stacked_center.currentWidget(), fresh)

    def test_one_table_can_be_discarded_and_the_others_keep_their_changes(self):
        self.sidebar.activate_database(1)
        orders = self._open_table("orders")
        orders.table.item(0, 2).setText("9")
        customers = self._open_table("customers")
        customers.table.item(0, 1).setText("Zoe")
        customers.add_rows()
        self.assertTrue(customers.discard_btn.isVisibleTo(customers))

        self._discard(customers.discard_btn)
        self.assertEqual(self.builder.change_statements, ["UPDATE orders SET total = 9 WHERE id = 10"])
        fresh = self.sidebar.page_map[(1, "customers")]
        self.assertEqual([fresh.table.item(r, 1).text() for r in range(fresh.table.rowCount())], ["Ann", "NULL"])
        self.assertIs(self.window.stacked_center.currentWidget(), fresh)
        self.assertFalse(fresh.discard_btn.isVisibleTo(fresh))

    def test_discarding_a_rename_brings_back_the_link_and_the_known_foreign_key(self):
        self.sidebar.activate_database(1)
        page = self._open_table("orders")
        with mock.patch("dbmanager.ui.table_editor.table_details_page.ask_new_name", return_value="buyer_id"):
            page._rename_field(1)
        self._discard(page.discard_btn)
        self.assertEqual(self.builder.change_statements, [])
        self.assertEqual(self.window.diagram_page.export_links(), [("customers", "id", "orders", "customer_id")])
        self.assertEqual(self.sidebar.databases[1]["db_links"], {("customers", "id", "orders", "customer_id")})

    def test_discarding_a_deleted_column_brings_back_its_link(self):
        self.sidebar.activate_database(1)
        page = self._open_table("orders")
        with mock.patch("dbmanager.ui.table_editor.table_details_page.confirm", return_value=True):
            page._delete_field(1)
        self.assertEqual(self.window.diagram_page.export_links(), [])
        self._discard(page.discard_btn)
        qt.raise_slot_errors()
        self.assertEqual(self.builder.change_statements, [])
        self.assertEqual(self.sidebar.page_map[(1, "orders")].state.column_names(), ["id", "customer_id", "total"])
        self.assertEqual(self.window.diagram_page.export_links(), [("customers", "id", "orders", "customer_id")])

    def test_discarding_a_table_designed_here_removes_it(self):
        self.sidebar.activate_database(1)
        page = self.sidebar.create_table_page(1, "drafts")
        page._append_column(["id", "int", "Not Null", "PK", "-", "-", "-"])
        page._changed()
        self.assertTrue(self.builder.change_statements[0].startswith("CREATE TABLE drafts"))
        self._discard(page.discard_btn)
        self.assertNotIn((1, "drafts"), self.sidebar.page_map)
        self.assertEqual(self.builder.change_statements, [])

    def test_closing_the_window_logs_out(self):
        self.window.close()
        self.assertFalse(self.api.signed_in)

    # ---------------- Sharing ----------------
    def _db_widget(self, connection_id):
        return self.sidebar.db_tree.itemWidget(self.sidebar.databases[connection_id]["item"], 0)

    def _button(self, widget, text):
        return next((button for button in widget.findChildren(QPushButton) if button.text() == text), None)

    def test_sharing_without_premium_offers_the_upgrade_first(self):
        with mock.patch("dbmanager.ui.dashboard.dashboard_window.confirm", return_value=False) as asked, \
                mock.patch.object(ShareDatabaseDialog, "exec") as share:
            self._button(self._db_widget(1), "Share").click()
        asked.assert_called_once()
        share.assert_not_called()

    def test_upgrading_from_the_share_button_goes_on_to_sharing(self):
        self.api.email = "ann@example.com"

        def upgrade(dialog):
            self.assertEqual(dialog.email_input.text(), "ann@example.com", "the registered address is offered")
            dialog.send_button.click()
            dialog.code_input.setText("123456")
            with mock.patch("dbmanager.ui.sharing.premium_dialog.show_styled_message"):
                dialog.confirm_button.click()

        with mock.patch("dbmanager.ui.dashboard.dashboard_window.confirm", return_value=True), \
                mock.patch.object(PremiumDialog, "exec", new=upgrade), \
                mock.patch.object(ShareDatabaseDialog, "exec") as share:
            self._button(self._db_widget(1), "Share").click()
        self.assertEqual(self.api.premium, {"connectedEmail": "ann@example.com"})
        share.assert_called_once()
        self.assertEqual(self.window.top_bar.premium_button.text(), "★  Premium")

    def test_a_premium_owner_invites_by_username_with_one_invitation_per_permission(self):
        self.api.premium = {"connectedEmail": "ann@example.com"}
        seen = {}

        def invite(dialog):
            dialog.username_input.setText("bob")
            dialog.checkboxes["INSERT_ROLE"].setChecked(True)  # SELECT is ticked already
            dialog.send_button.click()
            seen["status"] = dialog.status.text()
            seen["rows"] = [(dialog.table.item(row, 0).text(), dialog.table.item(row, 1).text())
                            for row in range(dialog.table.rowCount())]

        with mock.patch.object(ShareDatabaseDialog, "exec", new=invite):
            self._button(self._db_widget(1), "Share").click()
        self.assertEqual(self.api.invited, [(1, "bob", 1), (1, "bob", 2)])
        self.assertIn("Invited bob to SELECT, INSERT", seen["status"])
        self.assertEqual(seen["rows"], [("bob", "SELECT"), ("bob", "INSERT")])

    def test_accepting_an_invitation_adds_the_shared_database(self):
        self.api.invitations = [offer(11, "SELECT_ROLE"), offer(12, "INSERT_ROLE")]
        self.window.refresh_invitations()
        self.assertEqual(self.window.top_bar.invitations_button.text(), "✉  Invitations (1)")

        def accept(dialog):
            self.assertEqual(dialog.table.rowCount(), 1)  # one offer: two permissions, one database
            self._button(dialog.table.cellWidget(0, 3), "Accept").click()

        with mock.patch.object(InvitationsDialog, "exec", new=accept):
            self.window.top_bar.invitations_button.click()
        self.assertEqual(self.api.answered, [(11, "ACCEPTED"), (12, "ACCEPTED")])
        self.assertEqual(self.window.top_bar.invitations_button.text(), "✉  Invitations")
        shared = self._db_widget(5)
        self.assertIn("Shared with you by bob - you may SELECT, INSERT", shared.toolTip())
        self.assertIsNone(self._button(shared, "Share"), "only the owner can share a database")
        self.assertIsNone(shared.findChild(QToolButton), "nor edit, test or delete it")

    def test_premium_asks_for_an_address_when_the_account_has_none(self):
        seen = {}

        def look(dialog):
            seen["email"] = dialog.email_input.text()

        with mock.patch.object(PremiumDialog, "exec", new=look):
            self.window.top_bar.premium_button.click()
        self.assertEqual(seen["email"], "")

    # ---------------- Account ----------------
    def test_the_account_is_deleted_from_the_account_menu_once_the_password_is_right(self):
        seen = {}

        def confirm_with_password(dialog):
            seen["text"] = " ".join(label.text() for label in dialog.findChildren(QLabel))
            dialog.password_input.setText("wrong-password")
            dialog.delete_button.click()
            seen["wrong"] = dialog.status.text()
            dialog.password_input.setText("password123")
            dialog.delete_button.click()

        self.window.show()
        delete_action = next(a for a in self.window.top_bar.account_menu.actions() if a.text() == "Delete account…")
        with mock.patch.object(DeleteAccountDialog, "exec", new=confirm_with_password), \
                mock.patch("dbmanager.ui.dashboard.dashboard_window.show_styled_message") as told:
            delete_action.trigger()
        self.assertIn("your 1 saved database connection and their passwords", seen["text"])
        self.assertIn("nothing was deleted", seen["wrong"])
        self.assertTrue(self.api.account_deleted)
        self.assertIn("The account 'ann' was deleted.", told.call_args[0][2])
        self.assertFalse(self.window.isVisible(), "back to signing in")

    # ---------------- Managing databases ----------------
    def _add_db_third(self, port=5432):
        self.api.connections.append({**SHOP, "id": 2, "port": port, "dbName": "db_third"})
        self.sidebar.reload_databases()

    def test_a_database_you_own_has_a_menu_to_edit_test_share_and_delete_it(self):
        self.assertIsNotNone(self._db_widget(1).findChild(QToolButton))
        self.assertEqual([action.text() for action in self.sidebar._database_menu().actions()
                          if not action.isSeparator()],
                         ["Edit connection…", "Test connection", "Share…", "Delete…"])

    def test_one_of_several_databases_is_deleted_from_its_menu(self):
        self._add_db_third()
        with mock.patch.object(QMenu, "exec", new=lambda menu, pos: menu.actions()[-1]), \
                mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True) as asked:
            self._db_widget(2).findChild(QToolButton).click()  # ⋮ → Delete…
        self.assertIn("Remove 'db_third' from your account?", asked.call_args[0][2])
        self.assertEqual(self.api.deleted, [2])
        self.assertEqual(list(self.sidebar.databases), [1])

    def test_testing_a_database_says_whether_it_works(self):
        with mock.patch("dbmanager.ui.dashboard.side_bar.show_styled_message") as shown:
            self.sidebar.run_database_action(1, "test")
        self.assertIn("'shop' works.\nConnected to PostgreSQL", shown.call_args[0][2])

    def test_a_database_that_cannot_be_reached_offers_to_fix_its_settings(self):
        self._add_db_third(port=5439)

        def fix(dialog):
            dialog.port_input.setText("5432")
            dialog.accept()  # tests the new settings, then saves them
            return dialog.result()

        with mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True) as asked, \
                mock.patch.object(InputDatabaseWindow, "exec", new=fix):
            self.sidebar.on_tree_click(self.sidebar.databases[2]["item"])
        self.assertIn("localhost:5439/db_third: Connection refused", asked.call_args[0][2])
        self.assertIn("Edit its connection settings now?", asked.call_args[0][2])
        self.assertEqual([(key, details["port"]) for key, details in self.api.updated], [(2, 5432)])
        self.assertIn((2, "customers"), self.sidebar.page_map, "the fixed database is read at once")


class DatabaseDialogTest(unittest.TestCase):
    def _dialog(self, on_test):
        self.saved = []
        dialog = InputDatabaseWindow(None, on_submit=self.saved.append, on_test=on_test)
        dialog.host_input.setText("localhost")
        dialog.port_input.setText("5439")
        dialog.name_input.setText("db_third")
        dialog.user_input.setText("postgres")
        dialog.password_input.setText("secret")
        return dialog

    def test_test_shows_what_answered_and_saves_nothing(self):
        dialog = self._dialog(FakeApi().test_new_connection)
        dialog.port_input.setText("5432")
        next(button for button in dialog.findChildren(QPushButton) if button.text() == "Test").click()
        self.assertEqual(dialog.test_status.text(), "✓ Connected to PostgreSQL 16.4 in 9 ms")
        self.assertEqual(self.saved, [])

    def test_settings_nothing_answers_on_are_saved_only_if_the_user_insists(self):
        dialog = self._dialog(FakeApi().test_new_connection)
        with mock.patch("dbmanager.ui.dialogs.database_dialog.confirm", return_value=False) as asked:
            dialog.accept()
        self.assertIn("Save these settings anyway?", asked.call_args[0][2])
        self.assertTrue(dialog.test_status.text().startswith("✗ Could not connect"))
        self.assertEqual(self.saved, [])
        with mock.patch("dbmanager.ui.dialogs.database_dialog.confirm", return_value=True):
            dialog.accept()
        self.assertEqual([details["port"] for details in self.saved], [5439])

    def test_a_refused_value_is_not_offered_to_save_anyway(self):
        def invalid(details):
            raise ApiError(400, "Validation failed", {"host": "must be a host name or IP address"})

        dialog = self._dialog(invalid)
        with mock.patch("dbmanager.ui.dialogs.database_dialog.confirm") as asked:
            dialog.accept()
        asked.assert_not_called()
        self.assertEqual(self.saved, [])


class SignInTest(unittest.TestCase):
    def test_a_deleted_account_is_not_offered_again(self):
        window = SignInWindow()
        window.settings = mock.Mock()  # not the real remembered name
        window.settings.value.return_value = "ann"
        window.username.setText("ann")
        window.forget("ann")
        window.settings.remove.assert_called_once_with("remembered_username")
        self.assertEqual(window.username.text(), "")
        window.close()


class SignUpTest(unittest.TestCase):
    def test_an_account_needs_no_email(self):
        sign_in = mock.Mock()
        window = SignUpWindow(sign_in, None)
        window.username.setText("ann")
        window.password.field.setText("password123")
        with mock.patch("dbmanager.ui.auth.sign_up.ApiClient") as client, \
                mock.patch("dbmanager.ui.auth.sign_up.QMessageBox") as box:
            window.attempt_signup()
        box.warning.assert_not_called()
        client.return_value.register.assert_called_once_with("ann", "", "password123")
        sign_in.open_dashboard.assert_called_once()
        window.close()

    def test_a_database_nothing_answers_on_is_added_only_if_wanted(self):
        for wanted in (False, True):
            window = SignUpWindow(mock.Mock(), None)
            for field, text in ((window.username, "ann"), (window.password.field, "password123"),
                                (window.host, "localhost"), (window.port, "5439"), (window.database_name, "db_third"),
                                (window.db_username, "postgres"), (window.db_password.field, "secret")):
                field.setText(text)
            with mock.patch("dbmanager.ui.auth.sign_up.ApiClient") as client, \
                    mock.patch("dbmanager.ui.auth.sign_up.QMessageBox") as box:
                client.return_value.test_new_connection.side_effect = FakeApi().test_new_connection
                box.question.return_value = box.StandardButton.Yes if wanted else box.StandardButton.No
                window.attempt_signup()
            self.assertIn("Add it anyway?", box.question.call_args[0][2])
            self.assertEqual(client.return_value.create_connection.called, wanted)
            window.close()


if __name__ == "__main__":
    unittest.main()
