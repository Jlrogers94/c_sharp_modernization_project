from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    project TEXT,
    sha256 TEXT NOT NULL,
    loc INTEGER NOT NULL DEFAULT 0,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    target_framework TEXT,
    output_type TEXT,
    references_json TEXT NOT NULL DEFAULT '[]',
    packages_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    namespace TEXT,
    name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    signature TEXT,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    summary TEXT,
    UNIQUE(file_id, kind, full_name, start_line)
);
CREATE INDEX IF NOT EXISTS idx_symbols_full_name ON symbols(full_name);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);

CREATE TABLE IF NOT EXISTS references_graph (
    id INTEGER PRIMARY KEY,
    source_symbol_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
    source_file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    target_name TEXT NOT NULL,
    target_symbol_id INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
    reference_type TEXT NOT NULL,
    line INTEGER
);
CREATE INDEX IF NOT EXISTS idx_refs_target_name ON references_graph(target_name);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY,
    scope_type TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    summary TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scope_type, scope_key)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    task_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    target TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    priority INTEGER NOT NULL DEFAULT 100,
    attempts INTEGER NOT NULL DEFAULT 0,
    acceptance_criteria TEXT NOT NULL DEFAULT '',
    plan_json TEXT,
    blocked_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY,
    decision_key TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'accepted',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS functional_tests (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    test_type TEXT NOT NULL,
    framework TEXT NOT NULL DEFAULT 'TestComplete',
    raw_refs_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(path, name)
);

