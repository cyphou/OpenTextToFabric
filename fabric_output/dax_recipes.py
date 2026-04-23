"""DAX recipes — industry-specific KPI measure templates.

Pre-built DAX patterns for common business KPIs in Healthcare,
Finance, Retail, and Manufacturing domains.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Industry KPI recipes — each recipe is a dict with:
#   name, dax, description, category, industry, dependencies (optional column refs)
RECIPES: dict[str, list[dict[str, Any]]] = {
    "finance": [
        {
            "name": "Revenue YTD",
            "dax": 'TOTALYTD(SUM([Revenue]), \'Date\'[Date])',
            "description": "Year-to-date revenue",
            "category": "Revenue",
        },
        {
            "name": "Revenue vs Prior Year",
            "dax": 'SUM([Revenue]) - CALCULATE(SUM([Revenue]), SAMEPERIODLASTYEAR(\'Date\'[Date]))',
            "description": "Revenue change vs same period last year",
            "category": "Revenue",
        },
        {
            "name": "Revenue YoY %",
            "dax": 'DIVIDE(SUM([Revenue]) - CALCULATE(SUM([Revenue]), SAMEPERIODLASTYEAR(\'Date\'[Date])), CALCULATE(SUM([Revenue]), SAMEPERIODLASTYEAR(\'Date\'[Date])))',
            "description": "Year-over-year revenue growth percentage",
            "category": "Revenue",
        },
        {
            "name": "Gross Margin %",
            "dax": 'DIVIDE(SUM([Revenue]) - SUM([Cost]), SUM([Revenue]))',
            "description": "Gross margin as percentage of revenue",
            "category": "Profitability",
        },
        {
            "name": "Net Profit Margin",
            "dax": 'DIVIDE(SUM([NetIncome]), SUM([Revenue]))',
            "description": "Net profit as percentage of revenue",
            "category": "Profitability",
        },
        {
            "name": "EBITDA",
            "dax": 'SUM([Revenue]) - SUM([COGS]) - SUM([OpEx]) + SUM([Depreciation]) + SUM([Amortization])',
            "description": "Earnings before interest, taxes, depreciation, and amortization",
            "category": "Profitability",
        },
        {
            "name": "Current Ratio",
            "dax": 'DIVIDE(SUM([CurrentAssets]), SUM([CurrentLiabilities]))',
            "description": "Current assets to current liabilities ratio",
            "category": "Liquidity",
        },
        {
            "name": "Debt to Equity",
            "dax": 'DIVIDE(SUM([TotalDebt]), SUM([TotalEquity]))',
            "description": "Financial leverage ratio",
            "category": "Leverage",
        },
        {
            "name": "Working Capital",
            "dax": 'SUM([CurrentAssets]) - SUM([CurrentLiabilities])',
            "description": "Short-term financial health",
            "category": "Liquidity",
        },
        {
            "name": "DSO",
            "dax": 'DIVIDE(SUM([AccountsReceivable]), SUM([Revenue]) / 365)',
            "description": "Days Sales Outstanding",
            "category": "Efficiency",
        },
    ],
    "retail": [
        {
            "name": "Total Sales",
            "dax": 'SUM([SalesAmount])',
            "description": "Total sales amount",
            "category": "Sales",
        },
        {
            "name": "Average Transaction Value",
            "dax": 'DIVIDE(SUM([SalesAmount]), DISTINCTCOUNT([TransactionID]))',
            "description": "Average value per transaction",
            "category": "Sales",
        },
        {
            "name": "Units Per Transaction",
            "dax": 'DIVIDE(SUM([Quantity]), DISTINCTCOUNT([TransactionID]))',
            "description": "Average items per transaction",
            "category": "Sales",
        },
        {
            "name": "Conversion Rate",
            "dax": 'DIVIDE(DISTINCTCOUNT([TransactionID]), SUM([StoreVisits]))',
            "description": "Visitor to buyer conversion",
            "category": "Performance",
        },
        {
            "name": "Same Store Sales Growth",
            "dax": 'DIVIDE(SUM([SalesAmount]) - CALCULATE(SUM([SalesAmount]), SAMEPERIODLASTYEAR(\'Date\'[Date])), CALCULATE(SUM([SalesAmount]), SAMEPERIODLASTYEAR(\'Date\'[Date])))',
            "description": "Year-over-year sales growth for existing stores",
            "category": "Growth",
        },
        {
            "name": "Inventory Turnover",
            "dax": 'DIVIDE(SUM([COGS]), AVERAGE([Inventory]))',
            "description": "How quickly inventory sells",
            "category": "Inventory",
        },
        {
            "name": "Sell Through Rate",
            "dax": 'DIVIDE(SUM([UnitsSold]), SUM([UnitsReceived]))',
            "description": "Percentage of inventory sold",
            "category": "Inventory",
        },
        {
            "name": "Gross Margin Return on Investment",
            "dax": 'DIVIDE(SUM([GrossProfit]), AVERAGE([InventoryCost]))',
            "description": "Profit return on inventory investment",
            "category": "Profitability",
        },
        {
            "name": "Customer Retention Rate",
            "dax": 'DIVIDE(CALCULATE(DISTINCTCOUNT([CustomerID]), FILTER(ALL(), [PurchaseCount] > 1)), DISTINCTCOUNT([CustomerID]))',
            "description": "Rate of repeat customers",
            "category": "Customer",
        },
        {
            "name": "Revenue Per Square Foot",
            "dax": 'DIVIDE(SUM([SalesAmount]), SUM([StoreArea]))',
            "description": "Sales efficiency by store area",
            "category": "Performance",
        },
    ],
    "healthcare": [
        {
            "name": "Patient Volume",
            "dax": 'DISTINCTCOUNT([PatientID])',
            "description": "Unique patient count",
            "category": "Volume",
        },
        {
            "name": "Average Length of Stay",
            "dax": 'AVERAGE([LengthOfStay])',
            "description": "Average hospital stay in days",
            "category": "Operations",
        },
        {
            "name": "Bed Occupancy Rate",
            "dax": 'DIVIDE(SUM([OccupiedBedDays]), SUM([AvailableBedDays]))',
            "description": "Hospital bed utilization",
            "category": "Operations",
        },
        {
            "name": "Readmission Rate",
            "dax": 'DIVIDE(CALCULATE(DISTINCTCOUNT([PatientID]), [IsReadmission] = TRUE()), DISTINCTCOUNT([PatientID]))',
            "description": "30-day readmission percentage",
            "category": "Quality",
        },
        {
            "name": "Cost Per Patient",
            "dax": 'DIVIDE(SUM([TotalCost]), DISTINCTCOUNT([PatientID]))',
            "description": "Average cost per patient episode",
            "category": "Financial",
        },
        {
            "name": "Revenue Per Provider",
            "dax": 'DIVIDE(SUM([Revenue]), DISTINCTCOUNT([ProviderID]))',
            "description": "Revenue generated per healthcare provider",
            "category": "Productivity",
        },
        {
            "name": "Case Mix Index",
            "dax": 'AVERAGE([DRGWeight])',
            "description": "Average patient acuity",
            "category": "Clinical",
        },
        {
            "name": "Emergency Wait Time",
            "dax": 'AVERAGE([WaitTimeMinutes])',
            "description": "Average ER wait time in minutes",
            "category": "Patient Experience",
        },
    ],
    "manufacturing": [
        {
            "name": "OEE",
            "dax": '[Availability] * [Performance] * [Quality]',
            "description": "Overall Equipment Effectiveness",
            "category": "Production",
            "dependencies": ["Availability", "Performance", "Quality"],
        },
        {
            "name": "Availability",
            "dax": 'DIVIDE(SUM([RunTime]), SUM([PlannedProductionTime]))',
            "description": "Equipment availability rate",
            "category": "Production",
        },
        {
            "name": "Performance",
            "dax": 'DIVIDE(SUM([ActualOutput]), SUM([TheoreticalOutput]))',
            "description": "Equipment performance rate",
            "category": "Production",
        },
        {
            "name": "Quality Rate",
            "dax": 'DIVIDE(SUM([GoodUnits]), SUM([TotalUnits]))',
            "description": "First-pass yield rate",
            "category": "Quality",
        },
        {
            "name": "Scrap Rate",
            "dax": 'DIVIDE(SUM([ScrapUnits]), SUM([TotalUnits]))',
            "description": "Percentage of defective output",
            "category": "Quality",
        },
        {
            "name": "Throughput",
            "dax": 'DIVIDE(SUM([UnitsProduced]), SUM([Hours]))',
            "description": "Units produced per hour",
            "category": "Efficiency",
        },
        {
            "name": "Cycle Time",
            "dax": 'AVERAGE([CycleTimeMinutes])',
            "description": "Average production cycle time",
            "category": "Efficiency",
        },
        {
            "name": "Downtime %",
            "dax": 'DIVIDE(SUM([DowntimeMinutes]), SUM([PlannedProductionTime]) * 60)',
            "description": "Unplanned downtime percentage",
            "category": "Maintenance",
        },
        {
            "name": "MTBF",
            "dax": 'DIVIDE(SUM([RunTime]), COUNTROWS(FILTER(ALL(), [IsFailure] = TRUE())))',
            "description": "Mean Time Between Failures",
            "category": "Maintenance",
        },
        {
            "name": "MTTR",
            "dax": 'DIVIDE(SUM([RepairTime]), COUNTROWS(FILTER(ALL(), [IsFailure] = TRUE())))',
            "description": "Mean Time To Repair",
            "category": "Maintenance",
        },
    ],
}


class DaxRecipeLibrary:
    """Provides industry-specific DAX recipe templates."""

    def get_recipes(self, industry: str) -> list[dict[str, Any]]:
        """Get all recipes for an industry."""
        return RECIPES.get(industry.lower(), [])

    def get_industries(self) -> list[str]:
        """List available industries."""
        return sorted(RECIPES.keys())

    def get_recipe_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a recipe by name across all industries."""
        for industry_recipes in RECIPES.values():
            for recipe in industry_recipes:
                if recipe["name"].lower() == name.lower():
                    return recipe
        return None

    def get_recipes_by_category(self, industry: str, category: str) -> list[dict[str, Any]]:
        """Get recipes filtered by category within an industry."""
        return [
            r for r in RECIPES.get(industry.lower(), [])
            if r.get("category", "").lower() == category.lower()
        ]

    def apply_recipes(
        self,
        industry: str,
        table_name: str,
        column_map: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate ready-to-use measures from recipes.

        Args:
            industry: Industry name.
            table_name: Target table for measures.
            column_map: Optional mapping from recipe column names to actual column names.

        Returns:
            List of measure definitions ready for TMDL.
        """
        recipes = self.get_recipes(industry)
        measures = []
        for recipe in recipes:
            dax = recipe["dax"]
            if column_map:
                for placeholder, actual in column_map.items():
                    dax = dax.replace(f"[{placeholder}]", f"[{actual}]")
            measures.append({
                "name": recipe["name"].replace(" ", "_"),
                "table": table_name,
                "expression": dax,
                "description": recipe.get("description", ""),
                "displayFolder": recipe.get("category", ""),
            })
        return measures

    def summary(self) -> dict[str, int]:
        """Return recipe counts by industry."""
        return {industry: len(recipes) for industry, recipes in RECIPES.items()}


class ModelTemplate:
    """Industry-specific semantic model skeleton.

    Provides pre-built table/column/relationship structures for common
    industry data models.
    """

    TEMPLATES: dict[str, dict[str, Any]] = {
        "finance": {
            "tables": [
                {"name": "Fact_Transactions", "columns": ["TransactionID", "Date", "AccountID", "Amount", "Currency", "Type"]},
                {"name": "Dim_Accounts", "columns": ["AccountID", "AccountName", "AccountType", "ParentAccount"]},
                {"name": "Dim_CostCenters", "columns": ["CostCenterID", "Name", "Department", "Manager"]},
                {"name": "Dim_Date", "columns": ["Date", "Year", "Quarter", "Month", "MonthName", "WeekNum", "DayOfWeek", "IsBusinessDay"]},
            ],
            "relationships": [
                {"from": "Fact_Transactions.AccountID", "to": "Dim_Accounts.AccountID"},
                {"from": "Fact_Transactions.Date", "to": "Dim_Date.Date"},
            ],
        },
        "retail": {
            "tables": [
                {"name": "Fact_Sales", "columns": ["TransactionID", "Date", "ProductID", "StoreID", "CustomerID", "Quantity", "SalesAmount", "Discount"]},
                {"name": "Dim_Products", "columns": ["ProductID", "ProductName", "Category", "SubCategory", "Brand", "UnitPrice"]},
                {"name": "Dim_Stores", "columns": ["StoreID", "StoreName", "Region", "City", "StoreArea", "OpenDate"]},
                {"name": "Dim_Customers", "columns": ["CustomerID", "CustomerName", "Segment", "Region", "FirstPurchase"]},
                {"name": "Dim_Date", "columns": ["Date", "Year", "Quarter", "Month", "MonthName", "WeekNum", "DayOfWeek", "IsBusinessDay"]},
            ],
            "relationships": [
                {"from": "Fact_Sales.ProductID", "to": "Dim_Products.ProductID"},
                {"from": "Fact_Sales.StoreID", "to": "Dim_Stores.StoreID"},
                {"from": "Fact_Sales.CustomerID", "to": "Dim_Customers.CustomerID"},
                {"from": "Fact_Sales.Date", "to": "Dim_Date.Date"},
            ],
        },
        "healthcare": {
            "tables": [
                {"name": "Fact_Encounters", "columns": ["EncounterID", "Date", "PatientID", "ProviderID", "DepartmentID", "DRGCode", "LengthOfStay", "TotalCost"]},
                {"name": "Dim_Patients", "columns": ["PatientID", "Name", "DOB", "Gender", "InsuranceType"]},
                {"name": "Dim_Providers", "columns": ["ProviderID", "Name", "Specialty", "Department"]},
                {"name": "Dim_Date", "columns": ["Date", "Year", "Quarter", "Month", "MonthName", "WeekNum", "DayOfWeek", "IsBusinessDay"]},
            ],
            "relationships": [
                {"from": "Fact_Encounters.PatientID", "to": "Dim_Patients.PatientID"},
                {"from": "Fact_Encounters.ProviderID", "to": "Dim_Providers.ProviderID"},
                {"from": "Fact_Encounters.Date", "to": "Dim_Date.Date"},
            ],
        },
        "manufacturing": {
            "tables": [
                {"name": "Fact_Production", "columns": ["ProductionID", "Date", "LineID", "ProductID", "TotalUnits", "GoodUnits", "ScrapUnits", "RunTime", "DowntimeMinutes"]},
                {"name": "Dim_Lines", "columns": ["LineID", "LineName", "Plant", "Capacity"]},
                {"name": "Dim_Products", "columns": ["ProductID", "ProductName", "Category", "CycleTimeMinutes"]},
                {"name": "Dim_Date", "columns": ["Date", "Year", "Quarter", "Month", "MonthName", "WeekNum", "DayOfWeek", "IsBusinessDay"]},
            ],
            "relationships": [
                {"from": "Fact_Production.LineID", "to": "Dim_Lines.LineID"},
                {"from": "Fact_Production.ProductID", "to": "Dim_Products.ProductID"},
                {"from": "Fact_Production.Date", "to": "Dim_Date.Date"},
            ],
        },
    }

    def get_template(self, industry: str) -> dict[str, Any] | None:
        """Get the model template for an industry."""
        return self.TEMPLATES.get(industry.lower())

    def get_industries(self) -> list[str]:
        """List available model template industries."""
        return sorted(self.TEMPLATES.keys())

    def apply_template(self, industry: str, tmdl_generator: Any) -> None:
        """Apply a model template to a TMDL generator instance."""
        template = self.get_template(industry)
        if not template:
            logger.warning("No model template found for industry: %s", industry)
            return

        for table_def in template["tables"]:
            dataset = {
                "name": table_def["name"],
                "result_columns": [
                    {"name": col, "dataType": "string"} for col in table_def["columns"]
                ],
                "computed_columns": [],
                "column_hints": [],
            }
            tmdl_generator.add_table_from_dataset(dataset)

        logger.info("Applied %s model template: %d tables", industry, len(template["tables"]))
