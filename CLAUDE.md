# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run development server
python run.py

# Run tests
pytest

# Run a single test file
pytest tests/e2e/orchestrator/test_foo.py

# Lint
ruff check app/

# Auto-format
ruff format app/

# Generate OpenClaw API token for a user
flask openclaw-token-create <username>
```

**Database setup:**
```bash
# New database
mysql -u root -p sydixon_order < scripts/sql/00_full_schema.sql

# Migrate existing database
mysql -u root -p sydixon_order < scripts/sql/01_migrations_for_old_db.sql
```

Copy `.env.example` to `.env` and fill in `DATABASE_URL` and `SECRET_KEY`. Default dev credentials: `admin` / `password`.

## Architecture

Flask app with a service layer pattern: routes delegate to `app/services/`, which contain all business logic. Models are in `app/models/`.

**Key modules:**
- `app/auth/` — RBAC with fine-grained capabilities, menu generation, API key auth, OpenClaw token auth
- `app/models/` — ~40 SQLAlchemy models (no DB-level foreign keys — see constraint below)
- `app/services/` — business logic services (order, delivery, inventory, production, orchestrator, HR, machine, procurement)
- `app/main/` — 23 route files, one per domain
- `app/openclaw/` — REST API for AI integration
- `app/utils/` — Excel export, quantity/status display helpers
- `scripts/sql/` — database migrations (append-only `run_NN_*.sql` files)

**Documentation:** start at `docs/index.md`; in-repo project Skill for agents: `docs/04_ai/project-skill/SKILL.md`. After logic/RBAC/SQL/API changes, update domain docs and that Skill (see `docs/changes/README.md`).

**Orchestrator engine** (`app/services/orchestrator_engine.py`): event-driven state machine that reacts to domain events (`order.changed`, `inventory.changed`, `production.measured`, `quality.passed/failed`, `machine.abnormal`, etc.) and auto-generates actions (create preplan, run production measure, move order status, create procurement, escalate alerts). Supports replay, retry, overdue scanning, and a kill switch (`ORCHESTRATOR_KILL_SWITCH=1` env var). See `docs/orchestrator_runbook.md` for operations.

## Hard Constraints

### No database-level foreign keys
MySQL migration scripts (`scripts/sql/**/*.sql`) must not contain `CONSTRAINT ... FOREIGN KEY` or `REFERENCES` clauses. In SQLAlchemy models, do **not** use `ForeignKey()` on columns. Instead, write explicit `primaryjoin` with `foreign(child_table.fk_col)` to declare the logical foreign key side. Referential integrity is enforced at the application layer only.

### SQL migration scripts are append-only
`scripts/sql/run_*.sql` files that already exist must **never** be modified. To add new schema changes, create the next `run_NN_description.sql` file. Only `00_full_schema.sql` (the full schema definition) may be edited in place. Reason: incremental scripts may already have been executed in test/production environments; modifying them breaks auditability and replay.
