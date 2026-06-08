# donald-agent-hygiene M1 (skills + MCP cleanup) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stdlib-only Python CLI that scans every place Claude Code **and** Codex keep skills & MCP servers (including plugin-bundled ones), cross-references real usage from session transcripts, classifies each item 🟢/🟡/🔴, renders an interactive HTML report, and can safely clean (disable/uninstall/archive) with automatic backup.

**Architecture:** A `hygiene` Python package with one-responsibility modules: locate roots (`paths`) → build a unified `Item` inventory from all sources (`collect_cc`, `collect_codex`) → aggregate invocation counts/last-used from transcripts (`usage_cc`, `usage_codex`) → estimate context cost (`cost`) → apply classification rules (`classify`) → render report (`report`) or execute actions (`actions`), orchestrated by `cli`. Scan is always read-only; mutation only via `actions` with `--apply` + timestamped backup.

**Tech Stack:** Python 3.11+ (stdlib only: `json`, `glob`, `os`, `re`, `tomllib`, `html`, `shutil`, `datetime`, `argparse`, `http.server`), pytest. No third-party runtime deps.

---

## Case Coverage Matrix (the "cover all cases" contract)

Every row below maps to the task that implements it. Self-review (end of plan) re-checks this.

### Inventory-source cases
| # | Case | Host | Where | Task |
|---|---|---|---|---|
| S1 | Personal skills | CC | `~/.claude/skills/*/SKILL.md` | T6 |
| S2 | Project skills | CC | `<cwd>/.claude/skills/*/SKILL.md` | T6 |
| S3 | Plugin-bundled skills (ENABLED plugin) | CC | `~/.claude/plugins/cache/<mp>/<plugin>/<ver>/{skills,.claude/skills}/*/SKILL.md` | T6 |
| S4 | Catalog skills (available, NOT active) | CC | `~/.claude/plugins/marketplaces/**/SKILL.md` + cache of disabled plugins | T6 |
| S5 | Codex active skills | Codex | `~/.codex/skills/`, `~/.codex/superpowers/skills/` | T7 |
| S6 | Codex catalog/curated (available) | Codex | `~/.codex/vendor_imports/**/.curated/**/SKILL.md` | T7 |
| S7 | Codex legacy/tmp leftovers | Codex | `~/.codex/.tmp/legacy-*/**/SKILL.md` | T7 |
| M1 | User-level MCP | CC | `~/.claude.json` → `mcpServers` | T6 |
| M2 | Project MCP + enable flags | CC | `<cwd>/.mcp.json` + settings `enabled/disabledMcpjsonServers`, `enableAllProjectMcpServers` | T6 |
| M3 | Plugin-bundled MCP (ENABLED plugin) | CC | plugin `.mcp.json` | T6 |
| M4 | Codex MCP | Codex | `~/.codex/config.toml` → `[mcp_servers.*]` | T7 |
| P1 | Plugin enabled/disabled state | CC | `~/.claude.json` → `enabledPlugins` (`<plugin>@<mp>`→bool) | T6 |

### Detection cases (what makes something a cleanup candidate)
| # | Case | Rule | Task |
|---|---|---|---|
| D1 | Never used (active, 0 invocations ever) | 🟢 | T9 |
| D2 | Stale (used, but not within window N days) | 🟡 | T9 |
| D3 | Disabled-but-on-disk (disk bloat, no context cost) | 🟡 (archive) | T9 |
| D4 | Exact duplicate (same skill name in ≥2 active locations / shadowing) | 🟡 | T9 |
| D5 | Near-duplicate / overlap cluster (similar name or description) | 🟡 (review) | T9 |
| D6 | High-cost + low-use MCP | 🟡/🟢 | T9 |
| D7 | Actively used (recent) | KEEP (no action) | T9 |
| D8 | Core/safety item (write-scoped MCP, security skill) — never auto-green | 🔴 | T9 |
| D9 | Orphan usage (invoked in history, no longer installed) — informational | report-only | T9/T10 |
| D10 | Unmatched MCP usage (`mcp__x__` used, server not in any config, e.g. `ccd_session`) — informational | report-only | T9/T10 |

### Name-normalization cases (usage ↔ inventory matching)
| # | Case | Task |
|---|---|---|
| N1 | Skill usage name is `plugin:name` OR bare `name` | T2 |
| N2 | MCP usage `mcp__server__tool` → server, tolerant of spaces/case (`Framelink Figma MCP`) | T2 |
| N3 | Built-in tools (Bash/Read/Write/Edit/…) excluded from skill/MCP accounting | T4 |

---

## File Structure

```
scripts/
  pytest.ini
  hygiene/
    __init__.py        # package marker, __all__
    util.py            # read_frontmatter(), read_json(), read_toml(), iso->epoch
    model.py           # Enums + dataclasses: Item, Usage, Finding
    normalize.py       # skill_match_keys(), parse_mcp_tool(), norm_mcp_server()
    paths.py           # ClaudeRoots / CodexRoots dataclasses + locators
    usage_cc.py        # collect_usage() over ~/.claude/projects/**/*.jsonl
    usage_codex.py     # collect_usage() over ~/.codex/sessions/**/*.jsonl (best-effort)
    cost.py            # estimate(item) -> (est_tokens, cost_band)
    collect_cc.py      # collect() -> list[Item]  (S1-S4, M1-M3, P1)
    collect_codex.py   # collect() -> list[Item]  (S5-S7, M4)
    classify.py        # classify(items, usage_map, opts) -> list[Finding] (D1-D10)
    report.py          # render_html(findings, meta) -> str
    actions.py         # backup(), disable(), uninstall(), archive() — dry-run default
    cli.py             # argparse entrypoint: scan / report / apply
  tests/
    conftest.py        # fake_home fixture building a miniature CC+Codex tree
    fixtures/          # tiny sample transcripts
    test_normalize.py
    test_usage_cc.py
    test_collect_cc.py
    test_collect_codex.py
    test_cost.py
    test_classify.py
    test_report.py
    test_actions.py
    test_cli_smoke.py
```

Each module is small and independently testable. `collect_*` and `usage_*` take **root paths as arguments** (never hard-code `~`) so tests run against `tmp_path` fixtures and production passes real roots from `paths.py`.

---

## Task 0: Scaffold package + pytest

**Files:**
- Create: `scripts/hygiene/__init__.py`
- Create: `scripts/pytest.ini`
- Create: `scripts/tests/conftest.py`

- [ ] **Step 1: Create package marker**

`scripts/hygiene/__init__.py`:
```python
"""donald-agent-hygiene: audit & clean Claude Code / Codex skills & MCP servers."""
__all__ = ["model", "normalize", "paths", "usage_cc", "usage_codex",
           "cost", "collect_cc", "collect_codex", "classify", "report", "actions", "cli"]
```

- [ ] **Step 2: pytest config**

`scripts/pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -q
```

- [ ] **Step 3: conftest with a fake-home builder fixture**

