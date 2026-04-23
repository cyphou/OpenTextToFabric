# Multi-Agent Architecture — OpenText to Fabric Migration

This project uses a **10-agent specialization model** adapted from the [TableauToPowerBI](../../../TableauToPowerBI) 12-agent architecture. Each agent has scoped domain knowledge, file ownership, and clear boundaries.

## Quick Reference

| Agent | Invoke When | Owns |
|-------|-------------|------|
| **@orchestrator** | Pipeline coordination, CLI, batch, resume/retry | `migrate.py`, `config.py`, `progress.py`, `batch_runner.py` |
| **@extractor** | OpenText API integration, metadata parsing | `opentext_extract/*.py` (api_client, content_server, documentum, birt_parser) |
| **@content** | Document binaries, renditions, OCR, version history | `content_handler/*.py` (downloader, renditions, versioning, ocr_client) |
| **@report** | BIRT .rptdesign → Power BI visual/expression mapping | `report_converter/*.py` (birt_parser, expression_converter, visual_mapper) |
| **@semantic** | TMDL semantic model, relationships, hierarchies | `fabric_output/tmdl_generator.py`, `fabric_output/m_query_generator.py` |
| **@pipeline** | Fabric pipelines, Dataflows, PySpark Notebooks, Lakehouse DDL | `fabric_output/lakehouse_generator.py`, `fabric_output/pipeline_generator.py`, `fabric_output/notebook_generator.py`, `fabric_output/dataflow_generator.py` |
| **@governance** | Permissions (ACL→RLS), classifications, Purview, audit trail | `governance/*.py` (acl_mapper, classification_mapper, purview_mapper, audit) |
| **@assessor** | Readiness scoring, gap analysis, strategy, validation | `assessment/*.py` (scanner, complexity, readiness_report, validator) |
| **@deployer** | Fabric deployment, workspace provisioning, OneLake upload | `deploy/*.py` (auth, fabric_client, deployer, onelake_client) |
| **@tester** | Tests, coverage, fixtures, regression | `tests/*.py` |

## Architecture Diagram

```
                        ┌──────────────┐
                        │ Orchestrator │  ← CLI entry, pipeline coordination
                        └──────┬───────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
        ┌─────▼─────┐   ┌─────▼─────┐   ┌──────▼──────┐
        │ Extractor  │   │  Content  │   │   Report    │
        │ (OT APIs)  │   │ (Binaries)│   │ (BIRT→PBI)  │
        └─────┬──────┘   └─────┬─────┘   └──────┬──────┘
              │                │                │
              ▼                ▼                ▼
        ┌─────────────────────────────────────────────┐
        │          Intermediate JSON (15+ files)       │
        │  nodes.json, metadata.json, permissions.json │
        │  workflows.json, documents.json, reports.json│
        │  datasets.json, expressions.json, ...        │
        └──────────────────────┬───────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
        ┌─────▼─────┐   ┌─────▼─────┐   ┌──────▼──────┐
        │ Semantic   │   │ Pipeline  │   │ Governance  │
        │ (TMDL)     │   │ (Fabric)  │   │ (ACL/Purview)│
        └────────────┘   └───────────┘   └─────────────┘
                               │
                  ┌────────────┼────────────┐
                  │            │            │
            ┌─────▼─────┐ ┌───▼───┐ ┌──────▼──────┐
            │  Assessor  │ │Deploy │ │   Tester    │
            │ (Analysis) │ │(Fabric)│ │(Cross-cut)  │
            └────────────┘ └───────┘ └─────────────┘
```

## Data Flow

