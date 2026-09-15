from __future__ import annotations

import json


def planner_prompt(task, context: str) -> str:
    return f"""You are the planning stage of a conservative legacy C# modernization agent.
You MUST NOT write code in this response.

The system is incrementally modernizing a large WinForms application while preserving behavior.
Existing TestComplete functional tests are an acceptance contract and should remain green.
The target architecture must keep Domain and Application independent of any UI so a future ASP.NET Core/web presentation can use the same behavior.

TASK
Key: {task['task_key']}
Title: {task['title']}
Target: {task['target'] or ''}
Acceptance criteria:
{task['acceptance_criteria']}

CONTEXT
{context}

Return JSON only with this exact top-level shape:
{{
  "summary": "...",
  "behavior_to_preserve": ["..."],
  "files_required": ["relative/path"],
  "symbols_required": ["..."],
  "files_to_change": [{{"path":"relative/path","reason":"..."}}],
  "tests_to_add": ["..."],
  "testcomplete_risks": ["..."],
  "web_portability_notes": ["..."],
  "architectural_decisions": [{{"scope":"...","decision":"...","rationale":"..."}}],
  "risks": ["..."],
  "safe_to_implement": true
}}

Prefer the smallest behavior-preserving change. Never propose a big-bang UI rewrite. Do not move UI concepts below the presentation layer.
"""


def implementer_prompt(task, plan: dict, context: str) -> str:
    return f"""You are the implementation stage of a conservative C# modernization agent.
Apply ONLY the approved bounded task. Preserve existing observable behavior and TestComplete compatibility.

NON-NEGOTIABLE ARCHITECTURE
- Domain must not reference WinForms, ASP.NET, HTTP, MessageBox, controls, filesystem, database, or mutable global UI state.
- Application must not reference WinForms/Razor/HTML/MessageBox or UI controls.
- Application boundaries should use commands, queries, DTOs, typed results, and interfaces suitable for in-process WinForms today and HTTP/web tomorrow.
- New business behavior requires unit tests. Existing behavior should be characterized before refactoring.
- Do not rename/remove UI automation identifiers unless the task explicitly requires it.

TASK
{task['task_key']}: {task['title']}
Acceptance criteria:
{task['acceptance_criteria']}

APPROVED PLAN
{json.dumps(plan, indent=2)}

CONTEXT
{context}

Return JSON only:
{{
  "changes": [
    {{
      "path": "relative/path",
      "operation": "create|replace",
      "old_text": "required exact existing text for replace",
      "new_text": "complete replacement text for replace, or full new file for create"
    }}
  ],
  "validation_notes": ["..."],
  "decisions": [{{"scope":"...","decision":"...","rationale":"..."}}]
}}

Rules:
- For replace, old_text MUST be copied exactly from supplied source and should be the smallest safely unique block.
- Never return whole-file replacement for an existing file unless unavoidable.
- Never create files outside the repository.
- Do not include markdown fences.
"""


def bootstrap_prompt(inventory: str, architecture: str) -> str:
    return f"""You are analyzing a large legacy WinForms C# repository before any code changes.
Create a conservative first migration backlog. Existing TestComplete functional tests are a behavioral acceptance contract. The future system must support a web presentation without duplicating business logic.

ARCHITECTURE RULES
{architecture}

REPOSITORY INVENTORY
{inventory}

Return JSON only with:
{{
 "subsystems": [{{"name":"...","evidence":"...","risk":"low|medium|high"}}],
 "testability_hotspots": ["..."],
 "first_tasks": [
   {{
      "task_key":"MIG-0001",
      "title":"...",
      "target":"symbol or feature",
      "priority":10,
      "acceptance_criteria":"..."
   }}
 ]
}}
Create 10-25 small tasks. Prefer leaf business logic with TestComplete coverage. Do not propose replacing the UI first.
"""
