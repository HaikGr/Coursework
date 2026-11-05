"""Widget tests, run offscreen. They drive the real widgets against a fake API and fake databases."""

import time
import unittest
from decimal import Decimal
from unittest import mock

from tests import qt

from PyQt6.QtCore import QPoint, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QPalette  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QCheckBox, QDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QStyle, QStyleOptionFrame,
    QStyleOptionViewItem, QToolButton, QToolTip, QVBoxLayout, QWidget
)

from dbmanager.api import ApiError  # noqa: E402
from dbmanager.db import DatabaseError  # noqa: E402
from dbmanager.db.passwords import MemoryPasswords  # noqa: E402
from dbmanager.db.values import MAX_TEXT_LENGTH  # noqa: E402
from dbmanager.model.query import Filter, Join  # noqa: E402
from dbmanager.model.sharing import PERMISSIONS  # noqa: E402
from dbmanager.ui.auth.base import AuthWindow  # noqa: E402
from dbmanager.ui.auth.forgot_password import ForgotPasswordWindow  # noqa: E402
from dbmanager.ui.auth.sign_in import SignInWindow  # noqa: E402
from dbmanager.ui.auth.sign_up import SignUpWindow  # noqa: E402
from dbmanager.ui.common.data_grid import MAX_COLUMN_WIDTH, MIN_COLUMN_WIDTH, one_line  # noqa: E402
from dbmanager.ui.common.message_box import styled_message_box, styled_question_box  # noqa: E402
from dbmanager.ui.dashboard.dashboard_window import DashboardWindow  # noqa: E402
from dbmanager.ui.dialogs.database_dialog import InputDatabaseWindow  # noqa: E402
from dbmanager.ui.dialogs.delete_account_dialog import DeleteAccountDialog  # noqa: E402
from dbmanager.ui.dialogs.field_dialog import InputFieldsWindow  # noqa: E402
from dbmanager.ui.dialogs.password_dialog import DatabasePasswordDialog  # noqa: E402
from dbmanager.ui.dialogs.rename_dialog import RenameDialog  # noqa: E402
from dbmanager.ui.dialogs.table_name_dialog import InputTableNameWindow  # noqa: E402
from dbmanager.ui.diagram.diagram_page import DiagramPage  # noqa: E402
from dbmanager.ui.query.query_builder import SQLQueryBuilder  # noqa: E402
from dbmanager.ui.query.results_window import QueryResultsWindow  # noqa: E402
from dbmanager.ui.query.filter_dialog import FilterDialog  # noqa: E402
from dbmanager.ui.query.join_dialog import JoinDialog  # noqa: E402
from dbmanager.ui.query.help_dialog import QueryHelpDialog  # noqa: E402
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


