# Canonical Backlog

After the secure ChatGPT Project transfer, this file replaces GitHub Issues as the authoritative backlog. Keep completed items for traceability; update status, date, blockers, and validation evidence rather than deleting them.

Priority meanings:

- **P0** — required before trustworthy work against the real production repository.
- **P1** — core safety, intelligence, and migration capability.
- **P2** — operational maturity, reporting, CI, and proof work.

Status meanings:

- **DONE** — implementation and required validation complete.
- **PARTIAL** — implementation exists but one or more acceptance items still require the secure/real environment.
- **OPEN** — not yet implemented.
- **BLOCKED** — cannot proceed without missing environment/data/access.

---

## Secure transition items

### SEC-001 [P0] Verify secure-project transfer and establish a combined baseline

**Status:** OPEN

**Goal:** Ensure the file-by-file copy into the secure ChatGPT Project is complete and that the combined incremental-indexing + GenAI.mil snapshot works as one codebase.

**Work:**

- Verify every file listed in `HANDOFF.md` is present.
- Create a clean virtual environment and `pip install -e .[dev]`.
- Run `python -m pytest`.
- Run `python -m compileall src tests`.
- Resolve any combined regression caused by the former PR #19 / PR #18 integration.
- Record exact results in `CHANGELOG.md` and update `HANDOFF.md` validation history.

**Acceptance:** complete file set, full test suite green, compileall green, evidence recorded.

### SEC-002 [P1] Maintain manual snapshot/version discipline without GitHub

**Status:** PARTIAL — process documented in `SECURE_WORKFLOW.md`; continue using it during development.

**Goal:** Keep manual copy/paste development auditable after GitHub is no longer available.

**Work:**

- Update `ISSUES.md` and `CHANGELOG.md` in every completed change set.
- Record changed file paths and validation commands/results.
- Keep a human-readable snapshot/release note before major milestones.
- Do not build new work on a file version that has not been confirmed/applied.

### SEC-003 [P2] Add optional repository manifest/self-check

**Status:** OPEN

**Goal:** Reduce accidental omissions during future file-by-file transfers.

**Work:** add a local command/script that lists expected modernization-agent files and optionally hashes them. Never include proprietary target-repository source or secrets in the manifest.

---

## Historical issue backlog migrated from GitHub

### #2 [P0] Integrate and harden the real GenAI.mil completion endpoint

**Status:** PARTIAL — provider implementation exists in the handoff snapshot; exact secure-environment verification remains.

**Implemented:**

- GenAI.mil `api_style`.
- OpenAI-compatible chat-completions request: `model`, `messages`, `temperature`, `max_tokens`.
- Response extraction from `choices[0].message.content`.
- Configurable header/bearer/query authentication.
- HTTPS + explicit hostname allowlist.
- Bounded retry/backoff for transport errors and 408/429/5xx.
- `Retry-After` support.
- Truncation and blocked/content-filter detection.
- Secret/source-safe error messages.
- `ai-smoke` sends no repository source.
- Mocked provider tests.

**Remaining:**

- Confirm exact GenAI.mil endpoint URL.
- Confirm exact authentication scheme/header.
- Confirm model identifier available to the account.
- Run `ai-smoke` successfully.
- Verify planner and implementer JSON flows through the real endpoint.

**Acceptance:** harmless smoke succeeds; planner/implementer parse reliably; transient failures retry; permanent failures stop without edits; credentials are never persisted.

### #3 [P0] Tune TestComplete parsing against the real project and Name Mapping files

**Status:** OPEN / requires real artifacts.

**Goal:** Replace generic discovery with accurate representation of the actual TestComplete suite.

**Work:**

- Inspect actual `.pjs`, `.mds`, `.tcNM`, `.tcKDTest`, script, and related files.
- Parse project/test hierarchy and enabled/disabled test items.
- Parse Name Mapping aliases and object-identification criteria.
- Capture script/keyword references to aliases/reusable routines.
- Store stable test IDs/object mappings in SQLite.
- Add fixtures matching the real TestComplete version/structure.

**Acceptance:** indexed counts are plausible; known tests trace to aliases/objects; Name Mapping changes re-index correctly; tests cover real formats.

### #4 [P0] Incremental indexing and 300k-line benchmark

**Status:** PARTIAL — implementation complete and merged historically; real-repository benchmark remains.

**Implemented:**

- SHA-256 persistence and metadata fast path.
- Unchanged second scan skips content hashing/parsing.
- Addition/modification/deletion/rename cleanup.
- Stale symbol/reference/FTS/TestComplete/project cleanup.
- Targeted affected-reference relinking.
- Optional deterministic parallel parsing with sequential DB writes.
- Scan-run timing/throughput metrics.
- Existing v0.1 database migration for file metadata.
- Regression tests for incremental behavior.

