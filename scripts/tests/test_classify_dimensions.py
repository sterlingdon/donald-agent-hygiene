import time
from hygiene.classify import classify
from hygiene.cost import estimate
from hygiene.model import Item, Kind, Host, Origin, Severity

NOW = time.time()


def test_big_memory_flagged_yellow(tmp_path):
    big = tmp_path / "CLAUDE.md"; big.write_text("x\n" * 400)
    it = Item(Host.CLAUDE, Kind.MEMORY, "CLAUDE.md", Origin.USER_CONFIG, str(big), True)
    estimate(it)                                   # pipeline always estimates before classify
    f = [x for x in classify([it], {}, {}, NOW, 90) if x.item is it][0]
    assert f.severity == Severity.YELLOW
    assert any("line" in r.lower() for r in f.reasons)


def test_small_memory_is_keep(tmp_path):
    small = tmp_path / "CLAUDE.md"; small.write_text("short\n")
    it = Item(Host.CLAUDE, Kind.MEMORY, "CLAUDE.md", Origin.USER_CONFIG, str(small), True)
    estimate(it)
    f = [x for x in classify([it], {}, {}, NOW, 90) if x.item is it][0]
    assert f.severity == Severity.KEEP


def test_hook_is_keep_not_green():
    it = Item(Host.CLAUDE, Kind.HOOK, "settings:PostToolUse", Origin.USER_CONFIG, "/s", True)
    f = [x for x in classify([it], {}, {}, NOW, 90) if x.item is it][0]
    assert f.severity != Severity.GREEN           # hooks never auto-cleanable
