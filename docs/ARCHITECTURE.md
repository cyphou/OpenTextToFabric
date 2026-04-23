# Architecture — OpenText to Fabric Migration Tool

## Pipeline Overview

The migration follows a **2-step pipeline** (same pattern as TableauToPowerBI): Extraction → Generation.
A third step (Content Transfer) handles binary document migration unique to ECM.

```
              ┌──────────────────────────────────┐
              │            INPUT                  │
              │                                   │
              │  OpenText Content Server (REST v2) │
              │  OpenText Documentum (REST/DFC)    │
              │  BIRT .rptdesign files (XML)       │
              │  OpenText AppWorks (metadata)      │
              └───────────────┬───────────────────┘
                              │
                              ▼
              ┌──────────────────────────────────┐
              │   STEP 1 — EXTRACTION             │
              │   opentext_extract/               │
              │                                   │
              │   api_client.py                   │
              │     +── content_server.py         │
              │     │   (nodes, categories,       │
              │     │    workflows, permissions)   │
              │     +── documentum_client.py      │
              │     │   (cabinets, objects,        │
              │     │    lifecycles, ACLs)         │
              │     +── birt_parser.py             │
              │         (.rptdesign XML parsing,   │
              │          datasets, expressions,    │
              │          visuals, parameters)      │
              └───────────────┬───────────────────┘
                              │
                              ▼
              ┌──────────────────────────────────┐
              │   15+ INTERMEDIATE JSON FILES     │
              │                                   │
              │   nodes.json        metadata.json │
              │   permissions.json  workflows.json│
              │   documents.json    renditions.json│
              │   versions.json     retention.json│
              │   classifications.json             │
              │   reports.json      datasets.json │
              │   expressions.json  visuals.json  │
              │   connections.json  relationships.json│
              └───────────────┬───────────────────┘
                              │
              ┌───────────────┼───────────────────┐
              │               │                   │
              ▼               ▼                   ▼
  ┌───────────────┐  ┌──────────────┐  ┌──────────────────┐
  │STEP 2a — FABRIC│  │STEP 2b — PBI│  │ STEP 2c — GOVERN │
  │fabric_output/  │  │report_conv/  │  │ governance/      │
  │               │  │              │  │                  │
  │lakehouse_gen  │  │birt_parser   │  │ acl_mapper       │
  │pipeline_gen   │  │expr_converter│  │ classification   │
  │notebook_gen   │  │visual_mapper │  │ purview_mapper   │
  │dataflow_gen   │  │pbip_generator│  │ audit_trail      │
  │tmdl_generator │  │              │  │                  │
  └───────┬───────┘  └──────┬───────┘  └────────┬─────────┘
          │                 │                    │
          ▼                 ▼                    ▼
  ┌──────────────────────────────────────────────────────┐
  │                    OUTPUT                             │
  │                                                      │
  │  Fabric Artifacts:          Power BI Reports:         │
  │  ├── Lakehouse DDL          ├── .pbip project         │
  │  ├── Data Factory Pipelines │   ├── PBIR v4.0 report  │
  │  ├── PySpark Notebooks      │   └── TMDL semantic model│
  │  └── Dataflow Gen2          │                          │
  │                                                      │
  │  Governance:                Assessment:               │
  │  ├── RLS roles              ├── Readiness report      │
  │  ├── Purview labels         ├── Gap analysis          │
  │  └── Audit trail            └── Wave plan             │
  └──────────────────────────────────────────────────────┘
```

## Detailed Component Architecture

### Step 1 — Extraction Layer (`opentext_extract/`)

#### Content Server Extraction
```
Content Server REST v2 API
│
├── /api/v2/nodes/{id}              → Node metadata (folders, documents, URLs, shortcuts)
├── /api/v2/nodes/{id}/nodes        → Child listing (recursive traversal)
├── /api/v2/nodes/{id}/categories   → Category/attribute metadata
├── /api/v2/nodes/{id}/permissions  → ACL entries (users, groups, permissions)
├── /api/v2/nodes/{id}/versions     → Version history chain
├── /api/v2/nodes/{id}/content      → Binary download (with renditions)
├── /api/v2/members                 → Users and groups
├── /api/v2/workflows               → Workflow definitions and instances
└── /api/v2/searchresults           → Full-text search (for discovery)
```

#### Documentum Extraction
```
Documentum REST Services
│
├── /repositories/{repo}/objects/{id}           → Object metadata
├── /repositories/{repo}/objects/{id}/contents  → Binary content
├── /repositories/{repo}/objects/{id}/relations → Related objects
├── /dql                                        → DQL queries (SELECT * FROM dm_document)
├── ACL queries                                 → Permission sets
└── Lifecycle queries                           → Document lifecycle states
```

#### BIRT Report Extraction
```
.rptdesign XML Schema
│
├── <data-sources>          → JDBC/ODA connection definitions
│   └── <oda-data-source>   → Driver class, connection URL, credentials
├── <data-sets>             → SQL queries, parameters, computed columns
│   ├── <query-text>        → SQL statement
│   ├── <parameters>        → Input parameters (type, default)
│   └── <computed-columns>  → BIRT expressions → DAX candidates
├── <body>                  → Report layout
│   ├── <table>             → Tabular data display
│   ├── <extended-item>     → Charts (bar, line, pie, scatter)
│   ├── <cross-tab>         → Crosstab / pivot table
│   ├── <grid>              → Layout container
│   └── <label>/<text>      → Static text, dynamic expressions
├── <page-setup>            → Master pages, headers, footers
├── <styles>                → CSS-like styling definitions
└── <parameters>            → Report-level parameters (cascading, multi-value)
```

