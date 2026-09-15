from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import AgentConfig
from .ai import GeminiClient, parse_json_response
from .db import Database
from .orchestrator import ModernizerAgent
from .templates import initialize_repo


def dump(value) -> None:
    print(json.dumps(value, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="modernizer", description="Conservative local C# modernization agent")
    p.add_argument("--repo", default=".", help="Legacy repository root")
    p.add_argument("--config", default=None, help="Path to modernizer.toml")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create modernizer.toml and .modernizer architecture rules")
    sub.add_parser("index", help="Index C#, projects and TestComplete artifacts")
    sub.add_parser("stats", help="Show local index statistics")
    sub.add_parser("ai-smoke", help="Send a harmless fixed prompt to verify the configured AI endpoint; no repository source is included")

    s = sub.add_parser("search", help="Search indexed code")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=20)

    t = sub.add_parser("create-task", help="Create/update one bounded migration task")
    t.add_argument("task_key")
    t.add_argument("title")
    t.add_argument("--target", default=None)
    t.add_argument("--priority", type=int, default=100)
    t.add_argument("--criteria", default="Build, unit tests and configured TestComplete tests pass; observable behavior is preserved.")

    sub.add_parser("bootstrap-plan", help="Ask Gemini for the first conservative migration backlog")

    pt = sub.add_parser("plan-task", help="Plan one task without writing code")
    pt.add_argument("task_key")

    rt = sub.add_parser("run-task", help="Generate a bounded patch; dry-run by default")
    rt.add_argument("task_key")
    rt.add_argument("--apply", action="store_true", help="Actually apply the patch and run validation")
    rt.add_argument("--skip-functional", action="store_true", help="Skip TestComplete commands for this run")

    rn = sub.add_parser("run-next", help="Run the next pending task")
    rn.add_argument("--apply", action="store_true")
    rn.add_argument("--skip-functional", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.repo).resolve()
    if args.command == "init":
        created = initialize_repo(root)
        dump({"created": [str(x.relative_to(root)) for x in created], "repo": str(root)})
        return 0

    config = AgentConfig.load(root, args.config)
    if args.command == "ai-smoke":
        try:
            text = GeminiClient(config).complete(
                'Return only this JSON object: {"status":"ok"}', json_mode=True
            )
            parsed = parse_json_response(text)
            if not isinstance(parsed, dict) or parsed.get("status") != "ok":
                raise RuntimeError("AI smoke response did not contain the expected status")
            dump({"status": "ok", "provider": config.gemini.api_style, "model": config.gemini.model})
            return 0
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    if args.command in {"stats", "search", "create-task"}:
        db = Database(config.db_path)
        try:
            if args.command == "stats":
                dump(db.stats())
            elif args.command == "search":
                dump([dict(r) for r in db.search(args.query, args.limit)])
            else:
                db.create_task(args.task_key, args.title, args.target, args.priority, args.criteria)
                dump({"task": args.task_key, "status": "PENDING"})
            return 0
        finally:
            db.close()

    agent = ModernizerAgent(config)
    try:
        if args.command == "index":
            dump(agent.index())
        elif args.command == "bootstrap-plan":
            dump(agent.bootstrap_plan())
        elif args.command == "plan-task":
            dump(agent.plan_task(args.task_key))
        elif args.command == "run-task":
            dump(agent.run_task(args.task_key, apply=args.apply, run_functional=not args.skip_functional))
        elif args.command == "run-next":
            task = agent.db.next_task()
            if task is None:
                dump({"status": "NO_PENDING_TASKS"})
            else:
                dump(agent.run_task(task["task_key"], apply=args.apply, run_functional=not args.skip_functional))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        agent.close()


if __name__ == "__main__":
    raise SystemExit(main())
