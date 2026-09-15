# Changelog

This changelog becomes especially important after development moves into a secure ChatGPT Project without GitHub history. Every completed or materially changed issue should add an entry with changed files and validation evidence.

## Unreleased — Secure Project Handoff

### Added

- `PROJECT_INSTRUCTIONS.md` — pasteable secure ChatGPT Project instructions and durable AI-development rules.
- `HANDOFF.md` — architecture, current implementation state, provider/TestComplete strategy, limitations, CLI, and first secure-environment actions.
- `ISSUES.md` — canonical backlog replacing GitHub Issues after transfer.
- `DEVELOPMENT_PLAN.md` — staged roadmap from secure bootstrap through safe real migration and web-portability proof.
- `SECURE_WORKFLOW.md` — file-by-file/manual editing, validation, security, snapshot, and documentation workflow.
- `CHANGELOG.md` — this repository-resident history.
- Secure transition backlog items for transfer validation, manual snapshot discipline, and optional manifest/self-check.

### Transition state

The handoff branch is based on the incremental-indexing merge and contains the GenAI.mil provider work refreshed on top of it.

The next mandatory secure-environment task is **SEC-001**: verify the complete file transfer and run a fresh combined test/compile baseline.

### Validation note

No new runtime code was introduced by the handoff-documentation change itself. Historical validation evidence from the code changes is recorded below. A fresh combined test run is intentionally required after transfer rather than inferred from independent branch runs.

---

## 2026-09-15 — GenAI.mil Provider Implementation (historical Issue #2, partial)

### Summary

Added GenAI.mil-ready AI provider support based on the remembered OpenAI-compatible chat-completions gateway contract.

### Key behavior

- Request shape uses `model`, `messages`, `temperature`, and `max_tokens`.
- Expected response content is `choices[0].message.content`.
- JSON-only behavior is reinforced through the system prompt.
- Auth can be header, bearer, or query based.
- GenAI.mil requires explicit HTTPS hostname allowlisting.
- Retry/backoff handles transport failures and 408/429/5xx, including `Retry-After`.
- Truncated/content-filtered responses are rejected.
- Errors avoid echoing prompt/source/body/key data.
- Added source-free `ai-smoke` command.

### Main files changed

```text
README.md
examples/modernizer.toml
src/modernizer_agent/ai.py
src/modernizer_agent/cli.py
src/modernizer_agent/config.py
src/modernizer_agent/templates.py
tests/test_ai.py
```

### Validation

Provider/regression tests passed locally before the branch was refreshed on top of the incremental-indexing merge. The secure transfer must rerun the complete combined suite.

### Remaining

Exact authorized endpoint URL, authentication scheme/header, model availability, `ai-smoke`, and real planner/implementer verification.

---

## 2026-09-15 — Incremental Indexing (historical Issue #4, implementation complete)

### Summary

Made repository indexing incremental and safe for large-repository repeated scans.

### Key behavior

- Persists content hash and file modification metadata.
- Unchanged files can skip content reads/hashing/parsing.
- Timestamp/metadata changes can fall back to content-hash verification.
- Deleted/renamed files remove stale file/symbol/reference/FTS/TestComplete/project records.
- Changed TestComplete files replace stale tests.
- Reference relinking is limited to affected sources/target symbol names when possible.
- Optional parse workers keep SQLite writes deterministic/sequential.
- Scan phase timing/throughput metrics are persisted.
- Existing v0.1 index schema gains `mtime_ns` through forward migration.

### Main files changed

```text
examples/modernizer.toml
src/modernizer_agent/config.py
src/modernizer_agent/db.py
src/modernizer_agent/scanner.py
src/modernizer_agent/templates.py
tests/test_incremental_indexing.py
```

### Validation

Historical branch run: **14 tests passed**, including 9 incremental-indexing regressions plus the existing suite at that time. Python compile validation also passed during implementation.

### Remaining

Record cold, unchanged incremental, and representative changed-file timing on the real ~300k LOC repository.

---

## Initial v0.1 Foundation

### Summary

Created the first conservative local Python modernization agent.

### Capabilities

- C#/project/TestComplete discovery.
- Tree-sitter + fallback C# parsing.
- SQLite/FTS persistence.
- Approximate symbol/reference graph.
- Persistent migration tasks and decisions.
- Bounded context creation.
- Separate AI planner/implementer.
- Structured create/replace changes.
- Exact single-match patch validation.
- Backups/rollback.
- Build/unit/functional command validation.
- Dry-run default CLI.
- Architecture guidance for extracting Domain/Application behavior while preserving WinForms and future web portability.

### Historical validation

Initial unit suite: **5 tests passed**. A synthetic WinForms/TestComplete-style smoke repository was also indexed successfully during initial development.

---

## Entry template for future work

Copy this section for future completed/partial tasks:

```markdown
## YYYY-MM-DD — <Issue ID> <Title>

### Status
DONE | PARTIAL | BLOCKED

### Summary
<What changed and why>

### Files changed
- `path`

### Persistent/config/schema impact
<None or details>

### Validation
- `<command>` — PASS/FAIL, relevant counts

### Remaining / follow-up
<None or explicit blocker/next item>
```
