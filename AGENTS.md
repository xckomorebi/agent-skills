# AGENTS.md

This file provides guidance to coding agents (Claude Code, Codex, and others) when working with code in this repository.

## What this repo is

A collection of personal Agent Skills. Each top-level directory is one skill with a `SKILL.md` at its root (YAML frontmatter `name` and `description`, optionally `metadata.short-description`), plus optional `scripts/`, `references/`, and `schemas/`.

Skills are installed by symlink, not by copying: `~/.claude/skills/<name>` and `~/.agents/skills/<name>` point back into this repo. Edits here are live in every agent session immediately, and a new skill needs the same symlinks to be picked up. The `description` frontmatter is what agents match on to decide when to load a skill, so treat changes to it as behavior changes.

## Commands

There is no build, lint config, or test suite. Python is stdlib-only (no dependencies to install).

```bash
# Syntax check the bridge scripts
python3 -m py_compile codex-bridge/scripts/*.py

# Smoke-test the CLI surface
python3 codex-bridge/scripts/codex_bridge.py --help
python3 codex-bridge/scripts/codex_bridge.py start --help

# Read-only commands, safe to run anytime
python3 codex-bridge/scripts/codex_bridge.py list
python3 codex-bridge/scripts/codex_bridge.py prune --dry-run --days 30
```

`start`, `resume`, and `fork` require the `codex` CLI on PATH and create real Codex threads that appear in the user's Codex Desktop sidebar (tagged `[codex-bridge]`). Use `--sandbox read-only` and a short `--timeout` when exercising them end to end.

## codex-bridge architecture

Two scripts with a clean split:

- `scripts/appserver_runner.py` is the transport. It spawns `codex app-server --stdio` and speaks line-delimited JSON-RPC (`initialize`, `thread/start|resume|fork`, `thread/name/set`, `turn/start`, `turn/interrupt`). A reader thread routes responses to per-request waiters and notifications to an inbox; `run_turn` drains the inbox until `turn/completed` for its turn id. Approval policy is always `never`, so any server-initiated request is refused and surfaced as an error. On timeout it sends `turn/interrupt` and waits a 15s grace period.
- `scripts/codex_bridge.py` is the argparse CLI (`start`, `resume`, `fork`, `status`, `list`, `prune`) and owns bridge state. It imports `appserver_runner` lazily via `sys.path` insertion, so the two files must stay side by side.

State lives in `~/.codex-bridge/sessions/<bridge_session_id>/` (`session.json` plus `runs/turn_<n>_<ts>/{events.jsonl,stderr.log,last_message.txt}`). The bridge must never write to `~/.codex`; Codex owns thread records there, and `codex_thread_id` in `session.json` is the only link between the two stores. Sessions can be selected by bridge session ID, Codex thread ID, or a unique prefix of either.

The `--json` output contract is defined in `schemas/result.schema.json`. When changing flags, defaults, JSON fields, state layout, or thread-naming behavior, update `SKILL.md`, `references/lifecycle.md`, and the schema together; they document the same behavior from different angles.

`SKILL.md` references the scripts by absolute path (`/Users/xuchen/repo/agent-skills/...`) because it is consumed from the symlinked location by other agents.

## tech-design

A prose-only skill (no scripts). Its instructions are in English while the document it produces is in Chinese, with Chinese section headings that are part of the required output structure. When editing it, preserve the section skeleton, the "organize by service, then functional change" rule, and the budget and self-check sections; recent history shows deliberate tightening toward conciseness, so avoid re-expanding it.

## Conventions

- Commits follow Conventional Commits with a skill name or `skills` as scope, e.g. `feat(skills): ...`, `docs(tech-design): ...`.
- `.ma/` is a local, globally gitignored directory; ignore it.
