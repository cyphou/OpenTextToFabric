<p align="center">
  <img src="docs/assets/logo.svg" alt="OpenText → Fabric" width="720"/>
</p>

<p align="center">
  <strong>Automated migration of OpenText ECM &amp; BIRT reports to Microsoft Fabric and Power BI</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#output-artifacts">Artifacts</a> ·
  <a href="#html-migration-dashboard">Dashboard</a> ·
  <a href="docs/AGENTS.md">Agents</a> ·
  <a href="docs/ARCHITECTURE.md">Deep-Dive</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&logoColor=white" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/dependencies-zero-brightgreen" alt="Zero Dependencies"/>
  <img src="https://img.shields.io/badge/tests-405%20passed-107c10?logo=pytest&logoColor=white" alt="Tests"/>
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License"/>
  <img src="https://img.shields.io/badge/agents-10-8764b8" alt="10 Agents"/>
</p>

---

## Overview

**OpenTextToFabric** extracts content, metadata, reports, and permissions from OpenText systems and generates ready-to-deploy Microsoft Fabric artifacts and Power BI reports — in a single CLI command.

| Capability | Details |
|:---|:---|
| **37 source modules** | Extraction, conversion, governance, deployment, reporting |
| **405 tests** | Comprehensive coverage across all modules |
| **Zero dependencies** | Pure Python stdlib — no pip install needed for core |
| **10-agent architecture** | Specialized agents for each migration concern |
| **HTML dashboard** | Interactive migration report with fidelity scoring |

---

## Architecture

<p align="center">
  <img src="docs/assets/architecture.svg" alt="Architecture Diagram" width="900"/>
</p>

