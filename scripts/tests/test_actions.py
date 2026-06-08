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
    # backup is nested under a timestamp dir: bk/<stamp>/z/SKILL.md
    backed = [d for _, dirs, _ in os.walk(str(tmp_path / "bk")) for d in dirs]
    assert "z" in backed                               # backup copy exists


def test_archive_symlinked_skill_unlinks_only(tmp_path):
    real = tmp_path / "real" / "design"; real.mkdir(parents=True); (real / "SKILL.md").write_text("x")
    link = tmp_path / "skills" / "design"; link.parent.mkdir(parents=True)
    os.symlink(str(real), str(link))
    plan = archive_skill(str(link), backups=str(tmp_path / "bk"), dry_run=False)
    assert not os.path.lexists(link)            # symlink removed
    assert (real / "SKILL.md").exists()         # plugin-owned target untouched
    assert "unlink" in plan.lower()


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
