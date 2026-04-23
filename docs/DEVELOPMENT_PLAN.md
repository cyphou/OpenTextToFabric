# Development Plan — OpenText to Power BI / Fabric Migration Tool

**Version:** v0.2.0  
**Date:** 2026-04-23  
**Current state:** Core pipeline operational — extraction, conversion, PBIR v4.0 output  
**Target:** Production-ready enterprise migration tool with deployment automation

---

## Project Vision

Migrate **OpenText Content Server, Documentum, and Analytics (BIRT/iHub)** artifacts into **Microsoft Fabric** (OneLake, Lakehouse, Data Factory, Notebooks, Power BI) with a multi-agent pipeline inspired by the [TableauToPowerBI](../../../TableauToPowerBI) project architecture.

### Source Systems Covered

| OpenText Product | What It Contains | Migration Target |
|-----------------|------------------|-----------------|
| **Content Server** (formerly Livelink) | Documents, folders, metadata, workflows, permissions, categories | OneLake Lakehouse + Purview governance |
| **Documentum** | Documents, ACLs, lifecycles, retention policies, renditions | OneLake Lakehouse + Purview governance |
| **Analytics / iHub** (Actuate BIRT) | Reports (.rptdesign), dashboards, data sources, schedules | Power BI (.pbip PBIR + TMDL) |
| **AppWorks** | Low-code apps, forms, workflows, business rules | Power Automate + Power Apps (metadata only) |
| **Magellan** | AI models, analytics pipelines, data connections | Fabric Data Science + Notebooks |
| **Extended ECM** | SAP/Salesforce integrations, business workspace metadata | Fabric Pipelines + Dataflows |

### Target Platform

| Fabric Component | Purpose |
|-----------------|---------|
| **OneLake / Lakehouse** | Centralized document + metadata storage (Delta tables) |
| **Data Factory** | Ingestion pipelines (OpenText APIs → OneLake) |
| **Notebooks (PySpark)** | ETL transformations, document processing, OCR extraction |
| **Power BI (.pbip)** | Reports migrated from BIRT/iHub, new dashboards over migrated data |
| **Purview** | Governance, sensitivity labels, lineage (maps from OT classifications) |
| **Power Automate** | Workflow migration from OT workflows/AppWorks |

---

## 10-Agent Architecture

Adapted from the TableauToPowerBI 12-agent model, streamlined for ECM→Fabric migration.

| Agent | Scope |
|-------|-------|
| **@orchestrator** | Pipeline coordination, CLI, batch processing |
| **@extractor** | OpenText API integration, content extraction, metadata parsing |
| **@content** | Document migration, renditions, OCR, binary handling |
| **@report** | BIRT .rptdesign → Power BI visual mapping |
| **@semantic** | Semantic model (TMDL), relationships, hierarchies |
| **@pipeline** | Fabric Data Factory pipelines, Dataflows, Notebooks |
| **@governance** | Permissions mapping (OT ACLs → Fabric RLS/Purview), classifications |
| **@assessor** | Readiness scoring, gap analysis, migration strategy |
| **@deployer** | Fabric workspace deployment, capacity management |
| **@tester** | Tests, coverage, regression validation |

See [AGENTS.md](AGENTS.md) for full architecture, data flow, and handoff protocol.

---

## Phase 0 — Foundation (Sprints 1–4) ✅ DONE

### Sprint 1 — Project Scaffolding & OpenText API Client

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Project structure | @orchestrator | ✅ | Python 3.12+, zero external deps for core, pyproject.toml |
| OpenText REST API client | @extractor | ✅ | Content Server REST v2 API (auth, session, pagination) |
| CLI entry point (`migrate.py`) | @orchestrator | ✅ | `--source-type {content-server,documentum,birt}`, `--server-url`, `--auth` |
| Configuration model | @orchestrator | ✅ | YAML/JSON config for server connection, scope, filters |
| Unit test scaffolding | @tester | ✅ | pytest setup, fixtures, mock API responses |

