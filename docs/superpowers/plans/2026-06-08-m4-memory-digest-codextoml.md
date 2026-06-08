# donald-agent-hygiene M4 Implementation Plan

> Builds on M1–M3. Inline TDD. Run pytest from `scripts/`. stdlib only.

**Goal:** Three rounding-out features:
- **A. Memory cross-file duplicate detection** — flag the same instruction repeated across CLAUDE.md / AGENTS.md / memory files.
- **B. `digest` + installable periodic hook** — a fast one-line health summary backed by a cache file, plus an `install-hook` command that wires a SessionStart hook (backup + dry-run default).
- **C. Codex MCP real removal** — a safe line-based TOML table remover so `apply` can actually remove a Codex `[mcp_servers.X]` (with backup), replacing M2's command-only behavior.

---

## Task A: memory cross-file duplicate detection

**Files:** Create `scripts/hygiene/memory.py`, `scripts/tests/test_memory.py`; modify `classify.py`.

- `memory.py`:
  - `_entries(path) -> set[str]`: normalized non-trivial lines (strip `-*# `, lowercase, len>=12, skip code fences); returns empty on OSError/IsADirectoryError.
  - `cross_file_duplicates(memory_items) -> dict[path,int]`: for each MEMORY item's path, count entries that also appear in ANY other memory item's file.
- `classify.py`: before the loop compute `mem_dups = memory.cross_file_duplicates([i for i in items if i.kind==Kind.MEMORY])`; in the hooks/memory branch, if `it.path in mem_dups`, append reason `"N entries duplicated in other memory files"` and set `Severity.YELLOW`.
- Tests: two memory files sharing ≥1 entry → both in the dup map with count≥1; a unique file → not in map; classify marks a duplicated memory YELLOW.

## Task B: `digest` + cache + `install-hook`

**Files:** modify `scripts/hygiene/cli.py`; create `scripts/hygiene/state.py`, `scripts/tests/test_digest_hook.py`.

- `state.py`:
  - `write_state(path, findings)`: dump `{green, yellow, red, ts}` JSON.
  - `read_state(path) -> dict|None`.
  - `default_state_path() -> ~/.agent-hygiene-state.json`.
- `cli scan`: after writing HTML, also `state.write_state(state.default_state_path(), findings)`.
- `cli digest`: read state; print one line e.g. `🧹 hygiene: 🟢43 🟡125 (checked 2h ago) — run 'hygiene serve' to clean`; if missing, print `no scan yet — run 'hygiene scan'`. Instant (no pipeline) so it is hook-safe. Returns 0.
- `cli install-hook`: write a `SessionStart` hook into `~/.claude/settings.json` that runs `python -m hygiene.cli digest`. Dry-run default (prints what it would add); `--apply` writes it (backup `settings.json` first; merge, don't clobber existing hooks). Idempotent (skip if already present).
- Tests: write_state/read_state round-trip; digest with a state file prints the counts; install-hook dry-run doesn't modify; `--apply` adds a SessionStart hook and is idempotent on a second run.

## Task C: Codex MCP real removal (safe TOML)

**Files:** modify `scripts/hygiene/actions.py`; modify `scripts/tests/test_actions_execute.py`; create `scripts/tests/test_toml_remove.py`.

- `actions.remove_toml_server(text, server) -> str`: line-based remover that drops the `[mcp_servers.<server>]` table and any `[mcp_servers.<server>.*]` sub-tables (a table runs from its `[` header to the next top-level `[` or EOF).
- `actions.remove_codex_mcp(config_path, server, backups, dry_run=True)`: backup then rewrite config.toml with the server removed.
- `actions.execute` Codex-MCP branch: dry_run → `ActionResult("remove_codex_mcp", name, cmd, False)`; apply → call `remove_codex_mcp(..., dry_run=False)` → applied True.
- Update the M2 `test_codex_mcp_is_command_only` to the new behavior (dry-run not-applied + a real apply that removes the server and leaves the file valid per `tomllib`).
- Tests (`test_toml_remove.py`): removing one of two servers leaves the other; sub-table `[mcp_servers.x.env]` also removed; result re-parses with `tomllib` and no longer contains the server.

## Self-Review
- Safety unchanged: scan read-only; apply/install-hook dry-run default + backup; server still 127.0.0.1+token.
- New mutation path (Codex TOML) backs up first and is validated by a `tomllib` reparse test.
- digest is cache-only (no slow pipeline) so the SessionStart hook never delays a session.
