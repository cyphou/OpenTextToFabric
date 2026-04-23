"""Generate the HTML migration dashboard from extraction/generation outputs.

Reads JSON intermediates from the output directory, computes aggregate
statistics, and writes a single ``MIGRATION_REPORT.html`` file.

Usage::

    from reporting.generate_report import generate_report
    generate_report(output_dir="./output")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from reporting.html_template import (
    html_open,
    html_close,
    stat_card,
    stat_grid,
    section_open,
    section_close,
    card,
    badge,
    fidelity_bar,
    donut_chart,
    bar_chart,
    data_table,
    tab_bar,
    tab_content,
    flow_diagram,
    cmd_box,
    esc,
    SUCCESS,
    WARN,
    FAIL,
    PBI_BLUE,
    PBI_DARK_BLUE,
    PURPLE,
    TEAL,
    ORANGE,
)
from reporting.migration_report import (
    MigrationReport,
    EXACT,
    APPROXIMATE,
    UNSUPPORTED,
    SKIPPED,
)

logger = logging.getLogger(__name__)

VERSION = "1.0.0"

# Palette for donut/bar segments
STATUS_COLORS = {
    EXACT: SUCCESS,
    APPROXIMATE: WARN,
    UNSUPPORTED: FAIL,
    SKIPPED: "#a19f9d",
}


# ═══════════════════════════════════════════════════════════════════════
#  JSON loaders
# ═══════════════════════════════════════════════════════════════════════

def _load_json(path: Path) -> Any:
    """Load a JSON file, return ``[]`` / ``{}`` if missing."""
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def _load_list(path: Path) -> list:
    data = _load_json(path)
    return data if isinstance(data, list) else []


def _load_dict(path: Path) -> dict:
    data = _load_json(path)
    return data if isinstance(data, dict) else {}


# ═══════════════════════════════════════════════════════════════════════
#  Build MigrationReport from output files
# ═══════════════════════════════════════════════════════════════════════

def _build_report(out: Path) -> MigrationReport:
    """Scan all extraction/generation outputs and build the fidelity tracker."""
    report = MigrationReport()

    # Nodes
    nodes = _load_list(out / "nodes.json")
    for n in nodes:
        report.add(
            name=n.get("name", ""),
            category="nodes",
            status=EXACT,
            source_type=n.get("type", ""),
            details=f"id={n.get('id', '')}",
        )

    # Documents
    docs = _load_list(out / "documents.json")
    for d in docs:
        report.add(
            name=d.get("name", ""),
            category="documents",
            status=EXACT,
            source_type=d.get("mime_type", ""),
        )

    # Permissions
    perms = _load_list(out / "permissions.json")
    for p in perms:
        status = EXACT if p.get("rls_role") else APPROXIMATE
        report.add(
            name=p.get("name", p.get("node_name", "")),
            category="permissions",
            status=status,
            details=p.get("rls_role", ""),
        )

    # Metadata
    meta = _load_list(out / "metadata.json")
    for m in meta:
        report.add(
            name=m.get("key", m.get("name", "")),
            category="metadata",
            status=EXACT,
            source_type=m.get("type", ""),
        )

    # Expressions (BIRT → DAX)
    expressions = _load_list(out / "expressions.json")
    for e in expressions:
        raw_status = e.get("status", "")
        if raw_status == "success":
            status = EXACT
        elif raw_status == "partial":
            status = APPROXIMATE
        elif raw_status == "unsupported":
            status = UNSUPPORTED
        else:
            status = SKIPPED
        report.add(
            name=e.get("column_name", e.get("expression", "")[:60]),
            category="expressions",
            status=status,
            details=e.get("dax", ""),
        )

    # Visuals
    visuals = _load_list(out / "visuals.json")
    for v in visuals:
        report.add(
            name=v.get("name", v.get("type", "")),
            category="visuals",
            status=EXACT,
            source_type=v.get("type", ""),
        )

    # Datasets
    datasets = _load_list(out / "datasets.json")
    for ds in datasets:
        report.add(
            name=ds.get("name", ""),
            category="datasets",
            status=EXACT,
        )

    # Connections
    connections = _load_list(out / "connections.json")
    for c in connections:
        report.add(
            name=c.get("name", c.get("driver", "")),
            category="connections",
            status=EXACT,
            source_type=c.get("driver", ""),
        )

    return report


# ═══════════════════════════════════════════════════════════════════════
#  Section builders
# ═══════════════════════════════════════════════════════════════════════

def _section_executive(report: MigrationReport) -> str:
    """Executive summary section."""
    fidelity = report.overall_fidelity()
    counts = report.status_counts()
    total = len(report.items)

    # Stat cards
    cards = [
        stat_card(total, "Total Items", accent="blue"),
        stat_card(f"{fidelity:.1f}%", "Overall Fidelity", accent="success" if fidelity >= 95 else "warn" if fidelity >= 80 else "fail"),
        stat_card(counts.get(EXACT, 0), "Exact", accent="success"),
        stat_card(counts.get(APPROXIMATE, 0), "Approximate", accent="warn"),
        stat_card(counts.get(UNSUPPORTED, 0), "Unsupported", accent="fail"),
        stat_card(counts.get(SKIPPED, 0), "Skipped", accent="purple"),
    ]

    html = section_open("exec-summary", "Executive Summary", "&#128202;")
    html += stat_grid(cards)

    # Category fidelity table
    cat_rows = []
    for cat in report.categories():
        cat_counts = report.status_counts(cat)
        cat_fid = report.category_fidelity(cat)
        cat_total = sum(cat_counts.values())
        cat_rows.append([
            f"<strong>{esc(cat.title())}</strong>",
            str(cat_total),
            str(cat_counts.get(EXACT, 0)),
            str(cat_counts.get(APPROXIMATE, 0)),
            str(cat_counts.get(UNSUPPORTED, 0)),
            fidelity_bar(cat_fid),
        ])

    html += data_table(
        headers=["Category", "Items", "Exact", "Approx", "Unsupported", "Fidelity"],
        rows=cat_rows,
        table_id="tbl-categories",
        sortable=True,
    )
    html += section_close()
    return html


def _section_extraction(report: MigrationReport) -> str:
    """Extraction overview with charts."""
    nodes = report.by_category("nodes")
    docs = report.by_category("documents")

    html = section_open("extraction", "Extraction Overview", "&#128230;")

    cards = [
        stat_card(len(nodes), "Nodes Extracted", accent="blue"),
        stat_card(len(docs), "Documents", accent="teal"),
        stat_card(len(report.by_category("metadata")), "Metadata Fields", accent="purple"),
        stat_card(len(report.by_category("permissions")), "Permission Entries", accent="success"),
    ]
    html += stat_grid(cards)

    # Charts row
    html += '<div class="chart-row">\n'

    # Donut: items by category
    cat_segments = []
    palette = [PBI_BLUE, TEAL, PURPLE, SUCCESS, ORANGE, PBI_DARK_BLUE]
    for i, cat in enumerate(report.categories()):
        cat_items = report.by_category(cat)
        if cat_items:
            cat_segments.append((cat.title(), len(cat_items), palette[i % len(palette)]))
    html += '<div class="chart-card">\n<h4>Items by Category</h4>\n'
    html += donut_chart(cat_segments, center_text=str(len(report.items)))
    html += '\n</div>\n'

    # Bar chart: node types
    type_counts: dict[str, int] = {}
    for n in nodes:
        t = n.source_type or "Other"
        type_counts[t] = type_counts.get(t, 0) + 1
    if type_counts:
        bar_items = [(t, float(c), PBI_BLUE) for t, c in sorted(type_counts.items(), key=lambda x: -x[1])[:10]]
        html += '<div class="chart-card">\n<h4>Node Types</h4>\n'
        html += bar_chart(bar_items)
        html += '\n</div>\n'

    html += '</div>\n'
    html += section_close()
    return html


def _section_content(report: MigrationReport) -> str:
    """Content inventory table."""
    items = report.by_category("nodes") + report.by_category("documents")
    if not items:
        return ""

    html = section_open("content", "Content Inventory", "&#128196;", collapsed=True)
    rows = []
    for it in items:
        rows.append([
            esc(it.name),
            esc(it.category.title()),
            esc(it.source_type),
            badge(it.status),
            esc(it.details),
        ])
    html += data_table(
        headers=["Name", "Category", "Type", "Status", "Details"],
        rows=rows,
        table_id="tbl-content",
        sortable=True,
        searchable=True,
    )
    html += section_close()
    return html


def _section_governance(report: MigrationReport) -> str:
    """Governance mapping section."""
    perms = report.by_category("permissions")
    if not perms:
        return ""

    html = section_open("governance", "Governance &amp; Security", "&#128274;")

    exact = sum(1 for p in perms if p.status == EXACT)
    approx = sum(1 for p in perms if p.status == APPROXIMATE)
    html += stat_grid([
        stat_card(len(perms), "Permission Entries", accent="blue"),
        stat_card(exact, "Mapped to RLS", accent="success"),
        stat_card(approx, "Approximate Mapping", accent="warn"),
    ])

    rows = []
    for p in perms:
        rows.append([
            esc(p.name),
            badge(p.status),
            esc(p.details or "—"),
        ])
    html += data_table(
        headers=["Source Permission", "Status", "RLS Role"],
        rows=rows,
        table_id="tbl-governance",
        sortable=True,
        searchable=True,
    )
    html += section_close()
    return html


def _section_expressions(report: MigrationReport) -> str:
    """Expression conversion section."""
    exprs = report.by_category("expressions")
    if not exprs:
        return ""

    counts = report.status_counts("expressions")
    fid = report.category_fidelity("expressions")

    html = section_open("expressions", "Expression Conversion (BIRT &#8594; DAX)", "&#128295;")
    html += stat_grid([
        stat_card(len(exprs), "Expressions", accent="blue"),
        stat_card(counts.get(EXACT, 0), "Exact", accent="success"),
        stat_card(counts.get(APPROXIMATE, 0), "Partial", accent="warn"),
        stat_card(counts.get(UNSUPPORTED, 0), "Unsupported", accent="fail"),
        stat_card(f"{fid:.1f}%", "Fidelity", accent="success" if fid >= 95 else "warn" if fid >= 80 else "fail"),
    ])

    # Donut chart
    segments = []
    for status, color in STATUS_COLORS.items():
        c = counts.get(status, 0)
        if c:
            segments.append((status.title(), c, color))
    if segments:
        html += '<div class="chart-row"><div class="chart-card"><h4>Conversion Status</h4>\n'
        html += donut_chart(segments, center_text=str(len(exprs)))
        html += '\n</div></div>\n'

    # Detail table
    rows = []
    for e in exprs:
        rows.append([
            f'<code>{esc(e.name)}</code>',
            badge(e.status),
            f'<code>{esc(e.details[:80])}</code>' if e.details else "—",
        ])
    html += data_table(
        headers=["Expression / Column", "Status", "DAX Output"],
        rows=rows,
        table_id="tbl-expressions",
        sortable=True,
        searchable=True,
    )
    html += section_close()
    return html


def _section_fabric(out: Path) -> str:
    """Fabric artifacts section."""
    html = section_open("fabric", "Fabric Artifacts", "&#9881;")

    # Pipeline diagram
    html += card(
        title="Migration Pipeline",
        content=flow_diagram([
            ("OpenText ECM", False),
            ("Extraction", True),
            ("JSON Intermediates", False),
            ("Generation", True),
            ("Fabric / Power BI", False),
        ]),
    )

    # List generated files
    generated: list[tuple[str, str]] = []
    for ext in ("*.json", "*.tmdl", "*.pbip", "*.py", "*.pq"):
        for f in sorted(out.glob(ext)):
            size = f.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
            generated.append((f.name, size_str))
    for sub in sorted(out.iterdir()):
        if sub.is_dir():
            count = sum(1 for _ in sub.rglob("*") if _.is_file())
            if count:
                generated.append((f"{sub.name}/", f"{count} files"))

    if generated:
        rows = [[esc(name), esc(size)] for name, size in generated]
        html += data_table(
            headers=["Artifact", "Size"],
            rows=rows,
            table_id="tbl-artifacts",
            sortable=True,
        )

    html += section_close()
    return html


def _section_birt(report: MigrationReport) -> str:
    """BIRT report conversion section."""
    visuals = report.by_category("visuals")
    datasets = report.by_category("datasets")
    if not visuals and not datasets:
        return ""

    html = section_open("birt", "BIRT Report Conversion", "&#128200;", collapsed=True)

    html += stat_grid([
        stat_card(len(visuals), "Visuals Mapped", accent="blue"),
        stat_card(len(datasets), "Datasets", accent="teal"),
        stat_card(len(report.by_category("connections")), "Connections", accent="purple"),
    ])

    # Tabs: visuals | datasets | connections
    html += tab_bar("birt-tabs", [
        ("visuals", f"Visuals ({len(visuals)})", True),
        ("datasets", f"Datasets ({len(datasets)})", False),
        ("connections", f"Connections ({len(report.by_category('connections'))})", False),
    ])

    # Visuals tab
    vrows = [[esc(v.name), esc(v.source_type), badge(v.status)] for v in visuals]
    html += tab_content("birt-tabs", "visuals", data_table(
        headers=["Visual", "BIRT Type", "Status"],
        rows=vrows,
        table_id="tbl-visuals",
        sortable=True,
    ), active=True)

    # Datasets tab
    drows = [[esc(d.name), badge(d.status)] for d in datasets]
    html += tab_content("birt-tabs", "datasets", data_table(
        headers=["Dataset", "Status"],
        rows=drows,
        table_id="tbl-datasets",
        sortable=True,
    ))

    # Connections tab
    conns = report.by_category("connections")
    crows = [[esc(c.name), esc(c.source_type), badge(c.status)] for c in conns]
    html += tab_content("birt-tabs", "connections", data_table(
        headers=["Connection", "Driver", "Status"],
        rows=crows,
        table_id="tbl-connections",
        sortable=True,
    ))

    html += section_close()
    return html


def _section_audit(out: Path) -> str:
    """Audit trail summary."""
    audit = _load_dict(out / "audit_trail.json")
    if not audit:
        return ""

    entries = audit.get("entries", [])
    if not entries:
        return ""

    html = section_open("audit", "Audit Trail", "&#128209;", collapsed=True)

    # Summary stats
    statuses: dict[str, int] = {}
    for e in entries:
        s = e.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1

    cards = [stat_card(len(entries), "Events", accent="blue")]
    for s, c in sorted(statuses.items()):
        accent = "success" if s == "success" else "warn" if s == "warning" else "fail" if s in ("error", "failed") else "purple"
        cards.append(stat_card(c, s.title(), accent=accent))
    html += stat_grid(cards)

    # Event table (last 100)
    rows = []
    for e in entries[-100:]:
        rows.append([
            esc(e.get("timestamp", "")),
            esc(e.get("action", "")),
            esc(e.get("source_type", "")),
            esc(e.get("source_name", "")),
            badge(e.get("status", "")),
            esc(e.get("details", "")[:80]),
        ])
    html += data_table(
        headers=["Time", "Action", "Source", "Name", "Status", "Details"],
        rows=rows,
        table_id="tbl-audit",
        sortable=True,
        searchable=True,
    )
    html += section_close()
    return html


# ═══════════════════════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════════════════════

def generate_report(
    output_dir: str = "./output",
    report_path: str | None = None,
) -> str:
    """Generate the full HTML migration dashboard.

    Args:
        output_dir: Directory containing extraction/generation JSON files.
        report_path: Where to write the report.
                     Defaults to ``<output_dir>/MIGRATION_REPORT.html``.

    Returns:
        The path to the generated HTML file.
    """
    out = Path(output_dir)
    if not report_path:
        report_path = str(out / "MIGRATION_REPORT.html")

    # Build fidelity report from outputs
    report = _build_report(out)

    # Save JSON sidecar
    report.save(out / "migration_report.json")

    # Assemble HTML
    html = html_open(
        title="OpenText \u2192 Fabric Migration Report",
        subtitle="Automated migration dashboard — content, governance, and conversion fidelity",
        version=VERSION,
    )
    html += _section_executive(report)
    html += _section_extraction(report)
    html += _section_content(report)
    html += _section_governance(report)
    html += _section_expressions(report)
    html += _section_fabric(out)
    html += _section_birt(report)
    html += _section_audit(out)
    html += html_close(version=VERSION)

    # Write
    rp = Path(report_path)
    rp.parent.mkdir(parents=True, exist_ok=True)
    with open(rp, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Migration report generated: %s", report_path)
    return str(rp)
