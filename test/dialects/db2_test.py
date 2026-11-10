"""Tests specific to the Db2 dialect."""

import pytest

from sqlfluff.core import Linter


@pytest.mark.parametrize("modifier", ["FINAL", "NEW", "OLD"])
@pytest.mark.parametrize(
    "statement,statement_type,allowed_modifiers",
    [
        (
            "INSERT INTO orders (id) VALUES (1)",
            "insert_statement",
            {"FINAL", "NEW"},
        ),
        (
            "UPDATE orders SET amount = 100 WHERE id = 1",
            "update_statement",
            {"FINAL", "NEW", "OLD"},
        ),
        (
            "DELETE FROM orders WHERE id = 1",
            "delete_statement",
            {"OLD"},
        ),
    ],
)
def test_db2_data_change_table_modifier(
    modifier: str,
    statement: str,
    statement_type: str,
    allowed_modifiers: set[str],
) -> None:
    """Check the DML choices for each data-change table modifier."""
    sql = f"SELECT * FROM {modifier} TABLE ({statement});"
    parsed = Linter(dialect="db2").parse_string(sql)
    assert parsed.tree is not None
    assert parsed.tree.raw == sql
    references = list(parsed.tree.recursive_crawl("data_change_table_reference"))

    if modifier in allowed_modifiers:
        assert not parsed.violations
        assert len(references) == 1
        assert list(references[0].recursive_crawl(statement_type))
    else:
        assert any(violation.rule_code() == "PRS" for violation in parsed.violations)
        assert not references