SHOP = {"id": 1, "ownerUserId": 7, "host": "192.168.1.20", "port": 5432, "dbName": "shop",
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
        self.signed_in = True
        self.connections = [SHOP]
        self.invitations = []
        self.premium = None
        self.invited = []   # (connection id, username, permission id)
        self.answered = []  # (invitation id, status)
        self.updated = []   # (connection id, details)
        self.deleted = []   # connection ids
        self.withdrawn = []  # invitation ids deleted
        self.guest_accounts = {}  # connection id -> [{"userId", "dbUsername"}]
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

    def delete_invitation(self, invitation_id):
        self.withdrawn.append(invitation_id)
        self.invitations = [invitation for invitation in self.invitations if invitation["id"] != invitation_id]

    def list_guest_accounts(self, connection_id):
        return list(self.guest_accounts.get(connection_id, []))

    def _saved(self, connection_id):
        return next(c for c in self.connections if c["id"] == connection_id)

    def create_connection(self, details):
        created = {**details, "id": max(c["id"] for c in self.connections) + 1, "ownerUserId": self.user_id}
        self.connections.append(created)
        return created

    def update_connection(self, connection_id, details):
        self.updated.append((connection_id, details))
        index = self.connections.index(self._saved(connection_id))
        self.connections[index] = {**self.connections[index], **details}
        return self.connections[index]

    def delete_connection(self, connection_id):
        self.deleted.append(connection_id)
        self.connections.remove(self._saved(connection_id))


class FakeDb:
    """The databases themselves, as DatabaseClient reaches them from this computer."""

    def __init__(self, api):
        self.api = api
        self.passwords = MemoryPasswords()
        self.ask_password = None
        self.scripts = []
        self.schema_reads = 0
        self.synced = []      # connection ids whose guest logins were brought up to date
        self.sync_error = None
        self.dropped = []     # connection ids whose guest logins were dropped
        self.forgotten = []
        self.sessions_ended = 0

    # Only port 5432 answers: anything else is a database this computer cannot reach
    @staticmethod
    def _reach(details):
        if details["port"] != 5432:
            raise DatabaseError(f"Could not connect to POSTGRESQL {details['host']}:{details['port']}/"
                                f"{details['dbName']}: Connection refused.", unreachable=True)
        return "Connected to PostgreSQL 16.4 in 9 ms"

    def is_owner(self, connection):
        return connection.get("ownerUserId") == self.api.user_id

    def test_new(self, details):
        return self._reach(details)

    def test_saved(self, connection, details=None):
        return self._reach({**connection, **(details or {})})

    def create_connection(self, details):
        assert "dbPassword" in details, "the dialog hands the password over"
        return self.api.create_connection(details)

    def update_connection(self, connection_id, details):
        return self.api.update_connection(connection_id, details)

    def delete_connection(self, connection_id):
        self.api.delete_connection(connection_id)

    def forget(self, connection_id):
        self.forgotten.append(connection_id)

    def end_session(self):
        self.sessions_ended += 1

    def sync_guests(self, connection, invitations=None):
        self.synced.append(connection["id"])
        if self.sync_error:
            raise self.sync_error
        return {"created": [], "dropped": []}

    def drop_guest_logins(self, connection):
        self.dropped.append(connection["id"])
        return []

    def schema(self, connection):
        self._reach(connection)
        self.schema_reads += 1
        return [
            {"name": "customers", "type": "TABLE", "columns": [
                {"name": "id", "type": "int4", "nullable": False, "primaryKey": True},
                {"name": "name", "type": "varchar", "nullable": True, "primaryKey": False}]},
            {"name": "orders", "type": "TABLE", "columns": [
                {"name": "id", "type": "int4", "nullable": False, "primaryKey": True},
                {"name": "customer_id", "type": "int4", "nullable": True, "primaryKey": False,
                 "referencedTable": "customers", "referencedColumn": "id"},
                {"name": "total", "type": "money", "nullable": True, "primaryKey": False}],
             "constraints": [{"kind": "FOREIGN KEY", "name": "orders_customer_id_fkey", "columns": ["customer_id"],
                              "refTable": "customers", "refColumns": ["id"]}]},
            {"name": "big_orders", "type": "VIEW", "columns": [
                {"name": "id", "type": "int4", "nullable": True, "primaryKey": False}]},
        ]

    def run_query(self, connection, sql, max_rows=None):
        if "orders" in sql:
            return {"columns": ["id", "customer_id", "total"], "rows": [[10, 1, Decimal("5.00")]], "truncated": False}
        return {"columns": ["id", "name"], "rows": [[1, "Ann"], [2, None]], "truncated": False}

    def run_script(self, connection, sql):
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


class WideTableTest(unittest.TestCase):
    """A table with many fields or long values: the columns used to share the width equally, so with enough
    of them every value was cut down to nothing."""

    FIELDS = [["id", "int", "Not Null", "PK", "-", "-"]] + [[f"field{n}", "varchar(255)", "Null", "-", "-", "-"]
                                                            for n in range(1, 25)]

    def setUp(self):
        self.window = QMainWindow()
        self.window.setStyleSheet("background-color: #f5f6f7;")  # what the dashboard sets
        self.page = TableDetailsPage("declarations", None, columns=self.FIELDS, live=True)
        self.window.setCentralWidget(self.page)
        self.window.resize(1200, 640)
        self.window.show()
        names = [field[0] for field in self.FIELDS]
        rows = [[1] + ["ТАМОЖЕННЫЙ ПУНКТ-ОТДЕЛ БАГРАТАШЕН"] * 24,
                [2, "first line\nsecond line"] + ["x" * 600] + [None] * 22]
        self.page.set_rows(names, rows)
        APP.processEvents()

    def tearDown(self):
        TableDetailsPage.value_panel_open = False  # a choice kept for the session: not for the next test
        self.window.close()

    def test_many_fields_scroll_sideways_and_each_keeps_room_for_its_values(self):
        table = self.page.table
        widths = [table.columnWidth(column) for column in range(table.columnCount() - 1)]  # the last one stretches
        self.assertTrue(all(MIN_COLUMN_WIDTH <= width <= MAX_COLUMN_WIDTH for width in widths), widths)
        self.assertGreater(table.horizontalScrollBar().maximum(), 0, "the fields do not fit: the rows scroll")
        text = table.fontMetrics().horizontalAdvance("ТАМОЖЕННЫЙ ПУНКТ-ОТДЕЛ БАГРАТАШЕН")
        self.assertGreaterEqual(table.columnWidth(5), text, "a value that fits the widest column is shown whole")

    def test_a_cut_value_has_a_tooltip_with_all_of_it_and_one_that_fits_has_none(self):
        table = self.page.table

        def tooltip(row, column):
            index = table.model().index(row, column)
            option = QStyleOptionViewItem()
            option.rect = table.visualRect(index)
            return table.itemDelegate().cut_value(table, option, index)

        self.assertEqual(tooltip(1, 2), "x" * 600)
        self.assertIsNone(tooltip(0, 2))
        self.assertEqual(tooltip(1, 1), "first line\nsecond line", "its lines, which the cell shows on one")
        self.assertEqual(table.item(1, 1).text(), one_line("first line\nsecond line"))
        self.assertEqual(table.horizontalHeaderItem(3).toolTip(), "field3 (varchar(255))")

    def test_the_value_panel_shows_the_whole_value_of_the_current_cell(self):
        self.page.table.setCurrentCell(1, 2)
        self.page.value_btn.click()
        panel = self.page.value_panel
        self.assertTrue(panel.isVisible())
        self.assertEqual(panel.text(), "x" * 600)
        self.assertEqual(panel.title.full_text(), "field2")
        self.assertIn("600 characters", panel.status.text())
        self.page.table.setCurrentCell(1, 3)
        self.assertEqual(panel.text(), "", "it follows the current cell")
        self.assertIn("NULL", panel.status.text())

    def test_typing_in_the_value_panel_edits_the_cell_at_once(self):
        self.page.table.setCurrentCell(0, 4)
        self.page.open_value_panel()
        self.page.value_panel.editor.setPlainText("one\ntwo")
        self.assertEqual(self.page.state.rows[0][4], "one\ntwo")
        self.assertEqual(self.page.table.item(0, 4).text(), "one ↵ two")
        self.assertFalse(self.page.table.item(0, 4).flags() & Qt.ItemFlag.ItemIsEditable,
                         "a one-line editor would join its lines: it is edited in the panel")
        self.assertTrue(any("UPDATE" in statement for statement in self.page.state.data_statements()))
        self.assertTrue(self.page.pending_label.isVisibleTo(self.page))

        self.page.value_panel.null_btn.click()
        self.assertEqual(self.page.state.rows[0][4], "NULL")
        self.assertEqual(self.page.value_panel.text(), "")

    def test_text_a_number_field_cannot_hold_is_not_taken_and_the_page_says_so_when_left(self):
        self.page.table.setCurrentCell(0, 0)
        self.page.open_value_panel()
        self.page.value_panel.editor.setPlainText("abc")
        self.assertEqual(self.page.state.rows[0][0], 1)
        self.assertIn('holds numbers (int), not "abc" - not taken', self.page.value_panel.status.text())
        self.assertEqual(self.page.cell_notice, "", "no notice on the page while typing")
        self.page.value_panel.editing_finished.emit()
        self.assertIn("id holds numbers (int), not \"abc\" - the value was not taken.", self.page.cell_notice)
        self.assertEqual(self.page.value_panel.text(), "1", "back to what the cell holds")

    def test_a_double_click_on_a_value_of_several_lines_opens_it_in_the_panel(self):
        self.page.table.setCurrentCell(1, 1)
        self.page.table.cellDoubleClicked.emit(1, 1)
        self.assertTrue(self.page.value_btn.isChecked())
        self.assertEqual(self.page.value_panel.text(), "first line\nsecond line")
        self.assertFalse(self.page.value_panel.editor.isReadOnly())

    def test_a_value_longer_than_what_is_read_cannot_be_changed(self):
        page = TableDetailsPage("notes", None, columns=[["body", "text", "Null", "-", "-", "-"]], live=True)
        page.set_rows(["body"], [["Q" * MAX_TEXT_LENGTH], ["short"]])
        self.assertFalse(page.table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable)
        self.assertTrue(page.table.item(1, 0).flags() & Qt.ItemFlag.ItemIsEditable)
        page.table.setCurrentCell(0, 0)
        page.open_value_panel()
        self.assertTrue(page.value_panel.editor.isReadOnly())
        self.assertIn("only these were read", page.value_panel.status.text())

    def test_the_value_panel_stays_open_from_table_to_table(self):
        self.page.value_btn.click()
        other = TableDetailsPage("other", None, columns=[["id", "int", "Not Null", "PK", "-", "-"]], live=True)
        other.show()
        self.assertTrue(other.value_btn.isChecked())
        self.assertFalse(other.value_panel.isHidden())
        other.value_panel.findChild(QPushButton, "valueClose").click()
        self.assertFalse(other.value_btn.isChecked())
        self.assertFalse(TableDetailsPage.value_panel_open)
        other.close()

    def test_clicking_a_field_in_the_schema_shows_it_in_the_rows(self):
        self.page.table.setCurrentCell(1, 0)
        QTest.mouseClick(self.page.schema_rows[20], Qt.MouseButton.LeftButton)
        self.assertEqual((self.page.table.currentRow(), self.page.table.currentColumn()), (1, 20))
        self.assertGreater(self.page.table.horizontalScrollBar().value(), 0)

    def test_a_long_field_name_is_cut_in_the_schema_and_whole_in_its_tooltip(self):
        name = "a_really_long_field_name_for_the_customs_declaration_registration_office"
        page = TableDetailsPage("t", None, columns=[[name, "enum('pending','accepted','rejected','cancelled')",
                                                     "Null", "-", "-", "-"]], live=True)
        page.resize(900, 500)
        page.show()
        APP.processEvents()
        label = page.schema_rows[0].findChild(QLabel, "field_name_label")
        self.assertNotEqual(label.text(), name)
        self.assertEqual(label.toolTip(), name)
        self.assertIn(name, page.schema_rows[0].toolTip())
        page.close()

    def test_a_query_result_shows_a_whole_value_on_a_double_click(self):
        results = [{"statementType": "SELECT", "updateCount": None, "columns": ["name", "note"],
                    "rows": [["Ann", "one\ntwo"], [None, "y" * 400]]}]
        dialog = QueryResultsWindow(results, 12, "shop")
        dialog.show()
        dialog.table.setCurrentCell(0, 1)
        dialog.table.cellDoubleClicked.emit(0, 1)
        self.assertTrue(dialog.value_panel.isVisible())
        self.assertEqual(dialog.value_panel.text(), "one\ntwo")
        self.assertTrue(dialog.value_panel.editor.isReadOnly())
        self.assertFalse(dialog.value_panel.null_btn.isVisible())
        dialog.close()


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
        with mock.patch("dbmanager.ui.dashboard.dashboard_window.confirm", return_value=True):
            self.window.close()  # a test may leave changes that were never run

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
            self.assert_readable(DatabasePasswordDialog(parent, SHOP, "password authentication failed"),
                                 f"Database Password over {where}")


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

    def row(self, table, field):
        return self.page.cards[table].find_row(field)

    def test_the_circle_on_a_row_adds_the_field_and_takes_it_out_again(self):
        row = self.row("orders", "id")
        row.toggle.clicked.emit()
        self.assertTrue(row.is_selected_for_query)
        self.assertTrue(row.toggle.checked)
        self.assertEqual(self.builder.builder_query, "SELECT orders.id\nFROM orders")
        self.assertEqual(self.builder.selected_key, ("orders", "id"))  # the toolbar acts on it now
        row.toggle.clicked.emit()
        self.assertFalse(row.is_selected_for_query)
        self.assertEqual(self.builder.builder_query, "")

    def test_the_query_selection_survives_a_card_refresh(self):
        self.row("orders", "id").toggle.clicked.emit()
        self.page.add_table_card("orders", self.orders + [["note", "text", "Null", "-", "-", "-"]])
        self.assertTrue(self.row("orders", "id").is_selected_for_query)

    def test_the_query_survives_the_diagram_being_drawn_again(self):
        self.row("orders", "id").toggle.clicked.emit()
        self.page.clear_diagram()  # what the sidebar does after a Run
        self.page.add_table_card("orders", self.orders)
        self.assertTrue(self.row("orders", "id").is_selected_for_query)
        self.assertIn("orders.id", self.builder.builder_query)

    def test_a_filter_marks_its_field_without_adding_it(self):
        self.builder.add_filter(Filter("customers", "id", "int", ">", ("5",)))
        row = self.row("customers", "id")
        self.assertFalse(row.is_selected_for_query)
        self.assertTrue(row.is_filtered)
        self.assertEqual(self.builder.builder_query, "SELECT *\nFROM customers\nWHERE customers.id > 5")

    def menu_actions(self, menu):
        return {action.text(): action for action in menu.actions()}

    def test_the_field_menu_adds_summarises_and_sorts(self):
        row = self.row("orders", "customer_id")
        self.menu_actions(self.page.field_menu(row))["Add to query"].trigger()
        self.assertTrue(row.is_selected_for_query)

        summarize = self.menu_actions(self.page.field_menu(row))["Summarize"].menu()
        count = next(action for action in summarize.actions() if action.data() == "COUNT")
        summarize.triggered.emit(count)
        self.assertEqual(self.builder.model.column("orders", "customer_id").aggregate, "COUNT")

        sort = self.menu_actions(self.page.field_menu(row))["Sort"].menu()
        next(action for action in sort.actions() if action.text().startswith("Largest")).trigger()
        self.assertIn("ORDER BY COUNT(orders.customer_id) DESC", self.builder.builder_query)

        self.menu_actions(self.page.field_menu(row))["Remove from query"].trigger()
        self.assertFalse(row.is_selected_for_query)

    def test_sum_is_offered_only_for_numbers(self):
        self.page.add_table_card("customers", [["id", "int", "Not Null", "PK", "-", "-"],
                                               ["name", "varchar(80)", "Null", "-", "-", "-"]])
        summarize = self.menu_actions(self.page.field_menu(self.row("customers", "name")))["Summarize"].menu()
        enabled = {action.data(): action.isEnabled() for action in summarize.actions()}
        self.assertFalse(enabled["SUM"])
        self.assertFalse(enabled["AVG"])
        self.assertTrue(enabled["MAX"])
        self.assertTrue(enabled["COUNT_DISTINCT"])

    def test_a_drawn_link_can_be_taken_back_from_the_menu(self):
        actions = self.menu_actions(self.page.field_menu(self.row("orders", "customer_id")))
        actions["Remove link to customers.id"].trigger()
        self.assertEqual(self.page.export_links(), [])
        self.assertEqual(self.builder.table_connections, [])

    def test_a_saved_foreign_key_is_not_offered_for_removal(self):
        self.page.is_saved_link = lambda link: True
        actions = self.menu_actions(self.page.field_menu(self.row("orders", "customer_id")))
        self.assertFalse(actions["Linked to customers.id by a foreign key"].isEnabled())

    def test_renaming_a_field_keeps_it_in_the_query(self):
        self.row("orders", "customer_id").toggle.clicked.emit()
        self.page.rename_field("orders", "customer_id", "buyer_id",
                               [self.orders[0], ["buyer_id", "int", "Null", "FK", "-", "-"]])
        self.assertIn("orders.buyer_id", self.builder.builder_query)
        self.assertTrue(self.row("orders", "buyer_id").is_selected_for_query)

    def test_deleting_a_field_takes_it_out_of_the_query(self):
        self.row("orders", "customer_id").toggle.clicked.emit()
        self.page.remove_field_from_card("orders", self.orders[:1])
        self.assertEqual(self.builder.builder_query, "")

    def test_tables_appear_in_the_order_their_fields_were_picked(self):
        self.builder.add_field("orders", "id", "int")
        self.builder.add_field("customers", "id", "int")
        self.assertIn("FROM orders\nJOIN customers ON orders.customer_id = customers.id", self.builder.builder_query)


class LinkingTest(unittest.TestCase):
    """Linking two fields on the diagram with the mouse, sent through the window as a user's would be"""

    def setUp(self):
        self.window = QMainWindow()
        self.builder = SQLQueryBuilder()
        self.page = DiagramPage(sql_builder=self.builder)
        self.window.setCentralWidget(self.page)
        self.window.resize(1300, 800)
        self.window.show()
        self.page.add_table_card("customers", [["id", "int4", "Not Null", "PK", "-", "-"],
                                               ["name", "varchar", "Null", "-", "-", "-"]])
        self.page.add_table_card("orders", [["id", "int4", "Not Null", "PK", "-", "-"],
                                            ["customer_id", "int4", "Null", "-", "-", "-"],
                                            ["note", "text", "Null", "-", "-", "-"]])
        QTest.qWait(30)
        self.messages = []
        self.page.table_area.link_message.connect(lambda text, done: self.messages.append(text))

    def tearDown(self):
        self.window.close()

    def row(self, table, field):
        return self.page.cards[table].find_row(field)

    def point(self, row):
        return row.mapTo(self.window, QPoint(row.width() // 3, row.height() // 2))

    def drag(self, source, target):
        handle, start, end = self.window.windowHandle(), self.point(source), self.point(target)
        QTest.mousePress(handle, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
        for step in range(1, 9):
            QTest.mouseMove(handle, start + (end - start) * (step / 8))
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
        qt.raise_slot_errors()

    def click(self, row):
        QTest.mouseClick(self.window.windowHandle(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         self.point(row))
        qt.raise_slot_errors()

    def test_dragging_a_key_onto_any_field_of_another_table_links_them(self):
        self.drag(self.row("customers", "id"), self.row("orders", "customer_id"))
        self.assertEqual(self.page.export_links(), [("customers", "id", "orders", "customer_id")])
        self.assertEqual(self.builder.table_connections, [("customers", "id", "orders", "customer_id")])
        self.assertIn("Linked: orders.customer_id → customers.id", self.messages[-1])

    def test_dragging_from_the_field_to_the_key_works_too(self):
        self.drag(self.row("orders", "customer_id"), self.row("customers", "id"))
        self.assertEqual(self.page.export_links(), [("customers", "id", "orders", "customer_id")])

    def test_clicking_one_then_the_other_links_them(self):
        self.click(self.row("customers", "id"))
        self.assertIn("Now click the field", self.messages[-1])
        self.click(self.row("orders", "customer_id"))
        self.assertEqual(self.page.export_links(), [("customers", "id", "orders", "customer_id")])

    def test_escape_gives_up(self):
        self.click(self.row("customers", "id"))
        QTest.keyClick(self.page.table_area, Qt.Key.Key_Escape)
        self.assertIsNone(self.page.table_area.source)
        self.click(self.row("orders", "customer_id"))  # now the start of a new link
        self.assertEqual(self.page.export_links(), [])

    def test_a_refusal_says_why(self):
        self.drag(self.row("customers", "name"), self.row("orders", "note"))
        self.assertEqual(self.page.export_links(), [])
        self.assertIn("Neither customers.name nor orders.note is a primary key", self.messages[-1])
        self.drag(self.row("customers", "id"), self.row("orders", "note"))
        self.assertIn("same kind of values", self.messages[-1])
        self.assertTrue(self.page.notice.isVisibleTo(self.page))

    def test_a_field_points_at_one_key(self):
        self.drag(self.row("customers", "id"), self.row("orders", "customer_id"))
        self.page.add_table_card("people", [["id", "int4", "Not Null", "PK", "-", "-"]])
        self.drag(self.row("people", "id"), self.row("orders", "customer_id"))
        self.assertIn("points at customers.id already", self.messages[-1])

    def test_link_to_without_dragging(self):
        menu = self.page.field_menu(self.row("orders", "customer_id"))
        link_to = next(action.menu() for action in menu.actions() if action.text() == "Link to")
        customers = next(action.menu() for action in link_to.actions() if action.text() == "customers")
        self.assertEqual([action.text() for action in customers.actions()], ["id  (primary key)"],
                         "only the key of the same kind is offered")
        customers.actions()[0].trigger()
        self.assertEqual(self.page.export_links(), [("customers", "id", "orders", "customer_id")])

    def test_a_guest_cannot_link_but_is_told_to_join(self):
        self.page.can_change_structure = False
        self.drag(self.row("customers", "id"), self.row("orders", "customer_id"))
        self.assertEqual(self.page.export_links(), [])
        self.assertIn("use Join…", self.messages[-1])
        menu = self.page.field_menu(self.row("orders", "customer_id"))
        self.assertNotIn("Link to", [action.text() for action in menu.actions()])


class JoinTest(unittest.TestCase):
    COLUMNS = {"customers": [("id", "int4"), ("name", "varchar"), ("email", "varchar")],
               "orders": [("id", "int4"), ("customer_id", "int4"), ("contact", "varchar")]}

    def test_the_likely_fields_are_chosen_and_the_sql_is_shown(self):
        dialog = JoinDialog(None, self.COLUMNS, ["customers"], "POSTGRESQL", right_table="orders")
        self.assertEqual(dialog.join(), Join("customers", "id", "orders", "customer_id"))
        dialog.kind.setCurrentIndex(dialog.kind.findData("LEFT"))
        self.assertEqual(dialog.preview.text(), "FROM customers\nLEFT JOIN orders ON customers.id = orders.customer_id")
        dialog._apply()
        self.assertEqual(dialog.result.kind, "LEFT")

    def test_fields_of_different_kinds_are_refused(self):
        dialog = JoinDialog(None, self.COLUMNS, ["customers"], right_table="orders")
        dialog.left_field.setCurrentIndex(dialog.left_field.findData("name"))
        self.assertFalse(dialog.ok_btn.isEnabled())
        self.assertIn("cannot compare them", dialog.status.text())
        dialog.right_field.setCurrentIndex(dialog.right_field.findData("contact"))
        self.assertTrue(dialog.ok_btn.isEnabled())

    def test_an_unjoined_table_offers_a_join_in_the_panel(self):
        builder = SQLQueryBuilder()
        builder.table_columns = lambda: self.COLUMNS
        builder.add_field("customers", "name", "varchar")
        builder.add_field("orders", "id", "int4")
        self.assertIn("CROSS JOIN orders", builder.builder_query)
        self.assertTrue(builder.join_unjoined_btn.isVisibleTo(builder))
        self.assertEqual(builder.join_unjoined_btn.text(), "Join orders…")

        def answer(dialog):
            self.assertEqual(dialog.join().right_table, "orders")
            dialog._apply()
            return QDialog.DialogCode.Accepted
        with mock.patch.object(JoinDialog, "exec", answer):
            builder.join_unjoined_btn.click()
        self.assertIn("JOIN orders ON customers.id = orders.customer_id", builder.builder_query)
        self.assertFalse(builder.join_unjoined_btn.isVisibleTo(builder))
        self.assertEqual(builder.joins_title.text(), "JOINS (1)")


class FilterDialogTest(unittest.TestCase):
    def test_a_value_is_typed_as_it_is_and_previewed_as_sql(self):
        dialog = FilterDialog(None, "customers", "name", "varchar(80)", "POSTGRESQL")
        dialog.operator_combo.setCurrentIndex(dialog.operator_combo.findData("CONTAINS"))
        self.assertFalse(dialog.apply_btn.isEnabled())  # nothing typed yet
        dialog.value_edit.setText("O'Hara")
        self.assertTrue(dialog.apply_btn.isEnabled())
        self.assertEqual(dialog.preview.text(), "WHERE customers.name ILIKE '%O''Hara%'")
        dialog.apply_btn.click()
        self.assertEqual(dialog.result, Filter("customers", "name", "varchar(80)", "CONTAINS", ("O'Hara",)))

    def test_a_number_column_refuses_text(self):
        dialog = FilterDialog(None, "orders", "total", "numeric(10,2)", "POSTGRESQL")
        self.assertEqual(dialog.operator_combo.findData("CONTAINS"), -1)  # text only
        dialog.value_edit.setText("lots")
        self.assertFalse(dialog.apply_btn.isEnabled())
        self.assertIn("holds numbers", dialog.status.text())

    def test_between_asks_for_two_values(self):
        dialog = FilterDialog(None, "orders", "total", "int", "SQLSERVER")
        dialog.operator_combo.setCurrentIndex(dialog.operator_combo.findData("BETWEEN"))
        self.assertTrue(dialog.second_edit.isVisibleTo(dialog))
        dialog.value_edit.setText("1")
        dialog.second_edit.setText("5")
        self.assertEqual(dialog.preview.text(), "WHERE orders.total BETWEEN 1 AND 5")

    def test_a_summarised_column_can_be_tested_per_group(self):
        dialog = FilterDialog(None, "orders", "total", "int", "MYSQL", aggregate="SUM")
        self.assertEqual(dialog.target_combo.count(), 2)
        dialog.target_combo.setCurrentIndex(1)
        dialog.value_edit.setText("100")
        self.assertEqual(dialog.preview.text(), "HAVING SUM(orders.total) = 100")

    def test_an_existing_filter_can_be_changed_or_removed(self):
        existing = Filter("orders", "total", "int", ">", ("5",))
        dialog = FilterDialog(None, "orders", "total", "int", existing=existing)
        self.assertEqual(dialog.value_edit.text(), "5")
        self.assertEqual(dialog._operator(), ">")
        dialog._remove()
        self.assertTrue(dialog.removed)

    def test_enter_applies_once(self):
        builder = SQLQueryBuilder()
        builder.add_field("orders", "id", "int")
        def answer(dialog):
            dialog.show()  # Enter presses the default button only while the dialog is on screen
            dialog.value_edit.setText("3")
            QTest.keyClick(dialog.value_edit, Qt.Key.Key_Return)
            return QDialog.DialogCode.Accepted if dialog.result is not None else QDialog.DialogCode.Rejected
        with mock.patch.object(FilterDialog, "exec", answer):
            self.assertTrue(builder.edit_filter("orders", "id", "int"))
        self.assertEqual(len(builder.model.filters), 1)
        self.assertIn("WHERE orders.id = 3", builder.builder_query)


class FieldDialogTest(unittest.TestCase):
    def test_a_required_field_says_what_the_existing_rows_need(self):
        dialog = InputFieldsWindow(existing_rows=3)
        dialog.null_checkbox.setChecked(False)
        self.assertIn("The 3 rows already in the table need a value", dialog.rows_note.text())
        dialog.default_input.setText("0")
        self.assertIn("get the default value", dialog.rows_note.text())
        dialog.input_field.setText("qty")
        dialog.accept()
        self.assertEqual(dialog.get_data(), ["qty", "int", "Not Null", "-", "-", "-", "-", "0"])

    def test_a_number_field_needs_a_number_as_its_default(self):
        dialog = InputFieldsWindow(existing_rows=0)
        dialog.input_field.setText("qty")
        dialog.default_input.setText("some")
        dialog.accept()
        self.assertIsNone(dialog.get_data())
        self.assertIn("must be a number", dialog.rows_note.text())

    def test_a_new_table_needs_no_note(self):
        dialog = InputFieldsWindow()
        dialog.null_checkbox.setChecked(False)
        self.assertEqual(dialog.rows_note.text(), "")


class EnterKeyTest(unittest.TestCase):
    """Enter does one thing: the dialog's own action, never Cancel or a second action on top"""

    def press_enter(self, dialog, field):
        dialog.show()
        field.setFocus()
        QTest.keyClick(field, Qt.Key.Key_Return)
        qt.raise_slot_errors()

    def test_enter_adds_the_field(self):
        dialog = InputFieldsWindow()
        dialog.input_field.setText("note")
        self.press_enter(dialog, dialog.input_field)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_a_wrong_password_keeps_the_delete_dialog_open(self):
        dialog = DeleteAccountDialog(None, FakeApi(), 1)
        dialog.password_input.setText("wrong")
        self.press_enter(dialog, dialog.password_input)
        self.assertTrue(dialog.isVisible())
        self.assertIn("not the account's password", dialog.status.text())
        dialog.close()

    def test_enter_in_the_host_field_connects_once(self):
        saved = []
        dialog = InputDatabaseWindow(None, on_submit=saved.append, on_test=lambda details: None)
        for field, text in ((dialog.host_input, "192.168.1.20"), (dialog.name_input, "shop"),
                            (dialog.user_input, "postgres"), (dialog.password_input, "pw")):
            field.setText(text)
        with mock.patch.object(dialog, "_test", return_value=None) as test:
            self.press_enter(dialog, dialog.host_input)
        self.assertEqual(len(saved), 1)  # Connect, once - not Test alone, and not twice
        test.assert_called_once()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)


class DashboardTest(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.db = FakeDb(self.api)
        self.window = DashboardWindow(self.api, db=self.db)
        self.sidebar = self.window.sidebar_widget
        self.builder = self.window.sql_builder

    def tearDown(self):
        with mock.patch("dbmanager.ui.dashboard.dashboard_window.confirm", return_value=True):
            self.window.close()  # a test may leave changes that were never run

    def _open_table(self, name):
        db_item = self.sidebar.databases[1]["item"]
        for i in range(db_item.childCount()):
            if db_item.child(i).data(0, 257) == name:  # NAME role
                self.sidebar.on_tree_click(db_item.child(i))
                return self.sidebar.page_map[(1, name)]
        self.fail(f"no tree item for {name}")

    def test_the_aggregate_buttons_act_on_the_selected_column(self):
        toolbar = self.window.toolbar
        self.assertFalse(toolbar.agg_buttons["SUM"].isEnabled())  # nothing selected: nothing to summarise
        self.builder.add_field("customers", "name", "text")
        self.builder.add_field("orders", "total", "numeric(10,2)")
        self.assertEqual(toolbar.target_label.full_text(), "orders.total")
        toolbar.agg_buttons["SUM"].click()
        self.assertTrue(toolbar.agg_buttons["SUM"].is_active)
        self.assertIn("SUM(orders.total) AS sum_total", self.builder.builder_query)
        self.assertIn("GROUP BY customers.name", self.builder.builder_query)

        self.builder.select_column(("customers", "name"))
        self.assertFalse(toolbar.agg_buttons["SUM"].isEnabled())  # text cannot be added up
        self.assertTrue(toolbar.agg_buttons["MAX"].isEnabled())
        self.assertFalse(toolbar.agg_buttons["SUM"].is_active)

        self.builder.select_column(("orders", "total"))
        toolbar.agg_buttons["SUM"].click()  # the lit button turns it off again
        self.assertNotIn("SUM(", self.builder.builder_query)

    def test_query_options_from_the_toolbar_reset_with_the_query(self):
        toolbar = self.window.toolbar
        self.builder.add_field("customers", "name", "text")
        toolbar.count_btn.click()
        toolbar.distinct_btn.click()
        toolbar.limit_spin.setValue(10)
        self.assertEqual(self.builder.builder_query, "SELECT DISTINCT customers.name,\n       COUNT(*) AS row_count\n"
                                                     "FROM customers\nGROUP BY customers.name\nLIMIT 10")
        self.builder.clear_query()
        self.assertFalse(toolbar.count_btn.is_active or toolbar.distinct_btn.is_active)
        self.assertEqual(toolbar.limit_spin.value(), 0)
        self.assertIsNone(toolbar.target)

    def test_sql_typed_by_hand_stays_while_nothing_is_picked(self):
        self.sidebar.activate_database(1)
        self.builder.sql_editor.setPlainText("SELECT 1")
        self.window.toolbar.distinct_btn.click()
        self.assertEqual(self.builder.sql_editor.toPlainText(), "SELECT 1")

    def test_the_query_is_kept_after_a_run_redraws_the_diagram(self):
        self.sidebar.activate_database(1)
        row = self.window.diagram_page.cards["customers"].find_row("name")
        row.toggle.clicked.emit()
        with mock.patch("dbmanager.ui.query.query_builder.QueryResultsWindow"):
            self.builder.run_query()
        qt.raise_slot_errors()
        self.assertTrue(self.window.diagram_page.cards["customers"].find_row("name").is_selected_for_query)
        self.assertIn("customers.name", self.builder.builder_query)

    def test_the_help_explains_the_query(self):
        with mock.patch("dbmanager.ui.dashboard.dashboard_window.QueryHelpDialog") as dialog:
            self.window.toolbar.help_requested.emit()
        dialog.assert_called_once()
        QueryHelpDialog(self.window)  # builds

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
        self.assertEqual(self.db.scripts, ["UPDATE customers SET name = 'Bob' WHERE id = 2;"])
        self.assertEqual(self.db.schema_reads, 2)  # read again after the change
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

    def test_unsaved_changes_are_not_lost_without_asking(self):
        self.sidebar.activate_database(1)
        self._open_table("customers").add_rows()
        with mock.patch("dbmanager.ui.dashboard.dashboard_window.confirm", return_value=False) as asked:
            self.window.log_out()
            self.window.close()
        self.assertEqual(asked.call_count, 2)
        self.assertIn("1 change is not saved", asked.call_args[0][2])
        self.assertTrue(self.api.signed_in)  # still here, with the change

        with mock.patch("dbmanager.ui.dashboard.dashboard_window.confirm", return_value=True):
            self.window.log_out()
        self.assertFalse(self.api.signed_in)

    def test_a_shared_database_keeps_its_structure(self):
        self.api.connections.append({**SHOP, "id": 5, "ownerUserId": 9, "dbName": "crm"})
        self.sidebar.reload_databases()
        self.sidebar.activate_database(5)
        db_item = self.sidebar.databases[5]["item"]
        add_table = next(db_item.child(i) for i in range(db_item.childCount())
                         if db_item.child(i).data(0, Qt.ItemDataRole.UserRole) == "add_table")
        self.assertTrue(add_table.isHidden())
        page = self.sidebar.page_map[(5, "customers")]
        self.assertFalse(page.add_field_btn.isEnabled())
        self.assertTrue(page.add_row_btn.isEnabled())  # rows: as far as the share allows, the database decides
        with mock.patch("dbmanager.ui.dashboard.side_bar.show_styled_message") as told:
            self.sidebar._toggle_drop(5, None, page)
        told.assert_called_once()
        self.assertEqual(self.builder.change_statements, [])

    # ---------------- Changing and dropping the structure ----------------
    def test_dropping_a_table_others_point_at_drops_their_keys_first(self):
        self.sidebar.activate_database(1)
        page = self._open_table("customers")
        with mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True) as asked:
            page.drop_btn.click()
        self.assertIn("orders.customer_id", asked.call_args[0][2])
        self.assertEqual(self.builder.change_statements,
                         ["ALTER TABLE orders DROP CONSTRAINT orders_customer_id_fkey", "DROP TABLE customers"])
        self.assertEqual(page.drop_btn.text(), "Keep table")
        with mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True):
            page.drop_btn.click()
        self.assertEqual(self.builder.change_statements, [])
        self.assertEqual(page.drop_btn.text(), "Drop table")

    def test_a_field_is_deleted_from_its_menu_with_the_keys_pointing_at_it(self):
        self.sidebar.activate_database(1)
        page = self._open_table("customers")
        menu = {action.text(): action for action in page.field_menu(0).actions()}
        with mock.patch("dbmanager.ui.table_editor.table_details_page.confirm", return_value=True) as asked:
            menu["Delete field…"].trigger()
        self.assertIn("orders.customer_id", asked.call_args[0][2])
        self.assertEqual(self.builder.change_statements, ["ALTER TABLE orders DROP CONSTRAINT orders_customer_id_fkey",
                                                          "ALTER TABLE customers DROP COLUMN id"])

    def test_the_diagram_offers_dropping_tables_and_deleting_fields_to_the_owner(self):
        self.sidebar.activate_database(1)
        diagram = self.window.diagram_page
        menu = {action.text(): action for action in diagram.card_menu(diagram.cards["orders"]).actions()}
        with mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True):
            menu["Drop table…"].trigger()
        self.assertEqual(self.builder.change_statements, ["DROP TABLE orders"])
        field_menu = {action.text(): action
                      for action in diagram.field_menu(diagram.cards["customers"].find_row("name")).actions()}
        with mock.patch("dbmanager.ui.table_editor.table_details_page.confirm", return_value=True):
            field_menu["Delete field…"].trigger()
        self.assertIn("ALTER TABLE customers DROP COLUMN name", self.builder.change_statements)

    def test_a_required_field_waits_for_its_values_and_the_run_waits_for_them(self):
        self.sidebar.activate_database(1)
        page = self._open_table("customers")
        with mock.patch("dbmanager.ui.table_editor.table_details_page.InputFieldsWindow") as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.get_data.return_value = ["qty", "int", "Not Null", "-", "-", "-", "-", None]
            page.add_field()
        self.assertEqual(dialog.call_args.kwargs["existing_rows"], 2)
        self.assertTrue(page.problems_label.isVisibleTo(page))
        self.assertIn("rows 1 and 2 have none", page.problems_label.text())
        with mock.patch("dbmanager.ui.query.query_builder.show_styled_message") as told:
            self.builder.run_query()
        self.assertEqual(told.call_args[0][1], "Not Run Yet")
        self.assertEqual(self.db.scripts, [], "nothing ran")

        page.table.item(0, 2).setText("3")
        page.table.item(1, 2).setText("4")
        self.assertFalse(page.problems_label.isVisibleTo(page))
        self.assertEqual(self.builder.change_statements, [
            "ALTER TABLE customers ADD COLUMN qty integer", "UPDATE customers SET qty = 3 WHERE id = 1",
            "UPDATE customers SET qty = 4 WHERE id = 2", "ALTER TABLE customers ALTER COLUMN qty SET NOT NULL"])

    def test_a_default_value_can_be_given_to_a_new_field_afterwards(self):
        self.sidebar.activate_database(1)
        page = self._open_table("customers")
        with mock.patch("dbmanager.ui.table_editor.table_details_page.InputFieldsWindow") as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.get_data.return_value = ["qty", "int", "Not Null", "-", "-", "-", "-", None]
            page.add_field()
        menu = {action.text(): action for action in page.field_menu(2).actions()}
        with mock.patch("dbmanager.ui.table_editor.table_details_page.ask_new_name", return_value="0"):
            menu["Default value…"].trigger()
        self.assertEqual([page.table.item(row, 2).text() for row in range(2)], ["0", "0"])
        self.assertFalse(page.problems_label.isVisibleTo(page))
        self.assertEqual(self.builder.change_statements,
                         ["ALTER TABLE customers ADD COLUMN qty integer NOT NULL DEFAULT 0"])
        self.assertNotIn("Default value…", [a.text() for a in page.field_menu(0).actions()], "only for new fields")

    def test_requiring_a_value_asks_what_the_empty_rows_get(self):
        self.sidebar.activate_database(1)
        page = self._open_table("customers")
        menu = {action.text(): action for action in page.field_menu(1).actions()}
        with mock.patch("dbmanager.ui.table_editor.table_details_page.ask_fill_value",
                        return_value="unknown") as asked:
            menu["Require a value (NOT NULL)…"].trigger()
        self.assertEqual(asked.call_args[0][4], 1, "one row shown has no name")
        self.assertEqual(self.builder.change_statements,
                         ["UPDATE customers SET name = 'unknown' WHERE name IS NULL",
                          "ALTER TABLE customers ALTER COLUMN name SET NOT NULL"])
        menu = {action.text(): action for action in page.field_menu(1).actions()}
        menu["Allow empty values (NULL)"].trigger()
        self.assertEqual(self.builder.change_statements, [])

    def test_text_typed_in_a_number_column_is_not_taken(self):
        self.sidebar.activate_database(1)
        page = self._open_table("orders")
        page.table.item(0, 2).setText("lots")
        self.assertEqual(self.builder.change_statements, [])
        self.assertIn('total holds numbers (money), not "lots"', page.problems_label.text())
        self.assertEqual(page.table.item(0, 2).text(), "$5.00")

    def test_nothing_to_save_means_no_question(self):
        with mock.patch("dbmanager.ui.dashboard.dashboard_window.confirm") as asked:
            self.window.log_out()
        asked.assert_not_called()
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

    def test_a_database_saved_as_localhost_cannot_be_shared(self):
        self.api.connections[0] = {**SHOP, "host": "localhost"}
        self.sidebar.reload_databases()
        with mock.patch("dbmanager.ui.dashboard.dashboard_window.show_styled_message") as told, \
                mock.patch.object(ShareDatabaseDialog, "exec") as share:
            self._button(self._db_widget(1), "Share").click()
        share.assert_not_called()
        self.assertIn("only means this computer", told.call_args[0][2])

    def test_inviting_makes_the_guest_a_login_in_the_database(self):
        self.api.premium = {"connectedEmail": "ann@example.com"}

        def invite(dialog):
            dialog.username_input.setText("bob")
            dialog.send_button.click()

        with mock.patch.object(ShareDatabaseDialog, "exec", new=invite):
            self._button(self._db_widget(1), "Share").click()
        self.assertEqual(self.db.synced, [1])
        self.assertEqual(self.api.withdrawn, [])

    def test_a_share_the_database_cannot_carry_out_is_taken_back(self):
        self.api.premium = {"connectedEmail": "ann@example.com"}
        self.db.sync_error = DatabaseError("permission denied to create role")
        seen = {}

        def invite(dialog):
            dialog.username_input.setText("bob")
            dialog.checkboxes["INSERT_ROLE"].setChecked(True)
            dialog.send_button.click()
            seen["status"] = dialog.status.text()

        with mock.patch.object(ShareDatabaseDialog, "exec", new=invite):
            self._button(self._db_widget(1), "Share").click()
        self.assertEqual(self.api.withdrawn, [101, 102], "both invitations are withdrawn")
        self.assertIn("Nothing was shared with bob: permission denied to create role", seen["status"])

    def test_revoking_takes_the_permission_out_of_the_database_too(self):
        self.api.premium = {"connectedEmail": "ann@example.com"}
        self.api.invite(1, "bob", 1)
        self.api.set_invitation_status(101, "ACCEPTED")

        def revoke(dialog):
            with mock.patch("dbmanager.ui.sharing.share_dialog.confirm", return_value=True):
                self._button(dialog.table.cellWidget(0, 3), "Revoke").click()

        with mock.patch.object(ShareDatabaseDialog, "exec", new=revoke):
            self._button(self._db_widget(1), "Share").click()
        self.assertIn((101, "REVOKED"), self.api.answered)
        self.assertEqual(self.db.synced, [1])

    def test_opening_your_database_brings_its_guest_logins_up_to_date_once(self):
        self.sidebar.activate_database(1)
        self.sidebar.refresh()  # reads the database again
        self.assertEqual(self.db.synced, [1])

    def test_opening_a_database_shared_with_you_changes_no_logins(self):
        self.api.connections.append({**SHOP, "id": 5, "ownerUserId": 9, "dbName": "crm"})
        self.sidebar.reload_databases()
        self.sidebar.activate_database(5)
        self.assertIn((5, "customers"), self.sidebar.page_map)
        self.assertEqual(self.db.synced, [])

    def test_a_password_prompt_you_cancel_is_not_an_error(self):
        def cancelled(connection):
            raise DatabaseError("No password for 'shop' is kept on this computer.", cancelled=True)

        with mock.patch.object(self.db, "schema", side_effect=cancelled), \
                mock.patch("dbmanager.ui.dashboard.side_bar.show_styled_message") as told:
            self.sidebar.activate_database(1)
        told.assert_not_called()

    def test_signing_out_forgets_the_session_logins(self):
        self.window.log_out()
        self.assertEqual(self.db.sessions_ended, 1)

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
        self.assertIn("your 1 saved database connection, every share you gave", seen["text"])
        self.assertIn("nothing was deleted", seen["wrong"])
        self.assertTrue(self.api.account_deleted)
        self.assertIn("The account 'ann' was deleted.", told.call_args[0][2])
        self.assertFalse(self.window.isVisible(), "back to signing in")

    # ---------------- Managing databases ----------------
    def _add_db_third(self, port=5432):
        self.api.connections.append({**SHOP, "id": 2, "port": port, "dbName": "db_third"})
        self.sidebar.reload_databases()

    def test_a_database_you_own_has_a_menu_to_edit_share_and_delete_it(self):
        self.assertIsNotNone(self._db_widget(1).findChild(QToolButton))
        self.assertEqual([action.text() for action in self.sidebar._database_menu().actions()
                          if not action.isSeparator()],
                         ["Edit connection…", "Share…", "Delete…"])

    def test_one_of_several_databases_is_deleted_from_its_menu(self):
        self._add_db_third()
        with mock.patch.object(QMenu, "exec", new=lambda menu, pos: menu.actions()[-1]), \
                mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True) as asked:
            self._db_widget(2).findChild(QToolButton).click()  # ⋮ → Delete…
        self.assertIn("Remove 'db_third' from your account?", asked.call_args[0][2])
        self.assertEqual(self.api.deleted, [2])
        self.assertEqual(list(self.sidebar.databases), [1])

    def test_deleting_a_shared_database_drops_its_guest_logins_first(self):
        self._add_db_third()
        self.api.guest_accounts[2] = [{"userId": 8, "dbUsername": "dbm_u8_c2"}]
        with mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True):
            self.sidebar.delete_database(2)
            self.sidebar.delete_database(1)  # never shared: the database is not even opened
        self.assertEqual(self.db.dropped, [2])
        self.assertEqual(self.api.deleted, [2, 1])
        self.assertEqual(self.db.forgotten, [2, 1], "its password goes from this computer too")

    def test_a_database_that_cannot_be_reached_offers_to_fix_its_settings(self):
        self._add_db_third(port=5439)

        def fix(dialog):
            dialog.port_input.setText("5432")
            dialog.accept()  # tests the new settings, then saves them
            return dialog.result()

        with mock.patch("dbmanager.ui.dashboard.side_bar.confirm", return_value=True) as asked, \
                mock.patch.object(InputDatabaseWindow, "exec", new=fix):
            self.sidebar.on_tree_click(self.sidebar.databases[2]["item"])
        self.assertIn("192.168.1.20:5439/db_third: Connection refused", asked.call_args[0][2])
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
        dialog = self._dialog(FakeDb(FakeApi()).test_new)
        dialog.port_input.setText("5432")
        next(button for button in dialog.findChildren(QPushButton) if button.text() == "Test").click()
        self.assertEqual(dialog.test_status.text(), "✓ Connected to PostgreSQL 16.4 in 9 ms")
        self.assertEqual(self.saved, [])

    def test_settings_nothing_answers_on_are_saved_only_if_the_user_insists(self):
        dialog = self._dialog(FakeDb(FakeApi()).test_new)
        with mock.patch("dbmanager.ui.dialogs.database_dialog.confirm", return_value=False) as asked:
            dialog.accept()
        self.assertIn("This computer could not connect", asked.call_args[0][2])
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
            with mock.patch("dbmanager.ui.auth.sign_up.ApiClient"), \
                    mock.patch("dbmanager.ui.auth.sign_up.DatabaseClient") as db, \
                    mock.patch("dbmanager.ui.auth.sign_up.QMessageBox") as box:
                db.return_value.test_new.side_effect = FakeDb(FakeApi()).test_new
                box.question.return_value = box.StandardButton.Yes if wanted else box.StandardButton.No
                window.attempt_signup()
            self.assertIn("Add it anyway?", box.question.call_args[0][2])
            self.assertEqual(db.return_value.create_connection.called, wanted)
            if wanted:
                self.assertEqual(db.return_value.create_connection.call_args[0][0]["dbPassword"], "secret")
            window.close()


