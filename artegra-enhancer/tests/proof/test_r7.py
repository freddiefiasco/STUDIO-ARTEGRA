"""tools/proof/r7.py on a stub (no card): host memory in place of the card's, so the probe's readings, rises, ratios, the
work drive's space and its record format are checked without a GPU. Inside a real Windows Job (the probe run as a child
of service/windows_job.WindowsJobProcess) the Job commit is read too; outside one it is recorded as unmeasured."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tools.proof import r7

ROOT = Path(__file__).resolve().parents[2]
MIB = 1 << 20


class Stub(unittest.TestCase):
    def test_rows_rises_and_ratios_on_host_memory(self):
        alloc, free, label = r7.stub_allocator()
        with tempfile.TemporaryDirectory() as d:
            rec = r7.probe([32 * MIB, 96 * MIB], alloc, free, work_dir=d, settle_s=0.05, label=label)
        self.assertEqual(rec['format'], 'cu-r7-1')
        self.assertEqual([r['bytes'] for r in rec['rows']], [32 * MIB, 96 * MIB])
        self.assertIn('context', rec)
        self.assertGreater(rec['work_drive']['free_bytes'], 0)
        if sys.platform == 'win32':
            for r in rec['rows']:
                self.assertGreater(r['private_ratio'], 0.9, r)           # a touched host buffer is all commit
                self.assertLess(r['private_ratio'], 1.2, r)
                self.assertLess(abs(r['private_left_after_free']), 0.5 * r['bytes'], r)
        in_job = r7.own_job_memory()[0] is not None                      # a shell may run the tests inside a Job
        self.assertEqual('job_commit' in rec['unmeasured'], not in_job)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows Jobs')
    def test_inside_a_job_the_job_commit_is_read(self):
        from service import windows_job
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            out = Path(d) / 'r7.json'
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            p = windows_job.WindowsJobProcess([sys.executable, '-B', '-m', 'tools.proof.r7', '--stub', '--sizes-mib', '64',
                                               '--settle', '0.05', '--work', d, '--out', str(out)], cwd=str(ROOT), env=env,
                                              log_path=Path(d) / 'log.txt')
            try:
                self.assertEqual(p.wait(120), 0, (Path(d) / 'log.txt').read_text(encoding='utf8', errors='replace'))
            finally:
                p.close()
            rec = json.loads(out.read_text(encoding='utf8'))
        self.assertTrue(rec['stub'])
        self.assertNotIn('job_commit', rec['unmeasured'])
        row = rec['rows'][0]
        self.assertGreater(row['job_commit_ratio'], 0.9, row)
        self.assertLess(row['job_commit_ratio'], 1.2, row)

    def test_the_stub_free_empties_the_holder(self):
        alloc, free, _ = r7.stub_allocator()
        box = [alloc(4096)]
        self.assertIsNone(free(box))
        self.assertEqual(box, [])

    def test_the_registered_record_names_the_sizes_and_the_disk_rule(self):
        from tools.proof import packets
        r = packets.r7_record()
        self.assertEqual(r['sizes_gib'], [2, 8, 16])
        self.assertEqual(r['disk_threshold_gb'], 130.0)
        self.assertIn('no pass or fail', r['rule'])


class _Tensor:
    """A stand-in CUDA tensor: weakref-able, so the fake torch can tell whether anything still holds it."""

    def __init__(self, n):
        self.n = int(n)

    def fill_(self, v):
        return self


class _FakeCuda:
    """torch.cuda as the probe uses it. empty_cache records, at each call, the stand-in tensors still referenced: the real
    allocator hands a block back to the driver only once no tensor references it, so a live one here means the 'after'
    reading would still count the block (the check's finding: free() ran while probe() held the tensor)."""

    def __init__(self):
        self.refs, self.calls = [], []

    def synchronize(self, device=None):
        pass

    def empty_cache(self):
        self.calls.append([r().n for r in self.refs if r() is not None])

    def memory_reserved(self, device=None):
        return sum(r().n for r in self.refs if r() is not None)

    def get_device_name(self, device=None):
        return 'stand-in card'

    def live(self):
        return [r().n for r in self.refs if r() is not None]


def fake_torch():
    import types
    import weakref
    cuda = _FakeCuda()

    def empty(n, dtype=None, device=None):
        t = _Tensor(n)
        cuda.refs.append(weakref.ref(t))
        return t
    return types.SimpleNamespace(empty=empty, uint8='uint8', cuda=cuda, __version__='stand-in')


class _Gpu:
    """The probe's GPU counters, here recording which stand-in tensors are alive at each reading."""

    def __init__(self, cuda):
        self.cuda, self.seen = cuda, []

    def read(self):
        self.seen.append(self.cuda.live())
        return None, None

    def close(self):
        pass


class CudaFree(unittest.TestCase):
    """The card path's free (cuda_allocator) with a stand-in torch: the probe must drop every reference to an allocation
    before torch's cache is emptied, so the block goes back to the driver and each row starts from the card as it was."""

    def test_nothing_is_held_when_the_cache_is_emptied_or_after_a_free(self):
        from unittest import mock
        t = fake_torch()
        with mock.patch.dict(sys.modules, {'torch': t}):
            alloc, free, label = r7.cuda_allocator(0)
            gpu = _Gpu(t.cuda)
            rec = r7.probe([2 * MIB, 8 * MIB, 16 * MIB], alloc, free, settle_s=0.0, label=label, gpu=gpu)
        # one empty_cache per free: the context row's and each size row's, each with nothing referenced
        self.assertEqual(len(t.cuda.calls), 4, t.cuda.calls)
        self.assertEqual(t.cuda.calls, [[], [], [], []])
        # readings: context before / after, then per row before, held, after. Only 'held' sees the allocation.
        seen = gpu.seen
        self.assertEqual(seen[0], [])
        self.assertEqual(seen[1], [1])                               # the context's one-byte allocation, held
        for k, n in enumerate((2 * MIB, 8 * MIB, 16 * MIB)):
            before, held, after = seen[2 + 3 * k: 5 + 3 * k]
            self.assertEqual(before, [], f'row {k}: an earlier allocation still held at its baseline')
            self.assertEqual(held, [n])
            self.assertEqual(after, [], f'row {k}: the allocation still held at the after-free reading')
        self.assertEqual([r['reserved_after_free'] for r in rec['rows']], [0, 0, 0])
        self.assertEqual(rec['context']['reserved_after_free'], 0)


if __name__ == '__main__':
    unittest.main()
