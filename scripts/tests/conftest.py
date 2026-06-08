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
    # M1 user MCP (lives in ~/.claude.json)
    _w(f"{h}/.claude.json", json.dumps({
        "mcpServers": {"playwright-extension": {"command": "npx"},
                       "Framelink Figma MCP": {"command": "npx"}},
    }))
    # M3 plugin-bundled MCP (enabled plugin 'superpowers' has none; add a fake enabled neon)
    _w(f"{h}/.claude/plugins/cache/off/neon/1.0.0/.mcp.json",
       json.dumps({"mcpServers": {"neon": {"command": "npx"}}}))
    # P1 enabledPlugins (lives in ~/.claude/settings.json)
    _w(f"{h}/.claude/settings.json", json.dumps({
        "enabledPlugins": {"superpowers@off": True, "playwright@off": False},
    }))
    _patch_enabled(h, "neon@off", True)
    # Codex: S5 active, S6 catalog, M4 mcp
    _w(f"{h}/.codex/skills/codexalpha/SKILL.md", "---\nname: codexalpha\ndescription: cx\n---\nb")
    _w(f"{h}/.codex/vendor_imports/skills/skills/.curated/sentry/SKILL.md",
       "---\nname: sentry\ndescription: cx curated\n---\nb")
    _w(f"{h}/.codex/config.toml", '[mcp_servers.node_repl]\ncommand = "node"\n')
    return h

def _patch_enabled(h, key, val):
    p = f"{h}/.claude/settings.json"
    with open(p) as f: data = json.load(f)
    data.setdefault("enabledPlugins", {})[key] = val
    with open(p, "w") as f: json.dump(data, f)
