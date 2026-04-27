# AGENTS.md

## What This Is

This is a generated `autocli` workspace. The parent `autocli` project generated this repository from captured HTTP traffic; this workspace is the editable product surface for turning those captures into a useful CLI.

## Repository Map

- `pyproject.toml`: package metadata, console script entry point, dependencies, and `[tool.autocli]` workspace settings.
- `commands/<command>/command.yaml`: generated command metadata and request mapping.
- `commands/<command>/fixtures/`: captured request/response cases used as evidence.
- `commands/<command>/processors/pre.py`: request-shaping hook for live execution.
- `commands/<command>/processors/post.py`: response-to-JSON hook for the CLI output contract.
- `commands/<command>/goldens/`: approved post-processed output contracts.
- `shared/`: workspace-local shared code for processors or command implementations.
- `www_rimi_ee/runtime.py`: workspace-local CLI runtime.
- `www_rimi_ee/testing.py`: workspace-local contract test helpers.
- `skills/build-cli/SKILL.md`: iterative workflow for developing this CLI with user feedback.

## Governing Principles

- Captured fixtures are evidence, not a complete product specification.
- Generated command IDs, argument names, and output shapes are raw material, not final product decisions.
- Prefer pragmatic fixes in this generated workspace before changing the parent generator.
- Keep workspace-specific runtime, testing, and processor changes inside this repository.
- Goldens must reflect intentionally approved post-processed JSON, not raw transport bodies.
- Keep output schemas explicit and stable once approved.
- If the response is HTML, parse it structurally when possible.
- Session-sensitive headers should come from the system keyring or the `PLAYWRIGHT_HEADERS_JSON` process environment override, not persisted fixtures.

## Working With This Workspace

- Use `skills/build-cli/SKILL.md` when the task is to improve, finish, or review the generated CLI.
- Use `processors/pre.py` only for request-shaping behavior needed by live execution.
- Use `processors/post.py` for the command's JSON output contract.
- Update goldens only when the output contract is intentionally changed.
- Stay inside this generated workspace unless there is a clear blocker that only the parent `autocli` generator can fix.

## Updating Live Session Headers

Authenticated commands need fresh browser-session headers stored in the system keyring.

- If headers are missing or stale, use Playwright to open `https://www.rimi.ee/` and ask the user to sign in when needed.
- Wait for a representative authenticated Rimi request, then call `await request.allHeaders()` in Playwright.
- Write `JSON.stringify({ headers })` to a temporary browser local-storage key such as `autocli.playwrightHeadersJson`.
- Persist the browser context to the workspace-local `.autocli-playwright-storage-state.json` path.
- Read that storage-state file locally, extract the temporary local-storage value, and pass it to `rimi auth store-headers` through stdin or `--file`.
- Do not print cookies, authorization headers, CSRF/XSRF tokens, or full `PLAYWRIGHT_HEADERS_JSON` values in the conversation or logs.
- Do not commit `.autocli-playwright-storage-state.json` or any captured private session values.
- Keep session-sensitive values in the system keyring; do not copy them into fixtures, goldens, `command.yaml`, README examples, or tests.

## Common Failure Modes

- Optional query/path/body args treated as required during fixture replay.
- Compressed response bodies not decoded before parsing.
- HTML or HTML-in-JSON responses handled with brittle string slicing.
- Generated `request_mapping` mismatches between args and fixture requests.
- Live-session headers not supplied correctly for authenticated requests.

## Useful Commands

- Install CLI tool: `uv tool install --editable .`
- CLI help: `rimi --help` or `python -m www_rimi_ee --help`
- Command help: `rimi <command path> --help`
- Contract tests: `uv run --extra dev python -m pytest -q commands/<command_id>/tests/test_command.py`
- Live authenticated runs can use the `PLAYWRIGHT_HEADERS_JSON` process environment override
