"""Tests for source line lengths in templated SQL."""

import pytest

from sqlfluff.core import FluffConfig, Linter


@pytest.mark.parametrize("flag", [True, False])
@pytest.mark.parametrize(
    "sql",
    [
        "{% macro x() %}" + "a" * 55 + "{% endmacro %} SELECT 1\n",
        "{% macro x() %}" + "a" * 55 + "{% endmacro %}\nSELECT 1\n",
        "SELECT a FROM t\n"
        "{% if flag %}WHERE b_column_with_a_long_name = 1"
        "{% else %}WHERE c_column_with_a_long_name = 2{% endif %}\n",
        "{% for x in [] %}" + "a" * 65 + "{% endfor %}\nSELECT 1\n",
        "    {%- if true %}SELECT " + "a" * 47 + "{%- endif %}\n",
        " {%- if true %}SELECT " + "a" * 64 + " {%- endif %}\n",
        "{% macro x() %}\n" + "a" * 85 + "\n{% endmacro %}\nSELECT 1\n",
        "{% for x in [] %}\n" + "a" * 82 + "\n{% endfor %}\nSELECT 1\n",
        "{% macro x() %}\n" + "a" * 85 + "\n{% endmacro %}",
        "{% macro x() %}\n"
        + "a" * 85
        + "\n"
        + "b" * 81
        + "\n{% endmacro %}\nSELECT 1\n",
        "{% macro x() %}" + "a" * 85 + "\n{% endmacro %}\nSELECT 1\n",
        "{% macro x() %}\n" + "a" * 85 + "\n{% endmacro %} SELECT " + "a" * 85,
        "{% if flag %}\nSELECT 1\n{% else %}\nSELECT " + "a" * 85 + "\n{% endif %}\n",
        "{% if flag %}\nSELECT 1\n{% else %}\n    SELECT "
        + "a" * 85
        + "\n{% endif %}\n",
        "{% if false %}SELECT " + "a" * 85 + "{% endif %}\n",
        "SELECT \n" + " " * 81 + "\n{{- ' 1' }}\n",
        "SELECT \n" + " " * 81 + "\n{#- comment #} 1\n",
        "{% if true -%}\n" + " " * 81 + "\nSELECT 1\n{% endif %}\n",
        "SELECT {{ 1 -}}\n" + " " * 81 + "\n",
    ],
)
def test_lt05_complete_source_line_lengths(sql, flag):
    """Report every overlong source line once with its complete length."""
    config = FluffConfig(
        configs={
            "core": {"dialect": "ansi", "rules": "LT05"},
            "templater": {"jinja": {"context": {"flag": flag}}},
        }
    )
    result = Linter(config=config).lint_string(sql)
    assert all(violation.rule_code() == "LT05" for violation in result.get_violations())
    assert [(v.line_no, v.desc()) for v in result.get_violations()] == [
        (line_no, f"Line is too long ({len(line)} > 80).")
        for line_no, line in enumerate(sql.splitlines(), 1)
        if len(line) > 80
    ]


@pytest.mark.parametrize("length", [79, 80, 81])
@pytest.mark.parametrize("limit", [0, 80])
def test_lt05_unrendered_source_length_limit(length, limit):
    """Respect the exact boundary and disabled line-length checking."""
    sql = "{% macro x() %}\n" + "a" * length + "\n{% endmacro %}\nSELECT 1\n"
    result = Linter(
        config=FluffConfig(
            overrides={"dialect": "ansi", "rules": "LT05", "max_line_length": limit}
        )
    ).lint_string(sql)
    assert len(result.get_violations()) == (limit > 0 and length > limit)


@pytest.mark.parametrize("ignore", [True, False])
def test_lt05_multiline_template_comment(ignore):
    """Apply the comment-line exemption to hidden template comment lines."""
    sql = "{#\n" + "a" * 85 + "\n#}\nSELECT 1\n"
    config = FluffConfig(
        configs={
            "core": {"dialect": "ansi", "rules": "LT05"},
            "rules": {"layout.long_lines": {"ignore_comment_lines": ignore}},
        }
    )
    result = Linter(config=config).lint_string(sql)
    assert len(result.get_violations()) == (not ignore)


@pytest.mark.parametrize("ignore", [True, False])
@pytest.mark.parametrize(
    "sql,option",
    [
        ("SELECT 1 --" + "a" * 85, "ignore_comment_lines"),
        (
            "CREATE TABLE t (a INT) COMMENT='" + "a" * 85 + "';",
            "ignore_comment_clauses",
        ),
    ],
)
def test_lt05_comment_after_multiline_placeholder(sql, option, ignore):
    """Preserve comment exemptions on a placeholder's final source line."""
    config = FluffConfig(
        configs={
            "core": {"dialect": "snowflake", "rules": "LT05"},
            "rules": {"layout.long_lines": {option: ignore}},
        }
    )
    result = Linter(config=config).lint_string(
        "{% macro x() %}\nx\n{% endmacro %} " + sql + "\n"
    )
    assert len(result.get_violations()) == (not ignore)


@pytest.mark.parametrize("flag", [True, False])
@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({}, 0),
        ({"disable_noqa": True}, 1),
        ({"disable_noqa_except": "LT05"}, 0),
        ({"disable_noqa_except": "layout.*"}, 0),
        ({"disable_noqa_except": "CP01"}, 1),
    ],
)
def test_lt05_unrendered_source_noqa(flag, overrides, expected):
    """Respect source noqa directives regardless of which branch renders."""
    sql = (
        "{% if flag %}\nSELECT 1\n{% else %}\nSELECT "
        + "a" * 85
        + " -- noqa: LT05\n{% endif %}\n"
    )
    config = FluffConfig(
        configs={
            "core": {"dialect": "ansi", "rules": "LT05", **overrides},
            "templater": {"jinja": {"context": {"flag": flag}}},
        }
    )
    assert len(Linter(config=config).lint_string(sql).get_violations()) == expected


@pytest.mark.parametrize("list_wrapping", ["one_per_line", "fill"])
def test_lt05_source_length_fix_and_relint(list_wrapping):
    """Keep detecting overlong conditional source after fixing a list."""
    sql = (
        "select a\nfrom tbl\n"
        "group by col_a, {% if flag %}col_b{% else %}col_c{% endif %}, "
        "col_d, long_column_name1, long_column_name2\n"
    )
    config = FluffConfig(
        configs={
            "core": {"dialect": "ansi", "rules": "LT05", "max_line_length": 46},
            "indentation": {"list_wrapping": list_wrapping},
            "templater": {"jinja": {"context": {"flag": True}}},
        }
    )
    linter = Linter(config=config)
    assert linter.lint_string(sql).get_violations()[0].desc() == (
        "Line is too long (105 > 46)."
    )
    fixed = linter.lint_string(sql, fix=True).fix_string()[0]
    assert fixed != sql
    for candidate in (
        fixed,
        "select a\nfrom tbl\ngroup by\n    col_a,\n"
        "    {% if flag %}col_b{% else %}col_c{% endif %},\n"
        "    col_d,\n    long_column_name1,\n    long_column_name2\n",
    ):
        assert [
            (v.line_no, v.desc())
            for v in linter.lint_string(candidate).get_violations()
        ] == [
            (line_no, f"Line is too long ({len(line)} > 46).")
            for line_no, line in enumerate(candidate.splitlines(), 1)
            if len(line) > 46
        ]
    assert linter.lint_string(fixed, fix=True).fix_string()[0] == fixed
