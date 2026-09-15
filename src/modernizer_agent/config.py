from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib


@dataclass(slots=True)
class GeminiConfig:
    endpoint: str = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    model: str = "gemini-2.5-pro"
    api_key_env: str = "GEMINI_API_KEY"
    timeout_seconds: float = 180.0
    temperature: float = 0.1
    max_output_tokens: int = 32768
    api_style: str = "google"


@dataclass(slots=True)
class ValidationConfig:
    build_commands: list[str] = field(default_factory=lambda: ["dotnet build"])
    unit_test_commands: list[str] = field(default_factory=lambda: ["dotnet test --no-build"])
    functional_test_commands: list[str] = field(default_factory=list)
    timeout_seconds: int = 1800


@dataclass(slots=True)
class AgentConfig:
    repo_root: Path
    state_dir: Path
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    include_globs: list[str] = field(default_factory=lambda: ["**/*.cs", "**/*.csproj", "**/*.sln"])
    exclude_dirs: list[str] = field(default_factory=lambda: [".git", ".vs", "bin", "obj", "packages", "node_modules", ".modernizer"])
    max_repair_attempts: int = 4
    context_char_budget: int = 180_000

    @property
    def db_path(self) -> Path:
        return self.state_dir / "index.db"

    @classmethod
    def load(cls, repo_root: str | Path, config_path: str | Path | None = None) -> "AgentConfig":
        root = Path(repo_root).resolve()
        path = Path(config_path).resolve() if config_path else root / "modernizer.toml"
        raw: dict = {}
        if path.exists():
            with path.open("rb") as f:
                raw = tomllib.load(f)

        state_dir = root / raw.get("agent", {}).get("state_dir", ".modernizer")
        gemini_raw = raw.get("gemini", {})
        validation_raw = raw.get("validation", {})
        scan_raw = raw.get("scan", {})

        gemini_defaults = GeminiConfig()
        validation_defaults = ValidationConfig()
        gemini = GeminiConfig(
            endpoint=gemini_raw.get("endpoint", gemini_defaults.endpoint),
            model=gemini_raw.get("model", gemini_defaults.model),
            api_key_env=gemini_raw.get("api_key_env", gemini_defaults.api_key_env),
            timeout_seconds=float(gemini_raw.get("timeout_seconds", gemini_defaults.timeout_seconds)),
            temperature=float(gemini_raw.get("temperature", gemini_defaults.temperature)),
            max_output_tokens=int(gemini_raw.get("max_output_tokens", gemini_defaults.max_output_tokens)),
            api_style=gemini_raw.get("api_style", gemini_defaults.api_style),
        )
        validation = ValidationConfig(
            build_commands=list(validation_raw.get("build_commands", ["dotnet build"])),
            unit_test_commands=list(validation_raw.get("unit_test_commands", ["dotnet test --no-build"])),
            functional_test_commands=list(validation_raw.get("functional_test_commands", [])),
            timeout_seconds=int(validation_raw.get("timeout_seconds", validation_defaults.timeout_seconds)),
        )
        agent_raw = raw.get("agent", {})
        return cls(
            repo_root=root,
            state_dir=state_dir,
            gemini=gemini,
            validation=validation,
            include_globs=list(scan_raw.get("include_globs", ["**/*.cs", "**/*.csproj", "**/*.sln"])),
            exclude_dirs=list(scan_raw.get("exclude_dirs", [".git", ".vs", "bin", "obj", "packages", "node_modules", ".modernizer"])),
            max_repair_attempts=int(agent_raw.get("max_repair_attempts", 4)),
            context_char_budget=int(agent_raw.get("context_char_budget", 180_000)),
        )

    def api_key(self) -> str:
        value = os.environ.get(self.gemini.api_key_env, "")
        if not value:
            raise RuntimeError(f"Missing API key environment variable: {self.gemini.api_key_env}")
        return value
