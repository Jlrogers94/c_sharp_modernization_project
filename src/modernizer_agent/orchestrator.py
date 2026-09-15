from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .ai import GeminiClient, parse_json_response
from .config import AgentConfig
from .context import ContextBuilder
from .db import Database
from .patcher import SafePatcher
from .prompts import planner_prompt, implementer_prompt, bootstrap_prompt
from .scanner import RepoScanner
from .validator import Validator


class ModernizerAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(config.db_path)
        self.ai = GeminiClient(config)
        self.context = ContextBuilder(config, self.db)
        self.patcher = SafePatcher(config.repo_root, config.state_dir / "backups")
        self.validator = Validator(config, self.db)

    def close(self):
        self.db.close()

    def index(self) -> dict:
        return RepoScanner(self.config, self.db).scan()

    def bootstrap_plan(self) -> dict:
        projects = self.db.query("SELECT * FROM projects ORDER BY path")
        high_ref = self.db.query(
            """SELECT s.full_name,s.kind,f.path,COUNT(r.id) AS refs
               FROM symbols s JOIN files f ON f.id=s.file_id
               LEFT JOIN references_graph r ON r.target_symbol_id=s.id
               GROUP BY s.id ORDER BY refs DESC LIMIT 80"""
        )
        tc = self.db.query("SELECT path,name,test_type,raw_refs_json FROM functional_tests LIMIT 100")
        inventory = json.dumps({
            "stats": self.db.stats(),
            "projects": [dict(x) for x in projects],
            "high_reference_symbols": [dict(x) for x in high_ref],
            "functional_tests_sample": [dict(x) for x in tc],
        }, indent=2)
        architecture_path = self.config.state_dir / "architecture.md"
        architecture = architecture_path.read_text(encoding="utf-8") if architecture_path.exists() else ""
        response = parse_json_response(self.ai.complete(bootstrap_prompt(inventory, architecture), json_mode=True))
        for task in response.get("first_tasks", []):
            self.db.create_task(task["task_key"], task["title"], task.get("target"), int(task.get("priority", 100)), task.get("acceptance_criteria", ""))
        return response

    def plan_task(self, task_key: str) -> dict:
        task = self.db.get_task(task_key)
        if task is None:
            raise KeyError(f"Unknown task: {task_key}")
        context = self.context.build_for_task(task)
        plan = parse_json_response(self.ai.complete(planner_prompt(task, context), json_mode=True))
        requested = [p for p in plan.get("files_required", []) if p]
        if requested:
            extra = self.context.fetch_requested(requested)
            if extra:
                context += extra
                plan = parse_json_response(self.ai.complete(planner_prompt(task, context), json_mode=True))
        self.db.update_task(task_key, plan_json=json.dumps(plan))
        return plan

    def run_task(self, task_key: str, *, apply: bool = False, run_functional: bool = True) -> dict:
        task = self.db.get_task(task_key)
        if task is None:
            raise KeyError(f"Unknown task: {task_key}")
        plan = json.loads(task["plan_json"]) if task["plan_json"] else self.plan_task(task_key)
        if not plan.get("safe_to_implement", False):
            self.db.update_task(task_key, status="BLOCKED", blocked_reason="Planner marked task unsafe")
            return {"status": "BLOCKED", "plan": plan}

        context = self.context.build_for_task(task) + self.context.fetch_requested(plan.get("files_required", []))
        implementation = parse_json_response(self.ai.complete(implementer_prompt(task, plan, context), json_mode=True))
        changes = implementation.get("changes", [])
        patch_check = self.patcher.validate(changes)
        if not patch_check.success:
            return {"status": "PATCH_REJECTED", "error": patch_check.error, "implementation": implementation}
        if not apply:
            return {"status": "DRY_RUN", "plan": plan, "implementation": implementation, "changed_paths": patch_check.changed_paths}

        task_id = int(task["id"])
        patch = self.patcher.apply(changes, task_key)
        if not patch.success:
            return {"status": "PATCH_FAILED", "error": patch.error}

        results = self.validator.validate(task_id, include_functional=run_functional)
        if not all(r.success for r in results):
            self.patcher.restore(task_key, patch.changed_paths)
            self.db.update_task(task_key, status="PENDING", attempts=int(task["attempts"]) + 1)
            return {
                "status": "VALIDATION_FAILED_ROLLED_BACK",
                "changed_paths": patch.changed_paths,
                "validation": [asdict(r) for r in results],
            }

        self.db.update_task(task_key, status="COMPLETE", attempts=int(task["attempts"]) + 1)
        self.index()
        self._record_decisions(task_key, implementation.get("decisions", []))
        return {"status": "COMPLETE", "changed_paths": patch.changed_paths, "validation": [asdict(r) for r in results]}

    def _record_decisions(self, task_key: str, decisions: list[dict]) -> None:
        for i, d in enumerate(decisions, 1):
            key = f"{task_key}-ADR-{i:02d}"
            self.db.execute(
                """INSERT OR IGNORE INTO decisions(decision_key,scope,decision,rationale)
                   VALUES(?,?,?,?)""",
                (key, d.get("scope", task_key), d.get("decision", ""), d.get("rationale", "")),
            )
