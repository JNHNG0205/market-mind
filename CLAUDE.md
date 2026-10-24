# MarketMind

A Python 3.12 async service that answers crypto research questions and runs paper trades through a LangGraph agent. Tools live in a separate FastMCP server process.

- **Source of truth:** `SPEC.md`. Decisions that refine or override the spec are in `DECISIONS.md`; read both before starting a step.
- **Current state:** no code yet. M1 restarts from step 1 (scaffold). Target 2026-10-31.

## Working mode: the user writes all the code; Claude instructs and reviews

The user is building this project to learn it well enough to explain every part in an interview. That goal outranks speed.

- **The user writes everything:** scaffold, config, Docker, CI and all Python. Claude does not create or edit project code or config files.
- **Claude gives clear instructions, one small task at a time.** Each task includes:
  - the exact shell commands to run
  - which files to create
  - what each file must do: signatures, behaviour, and the values pinned by SPEC.md and DECISIONS.md
  - the primary doc to read
  - a check that proves it's done
  Claude gives no code unless the user asks for a hint or a solution. Then Claude waits for "done" or "review".
- **Claude may still:** run read-only checks (tests, lint, CI status, `git diff`), review the user's diffs, open PRs when asked, and update CLAUDE.md, DECISIONS.md and memory.
- **The user writes every commit message**, one line in their own words, and runs the commits themselves.
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
- A draft of steps 1-3 exists under tag `archive/claude-draft-m1-steps-1-3`. Claude may read it to write better instructions, but never paste code from it unless the user asks for a solution.