### Sprint 2 — Content Server Metadata Extraction

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Node tree walker | @extractor | ✅ | Recursive folder/document traversal via CS REST API |
| Metadata extraction | @extractor | ✅ | Categories, attributes, custom metadata → JSON |
| Permission extraction | @governance | ✅ | ACLs, groups, user mappings → JSON |
| Workflow extraction | @extractor | ✅ | Workflow definitions, step maps, assignees |
| Intermediate JSON schema | @extractor | ✅ | Define 12+ JSON interchange files (nodes, metadata, permissions, workflows, etc.) |

### Sprint 3 — Document Binary Extraction & Staging

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Binary download pipeline | @content | ✅ | Chunked download, resume, checksum verification |
| Rendition handling | @content | ✅ | Extract all renditions (PDF, thumbnail, web viewable) |
| Version history | @content | ✅ | Download version chain, map to OneLake versioning strategy |
| OCR pipeline (optional) | @content | ✅ | Azure AI Document Intelligence integration for scanned docs |
| Local staging area | @orchestrator | ✅ | Temp directory management, cleanup, progress tracking |

### Sprint 4 — Foundation Tests & CI

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| API client tests (mocked) | @tester | ✅ | 50+ tests for REST client, pagination, error handling |
| Extraction tests | @tester | ✅ | Metadata, permissions, workflow extraction with fixtures |
| CI pipeline (.github/workflows) | @tester | ✅ | Lint → Test (3 OS × 2 Python) → Validate |
| Security baseline | @governance | ✅ | Credential handling, no secrets in logs, path validation |

### Phase 0 Success Criteria

| Metric | Target |
|--------|--------|
| Tests | 200+ |
| API coverage | Content Server REST v2 (nodes, categories, permissions, workflows) |
| Extraction | Full metadata + binary pipeline for Content Server |

---

## Phase 1 — Fabric Target Generation (Sprints 5–8) ✅ DONE

### Sprint 5 — Lakehouse Schema Generation

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Delta table schema generator | @pipeline | ✅ | OpenText metadata → Delta table DDL (documents, categories, permissions) |
| Folder hierarchy → Lakehouse paths | @pipeline | ✅ | OT folder tree → OneLake directory structure |
| Metadata table generator | @pipeline | ✅ | Flattened metadata views, custom attribute columns |
| Category → Tag mapping | @governance | ✅ | OT classifications → Purview sensitivity labels |

### Sprint 6 — Data Factory Pipeline Generation

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Ingestion pipeline templates | @pipeline | ✅ | REST connector → OneLake copy activities |
| Incremental sync logic | @pipeline | ✅ | Modified-date watermark, change detection |
| Notebook generator (PySpark) | @pipeline | ✅ | ETL notebooks for document processing, metadata enrichment |
| Pipeline orchestration | @pipeline | ✅ | Master pipeline with staged execution (metadata → binaries → relationships) |

### Sprint 7 — Permission & Governance Mapping

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| ACL → RLS mapping | @governance | ✅ | OpenText permissions → Fabric Row-Level Security roles |
| Group → Entra ID mapping | @governance | ✅ | OT groups/users → Azure AD security groups (config-driven) |
| Retention → Purview policies | @governance | ✅ | OT retention policies → Purview retention labels |
| Audit trail generation | @governance | ✅ | Migration audit log (what moved, permissions delta, data lineage) |

### Sprint 8 — Phase 1 Integration & Tests

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| End-to-end: CS → Lakehouse | @orchestrator | ✅ | Full pipeline test with mock Content Server |
| Lakehouse validation | @assessor | ✅ | Schema correctness, row counts, metadata completeness |
| Permission validation | @governance | ✅ | ACL mapping correctness tests |
| Tests target | @tester | ✅ | 500+ tests |

### Phase 1 Success Criteria

| Metric | Target |
|--------|--------|
| Tests | 500+ |
| Fabric artifacts | Lakehouse DDL + Data Factory pipelines + PySpark notebooks |
| Governance | ACL → RLS mapping, classification → Purview labels |

---

## Phase 2 — BIRT Report Migration (Sprints 9–14) ✅ DONE

### Sprint 9 — BIRT Report Parser

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| .rptdesign XML parser | @extractor | ✅ | Parse BIRT report XML schema (data sources, datasets, layout, expressions) |
| Data source extraction | @extractor | ✅ | JDBC connections, ODA data sources → connection metadata |
| Dataset extraction | @extractor | ✅ | SQL queries, parameters, computed columns → JSON |
| Report layout extraction | @extractor | ✅ | Tables, charts, crosstabs, lists, grids, labels, images |