The tool follows a **2-step pipeline** design — identical to the proven [TableauToPowerBI](https://github.com/cyphou/TableauToPowerBI) architecture:

```
Step 1: EXTRACTION                        Step 2: GENERATION
┌──────────────────┐                      ┌──────────────────┐
│  Content Server  │──┐                   │  fabric_output/  │──→  Fabric Lakehouse
│  Documentum      │──┤──→ 15+ JSON ──→──┤  report_converter/│──→  Power BI .pbip
│  BIRT .rptdesign │──┘    intermediates  │  governance/     │──→  RLS + Purview
└──────────────────┘                      └──────────────────┘
```

Each JSON intermediate is a clean, inspectable contract between the two steps. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full deep-dive and [docs/AGENTS.md](docs/AGENTS.md) for the 10-agent model.

---

## Quick Start

### Content Server → Fabric Lakehouse

```bash
python migrate.py \
  --source-type content-server \
  --server-url https://cs.example.com/otcs/cs.exe \
  --username admin --password-env OT_PASSWORD \
  --scope "/Enterprise/Finance" \
  --output-dir ./output
```

### BIRT Report → Power BI

```bash
python migrate.py \
  --source-type birt \
  --input ./reports/sales_report.rptdesign \
  --output-dir ./output
```

### Pre-Migration Assessment

```bash
python migrate.py \
  --source-type content-server \
  --server-url https://cs.example.com/otcs/cs.exe \
  --assess-only \
  --output-dir ./assessment
```

### Full Migration (all sources → all targets)

```bash
python migrate.py \
  --source-type all \
  --server-url https://cs.example.com/otcs/cs.exe \
  --username admin --password-env OT_PASSWORD \
  --input ./reports/ \
  --output-format both \
  --output-dir ./output
```

> **Tip:** Add `-v` for INFO logging or `-vv` for DEBUG. Use `--no-report` to skip HTML dashboard generation.

---

## Supported Sources

| Source | API | Output |
|:---|:---|:---|
| **OpenText Content Server** | REST v2 | Lakehouse + Data Factory + Notebooks |
| **OpenText Documentum** | REST / DFC | Lakehouse + Data Factory + Notebooks |
| **BIRT / iHub** | .rptdesign XML | Power BI (.pbip PBIR v4.0 + TMDL) |

---

## Output Artifacts

### 🔷 Fabric Native

| Artifact | Description |
|:---|:---|
| **Lakehouse DDL** | Delta table schemas for documents, metadata, classifications |
| **Data Factory Pipelines** | REST connector → OneLake copy activities (3-stage orchestration) |
| **PySpark Notebooks** | ETL for document processing, metadata enrichment, OCR |
| **Dataflow Gen2** | Power Query M for incremental data ingestion |
| **TMDL Semantic Model** | Tables, columns, measures, relationships |

### 🟡 Power BI (from BIRT reports)

| Artifact | Description |
|:---|:---|
| **.pbip Project** | PBIR v4.0 report definition |
| **DAX Measures** | 80+ BIRT JavaScript → DAX conversions |
| **Power Query M** | Converted from BIRT JDBC data sources |
| **Visual Mappings** | BIRT chart/table/crosstab → PBI visuals |

### 🟠 Governance & Security

| Artifact | Description |
|:---|:---|
| **RLS Roles** | Mapped from Content Server / Documentum ACLs |
| **Purview Sensitivity Labels** | Mapped from OpenText classifications |
| **Retention Policies** | Mapped to Purview retention |
| **Audit Trail** | Complete migration evidence chain (JSON + CSV) |
| **Security Validation** | Path traversal defense, credential scrubbing, ZIP-slip protection |

---

## HTML Migration Dashboard

Every migration produces an interactive **MIGRATION_REPORT.html** — a professional dashboard built with the same Fluent/Power BI design language used in the TableauToPowerBI project.

### Features

- 📊 **Executive Summary** — stat cards, overall fidelity score, category breakdown
- 📦 **Extraction Overview** — donut charts by category, bar charts by node type
- 📄 **Content Inventory** — sortable, searchable table of all extracted items
- 🔐 **Governance Mapping** — ACL → RLS role mapping with status badges
- 🔧 **Expression Conversion** — BIRT JS → DAX success/partial/unsupported breakdown
- ⚙️ **Fabric Artifacts** — pipeline flow diagram, generated file listing
- 📈 **BIRT Report Conversion** — visual/dataset/connection tabs
- 📋 **Audit Trail** — timestamped event log
- 🌙 **Dark Mode** — toggle with persistent preference
- 🖨️ **Print-ready** — clean print stylesheet
- 🛡️ **XSS-safe** — all user data HTML-escaped

> Generate with `python -c "from reporting.generate_report import generate_report; generate_report('./output')"`

---

## Project Structure

```
OpenTextToFabric/
├── migrate.py                  # CLI entry point & pipeline orchestrator
├── config.py                   # MigrationConfig (from_args / from_file / validate)
├── progress.py                 # Step-level progress tracking + checkpoints
│
├── opentext_extract/           # ── Step 1: Extraction ──────────────────
│   ├── api_client.py           #    Base REST client (auth, pagination, retry)
│   ├── content_server.py       #    Content Server REST v2 → 5 JSON files
│   ├── documentum_client.py    #    Documentum REST → 5 JSON files
│   └── birt_parser.py          #    .rptdesign XML → 4 JSON files
│
├── content_handler/            # ── Document Binary Management ──────────
│   ├── downloader.py           #    Chunked download with resume
│   ├── renditions.py           #    Format variant handling
│   ├── versioning.py           #    Version chain extraction
│   └── ocr_client.py           #    Azure AI Document Intelligence
│
├── report_converter/           # ── BIRT → Power BI Conversion ──────────
│   ├── expression_converter.py #    80+ BIRT JS → DAX mappings
│   ├── visual_mapper.py        #    BIRT visuals → PBI visual configs
│   └── pbip_generator.py       #    .pbip PBIR v4.0 project output
│
├── fabric_output/              # ── Step 2: Fabric Generation ───────────
│   ├── fabric_constants.py     #    Spark type maps, sanitization
│   ├── lakehouse_generator.py  #    Delta table DDL
│   ├── pipeline_generator.py   #    Data Factory pipeline JSON
│   ├── notebook_generator.py   #    PySpark notebook generation
│   ├── dataflow_generator.py   #    Dataflow Gen2 (Power Query M)
│   ├── tmdl_generator.py       #    TMDL semantic model
│   └── m_query_generator.py    #    Power Query M expressions
│
├── governance/                 # ── Permission & Compliance ─────────────
│   ├── acl_mapper.py           #    CS/DCTM ACL → RLS role mapping
│   ├── classification_mapper.py#    Categories → Purview sensitivity labels
│   ├── purview_mapper.py       #    Retention → Purview policies
│   ├── audit.py                #    Migration audit trail (JSON/CSV export)
│   └── security_validator.py   #    Path traversal, credential scrub, XXE
│
├── reporting/                  # ── HTML Migration Dashboard ────────────
│   ├── html_template.py        #    Fluent/PBI CSS + JS + 15 components
│   ├── migration_report.py     #    Per-item fidelity tracking & scoring
│   └── generate_report.py      #    8-section dashboard builder
│
├── assessment/                 # ── Pre-Migration Analysis ──────────────
│   ├── scanner.py              #    Content inventory
│   ├── complexity.py           #    Complexity scoring
│   ├── readiness_report.py     #    HTML readiness dashboard
│   ├── validator.py            #    Post-migration validation
│   └── strategy_advisor.py     #    Migration strategy recommendation
│
├── deploy/                     # ── Fabric Deployment ───────────────────
│   ├── auth.py                 #    Azure AD (Service Principal + MI)
│   ├── fabric_client.py        #    Fabric REST API client
│   ├── deployer.py             #    Workspace provisioning & deploy
│   └── onelake_client.py       #    ADLS Gen2 / OneLake upload
│
├── tests/                      # 405 tests across 22 test files
├── docs/                       # Architecture, agents, dev plan
│   ├── assets/                 #    Logo + architecture SVG
│   ├── ARCHITECTURE.md
│   ├── AGENTS.md
│   └── DEVELOPMENT_PLAN.md
└── .github/
    ├── agents/                 # 10 agent definitions
    └── workflows/              # CI/CD pipelines
```

---

## Development

```bash
# Clone
git clone https://github.com/cyphou/OpenTextToFabric.git
cd OpenTextToFabric

# No install needed — zero dependencies
# Just run tests directly:
python -m pytest tests/ -v

# Or with a venv:
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS/Linux
pip install -e ".[dev]"
pytest tests/ -v
```

### Requirements

- **Python 3.12+**
- **Zero external dependencies** for core migration
- Optional: `azure-ai-documentintelligence` (OCR), `azure-identity` (deployment)

---

## CLI Reference

```
usage: migrate [-h] --source-type {content-server,documentum,birt,all}
               [--server-url URL] [--username USER] [--password-env VAR]
               [--scope PATH] [--input PATH] [--output-dir DIR]
               [--output-format {fabric,pbip,both}] [--assess-only]
               [--batch] [--deploy] [--workspace-id ID] [--tenant-id ID]
               [--no-report] [-v]
```

| Flag | Description |
|:---|:---|
| `--source-type` | `content-server`, `documentum`, `birt`, or `all` |
| `--output-format` | `fabric` (Lakehouse), `pbip` (Power BI), or `both` (default) |
| `--assess-only` | Run pre-migration assessment without migrating |
| `--no-report` | Skip HTML migration report generation |
| `--deploy` | Deploy generated artifacts to a Fabric workspace |
| `-v` / `-vv` | INFO / DEBUG logging |

---

## 10-Agent Architecture

The project uses specialized [AI agents](docs/AGENTS.md) for each migration concern:

| Agent | Responsibility |
|:---|:---|
| **@orchestrator** | Pipeline coordination, CLI, batch processing |
| **@extractor** | OpenText API integration & JSON extraction |
| **@content** | Document binary handling (download, renditions, OCR) |
| **@report** | BIRT → Power BI report conversion |
| **@semantic** | TMDL semantic model generation |
| **@pipeline** | Fabric artifact generation (Lakehouse, Notebooks, Dataflows) |
| **@governance** | Permission & compliance mapping |
| **@assessor** | Pre-migration analysis & readiness scoring |
| **@deployer** | Fabric workspace deployment |
| **@tester** | Test creation & validation |

---

## Related Projects

| Project | Description |
|:---|:---|
| [**TableauToPowerBI**](https://github.com/cyphou/TableauToPowerBI) | Sister project — Tableau workbook migration to Power BI |

---

## License

[MIT](LICENSE) — free for commercial and personal use.
