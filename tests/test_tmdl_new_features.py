"""Tests for TMDL generator new features — hierarchies, calc groups, RLS roles."""

import tempfile
import unittest

from fabric_output.tmdl_generator import TMDLGenerator


def _add_table(gen, name, columns):
    """Helper to add a table directly for testing purposes."""
    gen.tables.append({
        "name": name,
        "columns": [{"name": c["name"], "dataType": c["dataType"], "sourceColumn": c["name"], "isHidden": False} for c in columns],
        "source_dataset": name,
        "source_query": "",
        "data_source": "",
    })


class TestTmdlHierarchies(unittest.TestCase):
    def test_add_hierarchy(self):
        gen = TMDLGenerator()
        _add_table(gen, "DimDate", [
            {"name": "Year", "dataType": "int64"},
            {"name": "Quarter", "dataType": "string"},
            {"name": "Month", "dataType": "string"},
            {"name": "Day", "dataType": "int64"},
        ])
        h = gen.add_hierarchy("DimDate", "Date Hierarchy", ["Year", "Quarter", "Month", "Day"])
        self.assertEqual(h["name"], "Date_Hierarchy")
        self.assertEqual(h["table"], "DimDate")
        self.assertEqual(len(h["levels"]), 4)

    def test_hierarchy_in_tmdl_output(self):
        gen = TMDLGenerator()
        _add_table(gen, "DimDate", [
            {"name": "Year", "dataType": "int64"},
            {"name": "Month", "dataType": "string"},
        ])
        gen.add_hierarchy("DimDate", "DateHier", ["Year", "Month"])
        files = gen.generate_tmdl()
        tmdl = files.get("tables/DimDate.tmdl", "")
        self.assertIn("hierarchy DateHier", tmdl)
        self.assertIn("level Year", tmdl)
        self.assertIn("level Month", tmdl)
        self.assertIn("ordinal: 0", tmdl)
        self.assertIn("ordinal: 1", tmdl)

    def test_hierarchy_with_display_folder(self):
        gen = TMDLGenerator()
        _add_table(gen, "Dim", [
            {"name": "A", "dataType": "string"},
            {"name": "B", "dataType": "string"},
        ])
        gen.add_hierarchy("Dim", "H1", ["A", "B"], display_folder="Navigation")
        files = gen.generate_tmdl()
        tmdl = files["tables/Dim.tmdl"]
        self.assertIn("displayFolder: Navigation", tmdl)

    def test_infer_hierarchies_date(self):
        gen = TMDLGenerator()
        _add_table(gen, "Calendar", [
            {"name": "Year", "dataType": "int64"},
            {"name": "Quarter", "dataType": "string"},
            {"name": "Month", "dataType": "string"},
            {"name": "Day", "dataType": "int64"},
        ])
        hierarchies = gen.infer_hierarchies()
        self.assertGreater(len(hierarchies), 0)
        names = [h["name"] for h in hierarchies]
        self.assertIn("Date_Hierarchy", names)

    def test_infer_hierarchies_geography(self):
        gen = TMDLGenerator()
        _add_table(gen, "Location", [
            {"name": "Country", "dataType": "string"},
            {"name": "State", "dataType": "string"},
            {"name": "City", "dataType": "string"},
        ])
        hierarchies = gen.infer_hierarchies()
        self.assertGreater(len(hierarchies), 0)

    def test_infer_hierarchies_no_match(self):
        gen = TMDLGenerator()
        _add_table(gen, "Fact", [
            {"name": "Amount", "dataType": "double"},
            {"name": "ID", "dataType": "int64"},
        ])
        hierarchies = gen.infer_hierarchies()
        self.assertEqual(len(hierarchies), 0)