### Sprint 10 — BIRT Expression → DAX Conversion

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| BIRT JavaScript expression parser | @report | ✅ | Parse BIRT expressions (JavaScript-based) |
| Expression → DAX converter | @report | ✅ | 80+ BIRT function → DAX mappings |
| Aggregation mapping | @report | ✅ | BIRT aggregations (SUM, COUNT, RUNNING_SUM, RANK) → DAX measures |
| Computed column → calc column | @report | ✅ | BIRT computed columns → DAX calculated columns |
| Parameter mapping | @report | ✅ | BIRT report parameters → Power BI slicers/filters |

### Sprint 11 — BIRT Visual → Power BI Visual Mapping

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Table → PBI Table/Matrix | @report | ✅ | BIRT table elements → Power BI table/matrix visuals |
| Chart → PBI chart | @report | ✅ | BIRT chart types (bar, line, pie, scatter, area) → PBI visuals |
| Crosstab → PBI Matrix | @report | ✅ | BIRT cross-tabulation → Power BI matrix |
| Layout → PBI page | @report | ✅ | BIRT master pages, grids → PBI report pages, layout |
| Styling → PBI theme | @report | ✅ | BIRT CSS/styles → Power BI theme JSON |

### Sprint 12 — TMDL Semantic Model Generation

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Dataset → TMDL table | @semantic | ✅ | BIRT datasets → TMDL tables with columns + data types |
| Relationship inference | @semantic | ✅ | Foreign key detection from SQL joins → TMDL relationships |
| Measure generation | @semantic | ✅ | BIRT aggregations → TMDL measures with DAX |
| Hierarchy generation | @semantic | ✅ | BIRT group hierarchies → TMDL display folders + hierarchies |
| M query generation | @semantic | ✅ | JDBC connections → Power Query M (SQL.Database, ODBC, etc.) |

### Sprint 13 — PBIP Report Generation

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| .pbip project structure | @report | ✅ | PBIR v4.0 report + TMDL semantic model |
| Visual container generation | @report | ✅ | Page layout, visual positioning, sizing |
| Filter generation | @report | ✅ | BIRT filters → PBI report/page/visual filters |
| Drill-through mapping | @report | ✅ | BIRT hyperlinks/drill-through → PBI drill-through pages |
| Conditional formatting | @report | ✅ | BIRT highlight rules → PBI conditional formatting |

### Sprint 14 — BIRT Migration Tests

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Parser tests | @tester | ✅ | .rptdesign parsing with sample reports |
| Expression conversion tests | @tester | ✅ | BIRT JS → DAX correctness |
| Visual mapping tests | @tester | ✅ | Layout fidelity validation |
| End-to-end BIRT → .pbip | @tester | ✅ | Full pipeline with reference reports |
| Tests target | @tester | ✅ | 1,000+ total |

### Phase 2 Success Criteria

| Metric | Target |
|--------|--------|
| Tests | 1,000+ |
| BIRT expressions | 80+ function conversions |
| Visual types | 20+ BIRT visual → PBI visual mappings |
| Output | .pbip (PBIR v4.0 + TMDL) opening in Power BI Desktop |

---

## Phase 3 — Documentum Migration (Sprints 15–18) ✅ DONE

### Sprint 15 — Documentum API Client

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Documentum REST API client | @extractor | ✅ | DFC/REST API authentication, session management |
| Cabinet/folder traversal | @extractor | ✅ | Recursive document tree walking |
| D2 metadata extraction | @extractor | ✅ | Object types, attributes, aspect metadata |
| Lifecycle & retention | @governance | ✅ | Documentum lifecycle states → Purview retention labels |

### Sprint 16 — Documentum Content Migration

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Content transfer | @content | ✅ | Binary documents, virtual documents, compound docs |
| Rendition migration | @content | ✅ | All format renditions → OneLake storage |
| Relationship mapping | @content | ✅ | Documentum relations → Lakehouse relationship tables |
| Audit trail | @governance | ✅ | Documentum audit events → migration log |

