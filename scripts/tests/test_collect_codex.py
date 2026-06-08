import os
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

def test_system_skipped_and_plugin_cache_is_plugin(tmp_path):
    def w(p, c):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(c)
    cx = tmp_path / ".codex"
    w(f"{cx}/skills/.system/builtin/SKILL.md", "---\nname: builtin\ndescription: sys\n---\nb")
    w(f"{cx}/plugins/cache/foo/1.0/skills/pcache/SKILL.md", "---\nname: pcache\ndescription: pl\n---\nb")
    w(f"{cx}/config.toml", "")
    items = collect(str(cx))
    names = {i.name: i for i in items if i.kind == Kind.SKILL}
    assert "builtin" not in names                      # .system excluded
    assert names["pcache"].origin == Origin.PLUGIN and names["pcache"].enabled is True
