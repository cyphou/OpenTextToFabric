"""Realistic tests for ExpressionConverter using real BIRT expression patterns.

Based on actual BIRT JavaScript expressions found in enterprise reports:
- Total.* aggregation functions
- BirtStr.* string functions
- BirtDateTime.* date functions
- BirtMath.* math functions
- Row/dataSetRow references
- Ternary conditionals
- Parameter references
"""

import unittest

from report_converter.expression_converter import ExpressionConverter
from tests.fixtures import BIRT_EXPRESSION_TEST_CASES


class TestRealisticExpressionConversion(unittest.TestCase):
    """Tests ExpressionConverter against real BIRT expression patterns."""

    def setUp(self):
        self.converter = ExpressionConverter()

    def test_all_aggregation_expressions(self):
        """Validates all BIRT Total.* functions convert correctly."""
        agg_cases = [c for c in BIRT_EXPRESSION_TEST_CASES if c["category"] == "aggregation"]
        for case in agg_cases:
            result = self.converter.convert(case["birt"])
            if "expected_dax" in case:
                self.assertEqual(
                    result["converted"], case["expected_dax"],
                    f"Failed for: {case['birt']}"
                )
            elif "expected_dax_contains" in case:
                self.assertIn(
                    case["expected_dax_contains"], result["converted"],
                    f"Failed for: {case['birt']} → {result['converted']}"
                )
            self.assertIn(result["status"], ("success", "partial"),
                          f"Status should be success/partial for: {case['birt']}")

    def test_all_string_expressions(self):
        """Validates all BirtStr.* functions convert correctly."""
        str_cases = [c for c in BIRT_EXPRESSION_TEST_CASES if c["category"] == "string"]
        for case in str_cases:
            result = self.converter.convert(case["birt"])
            self.assertEqual(
                result["converted"], case["expected_dax"],
                f"Failed for: {case['birt']}"
            )

    def test_all_datetime_expressions(self):
        """Validates all BirtDateTime.* functions convert correctly."""
        dt_cases = [c for c in BIRT_EXPRESSION_TEST_CASES if c["category"] == "datetime"]
        for case in dt_cases:
            result = self.converter.convert(case["birt"])
            self.assertEqual(
                result["converted"], case["expected_dax"],
                f"Failed for: {case['birt']}"
            )

    def test_all_math_expressions(self):
        """Validates BirtMath.* functions."""
        math_cases = [c for c in BIRT_EXPRESSION_TEST_CASES if c["category"] == "math"]
        for case in math_cases:
            result = self.converter.convert(case["birt"])
            if "expected_dax" in case:
                self.assertEqual(result["converted"], case["expected_dax"],
                                 f"Failed for: {case['birt']}")
            elif "expected_dax_contains" in case:
                self.assertIn(case["expected_dax_contains"], result["converted"],
                              f"Failed for: {case['birt']}")

    def test_row_references(self):
        """row["col"] → [col], dataSetRow["col"] → [col]."""
        ref_cases = [c for c in BIRT_EXPRESSION_TEST_CASES if c["category"] == "reference"]
        for case in ref_cases:
            result = self.converter.convert(case["birt"])
            self.assertEqual(result["converted"], case["expected_dax"],
                             f"Failed for: {case['birt']}")

    def test_parameter_references(self):
        """params["name"].value → [@name]."""
        param_cases = [c for c in BIRT_EXPRESSION_TEST_CASES if c["category"] == "parameter"]
        for case in param_cases:
            result = self.converter.convert(case["birt"])
            self.assertEqual(result["converted"], case["expected_dax"],
                             f"Failed for: {case['birt']}")

    def test_conditional_expressions(self):
        """Ternary ? : → IF()."""
        cond_cases = [c for c in BIRT_EXPRESSION_TEST_CASES if c["category"] == "conditional"]
        for case in cond_cases:
            result = self.converter.convert(case["birt"])
            self.assertIn(case["expected_dax_contains"], result["converted"],
                          f"Failed for: {case['birt']}")

    def test_operator_conversions(self):
        """== → =, !== → <>."""
        op_cases = [c for c in BIRT_EXPRESSION_TEST_CASES if c["category"] == "operator"]
        for case in op_cases:
            result = self.converter.convert(case["birt"])
            if "expected_dax_not_contains" in case:
                self.assertNotIn(case["expected_dax_not_contains"], result["converted"],
                                 f"Should not contain {case['expected_dax_not_contains']}: {result['converted']}")
            if "expected_dax_contains" in case:
                self.assertIn(case["expected_dax_contains"], result["converted"],
                              f"Should contain {case['expected_dax_contains']}: {result['converted']}")

    def test_computed_column_expressions(self):
        """Arithmetic expressions like row["qty"] * row["price"]."""
        comp_cases = [c for c in BIRT_EXPRESSION_TEST_CASES if c["category"] == "computed"]
        for case in comp_cases:
            result = self.converter.convert(case["birt"])
            self.assertEqual(result["converted"], case["expected_dax"],
                             f"Failed for: {case['birt']}")


