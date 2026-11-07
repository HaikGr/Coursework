import unittest
from datetime import date
from decimal import Decimal

from dbmanager.model.change_script import build_change_script, parents_first, references_to
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


def read_table(db_type, constraints=(), details=None, nullable_code=True, rows=((1, "a"), (2, None))):
    """A live table as the schema reader gives it: id (PK) and code"""
    table = TableState("items", db_type, live=True, constraints=[dict(c) for c in constraints])
    table.add_column(["id", "int", "Not Null", "PK", "-", "-"], origin="id", details={"sqlType": "int"})
    table.add_column(["code", "varchar", "Null" if nullable_code else "Not Null", "-", "-", "-"], origin="code",
                     details=details if details is not None else {"sqlType": "varchar(20)"})
    table.load_rows(["id", "code"], [list(row) for row in rows])
    return table


class NotNullTest(unittest.TestCase):
    def test_a_new_not_null_field_is_added_open_then_required_after_its_values(self):
        table = read_table("POSTGRESQL")
        table.add_column(["qty", "int", "Not Null", "-", "-", "-", "-"])
        self.assertEqual(table.schema_statements([]), ["ALTER TABLE items ADD COLUMN qty integer"])
        self.assertIn("rows 1 and 2 have none", table.problems()[0])
        table.set_cell(0, 2, "3")
        table.set_cell(1, 2, "4")
        self.assertEqual(table.problems(), [])
        self.assertEqual(table.data_statements(), ["UPDATE items SET qty = 3 WHERE id = 1",
                                                   "UPDATE items SET qty = 4 WHERE id = 2"])
        self.assertEqual(table.late_statements(), ["ALTER TABLE items ALTER COLUMN qty SET NOT NULL"])

    def test_the_same_on_sql_server_and_mysql_restates_the_type(self):
        for db_type, expected in (("SQLSERVER", "ALTER TABLE items ALTER COLUMN qty INT NOT NULL"),
                                  ("MYSQL", "ALTER TABLE items MODIFY COLUMN qty INT NOT NULL")):
            table = read_table(db_type, rows=())
            table.add_column(["qty", "int", "Not Null", "-", "-", "-", "-"])
            self.assertEqual(table.late_statements(), [expected])
            self.assertEqual(table.problems(), [], "an empty table needs no values")

    def test_a_default_value_fills_the_rows_in_one_statement(self):
        table = read_table("POSTGRESQL")
        defaults = table.add_column(["stock", "int", "Not Null", "-", "-", "-", "-", "5"])
        self.assertEqual(defaults, ["5", "5"])
        self.assertEqual(table.schema_statements([]),
                         ["ALTER TABLE items ADD COLUMN stock integer NOT NULL DEFAULT 5"])
        self.assertEqual(table.data_statements(), [], "the rows show the default: nothing to update")
        self.assertEqual(table.late_statements(), [])
        self.assertEqual(table.problems(), [])

    def test_a_default_given_later_fills_the_empty_rows(self):
        table = read_table("POSTGRESQL")
        table.add_column(["qty", "int", "Not Null", "-", "-", "-", "-"])
        table.set_cell(1, 2, "9")
        self.assertEqual(table.set_default(2, "7"), [(0, "7")], "a value typed already is kept")
        self.assertEqual(table.problems(), [])
        self.assertEqual(table.schema_statements([]), ["ALTER TABLE items ADD COLUMN qty integer NOT NULL DEFAULT 7"])
        self.assertEqual(table.data_statements(), ["UPDATE items SET qty = 9 WHERE id = 2"])
        self.assertEqual(table.late_statements(), [])
        table.set_cell(0, 2, "")
        self.assertIn("row 1 has none", table.problems()[0], "clearing it again would write NULL")
        table.add_row()
        self.assertIn("row 1 has none", table.problems()[0], "a new row left empty gets the default")

    def test_sql_server_names_its_default_and_fills_a_nullable_column_too(self):
        table = read_table("SQLSERVER")
        table.add_column(["note", "varchar", "Null", "-", "-", "-", "-", "n/a"])
        self.assertEqual(table.schema_statements([]),
                         ["ALTER TABLE items ADD note VARCHAR(255) CONSTRAINT DF_items_note DEFAULT N'n/a' WITH VALUES"])

    def test_more_rows_than_shown_need_a_default(self):
        table = read_table("POSTGRESQL")
        table.rows_truncated = True
        table.add_column(["qty", "int", "Not Null", "-", "-", "-", "-"])
        self.assertIn("may have more rows than are shown", table.problems()[0])

    def test_requiring_a_value_fills_the_empty_rows_after_the_edits(self):
        table = read_table("POSTGRESQL")
        table.set_nullable(1, False)
        self.assertIn("row 2 has none", table.problems()[0])
        table.set_nullable(1, False, fill="none")
        self.assertEqual(table.problems(), [])
        self.assertEqual(table.schema_statements([]), [])
        self.assertEqual(table.late_statements(), ["UPDATE items SET code = 'none' WHERE code IS NULL",
                                                   "ALTER TABLE items ALTER COLUMN code SET NOT NULL"])

    def test_a_value_typed_in_the_empty_row_is_enough(self):
        table = read_table("POSTGRESQL")
        table.set_nullable(1, False)
        table.set_cell(1, 1, "b")
        self.assertEqual(table.problems(), [])
        self.assertEqual(table.data_statements(), ["UPDATE items SET code = 'b' WHERE id = 2"])
        self.assertEqual(table.late_statements(), ["ALTER TABLE items ALTER COLUMN code SET NOT NULL"])

    def test_mysql_restates_the_whole_column(self):
        mysql = {"default": "'x'", "attributes": ["ON UPDATE CURRENT_TIMESTAMP"], "charset": "latin1",
                 "collation": "latin1_bin", "comment": "it's kept", "generated": False}
        table = read_table("MYSQL", details={"sqlType": "varchar(20)", "mysql": mysql}, rows=((1, "a"),))
        table.set_nullable(1, False)
        self.assertEqual(table.late_statements(), [
            "ALTER TABLE items MODIFY COLUMN code varchar(20) CHARACTER SET latin1 COLLATE latin1_bin NOT NULL "
            "DEFAULT 'x' ON UPDATE CURRENT_TIMESTAMP COMMENT 'it''s kept'"])

    def test_allowing_null_comes_before_the_rows(self):
        table = read_table("SQLSERVER", nullable_code=False, details={"sqlType": "nvarchar(20)"})
        table.set_nullable(1, True)
        self.assertEqual(table.schema_statements([]), ["ALTER TABLE items ALTER COLUMN code nvarchar(20) NULL"])
        self.assertEqual(table.late_statements(), [])

    def test_without_the_exact_type_sql_server_is_not_guessed_at(self):
        table = read_table("SQLSERVER", details={})
        table.set_nullable(1, False, fill="x")
        self.assertIn("exact type is not known", table.problems()[0])


