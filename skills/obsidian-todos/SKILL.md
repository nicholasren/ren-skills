---
name: obsidian-todos
description: Capture work as todos into Obsidian daily notes and manage their status, using the official Obsidian CLI's native task commands. Use when a user asks to capture a todo, log a task to Obsidian, mark a todo done or in-progress, list outstanding todos, refresh the task dashboard, or set up / verify the Obsidian todos integration on a machine.
---

# Obsidian Todos

## Overview

Capture the user's work as todos in their Obsidian vault and manage those todos over time. The bundled `scripts/obsidian_todo.py` is a thin orchestrator over the **official Obsidian CLI** (the `obsidian` command shipped inside the Obsidian app). It uses the CLI's native task primitives — `daily:append`, `tasks`, `task` — so it never rewrites whole notes and cannot clobber daily-note content.

Use the script rather than editing vault files directly, so task format, the `#agent-task` tag, and priorities stay consistent.

Two scopes matter:

- **Managed todos** — the ones this skill captures and updates. They carry the `#agent-task` tag and a `^agent-…` block id, and `list`/`update` operate only on these, so the agent never mutates a task the user wrote by hand.
- **The task dashboard** (`view`) — a shared, read-only overview of **all** tasks in the vault, the user's and the agent's alike. It is not filtered to `#agent-task`.

## Prerequisites

- **Obsidian app with CLI support** (v1.12+). The CLI is the app binary itself. If `obsidian` is not on `PATH`, point at it with `OBSIDIAN_CLI`, e.g. on macOS:
  `OBSIDIAN_CLI="/Applications/Obsidian.app/Contents/MacOS/obsidian"`.
- **Obsidian must be running** with the target vault open; the CLI talks to the live app.
- **Obsidian Tasks community plugin** — required only for the task dashboard (`view`) to render as live tables and for priority/due emoji to display richly. Capture, list, and update work without it. Install once:
  `obsidian plugin:install id=obsidian-tasks-plugin enable`.

## Setup on a new machine

Before the first capture on an unfamiliar machine, run the built-in check and let it guide the user:

```bash
python3 scripts/obsidian_todo.py doctor          # report status + fixes
python3 scripts/obsidian_todo.py doctor --fix    # also install the Tasks plugin if missing
```

`doctor` verifies each prerequisite and prints the exact remediation for anything missing:

1. **Obsidian CLI reachable** — tries `obsidian` on `PATH`, then the per-OS app binary. If found at a non-`PATH` location it prints the `export OBSIDIAN_CLI=…` line to make it stick.
2. **Daily notes core plugin** — needed for capture; shows where today's note resolves.
3. **Obsidian Tasks plugin** — a soft check (only the dashboard needs it); `--fix` installs it.
4. **Vault** — reports whether it's targeting the active vault or a pinned `--vault`.

The agent's job: run `doctor`, read the ✓/✗/! lines, and walk the user through each fix (install Obsidian, launch it with the vault open, set `OBSIDIAN_CLI`, enable Daily notes) until the result is "ready to capture todos." It exits non-zero while any blocking issue remains, so it's safe to gate captures on it.

## Vault selection

Do **not** guess the vault path. If the user has not told you which vault to use and it is not configured, ask them.

The CLI operates on the **active vault** by default. To target another vault by name, pass `--vault "<Vault Name>"` (or set `OBSIDIAN_VAULT`), which the script forwards as `vault=<name>` to the CLI.

## Configuration

| Setting | Default | Override |
|---|---|---|
| Obsidian CLI command | `obsidian` | `OBSIDIAN_CLI` or `--obsidian-cli` |
| Target vault | active vault | `OBSIDIAN_VAULT` or `--vault` |
| Task tag | `#agent-task` | `OBSIDIAN_TODO_TAG` |
| Task dashboard note | `Tasks/Task Dashboard.md` | `OBSIDIAN_TODO_VIEW` or `--output` |

