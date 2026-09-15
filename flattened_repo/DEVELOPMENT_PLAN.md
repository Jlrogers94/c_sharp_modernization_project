# Development Plan

This is the recommended implementation sequence after moving the modernization-agent project into a secure ChatGPT Project with no GitHub connectivity.

The plan intentionally delays high-autonomy behavior until indexing, TestComplete understanding, architecture checks, and safety guardrails are trustworthy on the real repository.

## Phase 0 — Secure-project bootstrap

### Objective

Establish a trustworthy local baseline after the file-by-file transfer.

### Work

1. Upload every repository file listed in `HANDOFF.md`.
2. Paste `PROJECT_INSTRUCTIONS.md` into the ChatGPT Project Instructions field.
3. Confirm `ISSUES.md`, `HANDOFF.md`, `DEVELOPMENT_PLAN.md`, `SECURE_WORKFLOW.md`, and `CHANGELOG.md` are available as Project files.
4. Create a fresh Python virtual environment.
5. Install with development dependencies.
6. Run the complete Python test suite and compile check.
7. Resolve any integration regression between incremental indexing and GenAI.mil support.
8. Record the new secure baseline in `CHANGELOG.md`.

### Gate

Do not begin new feature implementation until **SEC-001** is complete.

---

## Phase 1 — Finish P0 environment integration

### 1A. Finish GenAI.mil integration (#2)

Use the API page in the authorized environment to confirm:

- exact `/chat/completions`-style endpoint URL;
- API-key header/scheme;
- available model ID;
- any gateway-specific token/JSON restrictions.

Set the key only as an environment variable. Run `ai-smoke` first. Then exercise the actual planner and implementer JSON contracts with a synthetic/non-sensitive fixture before sending production source.

### 1B. Tune TestComplete parser (#3)

Obtain representative real artifacts:

```text
*.pjs
*.mds
*.tcNM
*.tcKDTest
script-test files used by the suite
```

Build fixtures from the real structure while removing business-sensitive values where appropriate. Make the parser reflect project hierarchy, enabled test items, Name Mapping aliases/object criteria, and script/keyword references.

### 1C. Complete real indexing benchmark (#4)

On a current real checkout:

1. cold index;
2. unchanged second index;
3. edit/touch one representative C# file and index;
4. optional worker-count comparison if allowed.

Record scan metrics and choose a conservative default worker count based on evidence, not assumption.

### 1D. Read-only production pilot (#5)

Run only discovery/planning commands. Establish:

- project and LOC inventory;
- symbol/reference plausibility;
- TestComplete inventory;
- build baseline;
- functional baseline;
- at least 10 reviewed candidate migration slices.

No AI-generated source edits during this phase.

### Gate

Do not allow meaningful production `--apply` usage until the P0 inventory/baseline is credible.

---

## Phase 2 — Strengthen safety before autonomy

These issues are nominally P1 but should precede large-scale applied migration.

### 2A. Patch/command/secret guardrails (#14)

Add:

- validation-command allowlisting;
- protected path policy;
- maximum file/line-change thresholds;
- stronger path validation everywhere;
- stale-plan/base checks;
- secret-redaction safeguards;
- human-only unsafe overrides.

### 2B. Executable architecture checks (#12)

Implement layer classification and rules that block new Domain/Application leakage from WinForms/UI, SQL, filesystem, network, and problematic global state. Apply strict enforcement to new/modernized layers without making all legacy code fail immediately.

### 2C. Characterization/differential workflows (#13)

Build repeatable task templates that capture current behavior before replacing it. For deterministic business logic, support old-vs-new differential execution.

### Gate

An applied migration should have machine-enforced scope, architecture, and behavioral evidence before automatic repair is enabled.

---

## Phase 3 — Improve repository intelligence

### 3A. Roslyn semantic index (#6)

Tree-sitter remains the fast syntax layer. Add an optional .NET helper using Roslyn to resolve:

- overload identity;
- callers/callees;
- interface implementations;
- inheritance;
- extension methods;
- partial classes;
- constructor dependencies;
- cross-project relationships.

Design it as a subprocess emitting JSON so Python remains the orchestrator.

