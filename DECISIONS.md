# Decisions

Choices that refine, resolve, or override `SPEC.md`. Newest entries at the bottom. Each entry: what was decided, and why.

## 2026-10-24: planning session (pre-M1)

### Project
- **D1. Name stays MarketMind; the spec file is `SPEC.md`.** Matches the repo name and the spec's own references.
- **D2. Planning depth:** M1 is planned in full; M2 only where it shapes M1 interfaces, schema or naming.

### LLMs
- **D3. Provider: OpenRouter through the `openai` SDK with a configurable `base_url`.** One key covers every model and embeddings. The `anthropic` adapter is still built (the spec asks for both SDKs) but is not the default.
- **D4. Model: `deepseek/deepseek-v4.1-flash-1017` for every node** (router, skill selection, planner, composer). Provider and model are configurable per node, so changing one is a config change.
- **D5. ~~OpenRouter routing pinned to the DeepSeek host~~ (superseded by D33). No host fallback** (`provider.order=["DeepSeek"]`, `allow_fallbacks=false`). Keeps results reproducible.
- **D6. Structured output uses JSON mode** (`response_format={"type": "json_object"}`) followed by Pydantic validation and one retry. The DeepSeek host on OpenRouter does not support strict `json_schema` output. The planner uses native tool calling, which that host supports.
- **D7. LLM fallback provider: `z-ai/glm-5.3-flash`**, any OpenRouter host, same JSON-mode path. Used only after the primary model's retries fail; logged as `llm_fallback`.
- **D8. Embeddings (from M2): `openai/text-embedding-3-small` via OpenRouter.** Local `bge-small` (sentence-transformers) is an opt-in extra so PyTorch stays out of the default image.
- **D9. Model comparison: router-only bake-off in M1** via `make eval-route --model`. A planner/composer comparison is deferred.

### Dependencies
- **D10. psycopg3 everywhere instead of asyncpg.** `langgraph-checkpoint-postgres` requires psycopg3; using one driver for SQLAlchemy, Alembic and the checkpointer avoids running two. DSN scheme: `postgresql+psycopg://`.
- **D11. Approved additions to SPEC §3:**
  - `langgraph-checkpoint-postgres`: the LangGraph Postgres checkpointer the spec requires.
  - `psycopg[binary]`: the driver (D10).
  - `psycopg-pool`: connection pool required by the checkpointer.
  - `python-ulid`: the spec requires ULIDs for ids.
  - `skills-ref` (dev only): the spec requires `skills-ref validate`.

### Data sources
- **D12. Market data: Binance public REST** (spot `api.binance.com`, futures `fapi.binance.com`), with CoinGecko as the fallback `MarketDataProvider`. Both were reachable from the dev network on 2026-10-23.
- **D13. Web search: Tavily.**
- **D14. Optional `COINGECKO_API_KEY`** (demo tier) setting; the code works without it at public rate limits.
- **D15. Ticker dictionary: a script snapshot of CoinGecko's top 200**, keeping only coins with a Binance USDT pair, written to a committed yaml file. Aliases are added by hand. Tests never touch the network.

### Agent behaviour
- **D16. M1 `select_skills`: filter by the routed intent, then an LLM pick** (at most 2, `"none"` allowed). The embedding prefilter is added in M2 behind the same interface.
- **D17. Tool allowlist:** take the union of the loaded skills' `allowed-tools`, then keep only what the intent allows. With no skill loaded, use the full intent allowlist. `read_skill_resource` and `crypto_data_lookup` are always added except for `off_topic`. Tools that don't exist yet are dropped and logged at debug level.
- **D18. `refuse` becomes `respond_direct`**, one node with two templates: the off_topic refusal and the router's clarifying question. No tool calls; streams the usual `token`/`citations`/`done` events.
- **D19. M1 rewriter is a deterministic stub with no LLM:** ticker-dictionary normalisation, with the original text passed through as `standalone`. The current UTC time from the injected `Clock` goes into the planner prompt. The M2 LLM rewriter keeps the same `RewrittenQuery` output.
- **D20. Citations:** Python numbers every tool result and chunk (`[1]`, `[2]`, …) in the composer prompt. The model cites those markers, which are parsed into `Citation` objects after streaming. Unknown markers are stripped, and uncited sentences are counted as a metric.

