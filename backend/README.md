# Business Billing & Operations Platform - backend foundation

FastAPI + PostgreSQL + Alembic. No Docker: it runs directly on your machine with a local PostgreSQL,
which you inspect with pgAdmin, all from one VS Code window.

Covers steps 0-2 of the plan: schema v2, migrations, authentication, company/tenant isolation,
role permissions enforced in the API, audit trail, and tests that prove it.

## What you need installed
| Tool | Version | Notes |
|---|---|---|
| Python | 3.10 or newer | tick "Add python.exe to PATH" on Windows |
| PostgreSQL + pgAdmin | PostgreSQL 13 or newer | the standard installer includes pgAdmin; remember the `postgres` password |
| VS Code | any | install the extensions it recommends when you open the folder |

## One-time setup (about 10 minutes)

Open the `billing-platform` folder in VS Code (File -> Open Folder), then Terminal -> New Terminal:

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -e ".[dev]"
python scripts/setup_db.py          # 1st run creates .env  -> edit it: put your PostgreSQL password in DATABASE_URL
python scripts/setup_db.py          # 2nd run creates the databases `billing` and `billing_test`
alembic upgrade head                # builds all tables
```
**macOS / Linux**
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python scripts/setup_db.py          # (twice, as above)
alembic upgrade head
```
Then in VS Code: Ctrl+Shift+P -> **Python: Select Interpreter** -> choose the one inside `.venv`.

Check it worked: in pgAdmin open `billing -> Schemas -> public -> Tables` (details in `docs/pgadmin-guide.md`).

## Daily workflow

| I want to... | Do this |
|---|---|
| Run the API with the debugger | press **F5** (runs on http://localhost:8000, docs at `/docs`) |
| Try endpoints | open `requests.http`, click **Send Request** (needs the *REST Client* extension) |
| Run the tests | Testing panel (flask icon) or Terminal -> Run Task -> **Run all tests** |
| Apply new migrations | Run Task -> **DB: migrate to latest** (or `alembic upgrade head`) |
| See the database | pgAdmin (refresh the Tables node with F5) |
| Start from a clean database | Run Task -> **DB: RESET dev database** |

All of these are in Terminal -> Run Task. They use the interpreter you selected, so no manual activation needed.

## Changing the schema (the Alembic way)

```powershell
python scripts/new_migration.py add_party_tags     # or Run Task -> "DB: new migration"
```
This creates three small files:
- `alembic/versions/0005_add_party_tags.py` - wiring, you don't edit it
- `alembic/sql/0005_add_party_tags.sql` - **your SQL goes here** (plain PostgreSQL)
- `alembic/sql/0005_add_party_tags.down.sql` - optional undo

Write the SQL, run `alembic upgrade head`, refresh pgAdmin, run the tests. Each migration runs in one
transaction: if any statement fails, nothing is applied. Other useful commands:
`alembic current` (where am I), `alembic history`, `alembic downgrade -1` (uses the `.down.sql`).

Rule of thumb: **change the database only through migrations, look at it through pgAdmin.**

## Run the tests
```powershell
pytest -v
```
They run against `billing_test` (your real `billing` data is never touched). The test database is wiped and rebuilt
from the migrations at the start of each run.

## Project layout
```
alembic/sql/        0001 original schema | 0002 schema v2 fixes | 0003 auth tables   <- the real schema
alembic/versions/   thin wrappers that run those SQL files (+ 0004 permission seed)
app/core/           config, security (argon2 passwords, JWT), errors, permissions list, request context
app/api/deps.py     get_current_user, get_company_context, require_permission(...)
app/api/v1/         endpoints: auth, companies, members/invitations, audit
app/modules/        business logic per area (identity, companies, audit)  <- sales, purchases... go here
scripts/            setup_db.py, reset_db.py, new_migration.py
tests/              auth, tenant isolation, permissions, database integrity rules
docs/               schema-v2-changes.md, pgadmin-guide.md
.vscode/            tasks, F5 launch config, test settings
```

## Troubleshooting
| Symptom | Fix |
|---|---|
| `password authentication failed` / `connection refused` | PostgreSQL not running, or wrong password/port in `.env` (special characters must be URL-encoded: `@` -> `%40`) |
| `could not connect` when running tests | create the test DB: `python scripts/setup_db.py` |
| `permission denied to create extension "pgcrypto"` | connect as the `postgres` superuser in `DATABASE_URL` |
| `pip install` fails building a package on Windows | upgrade pip first: `python -m pip install --upgrade pip` |
| PowerShell won't activate `.venv` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, reopen terminal |
| pgAdmin shows no tables | right-click `Tables` -> Refresh; make sure you expanded database `billing`, not `postgres` |
| Tests fail at the very first test | read the first error in the output; send it to me and I will fix it |

## Design decisions
| Decision | Choice | Why |
|---|---|---|
| Schema changes | Hand-written SQL migrations, no autogenerate | The triggers/constraints that protect the books can't be generated from models |
| DB access | SQLAlchemy 2 with explicit SQL, synchronous | Posting logic is easier to audit as SQL |
| Auth | 15-min JWT + rotating refresh token (stored hashed); session checked every request | Works for web and a future Android app; logout/removal is immediate |
| Company context | `X-Company-Id` header, re-validated in the DB each request | Unknown and forbidden companies both give 403, so IDs can't be probed |
| Roles | Per-tenant roles from `app/core/permissions.py`; only Owner manages users / closes periods | Matches the plan |
| Errors | `{"error": {"code", "message", "details", "request_id"}}` | Frontend and mobile switch on `code` |

## Status and gaps
- **Not run yet.** The code was written without access to PostgreSQL, so only syntax was checked. Run `pytest -v`
  first; send me any failures.
- Not built yet: email verification, password reset, MFA, emailing invitations, API rate limiting, GSTIN checksum.
- Next step (3): posting engine - Decimal GST calculator, numbering, default chart of accounts, first sales invoice + payment.
