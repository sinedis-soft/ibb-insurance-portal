# IBB Insurance Portal

FastAPI backend foundation for the IBB Insurance Portal MVP.

Bitrix24 remains the source of truth for business data. The portal stores only technical data needed for authentication, access control, Bitrix24 links, integration status, document transfer status, safe user actions, reference mappings, and audit.

## Local Setup

Copy `.env.example` to `.env` and fill local values. Do not commit `.env`.

```bash
python -m pip install -e ".[dev]"
```

## Database Migrations

Run migrations directly:

```bash
alembic upgrade head
alembic downgrade -1
```

Run migrations through Docker Compose:

```bash
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend alembic downgrade -1
```

Seed reference data idempotently:

```bash
python -m app.seed
docker compose run --rm backend python -m app.seed
```

## Health Endpoints

- `GET /health`
- `GET /health/live`
- `GET /health/ready`

Readiness checks PostgreSQL, Redis, the Alembic version table, and required reference data. Responses never expose `DATABASE_URL`, `REDIS_URL`, tokens, environment variables, request bodies, stack traces, or personal data.

## Verification

```bash
ruff check .
pytest
docker build -t ibb-backend-test .
```
