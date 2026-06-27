.PHONY: install lint test migrate downgrade seed run docker-build

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