**Remaining:**

- Record cold index duration on the real ~300k LOC repo.
- Record unchanged incremental duration.
- Record representative one-file-change duration.
- Tune `[scan] workers` only if measurements justify it.

**Acceptance:** benchmark results documented and repeated runs deterministic.

### #5 [P0] Run a read-only pilot against the real legacy repository

**Status:** BLOCKED until the secure environment has the real repo/TestComplete/build access.

**Goal:** Validate understanding before any AI-generated source change is applied.

**Work:**

- Run `init`, `index`, `stats`, search, and `bootstrap-plan` read-only.
- Capture project counts, C# LOC, forms/user controls, symbol counts, TestComplete tests, and side-effect dependencies.
- Spot-check index/search results against manual inspection.
- Record current build and TestComplete baseline.
- Generate/review at least 10 migration candidates without applying them.
- Create follow-up items for repository-specific gaps.

**Acceptance:** reproducible current build/TestComplete baseline; plausible inventory; reviewed candidate backlog; zero production source edits.

### #6 [P1] Add Roslyn-backed semantic C# analysis

**Status:** OPEN

**Goal:** Resolve accurate symbol/call/dependency relationships beyond Tree-sitter identifier heuristics.

**Work:** create a small .NET/Roslyn helper callable by Python; emit declaration identities, callers/callees, interface implementations, inheritance, constructor dependencies, and project relationships; merge into SQLite while retaining syntax-only fallback.

**Acceptance:** sampled real call chains resolve correctly; overloads are not conflated; context can follow semantic callers/callees; degraded fallback remains usable.

### #7 [P1] Build hierarchical summaries and token-aware context ranking

**Status:** OPEN

**Goal:** Improve relevant context without flooding the model.

**Work:** hash-keyed method/class/file/project summaries; full source for target/direct dependencies; summaries for deeper context; rank using semantic neighbors, FTS, TestComplete evidence, and decisions; token-aware budgets; prevent one huge file monopolizing context.

**Acceptance:** packets remain inside configured budget; large files cannot crowd out all dependencies/tests; unchanged summaries are reused; real sample tasks contain expected evidence.

### #8 [P1] Map code changes to targeted TestComplete acceptance tests

**Status:** OPEN; depends strongly on #3.

**Goal:** Run the smallest reliable functional subset for each migration while retaining full-suite escalation.

**Work:** map code/forms/features to aliases/tests with confidence/reason; persist affected tests; validation modes `targeted/full/none`; always-run smoke set; low-confidence/high-risk escalation.

**Acceptance:** known feature changes select expected tests; logs explain why; risky changes cannot silently skip broad validation; full suite remains available.

### #9 [P1] Add bounded automatic repair loops

**Status:** OPEN; should follow stronger safety gates.

**Goal:** Repair straightforward build/test failures without unbounded autonomous edits.

**Work:** configurable attempt cap; feed relevant compiler/test errors back with original plan; restrict repair to approved scope; revalidate every attempt; stop on repeated failures, architecture violations, or scope growth; mark `BLOCKED`; persist history.

**Acceptance:** synthetic compile failure repairs within limit; no infinite loop; no out-of-scope repair; unresolved work becomes reviewable `BLOCKED` state.

### #10 [P1] Add migration dependency graph, risk scoring, and vertical-slice scheduling

**Status:** OPEN

**Goal:** Select migration work by prerequisites/risk instead of simple queue order.

**Work:** task dependencies; feature/slice membership; reproducible risk score using dependency depth, UI coupling, side effects, static/global state, unit coverage, TestComplete coverage; prefer low-risk leaf logic; next-recommended explanation.

**Acceptance:** scheduler never selects unmet prerequisites; risk factors are evidence-based; at least one real feature becomes an ordered migration slice.

### #11 [P1] Add Git/local source-control integration and per-task audit trail

**Status:** OPEN; adapt to whatever source-control capability exists in the secure work environment.

**Goal:** Make applied target-repository migrations reviewable and reversible.

**Work:** local Git abstraction when available, optional pure-Python/restricted fallback, clean-working-tree checks, one task/slice commit, stale-base detection, retry/abandon/rollback commands, retain `.modernizer` backups.

**Acceptance:** successful task has isolated history; failed task does not leave committed changes; stale/dirty base is detected; documented fallback exists where Git is unavailable.

**Note:** this issue concerns source control for the **legacy target repository**, not GitHub connectivity for development of this Python tool.

### #12 [P1] Enforce web-portable architecture rules automatically

**Status:** OPEN

**Goal:** Turn the architecture contract into executable validation.

