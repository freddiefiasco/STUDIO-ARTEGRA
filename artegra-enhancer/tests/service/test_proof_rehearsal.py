"""The proof tools rehearsed end to end through a real developer-build service on the fake engine (engine design 7.4, 9.2):
one blind case's three runs (classic seed A, the Large-image engine on the classic plan through the developer force switch,
classic seed B), the 2 s sampler with Windows counters, the L3r record across each split (the memory cap 122.2 chosen, so
the forced plan splits every stage's finish into a fresh worker, and the fake engine holds memory so the commit fall is
seen), the analysis (fidelity and seams always; the halo metric when CU_HALO_TOOLS points at the halo tools), the pair maker,
the sealed key and the tally format. Synthetic images only.

The halo metric needs the halo tools' own interpreter (numpy, scipy, opencv, scikit-image), which is not the suite's: it runs
as a subprocess of that interpreter (python -m tools.proof.metrics measure), CU_HALO_PY naming it (a path, or 'py -3.12'),
else the Windows launcher's Python 3.12 where it imports the halo packages (tools/proof/halo_env). Without CU_HALO_TOOLS the
halo half is left out and the fidelity and seam checks run in the suite's own interpreter. With CU_HALO_TOOLS set and no
such interpreter, the test fails in plain words (build wave 4, WP3P-5): it never passes on fidelity and seams alone while
its halo half was asked for.

WRITTEN, NOT RUN in the proof package's worktree (it starts a service on the test ports; the merge role runs it first)."""
import datetime
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tests.service.helpers import gradient
from tests.service.test_banded_service import DEV
from tests.service.test_integration import Base, all_done
from tools.proof import halo_env

APP = Path(__file__).resolve().parents[2]
CAP = 122.2


def halo_python():
    """The halo tools' interpreter as a command list (tools/proof/halo_env.halo_python: CU_HALO_PY, else the Windows
    launcher's Python 3.12, each only when it imports the halo packages), else None."""
    return halo_env.halo_python()[0]


