# Legacy Modernizer Agent

A small, local Python orchestration agent for incrementally modernizing a large legacy C#/.NET application when the only AI capability available is a Gemini-style completion endpoint.

The design deliberately keeps **Python in control**. Gemini plans and proposes bounded changes; Python owns repository indexing, context selection, patch safety, builds, tests, TestComplete acceptance checks, rollback, task state, and architectural memory.

## Why this exists

This tool is designed for a large WinForms codebase with little unit testing and substantial TestComplete functional coverage. Its migration strategy is:

1. Keep the existing WinForms application functional while extracting behavior.
2. Treat existing TestComplete tests as an acceptance/compatibility contract.
3. Add characterization and unit tests around extracted behavior.
4. Move business logic into UI-independent Domain/Application layers.
5. Make Application contracts suitable for both WinForms and a future ASP.NET Core/web UI.
6. Replace presentation technology later, after behavior is safely behind reusable boundaries.

It intentionally does **not** attempt a whole-repository rewrite.

## Safety model

Existing files can only be changed through an exact text replacement whose `old_text` occurs **exactly once**. New files can be created. Before any applied migration task is accepted, configured build/test commands run. If validation fails, the touched files are rolled back from `.modernizer/backups/<task-key>/`.

`run-task` is a dry run unless `--apply` is explicitly supplied.

## Requirements

- Python 3.11+
- Filesystem access to the legacy repository
- Gemini completion endpoint reachable from Python
- For automated validation, Python must be allowed to launch your existing build/test commands (for example `dotnet build`, `dotnet test`, and TestComplete/TestExecute CLI commands)

Install in a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

or on bash-like shells:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## First run inside the legacy repository

If this tool lives in a `tools/legacy-modernizer-agent` directory, point `--repo` at the actual legacy repo root.

```bash
modernizer --repo C:\src\LegacyProduct init
modernizer --repo C:\src\LegacyProduct index
modernizer --repo C:\src\LegacyProduct stats
```

`init` creates:

```text
modernizer.toml
.modernizer/
  architecture.md
  migration-rules.md
  index.db              # after indexing; ignored by git
```

The deterministic index includes C# source, `.csproj` metadata, symbols, rough dependency references, full-text search, and TestComplete artifacts it can recognize.

## Gemini configuration

Edit `modernizer.toml`, then set your key in the environment:

```powershell
$env:GEMINI_API_KEY = "..."
```

The default request shape is the Gemini `generateContent` JSON shape. This also works with enterprise gateways that proxy that API unchanged.

If your internal endpoint expects `Authorization: Bearer ...` with a simple completion body, set:

```toml
[gemini]
api_style = "bearer"
endpoint = "https://your-internal-endpoint.example/completions"
model = "your-model-name"
```

If your internal endpoint has a different request or response contract, adapt **only** `src/modernizer_agent/ai.py`; the rest of the agent is intentionally provider-independent.

## GenAI.mil provider mode

The production target for this project is expected to use the GenAI.mil Gemini API. v0.1 includes a guarded `genai_mil` provider mode, but deliberately does **not** guess the tenant URL, model identifier, or authentication header. Copy those values from the authorized GenAI.mil API page when available.

```toml
[gemini]
api_style = "genai_mil"
endpoint = "https://REPLACE-WITH-GENAI-MIL-ENDPOINT/{model}:generateContent"
model = "REPLACE-WITH-GENAI-MIL-MODEL"
api_key_env = "GENAI_MIL_API_KEY"
auth_style = "header" # or bearer/query if the authorized instructions specify it
api_key_header = "x-goog-api-key" # placeholder; use the documented header
api_key_prefix = ""
allowed_hosts = ["REPLACE-WITH-AUTHORIZED-GENAI-MIL-HOST"]
max_retries = 3
retry_backoff_seconds = 1.0
retry_status_codes = [408, 429, 500, 502, 503, 504]
```

GenAI.mil mode refuses to send any request until `allowed_hosts` explicitly contains the configured endpoint hostname. API keys are read only from the named environment variable. HTTP errors and parsing failures do not echo response bodies, prompts, or credentials into exception messages.

After configuring the real endpoint, verify connectivity without sending repository source:

