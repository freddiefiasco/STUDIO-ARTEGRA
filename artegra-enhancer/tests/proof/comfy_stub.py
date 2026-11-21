"""A service.comfy.ComfyClient whose transport (_call) answers as ComfyUI does, so the real client's prompt() and history()
run in the proof tests (no port, no worker). Only the answers are stubbed:

  POST /prompt          {'prompt_id': <id>, 'number': <n>, 'node_errors': {}}
  GET  /history/<id>    {} while the prompt runs; then {<id>: {'prompt': [...], 'outputs': {...}, 'status': {...}, 'meta': {}}}
                        with ComfyUI's status record: success {'status_str': 'success', 'completed': True, 'messages':
                        [['execution_start', ...], ['execution_cached', ...], ['execution_success', ...]]}, error
                        {'status_str': 'error', 'completed': False, 'messages': [..., ['execution_error', {...}]]}."""
from service import comfy


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

    def __init__(self, on_prompt=None, polls_until_done=2):
        super().__init__(1)
        self.on_prompt = on_prompt or (lambda graph, pid: success_status(pid))
        self.polls_until_done = int(polls_until_done)
        self.entries, self.polls, self.calls, self.number = {}, {}, [], 0

    def _call(self, path, data=None, timeout=30.0):
        self.calls.append((path, None if data is None else sorted(data)))
        if path == '/prompt' and data is not None:
            pid = data['prompt_id']
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
