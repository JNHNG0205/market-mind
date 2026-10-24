# MarketMind

A crypto research agent runtime. It routes each question to an intent, loads the matching research skill, calls tools over MCP, and streams a grounded answer with citations. It can also place paper trades, which always need user confirmation. Spec: [`SPEC.md`](SPEC.md). Decisions that refine the spec: [`DECISIONS.md`](DECISIONS.md).

> Status: M1 in progress. Step 1 (scaffold) is done.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/) 0.13.4 or later, and Docker Desktop.

```bash
cp .env.example .env      # add OPENROUTER_API_KEY and TAVILY_API_KEY
make install              # uv sync + pre-commit hooks
make dev                  # postgres + redis in docker; api :8000 and mcp-tools :8001 with reload
```

Run the full stack in containers instead:

```bash
docker compose up --build
curl localhost:8000/readyz   # {"status":"ready","checks":{"postgres":"ok","redis":"ok","mcp":"ok"}}
```

## Checks

```bash
make lint typecheck test   # offline, no keys, no services
make test-integration      # needs `make infra`
```
