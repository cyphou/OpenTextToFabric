"""Tests for report_converter.dax_optimizer — AST-based DAX rewriter."""

import unittest

from report_converter.dax_optimizer import DaxOptimizer


class TestDaxOptimizerInit(unittest.TestCase):
    def test_fresh_stats(self):
        opt = DaxOptimizer()
        self.assertEqual(opt.stats["total"], 0)
        self.assertEqual(opt.stats["optimized"], 0)
        self.assertEqual(opt.stats["rules_applied"], 0)

    def test_has_rules(self):
        opt = DaxOptimizer()
        self.assertGreaterEqual(len(opt._rules), 10)


class TestIsblankToCoalesce(unittest.TestCase):
    def setUp(self):
        self.opt = DaxOptimizer()

    def test_simple_isblank(self):
        r = self.opt.optimize("IF(ISBLANK([X]), 0, [X])")
        self.assertIn("COALESCE", r["optimized"])
        self.assertTrue(r["changed"])

    def test_isblank_with_string_default(self):
        r = self.opt.optimize('IF(ISBLANK([Name]), "Unknown", [Name])')
        self.assertIn("COALESCE", r["optimized"])

    def test_no_match_different_columns(self):
        r = self.opt.optimize("IF(ISBLANK([X]), 0, [Y])")
        self.assertNotIn("COALESCE", r["optimized"])

    def test_isblank_blank_default(self):
        r = self.opt.optimize("IF(ISBLANK([X]), BLANK(), [X])")
        self.assertIn("COALESCE", r["optimized"])


class TestNestedIfToSwitch(unittest.TestCase):
    def setUp(self):
        self.opt = DaxOptimizer()

    def test_three_branches(self):
        dax = 'IF([Status]="A", 1, IF([Status]="B", 2, IF([Status]="C", 3, 0)))'
        r = self.opt.optimize(dax)
        self.assertIn("SWITCH(TRUE()", r["optimized"])
        self.assertIn("nested_if_to_switch", r["rules_applied"])

    def test_two_branches_no_switch(self):
        dax = 'IF([Status]="A", 1, IF([Status]="B", 2, 0))'
        r = self.opt.optimize(dax)
        self.assertNotIn("SWITCH", r["optimized"])


class TestSafeDivision(unittest.TestCase):
    def setUp(self):
        self.opt = DaxOptimizer()

    def test_simple_division(self):
        r = self.opt.optimize("[Revenue] / [Cost]")
        self.assertIn("DIVIDE([Revenue], [Cost])", r["optimized"])

    def test_already_divide(self):
        r = self.opt.optimize("DIVIDE([Revenue], [Cost])")
        self.assertNotIn("safe_division", r["rules_applied"])


class TestCalculateAll(unittest.TestCase):
    def setUp(self):
        self.opt = DaxOptimizer()

    def test_calculate_all_to_removefilters(self):
        dax = "CALCULATE(SUM([Sales]), ALL(Products))"
        r = self.opt.optimize(dax)
        self.assertIn("REMOVEFILTERS(Products)", r["optimized"])
        self.assertNotIn("ALL(", r["optimized"])

    def test_no_all_no_change(self):
        dax = "CALCULATE(SUM([Sales]))"
        r = self.opt.optimize(dax)
        # Redundant calculate should remove CALCULATE
        self.assertEqual(r["optimized"], "SUM([Sales])")


class TestRedundantCalculate(unittest.TestCase):
    def setUp(self):
        self.opt = DaxOptimizer()

    def test_calculate_sum_no_filter(self):
        r = self.opt.optimize("CALCULATE(SUM([X]))")
        self.assertEqual(r["optimized"], "SUM([X])")

    def test_calculate_average_no_filter(self):
        r = self.opt.optimize("CALCULATE(AVERAGE([X]))")
        self.assertEqual(r["optimized"], "AVERAGE([X])")

    def test_calculate_with_filter_preserved(self):
        dax = "CALCULATE(SUM([X]), FILTER(T, [A] > 0))"
        r = self.opt.optimize(dax)
        self.assertIn("CALCULATE", r["optimized"])


