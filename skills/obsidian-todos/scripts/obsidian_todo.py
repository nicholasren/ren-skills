#!/usr/bin/env python3
"""Capture and manage agent todos in an Obsidian vault via the official Obsidian CLI.

This is a thin orchestrator over the Obsidian CLI's native task primitives:

  daily:append   append a todo to today's daily note
  append         append a todo to a specific dated note
  daily:path     resolve today's daily-note path (and the journal folder)
  tasks          list checkbox tasks (JSON) without re-parsing files ourselves
  task           toggle/complete/restatus a task by file:line

It never rewrites whole notes, so it cannot clobber daily-note content.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys


DEFAULT_OBSIDIAN_CLI = os.environ.get("OBSIDIAN_CLI", "obsidian")
DEFAULT_AGENT_TAG = os.environ.get("OBSIDIAN_TODO_TAG", "#agent-task")
DEFAULT_VIEW = os.environ.get("OBSIDIAN_TODO_VIEW", "Tasks/Task Dashboard.md")

# Obsidian Tasks plugin priority emoji. Kept distinct so the plugin renders them.
PRIORITY_MARKER = {"A": "\U0001f53a", "B": "\U0001f53c", "C": "\U0001f53d", "none": ""}
PRIORITY_ALIASES = {
    "a": "A", "high": "A", "urgent": "A",
    "b": "B", "medium": "B", "normal": "B",
    "c": "C", "low": "C",
    "none": "none", "": "none",
}
DUE_MARKER = "\U0001f4c5"  # 📅 due date (Tasks plugin)

# status word -> Obsidian checkbox character
STATUS_TO_CHAR = {
    "open": " ", "todo": " ",
    "in-progress": "/", "in_progress": "/", "progress": "/", "doing": "/",
    "done": "x", "complete": "x", "completed": "x",
    "blocked": "!", "cancelled": "-", "canceled": "-",
}
CHAR_TO_STATUS = {" ": "open", "/": "in-progress", "x": "done", "X": "done", "!": "blocked", "-": "cancelled"}

BLOCK_ID_RE = re.compile(r"\s\^(?P<id>[A-Za-z0-9_-]+)\s*$")


# --------------------------------------------------------------------------- CLI plumbing

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture and manage agent todos in Obsidian.")
    parser.add_argument(
        "--vault",
        default=os.environ.get("OBSIDIAN_VAULT"),
        help="Target vault NAME (passed to the CLI as vault=<name>). Omit to use the active vault.",
    )
    parser.add_argument(
        "--obsidian-cli",
        default=DEFAULT_OBSIDIAN_CLI,
        help="Obsidian CLI command. Default: OBSIDIAN_CLI or 'obsidian'.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Append a todo to a daily note.")
    add.add_argument("--title", required=True, help="Todo title.")
    add.add_argument("--priority", default="none", help="A, B, C, or none.")
    add.add_argument("--due", help="Due date, YYYY-MM-DD.")
    add.add_argument("--date", help="Daily-note date to append to, YYYY-MM-DD. Default: today.")
    add.add_argument("--source", action="append", default=[], help="Source link or context. Repeatable.")
    add.add_argument("--dry-run", action="store_true", help="Print the intended command without running it.")

    update = sub.add_parser("update", help="Change a todo's status by id, text match, or ref.")
    sel = update.add_mutually_exclusive_group(required=True)
    sel.add_argument("--id", help="Block id appended to the task, e.g. agent-20260627-ab12cd34.")
    sel.add_argument("--match", help="Unique substring of the task text.")
    sel.add_argument("--ref", help="Exact task reference, path:line.")
    update.add_argument("--status", help="open, in-progress, done, blocked, cancelled.")
    update.add_argument("--toggle", action="store_true", help="Toggle done/not-done.")
    update.add_argument("--dry-run", action="store_true", help="Print the intended command without running it.")

    lst = sub.add_parser("list", help="List agent todos.")
    lst.add_argument("--status", action="append", help="Filter by status. Repeatable. (open/in-progress/done/...)")
    lst.add_argument("--all", action="store_true", help="Include tasks without the agent tag.")
    lst.add_argument("--json", action="store_true", help="Print JSON instead of a table.")

    view = sub.add_parser("view", help="Write a Tasks-plugin dashboard note covering all tasks.")
    view.add_argument("--output", default=DEFAULT_VIEW, help=f"View note path. Default: {DEFAULT_VIEW}")
    view.add_argument("--dry-run", action="store_true", help="Print the note instead of writing it.")

    doctor = sub.add_parser("doctor", help="Check that prerequisites are set up; print fixes for anything missing.")
    doctor.add_argument("--fix", action="store_true", help="Attempt safe fixes (e.g. install the Tasks plugin).")

    return parser.parse_args(argv)


def cli_base(args: argparse.Namespace) -> list[str]:
    parts = shlex.split(args.obsidian_cli)
    if not parts:
        raise SystemExit("Obsidian CLI command cannot be empty.")
    if args.vault:
        parts.append(f"vault={args.vault}")
    return parts


NOISE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} Loading updated app package |"
    r"^Your Obsidian installer is out of date"
)


def run_cli(args: argparse.Namespace, cli_args: list[str], *, check: bool = True) -> str:
    completed = subprocess.run(cli_base(args) + cli_args, text=True, capture_output=True)
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"
        raise SystemExit(
            f"Obsidian CLI failed ({' '.join(cli_args[:1])}): {detail}\n"
            "Is the Obsidian app running and the vault open?"
        )
    return "\n".join(line for line in completed.stdout.splitlines() if not NOISE_RE.match(line))


# --------------------------------------------------------------------------- helpers

def single_line(text: str) -> str:
    return " ".join(text.split()).strip()


def parse_date(value: str) -> str:
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise SystemExit(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


def normalize_priority(value: str | None) -> str:
    key = (value or "none").strip().lower()
    if key not in PRIORITY_ALIASES:
        raise SystemExit("Priority must be A, B, C, high, medium, low, or none.")
    return PRIORITY_ALIASES[key]


def normalize_status(value: str) -> str:
    key = value.strip().lower()
    if key not in STATUS_TO_CHAR:
        raise SystemExit(f"Unknown status '{value}'. Use open, in-progress, done, blocked, or cancelled.")
    return key


def generate_block_id(title: str, sources: list[str]) -> str:
    today = dt.date.today().strftime("%Y%m%d")
    seed = f"{dt.datetime.now().isoformat()}|{title}|{'|'.join(sources)}"
    return f"agent-{today}-{hashlib.sha1(seed.encode()).hexdigest()[:8]}"


def build_task_line(title: str, priority: str, due: str | None, block_id: str) -> str:
    parts = [single_line(title)]
    marker = PRIORITY_MARKER[priority]
    if marker:
        parts.append(marker)
    if due:
        parts.append(f"{DUE_MARKER} {due}")
    parts.extend([DEFAULT_AGENT_TAG, f"^{block_id}"])
    return f"- [ ] {' '.join(parts)}"


def journal_folder(args: argparse.Namespace) -> str:
    path = single_line(run_cli(args, ["daily:path"]))
    return path.rsplit("/", 1)[0] if "/" in path else ""


# --------------------------------------------------------------------------- commands

def add_command(args: argparse.Namespace) -> int:
    title = single_line(args.title)
    if not title:
        raise SystemExit("Title cannot be empty.")
    priority = normalize_priority(args.priority)
    due = parse_date(args.due) if args.due else None
    date = parse_date(args.date) if args.date else None
    sources = [single_line(s) for s in args.source if single_line(s)]
    block_id = generate_block_id(title, sources)

    content = build_task_line(title, priority, due, block_id)
    for source in sources:
        content += f"\n  - source: {source}"

    if date and date != dt.date.today().isoformat():
        folder = journal_folder(args)
        note = f"{folder}/{date}.md" if folder else f"{date}.md"
        cli_args = ["append", f"path={note}", f"content={content}"]
        target = note
    else:
        cli_args = ["daily:append", f"content={content}"]
        target = "today's daily note"

    if args.dry_run:
        print(f"Would append to {target}:")
        print(content)
        return 0

    run_cli(args, cli_args)
    print(f"Added ^{block_id} to {target}")
    print(content.splitlines()[0])
    return 0


def fetch_tasks(args: argparse.Namespace, *, agent_only: bool = True) -> list[dict]:
    out = run_cli(args, ["tasks", "format=json"]).strip()
    tasks = json.loads(out) if out else []
    for task in tasks:
        text = task.get("text", "")
        id_match = BLOCK_ID_RE.search(text)
        task["id"] = id_match.group("id") if id_match else ""
        task["status_word"] = CHAR_TO_STATUS.get(task.get("status", " "), "open")
        task["ref"] = f"{task.get('file', '')}:{task.get('line', '')}"
    if agent_only:
        tasks = [t for t in tasks if DEFAULT_AGENT_TAG in t.get("text", "")]
    return tasks


def resolve_ref(args: argparse.Namespace) -> str:
    if args.ref:
        return args.ref
    # Resolve --id / --match against agent-managed todos only, so a common word
    # does not collide with the hundreds of unrelated tasks elsewhere in the vault.
    tasks = fetch_tasks(args, agent_only=True)
    if args.id:
        matches = [t for t in tasks if t["id"] == args.id]
        label = f"id {args.id}"
    else:
        needle = args.match.lower()
        matches = [t for t in tasks if needle in t["text"].lower()]
        label = f"match {args.match!r}"
    if not matches:
        raise SystemExit(f"No task found for {label}.")
    if len(matches) > 1:
        listing = "\n".join(f"  {t['ref']}  {t['text']}" for t in matches)
        raise SystemExit(f"{label} is ambiguous ({len(matches)} matches):\n{listing}\nUse --ref path:line.")
    return matches[0]["ref"]


def update_command(args: argparse.Namespace) -> int:
    if not args.status and not args.toggle:
        raise SystemExit("Provide --status or --toggle.")
    ref = resolve_ref(args)
    cli_args = ["task", f"ref={ref}"]
    if args.toggle:
        cli_args.append("toggle")
    else:
        status = normalize_status(args.status)
        cli_args.append(f'status={STATUS_TO_CHAR[status]}')

    if args.dry_run:
        print(f"Would run: task {' '.join(cli_args[1:])}")
        return 0

    print(single_line(run_cli(args, cli_args)) or f"Updated {ref}")
    return 0


def list_command(args: argparse.Namespace) -> int:
    tasks = fetch_tasks(args, agent_only=not args.all)
    if args.status:
        allowed = {normalize_status(s) for s in args.status}
        tasks = [t for t in tasks if t["status_word"] in allowed]

    if args.json:
        print(json.dumps(tasks, indent=2))
        return 0

    if not tasks:
        print("No agent todos found.")
        return 0
    print(f"{'STATUS':<12} {'REF':<28} TASK")
    for t in sorted(tasks, key=lambda t: (t["status_word"] != "in-progress", t["status_word"] == "done", t["ref"])):
        text = re.sub(r"^- \[.\]\s*", "", t["text"])
        print(f"{t['status_word']:<12} {t['ref']:<28} {text}")
    return 0


def view_command(args: argparse.Namespace) -> int:
    # Includes every task in the vault — yours and agent-captured alike — so this
    # is a general dashboard, not an agent-only view. No #agent-task filter.
    # "Most recent first": daily-note tasks carry their date in the path
    # (Journals/YYYY-MM-DD.md), so `sort by path reverse` floats the newest to
    # the top. A secondary line-number sort puts later-added tasks above earlier
    # ones within the same note.
    content = (
        "# Task Dashboard\n\n"
        "_Live view of all tasks in the vault, most recent first. Requires the Obsidian Tasks plugin._\n\n"
        "## In progress\n\n"
        "```tasks\n"
        "status.type is IN_PROGRESS\n"
        "sort by path reverse\n"
        "sort by function task.lineNumber reverse\n"
        "```\n\n"
        "## Open\n\n"
        "```tasks\n"
        "not done\n"
        "status.type is not IN_PROGRESS\n"
        "sort by path reverse\n"
        "sort by function task.lineNumber reverse\n"
        "```\n\n"
        "## Done recently\n\n"
        "```tasks\n"
        "done\n"
        "sort by done reverse\n"
        "limit 25\n"
        "```\n"
    )
    if args.dry_run:
        print(content)
        return 0
    run_cli(args, ["create", f"path={args.output}", f"content={content}", "overwrite"])
    print(f"Wrote task dashboard: {args.output}")
    return 0


def default_cli_candidates() -> list[str]:
    system = platform.system()
    if system == "Darwin":
        return [
            "/Applications/Obsidian.app/Contents/MacOS/obsidian",
            os.path.expanduser("~/Applications/Obsidian.app/Contents/MacOS/obsidian"),
        ]
    if system == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        return [os.path.join(local, "Obsidian", "Obsidian.exe")] if local else []
    return []  # Linux: rely on `obsidian` being on PATH


def probe(parts: list[str], cli_args: list[str], vault: str | None, timeout: int = 15):
    """Run a CLI command, returning (ok, output) or None if the binary is missing."""
    cmd = list(parts) + ([f"vault={vault}"] if vault else []) + cli_args
    try:
        done = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except subprocess.TimeoutExpired:
        return (False, "<timed out — is Obsidian running with the vault open?>")
    out = "\n".join(line for line in done.stdout.splitlines() if not NOISE_RE.match(line)).strip()
    # The CLI exits 0 even for unknown commands, so treat an "Error:" body as failure.
    ok = bool(out) and not out.startswith("Error:")
    return (ok, out or done.stderr.strip())


def doctor_command(args: argparse.Namespace) -> int:
    print("Obsidian Todos — setup check\n")
    failures = 0

    # 1. Resolve a working CLI: the configured one first, then per-OS app paths.
    #    Distinguish "binary missing" (probe -> None) from "binary present but the
    #    app didn't respond" (probe -> (False, ...)), since the fixes differ.
    requested = shlex.split(args.obsidian_cli)
    candidates: list[list[str]] = [requested] + [[c] for c in default_cli_candidates() if [c] != requested]
    print("(checking — this can take a few seconds while it reaches the Obsidian app)\n")
    cli_parts: list[str] | None = None
    enabled = ""
    unresponsive: tuple[list[str], str] | None = None
    for parts in candidates:
        result = probe(parts, ["plugins:enabled"], args.vault)
        if result is None:
            continue  # binary not found at this path
        ok, body = result
        if ok:
            cli_parts, enabled = parts, body
            break
        if unresponsive is None:
            unresponsive = (parts, body)

    if not cli_parts:
        failures += 1
        if unresponsive:
            parts, body = unresponsive
            print(f"✗ Obsidian not responding — found the CLI at `{' '.join(parts)}`, but the app didn't answer.")
            print(f"  Detail: {body}")
            print("  • Launch Obsidian and open your vault, then re-run `doctor`.")
        else:
            print("✗ Obsidian CLI — not found on this machine.")
            print("  • Install Obsidian 1.12+ (its CLI ships in the app): https://obsidian.md/download")
            print("  • Then point at the binary, e.g. on macOS:")
            print('      export OBSIDIAN_CLI="/Applications/Obsidian.app/Contents/MacOS/obsidian"')
        print("\nResult: not ready. Fix the issue above, then re-run `doctor`.")
        return 1

    shown = " ".join(cli_parts)
    print(f"✓ Obsidian CLI — reachable via `{shown}`.")
    if shown != "obsidian":
        print(f"  Tip: persist this with  export OBSIDIAN_CLI=\"{shown}\"")

    enabled_ids = set(enabled.split())

    # 2. Daily notes core plugin (needed for capture).
    if "daily-notes" in enabled_ids:
        path = probe(cli_parts, ["daily:path"], args.vault)
        where = path[1] if path and path[0] else "(unknown)"
        print(f"✓ Daily notes — enabled. Today resolves to: {where}")
    else:
        failures += 1
        print("✗ Daily notes core plugin — disabled.")
        print("  • Enable it in Obsidian: Settings → Core plugins → Daily notes.")

    # 3. Tasks community plugin (needed only for the dashboard to render).
    if "obsidian-tasks-plugin" in enabled_ids:
        print("✓ Obsidian Tasks plugin — installed and enabled.")
    elif args.fix:
        res = probe(cli_parts, ["plugin:install", "id=obsidian-tasks-plugin", "enable"], args.vault)
        if res and ("already installed" in res[1] or res[0]):
            print("✓ Obsidian Tasks plugin — installed via --fix.")
        else:
            print("! Obsidian Tasks plugin — install attempt unclear; check Obsidian.")
    else:
        print("! Obsidian Tasks plugin — not enabled (capture/list/update still work).")
        print("  • The task dashboard won't render as live tables without it.")
        print(f"  • Install:  {shown} plugin:install id=obsidian-tasks-plugin enable")
        print("    or re-run:  doctor --fix")

    # 4. Vault confirmation.
    print(f"\nVault: {'--vault ' + args.vault if args.vault else 'active vault (the one open in Obsidian)'}")
    if not args.vault and not os.environ.get("OBSIDIAN_VAULT"):
        print("  Note: commands target whichever vault is active in Obsidian. Pass --vault \"<name>\" to pin it.")

    print("\nResult: " + ("ready to capture todos." if failures == 0 else f"{failures} blocking issue(s) above — fix and re-run `doctor`."))
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    return {
        "add": add_command,
        "update": update_command,
        "list": list_command,
        "view": view_command,
        "doctor": doctor_command,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
