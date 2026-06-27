.PHONY: install lint test migrate downgrade seed run docker-build dev-up dev-down dev-reset logs docker-migrate docker-seed

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .

test:
	pytest

migrate:
	alembic upgrade head

downgrade:
	alembic downgrade -1

seed:
	python -m app.seed

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

docker-build:
	docker build -t ibb-backend-test .

dev-up:
	docker compose up --build

dev-down:
	docker compose down

dev-reset:
	docker compose down -v

docker-migrate:
	docker compose run --rm migrate

docker-seed:
	docker compose run --rm seed

logs:
	docker compose logs -f backend frontend postgres redis