### Sprint 17 — Documentum → Fabric Pipeline

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Schema mapping | @pipeline | ✅ | Documentum object types → Delta tables |
| ACL translation | @governance | ✅ | Documentum ACLs (permit levels) → Fabric RLS |
| Workflow migration | @pipeline | ✅ | Documentum workflows → Power Automate flows (metadata) |
| Integration tests | @tester | ✅ | 200+ Documentum-specific tests |

### Sprint 18 — Documentum Integration

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| End-to-end Documentum test | @orchestrator | ✅ | Full pipeline with mock Documentum server |
| Cross-platform merge | @orchestrator | ✅ | CS + Documentum → unified Lakehouse |
| Tests target | @tester | ✅ | 1,500+ total |

---

## Phase 4 — Assessment & Deployment Foundation (Sprints 19–24) 🔲 NEXT

> **Goal:** Populate the empty `assessment/` and `deploy/` packages with real implementations, add batch processing, and bring test count from 405 → 600+.

### Sprint 19 — Pre-Migration Assessment Engine

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| `assessment/scanner.py` | @assessor | 🔲 | Content inventory scanner — volumes, types, sizes, MIME breakdown |
| `assessment/complexity.py` | @assessor | 🔲 | Complexity scoring per content area (ACL depth, expression difficulty, relationship density) |
| `assessment/readiness_report.py` | @assessor | 🔲 | HTML readiness dashboard with pass/warn/fail categories (reuse `html_template.py`) |
| `assessment/validator.py` | @assessor | 🔲 | Post-migration validation — compare source inventory vs generated artifacts |
| `assessment/strategy_advisor.py` | @assessor | 🔲 | Migration strategy recommendation (big bang vs wave, import vs DirectLake) |
| `--assess-only` CLI integration | @orchestrator | 🔲 | Wire scanner + readiness report into existing CLI flag |

### Sprint 20 — Fabric Deployment Client

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| `deploy/auth.py` | @deployer | 🔲 | Azure AD auth — Service Principal + Managed Identity (azure-identity optional dep) |
| `deploy/fabric_client.py` | @deployer | 🔲 | Fabric REST API client — workspace list/create, item CRUD, import |
| `deploy/onelake_client.py` | @deployer | 🔲 | ADLS Gen2 / OneLake file upload (PUT blob, mkdir, streaming upload) |
| `deploy/deployer.py` | @deployer | 🔲 | Orchestrator — workspace provisioning → Lakehouse deploy → report publish |
| Key Vault credential provider | @governance | 🔲 | Optional Azure Key Vault integration for OT server credentials |

### Sprint 21 — Batch Processing & Resume

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| `--batch` directory mode | @orchestrator | 🔲 | Process all `.rptdesign` files in a directory with shared semantic model |
| Checkpoint-based resume | @orchestrator | 🔲 | Extend `progress.py` with file-level checkpoints; `--resume` flag |
| Parallel extraction | @orchestrator | 🔲 | `concurrent.futures.ThreadPoolExecutor` for multi-file BIRT parsing |
| Batch progress dashboard | @orchestrator | 🔲 | Real-time HTML with per-file status rows (green/yellow/red) |
| Error isolation | @orchestrator | 🔲 | One failed report doesn't halt the batch; collect errors for summary |

### Sprint 22 — BIRT Expression Converter v2

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| LOD expression support | @report | 🔲 | BIRT cross-tab aggregations → CALCULATE + FILTER patterns |
| Window function mapping | @report | 🔲 | BIRT running totals / rank → DAX RANKX, SUMX, EARLIER |
| Date/time function expansion | @report | 🔲 | BIRT DateTimeSpan, DateDiff, FormatDate → DAX date intelligence |
| Parameter → slicer wiring | @report | 🔲 | BIRT cascading parameters → PBI slicer sync groups |
| Target: 65 → 120 functions | @report | 🔲 | Double function coverage, especially aggregation + date patterns |
| Conversion accuracy tests | @tester | 🔲 | 50+ new tests with real-world BIRT expressions from customer reports |