FK_TO_CODE = {"kind": "FOREIGN KEY", "name": "fk_orders_code", "columns": ["item_code"],
              "refTable": "items", "refColumns": ["code"]}


class DropTest(unittest.TestCase):
    def orders(self, db_type):
        orders = TableState("orders", db_type, live=True, constraints=[FK_TO_CODE])
        orders.add_column(["id", "int", "Not Null", "PK", "-", "-"], origin="id")
        orders.add_column(["item_code", "varchar", "Null", "FK", "items", "code"], origin="item_code")
        return orders

    def test_a_column_others_point_at_loses_those_keys_first(self):
        items, orders = read_table("POSTGRESQL"), self.orders("POSTGRESQL")
        items.delete_column(1)
        script = build_change_script({"items": items, "orders": orders}, [], set(), "POSTGRESQL")
        self.assertEqual(script, ["ALTER TABLE orders DROP CONSTRAINT fk_orders_code",
                                  "ALTER TABLE items DROP COLUMN code"])

    def test_a_table_others_point_at_loses_those_keys_first(self):
        items, orders = read_table("MYSQL"), self.orders("MYSQL")
        items.pending_drop = True
        script = build_change_script({"items": items, "orders": orders}, [], set(), "MYSQL")
        self.assertEqual(script, ["ALTER TABLE orders DROP FOREIGN KEY fk_orders_code", "DROP TABLE items"])

    def test_a_table_dropped_with_its_children_needs_no_key_dropped(self):
        items, orders = read_table("POSTGRESQL"), self.orders("POSTGRESQL")
        items.pending_drop = orders.pending_drop = True
        link = ("items", "code", "orders", "item_code")
        script = build_change_script({"items": items, "orders": orders}, [], {link}, "POSTGRESQL")
        self.assertEqual(script, ["DROP TABLE orders", "DROP TABLE items"])

    def test_sql_server_drops_what_hangs_on_the_column_first(self):
        own = [{"kind": "DEFAULT", "name": "DF_code", "columns": ["code"]},
               {"kind": "INDEX", "name": "ix_code", "columns": ["code", "id"]},
               {"kind": "FOREIGN KEY", "name": "fk_code", "columns": ["code"], "refTable": "codes",
                "refColumns": ["code"]},
               {"kind": "PRIMARY KEY", "name": "pk_items", "columns": ["id"]}]
        table = read_table("SQLSERVER", constraints=own)
        table.delete_column(1)
        self.assertEqual(table.schema_statements([]), ["ALTER TABLE items DROP CONSTRAINT fk_code",
                                                       "ALTER TABLE items DROP CONSTRAINT DF_code",
                                                       "DROP INDEX ix_code ON items",
                                                       "ALTER TABLE items DROP COLUMN code"])

    def test_mysql_drops_a_columns_own_foreign_key_and_postgresql_needs_not(self):
        fk = {"kind": "FOREIGN KEY", "name": "fk_code", "columns": ["code"], "refTable": "codes", "refColumns": ["c"]}
        mysql = read_table("MYSQL", constraints=[fk])
        mysql.delete_column(1)
        self.assertEqual(mysql.schema_statements([]), ["ALTER TABLE items DROP FOREIGN KEY fk_code",
                                                       "ALTER TABLE items DROP COLUMN code"])
        postgres = read_table("POSTGRESQL", constraints=[fk])
        postgres.delete_column(1)
        self.assertEqual(postgres.schema_statements([]), ["ALTER TABLE items DROP COLUMN code"])

    def test_who_points_here(self):
        items, orders = read_table("POSTGRESQL"), self.orders("POSTGRESQL")
        tables = {"items": items, "orders": orders}
        self.assertEqual(references_to(tables, "items"), [("orders", FK_TO_CODE)])
        self.assertEqual(references_to(tables, "items", "code"), [("orders", FK_TO_CODE)])
        self.assertEqual(references_to(tables, "items", "id"), [])


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