`scripts/tests/conftest.py`:
```python
import json, os, textwrap
import pytest

def _w(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

@pytest.fixture
def fake_home(tmp_path):
    """A miniature ~/.claude + ~/.codex tree covering inventory cases S1-S7, M1-M4, P1."""
    h = tmp_path
    # S1 personal skills
    _w(f"{h}/.claude/skills/alpha/SKILL.md", "---\nname: alpha\ndescription: Alpha personal skill\n---\nbody")
    _w(f"{h}/.claude/skills/never-used/SKILL.md", "---\nname: never-used\ndescription: zombie\n---\nbody")
    # S3 plugin (enabled) skill
    _w(f"{h}/.claude/plugins/cache/off/superpowers/5.1.0/skills/brainstorming/SKILL.md",
       "---\nname: brainstorming\ndescription: ideation\n---\nbody")
    # S4 catalog skill (marketplace, not active)
    _w(f"{h}/.claude/plugins/marketplaces/anthropic-agent-skills/skills/pdf/SKILL.md",
       "---\nname: pdf\ndescription: pdf tools\n---\nbody")
    # M1 user MCP + P1 enabledPlugins  (live in ~/.claude.json)
    _w(f"{h}/.claude.json", json.dumps({
        "mcpServers": {"playwright-extension": {"command": "npx"},
                       "Framelink Figma MCP": {"command": "npx"}},
        "enabledPlugins": {"superpowers@off": True, "playwright@off": False},
    }))
    # M3 plugin-bundled MCP (enabled plugin 'superpowers' has none; add a fake enabled neon)
    _w(f"{h}/.claude/plugins/cache/off/neon/1.0.0/.mcp.json",
       json.dumps({"mcpServers": {"neon": {"command": "npx"}}}))
    _patch_enabled(h, "neon@off", True)
    # settings.json (no project mcp flags)
    _w(f"{h}/.claude/settings.json", json.dumps({}))
    # Codex: S5 active, S6 catalog, M4 mcp
    _w(f"{h}/.codex/skills/codexalpha/SKILL.md", "---\nname: codexalpha\ndescription: cx\n---\nb")
    _w(f"{h}/.codex/vendor_imports/skills/skills/.curated/sentry/SKILL.md",
       "---\nname: sentry\ndescription: cx curated\n---\nb")
    _w(f"{h}/.codex/config.toml", '[mcp_servers.node_repl]\ncommand = "node"\n')
    return h

def _patch_enabled(h, key, val):
    p = f"{h}/.claude.json"
    with open(p) as f: data = json.load(f)
    data["enabledPlugins"][key] = val
    with open(p, "w") as f: json.dump(data, f)
```

- [ ] **Step 4: Run to confirm collection works (no tests yet → 0 collected, exit 5 is ok)**

Run: `cd scripts && python -m pytest`
Expected: `no tests ran` (exit code 5). Confirms pytest + imports load.

- [ ] **Step 5: Commit**

```bash
cd /Users/liam/workspace/donald/1M/Agents/donald-agent-hygiene
git init -q 2>/dev/null; git add scripts/ && git commit -q -m "chore: scaffold hygiene package + pytest"
```

---

## Task 1: Data model (`model.py`)

**Files:**
- Create: `scripts/hygiene/model.py`
- Test: `scripts/tests/test_model.py`

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_model.py`:
```python
from hygiene.model import Item, Usage, Finding, Kind, Host, Origin, Severity

def test_item_defaults_and_mutability():
    it = Item(host=Host.CLAUDE, kind=Kind.SKILL, name="alpha",
              origin=Origin.PERSONAL, path="/x/SKILL.md", enabled=True)
    assert it.plugin is None and it.est_tokens == 0 and it.cost_band == "low"
    it.est_tokens = 42  # must be mutable (cost.py fills later)
    assert it.est_tokens == 42

def test_enum_values_are_strings():
    assert Severity.GREEN.value == "green"
    assert Kind.MCP.value == "mcp"

def test_finding_holds_reasons_list():
    it = Item(Host.CODEX, Kind.MCP, "neon", Origin.PLUGIN, "/p/.mcp.json", True)
    f = Finding(item=it, severity=Severity.YELLOW, reasons=["stale"])
    assert f.reasons == ["stale"] and f.usage is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_model.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'hygiene.model'`

- [ ] **Step 3: Implement**

`scripts/hygiene/model.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class Kind(str, Enum):
    SKILL = "skill"; MCP = "mcp"; PLUGIN = "plugin"

class Host(str, Enum):
    CLAUDE = "claude"; CODEX = "codex"

class Origin(str, Enum):
    PERSONAL = "personal"; PROJECT = "project"; PLUGIN = "plugin"
    CATALOG = "catalog"; USER_CONFIG = "user_config"

class Severity(str, Enum):
    GREEN = "green"; YELLOW = "yellow"; RED = "red"; KEEP = "keep"

@dataclass
class Item:
    host: Host
    kind: Kind
    name: str
    origin: Origin
    path: str
    enabled: bool
    plugin: Optional[str] = None
    description: str = ""
    est_tokens: int = 0
    cost_band: str = "low"            # low | med | high
    match_keys: frozenset = field(default_factory=frozenset)

@dataclass
class Usage:
    name: str
    count: int
    last_used: Optional[float]        # epoch seconds

@dataclass
class Finding:
    item: Item
    severity: Severity
    reasons: list                     # list[str]
    usage: Optional[Usage] = None
    suggested_cmd: Optional[str] = None
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_model.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/hygiene/model.py scripts/tests/test_model.py
git commit -q -m "feat(model): Item/Usage/Finding domain types"
```

---

## Task 2: Name normalization (`normalize.py`) — cases N1, N2

**Files:**
- Create: `scripts/hygiene/normalize.py`
- Test: `scripts/tests/test_normalize.py`

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_normalize.py`:
```python
from hygiene.normalize import skill_match_keys, parse_mcp_tool, norm_mcp_server

def test_skill_keys_plugin_namespaced():        # N1
    assert skill_match_keys("superpowers:brainstorming") == {"superpowers:brainstorming", "brainstorming"}

def test_skill_keys_bare():
    assert skill_match_keys("alpha") == {"alpha"}

def test_parse_mcp_tool():                        # N2
    assert parse_mcp_tool("mcp__playwright-extension__browser_click") == ("playwright-extension", "browser_click")
    assert parse_mcp_tool("Bash") is None
    assert parse_mcp_tool("mcp__noTool") is None

def test_norm_mcp_server_tolerates_space_and_case():   # N2 (Framelink Figma MCP)
    assert norm_mcp_server("Framelink Figma MCP") == norm_mcp_server("framelink_figma_mcp")
    assert norm_mcp_server("playwright-extension") == "playwrightextension"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_normalize.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`scripts/hygiene/normalize.py`:
```python
import re
from typing import Optional, Tuple

def skill_match_keys(name: str) -> set:
    """Keys a usage record might use to refer to this skill. N1."""
    name = (name or "").strip()
    keys = {name}
    if ":" in name:
        keys.add(name.split(":", 1)[1])
    return {k for k in keys if k}

def parse_mcp_tool(tool_full: str) -> Optional[Tuple[str, str]]:
    """'mcp__server__tool' -> ('server','tool'); None if not a 2-part mcp tool. N2."""
    if not isinstance(tool_full, str) or not tool_full.startswith("mcp__"):
        return None
    rest = tool_full[len("mcp__"):]
    server, sep, tool = rest.partition("__")
    if not server or not sep:
        return None
    return server, tool

def norm_mcp_server(raw: str) -> str:
    """Collapse to lowercase alphanumerics so config keys with spaces/case match
    the underscore-joined form seen in `mcp__...` usage. N2."""
    return re.sub(r"[^a-z0-9]", "", (raw or "").lower())
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_normalize.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/hygiene/normalize.py scripts/tests/test_normalize.py
git commit -q -m "feat(normalize): skill/mcp name matching (N1,N2)"
```

---

## Task 3: Filesystem utilities (`util.py`)

**Files:**
- Create: `scripts/hygiene/util.py`
- Test: `scripts/tests/test_util.py`

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_util.py`:
```python
from hygiene.util import read_frontmatter, read_json, iso_to_epoch

def test_read_frontmatter(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: foo\ndescription: Does a thing\n---\n# body\nmore")
    fm = read_frontmatter(str(p))
    assert fm["name"] == "foo"
    assert fm["description"] == "Does a thing"

def test_read_frontmatter_missing_fence(tmp_path):
    p = tmp_path / "SKILL.md"; p.write_text("no frontmatter here")
    assert read_frontmatter(str(p)) == {}

def test_read_json_bad(tmp_path):
    p = tmp_path / "x.json"; p.write_text("{not json")
    assert read_json(str(p)) == {}

def test_iso_to_epoch():
    assert iso_to_epoch("2026-06-08T03:49:48.417Z") == 1780890588.417
    assert iso_to_epoch("garbage") is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_util.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`scripts/hygiene/util.py`:
```python
import json, re
from datetime import datetime, timezone
from typing import Optional

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

_FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

