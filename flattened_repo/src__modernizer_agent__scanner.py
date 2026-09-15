from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import threading
import time
import xml.etree.ElementTree as ET

from .config import AgentConfig
from .csharp import CSharpParser, ParseResult
from .db import Database
from .testcomplete import TESTCOMPLETE_EXTENSIONS, looks_like_testcomplete, parse_testcomplete_file

TEXT_EXTENSIONS = {".cs", ".csproj", ".sln", ".props", ".targets"} | TESTCOMPLETE_EXTENSIONS


@dataclass(slots=True)
class _PreparedFile:
    path: Path
    rel: str
    mtime_ns: int
    size_bytes: int
    digest: str
    text: str
    content_changed: bool
    parsed: ParseResult | None


class RepoScanner:
    def __init__(self, config: AgentConfig, db: Database, *, workers: int | None = None):
        self.config = config
        self.db = db
        self.workers = max(1, int(workers if workers is not None else getattr(config, "scan_workers", 1)))
        self._local = threading.local()

    def _excluded(self, path: Path) -> bool:
        rel_parts = path.relative_to(self.config.repo_root).parts
        return any(part in self.config.exclude_dirs for part in rel_parts)

    def _project_for(self, path: Path, projects: list[Path]) -> str | None:
        candidates = [p for p in projects if p.parent == path.parent or p.parent in path.parents]
        if not candidates:
            return None
        return str(max(candidates, key=lambda p: len(p.parts)).relative_to(self.config.repo_root)).replace("\\", "/")

    def _parser(self) -> CSharpParser:
        parser = getattr(self._local, "csharp_parser", None)
        if parser is None:
            parser = CSharpParser()
            self._local.csharp_parser = parser
        return parser

    def _prepare(self, item: tuple[Path, str, str | None, int, int]) -> _PreparedFile | None:
        path, rel, old_hash, mtime_ns, size_bytes = item
        try:
            raw = path.read_bytes()
        except OSError:
            return None
        digest = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8-sig", errors="replace")
        changed = old_hash != digest
        parsed = self._parser().parse(text) if changed and path.suffix == ".cs" else None
        return _PreparedFile(path, rel, mtime_ns, size_bytes, digest, text, changed, parsed)

    def scan(self) -> dict:
        total_start = time.perf_counter()
        root = self.config.repo_root

        discovery_start = time.perf_counter()
        paths = sorted(
            (p for p in root.rglob("*") if p.is_file() and not self._excluded(p) and p.suffix in TEXT_EXTENSIONS),
            key=lambda p: p.relative_to(root).as_posix(),
        )
        projects = [p for p in paths if p.suffix == ".csproj"]
        project_rels = {p.relative_to(root).as_posix() for p in projects}
        discovery_ms = int((time.perf_counter() - discovery_start) * 1000)

        known = self.db.indexed_files()
        current_rels = {p.relative_to(root).as_posix() for p in paths}
        stale_paths = sorted(set(known) - current_rels)
        affected_target_names: set[str] = set()
        if stale_paths:
            affected_target_names |= self.db.symbol_target_names([int(known[p]["id"]) for p in stale_paths])
        deleted_files = self.db.delete_indexed_files(stale_paths)
        deleted_projects = self.db.reconcile_projects(project_rels)

        unchanged = 0
        metadata_skipped = 0
        hash_unchanged = 0
        to_prepare: list[tuple[Path, str, str | None, int, int]] = []
        for path in paths:
            rel = path.relative_to(root).as_posix()
            try:
                stat = path.stat()
            except OSError:
                continue
            mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
            old = known.get(rel)
            if old and int(old["size_bytes"]) == stat.st_size and int(old["mtime_ns"]) == mtime_ns:
                unchanged += 1
                metadata_skipped += 1
                continue
            to_prepare.append((path, rel, old["sha256"] if old else None, mtime_ns, stat.st_size))

        content_start = time.perf_counter()
        workers = self.workers
        if workers == 1:
            prepared_results = [self._prepare(item) for item in to_prepare]
        else:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="modernizer-index") as pool:
                prepared_results = list(pool.map(self._prepare, to_prepare))
        read_errors = sum(1 for item in prepared_results if item is None)
        prepared = [item for item in prepared_results if item is not None]
        prepared.sort(key=lambda x: x.rel)

        changed = 0
        tc_count = 0
        changed_source_ids: list[int] = []
        bytes_hashed = sum(p.size_bytes for p in prepared)
        for item in prepared:
            project = self._project_for(item.path, projects)
            old = known.get(item.rel)
            if not item.content_changed:
                unchanged += 1
                hash_unchanged += 1
                self.db.update_file_metadata(item.rel, project, item.size_bytes, item.mtime_ns)
                continue

            if old:
                affected_target_names |= self.db.symbol_target_names([int(old["id"])])
            kind = "csharp" if item.path.suffix == ".cs" else ("project" if item.path.suffix == ".csproj" else "text")
            file_id = self.db.upsert_file(
                item.rel, kind, project, item.digest, item.text.count("\n") + 1, item.size_bytes, item.mtime_ns
            )
            changed += 1

            if item.path.suffix == ".cs":
                parsed = item.parsed or self._parser().parse(item.text)
                self.db.replace_symbols(file_id, parsed.symbols, parsed.references, item.text, item.rel)
                changed_source_ids.append(file_id)
                for symbol in parsed.symbols:
                    affected_target_names.add(symbol["name"])
                    affected_target_names.add(symbol["full_name"])
            else:
                self.db.replace_symbols(file_id, [], [], item.text, item.rel)

            if item.path.suffix == ".csproj":
                self._scan_project(item.path)

            # Replace functional-test rows for a changed file so removed/renamed tests do not linger.
            self.db.delete_functional_tests_for_path(item.rel)
            if looks_like_testcomplete(item.path, item.text):
                tc_count += self._store_testcomplete(item.rel, item.text)

        content_ms = int((time.perf_counter() - content_start) * 1000)
        relink_start = time.perf_counter()
        relinked = self.db.relink_references(changed_source_ids, affected_target_names)
        relink_ms = int((time.perf_counter() - relink_start) * 1000)
        duration_ms = int((time.perf_counter() - total_start) * 1000)
        seconds = max(duration_ms / 1000.0, 0.001)
        content_seconds = max(content_ms / 1000.0, 0.001)
        metrics = {
            "discovered_files": len(paths),
            "changed_files": changed,
            "unchanged_files": unchanged,
            "deleted_files": deleted_files,
            "deleted_projects": deleted_projects,
            "metadata_skipped_files": metadata_skipped,
            "hash_unchanged_files": hash_unchanged,
            "hashed_files": len(prepared),
            "bytes_hashed": bytes_hashed,
            "functional_tests_updated": tc_count,
            "read_errors": read_errors,
            "relinked_references": relinked,
            "scan_workers": workers,
            "discovery_ms": discovery_ms,
            "content_index_ms": content_ms,
            "relink_ms": relink_ms,
            "duration_ms": duration_ms,
            "files_per_second": round(len(paths) / seconds, 2),
            "content_mb_per_second": round((bytes_hashed / (1024 * 1024)) / content_seconds, 2) if bytes_hashed else 0.0,
        }
        self.db.record_scan_run(metrics)
        return {**metrics, "functional_tests_seen": tc_count, **self.db.stats()}

    def _scan_project(self, p: Path) -> None:
        rel = p.relative_to(self.config.repo_root).as_posix()
        framework = None
        output_type = None
        refs: list[str] = []
        packages: list[dict] = []
        try:
            tree = ET.parse(p)
            root = tree.getroot()
            for elem in root.iter():
                tag = elem.tag.split("}")[-1]
                if tag in {"TargetFramework", "TargetFrameworkVersion", "TargetFrameworks"} and elem.text:
                    framework = elem.text.strip()
                elif tag == "OutputType" and elem.text:
                    output_type = elem.text.strip()
                elif tag == "ProjectReference":
                    include = elem.attrib.get("Include")
                    if include:
                        refs.append(include)
                elif tag == "PackageReference":
                    include = elem.attrib.get("Include")
                    version = elem.attrib.get("Version")
                    if include:
                        packages.append({"name": include, "version": version})
        except Exception:
            pass
        self.db.execute(
            """INSERT INTO projects(path,name,target_framework,output_type,references_json,packages_json)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(path) DO UPDATE SET target_framework=excluded.target_framework,
                 output_type=excluded.output_type,references_json=excluded.references_json,packages_json=excluded.packages_json""",
            (rel, p.stem, framework, output_type, json.dumps(refs), json.dumps(packages)),
        )

    def _store_testcomplete(self, rel: str, text: str) -> int:
        tests = parse_testcomplete_file(rel, text)
        for test in tests:
            self.db.execute(
                """INSERT INTO functional_tests(path,name,test_type,raw_refs_json)
                   VALUES(?,?,?,?)
                   ON CONFLICT(path,name) DO UPDATE SET test_type=excluded.test_type,raw_refs_json=excluded.raw_refs_json""",
                (test["path"], test["name"], test["test_type"], json.dumps(test["raw_refs"])),
            )
            test_id = int(self.db.query("SELECT id FROM functional_tests WHERE path=? AND name=?", (test["path"], test["name"]))[0]["id"])
            self.db.execute("DELETE FROM test_ui_objects WHERE functional_test_id=?", (test_id,))
            for alias in test["aliases"]:
                self.db.execute("INSERT OR IGNORE INTO test_ui_objects(functional_test_id,alias) VALUES(?,?)", (test_id, alias))
        return len(tests)
