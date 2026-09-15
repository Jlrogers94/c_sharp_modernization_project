from pathlib import Path
import time

from modernizer_agent.config import AgentConfig
from modernizer_agent.db import Database
from modernizer_agent.scanner import RepoScanner


def make_agent(tmp_path: Path, workers: int = 1):
    cfg = AgentConfig(repo_root=tmp_path, state_dir=tmp_path / ".modernizer", scan_workers=workers)
    db = Database(cfg.db_path)
    return cfg, db, RepoScanner(cfg, db)


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_second_scan_uses_metadata_fast_path(tmp_path):
    write(tmp_path / "A.cs", "namespace Demo; public class A { public void Run() {} }\n")
    cfg, db, scanner = make_agent(tmp_path)
    first = scanner.scan()
    second = scanner.scan()
    assert first["changed_files"] == 1
    assert second["changed_files"] == 0
    assert second["hashed_files"] == 0
    assert second["metadata_skipped_files"] == 1
    assert second["unchanged_files"] == 1
    db.close()


def test_edit_one_file_only_reindexes_that_file(tmp_path):
    write(tmp_path / "A.cs", "namespace Demo; public class A {}\n")
    write(tmp_path / "B.cs", "namespace Demo; public class B {}\n")
    cfg, db, scanner = make_agent(tmp_path)
    scanner.scan()
    time.sleep(0.002)
    write(tmp_path / "A.cs", "namespace Demo; public class A2 {}\n")
    result = scanner.scan()
    assert result["changed_files"] == 1
    assert result["unchanged_files"] == 1
    assert result["hashed_files"] == 1
    names = {r["name"] for r in db.query("SELECT name FROM symbols")}
    assert "A2" in names and "A" not in names and "B" in names
    db.close()


def test_delete_removes_file_symbols_fts_and_testcomplete_rows(tmp_path):
    write(tmp_path / "Gone.cs", "namespace Demo; public class Gone {}\n")
    write(tmp_path / "Order.js", "// TestComplete\nAliases.App.OrderForm.SaveButton.Click();\n")
    cfg, db, scanner = make_agent(tmp_path)
    scanner.scan()
    assert db.query("SELECT * FROM functional_tests WHERE path='Order.js'")
    (tmp_path / "Gone.cs").unlink()
    (tmp_path / "Order.js").unlink()
    result = scanner.scan()
    assert result["deleted_files"] == 2
    assert not db.query("SELECT * FROM files WHERE path IN ('Gone.cs','Order.js')")
    assert not db.query("SELECT * FROM symbols WHERE name='Gone'")
    assert not db.query("SELECT * FROM code_fts WHERE path IN ('Gone.cs','Order.js')")
    assert not db.query("SELECT * FROM functional_tests WHERE path='Order.js'")
    db.close()


def test_rename_leaves_no_stale_path_and_relinks_references(tmp_path):
    write(tmp_path / "Consumer.cs", "namespace Demo; public class Consumer { Service field; }\n")
    write(tmp_path / "Service.cs", "namespace Demo; public class Service {}\n")
    cfg, db, scanner = make_agent(tmp_path)
    scanner.scan()
    linked = db.query("SELECT target_symbol_id FROM references_graph WHERE target_name='Service'")
    assert linked and any(r["target_symbol_id"] is not None for r in linked)

    (tmp_path / "Service.cs").rename(tmp_path / "MovedService.cs")
    result = scanner.scan()
    assert result["deleted_files"] == 1
    assert not db.query("SELECT * FROM files WHERE path='Service.cs'")
    assert db.query("SELECT * FROM files WHERE path='MovedService.cs'")
    linked = db.query("SELECT target_symbol_id FROM references_graph WHERE target_name='Service'")
    assert linked and any(r["target_symbol_id"] is not None for r in linked)
    db.close()


def test_changed_target_name_nulls_old_links_without_full_relink(tmp_path):
    write(tmp_path / "Consumer.cs", "namespace Demo; public class Consumer { Service field; }\n")
    write(tmp_path / "Service.cs", "namespace Demo; public class Service {}\n")
    cfg, db, scanner = make_agent(tmp_path)
    scanner.scan()
    time.sleep(0.002)
    write(tmp_path / "Service.cs", "namespace Demo; public class Replacement {}\n")
    result = scanner.scan()
    assert result["changed_files"] == 1
    refs = db.query("SELECT target_symbol_id FROM references_graph WHERE target_name='Service'")
    assert refs and all(r["target_symbol_id"] is None for r in refs)
    total_refs = db.query("SELECT COUNT(*) AS n FROM references_graph")[0]["n"]
    assert result["relinked_references"] <= total_refs
    db.close()


def test_changed_testcomplete_file_replaces_old_test_names(tmp_path):
    tc = tmp_path / "Flow.tcKDTest"
    write(tc, '<Node Name="OldFlow" />\nAliases.App.SaveButton.Click();\n')
    cfg, db, scanner = make_agent(tmp_path)
    scanner.scan()
    assert db.query("SELECT * FROM functional_tests WHERE name='OldFlow'")
    time.sleep(0.002)
    write(tc, '<Node Name="NewFlow" />\nAliases.App.SaveButton.Click();\n')
    scanner.scan()
    assert not db.query("SELECT * FROM functional_tests WHERE name='OldFlow'")
    assert db.query("SELECT * FROM functional_tests WHERE name='NewFlow'")
    db.close()


def test_deleted_project_is_removed(tmp_path):
    proj = tmp_path / "Legacy.csproj"
    write(proj, '<Project><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>')
    cfg, db, scanner = make_agent(tmp_path)
    scanner.scan()
    assert db.query("SELECT * FROM projects WHERE path='Legacy.csproj'")
    proj.unlink()
    result = scanner.scan()
    assert result["deleted_projects"] == 1
    assert not db.query("SELECT * FROM projects WHERE path='Legacy.csproj'")
    db.close()


def test_parallel_prepare_keeps_deterministic_database_results(tmp_path):
    for i in range(20):
        write(tmp_path / f"C{i:02}.cs", f"namespace Demo; public class C{i:02} {{ public C{(i+1)%20:02} Next; }}\n")
    cfg, db, scanner = make_agent(tmp_path, workers=4)
    first = scanner.scan()
    snapshot1 = [
        (r["path"], r["full_name"])
        for r in db.query(
            "SELECT f.path,s.full_name FROM symbols s JOIN files f ON f.id=s.file_id ORDER BY f.path,s.full_name"
        )
    ]
    second = scanner.scan()
    snapshot2 = [
        (r["path"], r["full_name"])
        for r in db.query(
            "SELECT f.path,s.full_name FROM symbols s JOIN files f ON f.id=s.file_id ORDER BY f.path,s.full_name"
        )
    ]
    assert first["scan_workers"] == 4
    assert second["hashed_files"] == 0
    assert snapshot1 == snapshot2
    assert db.query("SELECT COUNT(*) AS n FROM scan_runs")[0]["n"] == 2
    db.close()


def test_existing_v01_database_is_migrated_with_mtime_column(tmp_path):
    import sqlite3

    path = tmp_path / "legacy-index.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, project TEXT, sha256 TEXT NOT NULL, loc INTEGER NOT NULL DEFAULT 0, size_bytes INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()
    db = Database(path)
    columns = {r["name"] for r in db.query("PRAGMA table_info(files)")}
    assert "mtime_ns" in columns
    db.close()