```
1. Orchestrator receives CLI command (migrate.py)
   → --source-type {content-server, documentum, birt, all}
   → --server-url, --auth, --scope, --output-dir

2. Orchestrator delegates to Extractor:
   a. Content Server: REST v2 API → node tree, metadata, categories, workflows
   b. Documentum: REST/DFC API → cabinets, objects, lifecycles, ACLs
   c. BIRT/iHub: .rptdesign XML parsing → datasets, expressions, visuals

3. Orchestrator delegates to Content Handler:
   a. Binary download (chunked, resumable)
   b. Rendition extraction (PDF, thumbnails)
   c. Version history chain
   d. (Optional) OCR via Azure AI Document Intelligence

4. Extraction produces 15+ Intermediate JSON files:
   → nodes.json          (folder/document tree)
   → metadata.json       (custom attributes, categories)
   → permissions.json    (ACLs, groups, users)
   → workflows.json      (workflow definitions, steps)
   → documents.json      (binary manifest, checksums, sizes)
   → renditions.json     (format variants)
   → versions.json       (version chains)
   → classifications.json (taxonomies, categories)
   → retention.json      (retention policies, lifecycles)
   → reports.json        (BIRT report definitions)
   → datasets.json       (BIRT SQL queries, parameters)
   → expressions.json    (BIRT computed fields → DAX candidates)
   → visuals.json        (BIRT layout → PBI visual mapping)
   → connections.json    (data source connection strings)
   → relationships.json  (cross-object references)

5. Orchestrator delegates to generation:
   a. @pipeline → Lakehouse DDL, Data Factory pipelines, PySpark notebooks
   b. @semantic → TMDL semantic model (for BIRT reports)
   c. @report  → .pbip report (PBIR v4.0) from BIRT
   d. @governance → ACL→RLS, classifications→Purview, audit trail

6. (Optional) @assessor → readiness report, gap analysis, wave planning
7. (Optional) @deployer → Fabric workspace deployment, OneLake upload
8. @tester validates all steps
```

## Agent Domain Details

### @orchestrator — Pipeline Coordinator
- **Owns:** `migrate.py`, `config.py`, `progress.py`, `batch_runner.py`, `incremental.py`
- **Responsibility:** CLI parsing, pipeline sequencing, batch mode, resume/retry, progress tracking
- **Delegates to:** All other agents based on `--source-type` flag

### @extractor — OpenText API Integration
- **Owns:** `opentext_extract/api_client.py`, `opentext_extract/content_server.py`, `opentext_extract/documentum_client.py`, `opentext_extract/birt_parser.py`
- **Responsibility:** REST API authentication, session management, pagination, rate limiting, metadata extraction
- **APIs:**
  - Content Server REST v2 (`/api/v2/nodes`, `/api/v2/members`, `/api/v2/workflows`)
  - Documentum REST Services (`/repositories/{repo}/objects`, `/dql`)
  - BIRT .rptdesign XML schema parsing
- **Output:** Intermediate JSON files (nodes, metadata, permissions, workflows)

### @content — Document Binary Handler
- **Owns:** `content_handler/downloader.py`, `content_handler/renditions.py`, `content_handler/versioning.py`, `content_handler/ocr_client.py`
- **Responsibility:** Binary document download, rendition management, version chain extraction, OCR integration
- **Key concerns:** Chunked transfer, resume on failure, checksum validation, temp storage management

### @report — BIRT Report Converter
- **Owns:** `report_converter/birt_parser.py`, `report_converter/expression_converter.py`, `report_converter/visual_mapper.py`, `report_converter/pbip_generator.py`
- **Responsibility:** .rptdesign XML → Power BI report conversion
- **Mappings:**
  - BIRT JavaScript expressions → DAX formulas
  - BIRT data source (JDBC) → Power Query M
  - BIRT tables/charts/crosstabs → PBI table/matrix/chart visuals
  - BIRT parameters → PBI slicers/filters
  - BIRT styles → PBI theme JSON

### @semantic — Semantic Model Specialist
- **Owns:** `fabric_output/tmdl_generator.py`, `fabric_output/m_query_generator.py`
- **Responsibility:** Generate TMDL semantic model from BIRT datasets or migrated Lakehouse tables
- **Output:** TMDL files (tables, columns, measures, relationships, hierarchies, RLS roles)

### @pipeline — Fabric Artifact Generator
- **Owns:** `fabric_output/lakehouse_generator.py`, `fabric_output/pipeline_generator.py`, `fabric_output/notebook_generator.py`, `fabric_output/dataflow_generator.py`, `fabric_output/fabric_constants.py`
- **Responsibility:** Generate Fabric-native artifacts
- **Output:**
  - Lakehouse DDL (Delta table schemas)
  - Data Factory pipeline JSON (copy activities, REST connector → OneLake)
  - PySpark notebooks (ETL, document processing, metadata enrichment)
  - Dataflow Gen2 (Power Query M for incremental ingestion)

