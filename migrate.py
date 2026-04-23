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

    out = Path(output_dir)

    # Load extracted data
    datasets = _load_json(out / "datasets.json")
    connections = _load_json(out / "connections.json")
    expressions = _load_json(out / "expressions.json")
    visuals_data = _load_json(out / "visuals.json")

    # Convert expressions
    expr_conv = ExpressionConverter()
    expr_conv.convert_batch(expressions)

    # Build semantic model
    tmdl = TMDLGenerator()
    for ds in datasets:
        tmdl.add_table_from_dataset(ds)
    tmdl.infer_relationships(datasets)
    tmdl.export(output_dir)

    # Generate M queries
    mq = MQueryGenerator()
    mq.generate_from_datasets(datasets, connections)

    # Map visuals
    vm = VisualMapper()
    pbi_visuals = vm.map_all(visuals_data)

    # Generate PBIP
    pbip = PBIPGenerator()
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


if __name__ == "__main__":
    sys.exit(main())
