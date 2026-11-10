"""Integration tests for chained function layout."""

import pytest

from sqlfluff.core import FluffConfig, Linter


def _linter(style: str, rules: str = "LT16") -> Linter:
    return Linter(
        config=FluffConfig.from_string(f"""[sqlfluff]
dialect = bigquery
rules = {rules}

[sqlfluff:rules:layout.chained_functions]
writing_style = {style}
""")
    )


@pytest.mark.parametrize("style", ["one_liner", "aligned", "indented", "consistent"])
@pytest.mark.parametrize("rules", ["LT01,LT02,LT06,LT09,LT16", "all"])
def test_chained_layout_idempotence_with_layout_rules(style: str, rules: str) -> None:
    """Spacing and indentation rules respect the selected chain layout."""
    linter = _linter(style, rules)
    sql = "SELECT\n    (foo).REPLACE('a', '0').TRIM() AS foo,\n    (bar).LOWER() AS bar;\n"
    result = linter.lint_string(sql, fix=True)
    fixed = result.fix_string()[0]
    assert not linter.lint_string(fixed).get_violations()
    assert linter.lint_string(fixed, fix=True).fix_string()[0] == fixed
    if style in ("consistent", "one_liner"):
        assert fixed == sql
    else:
        indent = "        " if style == "indented" else "    "
        assert fixed == (
            f"SELECT\n    (foo)\n{indent}.REPLACE('a', '0')\n{indent}.TRIM() AS foo,"
            f"\n    (bar)\n{indent}.LOWER() AS bar;\n"
        )


def test_chained_layout_consistent_per_file() -> None:
    """A reused linter infers style independently for each file."""
    linter = _linter("consistent")
    for indent in ("", "    "):
        sql = f"SELECT\n    (foo)\n    {indent}.TRIM(),\n    (bar).LOWER();\n"
        fixed = linter.lint_string(
            sql, fname=f"{len(indent)}.sql", fix=True
        ).fix_string()[0]
        assert fixed == sql.replace("(bar).LOWER()", f"(bar)\n    {indent}.LOWER()")
        assert not linter.lint_string(fixed).get_violations()
    sql = "SELECT (foo).TRIM(), (bar).LOWER();\n"
    assert not linter.lint_string(sql, fname="one_line.sql").get_violations()


@pytest.mark.parametrize("comment", [" -- keep\n    ", "/*keep*/", " /*keep*/\n    "])
def test_chained_layout_comment_safety(comment: str) -> None:
    """Collapsing a chain never deletes, relocates, or swallows comments."""
    linter = _linter("one_liner")
    sql = f"SELECT (foo){comment}.TRIM();\n"
    result = linter.lint_string(sql, fix=True)
    assert result.fix_string()[0] == sql
    violations = result.get_violations()
    assert len(violations) == 1
    assert violations[0].rule_code() == "LT16"
    assert not violations[0].fixes


def test_chained_layout_consistent_nested_source_order() -> None:
    """The first dot in source order, not the outer expression, selects style."""
    sql = (
        "SELECT\n    ((foo).TRIM())\n        .LOWER(),\n    (bar)\n        .UPPER();\n"
    )
    result = _linter("consistent").lint_string(sql, fix=True)
    assert result.fix_string()[0] == (
        "SELECT\n    ((foo).TRIM()).LOWER(),\n    (bar).UPPER();\n"
    )


@pytest.mark.parametrize("style", ["one_liner", "aligned", "indented"])
def test_chained_layout_expression_preserved(style: str) -> None:
    """Real fix flow preserves code tokens and comments for each explicit style."""
    linter = _linter(style)
    sql = "SELECT\n    (foo)\n .REPLACE('a', LOWER(bar))\n   .TRIM() AS cleaned;\n"
    before = linter.parse_string(sql)
    result = linter.lint_string(sql, fix=True)
    fixed = result.fix_string()[0]
    after = linter.parse_string(fixed)
    assert not before.violations
    assert not after.violations
    assert before.tree is not None and after.tree is not None
    assert [segment.raw for segment in before.tree.raw_segments if segment.is_code] == [
        segment.raw for segment in after.tree.raw_segments if segment.is_code
    ]
    assert not linter.lint_string(fixed).get_violations()
    assert linter.lint_string(fixed, fix=True).fix_string()[0] == fixed


@pytest.mark.parametrize("style", ["one_liner", "aligned", "indented"])
def test_chained_layout_long_example(style: str) -> None:
    """All layouts support the longer example without rewriting nested calls."""
    linter = _linter(style)
    traditional = (
        "    REPLACE(REPLACE(REPLACE(REPLACE(LOWER(TRIM(adresse)), "
        "'ch', 'chemin'), 'av', 'avenue'), 'bd', 'boulevard'), "
        "'bvd', 'boulevard') AS original,\n"
    )
    calls = [
        ".TRIM()",
        ".LOWER()",
        ".REPLACE('ch', 'chemin')",
        ".REPLACE('av', 'avenue')",
        ".REPLACE('bd', 'boulevard')",
        ".REPLACE('bvd', 'boulevard')",
    ]
    sql = "SELECT\n" + traditional + "    (adresse)" + "".join(calls) + " AS cleaned;\n"
    fixed = linter.lint_string(sql, fix=True).fix_string()[0]
    separator = {"one_liner": "", "aligned": "\n    ", "indented": "\n        "}[style]
    expected = (
        "SELECT\n"
        + traditional
        + "    (adresse)"
        + "".join(separator + call for call in calls)
        + " AS cleaned;\n"
    )
    assert fixed == expected
    assert not linter.lint_string(fixed).get_violations()
