# MarketMind

A Python 3.12 async service that answers crypto research questions and runs paper trades through a LangGraph agent. Tools live in a separate FastMCP server process.

- **Source of truth:** `SPEC.md`. Decisions that refine or override the spec are in `DECISIONS.md`; read both before starting a step.
- **Current state:** no code yet. M1 restarts from step 1 (scaffold). Target 2026-10-31.

## Working mode: the user is learning; Claude types, the user thinks

The user is building this project to learn it well enough to explain every part in an interview. That goal outranks speed.

- **The user writes only the core pieces:** the router, the executor's timeout and retry logic, the plan-and-execute loop, and RRF merging, plus anything else the user explicitly claims later. For those, Claude writes only `TODO(you)` stubs (signatures plus `raise NotImplementedError`) and failing tests that define the behaviour. Then Claude stops.
- **Claude writes everything else:** scaffolding, config, Docker, CI, API plumbing, adapters, persistence, tools and other boilerplate.
- **When unsure whether something is core, ask** instead of writing it.
- **Never merge a diff the user can't explain.** Keep diffs small and readable. When asked "why this approach over X?", answer directly.
- **The user writes every commit message**, one line in their own words. Claude proposes no commit message unless asked, and doesn't commit until the user supplies one.
- **Struggle first.** When the user is stuck, point to the primary source (LangGraph docs on interrupts and checkpoints, the MCP spec, library source) before giving the answer. Give hints before solutions unless the user asks for the solution.
- **Review and grill on request.** Review the user's code like a senior engineer, and grill them on their own codebase like an interviewer, noting what they couldn't answer.
- **Encourage predict-then-run:** before running a test, an eval or a query, ask what they expect.

## Workflow

- One branch and one PR per checklist step: `feat/m1-NN-<slug>`. Squash-merge only after the user's OK.
- No AI attribution anywhere: no `Co-Authored-By: Claude` trailers in commits, and no "Generated with Claude Code" lines in PR descriptions.
- If something is ambiguous: choose the simplest option, add it to `DECISIONS.md`, and say so.
- Use only dependencies listed in `SPEC.md` §3 or approved in `DECISIONS.md`; propose anything else with a reason first.

## Code rules (from the spec)

- Fully typed; `mypy --strict` with no `type: ignore` unless a comment explains it. Ruff for lint and format.
- Graph nodes are pure async functions `(state, deps) -> partial state`, with dependencies passed in through `Deps`.
- No `datetime.now()` in app code; use the injected `Clock`.
- Prompts live in `agent/prompts/*.md`; research procedures live in `skills/<name>/SKILL.md`.
- Every external call goes through the MCP tool server; tools return `ToolResult(ok=False, ...)` instead of raising.
- `make test` passes offline with no API keys (fake LLM, recorded HTTP fixtures).

## Facts worth knowing (checked 2026-10-24)

- `mcp` 2.x renamed FastMCP to `MCPServer` (`from mcp.server.mcpserver import MCPServer`).
- The `openai`, `anthropic` and `mcp` SDKs use `httpx2`, so mock them with `httpx2.MockTransport` via `http_client=`, not respx (D32).
- OpenRouter: the account's privacy setting blocks DeepSeek's own host, so pin Fireworks then Together (D33).
- A draft of steps 1-3 exists under tag `archive/claude-draft-m1-steps-1-3`. Claude may reuse it for non-core parts. Never use it to fill in, or hint at, a core piece unless the user asks.
