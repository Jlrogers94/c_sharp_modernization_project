# Repository Map for Flattened ChatGPT Project Uploads

This file maps the **real repository path** of every current project file to the filename that should be used when uploading into a ChatGPT Project that does not preserve folder structure.

After the secure-project transfer, this file is authoritative for translating between flattened Project filenames and real repository paths. Do not infer a path from a flattened filename when this file provides the mapping.

## Naming convention

1. Folder separators `/` become `__` in the uploaded filename.
2. Root-level files keep their normal basename.
3. If ChatGPT does not accept a source/config extension, append `.txt` **without changing the file contents**.
4. A trailing `.txt` used this way is an upload-only wrapper and is not part of the real repository filename.
5. Always refer to the **real repository path** in change instructions, changelog entries, issue notes, and local filesystem commands.
6. Do not mechanically split a flattened filename on `__` when a basename itself contains double underscores (for example `__init__.py`). Use this map.

Examples:

```text
src/modernizer_agent/config.py
  -> src__modernizer_agent__config.py

examples/modernizer.toml
  -> examples__modernizer.toml.txt

pyproject.toml
  -> pyproject.toml.txt
```

When an AI proposes an updated `examples__modernizer.toml.txt`, the user should copy its contents back to the real local path `examples/modernizer.toml`.

## Current file map

| Real repository path | ChatGPT Project upload filename |
| --- | --- |
| `.gitignore` | `.gitignore.txt` |
| `CHANGELOG.md` | `CHANGELOG.md` |
| `DEVELOPMENT_PLAN.md` | `DEVELOPMENT_PLAN.md` |
| `HANDOFF.md` | `HANDOFF.md` |
| `ISSUES.md` | `ISSUES.md` |
| `PROJECT_INSTRUCTIONS.md` | `PROJECT_INSTRUCTIONS.md` |
| `README.md` | `README.md` |
| `REPOSITORY_MAP.md` | `REPOSITORY_MAP.md` |
| `SECURE_WORKFLOW.md` | `SECURE_WORKFLOW.md` |
| `examples/modernizer.toml` | `examples__modernizer.toml.txt` |
| `pyproject.toml` | `pyproject.toml.txt` |
| `src/modernizer_agent/__init__.py` | `src__modernizer_agent____init__.py` |
| `src/modernizer_agent/__main__.py` | `src__modernizer_agent____main__.py` |
| `src/modernizer_agent/ai.py` | `src__modernizer_agent__ai.py` |
| `src/modernizer_agent/cli.py` | `src__modernizer_agent__cli.py` |
| `src/modernizer_agent/config.py` | `src__modernizer_agent__config.py` |
| `src/modernizer_agent/context.py` | `src__modernizer_agent__context.py` |
| `src/modernizer_agent/csharp.py` | `src__modernizer_agent__csharp.py` |
| `src/modernizer_agent/db.py` | `src__modernizer_agent__db.py` |
| `src/modernizer_agent/orchestrator.py` | `src__modernizer_agent__orchestrator.py` |
| `src/modernizer_agent/patcher.py` | `src__modernizer_agent__patcher.py` |
| `src/modernizer_agent/prompts.py` | `src__modernizer_agent__prompts.py` |
| `src/modernizer_agent/scanner.py` | `src__modernizer_agent__scanner.py` |
| `src/modernizer_agent/templates.py` | `src__modernizer_agent__templates.py` |
| `src/modernizer_agent/testcomplete.py` | `src__modernizer_agent__testcomplete.py` |
| `src/modernizer_agent/validator.py` | `src__modernizer_agent__validator.py` |
| `tests/test_ai.py` | `tests__test_ai.py` |
| `tests/test_csharp.py` | `tests__test_csharp.py` |
| `tests/test_db.py` | `tests__test_db.py` |
| `tests/test_incremental_indexing.py` | `tests__test_incremental_indexing.py` |
| `tests/test_patcher.py` | `tests__test_patcher.py` |
| `tests/test_testcomplete.py` | `tests__test_testcomplete.py` |

## Upload checklist

Before starting development in the secure Project:

- Upload every file in the table above.
- Rename files to the upload filenames shown above before upload.
- Do not alter file contents just to make them uploadable.
- Confirm `REPOSITORY_MAP.md`, `PROJECT_INSTRUCTIONS.md`, `HANDOFF.md`, `ISSUES.md`, `DEVELOPMENT_PLAN.md`, `SECURE_WORKFLOW.md`, and `CHANGELOG.md` are visible in the Project.
- Paste the contents of `PROJECT_INSTRUCTIONS.md` into the Project Instructions field.
- Complete `SEC-001` in `ISSUES.md` before additional implementation work.

## When files are added or removed later

Any change that creates, deletes, or renames a repository file must update this map in the same change set.

For a new path:

```text
folder/subfolder/file.ext
```

use:

```text
folder__subfolder__file.ext
```

and append `.txt` only when required by ChatGPT upload restrictions.

If a future filename makes the flattening convention ambiguous, add an explicit mapping here rather than inventing a second implicit rule.
