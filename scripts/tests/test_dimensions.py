import json
from hygiene.collect_cc import collect
from hygiene.collect_codex import collect as collect_cx
from hygiene.model import Kind


def test_cc_hooks_and_memory(fake_home):
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