Daily-note location and date format come from the vault itself via `obsidian daily:path`; the script does not need to read `.obsidian/daily-notes.json`.

## Workflow

1. Translate the user's request into a concise task title.
2. Choose a priority only from explicit or strongly implied intent:
   - `A`: urgent / high priority.
   - `B`: important current work.
   - `C`: nice-to-have or follow-up.
   - `none`: unclear (default).
3. Add a `--due YYYY-MM-DD` only if the user gave or clearly implied a deadline.
4. Preserve useful context with `--source` (issue, PR, chat, doc, or design links). Do not invent sources.
5. Run `scripts/obsidian_todo.py add`. It appends to the **end** of today's daily note via `daily:append`.
6. Report the created task id (`^agent-…`) so the user — or a later `update` — can address it.

## Commands

Run from this skill directory. On macOS, prefix with the CLI path if `obsidian` is not on `PATH`:

```bash
export OBSIDIAN_CLI="/Applications/Obsidian.app/Contents/MacOS/obsidian"
```

**Capture a todo** (appends to today's daily note):

```bash
python3 scripts/obsidian_todo.py add \
  --title "Follow up on project risks" \
  --priority B \
  --due 2026-07-01 \
  --source "weekly 1:1"
```

Capture to a specific past/future day with `--date YYYY-MM-DD`. Preview without writing with `--dry-run`.

**Update a todo's status** — address it by stable block id, by a unique text match, or by exact `path:line`:

```bash
python3 scripts/obsidian_todo.py update --id agent-20260627-ab12cd34 --status done
python3 scripts/obsidian_todo.py update --match "project risks" --status in-progress
python3 scripts/obsidian_todo.py update --ref "Journals/2026-06-27.md:12" --toggle
```

Statuses: `open`, `in-progress`, `done`, `blocked`, `cancelled`. `--toggle` flips done/not-done. A non-unique `--match` fails and lists the candidates so you can pick a `--ref`.

**List agent todos** (defaults to a terminal table; `--json` for machine output):

```bash
python3 scripts/obsidian_todo.py list
python3 scripts/obsidian_todo.py list --status open --status in-progress
python3 scripts/obsidian_todo.py list --all   # include non-agent tasks
```

**Refresh the task dashboard** (writes an Obsidian Tasks query note covering **all** tasks in the vault — yours and agent-captured alike, not filtered to `#agent-task`):

```bash
python3 scripts/obsidian_todo.py view
```

This note renders as live tables only with the Tasks plugin installed.

## Task format

Each captured todo is a standard Markdown checkbox the Obsidian Tasks plugin recognizes:

```md
- [ ] Follow up on project risks 🔼 📅 2026-07-01 #agent-task ^agent-20260627-ab12cd34
  - source: weekly 1:1
```

- Status uses Obsidian checkbox characters: `open` `[ ]`, `in-progress` `[/]`, `done` `[x]`, `blocked` `[!]`, `cancelled` `[-]`.
- Priority emoji (Tasks plugin): `A` 🔺, `B` 🔼, `C` 🔽; `none` omits the marker.
- Due date uses the Tasks plugin 📅 marker.
- `#agent-task` tags todos this skill manages; `^agent-…` is a stable block id for addressing the task later.

## Guardrails

- Never guess the vault. If it is unknown, ask the user.
- Do not require the Obsidian Local REST API; this skill uses only the official CLI.
- Do not write vault files directly. Capture via `daily:append`/`append` and change status via the native `task` command; only the generated task dashboard note is created with `overwrite`.
- Do not invent source links. If the user gives none, omit `--source`.
- For `update`, require an unambiguous selector: a block `--id`, a unique `--match`, or an exact `--ref`. If a match is ambiguous, stop and ask.
- This skill changes task **status**. It does not edit a captured todo's title, priority, or due date in place — recapture or have the user edit in Obsidian if those must change.
- If the CLI fails, it is usually because the Obsidian app is not running or the vault is not open. Run `doctor` to pinpoint the cause and report it rather than retrying blindly.
