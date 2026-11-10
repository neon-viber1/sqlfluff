"""Implementation of Rule BQ01."""

from typing import Optional

from sqlfluff.core.rules import BaseRule, LintResult, RuleContext
from sqlfluff.core.rules.crawlers import SegmentSeekerCrawler


class Rule_BQ01(BaseRule):
    """Disallow BigQuery ``WITH`` expressions when configured.

    BigQuery ``WITH`` expressions assign variables within an expression. This
    rule checks expression-level ``WITH`` syntax, not query-level ``WITH``
    clauses that define common table expressions. Set ``allow = False`` to flag
    each expression occurrence. The default is ``True``, so existing queries
    are unaffected unless the rule is explicitly configured.

    **Anti-pattern**

    .. code-block:: sql

        SELECT WITH (value AS 1, value + 1);

    **Best practice**

    Use the expression directly, or configure ``allow = True`` to permit
    ``WITH`` expressions.

    .. code-block:: sql

        SELECT 2;
    """

    name = "bigquery.with_expressions"
    aliases = ()
    groups = ("all", "bigquery")
    config_keywords = ["allow"]
    crawl_behaviour = SegmentSeekerCrawler({"with_expression"})

    def _eval(self, context: RuleContext) -> Optional[LintResult]:
        """Report a WITH expression when the configuration forbids it."""
        self.allow: bool

        if context.dialect.name != "bigquery" or self.allow:
            return None

        return LintResult(
            anchor=context.segment,
            description="BigQuery WITH expressions are disallowed by configuration.",
        )
