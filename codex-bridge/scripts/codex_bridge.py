#!/usr/bin/env python3
"""
codex_bridge.py - Unified bridge for invoking and managing OpenAI Codex CLI sessions.
Enables Antigravity CLI and other AI agents to delegate tasks to Codex as a subagent,
maintaining persistent multi-turn conversational context and workspace execution.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import stat
import sys
import time
import uuid
from pathlib import Path

BRIDGE_DIR = Path.home() / ".codex-bridge"
SESSIONS_DIR = BRIDGE_DIR / "sessions"
TITLE_TAG = "[codex-bridge]"
TITLE_BODY_LIMIT = 60
UNKNOWN_THREAD_ID = "unknown"

# Prepended to the first turn of every new session so Codex (and a human browsing
# the thread later) can tell it is agent-to-agent traffic, not a human prompt.
# ~/.codex/AGENTS.md documents this marker for Codex.
AGENT_SESSION_MARKER = (
    "[codex-bridge agent session] This thread was started programmatically by an AI agent "
    "via codex-bridge, not by a human. Treat the entire session as agent-to-agent "
    "communication and reply in English."
)


class BridgeInputError(ValueError):
    """An invalid command input or unusable session selector."""


def format_title(title=None, prompt=None, op='start', default='New session') -> str:
    """Build a one-line Codex thread name with a single bridge tag."""
    if title is None:
        first_line = ''
        for line in (prompt or '').splitlines():
            line = re.sub(r'^(?:(?:#{1,6}|[-+*]|\d+[.)]|>)\s+)*', '', line.strip())
            if re.fullmatch(r'[-*_`~\s]+', line):
                continue
            if not line:
                continue
            objective = re.match(r'^\s*[*_]*Objective\s*[*_]*:\s*[*_]*\s*(.*)$', line, re.IGNORECASE)
            if objective and objective[1].strip():
                first_line = objective[1]
                break
            if not first_line and not objective:
                first_line = line
        body = ' '.join(first_line.strip('*_` ').split())
    else:
        body = ' '.join(title.split())

    while body.startswith(TITLE_TAG) and (len(body) == len(TITLE_TAG) or body[len(TITLE_TAG)] == ' '):
        body = body[len(TITLE_TAG):].lstrip()
    if not body:
        body = 'Forked session' if op == 'fork' and default == 'New session' else default
    if title is None and len(body) > TITLE_BODY_LIMIT:
        body = body[:TITLE_BODY_LIMIT - 3].rstrip() + '...'
    return f'{TITLE_TAG} {body}'


def ensure_dirs():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def load_session(selector: str) -> dict:
    selector = selector.strip()
    if not selector:
        raise BridgeInputError("Session selector must not be empty")

    try:
        session_dirs = list(SESSIONS_DIR.iterdir())
    except FileNotFoundError:
        session_dirs = []
    except OSError as exc:
        raise BridgeInputError(f"Could not read bridge sessions: {exc}") from exc

    exact_matches = []
    prefix_matches = []
    for sdir in session_dirs:
        if not sdir.is_dir():
            continue
        try:
            with (sdir / "session.json").open(encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, ValueError, RecursionError):
            continue
        if not isinstance(data, dict):
            continue

        bridge_id = data.get("bridge_session_id") or sdir.name
        thread_id = data.get("codex_thread_id")
        ids = [bridge_id]
        if isinstance(thread_id, str) and thread_id not in ("", UNKNOWN_THREAD_ID):
            ids.append(thread_id)
        if selector in ids:
            exact_matches.append(data)
        elif any(isinstance(session_id, str) and session_id.startswith(selector) for session_id in ids):
            prefix_matches.append(data)

    matches = exact_matches or prefix_matches
    if len(matches) > 1:
        raise BridgeInputError(f"Ambiguous session selector: {selector!r}. Use the full bridge session ID.")
    if not matches:
        raise BridgeInputError(f"Session not found: {selector!r}")
    return matches[0]


def require_thread_id(session_data):
    thread_id = session_data.get("codex_thread_id")
    if not isinstance(thread_id, str) or thread_id in ("", UNKNOWN_THREAD_ID):
        raise BridgeInputError("This bridge session has no Codex thread")
    return thread_id


def read_prompt(args):
    prompt = args.prompt
    if args.prompt_file is not None:
        try:
            prompt = Path(args.prompt_file).read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            raise BridgeInputError(f"Could not read prompt file {args.prompt_file!r}: {exc}") from exc
    if not prompt or not prompt.strip():
        raise BridgeInputError("Prompt must not be empty")
    return prompt


def run_appserver_process(op, prompt, workspace, sandbox, model, run_dir, timeout, thread_id=None, title=None):
    # Drives `codex app-server --stdio` so Codex itself creates and persists the thread (visible in the desktop app).
    # Returns (retcode, timed_out, captured, duration).
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import appserver_runner as asr

    run_dir.mkdir(parents=True, exist_ok=True)
    captured = {
        'thread_id': None if op == 'fork' else thread_id,
        'token_usage': None,
        'items': [],
        'error': None,
    }
    retcode, timed_out = 1, False
    started = time.time()
    client = asr.AppServerClient(stderr_path=str(run_dir / 'stderr.log'))
    try:
        client.start()

        def remember(tid):
            captured['thread_id'] = tid

        out = asr.run_turn(
            client, op, prompt, workspace, sandbox, model, timeout,
            thread_id=thread_id, on_thread=remember, title=title,
        )
        captured['token_usage'] = out['token_usage']
        captured['items'] = out['messages']
        timed_out = out['timed_out']
        captured['error'] = out['error']
        if timed_out:
            captured['error'] = captured['error'] or f"Codex turn timed out after {timeout} seconds"
        elif out['status'] != 'completed':
            captured['error'] = captured['error'] or f"Codex turn ended with status {out['status']}"
        if captured['error'] is None:
            retcode = 0
    except (asr.AppServerError, OSError) as exc:
        captured['error'] = str(exc)
    finally:
        client.close()

    with open(run_dir / 'events.jsonl', 'w', encoding='utf-8') as f:
        for m in client.log:
            f.write(json.dumps(m, ensure_ascii=False) + '\n')
    if captured['error']:
        with open(run_dir / 'stderr.log', 'a', encoding='utf-8') as f:
            f.write(captured['error'] + '\n')
    if captured['items']:
        (run_dir / 'last_message.txt').write_text(captured['items'][-1], encoding='utf-8')
    return retcode, timed_out, captured, time.time() - started


def save_session(data: dict):
    session_id = data["bridge_session_id"]
    sdir = SESSIONS_DIR / session_id
    sdir.mkdir(parents=True, exist_ok=True)
    sfile = sdir / "session.json"
    temp_file = sdir / "session.json.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    temp_file.replace(sfile)


def cmd_start(args):
    prompt = read_prompt(args)
    prompt = f"{AGENT_SESSION_MARKER}\n\n{prompt}"
    ensure_dirs()
    workspace = os.path.abspath(args.workspace or os.getcwd())

    session_id = str(uuid.uuid4())
    run_id = f"turn_1_{int(time.time())}"
    run_dir = SESSIONS_DIR / session_id / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    last_msg_file = run_dir / "last_message.txt"

    # App-server backend: Codex creates and persists the thread itself, so it is visible in the desktop app.
    retcode, timed_out, captured, duration = run_appserver_process(
        op="start",
        prompt=prompt,
        workspace=workspace,
        sandbox=args.sandbox or "danger-full-access",
        model=args.model,
        run_dir=run_dir,
        timeout=args.timeout,
        title=format_title(args.title, prompt),
    )

    final_msg = ""
    if last_msg_file.exists():
        with open(last_msg_file, "r", encoding="utf-8") as f:
            final_msg = f.read()
    elif captured["items"]:
        final_msg = "\n\n".join(captured["items"])

    codex_thread_id = captured.get("thread_id") or UNKNOWN_THREAD_ID

    turn_data = {
        "turn_id": 1,
        "run_id": run_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "prompt": prompt,
        "final_message": final_msg,
        "token_usage": captured.get("token_usage"),
        "exit_code": retcode,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 2),
        "artifacts": {
            "events": str(run_dir / "events.jsonl"),
            "stderr": str(run_dir / "stderr.log"),
            "last_message": str(last_msg_file),
        },
    }

    session_data = {
        "bridge_session_id": session_id,
        "codex_thread_id": codex_thread_id,
        "workspace": workspace,
        "sandbox": args.sandbox or "danger-full-access",
        "model": args.model or "default",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "turns": [turn_data],
    }
    save_session(session_data)

    output = {
        "bridge_status": "completed" if retcode == 0 and not timed_out else "failed",
        "bridge_session_id": session_id,
        "codex_thread_id": codex_thread_id,
        "workspace": workspace,
        "turn": 1,
        "exit_code": retcode,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 2),
        "token_usage": captured.get("token_usage"),
        "final_message": final_msg,
        "error": captured["error"],
    }

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"=== Codex Session Started ===")
        print(f"Bridge Session ID: {session_id}")
        print(f"Codex Thread ID:   {codex_thread_id}")
        print(f"Workspace:         {workspace}")
        print(f"Exit Code:         {retcode}")
        print(f"Duration:          {round(duration, 2)}s")
        print("\n--- Codex Response ---")
        print(final_msg)

    sys.exit(retcode if not timed_out else 124)


def cmd_resume(args):
    prompt = read_prompt(args)
    session_data = load_session(args.session)
    session_id = session_data["bridge_session_id"]
    codex_thread_id = require_thread_id(session_data)

    workspace = args.workspace or session_data.get("workspace") or os.getcwd()
    sandbox = args.sandbox or session_data.get("sandbox") or "danger-full-access"
    model = args.model or session_data.get("model")

    turn_number = len(session_data.get("turns", [])) + 1
    run_id = f"turn_{turn_number}_{int(time.time())}"
    run_dir = SESSIONS_DIR / session_id / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    last_msg_file = run_dir / "last_message.txt"

    # App-server backend: thread/resume on the stored thread id, so Codex keeps owning persistence.
    retcode, timed_out, captured, duration = run_appserver_process(
        op="resume",
        prompt=prompt,
        workspace=workspace,
        sandbox=sandbox,
        model=model,
        run_dir=run_dir,
        timeout=args.timeout,
        thread_id=codex_thread_id,
        title=format_title(args.title, op='resume') if args.title is not None else None,
    )

    final_msg = ""
    if last_msg_file.exists():
        with open(last_msg_file, "r", encoding="utf-8") as f:
            final_msg = f.read()
    elif captured["items"]:
        final_msg = "\n\n".join(captured["items"])

    turn_data = {
        "turn_id": turn_number,
        "run_id": run_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "prompt": prompt,
        "final_message": final_msg,
        "token_usage": captured.get("token_usage"),
        "exit_code": retcode,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 2),
        "artifacts": {
            "events": str(run_dir / "events.jsonl"),
            "stderr": str(run_dir / "stderr.log"),
            "last_message": str(last_msg_file),
        },
    }

    session_data["turns"].append(turn_data)
    session_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_session(session_data)

    output = {
        "bridge_status": "completed" if retcode == 0 and not timed_out else "failed",
        "bridge_session_id": session_id,
        "codex_thread_id": codex_thread_id,
        "workspace": workspace,
        "turn": turn_number,
        "exit_code": retcode,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 2),
        "token_usage": captured.get("token_usage"),
        "final_message": final_msg,
        "error": captured["error"],
    }

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"=== Codex Session Resumed (Turn {turn_number}) ===")
        print(f"Bridge Session ID: {session_id}")
        print(f"Codex Thread ID:   {codex_thread_id}")
        print(f"Workspace:         {workspace}")
        print(f"Exit Code:         {retcode}")
        print(f"Duration:          {round(duration, 2)}s")
        print("\n--- Codex Response ---")
        print(final_msg)

    sys.exit(retcode if not timed_out else 124)


def cmd_fork(args):
    prompt = read_prompt(args)
    session_data = load_session(args.session)
    src_thread_id = require_thread_id(session_data)

    new_session_id = str(uuid.uuid4())
    workspace = os.path.abspath(args.workspace or session_data.get("workspace") or os.getcwd())
    sandbox = args.sandbox or session_data.get("sandbox") or "danger-full-access"
    model = args.model or session_data.get("model")

    run_id = f"fork_turn_1_{int(time.time())}"
    run_dir = SESSIONS_DIR / new_session_id / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    last_msg_file = run_dir / "last_message.txt"

    # App-server backend: thread/fork on the source thread id; the fork gets a new thread id owned by Codex.
    retcode, timed_out, captured, duration = run_appserver_process(
        op="fork",
        prompt=prompt,
        workspace=workspace,
        sandbox=sandbox,
        model=model,
        run_dir=run_dir,
        timeout=args.timeout,
        thread_id=src_thread_id,
        title=format_title(args.title, prompt, op='fork'),
    )

    final_msg = ""
    if last_msg_file.exists():
        with open(last_msg_file, "r", encoding="utf-8") as f:
            final_msg = f.read()
    elif captured["items"]:
        final_msg = "\n\n".join(captured["items"])

    new_thread_id = captured.get("thread_id") or UNKNOWN_THREAD_ID

    turn_data = {
        "turn_id": 1,
        "run_id": run_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "prompt": prompt,
        "final_message": final_msg,
        "token_usage": captured.get("token_usage"),
        "exit_code": retcode,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 2),
        "artifacts": {
            "events": str(run_dir / "events.jsonl"),
            "stderr": str(run_dir / "stderr.log"),
            "last_message": str(last_msg_file),
        },
    }

    new_session_data = {
        "bridge_session_id": new_session_id,
        "codex_thread_id": new_thread_id,
        "forked_from_session_id": session_data["bridge_session_id"],
        "forked_from_thread_id": src_thread_id,
        "workspace": workspace,
        "sandbox": sandbox,
        "model": model or "default",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "turns": [turn_data],
    }
    save_session(new_session_data)

    output = {
        "bridge_status": "completed" if retcode == 0 and not timed_out else "failed",
        "bridge_session_id": new_session_id,
        "codex_thread_id": new_thread_id,
        "forked_from": src_thread_id,
        "workspace": workspace,
        "turn": 1,
        "exit_code": retcode,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 2),
        "token_usage": captured.get("token_usage"),
        "final_message": final_msg,
        "error": captured["error"],
    }

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"=== Codex Session Forked ===")
        print(f"New Bridge Session ID: {new_session_id}")
        print(f"New Codex Thread ID:   {new_thread_id}")
        print(f"Forked From:           {src_thread_id}")
        print(f"Workspace:             {workspace}")
        print(f"Exit Code:             {retcode}")
        print(f"Duration:              {round(duration, 2)}s")
        print("\n--- Codex Response ---")
        print(final_msg)

    sys.exit(retcode if not timed_out else 124)


def cmd_status(args):
    session_data = load_session(args.session)
    if args.json:
        print(json.dumps(session_data, indent=2, ensure_ascii=False))
    else:
        turns = session_data.get("turns", [])
        print(f"Bridge Session ID: {session_data.get('bridge_session_id')}")
        print(f"Codex Thread ID:   {session_data.get('codex_thread_id')}")
        print(f"Workspace:         {session_data.get('workspace')}")
        print(f"Model:             {session_data.get('model')}")
        print(f"Sandbox:           {session_data.get('sandbox')}")
        print(f"Created At:        {session_data.get('created_at')}")
        print(f"Total Turns:       {len(turns)}")
        if turns:
            last_turn = turns[-1]
            print(f"Last Turn Exit:    {last_turn.get('exit_code')}")
            print(f"Last Turn Time:    {last_turn.get('timestamp')}")
            print(f"\n--- Latest Final Message ---")
            print(last_turn.get("final_message"))


def cmd_list(args):
    ensure_dirs()
    sessions = []
    for sdir in SESSIONS_DIR.iterdir():
        if sdir.is_dir():
            sf = sdir / "session.json"
            if sf.exists():
                try:
                    with open(sf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    turns = data.get("turns", [])
                    sessions.append({
                        "bridge_session_id": data.get("bridge_session_id"),
                        "codex_thread_id": data.get("codex_thread_id"),
                        "workspace": data.get("workspace"),
                        "turns_count": len(turns),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                    })
                except Exception:
                    continue

    sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    if args.json:
        print(json.dumps(sessions, indent=2, ensure_ascii=False))
    else:
        print(f"{'BRIDGE SESSION ID':<38} {'CODEX THREAD ID':<38} {'TURNS':<6} {'WORKSPACE'}")
        print("-" * 110)
        for s in sessions:
            print(f"{s['bridge_session_id']:<38} {s['codex_thread_id']:<38} {s['turns_count']:<6} {s['workspace']}")


def prune_session_metadata(session_dir, directory_mtime):
    metadata_path = session_dir / 'session.json'
    try:
        metadata_stat = metadata_path.lstat()
    except FileNotFoundError:
        metadata_stat = None

    data = {}
    mtime = directory_mtime
    if metadata_stat and stat.S_ISREG(metadata_stat.st_mode):
        mtime = metadata_stat.st_mtime
        try:
            with metadata_path.open(encoding='utf-8') as file:
                parsed = json.load(file)
            if isinstance(parsed, dict):
                data = parsed
        except (ValueError, RecursionError):
            pass

    for field in ('updated_at', 'created_at'):
        value = data.get(field)
        if isinstance(value, str):
            try:
                if value.endswith('Z'):
                    value = value[:-1] + '+00:00'
                timestamp = datetime.datetime.fromisoformat(value)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
                return data, timestamp.astimezone(datetime.timezone.utc)
            except (ValueError, OverflowError):
                continue
    return data, datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)


def directory_size(path):
    def raise_walk_error(error):
        raise error

    size = 0
    for directory, _, filenames in os.walk(path, onerror=raise_walk_error):
        for filename in filenames:
            entry = (Path(directory) / filename).lstat()
            if stat.S_ISREG(entry.st_mode):
                size += entry.st_size
    return size


def format_size(size):
    for unit, scale in (('GB', 1024**3), ('MB', 1024**2), ('KB', 1024)):
        if size >= scale:
            return f'{size / scale:.1f} {unit}'
    return f'{size} B'


def cmd_prune(args):
    now = datetime.datetime.now(datetime.timezone.utc)
    sessions = []
    had_error = False
    try:
        session_dirs = sorted(SESSIONS_DIR.iterdir())
    except FileNotFoundError:
        session_dirs = []
    except OSError as exc:
        print(f'Could not scan bridge sessions: {exc}', file=sys.stderr)
        session_dirs = []
        had_error = True

    for session_dir in session_dirs:
        try:
            directory = session_dir.lstat()
            if not stat.S_ISDIR(directory.st_mode):
                continue
            data, last_updated = prune_session_metadata(session_dir, directory.st_mtime)
            if (now - last_updated).total_seconds() <= args.days * 86400:
                continue
            size = directory_size(session_dir)
            if not args.dry_run:
                shutil.rmtree(session_dir)
            sessions.append({
                'bridge_session_id': data.get('bridge_session_id') or session_dir.name,
                'codex_thread_id': data.get('codex_thread_id'),
                'last_updated': last_updated.isoformat(),
                'size_bytes': size,
            })
        except FileNotFoundError:
            continue
        except OSError as exc:
            print(f'Could not process session {session_dir.name}: {exc}', file=sys.stderr)
            had_error = True

    freed_bytes = sum(session['size_bytes'] for session in sessions)
    if args.json:
        print(json.dumps({
            'pruned_count': len(sessions),
            'freed_bytes': freed_bytes,
            'dry_run': args.dry_run,
            'days_threshold': args.days,
            'sessions': sessions,
        }, indent=2))
    else:
        for session in sessions:
            print(f"{session['bridge_session_id']}  {session['last_updated']}  {format_size(session['size_bytes'])}")
        action = 'Would prune' if args.dry_run else 'Pruned'
        space = 'would free' if args.dry_run else 'freed'
        print(f'{action} {len(sessions)} session(s) older than {args.days} days, '
              f'{space} {format_size(freed_bytes)}.')

    if had_error:
        sys.exit(1)


def retention_days(value):
    days = int(value)
    if days < 0:
        raise argparse.ArgumentTypeError('retention days must be non-negative')
    return days


def positive_timeout(value):
    seconds = int(value)
    if seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be greater than zero")
    return seconds


def add_turn_arguments(parser):
    prompt = parser.add_mutually_exclusive_group(required=True)
    prompt.add_argument("-p", "--prompt", help="Instructions prompt string")
    prompt.add_argument("--prompt-file", help="Path to file containing prompt")
    parser.add_argument(
        "--timeout", type=positive_timeout, default=600,
        help="Turn timeout in seconds before requesting interruption (default: 600)",
    )


def main():
    parser = argparse.ArgumentParser(description="Codex Bridge CLI - Subagent management for Codex")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # start
    p_start = subparsers.add_parser("start", help="Start a new Codex session in a workspace")
    p_start.add_argument("-w", "--workspace", help="Workspace path (defaults to cwd)")
    add_turn_arguments(p_start)
    p_start.add_argument("--title", help="Codex thread title (defaults to a prompt excerpt)")
    p_start.add_argument("-s", "--sandbox", choices=["read-only", "workspace-write", "danger-full-access"], default="danger-full-access")
    p_start.add_argument("-m", "--model", help="Codex model override")
    p_start.add_argument("--json", action="store_true", help="Print structured JSON output")
    p_start.set_defaults(func=cmd_start)

    # resume
    p_resume = subparsers.add_parser("resume", help="Resume an existing Codex session")
    p_resume.add_argument("--session", "-S", required=True, help="Bridge session ID or Codex thread ID")
    add_turn_arguments(p_resume)
    p_resume.add_argument("--title", help="Rename the existing Codex thread")
    p_resume.add_argument("-w", "--workspace", help="Override workspace directory")
    p_resume.add_argument("-s", "--sandbox", choices=["read-only", "workspace-write", "danger-full-access"])
    p_resume.add_argument("-m", "--model", help="Codex model override")
    p_resume.add_argument("--json", action="store_true", help="Print structured JSON output")
    p_resume.set_defaults(func=cmd_resume)

    # fork
    p_fork = subparsers.add_parser("fork", help="Fork an existing session into a new conversation thread")
    p_fork.add_argument("--session", "-S", required=True, help="Source bridge session ID or Codex thread ID")
    p_fork.add_argument("-w", "--workspace", help="New workspace directory")
    add_turn_arguments(p_fork)
    p_fork.add_argument("--title", help="Forked Codex thread title (defaults to a prompt excerpt)")
    p_fork.add_argument("-s", "--sandbox", choices=["read-only", "workspace-write", "danger-full-access"])
    p_fork.add_argument("-m", "--model", help="Codex model override")
    p_fork.add_argument("--json", action="store_true", help="Print structured JSON output")
    p_fork.set_defaults(func=cmd_fork)

    # status
    p_status = subparsers.add_parser("status", help="Get session status and history")
    p_status.add_argument("--session", "-S", required=True, help="Bridge session ID or Codex thread ID")
    p_status.add_argument("--json", action="store_true", help="Print raw session JSON")
    p_status.set_defaults(func=cmd_status)

    # list
    p_list = subparsers.add_parser("list", help="List all managed bridge sessions")
    p_list.add_argument("--json", action="store_true", help="Print JSON list")
    p_list.set_defaults(func=cmd_list)

    p_prune = subparsers.add_parser("prune", help="Remove old bridge sessions and their run logs")
    p_prune.add_argument("--days", type=retention_days, default=30, help="Retention in days (default: 30)")
    p_prune.add_argument("--dry-run", action="store_true", help="Preview candidates without deleting them")
    p_prune.add_argument("--json", action="store_true", help="Print a JSON summary")
    p_prune.set_defaults(func=cmd_prune)

    args = parser.parse_args()
    try:
        args.func(args)
    except BridgeInputError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
