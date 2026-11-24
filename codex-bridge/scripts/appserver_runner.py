#!/usr/bin/env python3
# App-server backend for codex-bridge.
# Drives `codex app-server --stdio` over JSON-RPC (one JSON object per line), the same protocol the
# desktop app uses, so threads are created and persisted by Codex itself. This replaces the
# sqlite / global-state sync hook.
import json
import logging
import queue
import subprocess
import threading
import time

CLIENT_INFO = {'name': 'codex_bridge', 'title': 'Codex Bridge', 'version': '0.2.0'}
logger = logging.getLogger(__name__)


class AppServerError(RuntimeError):
    pass


# ---- SECTION: transport ----
class AppServerClient:
    def __init__(self, codex_bin='codex', stderr_path=None):
        self.codex_bin = codex_bin
        self.stderr_path = stderr_path
        self.proc = None
        self._next_id = 1
        self._pending = {}
        self._lock = threading.Lock()
        self.inbox = queue.Queue()  # server notifications and server-initiated requests
        self.log = []  # every raw message, written to events.jsonl by the caller

    def start(self):
        err = open(self.stderr_path, 'w') if self.stderr_path else subprocess.DEVNULL
        self.proc = subprocess.Popen(
            [self.codex_bin, 'app-server', '--stdio'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
            text=True, bufsize=1,
        )
        threading.Thread(target=self._read_loop, daemon=True).start()
        self.request('initialize', {'clientInfo': CLIENT_INFO}, timeout=30)
        self.notify('initialized')  # TODO verify against ClientNotification.json

    def _send(self, msg):
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + '\n')
        self.proc.stdin.flush()

    def notify(self, method, params=None):
        msg = {'method': method}
        if params is not None:
            msg['params'] = params
        self._send(msg)

    def request(self, method, params, timeout=60):
        with self._lock:
            rid = self._next_id
            self._next_id += 1
            waiter = queue.Queue(1)
            self._pending[rid] = waiter
        self._send({'id': rid, 'method': method, 'params': params})
        try:
            msg = waiter.get(timeout=timeout)
        except queue.Empty:
            raise AppServerError(method + ': no response within ' + str(timeout) + 's')
        if 'error' in msg:
            raise AppServerError(method + ': ' + json.dumps(msg['error']))
        return msg.get('result')

    def reject_server_request(self, msg, reason):
        # Approval policy is 'never', so any server-initiated request is unexpected: refuse it loudly.
        self._send({'id': msg['id'], 'error': {'code': -32601, 'message': reason}})

    def _read_loop(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            self.log.append(msg)
            if 'method' in msg:
                self.inbox.put(msg)
            else:
                with self._lock:
                    waiter = self._pending.pop(msg.get('id'), None)
                if waiter:
                    waiter.put(msg)
        self.inbox.put({'method': '_eof'})

    def close(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()


# Thread and turn lifecycle
SANDBOXES = ('read-only', 'workspace-write', 'danger-full-access')
METHODS = {'start': 'thread/start', 'resume': 'thread/resume', 'fork': 'thread/fork'}


def _usage(raw):
    # tokenUsage.total is cumulative for the thread, not just this turn.
    total = raw.get('total') if isinstance(raw, dict) else None
    if not isinstance(total, dict) or not total:
        return None
    return {
        'input_tokens': total.get('inputTokens'),
        'cached_input_tokens': total.get('cachedInputTokens'),
        'cache_write_input_tokens': total.get('cacheWriteInputTokens'),
        'output_tokens': total.get('outputTokens'),
        'reasoning_output_tokens': total.get('reasoningOutputTokens'),
    }


def _response_id(result, item, method):
    data = result.get(item) if isinstance(result, dict) else None
    item_id = data.get('id') if isinstance(data, dict) else None
    if not isinstance(item_id, str) or not item_id.strip():
        raise AppServerError(f'{method}: response is missing {item}.id')
    return item_id


def run_turn(
    client, op, prompt, workspace, sandbox, model, timeout, thread_id=None, on_thread=None, title=None
):
    if op not in METHODS:
        raise AppServerError('unknown op: ' + str(op))
    if sandbox not in SANDBOXES:
        raise AppServerError('unsupported sandbox: ' + str(sandbox))
    if op in ('resume', 'fork') and not thread_id:
        raise AppServerError(op + ' requires thread_id')

    params = {'cwd': workspace, 'sandbox': sandbox, 'approvalPolicy': 'never'}
    if model and model != 'default':
        params['model'] = model
    if op in ('resume', 'fork'):
        params['threadId'] = thread_id
    method = METHODS[op]
    res = client.request(method, params, timeout=60)
    tid = _response_id(res, 'thread', method)
    if op == 'fork' and tid == thread_id:
        raise AppServerError('thread/fork: response returned the source thread ID')
    if on_thread:
        on_thread(tid)

    if title is not None:
        try:
            client.request('thread/name/set', {'threadId': tid, 'name': title}, timeout=5)
        except AppServerError as exc:
            logger.warning('Could not set the name for Codex thread %s: %s', tid, exc)

    turn_params = {
        'threadId': tid,
        'input': [{'type': 'text', 'text': prompt, 'text_elements': []}],
        'cwd': workspace,
        'approvalPolicy': 'never',
    }
    if model and model != 'default':
        turn_params['model'] = model
    started = time.time()
    res = client.request('turn/start', turn_params, timeout=60)
    turn_id = _response_id(res, 'turn', 'turn/start')

    out = {
        'thread_id': tid, 'turn_id': turn_id, 'status': 'inProgress', 'messages': [],
        'token_usage': None, 'error': None, 'timed_out': False,
    }
    deadline = started + timeout
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            if out['timed_out']:
                break  # interrupt was sent and the turn still did not report completion
            out['timed_out'] = True
            try:
                client.request('turn/interrupt', {'threadId': tid, 'turnId': turn_id}, timeout=10)
            except AppServerError as exc:
                out['error'] = str(exc)
            deadline = time.time() + 15
            continue
        try:
            msg = client.inbox.get(timeout=remaining)
        except queue.Empty:
            continue
        method = msg.get('method')
        p = msg.get('params') or {}
        if msg.get('id') is not None:
            client.reject_server_request(msg, 'codex_bridge runs unattended with approvalPolicy never: ' + str(method))
            out['error'] = out['error'] or ('server asked for ' + str(method) + ' and it was refused')
            continue
        if method == '_eof':
            out['status'] = 'failed'
            out['error'] = out['error'] or 'app-server exited before the turn completed'
            break
        if p.get('threadId') not in (None, tid):
            continue
        if method == 'item/completed' and p.get('turnId') == turn_id:
            item = p.get('item') or {}
            if item.get('type') == 'agentMessage':
                out['messages'].append(item.get('text', ''))
        elif method == 'thread/tokenUsage/updated' and p.get('turnId') == turn_id:
            out['token_usage'] = _usage(p.get('tokenUsage'))
        elif method == 'error' and not p.get('willRetry'):
            out['error'] = json.dumps(p.get('error'), ensure_ascii=False)
        elif method == 'turn/completed' and (p.get('turn') or {}).get('id') == turn_id:
            turn = p['turn']
            out['status'] = turn.get('status')
            if turn.get('error') and not out['error']:
                out['error'] = json.dumps(turn['error'], ensure_ascii=False)
            break

    if out['timed_out'] and out['status'] == 'inProgress':
        out['status'] = 'interrupted'
    out['duration'] = round(time.time() - started, 2)
    out['final_message'] = out['messages'][-1] if out['messages'] else ''
    return out
