"""Implementation of Rule LT16."""

from collections.abc import Sequence
from typing import Optional

from sqlfluff.core.parser import BaseSegment, RawSegment
from sqlfluff.core.rules import BaseRule, LintFix, LintResult, RuleContext
from sqlfluff.core.rules.crawlers import RootOnlyCrawler
from sqlfluff.utils.reflow.elements import ReflowPoint
from sqlfluff.utils.reflow.reindent import construct_single_indent


class Rule_LT16(BaseRule):
    """Chained function calls should follow a consistent layout.

    This rule applies to BigQuery chained function calls, not ordinary function
    calls or field access. Configure it using:

    .. code-block:: ini

        [sqlfluff:rules:layout.chained_functions]
        writing_style = consistent

    ``one_liner`` removes whitespace between the input and each chained call.
    ``aligned`` puts each call on a new line at the input line's indentation.
    ``indented`` adds one indentation unit to that indentation, using
    ``indent_unit`` and ``tab_space_size``.

    The default, ``consistent``, infers a style from the first chain in each
    file, including single-call chains. If its first call starts on the input's
    last line, the style is ``one_liner``. Otherwise, a call indented farther
    than the input line selects ``indented``; all other indentation selects
    ``aligned``. This style applies to every chain in the file, including the
    remaining calls of the first chain. Each file infers independently.

    Only the whitespace before chained calls is changed. Argument formatting,
    nested functions and aliases are left alone. Comments are preserved. A
    boundary containing a comment cannot be collapsed to ``one_liner`` safely,
    so it is reported without a fix. Line length is handled separately by LT05.

    **Anti-pattern**

    With ``writing_style = indented``:

    .. code-block:: sql

        SELECT
            (adresse).TRIM().LOWER().REPLACE('ch', 'chemin') AS cleaned;

    **Best practice**

    .. code-block:: sql

        SELECT
            (adresse)
                .TRIM()
                .LOWER()
                .REPLACE('ch', 'chemin') AS cleaned;

    Alternatively, ``aligned`` produces:

    .. code-block:: sql

        SELECT
            (adresse)
            .TRIM()
            .LOWER()
            .REPLACE('ch', 'chemin') AS cleaned;

    With ``one_liner``, all three calls remain adjacent to ``(adresse)``.
    Traditional nested calls such as ``LOWER(TRIM(adresse))`` are not converted
    into chains.
    """

    name = "layout.chained_functions"
    groups = ("all", "layout")
    crawl_behaviour = RootOnlyCrawler()
    config_keywords = ["writing_style"]
    is_fix_compatible = True
    writing_style: str

    @staticmethod
    def _line_indent(raws: Sequence[RawSegment], index: int) -> str:
        """Return the leading whitespace on the input's first line."""
        start = index
        while start and not raws[start - 1].is_type("newline"):
            start -= 1
        indent = ""
        while start < index and raws[start].is_type("whitespace"):
            indent += raws[start].raw
            start += 1
        return indent

    def _eval(self, context: RuleContext) -> Optional[list[LintResult]]:
        if context.dialect.name != "bigquery":
            return None
        root = context.segment
        raws = root.raw_segments
        indices = {segment.uuid: index for index, segment in enumerate(raws)}
        chains: dict[int, tuple[BaseSegment, list[BaseSegment]]] = {}
        for expression in root.recursive_crawl("expression"):
            base = None
            for segment in expression.segments:
                if not segment.is_code:
                    continue
                if segment.is_type("chained_function_call") and base is not None:
                    chains.setdefault(base.uuid, (base, []))[1].append(segment)
                elif not segment.is_type(
                    "array_accessor", "semi_structured_expression"
                ):
                    base = segment
        ordered = sorted(
            chains.values(), key=lambda chain: indices[chain[1][0].raw_segments[0].uuid]
        )
        style = self.writing_style
        single_indent = construct_single_indent(
            context.config.get("indent_unit", section="indentation"),
            context.config.get("tab_space_size", section="indentation"),
        )
        results = []
        for base, calls in ordered:
            base_index = indices[base.raw_segments[0].uuid]
            indent = self._line_indent(raws, base_index)
            if style == "consistent":
                first_index = indices[calls[0].raw_segments[0].uuid]
                base_end = indices[base.raw_segments[-1].uuid]
                if not any(
                    "\n" in segment.raw for segment in raws[base_end + 1 : first_index]
                ):
                    style = "one_liner"
                elif len(
                    self._line_indent(raws, first_index).expandtabs(
                        context.config.get("tab_space_size", section="indentation")
                    )
                ) > len(
                    indent.expandtabs(
                        context.config.get("tab_space_size", section="indentation")
                    )
                ):
                    style = "indented"
                else:
                    style = "aligned"
            desired_indent = indent + (single_indent if style == "indented" else "")
            for call in calls:
                dot = call.raw_segments[0]
                index = indices[dot.uuid]
                start = index
                while start and not raws[start - 1].is_code:
                    start -= 1
                gap = raws[start:index]
                description = f"Expected {style} layout for chained function calls."
                if style == "one_liner":
                    whitespace = [
                        segment
                        for segment in gap
                        if segment.is_type("whitespace", "newline")
                    ]
                    if whitespace or any(segment.is_comment for segment in gap):
                        safe = all(
                            segment.is_type("whitespace", "newline", "indent")
                            for segment in gap
                        )
                        results.append(
                            LintResult(
                                anchor=dot,
                                fixes=[
                                    LintFix.delete(segment) for segment in whitespace
                                ]
                                if safe
                                else [],
                                description=description,
                            )
                        )
                else:
                    tail = index
                    while tail > start and raws[tail - 1].is_type(
                        "whitespace", "newline", "indent"
                    ):
                        tail -= 1
                    point = ReflowPoint(tuple(raws[tail:index]))
                    new_results, _ = point.indent_to(
                        desired_indent, before=dot, description=description
                    )
                    results.extend(new_results)
        return results
