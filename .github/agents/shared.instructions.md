# Shared Agent Instructions — OpenText to Fabric Migration

## Project Context
You are an agent in the **OpenText to Fabric Migration Tool** — a Python project that migrates OpenText ECM (Content Server, Documentum) content, metadata, and BIRT/iHub reports to Microsoft Fabric (OneLake Lakehouse, Data Factory, PySpark Notebooks) and Power BI (.pbip).

## Architecture
- **2-step pipeline:** Extraction (OpenText APIs/XML) → Intermediate JSON (15+ files) → Generation (Fabric + PBI artifacts)
- **10-agent model:** @orchestrator, @extractor, @content, @report, @semantic, @pipeline, @governance, @assessor, @deployer, @tester
- **Python 3.12+**, zero external dependencies for core

## Rules
1. **One owner per file.** Only the owning agent modifies a file. Read access is universal.
2. **Tests in `tests/` only.** Only @tester writes test files.
3. **No external dependencies** for core migration logic. Optional integrations (OCR, Key Vault) are pluggable.
4. **Security first.** Never log credentials. Validate all paths. Scrub sensitive data from audit trails.
5. **Intermediate JSON is the contract.** Extraction produces JSON; generation consumes JSON. Agents communicate through this contract.
6. **Handoff protocol.** When work crosses agent boundaries: complete your part → state the handoff → name the target agent → list artifacts → include context.

## Code Standards
- Type hints on all public functions
- Docstrings on all public classes and functions
- `unittest.TestCase` for tests (pytest runner)
- No `print()` — use `logging` module
- f-strings preferred over `.format()` or `%`

## File Naming
- Snake case for all Python files
- Test files: `test_{module_name}.py`
- JSON schema files: lowercase with underscores
