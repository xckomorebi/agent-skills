---
name: "codex-bridge"
description: "Bridge and delegate tasks to OpenAI Codex CLI as an external subagent. Manage persistent Codex sessions across multi-turn workflows, execute tasks within specific project directories or worktrees, resume existing sessions, fork conversations, and retrieve structured results."
metadata:
  short-description: "Delegate tasks to OpenAI Codex as a subagent with session persistence and workspace routing."
---

# Codex Bridge

The `codex-bridge` skill enables Antigravity CLI and other AI agents to invoke OpenAI Codex (`codex-cli`) as a specialized coding subagent. It manages persistent multi-turn conversations, maps workspace directories, and handles non-interactive I/O contracts.

Turns run through `codex app-server --stdio`, the protocol the Codex desktop app itself uses, so every bridge thread is a normal interactive thread: it shows up in the desktop app sidebar with its full history, and the bridge does not touch `~/.codex` state files. Threads are grouped under the app's project for the `--workspace` directory, so use a workspace that is already registered as a project in the app.

The bridge sets the name of every new session and fork with the `[codex-bridge]` prefix. This is the name used in Codex Desktop and Codex thread listings. By default, the title comes from a short excerpt of the prompt. Use `--title` to supply a specific name.

The first turn of every `start` session is prefixed with an `[codex-bridge agent session]` marker line telling Codex the thread was started programmatically by an agent. Codex recognizes this marker via `~/.codex/AGENTS.md` and treats the whole session as agent-to-agent communication.

## Language Preference

All communication with Codex must be in English. Write every prompt in English, even when the surrounding conversation with the user is in another language. The bridge's session marker also instructs Codex to reply in English, and `~/.codex/AGENTS.md` reinforces this for agent sessions.

## When to Use

- When you want to delegate a complex coding, refactoring, code review, or exploratory task to Codex.
- When working within specific projects configured in Codex (e.g. `agent-skills`, `maas-gateway`, `maas`, `stock`, `comfy`, etc.).
- When needing multi-turn collaboration with Codex (passing follow-up instructions while retaining full context).
- When comparing alternative implementation strategies using session forks.

---

## Quick Reference

The bridge CLI script is located at:
`scripts/codex_bridge.py` (or `/Users/xuchen/repo/agent-skills/codex-bridge/scripts/codex_bridge.py`)

### 1. Start a New Session in a Project Workspace

```bash
python3 /Users/xuchen/repo/agent-skills/codex-bridge/scripts/codex_bridge.py start \
  --workspace /path/to/project \
  --prompt "Analyze the architecture of pkg/composer and identify potential race conditions." \
  --json
```

**Common Flags:**
- `-w, --workspace <DIR>`: Project working directory (e.g. `/Users/xuchen/repo/agent-skills`).
- `-p, --prompt <TEXT>`: Instructions for Codex.
- `--prompt-file <FILE>`: Read the prompt from a file. Supply exactly one of `--prompt` and `--prompt-file`.
- `--title <TITLE>` sets the thread name with the `[codex-bridge]` prefix.
- `-s, --sandbox <MODE>`: `read-only`, `workspace-write`, or `danger-full-access` (default).
- `-m, --model <MODEL>`: Optional Codex model override (e.g. `gpt-6.1-terra`).
- `--timeout <SEC>`: Positive turn timeout in seconds before the bridge requests interruption (default: 600).
- `--json`: Output machine-readable JSON containing `bridge_session_id`, `codex_thread_id`, exit code, duration, token usage, `final_message`, and an `error` field for backend failures.

### 2. Resume an Existing Session (Follow-up)

```bash
python3 /Users/xuchen/repo/agent-skills/codex-bridge/scripts/codex_bridge.py resume \
  --session <BRIDGE_SESSION_ID_OR_THREAD_ID> \
  --prompt "Now write unit tests for the functions you proposed." \
  --json
```

Retains complete conversational history and the current thread name. Pass `--title <TITLE>` to rename the existing thread with the `[codex-bridge]` prefix.

Use a full bridge session ID or Codex thread ID with `--session`. A unique prefix also works.

### 3. Fork a Session (Branching Conversation)

```bash
python3 /Users/xuchen/repo/agent-skills/codex-bridge/scripts/codex_bridge.py fork \
  --session <BRIDGE_SESSION_ID_OR_THREAD_ID> \
  --workspace /path/to/alternative-worktree \
  --prompt "Try an alternative approach using channels instead of mutexes." \
  --json
```

Pass `--title <TITLE>` to name the fork. The default uses the fork prompt.

### 4. Check Session Status & History

```bash
python3 /Users/xuchen/repo/agent-skills/codex-bridge/scripts/codex_bridge.py status \
  --session <BRIDGE_SESSION_ID>
```

### 5. List All Active Sessions

```bash
python3 /Users/xuchen/repo/agent-skills/codex-bridge/scripts/codex_bridge.py list
```

### 6. Prune Old Bridge Sessions

```bash
python3 /Users/xuchen/repo/agent-skills/codex-bridge/scripts/codex_bridge.py prune --dry-run --days 30
python3 /Users/xuchen/repo/agent-skills/codex-bridge/scripts/codex_bridge.py prune --days 30 --json
```

Pruning removes local bridge session directories and their run logs from `~/.codex-bridge/sessions/`. Conversations stay in Codex Desktop.

- `--days <DAYS>` sets the retention period. The default is 30 days.
- `--dry-run` previews matching sessions and the estimated space they occupy.
- `--json` prints a machine-readable summary. In a dry run, `pruned_count` and `freed_bytes` describe the candidates and estimated savings.

---

## Orchestrator Best Practices

1. **Prefer Session Reuse:** Within a single Antigravity conversation (or any orchestrator session), **always prefer reusing the same Codex bridge session across turns** (via `resume`) rather than spawning a fresh `start` session for every instruction. Reusing the session preserves architectural context, avoids redundant codebase explanations, maintains conversation coherence, and keeps the user's Codex Desktop sidebar clean with a single organized thread.
2. **Active Writer Conflict & Fork Fallback:** If `resume` encounters `thread already has an active writer`, it means the Codex Desktop app or another process currently holds an exclusive write lock on that thread's file. In that case, either deselect/close the thread in the Desktop UI, or use `fork` to branch off it into a new writable thread while preserving 100% of the conversation history.
3. **Task Boundaries:** Provide explicit objectives, allowed files, constraints, and test commands.
4. **File Isolation:** If running parallel editing tasks, allocate separate Git worktrees rather than editing the same working directory concurrently.
5. **Verify Outcomes:** Treat Codex's final message as a proposal; inspect `git diff`, run tests, and verify code locally before committing.
6. **State Persistence:** All bridge sessions and turn logs are persisted in `~/.codex-bridge/sessions/`.
