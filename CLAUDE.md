# MarketMind

A Python 3.12 async service that answers crypto research questions and runs paper trades through a LangGraph agent. Tools live in a separate FastMCP server process.

- **Source of truth:** `SPEC.md`. Decisions that refine or override the spec are recorded in `DECISIONS.md`; read both before starting a step.
- **Current milestone:** M1 (target 2026-10-31). Work the M1 checklist in `SPEC.md` §15 in order, one step at a time.

## Commands

```bash
uv sync                      # install deps (Python 3.12 is managed by uv)
make dev                     # postgres + redis in docker, api + mcp-tools via uv run
make lint typecheck test     # must be green before every commit
make eval-route              # routing eval (replays fixtures unless RECORD_LLM=1)
docker compose up            # full stack (demo / clean-machine check)
```

## Workflow

- One branch and one PR per checklist step: `feat/m1-NN-<slug>`. Open the PR with `gh` once CI is green, then wait for the user's OK; squash-merge with `gh pr merge --squash` only after the OK, then branch the next step from the updated `main`.
- Conventional commit messages. Tests go in the same commit as the code; every bug fix adds a regression test first.
- No AI attribution anywhere: no `Co-Authored-By: Claude` trailers in commits, and no "Generated with Claude Code" lines in PR descriptions.
- If something is ambiguous: choose the simplest option, add it to `DECISIONS.md`, and continue.
- Use only dependencies listed in `SPEC.md` §3 or approved in `DECISIONS.md`; propose anything else with a reason before adding it.

## Code rules

- Fully typed; `mypy --strict` passes with no `type: ignore` unless a comment explains it. Ruff for lint and format.
- Each graph node is a pure async function `(state, deps) -> partial state`. Dependencies (LLM, MCP client, repos, clock) come in through the `Deps` container, never imported globals.
- Never call `datetime.now()` directly; use the injected `Clock`.
- Anything that crosses a node boundary is a Pydantic model (`SPEC.md` §4). Field names may grow but are not renamed without updating tests.
- Prompts live in `src/marketmind/agent/prompts/*.md`, never inline strings. Research procedures live in `skills/<name>/SKILL.md`, never in prompts.
- The runtime never calls external APIs directly; every external call goes through the MCP tool server.
- Tools return `ToolResult(ok=False, error=...)` instead of raising into the graph.
- Never log API keys, or full prompts at info level.

## Testing

- `make test` passes offline with no API keys. Use `FakeLLMProvider` with fixtures in `tests/fixtures/llm/`, and respx with recorded responses in `tests/fixtures/http/`.
- Live tests are opt-in only: `LIVE_TESTS=1 uv run pytest -m live` (uses the real OpenRouter key; costs fractions of a cent).
- LLM fixtures: use the `llm_case("name")` fixture; re-record with `RECORD_LLM=1`. The SDKs use `httpx2`, so mock them with `httpx2.MockTransport` via `http_client=`, not respx.
- Coverage of at least 80% on `agent/`, `mcp_client/`, `rag/`, `tools/`.

## Key decisions (details in DECISIONS.md)

- LLMs go through OpenRouter via the `openai` SDK with a `base_url`. Every node uses `deepseek/deepseek-v4.1-flash-1017`, pinned to the Fireworks then Together hosts, with JSON mode + Pydantic validation + one retry. The fallback is `z-ai/glm-5.3-flash`.
- Postgres driver is psycopg3 everywhere (`postgresql+psycopg://`); there is no asyncpg.
- Market data: Binance public REST, with CoinGecko as the fallback. Web search: Tavily.
- CI: GitHub Actions only.
