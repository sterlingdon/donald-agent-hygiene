from hygiene.cli import run


def _args(fake_home, extra):
    return (["apply", "--home", str(fake_home), "--codex-home", str(fake_home / ".codex"),
             "--projects", str(fake_home / "p"), "--sessions", str(fake_home / "s"),
             "--cwd", str(fake_home / "noproject"),
             "--backups", str(fake_home / "bk")] + extra)


def test_apply_dry_run_changes_nothing(fake_home):
    sd = fake_home / ".claude" / "skills" / "never-used"
    assert sd.exists()
    rc = run(_args(fake_home, ["--severity", "green"]))
    assert rc == 0 and sd.exists()          # dry-run default: nothing removed


def test_apply_executes_with_flag(fake_home):
    # an unused personal skill is now 🟡 (B), so clean it via --severity yellow
    sd = fake_home / ".claude" / "skills" / "never-used"
    rc = run(_args(fake_home, ["--severity", "yellow", "--apply"]))
    assert rc == 0 and not sd.exists()      # archived
    assert (fake_home / "bk").exists()      # backup created