class ForgotPasswordTest(unittest.TestCase):
    def setUp(self):
        self.sign_in = mock.Mock()
        self.window = ForgotPasswordWindow(self.sign_in, None)
        self.api = mock.patch("dbmanager.ui.auth.forgot_password.ApiClient").start().return_value
        self.box = mock.patch("dbmanager.ui.auth.forgot_password.QMessageBox").start()
        self.addCleanup(mock.patch.stopall)
        self.api.request_password_reset.return_value = "If an account uses ann@example.com, a code was sent there."
        self.api.reset_password.return_value = "ann"

    def tearDown(self):
        self.window.close()

    def _ask_for_a_code(self, email="ann@example.com"):
        self.window.email_input.setText(email)
        self.window.send_code()

    def _type(self, code="123456", password="brand-new-pw", repeat=None):
        self.window.code_input.setText(code)
        self.window.new_password.field.setText(password)
        self.window.repeat_password.field.setText(password if repeat is None else repeat)

    def test_the_code_and_a_new_password_sign_in_at_once(self):
        self._ask_for_a_code()
        self.assertEqual(self.window.steps.currentIndex(), 1)
        self.assertIn("a code was sent", self.window.subtitle.text())  # where the server says it went
        self.window.email_input.setText("someone.else@example.com")  # the code went to ann all the same
        self._type()
        self.window.reset_password()
        self.box.warning.assert_not_called()
        self.api.reset_password.assert_called_once_with("ann@example.com", "123456", "brand-new-pw")
        self.api.login.assert_called_once_with("ann", "brand-new-pw")  # the username: the address may not sign in
        self.sign_in.open_dashboard.assert_called_once()

    def test_what_is_typed_is_checked_before_the_server_is_asked(self):
        self._ask_for_a_code()
        for code, password, repeat, says in (("12345", "brand-new-pw", None, "six digits"),
                                              ("12ab56", "brand-new-pw", None, "six digits"),
                                              ("123456", "short", None, "at least 8"),
                                              ("123456", "brand-new-pw", "brand-new-pX", "not the same")):
            self._type(code, password, repeat)
            self.window.reset_password()
            self.assertIn(says, self.box.warning.call_args[0][2])
        self.api.reset_password.assert_not_called()

    def test_a_refused_code_is_said_and_nothing_else_happens(self):
        self.api.reset_password.side_effect = ApiError(400, "That code is not correct — 4 attempt(s) left")
        self._ask_for_a_code()
        self._type()
        self.window.reset_password()
        self.assertIn("not correct", self.box.warning.call_args[0][2])
        self.api.login.assert_not_called()
        self.sign_in.open_dashboard.assert_not_called()

    def test_when_signing_in_after_the_reset_fails_the_sign_in_window_offers_the_account(self):
        self.api.login.side_effect = ApiError(0, "Cannot reach the server")
        self._ask_for_a_code()
        self._type()
        with mock.patch.object(self.window, "go_back") as back:
            self.window.reset_password()
        self.assertIn("password was changed", self.box.information.call_args[0][2])
        self.sign_in.offer.assert_called_once_with("ann")
        back.assert_called_once()

    def test_a_new_code_goes_to_the_same_address_or_another_address_can_be_given(self):
        self._ask_for_a_code()
        self.window.send_new_code()
        self.assertEqual(self.api.request_password_reset.call_args_list, [mock.call("ann@example.com")] * 2)
        self.window.ask_for_email()
        self.assertEqual(self.window.steps.currentIndex(), 0)

    def test_what_is_not_an_address_is_not_sent(self):
        self._ask_for_a_code("not-an-address")
        self.api.request_password_reset.assert_not_called()
        self.assertEqual(self.window.steps.currentIndex(), 0)

    def test_the_sign_in_window_offers_the_account_whose_password_was_reset(self):
        window = SignInWindow()
        window.offer("ann")
        self.assertEqual((window.username.text(), window.password.text()), ("ann", ""))
        window.close()


