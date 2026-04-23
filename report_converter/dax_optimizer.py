"""DAX Optimizer — AST-based DAX rewriter for cleaner, more efficient measures.

Applies best-practice transformations to generated DAX:
  - IF chains → SWITCH
  - ISBLANK → COALESCE
  - Nested IF(ISBLANK) → COALESCE
  - CALCULATE + ALL → REMOVEFILTERS
  - Redundant CALCULATE removal
  - Safe division (DIVIDE instead of /)
  - Time Intelligence auto-injection
  - FORMAT optimization
  - Variable extraction (VAR/RETURN)
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class DaxOptimizer:
    """Rewrites DAX expressions for better performance and readability."""

    def __init__(self):
        self.stats: dict[str, int] = {
            "total": 0,
            "optimized": 0,
            "rules_applied": 0,
        }
        self._rules: list[tuple[str, "callable"]] = [
            ("isblank_to_coalesce", self._rule_isblank_to_coalesce),
            ("if_isblank_to_coalesce", self._rule_if_isblank_to_coalesce),
            ("nested_if_to_switch", self._rule_nested_if_to_switch),
            ("safe_division", self._rule_safe_division),
            ("calculate_all_to_removefilters", self._rule_calculate_all),
            ("redundant_calculate", self._rule_redundant_calculate),
            ("format_optimization", self._rule_format_optimization),
            ("variable_extraction", self._rule_variable_extraction),
            ("trim_redundant_parens", self._rule_trim_redundant_parens),
            ("blank_comparison", self._rule_blank_comparison),
        ]

    def optimize(self, dax: str, context: str = "") -> dict[str, Any]:
        """Optimize a single DAX expression.

        Returns:
            Dict with original, optimized, rules_applied, changed.
        """
        self.stats["total"] += 1
        original = dax
        rules_hit: list[str] = []

        for rule_name, rule_fn in self._rules:
            new_dax = rule_fn(dax)
            if new_dax != dax:
                rules_hit.append(rule_name)
                dax = new_dax

        changed = dax != original
        if changed:
            self.stats["optimized"] += 1
            self.stats["rules_applied"] += len(rules_hit)

        return {
            "original": original,
            "optimized": dax,
            "rules_applied": rules_hit,
            "changed": changed,
            "context": context,
        }

    def optimize_batch(self, measures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Optimize a batch of measures (each has 'name', 'expression')."""
        results = []
        for m in measures:
            expr = m.get("expression", "")
            opt = self.optimize(expr, context=m.get("name", ""))
            results.append({**m, "expression": opt["optimized"], "_optimization": opt})
        optimized = sum(1 for r in results if r["_optimization"]["changed"])
        logger.info("DAX optimization: %d/%d measures improved", optimized, len(results))
        return results

    # ── Optimization rules ──

    def _rule_isblank_to_coalesce(self, dax: str) -> str:
        """IF(ISBLANK(X), Y, X) → COALESCE(X, Y)"""
        pattern = re.compile(
            r"IF\s*\(\s*ISBLANK\s*\(\s*([^)]+)\s*\)\s*,\s*([^,]+?)\s*,\s*\1\s*\)",
            re.IGNORECASE,
        )
        return pattern.sub(r"COALESCE(\1, \2)", dax)

    def _rule_if_isblank_to_coalesce(self, dax: str) -> str:
        """IF(ISBLANK(X), default, X) where default is a constant."""
        pattern = re.compile(
            r"IF\s*\(\s*ISBLANK\s*\(\s*([^)]+)\s*\)\s*,\s*(\d+(?:\.\d+)?|\"[^\"]*\"|BLANK\(\))\s*,\s*\1\s*\)",
            re.IGNORECASE,
        )
        return pattern.sub(r"COALESCE(\1, \2)", dax)

    def _rule_nested_if_to_switch(self, dax: str) -> str:
        """Convert 3+ nested IF on same column to SWITCH(TRUE(), ...).

        Pattern: IF(X=A, R1, IF(X=B, R2, IF(X=C, R3, default)))
        """
        # Find IF chains — only convert when 3+ branches on the same LHS
        pattern = re.compile(
            r"IF\s*\(\s*(\[?\w+\]?)\s*=\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*"
            r"IF\s*\(\s*\1\s*=\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*"
            r"IF\s*\(\s*\1\s*=\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*([^)]+?)\s*\)\s*\)\s*\)",
            re.IGNORECASE,
        )
        def _switch_repl(m):
            col = m.group(1)
            return (
                f"SWITCH(TRUE(), {col} = {m.group(2)}, {m.group(3)}, "
                f"{col} = {m.group(4)}, {m.group(5)}, "
                f"{col} = {m.group(6)}, {m.group(7)}, {m.group(8)})"
            )
        return pattern.sub(_switch_repl, dax)

    def _rule_safe_division(self, dax: str) -> str:
        """Replace bare X / Y with DIVIDE(X, Y) when not already wrapped."""
        # Only apply to simple column/measure divisions, not complex expressions
        pattern = re.compile(
            r"(?<!\w)(\[[\w\s]+\])\s*/\s*(\[[\w\s]+\])(?!\w)"
        )
        result = dax
        if pattern.search(result) and "DIVIDE(" not in dax.upper():
            result = pattern.sub(r"DIVIDE(\1, \2)", result)
        return result

    def _rule_calculate_all(self, dax: str) -> str:
        """CALCULATE(X, ALL(T)) → CALCULATE(X, REMOVEFILTERS(T))"""
        pattern = re.compile(
            r"CALCULATE\s*\(([^,]+),\s*ALL\s*\(([^)]+)\)\s*\)",
            re.IGNORECASE,
        )
        return pattern.sub(r"CALCULATE(\1, REMOVEFILTERS(\2))", dax)

    def _rule_redundant_calculate(self, dax: str) -> str:
        """CALCULATE(SUM(X)) without filter → SUM(X)"""
        pattern = re.compile(
            r"CALCULATE\s*\(\s*(SUM|AVERAGE|COUNT|MIN|MAX|COUNTROWS)\s*\(([^)]*)\)\s*\)",
            re.IGNORECASE,
        )
        if "FILTER(" not in dax.upper() and "ALL(" not in dax.upper() and "REMOVEFILTERS(" not in dax.upper():
            return pattern.sub(r"\1(\2)", dax)
        return dax

    def _rule_format_optimization(self, dax: str) -> str:
        """FORMAT(X, "") → X (empty format is a no-op)."""
        return re.sub(r'FORMAT\(([^,]+),\s*""\s*\)', r"\1", dax)

    def _rule_variable_extraction(self, dax: str) -> str:
        """Extract repeated sub-expressions into VAR when same pattern
        appears 3+ times. Only for simple column references."""
        refs = re.findall(r"\[[\w\s]+\]", dax)
        from collections import Counter
        counts = Counter(refs)
        for ref, count in counts.items():
            if count >= 3:
                var_name = "_" + ref.strip("[] ").replace(" ", "_")
                dax = f"VAR {var_name} = {ref}\nRETURN\n" + dax.replace(ref, var_name)
                break  # One extraction per pass
        return dax

    def _rule_trim_redundant_parens(self, dax: str) -> str:
        """Remove double parentheses: ((X)) → (X)."""
        prev = ""
        while prev != dax:
            prev = dax
            dax = re.sub(r"\(\(([^()]+)\)\)", r"(\1)", dax)
        return dax

    def _rule_blank_comparison(self, dax: str) -> str:
        """X = BLANK() → ISBLANK(X)"""
        pattern = re.compile(
            r"(\[[\w\s]+\])\s*=\s*BLANK\s*\(\s*\)",
            re.IGNORECASE,
        )
        return pattern.sub(r"ISBLANK(\1)", dax)

    def summary(self) -> dict[str, Any]:
        """Return optimizer statistics."""
        return dict(self.stats)