### Sprint 23 — Security Hardening

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Credential scrubbing audit | @governance | 🔲 | Verify no passwords/tokens leak to JSON intermediates, logs, or output |
| XXE defense in BIRT parser | @governance | 🔲 | Disable DTD/external entity resolution in `ET.parse()` via `defusedxml` or manual `XMLParser` |
| Path traversal defense tests | @governance | 🔲 | Expand `security_validator.py` tests for edge cases (symlinks, UNC paths, `..` sequences) |
| PII detection pass | @governance | 🔲 | Regex-based PII scanner over extracted metadata (SSN, email, credit card patterns) |
| OWASP dependency check | @governance | 🔲 | Verify zero-dep core; document optional dep security posture |

### Sprint 24 — Phase 4 Integration & Release

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Assessment → Deploy E2E test | @tester | 🔲 | Full pipeline: scan → assess → migrate → validate → deploy (mock APIs) |
| Tests: 405 → 600+ | @tester | 🔲 | Cover assessment, deploy, batch, security modules |
| Performance baseline | @orchestrator | 🔲 | Benchmark: 100 BIRT reports in < 5 minutes on standard hardware |
| `v0.3.0` release tag | @orchestrator | 🔲 | Changelog, version bump, GitHub release |
| README update | @orchestrator | 🔲 | Update badge counts, add assessment + deploy sections |

### Phase 4 Success Criteria

| Metric | Target |
|--------|--------|
| Tests | 600+ |
| Assessment modules | 5 real implementations (not stubs) |
| Deploy modules | 4 real implementations |
| BIRT functions | 120+ conversions (currently 65) |
| Batch mode | Process directory of reports with resume |
| Security | XXE defense, PII scan, credential audit |

---

## Phase 5 — Advanced Report Fidelity (Sprints 25–30) 🔲 PLANNED

> **Goal:** Close the gap between BIRT report capabilities and Power BI output — conditional formatting, drill-through, sub-reports, and multi-data-source reports.

### Sprint 25 — Conditional Formatting & Styles

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| BIRT highlight rules → PBI rules | @report | 🔲 | Conditional color/icon/data bar rules from BIRT XML |
| BIRT CSS styles → PBI theme JSON | @report | 🔲 | Font, color, border, alignment mapping |
| Custom color palettes | @report | 🔲 | Extract BIRT chart palettes → PBI theme color arrays |
| Theme file generation | @report | 🔲 | Generate `CY24SU06.json` theme with extracted styles |

### Sprint 26 — Drill-Through & Sub-Reports

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| BIRT hyperlink actions → PBI drill-through | @report | 🔲 | Map BIRT drill-through to PBI drill-through pages |
| BIRT sub-reports → PBI drill-through | @report | 🔲 | Nested report references → separate PBI pages |
| Cross-report links | @report | 🔲 | BIRT report-to-report links → PBI bookmark/URL actions |
| Page navigation visual | @report | 🔲 | Auto-generate page navigator for multi-page migrations |

### Sprint 27 — Multi-Data-Source Reports

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Multiple JDBC sources | @semantic | 🔲 | BIRT reports with 3+ data sources → composite model |
| Cross-dataset relationships | @semantic | 🔲 | Auto-detect relationships across datasets via column name/type matching |
| Power Query M per source | @semantic | 🔲 | Generate separate M query per data source with proper folding |
| DirectLake mode detection | @semantic | 🔲 | When all sources are Delta tables, generate DirectLake model instead of Import |

### Sprint 28 — Visual Fidelity Improvements

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Expand visual map: 22 → 35 types | @report | 🔲 | Add: KPI, map, shape map, decomposition tree, key influencers, R/Python visual |
| BIRT group headers → PBI matrix subtotals | @report | 🔲 | Table group bands → matrix row/column subtotals |
| Chart axis configuration | @report | 🔲 | Axis titles, min/max, label rotation, gridlines |
| Legend positioning | @report | 🔲 | BIRT legend placement → PBI legend config |
| Tooltip customization | @report | 🔲 | BIRT tooltip expressions → PBI tooltip pages |

### Sprint 29 — BIRT iHub / Server Integration

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| iHub REST API client | @extractor | 🔲 | Connect to BIRT iHub for bulk report listing + download |
| Schedule extraction | @extractor | 🔲 | iHub scheduled report configs → PBI refresh schedules |
| Report catalog scanner | @assessor | 🔲 | Scan entire iHub server, build migration inventory |
| Server-to-server migration | @orchestrator | 🔲 | iHub → Fabric workspace direct deployment |

