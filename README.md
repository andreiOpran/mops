# Platforma web de monitorizare real-time a întârzierilor STB

MOPS lab project: an open, continuously updated history of real delays for Bucharest-Ilfov surface public transport, built from the TPBI GTFS / GTFS-RT feeds.

| Folder | Content |
|---|---|
| `docs/` | Requirements, user stories, product backlog, estimation, diagrams |
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

### Load the timetable

The database starts empty. Download the TPBI GTFS archive and import it with the US-01 importer (run each command on its own; the import prints nothing until it ends and can take a few minutes):

```bash
curl -L -A "Mozilla/5.0" -o backend/gtfs.zip https://gtfs.tpbi.ro/regional/BUCHAREST-REGION.zip
docker compose exec backend python -m app.gtfs gtfs.zip
rm backend/gtfs.zip
```

- On Windows PowerShell use `curl.exe` (plain `curl` is another command there), `backend\gtfs.zip` and `Remove-Item` instead of `rm`.
- The TPBI server rejects requests without a browser-like User-Agent, hence `-A`.
- The import should print `gtfs.zip: imported <version> (feed_version_id=<n>)`. An archive already imported is skipped.
- The VPS collector keeps every timetable version in `/var/lib/stb-collector/static/`; copy that folder locally and run `python -m app.gtfs --all <folder>` to import them all.

### Run the tests

The tests expect an empty database, so they use a separate `stb_test` database (create it once; recreate it after `docker compose down -v`):

```bash
docker compose exec db psql -U stb -c "create database stb_test"
docker compose exec -e DATABASE_URL=postgresql+psycopg://stb:stb@db:5432/stb_test backend sh -c "alembic upgrade head && pytest"
```

Frontend checks (the same as CI):

```bash
cd frontend
npm run lint
npm run build
```

### Reset the database

Deletes all data (timetable, test database); the migrations run again at the next start:

```bash
docker compose down -v
docker compose up --build
```

Needed when switching to a branch that lacks a migration the database already has (`Can't locate revision ...` at startup).

## Backend without Docker

Needs a PostgreSQL database (e.g. `docker compose up db`).

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

Tests against the separate test database (see [Run the tests](#run-the-tests)):

```bash
DATABASE_URL=postgresql+psycopg://stb:stb@localhost:5432/stb_test .venv/bin/alembic upgrade head
DATABASE_URL=postgresql+psycopg://stb:stb@localhost:5432/stb_test .venv/bin/pytest
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