### Paper trading
- **D21. Paper accounts are per session**, as in the SPEC §12 tables; each new session starts with 10,000 USDT.
- **D22. Trade rules:**
  - Market orders only (`order_type="market"`).
  - 0.1% fee, charged in USDT.
  - No shorting or margin: sells larger than the position and buys larger than the cash are rejected.
  - Maximum order of 5,000 USDT notional.
  - The fill price is fetched fresh at confirm time; the confirmation summary shows the plan-time price as "about X".
- **D23. The executor calls `get_price` to build the confirmation summary.** The MCP server writes the paper ledger to Postgres directly.

### Process
- **D24. CI: GitHub Actions only.** No `.gitlab-ci.yml`; the repo is hosted on GitHub.
- **D25. One branch and PR per checklist step** (`feat/m1-NN-<slug>`). The PR is squash-merged after the user's OK.
- **D26. Dev runtime:** Postgres and Redis run in docker compose; the api and mcp-tools run on the host via `uv run`. The full compose stack is for the demo and the clean-machine check.
- **D27. The routing eval set and the M1 skill procedures are drafted by Claude and reviewed by the user.** README numbers come from one live run (`RECORD_LLM=1`), which also records the fixtures CI replays.
- **D28. Chat page: one vanilla-JS `index.html`, no build step.** It reads the POST SSE stream with `fetch` and a `ReadableStream`, since `EventSource` only supports GET.
- **D29. If M1 runs late, the chat page's polish is cut first.** Backend, tests and eval-route are protected.

## 2026-10-24: decisions made after planning

A first draft of M1 steps 1-3 was written by Claude and then rolled back so the work can be done by hand (the code is kept under tag `archive/claude-draft-m1-steps-1-3`, for reference only). These decisions came out of that draft and still stand.

- **D30. Hardening for the eMudhra/emSign CA incident** ([advisory](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576)):
  - Use uv `>= 0.13.4`, and pin it in CI and the Dockerfile.
  - Keep `certifi >= 2026.10.19` (for example with a `[tool.uv] constraint-dependencies` entry).
  - Docker images upgrade `ca-certificates` and are built with `--pull --no-cache`.
  - Revisit when a CPython 3.12 release ships the `ssl` SPKI blocklist.
- **D31. `pytest-cov` approved** as a dev dependency, for the SPEC §14 coverage rule (at least 80%).
- **D32. SDK versions:** prefer releases at least two weeks old. When checked on 2026-10-24 that meant `anthropic` 1.13 (2.0 was three days old) and `openai` 3.28. Both SDKs, and `mcp` 2.x, now use `httpx2` rather than `httpx`, so respx can't mock them; inject `httpx2.MockTransport` through `http_client=` instead.
- **D33. The primary model is pinned to the Fireworks host, then Together** (`provider.order=["Fireworks","Together"]`, `allow_fallbacks=false`). The account's OpenRouter privacy setting excludes hosts that may train on prompts, which removes DeepSeek's own host (OpenRouter 404 "No endpoints found … Paid model training violation"). Fireworks charges $0.21/$0.84 per 1M tokens, and OpenRouter reports the cost in `usage.cost`.
- **D34. An OpenRouter 404 "No endpoints found" is retryable**, so the GLM fallback (D7) runs on routing failures. Other 4xx errors fail fast.

## Working mode (from 2026-10-24)

The user writes all the code, scaffold included. Claude gives step-by-step instructions (commands, files, spec per file, docs, done-check) and reviews. See CLAUDE.md. The scaffold Claude wrote earlier (PR #4) was removed from `main` so it can be rebuilt by hand.
