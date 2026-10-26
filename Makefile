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

.PHONY: test lint format typecheck