.PHONY: install infra infra-down dev api mcp test test-integration lint format typecheck check eval-route ingest

install:
	uv sync
	uv run pre-commit install

infra:
	docker compose up -d --wait postgres redis

infra-down:
	docker compose down

# Postgres + Redis in docker, api + mcp-tools on the host with reload (DECISIONS.md D26).
dev: infra
	@trap 'kill 0' INT TERM; \
	$(MAKE) mcp & \
	$(MAKE) api & \
	wait

api:
	uv run uvicorn --factory marketmind.api.app:create_default_app --reload --port 8000

mcp:
	uv run uvicorn --factory marketmind.tools.server:create_app --reload --port 8001

# Offline, no services, no keys.
test:
	uv run pytest -m "not integration and not live"

# Needs `make infra` (or CI service containers).
test-integration:
	uv run pytest -m integration

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy

check: lint typecheck test

eval-route:
	@echo "eval-route: not implemented yet (M1 step 9)" && exit 1

ingest:
	@echo "ingest: not implemented yet (M2 RAG)" && exit 1
