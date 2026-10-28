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

.PHONY: test lint format typecheck infra infra-down test-integration