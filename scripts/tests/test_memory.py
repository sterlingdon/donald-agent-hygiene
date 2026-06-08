import time
from hygiene.memory import cross_file_duplicates
from hygiene.classify import classify
from hygiene.model import Item, Kind, Host, Origin, Severity


def _mem(path):
    return Item(Host.CLAUDE, Kind.MEMORY, "CLAUDE.md", Origin.USER_CONFIG, str(path), True)


def test_cross_file_duplicates_detects_shared_lines(tmp_path):
    a = tmp_path / "a.md"; a.write_text("- always run the linter before commit\n- unique line aaa here\n")
    b = tmp_path / "b.md"; b.write_text("# header\nalways run the linter before commit\n")
    c = tmp_path / "c.md"; c.write_text("totally different guidance only here\n")
    dups = cross_file_duplicates([_mem(a), _mem(b), _mem(c)])
    assert dups.get(str(a), 0) >= 1 and dups.get(str(b), 0) >= 1
    assert str(c) not in dups


def test_classify_flags_duplicated_memory_yellow(tmp_path):
    a = tmp_path / "a.md"; a.write_text("- shared instruction repeated across files\n")
    b = tmp_path / "b.md"; b.write_text("shared instruction repeated across files\n")
    items = [_mem(a), _mem(b)]
    findings = classify(items, {}, {}, time.time(), 90)
    sevs = {f.item.path: f.severity for f in findings}
    assert sevs[str(a)] == Severity.YELLOW
    assert any("duplicated" in r for f in findings for r in f.reasons)
