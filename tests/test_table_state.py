import unittest
from datetime import date
from decimal import Decimal

from dbmanager.model.change_script import build_change_script, parents_first
from dbmanager.model.table_state import TableState

PK = ["id", "int4", "Not Null", "PK", "-", "-"]
NAME = ["name", "varchar", "Null", "-", "-", "-"]
PRICE = ["price", "numeric", "Null", "-", "-", "-"]


def live_table(*rows):
    table = TableState("items", "POSTGRESQL", live=True)
    for column in (PK, NAME, PRICE):
        table.add_column(column, origin=column[0])
    table.load_rows(["id", "name", "price"], [list(row) for row in rows])
    return table


class LiveTableTest(unittest.TestCase):
    def test_nothing_to_save_right_after_loading(self):
        table = live_table([1, "pen", Decimal("1.50")], [2, None, None])
        self.assertFalse(table.has_changes())

    def test_retyping_the_same_value_changes_nothing(self):
        table = live_table([1, "pen", Decimal("1.50")])
        table.set_cell(0, 2, "1.50")
        table.set_cell(0, 1, "pen")
        self.assertEqual(table.data_statements(), [])

    def test_edit_finds_the_row_by_primary_key(self):
        table = live_table([1, "pen", Decimal("1.50")])
        table.set_cell(0, 1, "it's a pen")
        table.set_cell(0, 2, "2")
        self.assertEqual(table.data_statements(),
                         ["UPDATE items SET name = 'it''s a pen', price = 2 WHERE id = 1"])

    def test_typing_null_clears_a_value(self):
        table = live_table([1, "pen", Decimal("1.50")])
        table.set_cell(0, 2, "NULL")
        self.assertEqual(table.data_statements(), ["UPDATE items SET price = NULL WHERE id = 1"])

    def test_new_row_leaves_empty_cells_to_the_database(self):
        table = live_table()
        row = table.add_row()
        self.assertEqual(row, ["", "", ""])
        table.set_cell(0, 1, "cup")
        self.assertEqual(table.data_statements(), ["INSERT INTO items (name) VALUES ('cup')"])

    def test_deleted_rows(self):
        table = live_table([1, "pen", None], [2, "cup", None], [3, "box", None])
        table.delete_rows([2, 0])
        self.assertEqual([row[0] for row in table.rows], [2])
        self.assertEqual(table.data_statements(),
                         ["DELETE FROM items WHERE id = 3", "DELETE FROM items WHERE id = 1"])

    def test_without_a_primary_key_every_column_identifies_the_row(self):
        table = TableState("log", "POSTGRESQL", live=True)
        table.add_column(NAME, origin="name")
        table.add_column(PRICE, origin="price")
        table.load_rows(["name", "price"], [["pen", None]])
        table.set_cell(0, 0, "ink")
        self.assertEqual(table.data_statements(),
                         ["UPDATE log SET name = 'ink' WHERE name = 'pen' AND price IS NULL"])

    def test_column_changes_come_before_row_changes_and_use_the_new_names(self):
        table = live_table([1, "pen", None])
        table.rename_column(0, "item_id")
        table.delete_column(2)
        table.add_column(["stock", "int", "Null", "-", "-", "-", "-"])
        table.set_cell(0, 2, "7")
        self.assertEqual(table.schema_statements([]), [
            "ALTER TABLE items DROP COLUMN price",
            "ALTER TABLE items RENAME COLUMN id TO item_id",
            "ALTER TABLE items ADD COLUMN stock integer",
        ])
        self.assertEqual(table.data_statements(), ["UPDATE items SET stock = 7 WHERE item_id = 1"])

    def test_column_names_clash_regardless_of_case(self):
        table = live_table()
        self.assertTrue(table.has_column("NAME"))
        self.assertFalse(table.has_column("name", ignore_index=1))

    def test_dropping_replaces_every_other_change(self):
        table = live_table([1, "pen", None])
        table.set_cell(0, 1, "cup")
        table.pending_drop = True
        self.assertEqual(table.schema_statements([]), ["DROP TABLE items"])
        self.assertEqual(table.data_statements(), [])


class ViewTest(unittest.TestCase):
    def test_a_view_is_never_altered_but_can_be_dropped(self):
        view = TableState("v_items", "POSTGRESQL", live=True, view=True)
        view.add_column(PK, origin="id")
        view.load_rows(["id"], [[1]])
        view.set_cell(0, 0, "2")
        self.assertEqual(view.schema_statements([]), [])
        self.assertEqual(view.data_statements(), [])
        view.pending_drop = True
        self.assertEqual(view.schema_statements([]), ["DROP VIEW v_items"])