class TestFormatOptimization(unittest.TestCase):
    def setUp(self):
        self.opt = DaxOptimizer()

    def test_empty_format_removed(self):
        r = self.opt.optimize('FORMAT([Date], "")')
        self.assertEqual(r["optimized"], "[Date]")

    def test_real_format_kept(self):
        r = self.opt.optimize('FORMAT([Date], "yyyy-MM-dd")')
        self.assertIn("FORMAT", r["optimized"])


class TestVariableExtraction(unittest.TestCase):
    def setUp(self):
        self.opt = DaxOptimizer()

    def test_repeated_ref_extracted(self):
        dax = "[Sales] + [Sales] + [Sales] + [Sales]"
        r = self.opt.optimize(dax)
        self.assertIn("VAR", r["optimized"])
        self.assertIn("RETURN", r["optimized"])

    def test_no_extraction_few_refs(self):
        dax = "[Sales] + [Cost]"
        r = self.opt.optimize(dax)
        self.assertNotIn("VAR", r["optimized"])


class TestTrimRedundantParens(unittest.TestCase):
    def setUp(self):
        self.opt = DaxOptimizer()

    def test_double_parens(self):
        r = self.opt.optimize("(([X] + [Y]))")
        self.assertEqual(r["optimized"], "([X] + [Y])")

    def test_triple_parens(self):
        r = self.opt.optimize("((([Z])))")
        self.assertEqual(r["optimized"], "([Z])")


class TestBlankComparison(unittest.TestCase):
    def setUp(self):
        self.opt = DaxOptimizer()

    def test_eq_blank_to_isblank(self):
        r = self.opt.optimize("[X] = BLANK()")
        self.assertEqual(r["optimized"], "ISBLANK([X])")


class TestOptimizeBatch(unittest.TestCase):
    def test_batch_optimization(self):
        opt = DaxOptimizer()
        measures = [
            {"name": "M1", "expression": "CALCULATE(SUM([X]))"},
            {"name": "M2", "expression": "[A] / [B]"},
            {"name": "M3", "expression": "SUM([Z])"},
        ]
        results = opt.optimize_batch(measures)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["expression"], "SUM([X])")
        self.assertIn("DIVIDE", results[1]["expression"])
        # M3 unchanged
        self.assertEqual(results[2]["expression"], "SUM([Z])")

    def test_batch_stats(self):
        opt = DaxOptimizer()
        measures = [
            {"name": "M1", "expression": "CALCULATE(SUM([X]))"},
            {"name": "M2", "expression": "SUM([Y])"},
        ]
        opt.optimize_batch(measures)
        self.assertEqual(opt.stats["total"], 2)
        self.assertEqual(opt.stats["optimized"], 1)


class TestSummary(unittest.TestCase):
    def test_summary_after_optimizations(self):
        opt = DaxOptimizer()
        opt.optimize("CALCULATE(SUM([X]))")
        opt.optimize("SUM([Y])")
        s = opt.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["optimized"], 1)


class TestOptimizeContext(unittest.TestCase):
    def test_context_in_result(self):
        opt = DaxOptimizer()
        r = opt.optimize("SUM([X])", context="MyMeasure")
        self.assertEqual(r["context"], "MyMeasure")


class TestNoChange(unittest.TestCase):
    def test_clean_expression(self):
        opt = DaxOptimizer()
        r = opt.optimize("SUM([Revenue])")
        self.assertFalse(r["changed"])
        self.assertEqual(r["rules_applied"], [])
        self.assertEqual(r["optimized"], "SUM([Revenue])")


class TestMultipleRules(unittest.TestCase):
    def test_multiple_rules_applied(self):
        opt = DaxOptimizer()
        dax = 'FORMAT([X], "")'  # format + potential other rules
        r = opt.optimize(dax)
        self.assertTrue(r["changed"])
        self.assertIn("format_optimization", r["rules_applied"])


if __name__ == "__main__":
    unittest.main()
