# IBB Insurance Portal

FastAPI backend foundation for the IBB Insurance Portal MVP.

Bitrix24 remains the source of truth for business data. The portal stores only technical data needed for authentication, access control, Bitrix24 links, integration status, document transfer status, safe user actions, reference mappings, and audit.

## Local Setup

Copy `.env.example` to `.env` and fill local values. Do not commit `.env`.

```bash
cp .env.example .env
python -m pip install -e ".[dev]"
```

## Docker Compose Runtime

The local Compose runtime starts:

- `backend` on `http://localhost:8000`;
- `frontend` on `http://localhost:3000`;
- `postgres` with the named volume `postgres_data`;
- `redis` as cache/queue without persistent volume.

Start local services:

```bash
cp .env.example .env
docker compose up --build
```

Apply migrations and seed reference data:

```bash
docker compose run --rm migrate
docker compose run --rm seed
```

Equivalent backend-container commands:

```bash
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m app.scripts.seed_reference_data
```

Stop or reset the local runtime:

```bash
docker compose down
docker compose down -v
```

Useful Makefile shortcuts:

```bash
make dev-up
make docker-migrate
make docker-seed
make logs
make dev-down
make dev-reset
```

Only public frontend variables with the `NEXT_PUBLIC_` prefix are passed to the frontend service. Backend-only secrets such as database URLs, Redis URLs, JWT/cookie secrets, SMTP credentials, and Bitrix24 webhook URLs must stay backend-only.

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
docker compose run --rm migrate
```

Seed reference data idempotently:

```bash
python -m app.scripts.seed_reference_data
docker compose run --rm backend python -m app.scripts.seed_reference_data
docker compose run --rm seed
```

## Health Endpoints

- `GET /health`
- `GET /health/live`
- `GET /health/ready`

Readiness checks PostgreSQL, Redis, the Alembic version table, and required reference data. Responses never expose `DATABASE_URL`, `REDIS_URL`, tokens, environment variables, request bodies, stack traces, or personal data.

## Auth Endpoints

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /auth/refresh`

Auth uses httpOnly cookies for access and refresh tokens. Refresh tokens are stored in PostgreSQL only as hashes in `user_sessions`; API responses do not return tokens. Login rate limiting uses Redis counters by IP and hashed email. Authentication actions are written to PostgreSQL `audit_logs` with sanitized metadata only.

## Verification

```bash
ruff check .
pytest
docker build -t ibb-backend-test .
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```
