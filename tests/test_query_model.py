"""The query built on the diagram: the SELECT it writes for each database, without any widget."""

import unittest

from dbmanager.model.query import Filter, Join, QueryModel, aggregate_problem, operators_for

LINKS = [("customers", "id", "orders", "customer_id"), ("orders", "id", "items", "order_id")]


def shop():
    model = QueryModel()
    model.links = list(LINKS)
    return model


class SelectTest(unittest.TestCase):
    def test_nothing_picked_is_no_query(self):
        self.assertEqual(QueryModel().build("POSTGRESQL"), ("", []))

    def test_plain_columns(self):
        model = shop()
        model.add_column("customers", "name", "varchar(80)")
        model.add_column("customers", "id", "int")
        self.assertEqual(model.build("POSTGRESQL")[0], "SELECT customers.name,\n       customers.id\nFROM customers")

    def test_a_column_is_added_once(self):
        model = shop()
        self.assertIsNotNone(model.add_column("customers", "id"))
        self.assertIsNone(model.add_column("customers", "id"))
        self.assertEqual(len(model.columns), 1)

    def test_names_are_quoted_for_the_database(self):
        model = shop()
        model.add_column("Order Items", "Qty")
        self.assertEqual(model.build("POSTGRESQL")[0], 'SELECT "Order Items"."Qty"\nFROM "Order Items"')
        self.assertEqual(model.build("MYSQL")[0], "SELECT `Order Items`.Qty\nFROM `Order Items`")
        self.assertEqual(model.build("SQLSERVER")[0], "SELECT [Order Items].Qty\nFROM [Order Items]")

    def test_columns_with_the_same_name_are_told_apart(self):
        model = shop()
        model.add_column("customers", "id")
        model.add_column("orders", "id")
        sql = model.build("POSTGRESQL")[0]
        self.assertIn("SELECT customers.id AS customers_id,\n       orders.id AS orders_id", sql)


class AggregateTest(unittest.TestCase):
    def test_summarising_a_column_groups_by_the_others(self):
        model = shop()
        model.add_column("customers", "name", "varchar(80)")
        model.add_column("orders", "total", "numeric(10,2)")
        model.set_aggregate("orders", "total", "SUM")
        self.assertTrue(model.is_group_key("customers", "name"))
        self.assertFalse(model.is_group_key("orders", "total"))
        self.assertEqual(model.build("POSTGRESQL")[0],
                         "SELECT customers.name,\n       SUM(orders.total) AS sum_total\n"
                         "FROM customers\nJOIN orders ON customers.id = orders.customer_id\n"
                         "GROUP BY customers.name")

    def test_only_summaries_need_no_group_by(self):
        model = shop()
        model.add_column("orders", "total", "numeric")
        model.set_aggregate("orders", "total", "AVG")
        self.assertEqual(model.build("POSTGRESQL")[0], "SELECT AVG(orders.total) AS avg_total\nFROM orders")

    def test_count_unique(self):
        model = shop()
        model.add_column("orders", "customer_id", "int")
        model.set_aggregate("orders", "customer_id", "COUNT_DISTINCT")
        self.assertIn("COUNT(DISTINCT orders.customer_id) AS count_distinct_customer_id", model.build("MYSQL")[0])

    def test_count_rows_counts_each_group(self):
        model = shop()
        model.add_column("customers", "name")
        model.count_rows = True
        self.assertEqual(model.build("POSTGRESQL")[0],
                         "SELECT customers.name,\n       COUNT(*) AS row_count\nFROM customers\n"
                         "GROUP BY customers.name")

    def test_sum_needs_numbers(self):
        self.assertIsNone(aggregate_problem("SUM", "orders.total", "decimal(18,2)"))
        self.assertIsNone(aggregate_problem("SUM", "orders.total", ""))  # not known: allowed
        self.assertIsNone(aggregate_problem("MAX", "customers.name", "varchar(80)"))
        self.assertIn("works on numbers", aggregate_problem("AVG", "customers.name", "varchar(80)"))
        model = shop()
        model.add_column("customers", "name", "text")
        model.set_aggregate("customers", "name", "SUM")
        self.assertEqual(len(model.build("POSTGRESQL")[1]), 1)


