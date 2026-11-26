# agent-skills

Personal [Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) for Claude Code, Codex, and other agents that load `SKILL.md` folders.

## Skills

| Skill | What it does |
| --- | --- |
| [codex-bridge](codex-bridge/SKILL.md) | Delegates tasks to the OpenAI Codex CLI as a subagent. Keeps sessions that persist across turns, and supports workspace routing, resume, and fork. Results come back as structured JSON. |
| [tech-design](tech-design/SKILL.md) | Drafts or revises concise technical design documents (技术文档) for backend, QA, and product reviewers. Organized by service and functional change, with concrete SQL, config, and a rollout checklist. |

## Install

Skills are installed by symlink, so edits in this repo take effect immediately:

```bash
for skill in codex-bridge tech-design; do
  ln -sfn "$PWD/$skill" ~/.claude/skills/$skill   # Claude Code
  ln -sfn "$PWD/$skill" ~/.agents/skills/$skill   # Codex and other agents
done
```

## codex-bridge requirements

- Python 3 (standard library only)
- The `codex` CLI on `PATH`. The bridge drives `codex app-server --stdio`, so bridge threads show up in Codex Desktop with a `[codex-bridge]` title prefix. For grouping in the sidebar, the `--workspace` directory should already be a project in the app.

Bridge session state and turn logs are written to `~/.codex-bridge/sessions/`. The bridge never writes to `~/.codex`.

```bash
python3 codex-bridge/scripts/codex_bridge.py start -w /path/to/project -p "Summarize the architecture." --json
python3 codex-bridge/scripts/codex_bridge.py resume -S <session-id> -p "Now add tests." --json
python3 codex-bridge/scripts/codex_bridge.py list
```

See [codex-bridge/SKILL.md](codex-bridge/SKILL.md) for all commands and flags, and [references/lifecycle.md](codex-bridge/references/lifecycle.md) for the protocol and session lifecycle.

## Layout

Each skill is a top-level directory with a `SKILL.md` (YAML frontmatter `name` and `description`). It may also have `scripts/`, `references/`, and `schemas/`. Notes for agents working in this repo are in [AGENTS.md](AGENTS.md).