def open_window(window):
    """Show a window and let it finish opening. A sign-in window fades in a moment after it is first shown, and
    raises itself then - which hides a tooltip shown in between."""
    window.show()
    if isinstance(window, AuthWindow):
        deadline = time.monotonic() + 5
        while not hasattr(window, "_fade_anim"):  # what WindowTransition.fade_in leaves on it
            if time.monotonic() > deadline:
                raise AssertionError(f"{window.windowTitle()} did not fade in")
            QTest.qWait(10)
    APP.processEvents()


def shown_tooltip(widget):
    """The widget's tooltip as Qt shows it: a window of its own, styled by the style sheets around the widget.
    A tooltip hides at a focus or activation event, which a window shown moments ago may still have coming."""
    for _ in range(2):
        APP.processEvents()
        QToolTip.showText(widget.mapToGlobal(QPoint(2, 2)), widget.toolTip(), widget)
        APP.processEvents()
        tip = next((top for top in APP.topLevelWidgets()
                    if top.metaObject().className() == "QTipLabel" and top.isVisible()), None)
        if tip is not None:
            return tip
    return None


def tooltip_problem(widget):
    """None when the widget's tooltip can be read, else what is wrong with it"""
    tip = shown_tooltip(widget)
    try:
        if tip is None:
            return "it is not shown"
        image = tip.grab().toImage()
        background = image.pixelColor(2, image.height() // 2)
        if background.alpha() < 255:
            # Nothing is behind a window of its own: what it does not paint is black on screen
            return f"its background is not opaque ({background.name(QColor.NameFormat.HexArgb)}): a black box"
        text = max((image.pixelColor(x, y) for x in range(4, image.width() - 4, 2)
                    for y in range(3, image.height() - 3)), key=lambda color: contrast(color, background))
        ratio = contrast(text, background)
        return None if ratio > 4.5 else f"its text has a contrast of only {ratio:.2f}"
    finally:
        QToolTip.hideText()
        APP.processEvents()


class TooltipTest(unittest.TestCase):
    """Qt styles a tooltip with the style sheets of the widget showing it and of every widget around it. A sheet
    without a selector reaches the tooltips too: a transparent background made them black boxes (a tooltip is a
    window of its own, with nothing behind it), a dark one put their black text on it. A QWidget or QLabel
    selector reaches every widget but no tooltip - those only answer to QToolTip."""

    def assert_tooltips_readable(self, window, name):
        checked = 0
        for widget in [window] + window.findChildren(QWidget):
            if widget.isVisible() and widget.toolTip():
                problem = tooltip_problem(widget)
                self.assertIsNone(problem, f"{name}: the tooltip of {type(widget).__name__} "
                                           f"'{' '.join(widget.toolTip().split())[:50]}': {problem}")
                checked += 1
        self.assertGreater(checked, 0, f"{name}: no tooltip found to check")

    def test_every_tooltip_of_the_dashboard_can_be_read(self):
        api = FakeApi()
        window = DashboardWindow(api, db=FakeDb(api))
        window.resize(1500, 900)
        window.show()
        window.sidebar_widget.activate_database(1)
        window.sql_builder.add_field("customers", "name", "text")
        window.sql_builder.add_field("orders", "total", "numeric(10,2)")
        window.sql_builder.add_filter(Filter("customers", "id", "int", ">", ("5",)))
        APP.processEvents()
        self.assert_tooltips_readable(window, "diagram")

        db_item = window.sidebar_widget.databases[1]["item"]
        window.sidebar_widget.on_tree_click(next(db_item.child(i) for i in range(db_item.childCount())
                                                 if db_item.child(i).data(0, 257) == "customers"))
        APP.processEvents()
        self.assert_tooltips_readable(window, "table page")
        page = window.stacked_center.currentWidget()
        page.table.setCurrentCell(0, 0)
        page.open_value_panel()
        APP.processEvents()
        self.assert_tooltips_readable(page.value_panel, "value panel")
        TableDetailsPage.value_panel_open = False
        with mock.patch("dbmanager.ui.dashboard.dashboard_window.confirm", return_value=True):
            window.close()

    def test_every_tooltip_of_the_sign_in_windows_can_be_read(self):
        sign_in = SignInWindow()
        forgot = ForgotPasswordWindow(sign_in, None)
        with mock.patch("dbmanager.ui.auth.forgot_password.ApiClient") as client:
            client.return_value.request_password_reset.return_value = "A code was sent to ann@example.com."
            forgot.email_input.setText("ann@example.com")
            forgot.send_code()  # on to the second step, which has a tooltip of its own
        for window, name in ((sign_in, "sign in"), (SignUpWindow(sign_in, None), "sign up"), (forgot, "forgot")):
            open_window(window)
            self.assert_tooltips_readable(window, name)
            window.close()


def text_rect(edit):
    """Where a line edit draws its text: inside its border, padding and text margins"""
    option = QStyleOptionFrame()
    edit.initStyleOption(option)
    rect = edit.style().subElementRect(QStyle.SubElement.SE_LineEditContents, option, edit)
    return rect.marginsRemoved(edit.textMargins())


class TextRoomTest(unittest.TestCase):
    """A fixed size smaller than what a padded field needs squeezes it until its text is cut: the rename dialog
    was 150 pixels tall for 170 pixels of content, and showed half of every name."""

    def assert_text_fits(self, window, name):
        open_window(window)
        checked = 0
        for edit in window.findChildren(QLineEdit):
            if edit.isVisible():
                self.assertGreaterEqual(text_rect(edit).height(), edit.fontMetrics().height(),
                                        f"{name}: the text of '{edit.placeholderText() or edit.text()}' is cut")
                checked += 1
        window.close()
        self.assertGreater(checked, 0, f"{name}: no field found to check")

    def test_the_text_of_every_field_fits_in_it(self):
        api = FakeApi()
        sign_in = SignInWindow()
        for window, name in (
                (RenameDialog(None, "Rename Field", "Enter new field name:", "table3Name"), "rename"),
                (RenameDialog(None, "Default Value", "Default value for total (numeric(10,2)) - empty for none:",
                              ""), "default value"),
                (InputFieldsWindow(), "add field"), (InputTableNameWindow(None), "new table"),
                (InputDatabaseWindow(None), "database"), (PremiumDialog(None, api), "premium"),
                (ShareDatabaseDialog(None, api, SHOP), "share"), (DeleteAccountDialog(None, api, 3), "delete account"),
                (DatabasePasswordDialog(None, SHOP, "password authentication failed"), "database password"),
                (FilterDialog(None, "customers", "name", "varchar(80)", "POSTGRESQL"), "filter"),
                (sign_in, "sign in"), (SignUpWindow(sign_in, None), "sign up"),
                (ForgotPasswordWindow(sign_in, None), "forgot password")):
            self.assert_text_fits(window, name)

    def test_a_long_name_is_shown_whole_when_renaming(self):
        name = "a_rather_long_field_name_that_needs_room"
        dialog = RenameDialog(None, "Rename Field", "Enter new field name:", name)
        dialog.show()
        APP.processEvents()
        edit = dialog.line_edit
        self.assertGreaterEqual(text_rect(edit).width(), edit.fontMetrics().horizontalAdvance(name))
        self.assertGreaterEqual(dialog.findChild(QLabel).width(), dialog.findChild(QLabel).sizeHint().width())
        dialog.close()

    def test_a_password_field_is_as_tall_as_the_field_above_and_its_text_stops_before_the_eye(self):
        window = SignInWindow()
        open_window(window)
        self.assertEqual(window.password.height(), window.username.height())
        field = window.password.field
        self.assertLessEqual(field.mapTo(window.password, text_rect(field).topRight()).x(), window.password.toggle.x())
        window.close()


if __name__ == "__main__":
    unittest.main()
