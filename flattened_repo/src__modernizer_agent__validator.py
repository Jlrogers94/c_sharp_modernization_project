from __future__ import annotations

from dataclasses import dataclass
import subprocess
import time

from .config import AgentConfig
from .db import Database


@dataclass(slots=True)
class CommandResult:
    stage: str
    command: str
    success: bool
    exit_code: int | None
    output: str
    duration_ms: int


class Validator:
    def __init__(self, config: AgentConfig, db: Database):
        self.config = config
        self.db = db

    def _run(self, stage: str, command: str, task_id: int | None) -> CommandResult:
        start = time.perf_counter()
        try:
            p = subprocess.run(
                command,
                cwd=self.config.repo_root,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.config.validation.timeout_seconds,
            )
            output = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
            result = CommandResult(stage, command, p.returncode == 0, p.returncode, output, int((time.perf_counter() - start) * 1000))
        except subprocess.TimeoutExpired as exc:
            output = f"Timed out after {self.config.validation.timeout_seconds}s\n{exc.stdout or ''}\n{exc.stderr or ''}"
            result = CommandResult(stage, command, False, None, output, int((time.perf_counter() - start) * 1000))
        self.db.add_validation_run(task_id, stage, command, result.success, result.exit_code, result.duration_ms, result.output)
        return result

    def validate(self, task_id: int | None, include_functional: bool = True) -> list[CommandResult]:
        results: list[CommandResult] = []
        stages = [
            ("build", self.config.validation.build_commands),
            ("unit", self.config.validation.unit_test_commands),
        ]
        if include_functional:
            stages.append(("functional", self.config.validation.functional_test_commands))
        for stage, commands in stages:
            for command in commands:
                result = self._run(stage, command, task_id)
                results.append(result)
                if not result.success:
                    return results
        return results