class SortAndLimitTest(unittest.TestCase):
    def test_sorted_in_the_order_the_sorts_were_set(self):
        model = shop()
        model.add_column("customers", "name")
        model.add_column("customers", "id")
        model.set_sort("customers", "id", "DESC")
        model.set_sort("customers", "name", "ASC")
        self.assertTrue(model.build("POSTGRESQL")[0].endswith("ORDER BY customers.id DESC, customers.name ASC"))
        self.assertEqual(model.sort_rank("customers", "id"), 1)
        model.set_sort("customers", "id", None)
        self.assertIsNone(model.sort_rank("customers", "name"))  # one sort left: no number needed

    def test_a_summary_sorts_by_its_value(self):
        model = shop()
        model.add_column("orders", "total", "int")
        model.set_aggregate("orders", "total", "SUM")
        model.set_sort("orders", "total", "DESC")
        self.assertIn("ORDER BY SUM(orders.total) DESC", model.build("POSTGRESQL")[0])

    def test_limit_and_distinct_per_database(self):
        model = shop()
        model.add_column("customers", "name")
        model.distinct, model.limit = True, 10
        self.assertEqual(model.build("POSTGRESQL")[0], "SELECT DISTINCT customers.name\nFROM customers\nLIMIT 10")
        self.assertEqual(model.build("SQLSERVER")[0], "SELECT DISTINCT TOP (10) customers.name\nFROM customers")

    def test_clear_forgets_the_choices_but_not_the_links(self):
        model = shop()
        model.add_column("customers", "name")
        model.distinct = model.count_rows = True
        model.clear()
        self.assertTrue(model.is_empty())
        self.assertFalse(model.distinct or model.count_rows)
        self.assertEqual(model.links, LINKS)


class FilterTest(unittest.TestCase):
    def sql(self, condition, db_type="POSTGRESQL"):
        return condition.sql(f"{condition.table}.{condition.column}", db_type)

    def test_values_are_quoted_for_their_type(self):
        self.assertEqual(self.sql(Filter("orders", "total", "int", ">", ("100",))), "orders.total > 100")
        self.assertEqual(self.sql(Filter("customers", "name", "varchar", "=", ("O'Hara",))),
                         "customers.name = 'O''Hara'")
        self.assertEqual(self.sql(Filter("customers", "name", "varchar", "=", ("Ann",)), "SQLSERVER"),
                         "customers.name = N'Ann'")

    def test_between_and_lists(self):
        self.assertEqual(self.sql(Filter("orders", "total", "int", "BETWEEN", ("1", "5"))),
                         "orders.total BETWEEN 1 AND 5")
        self.assertEqual(self.sql(Filter("customers", "name", "text", "IN", ("Ann, Bob ,",))),
                         "customers.name IN ('Ann', 'Bob')")
        self.assertEqual(self.sql(Filter("orders", "id", "int", "NOT IN", ("1,2",))), "orders.id NOT IN (1, 2)")

    def test_empty_and_not_empty(self):
        self.assertEqual(self.sql(Filter("customers", "name", "text", "IS NULL")), "customers.name IS NULL")
        self.assertEqual(self.sql(Filter("customers", "name", "text", "IS NOT NULL")), "customers.name IS NOT NULL")

    def test_contains_matches_the_text_as_typed(self):
        condition = Filter("products", "code", "varchar", "CONTAINS", ("50%_off",))
        self.assertEqual(self.sql(condition), r"products.code ILIKE '%50\%\_off%'")
        self.assertEqual(self.sql(condition, "MYSQL"), r"products.code LIKE '%50\\%\\_off%'")
        self.assertEqual(self.sql(condition, "SQLSERVER"), "products.code LIKE N'%50[%][_]off%'")
        self.assertEqual(self.sql(Filter("p", "c", "text", "STARTS", ("ab",))), "p.c ILIKE 'ab%'")
        self.assertEqual(self.sql(Filter("p", "c", "text", "ENDS", ("ab",)), "MARIADB"), "p.c LIKE '%ab'")

    def test_custom_sql_is_kept_as_typed(self):
        self.assertEqual(self.sql(Filter("orders", "total", "int", "SQL", ("> 5 OR orders.total IS NULL",))),
                         "orders.total > 5 OR orders.total IS NULL")

    def test_problems(self):
        self.assertEqual(Filter("o", "t", "int", ">", ("",)).problem(), "Type a value")
        self.assertIn("holds numbers", Filter("o", "t", "int", ">", ("abc",)).problem())
        self.assertIsNone(Filter("o", "t", "int", ">", ("$1 200.50",)).problem())
        self.assertIn("is empty", Filter("o", "t", "text", "=", ("null",)).problem())
        self.assertEqual(Filter("o", "t", "int", "BETWEEN", ("1", "")).problem(), "Type both values")
        self.assertIn("at least one", Filter("o", "t", "int", "IN", (" , ",)).problem())
        self.assertIsNone(Filter("o", "t", "text", "IS NULL").problem())
        self.assertIsNone(Filter("o", "t", "varchar", "CONTAINS", ("abc",)).problem())

    def test_text_operators_only_for_text(self):
        keys = lambda type_name: {operator.key for operator in operators_for(type_name)}  # noqa: E731
        self.assertIn("CONTAINS", keys("varchar(20)"))
        self.assertIn("CONTAINS", keys(""))  # not known
        self.assertNotIn("CONTAINS", keys("int"))
        self.assertIn("BETWEEN", keys("int"))

    def test_described_in_words(self):
        self.assertEqual(Filter("orders", "total", "int", ">=", ("10",)).describe(), "orders.total >= 10")
        self.assertEqual(Filter("c", "name", "text", "CONTAINS", ("an",)).describe(), 'c.name contains "an"')
        self.assertEqual(Filter("c", "name", "text", "IS NULL").describe(), "c.name is empty (NULL)")
        self.assertEqual(Filter("o", "total", "int", ">", ("5",), aggregate="SUM").describe(), "SUM(o.total) > 5")

    def test_where_and_having_in_one_query(self):
        model = shop()
        model.add_column("customers", "name", "text")
        model.add_column("orders", "total", "int")
        model.set_aggregate("orders", "total", "SUM")
        model.add_filter(Filter("customers", "name", "text", "STARTS", ("A",)))
        model.add_filter(Filter("orders", "total", "int", ">", ("100",), aggregate="SUM"))
        self.assertEqual(model.build("POSTGRESQL")[0],
                         "SELECT customers.name,\n       SUM(orders.total) AS sum_total\n"
                         "FROM customers\nJOIN orders ON customers.id = orders.customer_id\n"
                         "WHERE customers.name ILIKE 'A%'\nGROUP BY customers.name\n"
                         "HAVING SUM(orders.total) > 100")

    def test_a_count_is_compared_as_a_number(self):
        condition = Filter("customers", "name", "text", ">", ("2",), aggregate="COUNT")
        self.assertIsNone(condition.problem())
        self.assertEqual(self.sql(condition), "COUNT(customers.name) > 2")

    def test_match_any(self):
        model = shop()
        model.add_column("orders", "id")
        model.add_filter(Filter("orders", "total", "int", ">", ("100",)))
        model.add_filter(Filter("orders", "total", "int", "SQL", ("< 0 AND orders.id > 3",)))
        model.match_any = True
        self.assertIn("WHERE orders.total > 100\n   OR (orders.total < 0 AND orders.id > 3)",
                      model.build("POSTGRESQL")[0])

    def test_only_filters_shows_every_column(self):
        model = shop()
        model.add_filter(Filter("orders", "total", "int", ">", ("5",)))
        self.assertEqual(model.build("POSTGRESQL")[0], "SELECT *\nFROM orders\nWHERE orders.total > 5")

    def test_a_broken_filter_is_left_out_with_a_warning(self):
        model = shop()
        model.add_column("orders", "id")
        model.add_filter(Filter("orders", "total", "int", ">", ("lots",)))
        sql, warnings = model.build("POSTGRESQL")
        self.assertNotIn("WHERE", sql)
        self.assertIn("left out", warnings[0])


