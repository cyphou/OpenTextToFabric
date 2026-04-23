"""BIRT .rptdesign XML parser.

Parses BIRT report definition files to extract data sources, datasets,
expressions, visual elements, parameters, and layout.
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# BIRT XML namespaces
_NS = {
    "report": "http://www.eclipse.org/birt/2005/design",
}


class BIRTParseError(Exception):
    """Raised when BIRT report parsing fails."""


class BIRTParser:
    """Parser for BIRT .rptdesign XML files."""

    def __init__(self, report_path: str | Path):
        self.report_path = Path(report_path)
        if not self.report_path.exists():
            raise FileNotFoundError(f"Report file not found: {report_path}")
        if not self.report_path.suffix.lower() == ".rptdesign":
            logger.warning("File does not have .rptdesign extension: %s", report_path)

        self._tree: ET.ElementTree | None = None
        self._root: ET.Element | None = None

    def parse(self) -> dict[str, Any]:
        """Parse the .rptdesign file and return structured data."""
        logger.info("Parsing BIRT report: %s", self.report_path)
        try:
            self._tree = ET.parse(self.report_path)
            self._root = self._tree.getroot()
        except ET.ParseError as e:
            raise BIRTParseError(f"Invalid XML in {self.report_path}: {e}") from e

        # Strip XML namespaces so all findall() calls work without prefixes
        self._strip_namespaces(self._root)

        result: dict[str, Any] = {
            "report_name": self.report_path.stem,
            "report_path": str(self.report_path),
            "data_sources": self._extract_data_sources(),
            "datasets": self._extract_datasets(),
            "parameters": self._extract_parameters(),
            "body": self._extract_body(),
            "styles": self._extract_styles(),
            "page_setup": self._extract_page_setup(),
        }

        logger.info(
            "Parsed: %d data sources, %d datasets, %d parameters, %d body elements",
            len(result["data_sources"]),
            len(result["datasets"]),
            len(result["parameters"]),
            len(result["body"]),
        )
        return result

    # ── Data Sources ────────────────────────────────────────────

    def _extract_data_sources(self) -> list[dict[str, Any]]:
        """Extract data source definitions (JDBC, ODA, scripted)."""
        sources: list[dict[str, Any]] = []
        root = self._root
        assert root is not None

        for ds in self._find_all("data-sources/*"):
            source_type = self._local_tag(ds.tag)
            source: dict[str, Any] = {
                "type": source_type,
                "name": ds.get("name", ""),
                "id": ds.get("id", ""),
            }

            # ODA data source properties
            for prop in ds.findall(".//property"):
                prop_name = prop.get("name", "")
                prop_value = prop.text or ""
                if prop_name in ("odaDriverClass", "odaURL", "odaUser", "odaDataSource"):
                    source[prop_name] = prop_value
                elif prop_name == "extensionID":
                    source["extension_id"] = prop_value

            # JDBC-specific
            for prop in ds.findall(".//property"):
                name = prop.get("name", "")
                if name in ("driverClass", "url", "user"):
                    source[name] = prop.text or ""

            sources.append(source)

        return sources

    # ── Datasets ────────────────────────────────────────────────

    def _extract_datasets(self) -> list[dict[str, Any]]:
        """Extract dataset definitions (SQL queries, parameters, computed columns)."""
        datasets: list[dict[str, Any]] = []

        for ds in self._find_all("data-sets/*"):
            dataset: dict[str, Any] = {
                "type": self._local_tag(ds.tag),
                "name": ds.get("name", ""),
                "id": ds.get("id", ""),
                "data_source": "",
                "query": "",
                "parameters": [],
                "computed_columns": [],
                "column_hints": [],
                "result_columns": [],
            }

            # Data source reference
            for prop in ds.findall(".//property"):
                name = prop.get("name", "")
                if name == "dataSource":
                    dataset["data_source"] = prop.text or ""
                elif name == "queryText":
                    dataset["query"] = prop.text or ""

            # Query text can also be in xml-property
            for xp in ds.findall(".//xml-property"):
                if xp.get("name") == "queryText":
                    dataset["query"] = (xp.text or "").strip()

            # List-property for parameters
            for lp in ds.findall(".//list-property"):
                lp_name = lp.get("name", "")
                if lp_name == "parameters":
                    for param in lp.findall("structure"):
                        p: dict[str, str] = {}
                        for prop in param.findall("property"):
                            p[prop.get("name", "")] = prop.text or ""
                        dataset["parameters"].append(p)
                elif lp_name == "computedColumns":
                    for col in lp.findall("structure"):
                        c: dict[str, str] = {}
                        for prop in col.findall("property"):
                            c[prop.get("name", "")] = prop.text or ""
                        for expr in col.findall("expression"):
                            c["expression"] = expr.text or ""
                            c["expression_type"] = expr.get("type", "javascript")
                        dataset["computed_columns"].append(c)
                elif lp_name == "columnHints":
                    for hint in lp.findall("structure"):
                        h: dict[str, str] = {}
                        for prop in hint.findall("property"):
                            h[prop.get("name", "")] = prop.text or ""
                        dataset["column_hints"].append(h)
                elif lp_name in ("resultSetColumns", "resultSet"):
                    for col in lp.findall("structure"):
                        rc: dict[str, str] = {}
                        for prop in col.findall("property"):
                            rc[prop.get("name", "")] = prop.text or ""
                        dataset["result_columns"].append(rc)

            datasets.append(dataset)

        return datasets

    # ── Parameters ──────────────────────────────────────────────

    def _extract_parameters(self) -> list[dict[str, Any]]:
        """Extract report-level parameter definitions."""
        params: list[dict[str, Any]] = []

        for p in self._find_all("parameters/*"):
            param: dict[str, Any] = {
                "type": self._local_tag(p.tag),
                "name": p.get("name", ""),
                "id": p.get("id", ""),
            }
            for prop in p.findall(".//property"):
                name = prop.get("name", "")
                if name in ("dataType", "paramType", "isRequired", "defaultValue",
                            "promptText", "controlType", "allowBlank", "mustMatch"):
                    param[name] = prop.text or ""
            for expr in p.findall(".//expression"):
                param["default_expression"] = expr.text or ""
            params.append(param)

        return params

    # ── Body / Layout Elements ──────────────────────────────────

    def _extract_body(self) -> list[dict[str, Any]]:
        """Extract body elements (tables, charts, grids, labels, text, images)."""
        elements: list[dict[str, Any]] = []

        for elem in self._find_all("body/*"):
            parsed = self._parse_element(elem)
            if parsed:
                elements.append(parsed)

        return elements

    def _parse_element(self, elem: ET.Element, depth: int = 0) -> dict[str, Any]:
        """Recursively parse a body element."""
        tag = self._local_tag(elem.tag)
        element: dict[str, Any] = {
            "element_type": tag,
            "name": elem.get("name", ""),
            "id": elem.get("id", ""),
            "depth": depth,
            "properties": {},
            "children": [],
            "expressions": [],
        }

        # Collect properties
        for prop in elem.findall("property"):
            element["properties"][prop.get("name", "")] = prop.text or ""

        # Collect expressions
        for expr in elem.findall(".//expression"):
            element["expressions"].append({
                "name": expr.get("name", ""),
                "type": expr.get("type", "javascript"),
                "value": expr.text or "",
            })

        # Extended item type (charts, crosstabs)
        # extensionName may appear as XML attribute OR as a child <property>
        ext_type = elem.get("extensionName", "")
        if not ext_type:
            for prop in elem.findall("property"):
                if prop.get("name") == "extensionName":
                    ext_type = prop.text or ""
                    break
        if ext_type:
            element["extension_name"] = ext_type
            element["chart_config"] = self._extract_chart_config(elem)
            # Capture dataSet for charts/extended items so visuals can bind data
            for prop in elem.findall("property"):
                if prop.get("name") == "dataSet":
                    element["dataset"] = prop.text or ""
                    break

        # Table-specific: groups, header, detail, footer
        if tag == "table":
            element["dataset"] = ""
            for prop in elem.findall("property"):
                if prop.get("name") == "dataSet":
                    element["dataset"] = prop.text or ""
            element["groups"] = self._extract_table_groups(elem)
            element["columns"] = self._extract_table_columns(elem)

        # Cross-tab
        if tag == "extended-item" and ext_type == "Crosstab":
            element["crosstab_config"] = self._extract_crosstab_config(elem)

        # Recurse into children
        child_containers = ["cell", "row", "column", "grid", "list", "group"]
        for child in elem:
            child_tag = self._local_tag(child.tag)
            if child_tag in child_containers or child_tag in ("table", "grid", "list", "extended-item", "label", "text", "data", "image"):
                parsed_child = self._parse_element(child, depth + 1)
                if parsed_child:
                    element["children"].append(parsed_child)

        return element

    def _extract_table_groups(self, table_elem: ET.Element) -> list[dict[str, Any]]:
        """Extract group definitions from a table element."""
        groups: list[dict[str, Any]] = []
        for group in table_elem.findall(".//group"):
            g: dict[str, Any] = {
                "name": group.get("name", ""),
                "key_expression": "",
            }
            for expr in group.findall("expression"):
                if expr.get("name") == "keyExpr":
                    g["key_expression"] = expr.text or ""
            groups.append(g)
        return groups

    def _extract_table_columns(self, table_elem: ET.Element) -> list[dict[str, Any]]:
        """Extract column bindings from a table."""
        columns: list[dict[str, Any]] = []
        for lp in table_elem.findall("list-property"):
            if lp.get("name") == "boundDataColumns":
                for struct in lp.findall("structure"):
                    col: dict[str, str] = {}
                    for prop in struct.findall("property"):
                        col[prop.get("name", "")] = prop.text or ""
                    for expr in struct.findall("expression"):
                        col["expression"] = expr.text or ""
                        col["expression_type"] = expr.get("type", "javascript")
                    columns.append(col)
        return columns

    def _extract_chart_config(self, elem: ET.Element) -> dict[str, Any]:
        """Extract chart configuration from an extended item."""
        import re
        config: dict[str, Any] = {"chart_type": "", "series": [], "categories": []}
        for xp in elem.findall(".//xml-property"):
            if xp.get("name") != "xmlRepresentation":
                continue
            # xml-property may contain text OR nested children (model:Chart…)
            chart_xml = xp.text or ""
            for child in xp:
                try:
                    chart_xml += ET.tostring(child, encoding="unicode")
                except Exception:
                    pass
            config["raw_xml"] = chart_xml[:2000]  # truncate for safety

            # Prefer explicit <Type>...</Type>
            m = re.search(r"<(?:\w+:)?Type[^>]*>\s*([A-Za-z]+)\s*<", chart_xml)
            type_token = m.group(1).lower() if m else ""
            if not type_token:
                low = chart_xml.lower()
                for t in ("bar", "column", "line", "pie", "donut", "scatter", "bubble", "area"):
                    if t in low:
                        type_token = t
                        break
            config["chart_type"] = type_token or "unknown"

            # Extract category and value fields (strip namespace prefixes)
            for cat in re.findall(r"<(?:\w+:)?Category[^>]*>\s*([^<\s]+)\s*<", chart_xml):
                if cat:
                    config["categories"].append({"name": cat})
            for val in re.findall(r"<(?:\w+:)?Value[^>]*>\s*([^<\s]+)\s*<", chart_xml):
                if val:
                    config["series"].append({"name": val})
        return config

    def _extract_crosstab_config(self, elem: ET.Element) -> dict[str, Any]:
        """Extract crosstab (pivot table) configuration."""
        config: dict[str, Any] = {"rows": [], "columns": [], "measures": []}
        for xp in elem.findall(".//xml-property"):
            if xp.get("name") == "xmlRepresentation":
                config["raw_xml"] = (xp.text or "")[:2000]
        return config

    # ── Styles ──────────────────────────────────────────────────

    def _extract_styles(self) -> list[dict[str, Any]]:
        """Extract style definitions."""
        styles: list[dict[str, Any]] = []
        for style in self._find_all("styles/*"):
            s: dict[str, Any] = {
                "name": style.get("name", ""),
                "properties": {},
            }
            for prop in style.findall("property"):
                s["properties"][prop.get("name", "")] = prop.text or ""
            styles.append(s)
        return styles

    # ── Page Setup ──────────────────────────────────────────────

    def _extract_page_setup(self) -> dict[str, Any]:
        """Extract page setup (master pages)."""
        setup: dict[str, Any] = {"master_pages": []}
        for mp in self._find_all("page-setup/*"):
            page: dict[str, Any] = {
                "name": mp.get("name", ""),
                "type": self._local_tag(mp.tag),
                "properties": {},
            }
            for prop in mp.findall("property"):
                page["properties"][prop.get("name", "")] = prop.text or ""
            setup["master_pages"].append(page)
        return setup

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _strip_namespaces(root: ET.Element) -> None:
        """Remove all XML namespace prefixes from tags in-place."""
        for elem in root.iter():
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]

    def _find_all(self, xpath: str) -> list[ET.Element]:
        """Find elements (namespaces already stripped)."""
        assert self._root is not None
        return self._root.findall(xpath)

    @staticmethod
    def _local_tag(tag: str) -> str:
        """Strip namespace from tag name."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    # ── Export to JSON ──────────────────────────────────────────

    def export_json(self, output_dir: str | Path) -> dict[str, Path]:
        """Parse and export all data to intermediate JSON files."""
        data = self.parse()
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        files: dict[str, Path] = {}

        # Split into separate JSON files matching intermediate format
        files["reports.json"] = _write_json(out / "reports.json", [{
            "report_name": data["report_name"],
            "report_path": data["report_path"],
            "page_setup": data["page_setup"],
        }])
        files["datasets.json"] = _write_json(out / "datasets.json", data["datasets"])
        files["connections.json"] = _write_json(out / "connections.json", data["data_sources"])
        files["expressions.json"] = _write_json(
            out / "expressions.json",
            self._collect_all_expressions(data),
        )
        files["visuals.json"] = _write_json(out / "visuals.json", data["body"])

        return files

    def _collect_all_expressions(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Collect all expressions from datasets and body elements."""
        expressions: list[dict[str, Any]] = []

        # From computed columns in datasets
        for ds in data["datasets"]:
            for cc in ds.get("computed_columns", []):
                if cc.get("expression"):
                    expressions.append({
                        "source": f"dataset:{ds['name']}",
                        "column_name": cc.get("name", ""),
                        "expression": cc["expression"],
                        "expression_type": cc.get("expression_type", "javascript"),
                        "data_type": cc.get("dataType", ""),
                    })

        # From body elements
        self._collect_element_expressions(data["body"], expressions)

        return expressions

    def _collect_element_expressions(
        self,
        elements: list[dict[str, Any]],
        out: list[dict[str, Any]],
    ) -> None:
        """Recursively collect expressions from elements."""
        for elem in elements:
            for expr in elem.get("expressions", []):
                if expr.get("value"):
                    out.append({
                        "source": f"element:{elem.get('element_type', '')}:{elem.get('name', '')}",
                        "expression": expr["value"],
                        "expression_type": expr.get("type", "javascript"),
                    })
            # Table column bindings
            for col in elem.get("columns", []):
                if col.get("expression"):
                    out.append({
                        "source": f"table:{elem.get('name', '')}:column:{col.get('name', '')}",
                        "column_name": col.get("name", ""),
                        "expression": col["expression"],
                        "expression_type": col.get("expression_type", "javascript"),
                    })
            self._collect_element_expressions(elem.get("children", []), out)


def _write_json(path: Path, data: Any) -> Path:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return path
