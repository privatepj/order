# Repository Guidelines

## Project Structure & Module Organization
`app/` is the Flask application. Keep HTTP handlers in `app/main/`, auth and API access in `app/auth/` and `app/openclaw/`, business rules in `app/services/`, ORM models in `app/models/`, and reusable helpers in `app/utils/`. Jinja templates and static assets live in `app/templates/` and `app/static/`. Tests currently live under `tests/e2e/orchestrator/`. Database bootstrap and incremental migrations are in `scripts/sql/`. Operational and rollout notes belong in `docs/`.

## Build, Test, and Development Commands
Use the repo virtualenv instead of global tools:

- `.\.venv\Scripts\python.exe run.py` starts the dev server on port 5000.
- `.\.venv\Scripts\python.exe -m pytest` runs the full test suite.
- `.\.venv\Scripts\python.exe -m pytest tests/e2e/orchestrator/test_orchestrator_p2_e2e.py` runs one module.
- `.\.venv\Scripts\python.exe -m ruff check app` lints application code.
- `.\.venv\Scripts\python.exe -m ruff format app` formats application code.
- `Get-Content scripts/sql/00_full_schema.sql | mysql -u root -p sydixon_order` initializes a new database from PowerShell.

## Coding Style & Naming Conventions
Follow Python 3.9+ conventions with 4-space indentation, snake_case for functions/modules, and PascalCase for SQLAlchemy models. Route files use the `routes_<domain>.py` pattern; service modules use `<domain>_svc.py`. Keep request handling thin and move business logic into `app/services/`. Prefer small helpers over duplicating query logic across routes. Use Ruff for linting and formatting before opening a PR.

## Testing Guidelines
Pytest is configured through `pytest.ini` with `test_*.py` discovery under `tests/`. Existing tests use `create_app(TestConfig)` with in-memory SQLite, so new tests should isolate setup the same way when possible. There is no enforced coverage threshold yet; add regression tests for service-layer changes, orchestrator flows, and bug fixes.

## Commit & Pull Request Guidelines
Recent history mixes terse subjects (`0401`) with occasional prefixes like `fix:`. Prefer clearer commit subjects in imperative form, optionally using a prefix such as `fix:` or `feat:`. Keep each commit scoped to one change. PRs should include the affected module, database impact, test/lint results, and screenshots for template or UI changes.

## Documentation & Project Skill
- Entry: `docs/index.md`. In-repo **project Skill** for agents and humans: `docs/04_ai/project-skill/SKILL.md`.
- When changing business logic, RBAC, SQL/schema, or OpenClaw contracts, update the relevant `docs/02_domains/*.md` and project-skill pages; see `docs/changes/README.md`.
- Optional check before commit: `python scripts/check_docs_sync.py` (use `--strict` in CI if desired).

## Database & Migration Rules
Do not add database-level foreign keys in SQL or `ForeignKey()` in models; this project enforces relations in application code with explicit joins. Treat `scripts/sql/run_*.sql` as append-only. Add a new `run_NN_description.sql` file for schema changes, and only edit `00_full_schema.sql` when the full bootstrap must reflect the latest schema.
