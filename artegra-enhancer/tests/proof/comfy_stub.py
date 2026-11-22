"""A service.comfy.ComfyClient whose transport (_call) answers as ComfyUI does, so the real client's prompt() and history()
run in the proof tests (no port, no worker). Only the answers are stubbed:

  POST /prompt          {'prompt_id': <id>, 'number': <n>, 'node_errors': {}}
  GET  /history/<id>    {} while the prompt runs; then {<id>: {'prompt': [...], 'outputs': {...}, 'status': {...}, 'meta': {}}}
                        with ComfyUI's status record: success {'status_str': 'success', 'completed': True, 'messages':
                        [['execution_start', ...], ['execution_cached', ...], ['execution_success', ...]]}, error
                        {'status_str': 'error', 'completed': False, 'messages': [..., ['execution_error', {...}]]}.
With strict_ids (the default), POST /prompt refuses a client prompt id that is not a canonical lowercase hyphenated UUID with
ComfyUI's 400 invalid_prompt_id, as the runtime ComfyUI does (comfy_execution/jobs.validate_job_id: str(uuid.UUID(v)) == v)."""
import uuid

from service import comfy


def valid_job_id(value):
    """The runtime ComfyUI's rule for a client-supplied prompt id (comfy_execution/jobs.validate_job_id)."""
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False


def success_status(prompt_id):
    return {'status_str': 'success', 'completed': True,
            'messages': [['execution_start', {'prompt_id': prompt_id, 'timestamp': 1}],
                         ['execution_cached', {'nodes': [], 'prompt_id': prompt_id, 'timestamp': 1}],
                         ['execution_success', {'prompt_id': prompt_id, 'timestamp': 2}]]}


def error_status(prompt_id, message='boom', node_id='7', node_type='KSampler'):
    return {'status_str': 'error', 'completed': False,
            'messages': [['execution_start', {'prompt_id': prompt_id, 'timestamp': 1}],
                         ['execution_error', {'prompt_id': prompt_id, 'node_id': node_id, 'node_type': node_type,
                                              'executed': [], 'exception_message': message,
                                              'exception_type': 'RuntimeError', 'traceback': ['...'],
                                              'current_inputs': {}, 'current_outputs': {}, 'timestamp': 2}]]}


class StubComfy(comfy.ComfyClient):
    """on_prompt(graph, prompt_id) runs when ComfyUI would accept the prompt and returns the history entry's status record
    (success_status / error_status); the entry appears after `polls_until_done` history polls that answer {}."""

    def __init__(self, on_prompt=None, polls_until_done=2, strict_ids=True):
        super().__init__(1)
        self.on_prompt = on_prompt or (lambda graph, pid: success_status(pid))
        self.polls_until_done = int(polls_until_done)
        self.strict_ids = bool(strict_ids)
        self.refused = []
        self.entries, self.polls, self.calls, self.number = {}, {}, [], 0

    def _call(self, path, data=None, timeout=30.0):
        self.calls.append((path, None if data is None else sorted(data)))
        if path == '/prompt' and data is not None:
            pid = data.get('prompt_id')
            if pid is not None and self.strict_ids and not valid_job_id(pid):
                self.refused.append(pid)
                raise comfy.ComfyError('ComfyUI answered 400', status=400,
                                       detail={'error': {'type': 'invalid_prompt_id',
                                                         'message': 'job id must be a UUID in canonical lowercase '
                                                                    'hyphenated form'}})
            status = self.on_prompt(data['prompt'], pid)
            self.entries[pid] = {'prompt': [self.number, pid, data['prompt'], {'client_id': data['client_id']}, []],
                                 'outputs': {}, 'status': status, 'meta': {}}
            self.number += 1
            return {'prompt_id': pid, 'number': self.number - 1, 'node_errors': {}}
        if path.startswith('/history/') and data is None:
            pid = path[len('/history/'):]
            n = self.polls.get(pid, 0)
            self.polls[pid] = n + 1
            if pid not in self.entries or n < self.polls_until_done:
                return {}
            return {pid: self.entries[pid]}
        raise AssertionError(f'unexpected call {path}')
