# donald-agent-hygiene M2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Builds directly on the verified M1 package (`scripts/hygiene/*`). Steps use `- [ ]` checkboxes.

**Goal:** Turn the M1 read-only auditor into a tool that actually cleans — add an `apply` CLI subcommand that executes the suggested cleanup (archive skill / remove MCP / disable plugin) with dry-run default + automatic backup — and extend inventory/classification to the **hooks** and **memory** dimensions.

**Architecture:** Two segments. **A (apply layer):** a pure `actions.execute(finding, backups, dry_run)` router returning an `ActionResult`, plus a `cli apply` subcommand that rebuilds findings (same pipeline as `scan`), filters by severity+kind, and runs each action. Codex `config.toml` is NOT auto-edited (no safe stdlib TOML writer) — Codex MCP removal is emitted as a command only. **B (dimensions):** add `Kind.HOOK` / `Kind.MEMORY`, collect them in `collect_cc`/`collect_codex`, and classify by size/staleness (never usage — hooks/memory always load), so they surface as 🟡 (too big / stale) but never auto-🟢.

**Tech Stack:** same as M1 — Python 3.11+ stdlib only, pytest. Run pytest ONLY from `scripts/`.

---

## Case Coverage (M2)

| # | Case | Segment | Task |
|---|---|---|---|
| AP1 | Archive an unused CC personal/project skill (move to backup) | A | A1/A2 |
| AP2 | Remove an unused CC user-config MCP from `~/.claude.json` (backup first) | A | A1/A2 |
| AP3 | Disable an unused/disabled CC plugin via `settings.json` enabledPlugins | A | A1/A2 |
| AP4 | Codex skill archive (move dir) | A | A1 |
| AP5 | Codex MCP → command-only (no auto-edit of config.toml) | A | A1 |
| AP6 | Dry-run by default; `--apply` required to mutate; every mutation backs up first | A | A1/A2 |
| AP7 | Never mutate KEEP/RED items; only act on selected severities (default 🟢) | A | A2 |
| HK1 | CC user hooks (`~/.claude/settings.json` `hooks`) | B | B1 |
| HK2 | CC plugin-bundled hooks (enabled plugins' `hooks/hooks.json`) | B | B1 |
| HK3 | Codex hooks (`~/.codex/config.toml` hooks) | B | B1 |
| ME1 | CC memory: `~/.claude/CLAUDE.md`, project `CLAUDE.md`, memory store dir | B | B1 |
| ME2 | Codex memory: `~/.codex/AGENTS.md`, `memories/`, `rules/` | B | B1 |
| CL1 | Classify hooks/memory by size (oversized CLAUDE.md) / presence, never auto-green | B | B2 |

---

## Task A1: Action router (`actions.execute`)

**Files:**
- Modify: `scripts/hygiene/model.py` (add `ActionResult`)
- Modify: `scripts/hygiene/actions.py` (add `execute`)
- Test: `scripts/tests/test_actions_execute.py`

- [ ] **Step 1: Add `ActionResult` to model.py**

Append to `scripts/hygiene/model.py`:
```python
@dataclass
class ActionResult:
    kind: str            # archive_skill | remove_user_mcp | disable_plugin | command_only | skip
    target: str          # path or name acted on
    command: str         # human-readable description / shell command
    applied: bool        # True if a mutation actually happened
    backup: str = ""     # backup dir/file if any
```

- [ ] **Step 2: Write the failing test**

`scripts/tests/test_actions_execute.py`:
```python
import os, json
from hygiene.actions import execute
from hygiene.model import Item, Finding, Severity, Kind, Host, Origin

def _find(it, sev=Severity.GREEN):
    return Finding(item=it, severity=sev, reasons=["never used"])

def test_archive_cc_personal_skill_apply(tmp_path):
    sd = tmp_path / "skills" / "z"; sd.mkdir(parents=True); (sd / "SKILL.md").write_text("x")
    it = Item(Host.CLAUDE, Kind.SKILL, "z", Origin.PERSONAL, str(sd), True)
    r = execute(_find(it), backups=str(tmp_path / "bk"), dry_run=False)
    assert r.kind == "archive_skill" and r.applied and not os.path.exists(sd) and r.backup

def test_archive_dry_run_noop(tmp_path):
    sd = tmp_path / "skills" / "z"; sd.mkdir(parents=True); (sd / "SKILL.md").write_text("x")
    it = Item(Host.CLAUDE, Kind.SKILL, "z", Origin.PERSONAL, str(sd), True)
    r = execute(_find(it), backups=str(tmp_path / "bk"), dry_run=True)
    assert r.applied is False and os.path.exists(sd)

def test_remove_user_mcp_apply(tmp_path):
    cj = tmp_path / ".claude.json"; cj.write_text(json.dumps({"mcpServers": {"drop": {}, "keep": {}}}))
    it = Item(Host.CLAUDE, Kind.MCP, "drop", Origin.USER_CONFIG, str(cj), True)
    r = execute(_find(it), backups=str(tmp_path / "bk"), dry_run=False)
    assert r.kind == "remove_user_mcp" and r.applied
    assert "drop" not in json.loads(cj.read_text())["mcpServers"]

def test_codex_mcp_is_command_only(tmp_path):
    it = Item(Host.CODEX, Kind.MCP, "node_repl", Origin.USER_CONFIG, str(tmp_path/"config.toml"), True)
    r = execute(_find(it), backups=str(tmp_path / "bk"), dry_run=False)
    assert r.kind == "command_only" and r.applied is False and "codex mcp remove" in r.command

def test_disable_plugin_apply(tmp_path):
    st = tmp_path / ".claude" / "settings.json"; st.parent.mkdir(parents=True)
    st.write_text(json.dumps({"enabledPlugins": {"foo@mp": True}}))
    it = Item(Host.CLAUDE, Kind.SKILL, "s", Origin.PLUGIN, "/p", False, plugin="foo@mp")
    r = execute(_find(it, Severity.YELLOW), backups=str(tmp_path / "bk"),
                dry_run=False, home=str(tmp_path))
    assert r.kind == "disable_plugin" and r.applied
    assert json.loads(st.read_text())["enabledPlugins"]["foo@mp"] is False
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_actions_execute.py -q`
Expected: FAIL (ImportError: cannot import name 'execute')

- [ ] **Step 4: Implement `execute` in actions.py**

Append to `scripts/hygiene/actions.py` (uses existing `archive_skill`, `disable_mcp_user`, `disable_plugin`, `backup_path`):
```python
import os as _os
from .model import ActionResult, Kind, Origin, Host


def execute(finding, backups, dry_run=True, home=None):
    it = finding.item
    home = home or _os.path.expanduser("~")
    # CC / Codex personal/project skill -> archive the directory
    if it.kind == Kind.SKILL and it.origin in (Origin.PERSONAL, Origin.PROJECT):
        cmd = archive_skill(it.path, backups=backups, dry_run=True)
        if dry_run:
            return ActionResult("archive_skill", it.path, cmd, False)
        dest_parent = backup_path(backups)
        dest = _os.path.join(dest_parent, _os.path.basename(it.path.rstrip("/")))
        shutil.copytree(it.path, dest, dirs_exist_ok=True)
        shutil.rmtree(it.path)
        return ActionResult("archive_skill", it.path, cmd, True, dest_parent)
    # CC user-config MCP -> remove from ~/.claude.json
    if it.kind == Kind.MCP and it.origin == Origin.USER_CONFIG and it.host == Host.CLAUDE:
        claude_json = _os.path.join(home, ".claude.json")
        target = it.path if _os.path.basename(it.path) == ".claude.json" else claude_json
        cmd = f"claude mcp remove '{it.name}'  (edits {target})"
        if dry_run:
            return ActionResult("remove_user_mcp", it.name, cmd, False)
        disable_mcp_user(target, it.name, backups=backups, dry_run=False)
        return ActionResult("remove_user_mcp", it.name, cmd, True, backups)
    # Codex MCP -> command only (no safe stdlib TOML writer)
    if it.kind == Kind.MCP and it.host == Host.CODEX:
        return ActionResult("command_only", it.name, f"codex mcp remove '{it.name}'", False)
    # plugin-owned item -> disable the whole plugin via settings.json
    if it.plugin:
        settings = _os.path.join(home, ".claude/settings.json")
        cmd = f"disable plugin {it.plugin} in {settings}"
        if dry_run:
            return ActionResult("disable_plugin", it.plugin, cmd, False)
        disable_plugin(settings, it.plugin, backups=backups, dry_run=False)
        return ActionResult("disable_plugin", it.plugin, cmd, True, backups)
    return ActionResult("skip", it.name, f"# no automatic action for {it.name}", False)
```
Add `import shutil` at top of actions.py if not already imported (it is, from M1).

- [ ] **Step 5: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_actions_execute.py -q` then `python -m pytest -q`
Expected: PASS (5 new + all prior)

- [ ] **Step 6: Commit**

```bash
git add scripts/hygiene/model.py scripts/hygiene/actions.py scripts/tests/test_actions_execute.py
git -c user.name=donald -c user.email=lab42crypto@gmail.com commit -m "feat(actions): execute() router (archive/remove-mcp/disable-plugin), dry-run default"
```

---

## Task A2: `apply` CLI subcommand

**Files:**
- Modify: `scripts/hygiene/cli.py` (add `apply` subcommand + shared `_build_findings`)
- Test: `scripts/tests/test_cli_apply.py`

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_cli_apply.py`:
```python
import os
from hygiene.cli import run

def _args(fake_home, extra):
    return (["apply", "--home", str(fake_home), "--codex-home", str(fake_home / ".codex"),
             "--projects", str(fake_home / "p"), "--sessions", str(fake_home / "s"),
             "--cwd", str(fake_home / "noproject"),
             "--backups", str(fake_home / "bk")] + extra)

def test_apply_dry_run_changes_nothing(fake_home):
    # 'never-used' personal skill dir exists in fixture
    sd = fake_home / ".claude" / "skills" / "never-used"
    assert sd.exists()
    rc = run(_args(fake_home, ["--severity", "green"]))
    assert rc == 0 and sd.exists()          # dry-run default: nothing removed

def test_apply_executes_with_flag(fake_home):
    sd = fake_home / ".claude" / "skills" / "never-used"
    rc = run(_args(fake_home, ["--severity", "green", "--apply"]))
    assert rc == 0 and not sd.exists()      # archived
    assert (fake_home / "bk").exists()      # backup created
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_cli_apply.py -q`
Expected: FAIL (apply subcommand unknown / SystemExit)

- [ ] **Step 3: Refactor `run` to share pipeline + add `apply`**

In `scripts/hygiene/cli.py`, extract the findings pipeline used by `scan` into a helper and add the `apply` subparser:
```python
def _build_findings(home, codex_home, projects, sessions, cwd, window_days):
    items = collect_cc.collect(home, cwd=cwd) + collect_codex.collect(codex_home)
    items = _dedup(items)
    for it in items:
        cost.estimate(it)
    sk1, mc1 = usage_cc.collect_usage(projects)
    sk2, mc2 = usage_codex.collect_usage(sessions)
    skills = _merge(sk1, sk2); mcps = _merge(mc1, mc2)
    findings = classify.classify(items, skills, mcps, now=time.time(), window_days=window_days)
    for f in findings:
        f.suggested_cmd = actions.suggest_command(f)
    return findings
```
Replace the body of the `scan` branch to call `_build_findings(...)` then render. Add the `apply` subparser with args: `--home --codex-home --projects --sessions --cwd` (required), `--backups` (default `~/.agent-hygiene-backups`), `--severity` (default `green`, choices green/yellow), `--kinds` (default `skill,mcp`), `--window-days` (default 90), `--apply` (store_true). The apply handler:
```python
        findings = _build_findings(a.home, a.codex_home, a.projects, a.sessions, a.cwd, a.window_days)
        want_sev = a.severity
        want_kinds = set(a.kinds.split(","))
        selected = [f for f in findings
                    if f.severity.value == want_sev and f.item.kind.value in want_kinds]
        applied = 0
        for f in selected:
            r = actions.execute(f, backups=a.backups, dry_run=not a.apply, home=a.home)
            tag = "APPLIED" if r.applied else ("DRY-RUN" if not a.apply else r.kind)
            print(f"[{tag}] {r.kind:14s} {f.item.host.value}/{f.item.kind.value} {f.item.name} :: {r.command}")
            applied += int(r.applied)
        print(f"{'APPLIED' if a.apply else 'DRY-RUN'}: {len(selected)} selected, {applied} mutated"
              + ("" if a.apply else "  (re-run with --apply to execute)"))
        return 0
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_cli_apply.py -q` then `python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Real-machine DRY-RUN check (must NOT mutate)**

Run:
```bash
cd scripts && python -m hygiene.cli apply --home "$HOME" --codex-home "$HOME/.codex" \
  --projects "$HOME/.claude/projects" --sessions "$HOME/.codex/sessions" \
  --cwd "$PWD" --severity green | tail -15
```
Expected: lines prefixed `[DRY-RUN]`, ending `DRY-RUN: N selected, 0 mutated`. Verify `ls ~/.claude/skills | wc -l` is unchanged (49).

- [ ] **Step 6: Commit**

```bash
git add scripts/hygiene/cli.py scripts/tests/test_cli_apply.py
git -c user.name=donald -c user.email=lab42crypto@gmail.com commit -m "feat(cli): apply subcommand (dry-run default, --apply executes with backup)"
```

---

## Task B1: hooks + memory inventory

**Files:**
- Modify: `scripts/hygiene/model.py` (add `Kind.HOOK`, `Kind.MEMORY`)
- Modify: `scripts/hygiene/collect_cc.py` (+`collect_hooks_memory`)
- Modify: `scripts/hygiene/collect_codex.py` (+ hooks/memory)
- Test: `scripts/tests/test_dimensions.py`

- [ ] **Step 1: Add enum members**

In `model.py`, extend `Kind`:
```python
class Kind(str, Enum):
    SKILL = "skill"; MCP = "mcp"; PLUGIN = "plugin"; HOOK = "hook"; MEMORY = "memory"
```

- [ ] **Step 2: Write the failing test**

`scripts/tests/test_dimensions.py`:
```python
import json, os
from hygiene.collect_cc import collect
from hygiene.collect_codex import collect as collect_cx
from hygiene.model import Kind

def test_cc_hooks_and_memory(fake_home):
    # add a user hook + a big CLAUDE.md
    st = json.loads((fake_home / ".claude" / "settings.json").read_text())
    st["hooks"] = {"PostToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "echo hi"}]}]}
    (fake_home / ".claude" / "settings.json").write_text(json.dumps(st))
    (fake_home / ".claude" / "CLAUDE.md").write_text("# big\n" + "x\n" * 300)
    items = collect(str(fake_home), cwd=str(fake_home / "noproject"))
    hooks = [i for i in items if i.kind == Kind.HOOK]
    mem = [i for i in items if i.kind == Kind.MEMORY]
    assert any("PostToolUse" in h.name for h in hooks)
    assert any(m.path.endswith("CLAUDE.md") for m in mem)

def test_codex_memory(fake_home):
    (fake_home / ".codex" / "AGENTS.md").write_text("agents")
    items = collect_cx(str(fake_home / ".codex"))
    assert any(i.kind == Kind.MEMORY and i.path.endswith("AGENTS.md") for i in items)
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_dimensions.py -q`
Expected: FAIL

- [ ] **Step 4: Implement collectors**

In `collect_cc.py`, after the existing inventory in `collect()`, append hook + memory items (and add helper). Hooks from `~/.claude/settings.json` `hooks` (one Item per event name) and enabled-plugin `hooks/hooks.json`; memory from `~/.claude/CLAUDE.md`, project `CLAUDE.md`, and the memory store dir if present:
```python
    settings_path = os.path.join(home, ".claude/settings.json")
    hooks = (read_json(settings_path).get("hooks") or {})
    for event in hooks:
        items.append(Item(Host.CLAUDE, Kind.HOOK, f"settings:{event}", Origin.USER_CONFIG,
                          settings_path, True))
    for hj in glob.glob(os.path.join(home, ".claude/plugins/cache/**/hooks/hooks.json"), recursive=True):
        pid = _plugin_id_from_cache_path(hj)
        items.append(Item(Host.CLAUDE, Kind.HOOK, f"plugin:{pid}", Origin.PLUGIN, hj,
                          bool(_enabled_plugins(home).get(pid, False)), plugin=pid))
    for md in [os.path.join(home, ".claude/CLAUDE.md"), os.path.join(cwd, "CLAUDE.md")]:
        if os.path.isfile(md):
            items.append(Item(Host.CLAUDE, Kind.MEMORY, os.path.basename(md), Origin.USER_CONFIG, md, True))
```
In `collect_codex.py`, append AGENTS.md + memories/rules as memory items, and config.toml hooks if present:
```python
    for name in ("AGENTS.md", "memories", "rules"):
        p = os.path.join(codex_home, name)
        if os.path.exists(p):
            items.append(Item(Host.CODEX, Kind.MEMORY, name, Origin.USER_CONFIG, p, True))
    if (cfg.get("hooks")):
        items.append(Item(Host.CODEX, Kind.HOOK, "config.toml:hooks", Origin.USER_CONFIG,
                          os.path.join(codex_home, "config.toml"), True))
```
(`cfg` already read for MCP in collect_codex.)

- [ ] **Step 5: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_dimensions.py -q` then `python -m pytest -q`
Expected: PASS (existing tests unaffected — they filter by kind)

- [ ] **Step 6: Commit**

```bash
git add scripts/hygiene/model.py scripts/hygiene/collect_cc.py scripts/hygiene/collect_codex.py scripts/tests/test_dimensions.py
git -c user.name=donald -c user.email=lab42crypto@gmail.com commit -m "feat(collect): hooks + memory inventory (CC + Codex)"
```

---

## Task B2: classify + cost for hooks/memory

**Files:**
- Modify: `scripts/hygiene/cost.py` (size for memory files)
- Modify: `scripts/hygiene/classify.py` (hooks/memory branch — size/staleness, never auto-green)
- Test: `scripts/tests/test_classify_dimensions.py`

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_classify_dimensions.py`:
```python
import time
from hygiene.classify import classify
from hygiene.model import Item, Kind, Host, Origin, Severity

NOW = time.time()

def test_big_memory_flagged_yellow(tmp_path):
    big = tmp_path / "CLAUDE.md"; big.write_text("x\n" * 400)
    it = Item(Host.CLAUDE, Kind.MEMORY, "CLAUDE.md", Origin.USER_CONFIG, str(big), True)
    f = [x for x in classify([it], {}, {}, NOW, 90) if x.item is it][0]
    assert f.severity in (Severity.YELLOW, Severity.KEEP)
    assert any("line" in r.lower() or "big" in r.lower() or "keep" in r.lower() for r in f.reasons)

def test_hook_is_keep_not_green(tmp_path):
    it = Item(Host.CLAUDE, Kind.HOOK, "settings:PostToolUse", Origin.USER_CONFIG, "/s", True)
    f = [x for x in classify([it], {}, {}, NOW, 90) if x.item is it][0]
    assert f.severity != Severity.GREEN   # hooks never auto-cleanable
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_classify_dimensions.py -q`
Expected: FAIL (hooks/memory currently fall through usage logic)

- [ ] **Step 3: Implement**

In `cost.py`, add a memory branch (count lines):
```python
    elif item.kind.value == "memory":
        try:
            with open(item.path, "r", encoding="utf-8", errors="replace") as f:
                item.est_tokens = sum(1 for _ in f)  # store line count in est_tokens
        except (OSError, IsADirectoryError):
            item.est_tokens = 0
        item.cost_band = "high" if item.est_tokens > 200 else "low"
```
In `classify.py`, at the TOP of the per-item loop (right after `if it.kind == Kind.PLUGIN: continue`), short-circuit hooks/memory before the usage logic:
```python
        if it.kind in (Kind.HOOK, Kind.MEMORY):
            reasons = []
            sev = Severity.KEEP
            if it.kind == Kind.MEMORY and it.cost_band == "high":
                reasons.append(f"large memory file (~{it.est_tokens} lines) — consider trimming/splitting")
                sev = Severity.YELLOW
            else:
                reasons.append("always-loaded — review manually" if it.kind == Kind.HOOK
                               else "memory file")
            findings.append(Finding(item=it, severity=sev, reasons=reasons))
            continue
```
(Ensure `Kind` is already imported in classify.py — it is from M1.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_classify_dimensions.py -q` then `python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Real-machine read-only run (now includes hooks/memory)**

Run `scripts/run_hygiene.sh /tmp/ah.html` and confirm the report still generates and now contains rows with kind `hook` / `memory`. Verify configs unchanged (read-only).

- [ ] **Step 6: Commit**

```bash
git add scripts/hygiene/cost.py scripts/hygiene/classify.py scripts/tests/test_classify_dimensions.py
git -c user.name=donald -c user.email=lab42crypto@gmail.com commit -m "feat(classify): hooks/memory severity (size/always-loaded, never auto-green)"
```

---

## Self-Review
- AP1-AP7 → Tasks A1/A2 (+ real-machine dry-run safety check A2 Step 5).
- HK1-HK3, ME1-ME2 → Task B1. CL1 → Task B2.
- Safety invariants preserved from M1: scan/apply default to read-only/dry-run; every mutation backs up first; Codex config.toml never auto-edited; hooks/memory never auto-green.
- Type consistency: `ActionResult` fields, `execute(finding, backups, dry_run, home)`, `_build_findings(...)`, new `Kind.HOOK/MEMORY` used consistently across A1→B2.

## Execution
Implement A1 → A2 → B1 → B2 in order (each builds on the previous). After B2, run the full suite + a real-machine dry-run, then offer finishing-a-development-branch.
