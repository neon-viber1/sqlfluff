"""Test the select_crawler module."""

import pytest

from sqlfluff.core.linter.linter import Linter
from sqlfluff.utils.analysis.query import Query


def _parse_and_crawl_outer(sql):
    """Helper function for select crawlers.

    Given a SQL statement this crawls the SQL and instantiates
    a Query on the outer relevant segment.
    """
    linter = Linter(dialect="ansi")
    parsed = linter.parse_string(sql)
    # Make sure it's fully parsable.
    assert "unparsable" not in parsed.tree.descendant_type_set
    # Create a crawler from the root segment.
    query = Query.from_root(parsed.tree, linter.dialect)
    # Analyse the segment.
    return query, linter


@pytest.mark.parametrize(
    "sql, expected_json",
    [
        (
            # Test trivial query.
            "select 1",
            {"selectables": ["select 1"]},
        ),
        (
            # Test set expression.
            "select 1 union select 2",
            {"selectables": ["select 1", "select 2"]},
        ),
        (
            # Test multiple CTEs.
            "with cte1 as (select 1 as x), cte2 as (select 2 as y) "
            "select * from cte1 join cte2 using (x)",
            {
                "ctes": {
                    "CTE1": {"selectables": ["select 1 as x"]},
                    "CTE2": {"selectables": ["select 2 as y"]},
                },
                "query_type": "WithCompound",
                "selectables": ["select * from cte1 join cte2 using (x)"],
            },
        ),
        (
            # Nested CTEs (from AM04 test suite)
            """
        with a as (
            with b as (select 1 from c)
            select * from b
        )
        select * from a
        """,
            {
                "ctes": {
                    "A": {
                        "ctes": {"B": {"selectables": ["select 1 from c"]}},
                        "query_type": "WithCompound",
                        "selectables": ["select * from b"],
                    }
                },
                "query_type": "WithCompound",
                "selectables": ["select * from a"],
            },
        ),
        (
            # Nested CTEs (from AM04 test suite)
            """
        with b as (select 1 from c)
        select * from (
            with a as (select * from b)
            select * from a
        )
        """,
            {
                "ctes": {"B": {"selectables": ["select 1 from c"]}},
                "query_type": "WithCompound",
                "selectables": [
                    "select * from (\n"
                    "            with a as (select * from b)\n"
                    "            select * from a\n"
                    "        )"
                ],
                "subqueries": [
                    # NOTE: Subquery from the FROM clause.
                    {
                        "ctes": {"A": {"selectables": ["select * from b"]}},
                        "query_type": "WithCompound",
                        "selectables": ["select * from a"],
                    },
                ],
            },
        ),
        (
            # Test that subquery in "from" not included.
            "select a.x from (select z from b)",
            {
                "selectables": ["select a.x from (select z from b)"],
                "subqueries": [{"selectables": ["select z from b"]}],
            },
        ),
        (
            # Test that subquery in "from" / "join" not included.
            "select a.x from a join (select z from b) as b on (a.x = b.x)",
            {
                "selectables": [
                    "select a.x from a join (select z from b) as b on (a.x = b.x)"
                ],
                "subqueries": [{"selectables": ["select z from b"]}],
            },
        ),
        (
            # In CTE main query, test that subquery in "from" not included.
            "with prep as (select 1) select a.x from (select z from b)",
            {
                "ctes": {"PREP": {"selectables": ["select 1"]}},
                "query_type": "WithCompound",
                "selectables": ["select a.x from (select z from b)"],
                "subqueries": [{"selectables": ["select z from b"]}],
            },
        ),
        (
            # In CTE main query, test that subquery in "from" / "join" not included.
            "with prep as (select 1) "
            "select a.x from a join (select z from b) as b on (a.x = b.x)",
            {
                "ctes": {"PREP": {"selectables": ["select 1"]}},
                "query_type": "WithCompound",
                "selectables": [
                    "select a.x from a join (select z from b) as b on (a.x = b.x)"
                ],
                "subqueries": [{"selectables": ["select z from b"]}],
            },
        ),
        (
            """with prep_1 as (
    with d as (
        select x, z from b
    )
    select * from d
)
select
    a.x, a.y, b.z
from a
join prep_1 using (x)
""",
            {
                "ctes": {
                    "PREP_1": {
                        "ctes": {
                            "D": {"selectables": ["select x, z from b"]},
                        },
                        "query_type": "WithCompound",
                        "selectables": ["select * from d"],
                    }
                },
                "query_type": "WithCompound",
                "selectables": [
                    "select\n    a.x, a.y, b.z\nfrom a\njoin prep_1 using (x)"
                ],
            },
        ),
        # Test with a UNION as the main selectable of a WITH
        (
            "with a as (select 1), b as (select 2) "
            "select * from a union select * from b\n",
            {
                "ctes": {
                    "A": {"selectables": ["select 1"]},
                    "B": {"selectables": ["select 2"]},
                },
                "query_type": "WithCompound",
                "selectables": [
                    "select * from a",
                    "select * from b",
                ],
            },
        ),
        # Test with a VALUES clause in a WITH
        (
            "WITH txt AS ( VALUES (1, 'foo') ) SELECT * FROM txt\n",
            {
                "ctes": {
                    "TXT": {"selectables": ["VALUES (1, 'foo')"]},
                },
                "query_type": "WithCompound",
                "selectables": [
                    "SELECT * FROM txt",
                ],
            },
        ),
        # Test with Subqueries
        (
            "SELECT (\n"
            "    SELECT other_table.other_table_field_1 FROM other_table\n"
            "    WHERE other_table.id = field_2\n"
            ") FROM\n"
            "(SELECT * FROM some_table) AS my_alias\n",
            {
                "selectables": [
                    "SELECT (\n"
                    "    SELECT other_table.other_table_field_1 FROM other_table\n"
                    "    WHERE other_table.id = field_2\n"
                    ") FROM\n"
                    "(SELECT * FROM some_table) AS my_alias",
                ],
                "subqueries": [
                    {
                        "selectables": [
                            "SELECT other_table.other_table_field_1 FROM other_table\n"
                            "    WHERE other_table.id = field_2",
                        ]
                    },
                    {"selectables": ["SELECT * FROM some_table"]},
                ],
            },
        ),
        # Test a MERGE
        (
            """MERGE INTO t USING (SELECT * FROM u) AS u ON (a = b)
WHEN MATCHED THEN
UPDATE SET a = b
WHEN NOT MATCHED THEN
INSERT (b) VALUES (c);""",
            {
                "selectables": [
                    """MERGE INTO t USING (SELECT * FROM u) AS u ON (a = b)
WHEN MATCHED THEN
UPDATE SET a = b
WHEN NOT MATCHED THEN
INSERT (b) VALUES (c)"""  # NOTE: No trailing semicolon
                ],
                "subqueries": [{"selectables": ["SELECT * FROM u"]}],
            },
        ),
        # Test a DELETE
        (
            """DELETE FROM agent1
WHERE EXISTS(
    SELECT customer.cust_id FROM customer
    WHERE agent1.agent_code <> customer.agent_code);""",
            {
                "selectables": [
                    """DELETE FROM agent1
WHERE EXISTS(
    SELECT customer.cust_id FROM customer
    WHERE agent1.agent_code <> customer.agent_code)"""
                ],
                "subqueries": [
                    {
                        "selectables": [
                            """SELECT customer.cust_id FROM customer
    WHERE agent1.agent_code <> customer.agent_code"""
                        ]
                    }
                ],
            },
        ),
        # Test an UPDATE
        (
            """UPDATE my_table
SET row_sum = (
    SELECT COUNT(*) AS row_sum
    FROM
        another_table
    WHERE
        another_table.id = my_tableeee.id
)""",
            {
                "selectables": [
                    """UPDATE my_table
SET row_sum = (
    SELECT COUNT(*) AS row_sum
    FROM
        another_table
    WHERE
        another_table.id = my_tableeee.id
)"""
                ],
                "subqueries": [
                    {
                        "selectables": [
                            """SELECT COUNT(*) AS row_sum
    FROM
        another_table
    WHERE
        another_table.id = my_tableeee.id"""
                        ]
                    }
                ],
            },
        ),
    ],
)
def test_select_crawler_constructor(sql, expected_json):
    """Test Query when created using constructor."""
    query, _ = _parse_and_crawl_outer(sql)
    assert all(cte.cte_definition_segment is not None for cte in query.ctes.values())
    query_dict = query.as_dict()
    assert expected_json == query_dict


