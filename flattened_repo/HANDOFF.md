# Legacy Modernizer Agent — Secure Project Handoff

This file is the durable technical handoff for continuing development inside a secure ChatGPT Project without GitHub connectivity.

## 1. Purpose

The tool modernizes a large (~300,000 LOC) legacy C# WinForms application incrementally instead of attempting a whole-repository rewrite.

The intended migration pattern is:

```text
existing WinForms behavior
        |
        v
characterization + TestComplete acceptance contract
        |
        v
extract Application / Domain behavior
        |
        +--> existing WinForms presentation keeps working
        |
        +--> eventual ASP.NET Core / web presentation reuses the same behavior
```

Python is the orchestration agent. The AI endpoint proposes plans/changes; deterministic local code owns the repository, context selection, patching, validation, rollback, task state, and architecture memory.

## 2. Current implementation snapshot

The handoff snapshot is based on:

- Original v0.1 modernization agent merged through the initial repository work.
- Incremental indexing work from former Issue #4 / PR #19 merged into `main`.
- GenAI.mil chat-completions provider work from former Issue #2 / PR #18 refreshed on top of the incremental-indexing changes.
- Secure-project handoff documentation added afterward.

### Implemented capabilities

- Python CLI package (`modernizer`).
- SQLite persistent state under `.modernizer/index.db`.
- C# syntax indexing with Tree-sitter C# and a regex fallback.
- `.csproj` parsing for framework/output/project/package metadata.
- SQLite FTS5 search.
- Conservative symbol/reference graph.
- TestComplete artifact discovery and `Aliases.*` / `Sys.*` reference extraction.
- Persistent migration task queue and architecture decisions.
- Planner/implementer separation for AI calls.
- Exact single-match replacement safety for existing files.
- Backups and rollback for applied migration tasks.
- Build/unit/functional validation hooks.
- Dry-run by default; `--apply` required for repository edits.
- Incremental indexing with hash + file metadata fast path.
- Cleanup of stale symbols, FTS rows, TestComplete records, references, and project records after deletes/renames.
- Targeted reference relinking rather than unconditional full-graph relinking.
- Optional deterministic parallel parsing with sequential SQLite writes.
- Scan timing/throughput metrics and persisted scan history.
- GenAI.mil provider mode using an OpenAI-compatible chat-completions request/response shape.
- Configurable auth style (header/bearer/query), HTTPS/hostname allowlisting, bounded retries/backoff, `Retry-After`, truncation/blocked-response detection, and source-free `ai-smoke`.

## 3. Current repository map

```text
README.md
PROJECT_INSTRUCTIONS.md
HANDOFF.md
ISSUES.md
DEVELOPMENT_PLAN.md
SECURE_WORKFLOW.md
CHANGELOG.md
pyproject.toml
examples/
  modernizer.toml
src/modernizer_agent/
  __init__.py
  __main__.py
  ai.py
  cli.py
  config.py
  context.py
  csharp.py
  db.py
  orchestrator.py
  patcher.py
  prompts.py
  scanner.py
  templates.py
  testcomplete.py
  validator.py
tests/
  test_ai.py
  test_csharp.py
  test_db.py
  test_incremental_indexing.py
  test_patcher.py
  test_testcomplete.py
```

If the secure Project is missing an expected file, treat the transfer as incomplete before making dependent edits.

## 4. Important file responsibilities

- `ai.py` — AI provider request/auth/retry/response parsing. Provider-specific logic belongs here.
- `config.py` — TOML-backed configuration and endpoint safety validation.
- `db.py` — SQLite schema, migrations, task/index persistence, FTS/reference operations.
- `scanner.py` — repository discovery, incremental file detection, C#/TestComplete parsing orchestration, stale-record cleanup, metrics.
- `csharp.py` — Tree-sitter C# syntax extraction and fallback parser.
- `testcomplete.py` — generic TestComplete discovery/parser pending tuning against the real suite.
- `context.py` — bounded deterministic source/context assembly.
- `prompts.py` — planner/implementer/bootstrap AI instructions and JSON contracts.
- `patcher.py` — exact-match safe create/replace and rollback.
- `validator.py` — external command execution and validation result persistence.
- `orchestrator.py` — high-level index/plan/run flow.
- `cli.py` — command-line surface including `ai-smoke`.
- `templates.py` — generated `modernizer.toml`, architecture contract, migration rules.

## 5. Known validation history

Historical evidence before the secure transfer:

- Initial v0.1 tests: 5 passed.
- Incremental-indexing branch: 14 tests passed (existing tests + new indexing regressions) before merge.
- GenAI.mil provider branch: provider/regression suite passed locally before it was refreshed on top of the indexing merge.

Important: the **combined handoff snapshot must be re-run in the secure environment** after file-by-file transfer. Do not assume the independent historical runs are equivalent to a fresh combined baseline. This is tracked as the secure transfer P0 item in `ISSUES.md`.

Recommended baseline:

```bash
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m pytest
python -m compileall src tests
```

## 6. GenAI.mil contract

The remembered API shape is an OpenAI-compatible chat-completions gateway with a Gemini model.

Request shape:

```json
{
  "model": "google/gemini-3.1-pro",
  "messages": [
    {
      "role": "system",
      "content": "Follow the requested output format exactly."
    },
    {
      "role": "user",
      "content": "..."
    }
  ],
  "temperature": 0.1,
  "max_tokens": 32768
}
```

