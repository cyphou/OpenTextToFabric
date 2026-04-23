"""OpenText to Fabric Migration Tool — CLI Entry Point."""

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="migrate",
        description="Migrate OpenText ECM content and BIRT reports to Microsoft Fabric and Power BI.",
    )

    # Source configuration
    parser.add_argument(
        "--source-type",
        choices=["content-server", "documentum", "birt", "all"],
        required=True,
        help="Type of OpenText source system",
    )
    parser.add_argument("--server-url", help="OpenText server base URL")
    parser.add_argument("--username", help="OpenText username")
    parser.add_argument(
        "--password-env",
        help="Environment variable containing the password (never pass password directly)",
    )
    parser.add_argument(
        "--scope",
        help="Content scope path (e.g., /Enterprise/Finance)",
    )

    # BIRT input
    parser.add_argument(
        "--input",
        help="Path to .rptdesign file or directory of report files",
    )

    # Output configuration
    parser.add_argument(
        "--output-dir",
        default="./output",
        help="Output directory for generated artifacts (default: ./output)",
    )
    parser.add_argument(
        "--output-format",
        choices=["fabric", "pbip", "both"],
        default="both",
        help="Output format: fabric (Lakehouse/Pipeline), pbip (Power BI), or both",
    )

    # Assessment mode
    parser.add_argument(
        "--assess-only",
        action="store_true",
        help="Run pre-migration assessment without migrating",
    )

    # Batch mode
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process multiple content areas or reports in batch",
    )

    # Deployment
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Deploy generated artifacts to Fabric workspace",
    )
    parser.add_argument("--workspace-id", help="Target Fabric workspace ID")
    parser.add_argument("--tenant-id", help="Azure tenant ID for deployment")
    parser.add_argument("--client-id", help="Azure AD app client ID")
    parser.add_argument(
        "--client-secret-env",
        help="Environment variable containing the client secret",
    )
    parser.add_argument(
        "--create-workspace",
        action="store_true",
        help="Create workspace if it does not exist",
    )
    parser.add_argument("--workspace-name", help="Name for new workspace")
    parser.add_argument("--capacity-id", help="Fabric capacity ID for new workspace")

    # Batch resume
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a previous batch run from checkpoint",
    )

    # Report
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip HTML migration report generation",
    )

    # Verbosity
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )

    return parser


def configure_logging(verbosity: int) -> None:
    """Configure logging based on verbosity level."""
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """Main entry point for the migration tool."""
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.verbose)

    logger.info("OpenText to Fabric Migration Tool")
    logger.info("Source type: %s", args.source_type)

    from config import MigrationConfig
    from progress import MigrationProgress

    config = MigrationConfig.from_args(args)
    errors = config.validate()
    if errors:
        for err in errors:
            logger.error("Config error: %s", err)
        return 1

    progress = MigrationProgress()
    output_dir = args.output_dir

    try:
        # Assessment-only mode
        if args.assess_only:
            return _run_assessment(args, output_dir)

        # Batch mode — process multiple reports
        if args.batch:
            return _run_batch(args, output_dir, progress)

        if args.source_type in ("content-server", "all"):
            _run_content_server(args, output_dir, progress)
        if args.source_type in ("documentum", "all"):
            _run_documentum(args, output_dir, progress)
        if args.source_type in ("birt", "all"):
            _run_birt(args, output_dir, progress)

        # Generate Fabric artifacts
        if args.output_format in ("fabric", "both"):
            _generate_fabric(output_dir, progress)
        if args.output_format in ("pbip", "both") and args.source_type in ("birt", "all"):
            _generate_pbip(output_dir, progress)

        from pathlib import Path
        checkpoint = str(Path(output_dir) / "progress_checkpoint.json")
        progress.save_checkpoint(checkpoint)

        # Generate HTML migration report
        if not args.no_report:
            from reporting.generate_report import generate_report
            report_path = generate_report(output_dir=output_dir)
            logger.info("Migration report: %s", report_path)

        # Deploy to Fabric workspace
        if args.deploy:
            return _run_deploy(args, output_dir)

        logger.info("Migration complete. Summary: %s", progress.summary())
        return 0

    except Exception as e:
        logger.error("Migration failed: %s", e)
        from pathlib import Path
        checkpoint = str(Path(output_dir) / "progress_checkpoint.json")
        progress.save_checkpoint(checkpoint)
        return 1


def _run_content_server(args: argparse.Namespace, output_dir: str, progress: "MigrationProgress") -> None:
    """Run Content Server extraction pipeline."""
    import os
    from opentext_extract.content_server import ContentServerClient

    step = progress.add_step("content_server_extraction")
    step.start()

    password = os.environ.get(args.password_env, "") if args.password_env else ""
    client = ContentServerClient(
        base_url=args.server_url or "",
        username=args.username or "",
        password=password,
    )
    client.authenticate()

    root_id = 2000  # Enterprise workspace default; parse from --scope if provided
    files = client.extract_all(root_id=root_id, output_dir=output_dir)
    logger.info("Content Server extraction: %d files generated", len(files))
    step.complete()