### Sprint 30 — Fidelity Validation & Regression

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Visual diff tool | @tester | 🔲 | Side-by-side BIRT screenshot vs PBI screenshot comparison (SSIM) |
| Measure equivalence testing | @tester | 🔲 | Run BIRT expressions + DAX against same data, compare values |
| Regression snapshot suite | @tester | 🔲 | Golden-file output for sample reports; drift detection in CI |
| Tests: 600 → 900+ | @tester | 🔲 | Cover conditional formatting, drill-through, multi-source, fidelity |

### Phase 5 Success Criteria

| Metric | Target |
|--------|--------|
| Tests | 900+ |
| Visual types | 35+ BIRT → PBI mappings (currently 22) |
| BIRT functions | 150+ conversions |
| Report features | Conditional formatting, drill-through, sub-reports |
| iHub integration | Bulk server migration |

---

## Phase 6 — Enterprise Hardening & v1.0 (Sprints 31–36) 🔲 PLANNED

> **Goal:** Production-grade release with multi-tenant deployment, incremental sync, telemetry, and enterprise documentation.

### Sprint 31 — Incremental Sync Engine

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Change detection (file-hash + mtime) | @extractor | 🔲 | Detect modified/new/deleted content since last migration |
| Delta ingestion to Lakehouse | @pipeline | 🔲 | Merge (upsert) into Delta tables, tombstone deletes |
| Conflict resolution strategy | @orchestrator | 🔲 | Config-driven: last-writer-wins, source-wins, manual-review |
| Sync status dashboard | @orchestrator | 🔲 | HTML dashboard showing drift, pending changes, last sync |

### Sprint 32 — Multi-Tenant Deployment

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Template-based workspace creation | @deployer | 🔲 | Create per-tenant workspaces from migration output |
| RLS parameterization | @governance | 🔲 | Tenant-specific RLS roles from config |
| Config-driven deployment | @deployer | 🔲 | YAML deployment manifest (workspace, capacity, permissions) |
| Blue/green deployment | @deployer | 🔲 | Deploy to staging workspace → swap → rollback on failure |

### Sprint 33 — Telemetry & Observability

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Structured event logging | @orchestrator | 🔲 | JSON log events with correlation IDs |
| Azure Monitor integration | @orchestrator | 🔲 | Optional App Insights export for production monitoring |
| Prometheus metrics endpoint | @orchestrator | 🔲 | `/metrics` for container-based deployments |
| Telemetry dashboard (HTML) | @orchestrator | 🔲 | 4-tab interactive dashboard (timeline, errors, throughput, latency) |

### Sprint 34 — Performance Optimization

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Connection pooling | @extractor | 🔲 | HTTP session reuse for OT REST APIs |
| Async I/O for file operations | @content | 🔲 | Parallel file download + upload |
| Lazy XML parsing | @extractor | 🔲 | `iterparse` for large .rptdesign files (>50MB) |
| Memory profiling | @tester | 🔲 | Ensure <500MB RSS for 1000-report batch |
| Stress test: 10,000 docs | @tester | 🔲 | Validate throughput target: 1,000 docs/hour |

### Sprint 35 — Enterprise Documentation

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Enterprise migration guide (8-phase) | @orchestrator | 🔲 | Assessment → planning → pilot → wave → validate → deploy → cutover → support |
| BIRT → DAX reference guide | @report | 🔲 | Searchable table of all 150+ function mappings |
| Power Query M reference | @semantic | 🔲 | All supported JDBC/ODBC → M query patterns |
| Troubleshooting guide | @orchestrator | 🔲 | Common issues, error codes, resolution steps |
| API documentation | @orchestrator | 🔲 | Auto-generated API docs (pdoc/Sphinx) published to GitHub Pages |

### Sprint 36 — v1.0.0 Release

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Full regression suite | @tester | 🔲 | 1,200+ tests, 95%+ coverage |
| Security audit | @governance | 🔲 | Full OWASP review, dependency scan, credential audit |
| Performance certification | @tester | 🔲 | Documented benchmarks on standard hardware |
| Semantic versioning | @orchestrator | 🔲 | v1.0.0 tag, CHANGELOG, GitHub release with binaries |
| PyPI package (optional) | @orchestrator | 🔲 | `pip install opentext-to-fabric` for optional deps |
| Community contribution guide | @orchestrator | 🔲 | CONTRIBUTING.md with PR template, code standards |