### Intermediate JSON Schema

| File | Source | Content |
|------|--------|---------|
| `nodes.json` | CS / Documentum | Folder/document tree with IDs, types, names, paths |
| `metadata.json` | CS / Documentum | Custom attributes, categories, tags per node |
| `permissions.json` | CS / Documentum | ACL entries: user/group + permission level per node |
| `workflows.json` | CS | Workflow definitions, steps, assignees, conditions |
| `documents.json` | CS / Documentum | Binary manifest: file sizes, MIME types, checksums |
| `renditions.json` | CS / Documentum | Available renditions per document (PDF, thumbnail) |
| `versions.json` | CS / Documentum | Version chains with dates, users, comments |
| `classifications.json` | CS / Documentum | Taxonomy trees, category assignments |
| `retention.json` | Documentum | Retention policies, lifecycle states, hold status |
| `reports.json` | BIRT | Report definitions: pages, layout elements |
| `datasets.json` | BIRT | SQL queries, parameters, computed columns |
| `expressions.json` | BIRT | JavaScript expressions → DAX conversion candidates |
| `visuals.json` | BIRT | Chart/table/crosstab definitions with properties |
| `connections.json` | BIRT / CS | Data source connection metadata |
| `relationships.json` | CS / Documentum | Cross-object references, links |

### Step 2 — Generation Layer

#### Fabric Output (`fabric_output/`)

| Generator | Input JSON | Output |
|-----------|-----------|--------|
| `lakehouse_generator.py` | nodes, metadata, classifications | Delta table DDL + OneLake directory structure |
| `pipeline_generator.py` | connections, nodes | Data Factory pipeline JSON (REST → OneLake copy) |
| `notebook_generator.py` | documents, metadata | PySpark ETL notebooks (document processing) |
| `dataflow_generator.py` | connections, datasets | Dataflow Gen2 M queries (incremental ingestion) |
| `tmdl_generator.py` | datasets, expressions | TMDL semantic model (tables, measures, relationships) |
| `m_query_generator.py` | connections | Power Query M for data source connections |

#### Report Conversion (`report_converter/`)

| Module | Input | Output |
|--------|-------|--------|
| `birt_parser.py` | .rptdesign XML | Parsed report structure (intermediate dicts) |
| `expression_converter.py` | BIRT JS expressions | DAX formulas |
| `visual_mapper.py` | BIRT visuals JSON | PBI visual configs (PBIR v4.0) |
| `pbip_generator.py` | All report JSON | .pbip project (report + semantic model) |

#### Governance (`governance/`)

| Module | Input | Output |
|--------|-------|--------|
| `acl_mapper.py` | permissions.json | Fabric RLS roles + workspace role assignments |
| `classification_mapper.py` | classifications.json | Purview sensitivity label mappings |
| `purview_mapper.py` | retention.json | Purview retention policies |
| `audit.py` | All JSON | Migration audit trail (evidence chain) |
| `security_validator.py` | All inputs | Path traversal defense, credential scrubbing |

## Key Design Principles

### 1. Source-Agnostic Intermediate Format
Same intermediate JSON format regardless of whether data comes from Content Server, Documentum, or BIRT. This enables:
- Unified generation pipeline
- Mix-and-match sources
- Future source system support (e.g., SharePoint, Box)

### 2. Fabric-First Output
Unlike TableauToPowerBI (which generates .pbip first), this project prioritizes Fabric-native artifacts:
- **Primary:** Lakehouse + Data Factory + PySpark Notebooks
- **Secondary:** Power BI reports (only for BIRT migration)

### 3. Content vs. Metadata Separation
Documents are migrated in two streams:
- **Metadata stream:** Fast, lightweight → JSON → Lakehouse Delta tables
- **Content stream:** Heavy, resumable → Binary download → OneLake file storage

### 4. Governance as First-Class Citizen
ECM migrations require deep permission mapping. Governance is not optional:
- Every document carries its permission lineage
- ACL mapping is validated before deployment
- Audit trail tracks every decision made during migration

## Comparison with TableauToPowerBI Architecture

| Aspect | TableauToPowerBI | OpenTextToFabric |
|--------|-----------------|-----------------|
| Input | .twb/.twbx files (local) | REST APIs (remote) + .rptdesign (local) |
| Extraction | XML parsing (local, fast) | API calls (network, paginated, rate-limited) |
| Intermediate | 17 JSON files | 15+ JSON files |
| Primary output | .pbip (PBIR + TMDL) | Fabric artifacts (Lakehouse, Pipeline, Notebook) |
| Secondary output | Fabric artifacts | .pbip (for BIRT reports only) |
| Binary content | None (no document migration) | Full document binary migration |
| Permissions | Basic RLS from Tableau user filters | Deep ACL → RLS + Purview mapping |
| Formula language | Tableau calc → DAX (180+ mappings) | BIRT JavaScript → DAX (80+ mappings) |
| Agents | 12 (DAX/Wiring/Semantic/Visual specialists) | 10 (@content + @governance are new) |
