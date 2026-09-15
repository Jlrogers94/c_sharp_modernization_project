from __future__ import annotations

from pathlib import Path
from .config import AgentConfig
from .db import Database


class ContextBuilder:
    def __init__(self, config: AgentConfig, db: Database):
        self.config = config
        self.db = db

    def build_for_task(self, task) -> str:
        chunks: list[str] = []
        budget = self.config.context_char_budget

        def add(title: str, content: str) -> None:
            nonlocal budget
            if budget <= 0 or not content:
                return
            clipped = content[:budget]
            chunks.append(f"\n===== {title} =====\n{clipped}")
            budget -= len(clipped)

        for filename, title in (("architecture.md", "ARCHITECTURE RULES"), ("migration-rules.md", "MIGRATION RULES")):
            p = self.config.state_dir / filename
            if p.exists():
                add(title, p.read_text(encoding="utf-8", errors="replace"))

        decisions = self.db.query("SELECT decision_key,scope,decision,rationale FROM decisions WHERE status='accepted' ORDER BY id")
        if decisions:
            add("ARCHITECTURE DECISIONS", "\n".join(f"{r['decision_key']} [{r['scope']}]: {r['decision']} — {r['rationale']}" for r in decisions))

        target = task["target"] or task["title"]
        search_terms = [target, task["title"]]
        seen_paths: set[str] = set()
        for term in search_terms:
            for row in self.db.search(term, limit=12):
                path = row["path"]
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                p = self.config.repo_root / path
                if p.exists():
                    add(f"SOURCE: {path}", p.read_text(encoding="utf-8", errors="replace"))

        # Include directly connected symbol files.
        symbol_rows = self.db.query(
            """SELECT DISTINCT f.path FROM symbols s JOIN files f ON f.id=s.file_id
               WHERE s.name=? OR s.full_name=? OR s.full_name LIKE ? LIMIT 10""",
            (target, target, f"%{target}%"),
        )
        for row in symbol_rows:
            path = row["path"]
            if path in seen_paths:
                continue
            p = self.config.repo_root / path
            if p.exists():
                seen_paths.add(path)
                add(f"TARGET SOURCE: {path}", p.read_text(encoding="utf-8", errors="replace"))

        # Surface TestComplete safety-net evidence that references likely feature names.
        words = [w for w in target.replace(".", " ").split() if len(w) >= 4][:5]
        if words:
            like = " OR ".join("name LIKE ? OR raw_refs_json LIKE ?" for _ in words)
            params: list[str] = []
            for w in words:
                params.extend([f"%{w}%", f"%{w}%"])
            tests = self.db.query(f"SELECT path,name,test_type,raw_refs_json FROM functional_tests WHERE {like} LIMIT 30", tuple(params))
            if tests:
                add("RELATED TESTCOMPLETE TESTS", "\n".join(f"{r['name']} ({r['test_type']}) @ {r['path']} refs={r['raw_refs_json'][:1000]}" for r in tests))

        return "\n".join(chunks)

    def fetch_requested(self, paths: list[str]) -> str:
        chunks = []
        for raw in paths[:30]:
            path = (self.config.repo_root / raw).resolve()
            try:
                path.relative_to(self.config.repo_root)
            except ValueError:
                continue
            if path.is_file():
                chunks.append(f"\n===== REQUESTED SOURCE: {raw} =====\n{path.read_text(encoding='utf-8', errors='replace')}")
        return "\n".join(chunks)