### 3B. Hierarchical summaries/context ranking (#7)

Add content-hash-keyed summaries at symbol/file/project levels. Context policy should become:

```text
target source                    -> full
critical direct dependencies     -> full or focused symbol blocks
related tests/TestComplete       -> focused/full as needed
secondary dependencies           -> summaries
architectural decisions/rules    -> compact always-on context
```

Move from character-only clipping toward token/model-aware budgets.

### 3C. Targeted TestComplete mapping (#8)

Once #3 is accurate, link code/forms/features to TestComplete scenarios. Support targeted validation with confidence-based escalation to a broader/full suite.

### 3D. Risk-aware task scheduler (#10)

Add task dependencies, migration slices, and reproducible risk scoring. Prefer low-risk leaf logic and characterization tasks ahead of UI/data orchestration.

---

## Phase 4 — Add controlled repair and operational maturity

### 4A. Bounded repair loops (#9)

Only after Phase 2 safety is in place. Repairs must:

- remain within original scope;
- have a hard attempt cap;
- stop on repeated identical failures;
- stop on architecture/safety violations;
- persist attempt history;
- end in `BLOCKED` rather than widening scope autonomously.

### 4B. Reporting/history (#15)

Add CLI/Markdown/JSON reporting for task status, validation history, decisions, blocked work, and next recommendations.

### 4C. Agent quality automation (#16)

Use whatever secure/internal mechanism is available. At minimum create a local repeatable quality command/script that runs:

- pytest;
- compileall;
- formatter/linter if approved;
- type checking if approved;
- package/CLI smoke.

Do not assume GitHub Actions will be available.

### 4D. Target-repository source-control integration (#11)

If the work repository has local Git, use it for isolated task history. If not, implement/document a restricted fallback. This issue is independent of the ChatGPT Project's lack of GitHub access.

---

## Phase 5 — First real migration slices

Choose low-risk vertical slices from the Issue #5 pilot.

Recommended first candidates have most of these traits:

- deterministic/pure calculation or validation;
- few external side effects;
- limited UI coupling;
- clear existing TestComplete scenario or easily created characterization test;
- modest dependency fan-in/fan-out;
- obvious Application/Domain destination.

For each slice:

1. characterize behavior;
2. create/extract Domain/Application logic;
3. keep WinForms calling the extracted use case;
4. run unit/integration/TestComplete validation;
5. record architecture decisions;
6. re-index;
7. update backlog/reporting.

Avoid starting with a full screen rewrite or web UI replacement.

---

## Phase 6 — Web-portability proof (#17)

After several stable migrations, choose one representative feature already extracted to Application/Domain.

Add:

- minimal ASP.NET Core endpoint;
- minimal web presentation (Blazor is the default candidate unless the work environment suggests otherwise);
- stable automation IDs;
- matching web TestComplete scenario.

Prove that desktop and web invoke the same use case/business rules.

Use the result to confirm or revise the long-term web-stack choice.

---

## Recommended dependency order

```text
SEC-001
   |
   +--> #2 real endpoint verification
   +--> #3 real TestComplete parsing
   +--> #4 benchmark
             |
             +--> #5 read-only pilot
                       |
                       +--> #14 safety
                       +--> #12 architecture checks
                       +--> #13 characterization
                                 |
                                 +--> #6 semantic graph
                                 +--> #7 context quality
                                 +--> #8 targeted TestComplete
                                 +--> #10 risk scheduling
                                           |
                                           +--> #9 bounded repair
                                           +--> first applied slices
                                                     |
                                                     +--> #17 web proof

#15/#16/#11 can advance alongside later phases as environment capability permits.
```

## Stop conditions

A future AI/model should stop and request human review rather than broadening work when:

- a task requires credentials/secrets;
- source classification/handling rules are unclear;
- the required file is missing from the Project;
- the real build/TestComplete baseline is already failing for unrelated reasons;
- proposed changes exceed task scope or patch thresholds;
- architecture would require a major one-shot rewrite;
- provider responses are truncated/malformed repeatedly;
- model context appears insufficient to preserve behavior;
- repair attempts repeat the same failure.

The project succeeds by completing many verified small migrations, not by maximizing unattended code volume.