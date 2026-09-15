# Secure Project Development Workflow

This workflow assumes the modernization-agent project is maintained inside a secure ChatGPT Project without direct GitHub access and that many file changes must be applied manually by copy/paste.

## 1. Repository authority

The ChatGPT Project files are the working repository.

Canonical project-management files:

- `PROJECT_INSTRUCTIONS.md` — AI behavior and development rules.
- `HANDOFF.md` — current technical state and architecture.
- `ISSUES.md` — canonical backlog after transition.
- `DEVELOPMENT_PLAN.md` — implementation order and gates.
- `CHANGELOG.md` — completed work and validation evidence.

Do not rely on old chat history or GitHub to recover a decision that should be durable. Put durable information into one of these files.

## 2. Initial transfer checklist

Before new development:

- [ ] All root files uploaded.
- [ ] `src/modernizer_agent/*` uploaded.
- [ ] `tests/*` uploaded.
- [ ] `examples/modernizer.toml` uploaded.
- [ ] Secure handoff Markdown files uploaded.
- [ ] Project Instructions populated from `PROJECT_INSTRUCTIONS.md`.
- [ ] Fresh virtual environment created.
- [ ] `pip install -e .[dev]` succeeds.
- [ ] `python -m pytest` passes.
- [ ] `python -m compileall src tests` passes.
- [ ] Baseline recorded in `CHANGELOG.md`.

If any expected source file is missing, stop dependent implementation until it is available.

## 3. Session startup for an AI model

At the beginning of substantive work:

1. Read `HANDOFF.md`.
2. Read the relevant section of `ISSUES.md`.
3. Read `DEVELOPMENT_PLAN.md` if sequencing matters.
4. Read the current versions of every file expected to change.
5. Confirm the issue's acceptance criteria.
6. Check `CHANGELOG.md` for recent changes that may affect the task.

Do not draft edits against remembered/stale file contents when the current Project file can be read.

## 4. One issue at a time

Each change set should have one primary issue ID, for example:

```text
#3
#14
SEC-001
```

Before code changes, record/communicate:

- issue ID and goal;
- exact files likely to change;
- tests/commands required;
- blockers or missing real-environment information.

Avoid drive-by formatting/refactors unrelated to the active issue.

## 5. Manual file-edit format

Because the user may copy/paste changes manually, optimize for correctness rather than compact diffs.

### New file

Provide:

```text
Path: src/.../new_file.py
Action: CREATE
```

followed by the complete file.

### Small or moderate existing file

Prefer:

```text
Path: src/.../file.py
Action: REPLACE FILE
```

followed by the complete replacement contents.

### Very large existing file

If a full replacement is impractical, provide:

```text
Path: ...
Action: REPLACE BLOCK
Find this exact unique block:
<old block>

Replace with:
<new block>
```

Include enough unique surrounding context to prevent the wrong replacement.

### Multiple files

Handle files in dependency order. Keep documentation/backlog updates in the same logical change set but separate them clearly from code.

## 6. Never assume a proposed change was applied

A model must distinguish:

- **proposed** — replacement text was generated;
- **applied/confirmed** — user says it was applied or the revised Project file is visible;
- **validated** — required tests/commands passed.

Do not build a second patch on top of an unconfirmed first patch when file state matters.

## 7. Validation loop

For agent development, normal minimum:

```bash
python -m pytest
python -m compileall src tests
```

Use focused tests first during iteration, then the full suite before completing the issue.

For work against the real legacy application, use the configured local commands for:

```text
dotnet build
dotnet test
TestComplete/TestExecute
```

Record:

- command;
- pass/fail;
- significant count/timing when useful;
- any intentional skipped validation and why.

Never mark an issue DONE solely because code looks correct.

## 8. Documentation updates required with code

When a task completes:

### Always update

`ISSUES.md`

- status;
- completed date if meaningful;
- validation evidence;
- remaining blocker if PARTIAL.

`CHANGELOG.md`

- issue ID;
- summary;
- changed files;
- validation performed;
- migrations/config/schema implications.

### Update when relevant

`HANDOFF.md` if the change affects:

- architecture;
- SQLite schema/persistent state;
- CLI commands;
- AI provider contract;
- security model;
- TestComplete model;
- major capability/limitation.

`PROJECT_INSTRUCTIONS.md` if the development/security process itself changes.

`DEVELOPMENT_PLAN.md` if dependencies or recommended ordering materially change.

## 9. Security workflow

### Credentials

Never store API keys/tokens/passwords/cert private keys in Project files.

Use environment variables, for example:

```powershell
$env:GENAI_MIL_API_KEY = "..."
```

The user should enter the value locally; it should not be pasted into ChatGPT.

### Endpoint handling

- Use only the authorized GenAI.mil endpoint.
- Require HTTPS.
- Keep explicit `allowed_hosts`.
- Test with `ai-smoke` before source-bearing calls.
- Do not silently fall back to a public AI provider.

### Proprietary source

Do not send legacy application/TestComplete source to public web/API services. Public web research may be used for generic library/documentation questions only when permitted, without including proprietary code/context in the query.

## 10. Manual snapshot discipline

Without GitHub history, use lightweight repository-resident history.

Before a major milestone:

1. Ensure `CHANGELOG.md` reflects all applied changes.
2. Ensure `ISSUES.md` reflects actual status.
3. Download/export the current Project files as a dated snapshot if the product allows it.
4. Record a logical snapshot name in `CHANGELOG.md`, for example:

```text
secure-baseline-2026-09-15
post-testcomplete-parser-v1
pre-production-pilot
```

Do not place secrets or the proprietary target repository into a public/non-secure snapshot.

## 11. Conflict handling without Git

If two versions of a file exist:

1. Identify which was actually used for the last successful validation.
2. Compare required changes from both versions.
3. Build one explicit resolved version.
4. Run relevant tests.
5. Record the resolution in `CHANGELOG.md`.

Never resolve by blindly choosing the newest timestamp.

## 12. Persistent database/schema compatibility

Changes to `db.py` must consider an existing `.modernizer/index.db`.

When adding/changing schema:

- prefer forward migrations;
- add a regression test opening an older schema when feasible;
- document whether re-indexing is required;
- avoid silently discarding task/decision/validation history.

## 13. AI output contracts

Planner/implementer responses should remain structured JSON. Python, not the model, decides whether edits are legal and whether validation succeeded.

The model must not be allowed to:

- choose arbitrary shell commands;
- bypass path restrictions;
- decide to expand task scope after failure;
- mark its own work successful without validation;
- persist credentials;
- disable TestComplete/architecture gates just to obtain green status.

## 14. Real-repository rollout levels

Use explicit trust levels:

### Level 0 — Agent development only

Synthetic fixtures/tests. No real production repo.

### Level 1 — Real repo read-only

Index/search/stats/context/planning. No AI-generated edits.

### Level 2 — Human-applied dry-run proposals

AI proposes bounded changes; human reviews/applies; full validation.

### Level 3 — Agent `--apply` with strict gates

Only after P0 and key safety issues (#14/#12/#13) are complete.

### Level 4 — Bounded automatic repair

Only after Level 3 is stable and Issue #9 safeguards are implemented.

Do not jump directly from Level 1 to Level 4.

## 15. End-of-session checklist

- [ ] Current files reflect all changes discussed.
- [ ] Focused/full tests run as required.
- [ ] `ISSUES.md` updated.
- [ ] `CHANGELOG.md` updated.
- [ ] `HANDOFF.md` updated if capability/architecture changed.
- [ ] Any blocker is explicit rather than hidden in chat history.
- [ ] Next recommended issue/action is clear.