def measure_case(halo, src, outs, pos, d, py=None):
    """tools/proof/metrics.measure_case in the halo tools' interpreter (py, a command list; halo_python() by default):
    the arrays and positions through files."""
    import numpy as np
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / 'source.npy', src)
    args = []
    for k, v in outs.items():
        np.save(d / f'{k}.npy', v)
        args += [f"--{k.replace('_', '-')}", str(d / f'{k}.npy')]
    (d / 'seams.json').write_text(json.dumps(pos, default=int), encoding='utf8')
    cmd = (py or halo_python()) + ['-B', '-m', 'tools.proof.metrics', 'measure', '--halo', halo, '--source',
                                   str(d / 'source.npy'), '--seams', str(d / 'seams.json')] + args
    r = subprocess.run(cmd, cwd=str(APP), capture_output=True, text=True, timeout=1800,
                       env=dict(os.environ, CU_HALO_TOOLS=halo, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1'))
    if r.returncode != 0:
        raise AssertionError(f'the halo measurement failed: {r.stderr[-2000:]}')
    return json.loads(r.stdout.strip().splitlines()[-1])
SEEDS = {'A': 20261102, 'B': 20261120}
META = {'schema': 'creative-upscaler-settings-meta-v1', 'ram_cap_gb': {'chosen': True, 'saved': CAP}}


def facade(w=800, h=600, seed=3):
    """A small synthetic hard-geometry card: a gradient sky, dark windows with light frames and mullions."""
    a = gradient(w, h, seed).astype(np.float32) * 0.3 + 140
    for x in range(80, w - 60, 120):
        for y in range(300, h - 60, 110):
            a[y:y + 70, x:x + 50] = 40
            a[y - 4:y, x - 4:x + 54] = a[y + 70:y + 74, x - 4:x + 54] = 235
            a[y:y + 70, x + 23:x + 27] = 235
    return np.clip(a, 0, 255).astype(np.uint8)


class ProofRehearsal(Base):
    env = dict(DEV, CU_FAKE_PROCESS='1', CU_FAKE_HOLD_MB='512', CU_FAKE_STAGE_SECONDS='0.2')

    def run_case(self):
        state = self.d / 'state'
        state.mkdir(parents=True, exist_ok=True)
        (state / 'settings-meta.json').write_text(json.dumps(META), encoding='utf8')
        svc = self.service(settings={'ram_cap_gb': CAP})
        src = facade()
        (self.d / 'in').mkdir(parents=True, exist_ok=True)
        Image.fromarray(src).save(self.d / 'in' / 'facade.png')
        mid = self.add(svc, [self.d / 'in' / 'facade.png'])['items'][0]['id']
        from tools.proof import cases, sampler
        samples = self.d / 'samples.jsonl'
        s = sampler.Sampler(samples, 2.0, pids=lambda: {'service': svc.proc.pid}) if sys.platform == 'win32' else None
        if s:
            s.start()
        case = {'id': 'R1', 'mode': 'redux', 'factor': 2}
        runs = {}
        try:
            for run in cases.RUNS:
                body = cases.job_body(case, run, mid, SEEDS, f'reh-{run}')
                job = self.job(svc, body['media_ids'], body['settings'],
                               **({'dev_force_engine': 'banded'} if 'dev_force_engine' in body else {}))
                runs[run] = svc.wait_job(job['id'], all_done, timeout=300)
        finally:
            if s:
                s.stop()
        return svc, src, runs, samples

    def test_one_blind_case_end_to_end(self):
        from tools.proof import metrics, packets, pairs, records, sampler, seams, tally
        svc, src, runs, samples = self.run_case()
        for run, job in runs.items():
            self.assertEqual(job['items'][0]['state'], 'done', (run, job['items'][0]))
        bes = runs['bes_a']['items'][0]
        self.assertEqual(bes['plan']['engine'], 'banded')
        self.assertTrue(bes['plan']['banded']['forced'])
        classic = runs['classic_a']['items'][0]
        self.assertEqual([s['supersample'] for s in bes['plan']['stages']],
                         [s['supersample'] for s in classic['plan']['stages']])

        # the registered plan record of the Large-image run, and the L3r marks of its split against it
        cl = packets.classic_plan(800, 600, 2, CAP)
        rec = packets.plan_record(packets.forced(cl, CAP), CAP, 'bes')
        self.assertTrue(all(s['split_finish'] for s in rec['stages']))
        log = '\n'.join(json.dumps(r) for r in svc.log_lines())
        l3r = records.l3r_marks(bes, log, rec)
        self.assertTrue(l3r['pass'], json.dumps(l3r, indent=1))
        self.assertTrue(l3r['log_agrees'])
        self.assertEqual([r['stage'] for r in l3r['records']], l3r['expected_stages'])
        for r in l3r['records']:
            self.assertGreaterEqual(r['stopped_worker_last_commit_gb'], 0.5, r)       # the fake engine's 512 MiB

        # the 2 s sampler with the node's Windows counters
        if sys.platform == 'win32':
            rows = sampler.read_samples(samples)
            self.assertGreaterEqual(len(rows), 2)
            self.assertTrue(all('perf' in r and 'pagefile' in r for r in rows))
            summ = sampler.summarize(rows)
            self.assertGreater(summ['peak']['proc_commit_gb'], 0)

        # the analysis: fidelity and seams on every output (the halo metric with its tools)
        outs = {}
        for run, job in runs.items():
            with Image.open(job['items'][0]['output']) as im:
                outs[run] = np.asarray(im.convert('RGB'))
        pos = seams.positions(classic['plan']['stages'], ('classic', 'bes'))
        try:
            halo, py = halo_env.halo_half()        # CU_HALO_TOOLS set and no interpreter: a plain failure (WP3P-5)
        except halo_env.HaloUnavailable as e:
            self.fail(str(e))
        if halo:
            m = measure_case(halo, src, outs, pos, self.d / 'halo', py)
            self.assertTrue(m['result']['comparable'], m['result']['not_comparable'])
            self.assertTrue(m['halo']['sha256'])
            worst = (m['worst']['classic_a'], m['worst']['bes_a'])
        else:
            for k, v in outs.items():
                f = metrics.fidelity(src, v)
                self.assertEqual(sorted(f), ['sigma_1', 'sigma_4'], k)
                self.assertIn('max_z', seams.detect(v, pos.get('rows'), pos.get('cols')))
            worst = ([], [])

        # the pair maker, the sealed key, the tally format
        pdir, sealed = self.d / 'pairs', self.d / 'sealed'
        crops = pairs.select_crops(worst[0], worst[1], pos, src, 2)
        self.assertTrue(crops)
        man, key = pairs.make_pairs('R1', outs['classic_a'], outs['bes_a'], src, 2, crops, pdir)
        msha = pairs.write_manifest(pdir, man)
        text = (pdir / 'PAIRS.json').read_text(encoding='utf8').lower()
        for word in ('classic', 'bes', 'banded', 'large-image', 'identical'):
            self.assertNotIn(word, text)
        ksha = pairs.write_key(sealed / 'KEY.json', key, pdir, msha)
        self.assertFalse((pdir / 'KEY.json').exists())
        now = datetime.datetime.now(datetime.timezone.utc)
        verdicts, shas = {}, {}
        for judge in tally.JUDGES:
            v = {'format': tally.VERDICT_FORMAT, 'judge': judge, 'written_at': now.isoformat(timespec='seconds'),
                 'pairs_manifest_sha256': msha,
                 'verdicts': {row['pair']: dict({c: 'same' for c in tally.CRITERIA}, artefacts=[]) for row in man}}
            self.assertEqual(tally.validate_verdicts(v, man), [])
            verdicts[judge] = v
            shas[judge] = 'f' * 64
        opened = (now + datetime.timedelta(minutes=1)).isoformat(timespec='seconds')
        t = tally.tally(verdicts, pairs.read_key(sealed / 'KEY.json', ksha), man, shas, ksha, opened, msha)
        self.assertEqual(tally.validate_tally(t), [])
        self.assertIn('R1', t['cases'])

    def test_a_plan_the_planner_refuses_is_not_run(self):
        from tools.proof import packets
        p = packets.classic_plan(3500, 2188, 8, CAP)
        self.assertFalse(p.ok)
        self.assertTrue(packets.plan_record(packets.forced(p, CAP), CAP)['refused'])


if __name__ == '__main__':
    unittest.main()
