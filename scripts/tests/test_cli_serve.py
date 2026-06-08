from hygiene.cli import run


def test_serve_probe_returns(fake_home, capsys):
    rc = run(["serve", "--home", str(fake_home), "--codex-home", str(fake_home / ".codex"),
              "--projects", str(fake_home / "p"), "--sessions", str(fake_home / "s"),
              "--cwd", str(fake_home / "noproject"), "--port", "0", "--probe"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "127.0.0.1" in out and "token=" in out