### Phase 6 Success Criteria

| Metric | Target |
|--------|--------|
| Tests | 1,200+ |
| Coverage | ≥ 95% |
| Batch throughput | 1,000 docs/hour on 4-core / 16GB |
| BIRT functions | 150+ conversions |
| Visual types | 35+ mappings |
| Documentation | 6 guides + API docs |
| Release | v1.0.0 on GitHub + optional PyPI |

---

## Current State (v0.2.0) — What's Built

| Component | Status | Details |
|-----------|--------|---------|
| **Source modules** | 37 | Extraction, conversion, governance, reporting |
| **Tests** | 405 | Across 22 test files |
| **BIRT parser** | ✅ Working | Namespace-aware XML extraction (columns, queries, computed columns) |
| **Expression converter** | 65 functions | BIRT JS → DAX (aggregation, math, string, date, conditional) |
| **Visual mapper** | 22 types | BIRT → PBI (table, chart, crosstab, text, card, image) |
| **PBIP generator** | ✅ PBIR v4.0 | Correct folder structure, .platform files, $schema, visual configs |
| **TMDL generator** | ✅ Working | Tables, columns, measures, relationships, .platform, .pbism |
| **Lakehouse generator** | ✅ Working | Delta table DDL from extracted metadata |
| **Pipeline generator** | ✅ Working | Data Factory pipeline JSON (3-stage orchestration) |
| **Notebook generator** | ✅ Working | PySpark ETL notebooks |
| **Governance** | ✅ Working | ACL → RLS, classification → Purview, audit trail |
| **HTML dashboard** | ✅ Working | 8-section migration report with dark mode |
| **Assessment** | ❌ Stub | `assessment/` package exists but only has `__init__.py` |
| **Deployment** | ❌ Stub | `deploy/` package exists but only has `__init__.py` |
| **Batch mode** | ❌ Missing | CLI only supports single file/scope |
| **Security** | ⚠️ Basic | Path validation exists; XXE defense + PII scan missing |

---

## Roadmap Summary

| Phase | Sprints | Focus | Key Deliverables | Status |
|-------|---------|-------|-----------------|--------|
| **Phase 0** | 1–4 | Foundation | OT API client, metadata extraction, CI | ✅ Done |
| **Phase 1** | 5–8 | Fabric Generation | Lakehouse, Data Factory, PySpark, governance | ✅ Done |
| **Phase 2** | 9–14 | BIRT → Power BI | Report parser, DAX conversion, .pbip output | ✅ Done |
| **Phase 3** | 15–18 | Documentum | Documentum API, content migration, ACL mapping | ✅ Done |
| **Phase 4** | 19–24 | Assessment & Deploy | Assessment engine, deploy client, batch, security | 🔲 Next |
| **Phase 5** | 25–30 | Report Fidelity | Conditional formatting, drill-through, iHub, 35 visuals | 🔲 Planned |
| **Phase 6** | 31–36 | Enterprise v1.0 | Incremental sync, multi-tenant, telemetry, 1200 tests | 🔲 Planned |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| Core dependencies | Zero external deps (stdlib only) |
| Optional: OCR | Azure AI Document Intelligence |
| Optional: Hyper reader | tableauhyperapi (BIRT Hyper-like data) |
| Test framework | pytest |
| CI | GitHub Actions (3 OS × 2 Python versions) |
| Output format | .pbip (PBIR v4.0 + TMDL), Fabric artifacts (Lakehouse, Pipeline, Notebook) |

---

## Key Design Decisions

1. **2-Step Pipeline** (same as TableauToPowerBI): Extraction → Intermediate JSON → Generation
2. **Source-agnostic intermediate format**: JSON interchange files work for Content Server, Documentum, and BIRT
3. **Fabric-first output**: Unlike Tableau→PBI which generates .pbip first, this project targets Fabric native artifacts (Lakehouse, Pipelines) as primary output, with Power BI reports for BIRT migration
4. **Multi-agent ownership**: Each agent owns specific files and domains; handoff protocol between agents
5. **Zero external deps for core**: Optional integrations (OCR, Key Vault) are pluggable