def _run_documentum(args: argparse.Namespace, output_dir: str, progress: "MigrationProgress") -> None:
    """Run Documentum extraction pipeline."""
    import os
    from opentext_extract.documentum_client import DocumentumClient

    step = progress.add_step("documentum_extraction")
    step.start()

    password = os.environ.get(args.password_env, "") if args.password_env else ""
    client = DocumentumClient(
        base_url=args.server_url or "",
        username=args.username or "",
        password=password,
    )
    client.authenticate()

    files = client.extract_all(output_dir=output_dir)
    logger.info("Documentum extraction: %d files generated", len(files))
    step.complete()


def _run_birt(args: argparse.Namespace, output_dir: str, progress: "MigrationProgress") -> None:
    """Run BIRT report extraction pipeline."""
    from pathlib import Path
    from opentext_extract.birt_parser import BIRTParser

    step = progress.add_step("birt_extraction")
    step.start()

    input_path = Path(args.input) if args.input else None
    if not input_path or not input_path.exists():
        logger.warning("No BIRT input path specified or path not found")
        step.fail("No BIRT input path")
        return

    if input_path.is_file():
        parser = BIRTParser(input_path)
        parser.export_json(output_dir)
    elif input_path.is_dir():
        for rpt in input_path.glob("*.rptdesign"):
            parser = BIRTParser(rpt)
            parser.export_json(output_dir)

    step.complete()


def _generate_fabric(output_dir: str, progress: "MigrationProgress") -> None:
    """Generate Fabric artifacts from extracted data."""
    from fabric_output.lakehouse_generator import LakehouseGenerator
    from fabric_output.pipeline_generator import PipelineGenerator
    from fabric_output.notebook_generator import NotebookGenerator

    step = progress.add_step("fabric_generation")
    step.start()

    lh = LakehouseGenerator()
    lh.export(output_dir)

    pg = PipelineGenerator()
    pg.export(output_dir, tables=["documents", "folders", "metadata", "permissions"])

    nb = NotebookGenerator()
    nb.export(output_dir)

    step.complete()


def _generate_pbip(output_dir: str, progress: "MigrationProgress") -> None:
    """Generate Power BI report from BIRT extraction."""
    import json
    from pathlib import Path
    from report_converter.expression_converter import ExpressionConverter
    from report_converter.visual_mapper import VisualMapper
    from report_converter.pbip_generator import PBIPGenerator
    from fabric_output.tmdl_generator import TMDLGenerator
    from fabric_output.m_query_generator import MQueryGenerator

    step = progress.add_step("pbip_generation")
    step.start()

    report_name = "MigratedReport"
    out = Path(output_dir)
    project_dir = out / report_name  # .pbip project root

    # Load extracted data
    datasets = _load_json(out / "datasets.json")
    connections = _load_json(out / "connections.json")
    expressions = _load_json(out / "expressions.json")
    visuals_data = _load_json(out / "visuals.json")

    # Convert expressions → DAX measures
    expr_conv = ExpressionConverter()
    converted = expr_conv.convert_batch(expressions)

    # Build semantic model (TMDL) inside the project folder
    tmdl = TMDLGenerator(model_name=report_name)
    for ds in datasets:
        tmdl.add_table_from_dataset(ds)
    tmdl.infer_relationships(datasets)

    # Build table name lookup from dataset names
    table_names = {t["name"] for t in tmdl.tables}
    default_table = tmdl.tables[0]["name"] if tmdl.tables else "Measures"

    # Build column name lookup per table (to avoid measure/column name conflicts)
    table_column_names: dict[str, set[str]] = {}
    for t in tmdl.tables:
        table_column_names[t["name"]] = {
            c["name"] for c in t.get("columns", [])
        }

    # Add converted DAX measures
    for conv in converted:
        dax = conv.get("converted", "")
        if not dax or conv.get("status") not in ("success", "partial"):
            continue
        # Skip simple column references — only add aggregations as measures
        if dax.startswith("[") and dax.endswith("]") and dax.count("[") == 1:
            continue

        # Resolve table from source context (e.g. "dataset:SalesData")
        source = conv.get("source", "")
        table = default_table
        if ":" in source:
            parts = source.split(":")
            candidate = parts[-1]  # last segment
            if candidate in table_names:
                table = candidate
            elif parts[0] == "dataset" and len(parts) > 1 and parts[1] in table_names:
                table = parts[1]

        name = conv.get("column_name", "") or f"Measure_{len(tmdl.measures) + 1}"

        # Skip if a column with the same name already exists on this table
        # (PBI forbids a measure and column with the same name)
        if name in table_column_names.get(table, set()):
            continue

        tmdl.add_measure(table, name, dax)

    tmdl.export(str(project_dir))

    # Generate M queries
    mq = MQueryGenerator()
    mq.generate_from_datasets(datasets, connections)

    # Map visuals
    vm = VisualMapper()
    pbi_visuals = vm.map_all(visuals_data)

    # Generate PBIP project
    pbip = PBIPGenerator(report_name=report_name)
    pbip.generate(pbi_visuals, output_dir=output_dir)

    step.complete()