CREATE TABLE IF NOT EXISTS test_ui_objects (
    id INTEGER PRIMARY KEY,
    functional_test_id INTEGER REFERENCES functional_tests(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    mapped_object TEXT,
    UNIQUE(functional_test_id, alias)
);

CREATE TABLE IF NOT EXISTS test_feature_map (
    id INTEGER PRIMARY KEY,
    functional_test_id INTEGER NOT NULL REFERENCES functional_tests(id) ON DELETE CASCADE,
    feature TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    UNIQUE(functional_test_id, feature)
);

CREATE TABLE IF NOT EXISTS validation_runs (
    id INTEGER PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    command TEXT NOT NULL,
    success INTEGER NOT NULL,
    exit_code INTEGER,
    duration_ms INTEGER,
    output TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS code_fts USING fts5(
    path UNINDEXED,
    symbol,
    content,
    tokenize='unicode61'
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            self._conn.execute("BEGIN")
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        return cur

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return list(self._conn.execute(sql, params))

    def upsert_file(self, path: str, kind: str, project: str | None, sha256: str, loc: int, size_bytes: int) -> int:
        self._conn.execute(
            """INSERT INTO files(path,kind,project,sha256,loc,size_bytes)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(path) DO UPDATE SET kind=excluded.kind, project=excluded.project,
                 sha256=excluded.sha256, loc=excluded.loc, size_bytes=excluded.size_bytes,
                 updated_at=CURRENT_TIMESTAMP""",
            (path, kind, project, sha256, loc, size_bytes),
        )
        self._conn.commit()
        return int(self._conn.execute("SELECT id FROM files WHERE path=?", (path,)).fetchone()[0])

    def replace_symbols(self, file_id: int, symbols: Iterable[dict], references: Iterable[dict], source_text: str, path: str) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM references_graph WHERE source_file_id=?", (file_id,))
            conn.execute("DELETE FROM symbols WHERE file_id=?", (file_id,))
            conn.execute("DELETE FROM code_fts WHERE path=?", (path,))
            symbol_ids: dict[tuple[str, int], int] = {}
            for s in symbols:
                cur = conn.execute(
                    """INSERT INTO symbols(file_id,kind,namespace,name,full_name,signature,start_line,end_line)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (file_id, s["kind"], s.get("namespace"), s["name"], s["full_name"], s.get("signature"), s["start_line"], s["end_line"]),
                )
                symbol_ids[(s["full_name"], s["start_line"])] = int(cur.lastrowid)
                snippet = s.get("content", "")
                conn.execute("INSERT INTO code_fts(path,symbol,content) VALUES(?,?,?)", (path, s["full_name"], snippet))
            if not symbols:
                conn.execute("INSERT INTO code_fts(path,symbol,content) VALUES(?,?,?)", (path, "", source_text))
            for r in references:
                source_symbol_id = None
                key = r.get("source_symbol_key")
                if key:
                    source_symbol_id = symbol_ids.get(tuple(key))
                conn.execute(
                    """INSERT INTO references_graph(source_symbol_id,source_file_id,target_name,reference_type,line)
                       VALUES(?,?,?,?,?)""",
                    (source_symbol_id, file_id, r["target_name"], r.get("reference_type", "identifier"), r.get("line")),
                )

    def relink_references(self) -> None:
        # Keep this compatible with older SQLite builds that are common on locked-down
        # enterprise Python installations; avoid a correlated UPDATE dependency.
        refs = list(self._conn.execute("SELECT id,target_name FROM references_graph"))
        for ref in refs:
            target = self._conn.execute(
                """SELECT id FROM symbols
                   WHERE name=? OR full_name=?
                   ORDER BY CASE WHEN full_name=? THEN 0 ELSE 1 END, id
                   LIMIT 1""",
                (ref["target_name"], ref["target_name"], ref["target_name"]),
            ).fetchone()
            self._conn.execute(
                "UPDATE references_graph SET target_symbol_id=? WHERE id=?",
                (int(target[0]) if target else None, int(ref["id"])),
            )
        self._conn.commit()

    def search(self, query: str, limit: int = 20) -> list[sqlite3.Row]:
        try:
            return self.query(
                "SELECT path,symbol,snippet(code_fts,2,'[[',']]', '…', 24) AS snippet,bm25(code_fts) AS rank FROM code_fts WHERE code_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit),
            )
        except sqlite3.OperationalError:
            escaped = ' '.join(f'"{t}"' for t in query.split() if t.strip())
            return self.query(
                "SELECT path,symbol,snippet(code_fts,2,'[[',']]', '…', 24) AS snippet,bm25(code_fts) AS rank FROM code_fts WHERE code_fts MATCH ? ORDER BY rank LIMIT ?",
                (escaped, limit),
            )

    def stats(self) -> dict:
        tables = ["files", "projects", "symbols", "references_graph", "functional_tests", "tasks", "decisions"]
        return {t: int(self._conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for t in tables}

    def create_task(self, task_key: str, title: str, target: str | None, priority: int, acceptance_criteria: str) -> None:
        self.execute(
            """INSERT INTO tasks(task_key,title,target,priority,acceptance_criteria)
               VALUES(?,?,?,?,?)
               ON CONFLICT(task_key) DO UPDATE SET title=excluded.title,target=excluded.target,
                 priority=excluded.priority,acceptance_criteria=excluded.acceptance_criteria,updated_at=CURRENT_TIMESTAMP""",
            (task_key, title, target, priority, acceptance_criteria),
        )

    def get_task(self, task_key: str):
        rows = self.query("SELECT * FROM tasks WHERE task_key=?", (task_key,))
        return rows[0] if rows else None

    def next_task(self):
        rows = self.query("SELECT * FROM tasks WHERE status='PENDING' ORDER BY priority,id LIMIT 1")
        return rows[0] if rows else None

    def update_task(self, task_key: str, **fields) -> None:
        allowed = {"status", "attempts", "plan_json", "blocked_reason", "priority", "acceptance_criteria"}
        use = {k: v for k, v in fields.items() if k in allowed}
        if not use:
            return
        set_clause = ", ".join(f"{k}=?" for k in use) + ", updated_at=CURRENT_TIMESTAMP"
        self.execute(f"UPDATE tasks SET {set_clause} WHERE task_key=?", tuple(use.values()) + (task_key,))

    def add_validation_run(self, task_id: int | None, stage: str, command: str, success: bool, exit_code: int | None, duration_ms: int, output: str) -> None:
        self.execute(
            "INSERT INTO validation_runs(task_id,stage,command,success,exit_code,duration_ms,output) VALUES(?,?,?,?,?,?,?)",
            (task_id, stage, command, 1 if success else 0, exit_code, duration_ms, output[-100_000:]),
        )