class JoinTest(unittest.TestCase):
    def test_through_a_table_in_between(self):
        model = shop()
        model.add_column("customers", "name")
        model.add_column("items", "qty")
        sql, warnings = model.build("POSTGRESQL")
        self.assertEqual(warnings, [])
        self.assertIn("FROM customers\nJOIN orders ON customers.id = orders.customer_id\n"
                      "JOIN items ON orders.id = items.order_id", sql)

    def test_a_filter_brings_its_table_in(self):
        model = shop()
        model.add_column("customers", "name")
        model.add_filter(Filter("orders", "total", "int", ">", ("5",)))
        self.assertIn("JOIN orders ON customers.id = orders.customer_id\nWHERE orders.total > 5",
                      model.build("POSTGRESQL")[0])

    def test_an_unlinked_table_is_cross_joined_with_a_warning(self):
        model = shop()
        model.add_column("customers", "name")
        model.add_column("products", "title")
        sql, warnings = model.build("POSTGRESQL")
        self.assertIn("FROM customers\nCROSS JOIN products", sql)
        self.assertIn("products is not joined", warnings[0])
        self.assertEqual(model.unjoined, ["products"])

    def test_a_join_of_the_query_joins_on_any_two_fields(self):
        model = shop()
        model.add_column("customers", "name")
        model.add_column("products", "title")
        model.add_join(Join("customers", "favourite", "products", "code"))
        sql, warnings = model.build("POSTGRESQL")
        self.assertEqual(warnings, [])
        self.assertEqual(model.unjoined, [])
        self.assertIn("FROM customers\nJOIN products ON customers.favourite = products.code", sql)

    def test_a_left_join_keeps_the_rows_without_a_match(self):
        model = shop()
        model.add_column("customers", "name")
        model.add_column("orders", "total")
        model.add_join(Join("customers", "id", "orders", "customer_id", "LEFT"))
        self.assertIn("FROM customers\nLEFT JOIN orders ON customers.id = orders.customer_id",
                      model.build("POSTGRESQL")[0])

    def test_a_left_join_reached_from_its_right_side_keeps_its_meaning(self):
        model = shop()
        model.add_column("orders", "total")  # orders comes first now
        model.add_column("customers", "name")
        model.add_join(Join("customers", "id", "orders", "customer_id", "LEFT"))
        self.assertIn("FROM orders\nRIGHT JOIN customers ON orders.customer_id = customers.id",
                      model.build("POSTGRESQL")[0])

    def test_the_querys_own_join_wins_over_a_link(self):
        model = shop()  # customers.id = orders.customer_id is linked on the diagram
        model.add_column("customers", "name")
        model.add_column("orders", "total")
        model.add_join(Join("customers", "email", "orders", "contact"))
        self.assertIn("JOIN orders ON customers.email = orders.contact", model.build("POSTGRESQL")[0])

    def test_joins_follow_the_schema_and_go_with_clear(self):
        model = shop()
        model.add_join(Join("customers", "id", "orders", "customer_id"))
        model.rename_column("orders", "customer_id", "buyer_id")
        self.assertEqual(model.joins[0].right_column, "buyer_id")
        model.drop_column("orders", "buyer_id")
        self.assertEqual(model.joins, [])
        model.add_join(Join("customers", "id", "orders", "id"))
        self.assertTrue(model.keep_only({"customers": {"id"}}))
        self.assertEqual(model.joins, [])
        model.add_join(Join("customers", "id", "orders", "id"))
        model.clear()
        self.assertEqual(model.joins, [])