def _load_json(path: "Path") -> list:
    """Load JSON file, return empty list if not found."""
    import json
    from pathlib import Path as P
    p = P(path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return []


def _run_assessment(args: argparse.Namespace, output_dir: str) -> int:
    """Run pre-migration assessment only."""
    from pathlib import Path
    from assessment.scanner import ContentScanner
    from assessment.complexity import ComplexityScorer
    from assessment.readiness_report import ReadinessReport
    from assessment.strategy_advisor import StrategyAdvisor

    input_path = Path(args.input) if args.input else None
    if not input_path or not input_path.exists():
        logger.error("Assessment requires --input pointing to report(s)")
        return 1

    scanner = ContentScanner()
    if input_path.is_dir():
        scan_result = scanner.scan_directory(str(input_path))
    else:
        scan_result = scanner.scan_report_file(str(input_path))

    scorer = ComplexityScorer()
    complexity = scorer.score_batch(scan_result.get("reports", [scan_result]))

    advisor = StrategyAdvisor()
    strategy = advisor.recommend(scan_result, complexity)

    report = ReadinessReport()
    assessment = report.evaluate(scan_result, complexity, strategy)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "readiness_report.html"
    report.generate_html(assessment, str(html_path))

    logger.info("Assessment complete. Report: %s", html_path)
    logger.info(
        "Strategy: %s | Model: %s | Effort: %sh",
        strategy.get("approach_label"),
        strategy.get("model_mode"),
        strategy.get("estimated_effort_hours"),
    )
    return 0


def _run_batch(
    args: argparse.Namespace,
    output_dir: str,
    progress: "MigrationProgress",
) -> int:
    """Process multiple reports in batch mode with checkpoint/resume."""
    import json
    from pathlib import Path

    input_path = Path(args.input) if args.input else None
    if not input_path or not input_path.is_dir():
        logger.error("Batch mode requires --input pointing to a directory")
        return 1

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    checkpoint_path = out / "batch_checkpoint.json"

    # Load checkpoint for resume
    completed: set[str] = set()
    if args.resume and checkpoint_path.exists():
        with open(checkpoint_path, encoding="utf-8") as f:
            cp = json.load(f)
            completed = set(cp.get("completed", []))
        logger.info("Resuming batch: %d reports already done", len(completed))

    reports = sorted(input_path.glob("*.rptdesign"))
    if not reports:
        logger.warning("No .rptdesign files found in %s", input_path)
        return 0

    results: list[dict] = []
    for rpt in reports:
        if rpt.name in completed:
            logger.info("Skipping %s (already completed)", rpt.name)
            results.append({"report": rpt.name, "status": "skipped"})
            continue

        report_out = str(out / rpt.stem)
        logger.info("Processing %s → %s", rpt.name, report_out)

        try:
            from opentext_extract.birt_parser import BIRTParser

            parser = BIRTParser(rpt)
            parser.export_json(report_out)

            if args.output_format in ("pbip", "both"):
                _generate_pbip(report_out, progress)

            completed.add(rpt.name)
            results.append({"report": rpt.name, "status": "success"})
        except Exception as e:
            logger.error("Failed to process %s: %s", rpt.name, e)
            results.append({"report": rpt.name, "status": "failed", "error": str(e)})

        # Save checkpoint after each report
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump({"completed": sorted(completed), "results": results}, f, indent=2)

    successes = sum(1 for r in results if r["status"] == "success")
    failures = sum(1 for r in results if r["status"] == "failed")
    logger.info("Batch complete: %d success, %d failed, %d skipped", successes, failures, len(results) - successes - failures)
    return 1 if failures > 0 else 0


def _run_deploy(args: argparse.Namespace, output_dir: str) -> int:
    """Deploy migration output to Fabric workspace."""
    import os
    from deploy.deployer import Deployer

    client_secret = ""
    if args.client_secret_env:
        client_secret = os.environ.get(args.client_secret_env, "")
        if not client_secret:
            logger.error("Environment variable %s is empty", args.client_secret_env)
            return 1

    deployer = Deployer(
        workspace_id=args.workspace_id or "",
        tenant_id=args.tenant_id or "",
        client_id=args.client_id or "",
        client_secret=client_secret,
        create_workspace=args.create_workspace,
        workspace_name=args.workspace_name or "",
        capacity_id=args.capacity_id or "",
    )

    result = deployer.deploy(output_dir)
    errors = result.get("errors", [])
    if errors:
        for err in errors:
            logger.error("Deploy error: %s", err)
        return 1

    for step_r in result.get("steps", []):
        logger.info("Deploy %s: %s", step_r.get("step"), step_r.get("status"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