def read_frontmatter(path: str) -> dict:
    """Parse the leading `--- ... ---` block; capture single-line name/description."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(8192)
    except OSError:
        return {}
    m = _FM.match(head)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out

def read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

def read_toml(path: str) -> dict:
    if tomllib is None:
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, Exception):  # tomllib.TOMLDecodeError subclasses Exception
        return {}

def iso_to_epoch(s: str) -> Optional[float]:
    try:
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp() \
            if "+" not in s else datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return None
```

> Note: the `iso_to_epoch` expected value `1780890588.417` in the test assumes UTC. If the engineer's local run differs, assert with `abs(... - 1780890588.417) < 1`. Keep it simple: compute via `datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()`.

- [ ] **Step 4: Implement-correct iso_to_epoch (replace body to the robust one)**

Replace `iso_to_epoch` with:
```python
def iso_to_epoch(s: str) -> Optional[float]:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, AttributeError):
        return None
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_util.py -q`
Expected: PASS (4 passed). If `test_iso_to_epoch` is off by timezone, relax it to `abs(diff) < 1`.

- [ ] **Step 6: Commit**

```bash
git add scripts/hygiene/util.py scripts/tests/test_util.py
git commit -q -m "feat(util): frontmatter/json/toml/time helpers"
```

---

## Task 4: Claude usage parser (`usage_cc.py`) — cases N3, D1/D2 inputs

**Files:**
- Create: `scripts/hygiene/usage_cc.py`
- Test: `scripts/tests/test_usage_cc.py`

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_usage_cc.py`:
```python
import json, os
from hygiene.usage_cc import collect_usage

def _rec(name, **inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}}

def test_counts_skills_mcps_and_ignores_builtins(tmp_path):
    proj = tmp_path / "projects" / "p1"
    proj.mkdir(parents=True)
    lines = [
        _rec("Skill", skill="tavily-search"),
        _rec("Skill", skill="tavily-search"),
        _rec("Skill", skill="superpowers:brainstorming"),
        _rec("mcp__playwright-extension__browser_click"),
        _rec("Bash", command="ls"),            # N3 builtin ignored
        {"type": "user", "message": {"content": "hi"}},  # non-assistant ignored
    ]
    (proj / "s.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
    skills, mcps = collect_usage(str(tmp_path / "projects"))
    assert skills["tavily-search"]["count"] == 2
    assert skills["superpowers:brainstorming"]["count"] == 1
    assert mcps["playwright-extension"]["count"] == 1
    assert "Bash" not in skills and "Bash" not in mcps

def test_malformed_lines_skipped(tmp_path):
    proj = tmp_path / "projects" / "p"; proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text('{bad\n' + json.dumps(_rec("Skill", skill="x")) + "\n")
    skills, _ = collect_usage(str(tmp_path / "projects"))
    assert skills["x"]["count"] == 1

def test_last_used_uses_record_ts(tmp_path):
    proj = tmp_path / "projects" / "p"; proj.mkdir(parents=True)
    r = _rec("Skill", skill="x"); r["timestamp"] = "2026-06-08T03:49:48.417Z"
    (proj / "s.jsonl").write_text(json.dumps(r))
    skills, _ = collect_usage(str(tmp_path / "projects"))
    assert skills["x"]["last"] is not None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_usage_cc.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`scripts/hygiene/usage_cc.py`:
```python
import glob, json, os
from collections import defaultdict
from typing import Dict, Tuple
from .normalize import parse_mcp_tool
from .util import iso_to_epoch

def _blank():
    return {"count": 0, "last": None}

def _bump(d, key, ts):
    e = d[key]
    e["count"] += 1
    if ts and (e["last"] is None or ts > e["last"]):
        e["last"] = ts

def _record_ts(rec):
    return iso_to_epoch(rec.get("timestamp", "")) if isinstance(rec.get("timestamp"), str) else None

def collect_usage(projects_root: str) -> Tuple[Dict, Dict]:
    """Aggregate skill + MCP-server invocation counts/last-used from CC transcripts.
    Returns (skills, mcps) each: name -> {'count', 'last'}. Builtins excluded (N3)."""
    skills = defaultdict(_blank)
    mcps = defaultdict(_blank)
    for fp in glob.glob(os.path.join(projects_root, "**", "*.jsonl"), recursive=True):
        try:
            fmtime = os.path.getmtime(fp)
        except OSError:
            continue
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("type") != "assistant":
                        continue
                    content = (rec.get("message") or {}).get("content")
                    if not isinstance(content, list):
                        continue
                    ts = _record_ts(rec) or fmtime
                    for b in content:
                        if not isinstance(b, dict) or b.get("type") != "tool_use":
                            continue
                        name = b.get("name")
                        if name == "Skill":
                            sk = (b.get("input") or {}).get("skill")
                            if sk:
                                _bump(skills, sk, ts)
                        elif isinstance(name, str) and name.startswith("mcp__"):
                            parsed = parse_mcp_tool(name)
                            if parsed:
                                _bump(mcps, parsed[0], ts)
        except OSError:
            continue
    return dict(skills), dict(mcps)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_usage_cc.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/hygiene/usage_cc.py scripts/tests/test_usage_cc.py
git commit -q -m "feat(usage_cc): aggregate skill/mcp invocations from transcripts"
```

---

## Task 5: Codex usage parser (`usage_codex.py`) — best-effort + discovery

**Files:**
- Create: `scripts/hygiene/usage_codex.py`
- Test: `scripts/tests/test_usage_codex.py`

**Context:** Codex session rollout files (`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`) are an event stream: `{"timestamp","type","payload":{...}}`. `history.jsonl` holds only user prompts. The exact event type for tool/MCP calls must be confirmed against real data (see Step 1 discovery). We parse defensively: any `event_msg` whose payload looks like a function/MCP/command call contributes a usage event; the call name is pulled from common field names.

- [ ] **Step 1: Discover real Codex event types (run against actual machine, read-only)**

Run:
```bash
find ~/.codex/sessions -name 'rollout-*.jsonl' -print0 | xargs -0 cat 2>/dev/null \
 | jq -r '.payload.type // .type' 2>/dev/null | sort | uniq -c | sort -rn | head -40
```
Record the distinct payload types. Map any of: `function_call`, `mcp_tool_call`, `exec_command_begin`, `tool_call`, `custom_tool_call` (or whatever appears) into the `CALL_TYPES`/`CALL_NAME_FIELDS` constants below before finalizing.

- [ ] **Step 2: Write the failing test**

`scripts/tests/test_usage_codex.py`:
```python
import json
from hygiene.usage_codex import collect_usage

def _ev(ptype, **payload):
    payload["type"] = ptype
    return {"timestamp": "2026-06-08T03:49:48.417Z", "type": "event_msg", "payload": payload}

def test_extracts_mcp_and_skill_calls(tmp_path):
    d = tmp_path / "sessions" / "2026" / "06" / "08"; d.mkdir(parents=True)
    lines = [
        {"timestamp": "x", "type": "session_meta", "payload": {"id": "s1"}},
        _ev("mcp_tool_call", server="neon", tool="run_sql"),
        _ev("function_call", name="codexalpha"),
        _ev("exec_command_begin", command="ls -la"),   # builtin-ish, ignored
    ]
    (d / "rollout-x.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
    skills, mcps = collect_usage(str(tmp_path / "sessions"))
    assert mcps["neon"]["count"] == 1
    assert skills["codexalpha"]["count"] == 1

def test_no_sessions_dir_is_empty(tmp_path):
    skills, mcps = collect_usage(str(tmp_path / "nope"))
    assert skills == {} and mcps == {}
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_usage_codex.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement**

`scripts/hygiene/usage_codex.py`:
```python
import glob, json, os
from collections import defaultdict
from typing import Dict, Tuple
from .util import iso_to_epoch

# Confirmed/expanded in Step 1 against real data:
MCP_CALL_TYPES = {"mcp_tool_call", "mcp_call"}
SKILL_CALL_TYPES = {"function_call", "tool_call", "custom_tool_call"}
SKILL_NAME_FIELDS = ("name", "skill", "tool")
MCP_SERVER_FIELDS = ("server", "server_name")

def _blank(): return {"count": 0, "last": None}

def _bump(d, key, ts):
    if not key: return
    e = d[key]; e["count"] += 1
    if ts and (e["last"] is None or ts > e["last"]):
        e["last"] = ts

def _first(payload, fields):
    for k in fields:
        v = payload.get(k)
        if isinstance(v, str) and v:
            return v
    return None

def collect_usage(sessions_root: str) -> Tuple[Dict, Dict]:
    skills = defaultdict(_blank); mcps = defaultdict(_blank)
    for fp in glob.glob(os.path.join(sessions_root, "**", "rollout-*.jsonl"), recursive=True):
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try: rec = json.loads(line)
                    except json.JSONDecodeError: continue
                    payload = rec.get("payload") or {}
                    if not isinstance(payload, dict): continue
                    ptype = payload.get("type")
                    ts = iso_to_epoch(rec.get("timestamp", "")) or None
                    if ptype in MCP_CALL_TYPES:
                        _bump(mcps, _first(payload, MCP_SERVER_FIELDS), ts)
                    elif ptype in SKILL_CALL_TYPES:
                        _bump(skills, _first(payload, SKILL_NAME_FIELDS), ts)
        except OSError:
            continue
    return dict(skills), dict(mcps)
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_usage_codex.py -q`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add scripts/hygiene/usage_codex.py scripts/tests/test_usage_codex.py
git commit -q -m "feat(usage_codex): best-effort tool/mcp usage from session rollouts"
```

---

## Task 6: Claude inventory collector (`collect_cc.py`) — S1-S4, M1-M3, P1

**Files:**
- Create: `scripts/hygiene/collect_cc.py`
- Test: `scripts/tests/test_collect_cc.py`

- [ ] **Step 1: Write the failing test (uses `fake_home` fixture)**

`scripts/tests/test_collect_cc.py`:
```python
from hygiene.collect_cc import collect
from hygiene.model import Kind, Origin

def _by_name(items, kind):
    return {i.name: i for i in items if i.kind == kind}

def test_skills_cover_personal_plugin_catalog(fake_home):
    items = collect(str(fake_home), cwd=str(fake_home / "noproject"))
    sk = _by_name(items, Kind.SKILL)
    assert sk["alpha"].origin == Origin.PERSONAL and sk["alpha"].enabled is True
    assert sk["never-used"].origin == Origin.PERSONAL
    # plugin skill from ENABLED plugin 'superpowers' -> active, namespaced name available
    bs = sk.get("brainstorming") or sk.get("superpowers:brainstorming")
    assert bs is not None and bs.origin == Origin.PLUGIN and bs.enabled is True
    # catalog skill (marketplace) present but NOT active
    assert sk["pdf"].origin == Origin.CATALOG and sk["pdf"].enabled is False

def test_mcp_user_and_plugin(fake_home):
    items = collect(str(fake_home), cwd=str(fake_home / "noproject"))
    mc = _by_name(items, Kind.MCP)
    assert mc["playwright-extension"].origin == Origin.USER_CONFIG
    assert mc["Framelink Figma MCP"].origin == Origin.USER_CONFIG
    assert mc["neon"].origin == Origin.PLUGIN and mc["neon"].enabled is True

def test_disabled_plugin_skills_not_active(fake_home, tmp_path):
    # add a skill under DISABLED plugin 'playwright@off' -> should be CATALOG/inactive
    import os
    p = f"{fake_home}/.claude/plugins/cache/off/playwright/1.0.0/skills/pw/SKILL.md"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write("---\nname: pw\ndescription: x\n---\nb")
    items = collect(str(fake_home), cwd=str(fake_home / "noproject"))
    pw = [i for i in items if i.name in ("pw", "playwright:pw")][0]
    assert pw.enabled is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_collect_cc.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`scripts/hygiene/collect_cc.py`:
```python
import glob, os
from typing import List, Set
from .model import Item, Kind, Host, Origin
from .util import read_frontmatter, read_json
from .normalize import skill_match_keys

def _skill_item(skill_dir: str, origin: Origin, enabled: bool, plugin=None, ns=None) -> Item:
    fm = read_frontmatter(os.path.join(skill_dir, "SKILL.md"))
    base = fm.get("name") or os.path.basename(skill_dir)
    name = f"{ns}:{base}" if ns else base
    return Item(host=Host.CLAUDE, kind=Kind.SKILL, name=name, origin=origin,
                path=skill_dir, enabled=enabled, plugin=plugin,
                description=fm.get("description", ""),
                match_keys=frozenset(skill_match_keys(name)))

def _enabled_plugins(home: str) -> dict:
    # CORRECTION (verified on real machine): enabledPlugins lives in
    # ~/.claude/settings.json, NOT ~/.claude.json (which holds mcpServers).
    data = read_json(os.path.join(home, ".claude/settings.json"))
    return data.get("enabledPlugins") or {}

def _plugin_id_from_cache_path(path: str) -> str:
    # .../plugins/cache/<marketplace>/<plugin>/<version>/...
    parts = path.split(os.sep)
    try:
        i = parts.index("cache")
        return f"{parts[i+2]}@{parts[i+1]}"   # <plugin>@<marketplace>
    except (ValueError, IndexError):
        return ""

def collect(home: str, cwd: str) -> List[Item]:
    items: List[Item] = []
    enabled = _enabled_plugins(home)

    # S1 personal skills
    for d in glob.glob(os.path.join(home, ".claude/skills/*/")):
        items.append(_skill_item(d.rstrip("/"), Origin.PERSONAL, True))

    # S2 project skills
    for d in glob.glob(os.path.join(cwd, ".claude/skills/*/")):
        items.append(_skill_item(d.rstrip("/"), Origin.PROJECT, True))

    # S3/S4 plugin cache skills (active only if owning plugin enabled)
    for md in glob.glob(os.path.join(home, ".claude/plugins/cache/**/SKILL.md"), recursive=True):
        sd = os.path.dirname(md)
        pid = _plugin_id_from_cache_path(md)         # e.g. superpowers@off
        ns = pid.split("@", 1)[0] if pid else None
        is_on = bool(enabled.get(pid, False))
        items.append(_skill_item(sd, Origin.PLUGIN if is_on else Origin.CATALOG,
                                 is_on, plugin=pid, ns=ns))

    # S4 marketplace catalog skills (browseable, never active)
    for md in glob.glob(os.path.join(home, ".claude/plugins/marketplaces/**/SKILL.md"), recursive=True):
        items.append(_skill_item(os.path.dirname(md), Origin.CATALOG, False))

    # M1 user MCP
    cj = read_json(os.path.join(home, ".claude.json"))
    for name in (cj.get("mcpServers") or {}):
        items.append(Item(Host.CLAUDE, Kind.MCP, name, Origin.USER_CONFIG,
                          os.path.join(home, ".claude.json"), True))

    # M2 project MCP
    proj_mcp = read_json(os.path.join(cwd, ".mcp.json")).get("mcpServers") or {}
    settings = read_json(os.path.join(home, ".claude/settings.json"))
    dis = set(settings.get("disabledMcpjsonServers") or [])
    ena = set(settings.get("enabledMcpjsonServers") or [])
    all_on = bool(settings.get("enableAllProjectMcpServers"))
    for name in proj_mcp:
        on = (all_on or name in ena) and name not in dis
        items.append(Item(Host.CLAUDE, Kind.MCP, name, Origin.PROJECT,
                          os.path.join(cwd, ".mcp.json"), on))

    # M3 plugin-bundled MCP (active only if owning plugin enabled)
    for mj in glob.glob(os.path.join(home, ".claude/plugins/cache/**/.mcp.json"), recursive=True):
        pid = _plugin_id_from_cache_path(mj)
        is_on = bool(enabled.get(pid, False))
        for name in (read_json(mj).get("mcpServers") or {}):
            items.append(Item(Host.CLAUDE, Kind.MCP, name, Origin.PLUGIN, mj, is_on, plugin=pid))

    # P1 plugins themselves
    for pid, on in enabled.items():
        items.append(Item(Host.CLAUDE, Kind.PLUGIN, pid, Origin.PLUGIN,
                          os.path.join(home, ".claude/plugins"), bool(on), plugin=pid))
    return items
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_collect_cc.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/hygiene/collect_cc.py scripts/tests/test_collect_cc.py
git commit -q -m "feat(collect_cc): unified CC inventory (skills/mcp/plugins, all origins)"
```

---

## Task 7: Codex inventory collector (`collect_codex.py`) — S5-S7, M4

**Files:**
- Create: `scripts/hygiene/collect_codex.py`
- Test: `scripts/tests/test_collect_codex.py`

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_collect_codex.py`:
```python
from hygiene.collect_codex import collect
from hygiene.model import Kind, Origin

def test_codex_skills_and_mcp(fake_home):
    items = collect(str(fake_home / ".codex"))
    sk = {i.name: i for i in items if i.kind == Kind.SKILL}
    mc = {i.name: i for i in items if i.kind == Kind.MCP}
    assert sk["codexalpha"].origin == Origin.PERSONAL and sk["codexalpha"].enabled is True
    assert sk["sentry"].origin == Origin.CATALOG and sk["sentry"].enabled is False   # curated
    assert mc["node_repl"].origin == Origin.USER_CONFIG

def test_missing_codex_dir(tmp_path):
    assert collect(str(tmp_path / "nope")) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_collect_codex.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`scripts/hygiene/collect_codex.py`:
```python
import glob, os
from typing import List
from .model import Item, Kind, Host, Origin
from .util import read_frontmatter, read_toml
from .normalize import skill_match_keys

# active skill roots vs catalog/cache/tmp (inactive)
def _origin_for(md_path: str) -> (Origin, bool):
    low = md_path.lower()
    if ".curated" in low or "vendor_imports" in low:
        return Origin.CATALOG, False
    if f"{os.sep}.tmp{os.sep}" in low or "legacy-" in low:
        return Origin.CATALOG, False
    return Origin.PERSONAL, True

def collect(codex_home: str) -> List[Item]:
    if not os.path.isdir(codex_home):
        return []
    items: List[Item] = []
    # S5/S6/S7 skills (skills/, superpowers/skills/, vendor_imports curated, .tmp legacy)
    for md in glob.glob(os.path.join(codex_home, "**", "SKILL.md"), recursive=True):
        sd = os.path.dirname(md)
        origin, enabled = _origin_for(md)
        fm = read_frontmatter(md)
        name = fm.get("name") or os.path.basename(sd)
        items.append(Item(Host.CODEX, Kind.SKILL, name, origin, sd, enabled,
                          description=fm.get("description", ""),
                          match_keys=frozenset(skill_match_keys(name))))
    # M4 MCP from config.toml
    cfg = read_toml(os.path.join(codex_home, "config.toml"))
    for name in (cfg.get("mcp_servers") or {}):
        items.append(Item(Host.CODEX, Kind.MCP, name, Origin.USER_CONFIG,
                          os.path.join(codex_home, "config.toml"), True))
    return items
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_collect_codex.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/hygiene/collect_codex.py scripts/tests/test_collect_codex.py
git commit -q -m "feat(collect_codex): Codex skills/mcp inventory (S5-S7,M4)"
```

---

## Task 8: Cost estimation (`cost.py`)

**Files:**
- Create: `scripts/hygiene/cost.py`
- Test: `scripts/tests/test_cost.py`

**Context:** Skills' always-loaded cost = metadata (name+description) ≈ `len/4` tokens. MCP exact schema tokens require a live connection, so we assign a coarse `cost_band` from a known-heavy lookup (github/playwright/figma/postgres/firecrawl = high) and leave precise measurement to the report's `/context` cross-check note.

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_cost.py`:
```python
from hygiene.cost import estimate
from hygiene.model import Item, Kind, Host, Origin

def _skill(desc):
    return Item(Host.CLAUDE, Kind.SKILL, "x", Origin.PERSONAL, "/p", True, description=desc)

def test_skill_tokens_from_metadata_len():
    it = _skill("a" * 200)
    estimate(it)
    assert it.est_tokens >= 50  # ~ (name+desc)/4

def test_mcp_band_known_heavy():
    it = Item(Host.CLAUDE, Kind.MCP, "Framelink Figma MCP", Origin.USER_CONFIG, "/p", True)
    estimate(it)
    assert it.cost_band == "high"

def test_mcp_band_default_med():
    it = Item(Host.CLAUDE, Kind.MCP, "obscure-thing", Origin.USER_CONFIG, "/p", True)
    estimate(it)
    assert it.cost_band == "med"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_cost.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`scripts/hygiene/cost.py`:
```python
from .model import Item, Kind
from .normalize import norm_mcp_server

_HEAVY = {"github", "playwright", "playwrightextension", "framelinkfigmamcp", "figma",
          "postgres", "firecrawl", "browser", "puppeteer", "supabase"}

def estimate(item: Item) -> Item:
    if item.kind == Kind.SKILL:
        item.est_tokens = (len(item.name) + len(item.description)) // 4
        item.cost_band = "low"
    elif item.kind == Kind.MCP:
        key = norm_mcp_server(item.name)
        item.cost_band = "high" if any(h in key for h in _HEAVY) else "med"
        item.est_tokens = {"high": 15000, "med": 3000, "low": 800}[item.cost_band]
    return item
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_cost.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/hygiene/cost.py scripts/tests/test_cost.py
git commit -q -m "feat(cost): skill metadata tokens + mcp cost bands"
```

---

## Task 9: Classification (`classify.py`) — D1-D10

**Files:**
- Create: `scripts/hygiene/classify.py`
- Test: `scripts/tests/test_classify.py`

**Context:** `classify(items, skill_usage, mcp_usage, now, window_days)` returns `Finding`s. Usage maps are name→{count,last}. Matching uses `item.match_keys` for skills and `norm_mcp_server` for MCP. Rules in priority order: KEEP (recent) → RED (core/safety) → GREEN (never-used active high-value) → YELLOW (stale / disabled-on-disk / duplicate / overlap / heavy-low-use). Catalog items (inactive, not on the active path) are reported as "available, not installed" and only flagged GREEN if they are *plugin cache for a disabled plugin taking disk* (D3).

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_classify.py`:
```python
from hygiene.classify import classify
from hygiene.model import Item, Kind, Host, Origin, Severity

NOW = 1_780_000_000.0
DAY = 86400

def _skill(name, origin=Origin.PERSONAL, enabled=True, keys=None, desc=""):
    from hygiene.normalize import skill_match_keys
    return Item(Host.CLAUDE, Kind.SKILL, name, origin, f"/p/{name}", enabled,
                description=desc, match_keys=frozenset(keys or skill_match_keys(name)))

def test_keep_when_recent():                       # D7
    it = _skill("alpha")
    f = _index(classify([it], {"alpha": {"count": 5, "last": NOW - DAY}}, {}, NOW, 90))["alpha"]
    assert f.severity == Severity.KEEP

def test_green_never_used_active():                # D1
    it = _skill("never-used")
    f = _index(classify([it], {}, {}, NOW, 90))["never-used"]
    assert f.severity == Severity.GREEN and "never used" in " ".join(f.reasons)

def test_yellow_stale():                           # D2
    it = _skill("alpha")
    f = _index(classify([it], {"alpha": {"count": 1, "last": NOW - 200 * DAY}}, {}, NOW, 90))["alpha"]
    assert f.severity == Severity.YELLOW and "stale" in " ".join(f.reasons)

def test_namespaced_usage_matches_plugin_skill():  # N1 end-to-end
    it = _skill("superpowers:brainstorming", origin=Origin.PLUGIN)
    f = _index(classify([it], {"superpowers:brainstorming": {"count": 3, "last": NOW}}, {}, NOW, 90))["superpowers:brainstorming"]
    assert f.severity == Severity.KEEP

def test_duplicate_active_names():                 # D4
    a = _skill("dup", origin=Origin.PERSONAL)
    b = _skill("dup", origin=Origin.PLUGIN)
    fs = classify([a, b], {}, {}, NOW, 90)
    dups = [f for f in fs if "duplicate" in " ".join(f.reasons)]
    assert len(dups) >= 1

def test_overlap_cluster():                        # D5
    items = [_skill("tavily-search"), _skill("tavily-research"), _skill("tavily-extract")]
    fs = classify(items, {}, {}, NOW, 90)
    assert any("overlap" in " ".join(f.reasons) for f in fs)

def test_disabled_plugin_skill_archivable():       # D3
    it = _skill("pw", origin=Origin.CATALOG, enabled=False)
    it.plugin = "playwright@off"
    f = _index(classify([it], {}, {}, NOW, 90))["pw"]
    assert f.severity in (Severity.YELLOW, Severity.GREEN)

def test_red_for_safety_mcp():                     # D8
    it = Item(Host.CLAUDE, Kind.MCP, "github", Origin.USER_CONFIG, "/p", True)
    it.cost_band = "high"
    f = _index(classify([it], {}, {"github": {"count": 0, "last": None}}, NOW, 90))["github"]
    assert f.severity in (Severity.YELLOW, Severity.RED)  # never auto-green for write-scoped

def test_orphan_and_unmatched_usage():             # D9, D10
    fs = classify([], {"ghost-skill": {"count": 2, "last": NOW}},
                  {"ccd_session": {"count": 9, "last": NOW}}, NOW, 90)
    reasons = " ".join(r for f in fs for r in f.reasons)
    assert "orphan" in reasons and "unmatched" in reasons

def _index(findings):
    return {f.item.name: f for f in findings if f.item is not None}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_classify.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`scripts/hygiene/classify.py`:
```python
import re
from collections import defaultdict
from typing import Dict, List, Optional
from .model import Item, Finding, Severity, Kind, Origin
from .normalize import norm_mcp_server

SAFETY_HINTS = ("github", "postgres", "supabase", "aws", "filesystem")  # write-capable / sensitive
SAFETY_SKILL_HINTS = ("security", "vetter", "git-commit")

def _match_usage(item: Item, skill_usage: Dict, mcp_usage: Dict) -> Optional[dict]:
    if item.kind == Kind.SKILL:
        for k in item.match_keys or {item.name}:
            if k in skill_usage:
                return skill_usage[k]
        return None
    if item.kind == Kind.MCP:
        nk = norm_mcp_server(item.name)
        for uname, rec in mcp_usage.items():
            if norm_mcp_server(uname) == nk:
                return rec
        return None
    return None

def _overlap_clusters(items: List[Item]) -> Dict[str, int]:
    """Map item.name -> cluster size for skills sharing a name prefix token (>=3 members)."""
    buckets = defaultdict(list)
    for it in items:
        if it.kind == Kind.SKILL and it.enabled:
            token = re.split(r"[-_:]", it.name)[0].lower()
            buckets[token].append(it.name)
    size = {}
    for token, names in buckets.items():
        if len(names) >= 3:
            for n in names:
                size[n] = len(names)
    return size

def classify(items, skill_usage, mcp_usage, now, window_days) -> List[Finding]:
    findings: List[Finding] = []
    window = window_days * 86400
    overlaps = _overlap_clusters(items)

    # duplicate detection: same name among ENABLED items
    name_counts = defaultdict(int)
    for it in items:
        if it.enabled and it.kind == Kind.SKILL:
            name_counts[it.name.split(":")[-1]] += 1

    matched_skill_keys, matched_mcp_keys = set(), set()

    for it in items:
        if it.kind == Kind.PLUGIN:
            continue
        rec = _match_usage(it, skill_usage, mcp_usage)
        reasons, sev, cmd = [], None, None
        recent = bool(rec and rec.get("last") and (now - rec["last"]) <= window)
        used_ever = bool(rec and rec.get("count"))

        if rec is not None:
            if it.kind == Kind.SKILL:
                matched_skill_keys |= set(it.match_keys or {it.name})
            else:
                matched_mcp_keys.add(norm_mcp_server(it.name))

        # D3 disabled / inactive-on-disk
        if not it.enabled:
            if it.origin == Origin.PLUGIN:   # disabled plugin's cached skill = disk bloat
                reasons.append("disabled plugin on disk (archive candidate)")
                sev = Severity.YELLOW
            else:
                reasons.append("catalog/available — not active")
                sev = Severity.KEEP
        else:
            is_safety = (it.kind == Kind.MCP and any(h in norm_mcp_server(it.name) for h in SAFETY_HINTS)) \
                        or (it.kind == Kind.SKILL and any(h in it.name.lower() for h in SAFETY_SKILL_HINTS))
            if recent:
                reasons.append("actively used"); sev = Severity.KEEP
            elif used_ever:
                reasons.append(f"stale (last use >{window_days}d ago)"); sev = Severity.YELLOW
            else:
                # never used
                if is_safety:
                    reasons.append("never used but write-scoped/safety — review manually")
                    sev = Severity.RED
                else:
                    reasons.append("never used")
                    sev = Severity.GREEN
            # D4 duplicate
            if it.kind == Kind.SKILL and name_counts.get(it.name.split(":")[-1], 0) > 1:
                reasons.append("duplicate name across locations")
                sev = Severity.YELLOW if sev == Severity.KEEP else sev
            # D5 overlap
            if it.name in overlaps:
                reasons.append(f"overlap cluster x{overlaps[it.name]}")
                if sev == Severity.KEEP:
                    sev = Severity.YELLOW
            # D6 heavy + not recent
            if it.kind == Kind.MCP and it.cost_band == "high" and not recent:
                reasons.append("high context cost, low use")
                if sev == Severity.KEEP:
                    sev = Severity.YELLOW

        usage_obj = None
        if rec:
            from .model import Usage
            usage_obj = Usage(name=it.name, count=rec.get("count", 0), last_used=rec.get("last"))
        findings.append(Finding(item=it, severity=sev or Severity.YELLOW,
                                reasons=reasons, usage=usage_obj))

    # D9 orphan skill usage (used but not installed)
    for uname, rec in skill_usage.items():
        if uname not in matched_skill_keys and uname.split(":")[-1] not in {k.split(":")[-1] for k in matched_skill_keys}:
            findings.append(_info_finding("skill", uname, f"orphan usage (invoked {rec.get('count')}x, not installed)"))
    # D10 unmatched MCP usage (used but no config)
    for uname, rec in mcp_usage.items():
        if norm_mcp_server(uname) not in matched_mcp_keys:
            findings.append(_info_finding("mcp", uname, f"unmatched usage (invoked {rec.get('count')}x, no config found)"))
    return findings

def _info_finding(kind, name, reason) -> Finding:
    it = Item(Host.CLAUDE if False else Host.CLAUDE, Kind.SKILL if kind == "skill" else Kind.MCP,
              name, Origin.USER_CONFIG, "(usage-only)", False)
    return Finding(item=it, severity=Severity.KEEP, reasons=[reason])
```

> Import `Host` at top of `_info_finding` usage: add `from .model import ... Host` to the module imports.

- [ ] **Step 4: Fix imports & run to verify it passes**

Ensure line 4 imports include `Host`:
```python
from .model import Item, Finding, Severity, Kind, Origin, Host, Usage
```
Run: `cd scripts && python -m pytest tests/test_classify.py -q`
Expected: PASS (9 passed). Adjust rule thresholds only if a specific assertion fails; do not weaken the safety (RED) rule.

- [ ] **Step 5: Commit**

```bash
git add scripts/hygiene/classify.py scripts/tests/test_classify.py
git commit -q -m "feat(classify): D1-D10 severity rules (unused/stale/dup/overlap/safety/orphan)"
```

---

## Task 10: Interactive HTML report (`report.py`)

**Files:**
- Create: `scripts/hygiene/report.py`
- Test: `scripts/tests/test_report.py`

**Context:** One self-contained HTML string (no external assets), modeled on the storage-analyzer pattern: a summary header, three collapsible sections (🟢/🟡/🔴) plus KEEP and info, each row showing host/kind/origin/usage/cost and a one-click-copy suggested command. All dynamic text passed through `html.escape`.

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_report.py`:
```python
from hygiene.report import render_html
from hygiene.model import Item, Finding, Severity, Kind, Host, Origin

def _f(name, sev, cmd=None):
    it = Item(Host.CLAUDE, Kind.SKILL, name, Origin.PERSONAL, "/p", True)
    return Finding(item=it, severity=sev, reasons=["never used"], suggested_cmd=cmd)

def test_html_has_sections_and_counts():
    html = render_html([_f("z1", Severity.GREEN), _f("z2", Severity.GREEN), _f("k", Severity.KEEP)],
                       meta={"host": "claude+codex", "generated": "2026-06-08"})
    assert "<html" in html and "🟢" in html
    assert "z1" in html and "z2" in html
    assert "2" in html  # green count

def test_escapes_html():
    html = render_html([_f("<script>", Severity.YELLOW)], meta={})
    assert "<script>" not in html.split("</head>")[-1] or "&lt;script&gt;" in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_report.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`scripts/hygiene/report.py`:
```python
import html as _html
from collections import Counter
from .model import Severity

_SEV = [(Severity.GREEN, "🟢 可直接清理"), (Severity.YELLOW, "🟡 需人工判断"),
        (Severity.RED, "🔴 谨慎处理"), (Severity.KEEP, "✅ 保留 / 信息")]

def _row(f):
    it = f.item
    cmd = _html.escape(f.suggested_cmd or "")
    u = f.usage.count if f.usage else 0
    return (f"<tr><td>{_html.escape(it.host.value)}</td><td>{_html.escape(it.kind.value)}</td>"
            f"<td>{_html.escape(it.name)}</td><td>{_html.escape(it.origin.value)}</td>"
            f"<td>{'on' if it.enabled else 'off'}</td><td>{u}</td>"
            f"<td>{_html.escape(it.cost_band)}</td>"
            f"<td>{_html.escape('; '.join(f.reasons))}</td>"
            f"<td><code onclick=\"navigator.clipboard.writeText(this.textContent)\">{cmd}</code></td></tr>")

def render_html(findings, meta) -> str:
    counts = Counter(f.severity for f in findings)
    head = ("<!doctype html><html lang='zh'><head><meta charset='utf-8'>"
            "<title>agent-hygiene report</title><style>"
            "body{font:14px/1.5 -apple-system,sans-serif;background:#0d1117;color:#e6edf3;margin:2rem}"
            "h1{font-size:1.4rem} details{margin:1rem 0;border:1px solid #30363d;border-radius:8px;padding:.5rem 1rem}"
            "summary{cursor:pointer;font-weight:600} table{width:100%;border-collapse:collapse;margin-top:.5rem}"
            "td,th{padding:.35rem .5rem;border-bottom:1px solid #21262d;text-align:left;font-size:13px}"
            "code{background:#161b22;padding:.1rem .3rem;border-radius:4px;cursor:copy;color:#7ee787}"
            ".g{color:#3fb950}.y{color:#d29922}.r{color:#f85149}</style></head><body>")
    summary = (f"<h1>🧹 Agent Hygiene 体检</h1>"
               f"<p>{_html.escape(str(meta.get('host','')))} · {_html.escape(str(meta.get('generated','')))}</p>"
               f"<p><span class='g'>🟢 {counts[Severity.GREEN]}</span> · "
               f"<span class='y'>🟡 {counts[Severity.YELLOW]}</span> · "
               f"<span class='r'>🔴 {counts[Severity.RED]}</span> · ✅ {counts[Severity.KEEP]}</p>")
    body = []
    for sev, label in _SEV:
        rows = [_row(f) for f in findings if f.severity == sev]
        if not rows:
            continue
        body.append(
            f"<details {'open' if sev in (Severity.GREEN, Severity.YELLOW) else ''}>"
            f"<summary>{label} ({len(rows)})</summary>"
            "<table><tr><th>host</th><th>kind</th><th>name</th><th>origin</th><th>on</th>"
            "<th>uses</th><th>cost</th><th>reasons</th><th>cmd</th></tr>"
            + "".join(rows) + "</table></details>")
    return head + summary + "".join(body) + "</body></html>"
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_report.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/hygiene/report.py scripts/tests/test_report.py
git commit -q -m "feat(report): self-contained interactive HTML report"
```

---

## Task 11: Safe actions (`actions.py`) — backup + disable/uninstall/archive

**Files:**
- Create: `scripts/hygiene/actions.py`
- Test: `scripts/tests/test_actions.py`

**Context:** Mutating helpers default to `dry_run=True` (return the command/plan, change nothing). With `dry_run=False` they first copy the target into a timestamped backup dir, then act. `suggest_command(finding)` produces the copy-paste command shown in the report.

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_actions.py`:
```python
import os, json
from hygiene.actions import backup_path, archive_skill, disable_mcp_user, suggest_command
from hygiene.model import Item, Finding, Severity, Kind, Host, Origin

def test_archive_skill_dry_run_changes_nothing(tmp_path):
    sd = tmp_path / "skills" / "z"; sd.mkdir(parents=True); (sd / "SKILL.md").write_text("x")
    plan = archive_skill(str(sd), backups=str(tmp_path / "bk"), dry_run=True)
    assert os.path.exists(sd) and "mv" in plan

def test_archive_skill_apply_moves_and_backs_up(tmp_path):
    sd = tmp_path / "skills" / "z"; sd.mkdir(parents=True); (sd / "SKILL.md").write_text("x")
    archive_skill(str(sd), backups=str(tmp_path / "bk"), dry_run=False)
    assert not os.path.exists(sd)                       # moved out of active path
    assert any("z" in p for p in os.listdir(tmp_path / "bk"))  # backup exists

def test_disable_mcp_user_apply_rewrites_json_with_backup(tmp_path):
    cj = tmp_path / ".claude.json"
    cj.write_text(json.dumps({"mcpServers": {"keep": {}, "drop": {}}}))
    disable_mcp_user(str(cj), "drop", backups=str(tmp_path / "bk"), dry_run=False)
    data = json.loads(cj.read_text())
    assert "drop" not in data["mcpServers"] and "keep" in data["mcpServers"]
    assert os.path.isdir(tmp_path / "bk")

def test_suggest_command_for_green_skill():
    it = Item(Host.CLAUDE, Kind.SKILL, "z", Origin.PERSONAL, "/p/z", True)
    cmd = suggest_command(Finding(item=it, severity=Severity.GREEN, reasons=["never used"]))
    assert "z" in cmd
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_actions.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`scripts/hygiene/actions.py`:
```python
import json, os, shutil
from datetime import datetime
from .model import Finding, Kind, Origin

def backup_path(backups: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    p = os.path.join(backups, stamp)
    os.makedirs(p, exist_ok=True)
    return p

def archive_skill(skill_dir: str, backups: str, dry_run: bool = True) -> str:
    dest = os.path.join(backup_path(backups), os.path.basename(skill_dir.rstrip("/")))
    plan = f"mv {skill_dir} {dest}"
    if dry_run:
        return plan
    shutil.copytree(skill_dir, dest, dirs_exist_ok=True)
    shutil.rmtree(skill_dir)
    return plan

def disable_mcp_user(claude_json: str, server: str, backups: str, dry_run: bool = True) -> str:
    plan = f"remove mcpServers['{server}'] from {claude_json}"
    if dry_run:
        return plan
    bk = backup_path(backups)
    shutil.copy2(claude_json, os.path.join(bk, os.path.basename(claude_json)))
    with open(claude_json) as f:
        data = json.load(f)
    (data.get("mcpServers") or {}).pop(server, None)
    with open(claude_json, "w") as f:
        json.dump(data, f, indent=2)
    return plan

def disable_plugin(claude_json: str, plugin_id: str, backups: str, dry_run: bool = True) -> str:
    plan = f"set enabledPlugins['{plugin_id}']=false in {claude_json}"
    if dry_run:
        return plan
    bk = backup_path(backups)
    shutil.copy2(claude_json, os.path.join(bk, os.path.basename(claude_json)))
    with open(claude_json) as f:
        data = json.load(f)
    data.setdefault("enabledPlugins", {})[plugin_id] = False
    with open(claude_json, "w") as f:
        json.dump(data, f, indent=2)
    return plan

def suggest_command(f: Finding) -> str:
    it = f.item
    if it.kind == Kind.SKILL and it.origin in (Origin.PERSONAL, Origin.PROJECT):
        return f"# archive unused skill\nmv '{it.path}' ~/.agent-hygiene-backups/"
    if it.kind == Kind.SKILL and it.origin in (Origin.PLUGIN, Origin.CATALOG) and it.plugin:
        return f"# disable owning plugin\nclaude  # then /plugin disable {it.plugin}"
    if it.kind == Kind.MCP and it.origin == Origin.USER_CONFIG and it.host.value == "claude":
        return f"claude mcp remove '{it.name}'"
    if it.kind == Kind.MCP and it.host.value == "codex":
        return f"codex mcp remove '{it.name}'"
    return f"# review: {it.name}"
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_actions.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/hygiene/actions.py scripts/tests/test_actions.py
git commit -q -m "feat(actions): dry-run-default disable/archive/uninstall with backup"
```

---

## Task 12: CLI orchestration (`cli.py`) + paths (`paths.py`)

**Files:**
- Create: `scripts/hygiene/paths.py`
- Create: `scripts/hygiene/cli.py`
- Test: `scripts/tests/test_cli_smoke.py`

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_cli_smoke.py`:
```python
import os
from hygiene.cli import run

def test_run_scan_writes_html(fake_home, tmp_path):
    out = tmp_path / "report.html"
    rc = run(["scan", "--home", str(fake_home), "--codex-home", str(fake_home / ".codex"),
              "--projects", str(fake_home / ".claude" / "projects"),
              "--sessions", str(fake_home / ".codex" / "sessions"),
              "--cwd", str(fake_home / "noproject"), "--out", str(out)])
    assert rc == 0 and out.exists()
    text = out.read_text()
    assert "Agent Hygiene" in text
    # never-used personal skill should be flagged green somewhere
    assert "never-used" in text

def test_apply_requires_flag(fake_home, tmp_path):
    rc = run(["scan", "--home", str(fake_home), "--codex-home", str(fake_home / ".codex"),
              "--projects", str(fake_home / "p"), "--sessions", str(fake_home / "s"),
              "--cwd", str(fake_home), "--out", str(tmp_path / "r.html")])
    assert rc == 0  # scan never mutates
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts && python -m pytest tests/test_cli_smoke.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `paths.py`**

`scripts/hygiene/paths.py`:
```python
import os

def default_home() -> str:
    return os.path.expanduser("~")

def cc_projects(home: str) -> str:
    return os.path.join(home, ".claude", "projects")

def codex_home(home: str) -> str:
    return os.path.join(home, ".codex")

def codex_sessions(home: str) -> str:
    return os.path.join(home, ".codex", "sessions")
```

- [ ] **Step 4: Implement `cli.py`**

`scripts/hygiene/cli.py`:
```python
import argparse, time, sys
from . import collect_cc, collect_codex, usage_cc, usage_codex, cost, classify, report, actions

def run(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hygiene")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--home", required=True)
    s.add_argument("--codex-home", required=True)
    s.add_argument("--projects", required=True)
    s.add_argument("--sessions", required=True)
    s.add_argument("--cwd", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--window-days", type=int, default=90)
    args = ap.parse_args(argv)

    items = collect_cc.collect(args.home, cwd=args.cwd) + collect_codex.collect(args.codex_home)
    for it in items:
        cost.estimate(it)
    sk1, mc1 = usage_cc.collect_usage(args.projects)
    sk2, mc2 = usage_codex.collect_usage(args.sessions)
    skills = _merge(sk1, sk2); mcps = _merge(mc1, mc2)

    findings = classify.classify(items, skills, mcps, now=time.time(), window_days=args.window_days)
    for f in findings:
        f.suggested_cmd = actions.suggest_command(f)
    html = report.render_html(findings, meta={
        "host": "claude+codex", "generated": time.strftime("%Y-%m-%d %H:%M")})
    with open(args.out, "w", encoding="utf-8") as fp:
        fp.write(html)
    print(f"wrote {args.out}  ({len(findings)} findings)")
    return 0

def _merge(a, b):
    out = dict(a)
    for k, v in b.items():
        if k in out:
            out[k] = {"count": out[k]["count"] + v["count"],
                      "last": max(filter(None, [out[k]["last"], v["last"]]), default=None)}
        else:
            out[k] = v
    return out

def main():
    sys.exit(run())

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd scripts && python -m pytest tests/test_cli_smoke.py -q`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add scripts/hygiene/paths.py scripts/hygiene/cli.py scripts/tests/test_cli_smoke.py
git commit -q -m "feat(cli): scan pipeline -> interactive HTML report"
```

---

## Task 13: Real-machine read-only smoke run + SKILL.md wiring

**Files:**
- Modify: `SKILL.md` (replace "待 M1 实现" status, add Usage section)
- Create: `scripts/run_hygiene.sh` (convenience wrapper with real default paths)

- [ ] **Step 1: Create the wrapper**

`scripts/run_hygiene.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
HOME_DIR="${HOME}"
OUT="${1:-/tmp/agent-hygiene-report.html}"
cd "$(dirname "$0")"
python -m hygiene.cli scan \
  --home "$HOME_DIR" \
  --codex-home "$HOME_DIR/.codex" \
  --projects "$HOME_DIR/.claude/projects" \
  --sessions "$HOME_DIR/.codex/sessions" \
  --cwd "$PWD" \
  --out "$OUT"
echo "open $OUT"
```

- [ ] **Step 2: Run the full suite**

Run: `cd scripts && python -m pytest -q`
Expected: PASS (all tasks' tests green)

- [ ] **Step 3: Real read-only run against the actual machine**

Run: `cd scripts && chmod +x run_hygiene.sh && ./run_hygiene.sh /tmp/agent-hygiene-report.html`
Expected: prints `wrote /tmp/...` with a finding count. Open the HTML; verify it lists the ~21 never-used personal skills and `Framelink Figma MCP` (0 uses) under 🟢/🟡, and the heavily-used skills (tavily-search, brainstorming, donald-git-commit) under ✅ KEEP. **Nothing on disk is modified.**

- [ ] **Step 4: Update SKILL.md status + Usage**

Replace the status line and append a Usage section:
```markdown
> ✅ **状态：M1 已实现（只读体检 + HTML 报告，含安全处置器，dry-run 默认）**。

## 使用

```bash
# 只读体检 → 交互式 HTML 报告（绝不改配置）
scripts/run_hygiene.sh /tmp/agent-hygiene-report.html
```

处置（M1 提供安全执行器，默认 dry-run）：报告里每行给出可复制命令；
真正执行用 `python -m hygiene.cli` 的处置子命令（M2 接线），改写前自动备份到 `~/.agent-hygiene-backups/`。
```

- [ ] **Step 5: Commit**

```bash
git add scripts/run_hygiene.sh SKILL.md
git commit -q -m "feat: real-machine read-only run wrapper + SKILL.md M1 status"
```

---

## Self-Review

**1. Spec coverage** — every Case Coverage Matrix row maps to a task:
- S1-S4, M1-M3, P1 → Task 6 (`collect_cc`) + tests.
- S5-S7, M4 → Task 7 (`collect_codex`) + tests.
- N1-N3 → Task 2 (`normalize`) + Task 4 (`usage_cc` excludes builtins).
- D1-D10 → Task 9 (`classify`) + tests (`test_classify.py` asserts each rule).
- Usage extraction (CC validated, Codex best-effort+discovery) → Tasks 4, 5.
- Interactive HTML report → Task 10. Safe executor w/ backup → Task 11. Orchestration + real run → Tasks 12, 13.

**2. Placeholder scan** — no "TBD/TODO/handle edge cases": the one genuine unknown (Codex event-type names) is handled by a concrete discovery step (Task 5 Step 1) that prints real types, with defensive constants the engineer fills from observed output, plus working defaults and tests. Not a placeholder — a verify-against-real-data step.

**3. Type consistency** — `Item`, `Usage`, `Finding`, the enums (`Kind/Host/Origin/Severity`), `collect_usage()->(skills,mcps)` dict shape `{count,last}`, `classify(items, skill_usage, mcp_usage, now, window_days)`, `render_html(findings, meta)`, `estimate(item)`, and `actions.*(...,backups,dry_run)` signatures are used identically across Tasks 1-13. `classify.py` imports must include `Host` and `Usage` (noted in Task 9 Step 4).

**Known follow-ups (NOT in M1, by design):** hooks & memory dimensions (M-next), `/context`-based exact MCP token measurement, the report's "run-a-local-server-to-execute" button (M2 wires `actions` to an `http.server` endpoint), and confirming Codex's active-skill root (Task 5/7 treat curated/tmp as CATALOG which is the safe default).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-08-m1-skills-mcp-hygiene.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
