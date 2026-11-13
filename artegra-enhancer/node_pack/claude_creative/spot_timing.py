"""Spot timing implementation."""


import json
import os
import time

import torch


def _ctx():
    try:
        from comfy_execution.utils import get_executing_context
        c = get_executing_context()
        if c is not None:
            return c.prompt_id, c.node_id
    except Exception:
        pass
    return None, None


class PassTimer:
    def __init__(self, label):
        self.label = label
        self.prompt = None
        self.pass_no = 0
        self.rec = None

    def begin(self, sigmas):
        pid, nid = _ctx()
        if pid != self.prompt:
            self.prompt, self.pass_no = pid, 0
        self.pass_no += 1
        self.sig = [float(s) for s in sigmas.detach().flatten().cpu()]
        self.rec = {'label': self.label, 'prompt_id': pid, 'node': nid, 'pass': self.pass_no, 'steps': max(len(self.sig) - 1, 0),
                    't_outer_start': time.perf_counter(), 'calls': [], 'epoch_start': time.time()}

    def step_of(self, sigma):
        return min(range(len(self.sig)), key=lambda i: abs(self.sig[i] - sigma)) if self.sig else -1

    def call(self, kind, step, n_windows, t0, t1, extra=None):
        if self.rec is not None:
            row = [kind, step, n_windows, round(t0 - self.rec['t_outer_start'], 5), round(t1 - self.rec['t_outer_start'], 5)]
            if extra:
                row.append(extra)
            self.rec['calls'].append(row)

    def end(self, extra=None):
        if self.rec is None:
            return
        try:
            for i in range(torch.cuda.device_count()):
                torch.cuda.synchronize(i)
        except Exception:
            pass
        r = self.rec
        self.rec = None
        r['t_outer_end'] = time.perf_counter()
        r['pass_wall_s'] = round(r['t_outer_end'] - r['t_outer_start'], 4)
        calls = r['calls']
        if calls:
            first = calls[0][3]
            r['sampling_s'] = round(r['pass_wall_s'] - first, 4)
            starts = {}
            for c in calls:
                if c[0] == 'main' and c[1] not in starts:
                    starts[c[1]] = c[3]
            ks = sorted(starts)
            ends = [starts[k] for k in ks[1:]] + [r['pass_wall_s']]
            r['step_s'] = {str(k): round(e - starts[k], 4) for k, e in zip(ks, ends)}
            st = [r['step_s'][str(k)] for k in ks]
            r['first_step_s'] = st[0] if st else None
            r['mean_step_s_excl_first'] = round(sum(st[1:]) / max(len(st) - 1, 1), 4) if len(st) > 1 else None
            r['windows_main'] = sum(c[2] for c in calls if c[0] == 'main')
            r['windows_pag'] = sum(c[2] for c in calls if c[0] == 'pag')
        if extra:
            r.update(extra)
        r.pop('t_outer_start', None); r.pop('t_outer_end', None)
        try:
            import folder_paths
            d = os.path.join(folder_paths.get_output_directory(), 'claude_timing')
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, '%s_%s_pass%d_node%s.json' % (self.label, r['prompt_id'], r['pass'], r['node'])), 'w',
                      encoding='utf8') as f:
                json.dump(r, f, indent=0)
        except Exception:
            pass


def make_timer(label):
    """A PassTimer when env CLAUDE_SPOT_TIMING is 1 / on / true, else None (no timing, no files, no synchronisation)."""
    if os.environ.get('CLAUDE_SPOT_TIMING', '').strip().lower() in ('1', 'on', 'true', 'yes'):
        return PassTimer(label)
    return None