def test_select_crawler_nested():
    """Test invoking with an outer from_expression_segment."""
    sql = """
select
    a.x, a.y, b.z
from a
join (
    with d as (
        select x, z from b
    )
    select * from d
) using (x)
    """
    query, linter = _parse_and_crawl_outer(sql)

    inner_from = (
        query.selectables[0].select_info.table_aliases[1].from_expression_element
    )
    inner_select = next(inner_from.recursive_crawl("with_compound_statement"))
    inner_query = Query.from_segment(inner_select, linter.dialect)
    assert inner_query.as_dict() == {
        "selectables": [
            "select * from d",
        ],
        "ctes": {"D": {"selectables": ["select x, z from b"]}},
        "query_type": "WithCompound",
    }


@pytest.mark.parametrize(
    "dialect, sql, expected_aliases, expected_references, child_aliases",
    [
        ("ansi", "UPDATE orders SET val = 1", ["orders"], ["orders"], []),
        ("ansi", "DELETE FROM orders", ["orders"], ["orders"], []),
        (
            "ansi",
            "MERGE INTO orders t USING shipments s ON t.id = s.id "
            "WHEN MATCHED THEN UPDATE SET val = s.val",
            ["t", "s"],
            ["orders", "shipments"],
            [],
        ),
        (
            "postgres",
            "DELETE FROM orders o USING shipments s JOIN packages p ON s.id = p.id "
            "WHERE EXISTS (SELECT 1 FROM aux a WHERE a.id = p.id)",
            ["o", "s", "p"],
            ["orders", "shipments", "packages"],
            ["a"],
        ),
        (
            "postgres",
            "UPDATE orders o SET status = (SELECT l.status FROM line_items l "
            "WHERE l.order_id = o.id) RETURNING status AS returned",
            ["o"],
            ["orders"],
            ["l"],
        ),
        (
            "postgres",
            "UPDATE orders SET status = s.status FROM shipments s "
            "WHERE EXISTS (SELECT 1 FROM items i WHERE i.id = s.id)",
            ["orders", "s"],
            ["orders", "shipments"],
            ["i"],
        ),
        (
            "postgres",
            "DELETE FROM orders o USING shipments s, packages p "
            "WHERE EXISTS (SELECT 1 FROM items i WHERE i.id = o.id) "
            "RETURNING o.id AS returned",
            ["o", "s", "p"],
            ["orders", "shipments", "packages"],
            ["i"],
        ),
        (
            "postgres",
            "DELETE FROM orders USING (SELECT id FROM shipments hidden) s "
            "WHERE orders.id = s.id RETURNING orders.id AS returned",
            ["orders", "s"],
            ["orders", None],
            ["hidden"],
        ),
        (
            "tsql",
            "MERGE INTO orders t USING (SELECT * FROM staging hidden) s "
            "ON t.id = s.id WHEN MATCHED THEN UPDATE SET t.val = "
            "(SELECT max(a.x) FROM aux a WHERE a.id = t.id);",
            ["t", "s"],
            ["orders", None],
            ["hidden", "a"],
        ),
        (
            "ansi",
            "MERGE INTO orders t USING shipments s ON t.id = s.id "
            "WHEN MATCHED THEN UPDATE SET val = "
            "(SELECT a.val FROM aux a WHERE a.id = s.id)",
            ["t", "s"],
            ["orders", "shipments"],
            ["a"],
        ),
        (
            "mysql",
            "UPDATE orders o JOIN shipments s ON o.id = s.id "
            "SET o.val = (SELECT a.val FROM aux a WHERE a.id = s.id)",
            ["o", "s"],
            ["orders", "shipments"],
            ["a"],
        ),
        (
            "mysql",
            "UPDATE orders, shipments s SET orders.val = "
            "(SELECT a.val FROM aux a WHERE a.id = s.id)",
            ["s", "orders"],
            ["shipments", "orders"],
            ["a"],
        ),
        (
            "tsql",
            "UPDATE o SET val = s.val FROM orders o JOIN shipments s ON o.id = s.id "
            "WHERE EXISTS (SELECT 1 FROM aux a WHERE a.id = o.id)",
            ["o", "o", "s"],
            ["o", "orders", "shipments"],
            ["a"],
        ),
        (
            "tsql",
            "DELETE o FROM orders o JOIN shipments s ON o.id = s.id "
            "WHERE EXISTS (SELECT 1 FROM aux a WHERE a.id = o.id)",
            ["o", "o", "s"],
            ["o", "orders", "shipments"],
            ["a"],
        ),
        (
            "postgres",
            "WITH pending AS (SELECT id FROM shipments) UPDATE orders o "
            "SET val = (SELECT p.id FROM pending p WHERE p.id = o.id)",
            ["o"],
            ["orders"],
            ["p"],
        ),
        (
            "postgres",
            "UPDATE orders o SET val = 1 RETURNING "
            "(SELECT a.val FROM aux a WHERE a.id = o.id) AS returned",
            ["o"],
            ["orders"],
            ["a"],
        ),
        (
            "ansi",
            "UPDATE orders SET val = (SELECT a.val FROM aux a WHERE a.id = orders.id)",
            ["orders"],
            ["orders"],
            ["a"],
        ),
        (
            "postgres",
            'DELETE FROM public.orders AS "Target" WHERE EXISTS '
            '(SELECT 1 FROM aux a WHERE a.id = "Target".id)',
            ["Target"],
            ["public.orders"],
            ["a"],
        ),
        (
            "mysql",
            "DELETE FROM o USING orders o JOIN shipments s ON o.id = s.id "
            "WHERE EXISTS (SELECT 1 FROM aux a WHERE a.id = o.id)",
            ["o", "s"],
            ["orders", "shipments"],
            ["a"],
        ),
        (
            "snowflake",
            "DELETE FROM orders o USING shipments s WHERE EXISTS "
            "(SELECT 1 FROM aux a WHERE a.id = o.id AND a.id = s.id)",
            ["o", "s"],
            ["orders", "shipments"],
            ["a"],
        ),
        (
            "tsql",
            "UPDATE TOP (10) orders WITH (ROWLOCK) SET val = "
            "(SELECT a.val FROM aux a WHERE a.id = orders.id)",
            ["orders"],
            ["orders"],
            ["a"],
        ),
        (
            "postgres",
            "UPDATE orders o SET val = s.val "
            "FROM (SELECT val FROM aux hidden) s WHERE o.id = s.val",
            ["o", "s"],
            ["orders", None],
            ["hidden"],
        ),
    ],
)
def test_dml_query_scopes(
    dialect, sql, expected_aliases, expected_references, child_aliases
):
    """DML sources belong to the parent, not nested or RETURNING aliases."""
    linter = Linter(dialect=dialect)
    parsed = linter.parse_string(sql)
    assert not parsed.violations
    query = Query.from_root(parsed.tree, linter.dialect)
    assert len(query.selectables) == 1
    info = query.selectables[0].select_info
    assert [alias.ref_str for alias in info.table_aliases] == expected_aliases
    assert [
        alias.object_reference.raw if alias.object_reference else None
        for alias in info.table_aliases
    ] == expected_references
    assert len(query.subqueries) == len(child_aliases)
    for child, expected_alias in zip(query.subqueries, child_aliases):
        assert child.parent is query
        assert (
            child.selectables[0].select_info.table_aliases[0].ref_str == expected_alias
        )


def test_dml_cte_query_scope():
    """A data-modifying CTE retains its own scope and nested query parents."""
    linter = Linter(dialect="postgres")
    parsed = linter.parse_string(
        "WITH changed AS (UPDATE orders o SET val = "
        "(SELECT a.val FROM aux a WHERE a.id = o.id) RETURNING o.id) "
        "SELECT id FROM changed"
    )
    assert not parsed.violations
    query = Query.from_root(parsed.tree, linter.dialect)
    dml = query.ctes["CHANGED"]
    assert dml.parent is query
    assert dml.selectables[0].select_info.table_aliases[0].ref_str == "o"
    assert dml.subqueries[0].parent is dml
