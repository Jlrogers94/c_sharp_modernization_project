from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from .config import AgentConfig
from .csharp import CSharpParser
from .db import Database
from .testcomplete import TESTCOMPLETE_EXTENSIONS, looks_like_testcomplete, parse_testcomplete_file


TEXT_EXTENSIONS = {".cs", ".csproj", ".sln", ".props", ".targets"} | TESTCOMPLETE_EXTENSIONS


class RepoScanner:
    def __init__(self, config: AgentConfig, db: Database):
        self.config = config
        self.db = db
        self.csharp = CSharpParser()

    def _excluded(self, path: Path) -> bool:
        rel_parts = path.relative_to(self.config.repo_root).parts
        return any(part in self.config.exclude_dirs for part in rel_parts)

    def _project_for(self, path: Path, projects: list[Path]) -> str | None:
        candidates = [p for p in projects if p.parent == path.parent or p.parent in path.parents]
        if not candidates:
            return None
        return str(max(candidates, key=lambda p: len(p.parts)).relative_to(self.config.repo_root))

    def scan(self) -> dict:
        root = self.config.repo_root
        projects = [p for p in root.rglob("*.csproj") if not self._excluded(p)]
        self._scan_projects(projects)
        changed = 0
        unchanged = 0
        tc_count = 0

        for path in root.rglob("*"):
            if not path.is_file() or self._excluded(path) or path.suffix not in TEXT_EXTENSIONS:
                continue
            try:
                raw = path.read_bytes()
                text = raw.decode("utf-8-sig", errors="replace")
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            digest = hashlib.sha256(raw).hexdigest()
            old = self.db.query("SELECT id,sha256 FROM files WHERE path=?", (rel,))
            kind = "csharp" if path.suffix == ".cs" else ("project" if path.suffix == ".csproj" else "text")
            file_id = self.db.upsert_file(rel, kind, self._project_for(path, projects), digest, text.count("\n") + 1, len(raw))
            if old and old[0]["sha256"] == digest:
                unchanged += 1
                continue
            changed += 1
            if path.suffix == ".cs":
                parsed = self.csharp.parse(text)
                self.db.replace_symbols(file_id, parsed.symbols, parsed.references, text, rel)
            else:
                self.db.replace_symbols(file_id, [], [], text, rel)

            if looks_like_testcomplete(path, text):
                tc_count += self._store_testcomplete(rel, text)

        self.db.relink_references()
        return {"changed_files": changed, "unchanged_files": unchanged, "functional_tests_seen": tc_count, **self.db.stats()}

    def _scan_projects(self, projects: list[Path]) -> None:
        for p in projects:
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
