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
    result = iso_to_epoch("2026-06-08T03:49:48.417Z")
    assert abs(result - 1780890588.417) < 1
    assert iso_to_epoch("garbage") is None