**Work:** classify projects/layers; reject WinForms/UI leakage into Domain/Application; detect direct SQL/files/network where abstractions are required; detect static mutable state/direct clock/environment in testable business logic; support explicit temporary waivers.

**Acceptance:** deliberate invalid dependency fails validation with exact file/symbol/rule; legacy code is not globally blocked; extracted use cases remain callable from WinForms without WinForms dependencies.

### #13 [P1] Add characterization and differential-testing workflows

**Status:** OPEN

**Goal:** Preserve behavior with stronger evidence than code review alone.

**Work:** characterization-first task templates; identify deterministic inputs/outputs and seams; generate tests before risky replacement; old-vs-new differential execution; persist comparison counts/mismatches; explicit tests for intentional behavior changes.

**Acceptance:** representative legacy calculation is characterized and passes new implementation; differential mismatches are clear; preserved vs intentionally changed behavior is explicit.

### #14 [P1] Add command, patch-scope, and secret-handling guardrails

**Status:** OPEN — recommended before meaningful unattended `--apply` usage.

**Goal:** Harden the agent against unsafe model output and command execution.

**Work:** validation-command allow/deny list; max files/lines changed; protected paths; reject absolute/out-of-root paths everywhere; secret detection/redaction where practical; stale-plan/repo-state checks; human-only unsafe override.

**Acceptance:** cannot write outside root/protected areas; excessive patches rejected pre-write; only approved validation commands launch; credentials/obvious secrets are not persisted; violations get distinct rejected/blocked state.

### #15 [P2] Add migration status reporting and history views

**Status:** OPEN

**Goal:** Understand long-running modernization progress without inspecting SQLite manually.

**Work:** CLI task/status/blocked/attempt/decision/validation reports; repository metrics; per-task report; Markdown/JSON export; session summaries and next-task recommendations.

**Acceptance:** status is understandable from CLI; every applied task has an auditable report; blocked/repeated failures are visible; reports are review-friendly.

### #16 [P2] Add CI/linting/type checking/broader regression coverage for the agent

**Status:** OPEN; in secure environment use available internal CI or a local scripted equivalent instead of assuming GitHub Actions.

**Goal:** Keep the tool reliable as capability grows.

**Work:** pytest automation; formatting/linting/type checking appropriate to environment; synthetic multi-project WinForms/TestComplete fixtures; rollback/stale-plan/malformed-model/protected-path/deletion/validation-failure tests; Windows package/CLI smoke.

**Acceptance:** repeatable automated pass/fail signal; important safety/failure paths covered; install/CLI startup exercised; new features add regression coverage.

### #17 [P2] Prove web portability with one migrated vertical slice

**Status:** OPEN; execute after early real migrations are stable.

**Goal:** Demonstrate that WinForms and future web presentation can use the same Application/Domain behavior.

**Work:** choose small representative feature; extract/tests; keep WinForms calling it; add minimal ASP.NET Core API; add minimal web UI proof (Blazor default candidate unless constraints disagree); stable automation IDs; corresponding TestComplete web scenario.

**Acceptance:** desktop/web use same Application use case; no duplicated business behavior; shared tests pass; both presentations have functional coverage; findings confirm/adjust long-term web choice.

---

## Transition-era GitHub issues

### #20 [P0] Prepare self-contained secure ChatGPT Project handoff documentation

**Status:** DONE when `PROJECT_INSTRUCTIONS.md`, `HANDOFF.md`, `ISSUES.md`, `DEVELOPMENT_PLAN.md`, `SECURE_WORKFLOW.md`, and `CHANGELOG.md` are present and reviewed.

### #21 [P0] Verify secure-project transfer and establish combined baseline

**Status:** represented by `SEC-001`; keep `SEC-001` as the active secure-project task.

### #22 [P1] Manual snapshot/version discipline

**Status:** represented by `SEC-002`.

### #23 [P2] Repository manifest/self-check

**Status:** represented by `SEC-003`.

---

## Recommended immediate order

1. **SEC-001** — transfer integrity + combined test baseline.
2. **#2 remaining** — exact GenAI.mil config + `ai-smoke` + real planner/implementer JSON verification.
3. **#3** — real TestComplete parsing.
4. **#4 remaining** — real indexing benchmark.
5. **#5** — read-only production pilot.
6. **#14 + #12 + #13** — safety/architecture/behavior-preservation gates before significant applied migration.
7. **#6 + #7 + #8 + #10** — semantic intelligence/context/test-selection/scheduling.
8. **#9** — bounded repair loops after safety is strong.
9. **#15 + #16 + #11** — operations/reporting/quality/source-control maturity.
10. **#17** — web-portability proof slice.