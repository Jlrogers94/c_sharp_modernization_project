from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass(slots=True)
class PatchResult:
    success: bool
    changed_paths: list[str]
    error: str | None = None


class SafePatcher:
    def __init__(self, repo_root: Path, backup_dir: Path):
        self.repo_root = repo_root.resolve()
        self.backup_dir = backup_dir

    def _resolve(self, relative: str) -> Path:
        path = (self.repo_root / relative).resolve()
        try:
            path.relative_to(self.repo_root)
        except ValueError as exc:
            raise ValueError(f"Path escapes repository: {relative}") from exc
        return path

    def validate(self, changes: list[dict]) -> PatchResult:
        changed: list[str] = []
        for change in changes:
            try:
                path = self._resolve(change["path"])
            except (KeyError, ValueError) as exc:
                return PatchResult(False, changed, str(exc))
            op = change.get("operation")
            if op == "create":
                if path.exists():
                    return PatchResult(False, changed, f"Create rejected; file already exists: {change['path']}")
                if "new_text" not in change:
                    return PatchResult(False, changed, f"Create missing new_text: {change['path']}")
            elif op == "replace":
                if not path.is_file():
                    return PatchResult(False, changed, f"Replace target does not exist: {change['path']}")
                old = change.get("old_text", "")
                if not old:
                    return PatchResult(False, changed, f"Replace missing old_text: {change['path']}")
                current = path.read_text(encoding="utf-8", errors="replace")
                count = current.count(old)
                if count != 1:
                    return PatchResult(False, changed, f"Replace old_text must occur exactly once in {change['path']}; found {count}")
            else:
                return PatchResult(False, changed, f"Unsupported operation {op!r}")
            changed.append(change["path"])
        return PatchResult(True, changed)

    def apply(self, changes: list[dict], task_key: str) -> PatchResult:
        check = self.validate(changes)
        if not check.success:
            return check
        task_backup = self.backup_dir / task_key
        task_backup.mkdir(parents=True, exist_ok=True)
        applied: list[str] = []
        try:
            for change in changes:
                path = self._resolve(change["path"])
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    backup = task_backup / change["path"]
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, backup)
                if change["operation"] == "create":
                    path.write_text(change["new_text"], encoding="utf-8")
                else:
                    current = path.read_text(encoding="utf-8", errors="replace")
                    path.write_text(current.replace(change["old_text"], change["new_text"], 1), encoding="utf-8")
                applied.append(change["path"])
            return PatchResult(True, applied)
        except Exception as exc:
            self.restore(task_key, applied)
            return PatchResult(False, applied, f"Patch failed and rollback attempted: {exc}")

    def restore(self, task_key: str, paths: list[str]) -> None:
        task_backup = self.backup_dir / task_key
        for relative in paths:
            original = self._resolve(relative)
            backup = task_backup / relative
            if backup.exists():
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, original)
            elif original.exists():
                original.unlink()