```bash
modernizer --repo C:\src\LegacyProduct ai-smoke
```

`ai-smoke` sends only a fixed request asking for `{"status":"ok"}`. Run this successfully before allowing `bootstrap-plan`, `plan-task`, or `run-task` to call the provider.

## Configure validation

Update the exact commands that work in your environment:

```toml
[validation]
build_commands = ["dotnet build LegacyProduct.sln"]
unit_test_commands = ["dotnet test tests/Modern.UnitTests/Modern.UnitTests.csproj --no-build"]
functional_test_commands = [
  "\"C:\\Program Files (x86)\\SmartBear\\TestExecute 15\\x64\\Bin\\TestExecute.exe\" C:\\tests\\Legacy.pjs /run /SilentMode /exit"
]
```

The TestComplete/TestExecute line above is only an example shape; use the executable, suite/project and arguments approved for your environment.

## Build the first backlog

After indexing:

```bash
modernizer --repo C:\src\LegacyProduct bootstrap-plan
```

Gemini receives repository inventory and architecture rules—not the full 300k-line source tree—and proposes 10–25 small initial tasks. Tasks are persisted in SQLite.

You can also create one manually:

```bash
modernizer --repo C:\src\LegacyProduct create-task MIG-0001 \
  "Characterize and extract order discount calculation" \
  --target OrderPricing \
  --priority 10 \
  --criteria "Characterization tests preserve current discounts; extracted logic has no WinForms dependency; build/unit/TestComplete checks pass."
```

## Plan before coding

```bash
modernizer --repo C:\src\LegacyProduct plan-task MIG-0001
```

The planner may request specific additional files. Python fetches those files and replans. The planning call cannot edit code.

## Generate a patch safely

Dry run:

```bash
modernizer --repo C:\src\LegacyProduct run-task MIG-0001
```

Apply + validate:

```bash
modernizer --repo C:\src\LegacyProduct run-task MIG-0001 --apply
```

Applied flow:

```text
bounded task
  -> deterministic context retrieval
  -> Gemini planner
  -> Gemini implementer
  -> patch validation
  -> backup touched files
  -> apply exact replacements/new files
  -> build
  -> unit/integration tests
  -> TestComplete/TestExecute commands
  -> re-index changed repository
  -> mark task complete
```

Failure during validation rolls back the patch and keeps the task pending.

## Suggested repository layout during migration

The agent's architecture contract is compatible with a target such as:

```text
src/
  Legacy.WinForms/          # existing/transitional
  Product.Domain/           # pure business behavior
  Product.Application/      # use cases, ports, commands/queries/DTOs
  Product.Infrastructure/   # DB/files/external systems
  Product.Api/              # later ASP.NET Core boundary
  Product.Web/              # later web UI

tests/
  Legacy.CharacterizationTests/
  Product.Domain.Tests/
  Product.Application.Tests/
  Product.IntegrationTests/
```

WinForms and the future web UI should be clients of the same Application behavior rather than separate implementations.

## TestComplete support in v0.1

The indexer recognizes common TestComplete project/keyword/name-mapping artifacts and script files containing `Aliases.*` / `Sys.*` references. It stores functional tests and automation object references alongside code metadata so migration planning can surface likely functional-test risks.

This is intentionally format-tolerant rather than tightly coupled to one TestComplete version. Once pointed at the real TestComplete project, the parser can be tightened to the exact formats used by that repository.

## Current v0.1 limitations

- C# call-graph linking is deliberately conservative/approximate; it is not a replacement for Roslyn semantic analysis.
- TestComplete parsing is generic until the tool sees the real project structure.
- Automatic repair loops are not enabled yet; a failed applied task rolls back instead of repeatedly editing the repository.
- Git commits/branches are intentionally left to the surrounding environment initially. This keeps the first deployment usable even where Git CLI access is restricted.
- GenAI.mil provider plumbing is implemented, but the exact authorized endpoint/model/authentication values still must be copied from the GenAI.mil API instructions and verified with `ai-smoke`.

These are intentional first-release boundaries. The first milestone is reliable indexing, bounded context, safe patch generation, and deterministic validation—not unattended autonomous rewriting.
