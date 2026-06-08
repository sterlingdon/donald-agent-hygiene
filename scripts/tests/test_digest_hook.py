import json
from hygiene import state
from hygiene.cli import run
from hygiene.model import Item, Finding, Severity, Kind, Host, Origin


def _f(sev):
    it = Item(Host.CLAUDE, Kind.SKILL, "x", Origin.PERSONAL, "/p", True)
    return Finding(item=it, severity=sev, reasons=["r"])


def test_state_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    data = state.write_state(str(p), [_f(Severity.GREEN), _f(Severity.GREEN), _f(Severity.YELLOW)])
    assert data["green"] == 2 and data["yellow"] == 1
    back = state.read_state(str(p))
    assert back["green"] == 2 and "ts" in back


def test_digest_prints_counts(tmp_path, capsys):
    p = tmp_path / "state.json"
    state.write_state(str(p), [_f(Severity.GREEN), _f(Severity.YELLOW), _f(Severity.YELLOW)])
    rc = run(["digest", "--state", str(p)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "🟢1" in out and "🟡2" in out


def test_digest_no_state(tmp_path, capsys):
    rc = run(["digest", "--state", str(tmp_path / "missing.json")])
    assert rc == 0 and "no scan yet" in capsys.readouterr().out


def test_install_hook_dry_run_then_apply_idempotent(tmp_path, capsys):
    home = tmp_path
    (home / ".claude").mkdir()
    (home / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": {}}))
    # dry-run: no change
    run(["install-hook", "--home", str(home)])
    assert "DRY-RUN" in capsys.readouterr().out
    data = json.loads((home / ".claude" / "settings.json").read_text())
    assert "hooks" not in data or "SessionStart" not in data.get("hooks", {})
    # apply: installs
    run(["install-hook", "--home", str(home), "--apply"])
    data = json.loads((home / ".claude" / "settings.json").read_text())
    ss = data["hooks"]["SessionStart"]
    assert any("digest" in json.dumps(e) for e in ss)
    assert (home / ".claude" / "settings.json.hygiene-bak").exists()
    # idempotent: second apply doesn't duplicate
    run(["install-hook", "--home", str(home), "--apply"])
    data2 = json.loads((home / ".claude" / "settings.json").read_text())
    assert len(data2["hooks"]["SessionStart"]) == len(ss)
