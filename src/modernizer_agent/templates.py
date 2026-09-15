from __future__ import annotations

from pathlib import Path

MODERNIZER_TOML = r'''# Local modernization-agent configuration.

[agent]
state_dir = ".modernizer"
max_repair_attempts = 4
# Character budget for deterministic context before Gemini is called.
context_char_budget = 180000

[gemini]
# For the native Gemini generateContent API or a gateway that preserves its request shape.
endpoint = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
model = "gemini-2.5-pro"
api_key_env = "GEMINI_API_KEY"
api_style = "google" # google | genai_mil | bearer | simple
# GenAI.mil currently appears to expose an OpenAI-compatible chat-completions
# body/response. Use api_style="genai_mil" and copy the endpoint/auth details
# from the authorized API page. Do not commit the key itself. Example:
# endpoint = "https://REPLACE-WITH-GENAI-MIL-HOST/v1/chat/completions"
# model = "google/gemini-3.1-pro"
# api_key_env = "GENAI_MIL_API_KEY"
# api_style = "genai_mil"
# auth_style = "header"       # or bearer/query if documented
# api_key_header = "REPLACE-WITH-DOCUMENTED-HEADER"
# api_key_prefix = ""
# allowed_hosts = ["REPLACE-WITH-GENAI-MIL-HOST"]
max_retries = 3
retry_backoff_seconds = 1.0
retry_status_codes = [408, 429, 500, 502, 503, 504]
timeout_seconds = 180
max_output_tokens = 32768
temperature = 0.1

[validation]
# Change these to the exact solution/test commands available in your environment.
build_commands = ["dotnet build"]
unit_test_commands = ["dotnet test --no-build"]
# Put your TestComplete command-line invocation here. Leave empty until configured.
# Example shape only; use the actual TestComplete/TestExecute path and project suite in your environment.
functional_test_commands = []
timeout_seconds = 1800

[scan]
workers = 1
exclude_dirs = [".git", ".vs", "bin", "obj", "packages", "node_modules", ".modernizer"]
'''

ARCHITECTURE_MD = r'''# Modernization Architecture Contract

## Objective
Incrementally hollow out the legacy WinForms application while preserving observable behavior and the existing TestComplete functional-test contract. The resulting business/application code must be reusable by a future web application.

## Layer rules

### Domain
- Pure business rules, entities, value objects and deterministic services.
- MUST NOT reference `System.Windows.Forms`, ASP.NET, HTTP, UI controls, `MessageBox`, database APIs, filesystem APIs, mutable global UI state, or TestComplete.
- Time, randomness, environment and external services must enter through explicit abstractions when they affect behavior.

### Application
- Contains use cases, commands, queries, DTOs, typed results, ports/interfaces and orchestration.
- MUST NOT reference WinForms, Razor/HTML, UI controls or `MessageBox`.
- Contracts should be suitable for both in-process calls from WinForms and transport over HTTP later.

### Infrastructure
- Implements persistence, filesystem, HTTP/external integrations and other side effects behind Application/Domain interfaces.

### Presentation
- Legacy WinForms is transitional presentation code.
- Future web presentation should consume the same Application behavior, directly or via ASP.NET Core endpoints.
- Presentation owns UI-specific validation/display concerns; business validation belongs below it.

## Migration strategy
1. Preserve current behavior first; fix intentional behavior separately.
2. Add characterization/unit tests before risky refactors.
3. Prefer small vertical migration slices and low-dependency leaf logic.
4. Keep TestComplete scenarios green throughout the transition.
5. Do not replace the desktop UI as the first phase.
6. Use stable automation identities for future web controls (`data-testid` or equivalent) and keep TestComplete aliases semantic.
'''

MIGRATION_RULES_MD = r'''# Agent Migration Rules

- Every change must have a bounded migration task and explicit acceptance criteria.
- A successful compile is required before a task can complete.
- Relevant unit/integration tests must pass before a task can complete.
- Configured TestComplete functional tests are an acceptance contract and must pass before a task can complete.
- Existing files are edited only with exact, single-match text replacements. The agent may not blindly overwrite existing files.
- Failed validation rolls the task back from `.modernizer/backups/<task>/`.
- Never rename or remove automation-facing UI objects merely to make implementation cleaner.
- Prefer extracting behavior behind application/domain boundaries while leaving the existing WinForms screen behavior intact.
- Record architectural decisions so later AI calls do not invent duplicate abstractions such as multiple clock, user-context or repository interfaces.
- Block a task rather than broadening its scope unexpectedly.
'''


def initialize_repo(root: Path) -> list[Path]:
    created: list[Path] = []
    config = root / "modernizer.toml"
    state = root / ".modernizer"
    state.mkdir(parents=True, exist_ok=True)
    for path, content in [
        (config, MODERNIZER_TOML),
        (state / "architecture.md", ARCHITECTURE_MD),
        (state / "migration-rules.md", MIGRATION_RULES_MD),
    ]:
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(path)
    return created
