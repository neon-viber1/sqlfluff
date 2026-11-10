"""The BigQuery rules plugin bundle."""

from sqlfluff.core.plugin import hookimpl
from sqlfluff.core.rules import BaseRule, ConfigInfo


@hookimpl
def get_configs_info() -> dict[str, ConfigInfo]:
    """Get additional rule config validations and descriptions."""
    return {
        "allow": {
            "validation": [True, False],
            "definition": (
                "Whether BigQuery WITH expressions are allowed. Defaults to ``True``."
            ),
        },
    }


@hookimpl
def get_rules() -> list[type[BaseRule]]:
    """Get plugin rules.

    NOTE: Rules are imported only on fetch to manage import times.
    """
    from sqlfluff.rules.bigquery.BQ01 import Rule_BQ01

    return [Rule_BQ01]