### @governance — Permission & Compliance Mapper
- **Owns:** `governance/acl_mapper.py`, `governance/classification_mapper.py`, `governance/purview_mapper.py`, `governance/audit.py`, `governance/security_validator.py`
- **Responsibility:** Map OpenText security model to Fabric/Purview
- **Mappings:**
  - OT ACLs (See/SeeContents/Modify/EditAttrs/Reserve/Delete/Admin) → Fabric RLS + workspace roles
  - OT groups/users → Azure Entra ID security groups (config-driven mapping table)
  - OT classifications/categories → Purview sensitivity labels
  - OT retention policies → Purview retention labels
  - Migration audit trail with evidence chain

### @assessor — Migration Analysis
- **Owns:** `assessment/scanner.py`, `assessment/complexity.py`, `assessment/readiness_report.py`, `assessment/validator.py`, `assessment/strategy_advisor.py`
- **Responsibility:** Pre-migration analysis, readiness scoring, gap identification
- **Output:**
  - Content inventory (volume, types, sizes)
  - Complexity scoring (per-report, per-content-area)
  - Readiness report (HTML dashboard with pass/warn/fail)
  - Wave planning (automatic migration wave assignment)
  - Post-migration validation (completeness, accuracy)

### @deployer — Fabric Deployment
- **Owns:** `deploy/auth.py`, `deploy/fabric_client.py`, `deploy/deployer.py`, `deploy/onelake_client.py`
- **Responsibility:** Deploy generated artifacts to Fabric
- **Capabilities:**
  - Azure AD auth (Service Principal + Managed Identity)
  - Fabric REST API (workspace creation, item deployment)
  - OneLake file upload (ADLS Gen2 API)
  - Power BI REST API (.pbip import)
  - Capacity management (auto-scale awareness)

### @tester — Test Suite
- **Owns:** `tests/*.py`
- **Responsibility:** Unit tests, integration tests, E2E tests, regression
- **Cross-cutting:** Reads all source files, writes only to `tests/`
- **Target:** 2,000+ tests, ≥90% coverage

## Handoff Protocol

Same as TableauToPowerBI:

1. **Complete your part** — finish everything within your file scope
2. **State the handoff** — clearly describe what needs to happen next
3. **Name the target agent** — e.g., "Hand off to @semantic for TMDL updates"
4. **List artifacts** — specify files, functions, and data structures involved
5. **Include context** — provide any intermediate results the next agent needs

## File Ownership Rules

- **One owner per file** — each source file has exactly one owning agent
- **Read access is universal** — any agent can read any file for context
- **Write access is restricted** — only the owning agent modifies a file
- **@tester is special** — reads all source files, writes only to `tests/`
- **Cross-cutting:** `governance/security_validator.py` is used by @extractor, @orchestrator, and @deployer

## Comparison with TableauToPowerBI Agents

| TableauToPowerBI Agent | OpenTextToFabric Equivalent | Notes |
|----------------------|---------------------------|-------|
| @orchestrator | @orchestrator | Same role — CLI, pipeline, batch |
| @extractor | @extractor | OT REST APIs instead of Tableau XML |
| @dax | @report (partial) | BIRT expression → DAX conversion |
| @wiring | @report (partial) | BIRT data source → M query |
| @converter | _(merged into @report)_ | Simpler formula landscape than Tableau |
| @semantic | @semantic | Same — TMDL generation |
| @visual | @report (partial) | BIRT visuals → PBI visuals |
| @generator | @pipeline | Fabric-native artifacts (Lakehouse, Pipeline, Notebook) |
| @assessor | @assessor | Same — readiness, validation |
| @merger | _(not needed initially)_ | No multi-workbook merge concept in ECM |
| @deployer | @deployer | Same — Fabric/PBI deployment |
| @tester | @tester | Same — tests, coverage |
| _(new)_ | **@content** | Document binary handling — unique to ECM migration |
| _(new)_ | **@governance** | ACL/classification mapping — much deeper than Tableau RLS |

## Agent Files

All agent definitions will be in `.github/agents/`:
- `shared.instructions.md` — Base rules inherited by all agents
- `orchestrator.agent.md` — Pipeline coordination
- `extractor.agent.md` — OpenText API integration
- `content.agent.md` — Document binary handling
- `report.agent.md` — BIRT → Power BI conversion
- `semantic.agent.md` — TMDL semantic model
- `pipeline.agent.md` — Fabric artifact generation
- `governance.agent.md` — Permission & compliance mapping
- `assessor.agent.md` — Migration analysis
- `deployer.agent.md` — Fabric deployment
- `tester.agent.md` — Test creation and validation