class SchemaChangeTest(unittest.TestCase):
    def test_rename_and_drop(self):
        model = shop()
        model.add_column("orders", "total", "int")
        model.set_sort("orders", "total", "ASC")
        model.add_filter(Filter("orders", "total", "int", ">", ("1",)))
        model.rename_column("orders", "total", "amount")
        self.assertIn("ORDER BY orders.amount ASC", model.build("POSTGRESQL")[0])
        self.assertIn("WHERE orders.amount > 1", model.build("POSTGRESQL")[0])
        model.drop_column("orders", "amount")
        self.assertTrue(model.is_empty())

    def test_keep_only_what_the_database_still_has(self):
        model = shop()
        model.add_column("orders", "total")
        model.add_column("customers", "name")
        model.add_filter(Filter("orders", "note", "text", "IS NULL"))
        self.assertFalse(model.keep_only({"orders": {"total", "note"}, "customers": {"name"}}))
        self.assertTrue(model.keep_only({"customers": {"name"}}))
        self.assertEqual([entry.key for entry in model.columns], [("customers", "name")])
        self.assertEqual(model.filters, [])

    def test_drop_table(self):
        model = shop()
        model.add_column("orders", "total")
        model.add_column("customers", "name")
        model.add_filter(Filter("orders", "id", "int", "=", ("1",)))
        model.drop_table("orders")
        self.assertEqual([entry.key for entry in model.columns], [("customers", "name")])
        self.assertEqual(model.filters, [])


if __name__ == "__main__":
    unittest.main()


class LinkRuleTest(unittest.TestCase):
    def test_which_end_is_the_key(self):
        from dbmanager.model.links import End, plan_link
        customer_id = End("customers", "id", "int4", primary=True)
        buyer = End("orders", "buyer", "int8")
        self.assertEqual(plan_link(buyer, customer_id), (customer_id, buyer), "dragged either way")
        self.assertEqual(plan_link(customer_id, buyer), (customer_id, buyer))
        other_key = End("profiles", "id", "int4", primary=True)
        self.assertEqual(plan_link(customer_id, other_key), (customer_id, other_key), "one to one: from the source")

    def test_what_cannot_be_linked(self):
        from dbmanager.model.links import End, plan_link
        key = End("customers", "id", "int4", primary=True)
        self.assertIn("same table", plan_link(key, End("customers", "name", "varchar")))
        self.assertIn("Neither", plan_link(End("a", "x", "int"), End("b", "y", "int")))
        self.assertIn("same kind of values", plan_link(key, End("orders", "note", "text")))
        self.assertIsInstance(plan_link(key, End("orders", "ref", "")), tuple, "a type not known is let through")