class TestRealisticBatchConversion(unittest.TestCase):
    """Tests batch conversion of expressions from a real report."""

    def setUp(self):
        self.converter = ExpressionConverter()

    def test_batch_classic_models_expressions(self):
        """Convert all expressions from the Classic Models report at once."""
        expressions = [
            {"expression": 'row["quantityOrdered"] * row["priceEach"]', "source": "dataset:OrdersByCustomer:lineTotal"},
            {"expression": 'BirtDateTime.year(row["orderDate"])', "source": "dataset:OrdersByCustomer:orderYear"},
            {"expression": 'Total.sum(row["lineTotal"])', "source": "table:OrdersTable:totalRevenue"},
            {"expression": 'Total.countDistinct(row["orderNumber"])', "source": "table:OrdersTable:orderCount"},
            {"expression": 'Total.ave(row["lineTotal"])', "source": "table:OrdersTable:avgOrderValue"},
            {"expression": 'Total.percentSum(row["lineTotal"])', "source": "table:OrdersTable:pctOfTotal"},
            {"expression": 'Total.runningSum(row["lineTotal"])', "source": "table:OrdersTable:runningTotal"},
            {"expression": "BirtDateTime.now()", "source": "element:GeneratedDate"},
            {"expression": 'dataSetRow["customerName"]', "source": "table:OrdersTable:customerName"},
            {"expression": 'params["ReportStartDate"].value', "source": "element:ReportSubtitle"},
        ]

        results = self.converter.convert_batch(expressions)
        self.assertEqual(len(results), 10)

        # Check all converted successfully or partially
        for r in results:
            self.assertIn(r["status"], ("success", "partial"),
                          f"Failed: {r.get('original', '?')}")

    def test_batch_summary_statistics(self):
        """Summary after batch should show conversion counts."""
        expressions = [
            {"expression": 'Total.sum(row["amount"])', "source": "table"},
            {"expression": "BirtDateTime.now()", "source": "element"},
            {"expression": 'BirtStr.toUpper(row["name"])', "source": "table"},
            {"expression": 'row["price"] * 1.1', "source": "computed"},
        ]
        self.converter.convert_batch(expressions)
        summary = self.converter.summary()
        self.assertEqual(summary["total"], 4)
        # summary returns {"total": N, "statuses": {"success": N, ...}}
        success_count = summary["statuses"].get("success", 0)
        self.assertTrue(success_count >= 3)


class TestRealisticEdgeCases(unittest.TestCase):
    """Edge cases found in real BIRT reports."""

    def setUp(self):
        self.converter = ExpressionConverter()

    def test_nested_function_calls(self):
        """BirtStr.concat("$", BirtStr.left(row["total"].toString(), 10))."""
        result = self.converter.convert(
            'BirtStr.concat("$", BirtStr.left(row["total"], 10))'
        )
        # Should at least partially convert
        self.assertIn(result["status"], ("success", "partial"))

    def test_multiline_expression(self):
        """Expressions can span multiple lines in BIRT XML."""
        expr = '''
            row["quantityOrdered"] > 50 ? row["priceEach"] * 0.9 : row["priceEach"]
        '''
        result = self.converter.convert(expr.strip())
        self.assertIn("IF(", result["converted"])

    def test_quarter_concatenation(self):
        """'Q' + BirtDateTime.quarter(row["orderDate"])."""
        result = self.converter.convert('"Q" + BirtDateTime.quarter(row["orderDate"])')
        # Should convert the quarter function at minimum
        self.assertIn(result["status"], ("success", "partial"))

    def test_variance_and_stddev(self):
        """Statistical functions used in financial reports."""
        var_result = self.converter.convert('Total.variance(row["priceEach"])')
        self.assertIn("VAR.S", var_result["converted"])

        std_result = self.converter.convert('Total.stdDev(row["priceEach"])')
        self.assertIn("STDEV.S", std_result["converted"])

    def test_rank_function(self):
        """RANKX generation for sorted reports."""
        result = self.converter.convert('Total.rank(row["lineTotal"])')
        self.assertIn("RANKX", result["converted"])


if __name__ == "__main__":
    unittest.main()
