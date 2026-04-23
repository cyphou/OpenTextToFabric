# Development Plan — OpenText to Power BI / Fabric Migration Tool

**Version:** v0.1.0  
**Date:** 2026-04-23  
**Current state:** Project inception — architecture & planning phase  
**Target:** Fully automated migration of OpenText ECM artifacts to Microsoft Fabric & Power BI

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

## Phase 4 — Assessment & Enterprise Features (Sprints 19–24) 🔲 PLANNED

### Sprint 19 — Pre-Migration Assessment

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Content inventory scanner | @assessor | 🔲 | Volume, types, sizes, complexity scoring |
| Permission complexity analysis | @assessor | 🔲 | ACL depth, group nesting, cross-references |
| Report complexity scoring | @assessor | 🔲 | BIRT report difficulty (expressions, data sources, visuals) |
| Migration readiness report (HTML) | @assessor | 🔲 | Dashboard with pass/warn/fail categories |

### Sprint 20 — Batch & Portfolio Migration

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Batch processing | @orchestrator | 🔲 | `--batch` mode for multiple content areas |
| Wave planning | @assessor | 🔲 | Automatic migration wave assignment (complexity-based) |
| Progress dashboard | @orchestrator | 🔲 | Real-time HTML progress with per-item status |
| Resume/retry logic | @orchestrator | 🔲 | Checkpoint-based resume after failures |

### Sprint 21 — Deployment Automation

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Fabric workspace provisioning | @deployer | 🔲 | Auto-create workspaces, assign capacity |
| Lakehouse deployment | @deployer | 🔲 | Deploy Delta tables + upload documents to OneLake |
| Pipeline deployment | @deployer | 🔲 | Deploy Data Factory pipelines to Fabric workspace |
| Power BI deployment | @deployer | 🔲 | Deploy .pbip to Fabric PBI workspace |

### Sprint 22 — Incremental Sync

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Change detection | @extractor | 🔲 | Modification date watermarks, event-based sync |
| Delta ingestion | @pipeline | 🔲 | Incremental updates to Lakehouse (inserts, updates, deletes) |
| Conflict resolution | @orchestrator | 🔲 | Last-writer-wins vs manual review |
| Sync dashboard | @orchestrator | 🔲 | HTML dashboard showing sync status, drift |

### Sprint 23 — Security Hardening

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Credential vault integration | @governance | 🔲 | Azure Key Vault for OT credentials |
| Path traversal defense | @governance | 🔲 | ZIP slip, path injection prevention |
| Sensitive content detection | @governance | 🔲 | PII/PHI scanning during migration |
| Audit compliance report | @governance | 🔲 | Full audit trail with evidence chain |

### Sprint 24 — Enterprise Release

| Item | Owner | Status | Details |
|------|-------|--------|---------|
| Performance optimization | @orchestrator | 🔲 | Parallel extraction, connection pooling |
| Documentation | @orchestrator | 🔲 | README, ARCHITECTURE, ENTERPRISE_GUIDE, API docs |
| Stress testing | @tester | 🔲 | 10,000+ document migration test |
| v1.0.0 release | @orchestrator | 🔲 | Production-ready release |

### Phase 4 Success Criteria

| Metric | Target |
|--------|--------|
| Tests | 2,000+ |
| Coverage | ≥ 90% |
| Document types | 50+ MIME types handled |
| Batch throughput | 1,000 docs/hour on standard hardware |

---

## Roadmap Summary

| Phase | Sprints | Focus | Key Deliverables |
|-------|---------|-------|-----------------|
| **Phase 0** | 1–4 | Foundation | OT API client, metadata extraction, CI |
| **Phase 1** | 5–8 | Fabric Generation | Lakehouse, Data Factory, PySpark, governance |
| **Phase 2** | 9–14 | BIRT → Power BI | Report parser, DAX conversion, .pbip output |
| **Phase 3** | 15–18 | Documentum | Documentum API, content migration, ACL mapping |
| **Phase 4** | 19–24 | Enterprise | Assessment, batch, deployment, incremental sync |

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