Expected response path:

```text
choices[0].message.content
```

Expected finish handling:

- `stop` => normal completion.
- `length` / `max_tokens` => reject as truncated.
- `content_filter` / safety-style result => reject as blocked.

Still unknown until confirmed in the authorized environment:

- Exact HTTPS endpoint URL.
- Exact API-key authentication header/scheme.
- Exact currently available model identifier.

Never hard-code a guessed public endpoint. Keep `allowed_hosts` explicit and run:

```bash
modernizer --repo <legacy-repo> ai-smoke
```

before any request containing source context.

## 7. TestComplete migration strategy

TestComplete is the behavioral acceptance contract during migration.

Current parser is intentionally generic. It recognizes common file types and `Aliases.*` / `Sys.*` references, but Issue #3 still requires tuning against the actual TestComplete version/project structure.

Target model:

```text
TestComplete scenario
  -> Name Mapping aliases / automation objects
  -> WinForms form/feature
  -> event handler / orchestration
  -> current business/data behavior
```

A migration slice should eventually become:

```text
WinForms form
  -> Application use case
     -> Domain rules
     -> ports/interfaces
     -> Infrastructure implementations
```

while the relevant TestComplete scenario remains green.

For a later web UI, favor stable semantic automation IDs (`data-testid` or equivalent) and preserve the business scenario even if raw UI selectors change.

## 8. Target architecture

```text
src/
  Legacy.WinForms/
  Product.Domain/
  Product.Application/
  Product.Infrastructure/
  Product.Api/
  Product.Web/
```

### Domain

Pure business behavior. No WinForms, ASP.NET, UI controls, MessageBox, filesystem/database/network APIs, TestComplete, or mutable UI/global state.

### Application

Use cases, commands, queries, DTOs, typed results, ports/interfaces, orchestration. No WinForms/Razor/HTML/UI controls.

### Infrastructure

Database, files, HTTP/external services, operating-system integrations behind interfaces.

### Presentation

Legacy WinForms initially; later API/web. Both should consume the same Application behavior.

## 9. Migration safety model

Current safeguards:

- Dry-run default.
- Existing file edit requires exact `old_text` occurring once.
- New files only created if absent.
- Backups before edits.
- Rollback on failed validation.
- Planner cannot directly edit files.
- AI implementation response must use structured create/replace operations.
- GenAI.mil host allowlisting and environment-variable credentials.

Still required before unattended/large-scale applied migration:

- Issue #14 command/patch/secret guardrails.
- Issue #12 executable architecture boundary checks.
- Stronger semantic dependency information (Issue #6).
- Better characterization/differential workflows (Issue #13).
- Bounded repair loops (Issue #9) only after safety gates are strong.

## 10. Current limitations

- C# dependency linking remains syntax/identifier based; overloads/interfaces/extension methods can be ambiguous until Roslyn work (#6).
- TestComplete parser is generic until real artifacts are available (#3).
- Context selection still needs hierarchical summaries/token-aware ranking (#7).
- Functional tests are not yet selected per affected feature (#8).
- Automatic repair loops are not active (#9).
- Architecture rules are still mostly prompt/documentation driven (#12).
- Agent-level reporting/CI maturity is incomplete (#15/#16).
- Real 300k-line cold/incremental index timings still need to be recorded (#4 remaining acceptance item).
- The real production repository has not yet completed the read-only pilot (#5).

## 11. Core CLI

```bash
modernizer --repo <repo> init
modernizer --repo <repo> index
modernizer --repo <repo> stats
modernizer --repo <repo> search "PricingService" --limit 20
modernizer --repo <repo> ai-smoke

modernizer --repo <repo> create-task MIG-0001 "..." --target ... --priority 10 --criteria "..."
modernizer --repo <repo> bootstrap-plan
modernizer --repo <repo> plan-task MIG-0001
modernizer --repo <repo> run-task MIG-0001
modernizer --repo <repo> run-task MIG-0001 --apply
modernizer --repo <repo> run-next --apply
```

`--skip-functional` exists for controlled cases but should not become the normal path for behavior-affecting migration work.

## 12. Definition of done for a modernization task

A task is complete only when appropriate evidence shows:

1. Scope remained bounded to the approved task.
2. Required source/tests were changed deliberately.
3. Build passes.
4. Relevant unit/integration/characterization tests pass.
5. Relevant TestComplete acceptance coverage passes.
6. Architecture rules are satisfied or an explicit temporary waiver is recorded.
7. Index/state is refreshed.
8. Decisions that affect future work are recorded.
9. `ISSUES.md` and `CHANGELOG.md` are updated.

## 13. First actions after secure transfer

1. Confirm every repository file is uploaded to the Project.
2. Paste `PROJECT_INSTRUCTIONS.md` into the Project Instructions field.
3. Run the complete Python test/compile baseline and record results.
4. Confirm the current `modernizer.toml` template contains both GenAI.mil configuration support and `[scan] workers` from incremental indexing.
5. Fill in real GenAI.mil endpoint/auth/model values **locally only** and run `ai-smoke` without source.
6. Obtain representative real TestComplete artifacts and work Issue #3.
7. Run the real-repository cold and unchanged incremental index to finish Issue #4 benchmarking.
8. Perform Issue #5 read-only pilot before enabling applied migration work.

For sequencing after that, follow `DEVELOPMENT_PLAN.md`.