class TestTmdlRoles(unittest.TestCase):
    def test_add_role(self):
        gen = TMDLGenerator()
        role = gen.add_role(
            "SalesManager",
            {"Sales": '[Region] = "West"'},
            description="Restricts to West region",
        )
        self.assertEqual(role["name"], "SalesManager")
        self.assertEqual(len(role["tablePermissions"]), 1)

    def test_role_in_tmdl_output(self):
        gen = TMDLGenerator()
        _add_table(gen, "Sales", [{"name": "Region", "dataType": "string"}])
        gen.add_role("WestOnly", {"Sales": '[Region] = "West"'})
        files = gen.generate_tmdl()
        self.assertIn("roles.tmdl", files)
        roles_tmdl = files["roles.tmdl"]
        self.assertIn("role WestOnly", roles_tmdl)
        self.assertIn("modelPermission: read", roles_tmdl)
        self.assertIn("tablePermission Sales", roles_tmdl)
        self.assertIn('[Region] = "West"', roles_tmdl)

    def test_role_with_description(self):
        gen = TMDLGenerator()
        gen.add_role("Admin", {}, description="Full access")
        files = gen.generate_tmdl()
        self.assertIn("description: Full access", files["roles.tmdl"])

    def test_multiple_roles(self):
        gen = TMDLGenerator()
        gen.add_role("R1", {"T1": "[A] = 1"})
        gen.add_role("R2", {"T2": "[B] = 2"})
        files = gen.generate_tmdl()
        roles_tmdl = files["roles.tmdl"]
        self.assertIn("role R1", roles_tmdl)
        self.assertIn("role R2", roles_tmdl)

    def test_add_rls_from_acl(self):
        gen = TMDLGenerator()
        acl_roles = [
            {"name": "Reader", "filters": {"Sales": "[Dept] = USERPRINCIPALNAME()"}, "description": "Row filter by user"},
        ]
        roles = gen.add_rls_from_acl(acl_roles)
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0]["name"], "Reader")

    def test_no_roles_no_file(self):
        gen = TMDLGenerator()
        _add_table(gen, "T", [{"name": "C", "dataType": "string"}])
        files = gen.generate_tmdl()
        self.assertNotIn("roles.tmdl", files)


class TestTmdlCalculationGroups(unittest.TestCase):
    def test_add_calculation_group(self):
        gen = TMDLGenerator()
        cg = gen.add_calculation_group("Time Intelligence", [
            {"name": "Current", "expression": "SELECTEDMEASURE()"},
            {"name": "YTD", "expression": "CALCULATE(SELECTEDMEASURE(), DATESYTD('Date'[Date]))"},
            {"name": "PY", "expression": "CALCULATE(SELECTEDMEASURE(), SAMEPERIODLASTYEAR('Date'[Date]))"},
        ], precedence=10)
        self.assertEqual(cg["name"], "Time_Intelligence")
        self.assertEqual(len(cg["items"]), 3)
        self.assertEqual(cg["precedence"], 10)

    def test_calc_group_in_tmdl_output(self):
        gen = TMDLGenerator()
        gen.add_calculation_group("TimeCG", [
            {"name": "Current", "expression": "SELECTEDMEASURE()"},
            {"name": "YTD", "expression": "CALCULATE(SELECTEDMEASURE(), DATESYTD('Date'[Date]))"},
        ])
        files = gen.generate_tmdl()
        self.assertIn("tables/TimeCG.tmdl", files)
        cg_tmdl = files["tables/TimeCG.tmdl"]
        self.assertIn("table TimeCG", cg_tmdl)
        self.assertIn("calculationGroup", cg_tmdl)
        self.assertIn("calculationItem Current", cg_tmdl)
        self.assertIn("calculationItem YTD", cg_tmdl)
        self.assertIn("SELECTEDMEASURE()", cg_tmdl)

    def test_calc_group_precedence(self):
        gen = TMDLGenerator()
        gen.add_calculation_group("CG1", [
            {"name": "I1", "expression": "SELECTEDMEASURE()"},
        ], precedence=5)
        files = gen.generate_tmdl()
        cg_tmdl = files["tables/CG1.tmdl"]
        self.assertIn("precedence: 5", cg_tmdl)

    def test_no_calc_groups(self):
        gen = TMDLGenerator()
        _add_table(gen, "T", [{"name": "C", "dataType": "string"}])
        files = gen.generate_tmdl()
        cg_files = [f for f in files if "calculationGroup" in files.get(f, "")]
        self.assertEqual(len(cg_files), 0)


class TestTmdlExportWithNewFeatures(unittest.TestCase):
    def test_full_export_with_hierarchy_role_calcgroup(self):
        gen = TMDLGenerator()
        _add_table(gen, "DimDate", [
            {"name": "Year", "dataType": "int64"},
            {"name": "Month", "dataType": "string"},
        ])
        _add_table(gen, "FactSales", [
            {"name": "Amount", "dataType": "double"},
            {"name": "Region", "dataType": "string"},
        ])
        gen.add_hierarchy("DimDate", "DateH", ["Year", "Month"])
        gen.add_role("RegionFilter", {"FactSales": '[Region] = "North"'})
        gen.add_calculation_group("TimeCalc", [
            {"name": "Actual", "expression": "SELECTEDMEASURE()"},
        ])

        with tempfile.TemporaryDirectory() as td:
            files = gen.export(td)
            self.assertGreater(len(files), 0)
            # Check hierarchy in DimDate
            dim_date_files = [f for f in files if "DimDate" in str(files[f])]
            self.assertGreater(len(dim_date_files), 0)


if __name__ == "__main__":
    unittest.main()
