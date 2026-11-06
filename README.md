# Platforma web de monitorizare real-time a întârzierilor STB

MOPS lab project: an open, continuously updated history of real delays for Bucharest-Ilfov surface public transport, built from the TPBI GTFS / GTFS-RT feeds.

| Folder | Content |
|---|---|
| `docs/` | Requirements, user stories, product backlog, estimation, AI usage log, diagrams |
| `collector/` | Raw GTFS-RT archiver running 24/7 on the VPS (T-01), see its README |
| `backend/` | FastAPI API, SQLAlchemy + Alembic, PostgreSQL |
| `frontend/` | React + TypeScript web app (Vite) |

## Run locally

Requirements: Docker with Compose.

```bash
docker compose up --build
```

- Web app: http://localhost:5173
- API docs (OpenAPI): http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

The backend and frontend folders are mounted into the containers, so code changes reload automatically.

## Backend without Docker

Needs a PostgreSQL database (e.g. `docker compose up db`).

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
.venv/bin/pytest
```

New table: add the model under `app/` (subclass `app.db.Base`), import it in `alembic/env.py`, then:

```bash
.venv/bin/alembic revision --autogenerate -m "describe the change"
.venv/bin/alembic upgrade head
```

## Frontend without Docker

```bash
cd frontend
npm install
npm run dev     # proxies /api to http://localhost:8000
npm run lint
npm run build
```

## Workflow

- One branch per story or task (`feat/us-01-...`, `fix/...`, `docs/...`), merged through a Pull Request.
- Every PR is reviewed by a developer other than the author.
- CI (GitHub Actions) runs on every PR: backend tests with coverage against PostgreSQL, migrations, collector tests, frontend lint and build.
- TDD stories: separate commits for Red (failing test), Green, Refactor.
- Significant AI help is logged in `docs/ai-usage-log.md`.
