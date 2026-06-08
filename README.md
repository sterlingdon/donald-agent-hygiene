# donald-agent-hygiene 🧹

Keep **Claude Code** and **Codex** in their healthiest state — audit every place they keep
**skills / MCP servers / hooks / memory** (including plugin-bundled ones), cross-reference
your **real usage** from session transcripts, and safely clean out the cruft you installed
but never use.

> We accumulate MCP servers and skills without noticing. Many are installed-but-unused —
> they bloat the context window, slow startup, and degrade tool selection. This tool finds
> them and helps you remove them, across **both** Claude Code and Codex, in one pass.

stdlib-only Python · no third-party runtime deps · 64 tests · scan is always read-only.

## What it does

- **Inventory** every source: personal / project / **plugin-bundled** skills, user / project / plugin MCP servers, hooks, and memory files — for Claude Code **and** Codex.
- **Usage** from `~/.claude/projects/**/*.jsonl` and `~/.codex/sessions/**` — counts how often each skill / MCP was actually invoked, and when last.
- **Classify** each item 🟢 safe-to-clean / 🟡 review / 🔴 caution / ✅ keep — flags never-used, stale, duplicate, overlapping clusters, high-cost-low-use MCP, disabled-plugins-on-disk, oversized memory files.
- **Report** as a self-contained interactive HTML page.
- **Clean** safely: `apply` (dry-run by default, `--apply` executes with automatic backup) or a local **one-click-execute** web server.

## Usage

```bash
cd scripts

# Read-only audit -> interactive HTML report
python -m hygiene.cli scan  --home "$HOME" --codex-home "$HOME/.codex" \
  --projects "$HOME/.claude/projects" --sessions "$HOME/.codex/sessions" \
  --cwd "$PWD" --out /tmp/report.html

# Preview cleanup (dry-run). Add --apply to execute (backs up first).
python -m hygiene.cli apply --home "$HOME" --codex-home "$HOME/.codex" \
  --projects "$HOME/.claude/projects" --sessions "$HOME/.codex/sessions" \
  --cwd "$PWD" --severity green

# Local server: click "execute" per item in the browser
python -m hygiene.cli serve --home "$HOME" --codex-home "$HOME/.codex" \
  --projects "$HOME/.claude/projects" --sessions "$HOME/.codex/sessions" \
  --cwd "$PWD" --port 8765

python -m pytest -q          # run from scripts/
```

## Safety

- **Scan is always read-only.** Cleanup defaults to dry-run; mutations require `--apply` (CLI) or a click (server).
- **Every mutation backs up first** to `~/.agent-hygiene-backups/`.
- The local server binds **127.0.0.1 only**, gates execution behind a random token, and asks for confirmation.
- **Codex `config.toml` is never auto-edited** (MCP removal is emitted as a `codex mcp remove` command).
- **Hooks and memory are never auto-cleaned**; Codex skills (whose usage signal is best-effort) are never auto-green.

## Layout

```
scripts/hygiene/   collect_cc, collect_codex, usage_cc, usage_codex, cost,
                   classify, report, actions, serve, cli, model, normalize, util, paths
scripts/tests/     pytest suite
docs/              research notes, design, and the M1/M2/M3 implementation plans
SKILL.md           agent-skill manifest (Claude Code / Codex)
```

## License

MIT