class NewTableTest(unittest.TestCase):
    def test_new_rows_get_starting_values(self):
        table = TableState("people", "POSTGRESQL")
        for column in (["id", "int", "Not Null", "PK", "-", "-", "-"], ["joined", "date", "Null", "-", "-", "-", "-"],
                       ["fee", "decimal", "Null", "-", "-", "-", "-"], ["note", "text", "Null", "-", "-", "-", "-"],
                       ["seq", "int", "Not Null", "-", "-", "-", "AUTO"]):
            table.add_column(column)
        self.assertEqual(table.add_row(), [1, date.today().isoformat(), "0", "", ""])
        self.assertEqual(table.add_row()[0], 2)

    def test_foreign_keys_start_empty(self):
        table = TableState("orders", "POSTGRESQL")
        table.add_column(["id", "int", "Not Null", "PK", "-", "-", "-"])
        table.add_column(["customer_id", "int", "Null", "FK", "-", "-", "-"])
        self.assertEqual(table.add_row(), [1, ""])
        self.assertEqual(table.add_column(["shop_id", "int", "Null", "FK", "-", "-", "-"]), [""])

    def test_create_then_insert(self):
        table = TableState("people", "POSTGRESQL")
        table.add_column(["id", "int", "Not Null", "PK", "-", "-", "-"])
        table.add_row()
        defaults = table.add_column(["age", "int", "Null", "-", "-", "-", "-"])
        self.assertEqual(defaults, [1])
        self.assertEqual(table.schema_statements([]), [
            "CREATE TABLE people (\n    id integer NOT NULL,\n    age integer,\n    PRIMARY KEY (id)\n)"])
        self.assertEqual(table.data_statements(), ["INSERT INTO people (id, age) VALUES (1, 1)"])


class ChangeScriptTest(unittest.TestCase):
    def test_parents_come_first_and_cycles_terminate(self):
        links = [("a", "id", "b", "a_id"), ("b", "id", "c", "b_id")]
        self.assertEqual(parents_first(["c", "b", "a"], links), ["a", "b", "c"])
        cyclic = [("a", "id", "b", "a_id"), ("b", "id", "a", "b_id")]
        self.assertEqual(sorted(parents_first(["a", "b"], cyclic)), ["a", "b"])

    def test_order_of_a_full_script(self):
        customers = TableState("customers", "POSTGRESQL")
        customers.add_column(["id", "int", "Not Null", "PK", "-", "-", "-"])
        orders = TableState("orders", "POSTGRESQL")
        orders.add_column(["id", "int", "Not Null", "PK", "-", "-", "-"])
        orders.add_column(["customer_id", "int", "Null", "FK", "-", "-", "-"])
        orders.add_row()
        old = TableState("old", "POSTGRESQL", live=True)
        old.add_column(PK, origin="id")
        old.pending_drop = True
        items = live_table()
        items.add_column(["order_id", "int", "Null", "FK", "-", "-", "-"])

        links = [("customers", "id", "orders", "customer_id"), ("orders", "id", "items", "order_id")]
        script = build_change_script({"orders": orders, "items": items, "old": old, "customers": customers},
                                     links, set(), "POSTGRESQL")
        self.assertEqual(script[0], "DROP TABLE old")
        self.assertEqual(script[1], "ALTER TABLE items ADD COLUMN order_id integer")
        self.assertTrue(script[2].startswith("CREATE TABLE customers"))
        self.assertTrue(script[3].startswith("CREATE TABLE orders"))
        self.assertIn("FOREIGN KEY (customer_id) REFERENCES customers (id)", script[3])
        self.assertEqual(script[4], "ALTER TABLE items ADD FOREIGN KEY (order_id) REFERENCES orders (id)")
        self.assertEqual(script[5], "INSERT INTO orders (id) VALUES (1)")
        self.assertEqual(len(script), 6)

    def test_a_child_is_dropped_before_its_parent_even_when_the_link_left_the_diagram(self):
        parent, child = live_table(), live_table()
        parent.name, child.name = "parents", "children"
        parent.pending_drop = child.pending_drop = True
        link = ("parents", "id", "children", "name")
        script = build_change_script({"parents": parent, "children": child}, [], {link}, "POSTGRESQL")
        self.assertEqual(script, ["DROP TABLE children", "DROP TABLE parents"])

    def test_foreign_keys_the_database_already_has_are_not_added_again(self):
        parent, child = live_table(), live_table()
        parent.name, child.name = "parents", "children"
        link = ("parents", "id", "children", "name")
        self.assertEqual(build_change_script({"parents": parent, "children": child}, [link], {link}, "POSTGRESQL"), [])
        self.assertEqual(len(build_change_script({"parents": parent, "children": child}, [link], set(), "POSTGRESQL")), 1)


if __name__ == "__main__":
    unittest.main()
