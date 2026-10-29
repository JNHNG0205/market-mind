test:
	uv run pytest -m "not integration and not live" --cov

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy
	
infra:
	docker compose up -d --wait postgres redis

infra-down:
	docker compose down

test-integration:
	uv run pytest -m "integration"

api:
	uv run uvicorn --factory marketmind.api.app:create_default_app --reload --port 8000

mcp:
	uv run uvicorn --factory marketmind.tools.server:create_app --reload --port 8001

.PHONY: test lint format typecheck infra infra-down test-integration api mcp