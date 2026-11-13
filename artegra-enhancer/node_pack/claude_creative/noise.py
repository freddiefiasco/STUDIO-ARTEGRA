"""Noise implementation."""


import concurrent.futures
import contextlib
import logging
import time

import torch


class _Run:
    """One sampling run: its sigmas (as the sampler sees them, CPU 0-dim tensors), the worker, the counters."""

    def __init__(self, sigmas):
        s = sigmas.detach().flatten().cpu() if torch.is_tensor(sigmas) else torch.as_tensor(sigmas).flatten()
        self.sig_t = [s[i] for i in range(s.numel())]
        self.sig_f = [float(v) for v in self.sig_t]
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='claude-noise-prefetch')
        self.stats = {'samplers': 0, 'draws': 0, 'prefetched': 0, 'mispredicted': 0, 'on_demand': 0, 'wait_s': 0.0,
                      'prefetch_errors': 0}

    def next_pair(self, sigma_next_value):
        """(sigma_j, sigma_j+1) of the next noise draw after a draw that ended at sigma_next_value, or None. dpmpp_2m_sde draws
        no noise for a step that ends at sigma 0."""
        idx = [i for i, v in enumerate(self.sig_f) if v == sigma_next_value]
        if len(idx) != 1:
            return None
        j = idx[0]
        if j + 1 >= len(self.sig_f) or self.sig_f[j + 1] == 0:
            return None
        return self.sig_t[j], self.sig_t[j + 1]


def _mode_ctx(mode):
    inference, grad = mode
    if inference:
        return torch.inference_mode(True)
    if not grad:
        return torch.no_grad()
    return contextlib.nullcontext()


def make_class(base, run):
    class PrefetchBrownianTreeNoiseSampler(base):
        """The stock BrownianTreeNoiseSampler, with the next draw computed ahead on a background CPU thread."""
        _claude_prefetch = True

        def __init__(self, x, sigma_min, sigma_max, seed=None, transform=lambda x: x, cpu=False):
            super().__init__(x, sigma_min, sigma_max, seed=seed, transform=transform, cpu=cpu)
            self._run = run
            self._pending = None
            self._mode = (torch.is_inference_mode_enabled(), torch.is_grad_enabled())
            run.stats['samplers'] += 1
            if self.tree.cpu_tree and len(run.sig_t) > 1 and run.sig_f[1] != 0:
                self._submit(run.sig_t[0], run.sig_t[1])

        def _bounds(self, sigma, sigma_next):
            t0, t1 = self.transform(torch.as_tensor(sigma)), self.transform(torch.as_tensor(sigma_next))
            a, b, sign = self.tree.sort(t0, t1)
            return t0, t1, a, b, sign

        def _draw(self, ac, bc):
            with _mode_ctx(self._mode):
                return [tree(ac, bc) for tree in self.tree.trees]

        def _submit(self, s0, s1):
            try:
                _, _, a, b, _ = self._bounds(s0, s1)
                ac, bc = a.detach().cpu().float(), b.detach().cpu().float()
                self._pending = ((float(ac), float(bc)), self._run.pool.submit(self._draw, ac, bc))
            except Exception:
                self._pending = None
                self._run.stats['prefetch_errors'] += 1

        def __call__(self, sigma, sigma_next):
            if not self.tree.cpu_tree:
                return super().__call__(sigma, sigma_next)
            t0, t1, a, b, sign = self._bounds(sigma, sigma_next)
            device, dtype = a.device, a.dtype
            ac, bc = a.detach().cpu().float(), b.detach().cpu().float()
            key = (float(ac), float(bc))
            st = self._run.stats
            st['draws'] += 1
            parts = None
            pend, self._pending = self._pending, None
            tw = time.perf_counter()
            if pend is not None:
                pkey, fut = pend
                try:
                    res = fut.result()      
                except Exception:
                    res = None
                    st['prefetch_errors'] += 1
                if res is not None and pkey == key:
                    parts = res
                    st['prefetched'] += 1
                else:
                    st['mispredicted'] += 1
            if parts is None:
                parts = self._run.pool.submit(self._draw, ac, bc).result()
                st['on_demand'] += 1
            st['wait_s'] += time.perf_counter() - tw
            w = torch.stack(parts).to(device=device, dtype=dtype) * (self.tree.sign * sign)
            w = w if self.tree.batched else w[0]
            out = w / (t1 - t0).abs().sqrt()
            nxt = self._run.next_pair(float(torch.as_tensor(sigma_next)))
            if nxt is not None:
                self._submit(*nxt)
            return out

    return PrefetchBrownianTreeNoiseSampler


class Handle:
    def __init__(self, ks, base, cls, run):
        self.ks, self.base, self.cls, self.run = ks, base, cls, run

    def uninstall(self):
        if self.ks.BrownianTreeNoiseSampler is self.cls:
            self.ks.BrownianTreeNoiseSampler = self.base
        self.run.pool.shutdown(wait=True, cancel_futures=True)
        st = dict(self.run.stats)
        st['wait_s'] = round(st['wait_s'], 4)
        return st


def install(sigmas):
    """Install the prefetching sampler for one sampling run; returns a Handle (call uninstall() in a finally block) or None."""
    import comfy.k_diffusion.sampling as ks
    base = ks.BrownianTreeNoiseSampler
    if getattr(base, '_claude_prefetch', False) or base.__module__ != ks.__name__ or base.__name__ != 'BrownianTreeNoiseSampler':
        logging.info('ClaudeSpotTiles noise_prefetch: not installed (another noise sampler patch is active: %r)', base)
        return None
    run = _Run(sigmas)
    cls = make_class(base, run)
    ks.BrownianTreeNoiseSampler = cls
    return Handle(ks, base, cls, run)
