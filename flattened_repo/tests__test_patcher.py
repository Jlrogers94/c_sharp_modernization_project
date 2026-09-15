from pathlib import Path
from modernizer_agent.patcher import SafePatcher


def test_replace_requires_unique_match(tmp_path: Path):
    (tmp_path / "a.cs").write_text("foo\nfoo\n", encoding="utf-8")
    p = SafePatcher(tmp_path, tmp_path / ".backups")
    result = p.validate([{"path":"a.cs","operation":"replace","old_text":"foo","new_text":"bar"}])
    assert not result.success


def test_apply_and_restore(tmp_path: Path):
    f = tmp_path / "a.cs"
    f.write_text("alpha beta", encoding="utf-8")
    p = SafePatcher(tmp_path, tmp_path / ".backups")
    changes = [{"path":"a.cs","operation":"replace","old_text":"beta","new_text":"gamma"}]
    result = p.apply(changes, "MIG-0001")
    assert result.success
    assert f.read_text() == "alpha gamma"
    p.restore("MIG-0001", ["a.cs"])
    assert f.read_text() == "alpha beta"
