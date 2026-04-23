"""Tests for fabric_output.dax_recipes — industry KPI templates and model skeletons."""

import unittest
from unittest.mock import MagicMock

from fabric_output.dax_recipes import (
    RECIPES,
    DaxRecipeLibrary,
    ModelTemplate,
)


class TestRecipesData(unittest.TestCase):
    def test_has_four_industries(self):
        self.assertIn("finance", RECIPES)
        self.assertIn("retail", RECIPES)
        self.assertIn("healthcare", RECIPES)
        self.assertIn("manufacturing", RECIPES)

    def test_each_industry_has_recipes(self):
        for industry, recipes in RECIPES.items():
            self.assertGreater(len(recipes), 0, f"{industry} has no recipes")

    def test_recipe_structure(self):
        for industry, recipes in RECIPES.items():
            for r in recipes:
                self.assertIn("name", r, f"Missing name in {industry}")
                self.assertIn("dax", r, f"Missing dax in {industry}")
                self.assertIn("description", r, f"Missing description in {industry}")
                self.assertIn("category", r, f"Missing category in {industry}")


class TestDaxRecipeLibrary(unittest.TestCase):
    def setUp(self):
        self.lib = DaxRecipeLibrary()

    def test_get_recipes_finance(self):
        recipes = self.lib.get_recipes("finance")
        self.assertGreater(len(recipes), 5)

    def test_get_recipes_case_insensitive(self):
        r1 = self.lib.get_recipes("Finance")
        r2 = self.lib.get_recipes("FINANCE")
        self.assertEqual(len(r1), len(r2))

    def test_get_recipes_unknown_industry(self):
        recipes = self.lib.get_recipes("aerospace")
        self.assertEqual(recipes, [])

    def test_get_industries(self):
        industries = self.lib.get_industries()
        self.assertEqual(len(industries), 4)
        self.assertIn("finance", industries)
        self.assertIn("retail", industries)

    def test_get_recipe_by_name(self):
        recipe = self.lib.get_recipe_by_name("Revenue YTD")
        self.assertIsNotNone(recipe)
        self.assertEqual(recipe["name"], "Revenue YTD")

    def test_get_recipe_by_name_case_insensitive(self):
        recipe = self.lib.get_recipe_by_name("revenue ytd")
        self.assertIsNotNone(recipe)

    def test_get_recipe_by_name_not_found(self):
        recipe = self.lib.get_recipe_by_name("Nonexistent KPI")
        self.assertIsNone(recipe)

    def test_get_recipes_by_category(self):
        recipes = self.lib.get_recipes_by_category("finance", "Revenue")
        self.assertGreater(len(recipes), 0)
        for r in recipes:
            self.assertEqual(r["category"], "Revenue")

    def test_get_recipes_by_category_empty(self):
        recipes = self.lib.get_recipes_by_category("finance", "Nonexistent")
        self.assertEqual(recipes, [])

    def test_apply_recipes(self):
        measures = self.lib.apply_recipes("finance", "FactSales")
        self.assertGreater(len(measures), 0)
        for m in measures:
            self.assertEqual(m["table"], "FactSales")
            self.assertIn("name", m)
            self.assertIn("expression", m)
            self.assertIn("description", m)
            self.assertIn("displayFolder", m)

    def test_apply_recipes_with_column_map(self):
        measures = self.lib.apply_recipes(
            "retail",
            "Sales",
            column_map={"SalesAmount": "Amount", "TransactionID": "TxID"},
        )
        for m in measures:
            self.assertNotIn("[SalesAmount]", m["expression"])
            # Some recipes may not reference these columns, so just check no crash

    def test_apply_recipes_name_sanitized(self):
        measures = self.lib.apply_recipes("finance", "T")
        for m in measures:
            self.assertNotIn(" ", m["name"])

    def test_summary(self):
        s = self.lib.summary()
        self.assertEqual(len(s), 4)
        for industry, count in s.items():
            self.assertGreater(count, 0)

    def test_finance_has_dso(self):
        recipe = self.lib.get_recipe_by_name("DSO")
        self.assertIsNotNone(recipe)
        self.assertIn("AccountsReceivable", recipe["dax"])

    def test_retail_has_atv(self):
        recipe = self.lib.get_recipe_by_name("Average Transaction Value")
        self.assertIsNotNone(recipe)

    def test_healthcare_has_alos(self):
        recipe = self.lib.get_recipe_by_name("Average Length of Stay")
        self.assertIsNotNone(recipe)

    def test_manufacturing_has_oee(self):
        recipe = self.lib.get_recipe_by_name("OEE")
        self.assertIsNotNone(recipe)
        self.assertIn("dependencies", recipe)


class TestModelTemplate(unittest.TestCase):
    def setUp(self):
        self.mt = ModelTemplate()

    def test_get_template_finance(self):
        t = self.mt.get_template("finance")
        self.assertIsNotNone(t)
        self.assertIn("tables", t)
        self.assertIn("relationships", t)

    def test_get_template_all_industries(self):
        for industry in ["finance", "retail", "healthcare", "manufacturing"]:
            t = self.mt.get_template(industry)
            self.assertIsNotNone(t, f"No template for {industry}")
            self.assertGreater(len(t["tables"]), 0)

    def test_get_template_unknown(self):
        t = self.mt.get_template("aerospace")
        self.assertIsNone(t)

    def test_get_industries(self):
        industries = self.mt.get_industries()
        self.assertEqual(len(industries), 4)

    def test_tables_have_columns(self):
        for industry in self.mt.get_industries():
            t = self.mt.get_template(industry)
            for table in t["tables"]:
                self.assertIn("name", table)
                self.assertIn("columns", table)
                self.assertGreater(len(table["columns"]), 0)

    def test_relationships_reference_valid_tables(self):
        for industry in self.mt.get_industries():
            t = self.mt.get_template(industry)
            table_names = {tbl["name"] for tbl in t["tables"]}
            for rel in t["relationships"]:
                from_table = rel["from"].split(".")[0]
                to_table = rel["to"].split(".")[0]
                self.assertIn(from_table, table_names,
                    f"Relationship references unknown table {from_table} in {industry}")
                self.assertIn(to_table, table_names,
                    f"Relationship references unknown table {to_table} in {industry}")

    def test_apply_template(self):
        mock_gen = MagicMock()
        mock_gen.add_table_from_dataset = MagicMock()
        self.mt.apply_template("retail", mock_gen)
        # retail has 5 tables
        self.assertEqual(mock_gen.add_table_from_dataset.call_count, 5)

    def test_apply_template_unknown_industry(self):
        mock_gen = MagicMock()
        self.mt.apply_template("unknown", mock_gen)
        mock_gen.add_table_from_dataset.assert_not_called()

    def test_all_dim_date_have_standard_cols(self):
        """All industry models should have a Date dimension with Year/Month."""
        for industry in self.mt.get_industries():
            t = self.mt.get_template(industry)
            date_tables = [tbl for tbl in t["tables"] if "Date" in tbl["name"]]
            self.assertGreater(len(date_tables), 0, f"No Date table in {industry}")
            dt = date_tables[0]
            self.assertIn("Year", dt["columns"])
            self.assertIn("Month", dt["columns"])


if __name__ == "__main__":
    unittest.main()
