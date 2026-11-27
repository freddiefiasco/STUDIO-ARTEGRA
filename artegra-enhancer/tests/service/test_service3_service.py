"""5.0.2 build wave 3 through a real service on the fake engine (BUILD-WAVE-3 service package): the start-up probe's wiring
(contracts.g1u) with the launcher's stand-ins (tests/qa/launch_service.py CU_TEST_BXF_G1U: the engine environment and a stub
probe by selfprobe.py's command line), the developer keep-planes setting (contracts.keep_planes) and its refusal by a release
build, and the finish record's sidecar fields.

WRITTEN, NOT RUN by its package (no package starts a service on the workstation: ports 18950-18969 are shared with v6's
suite); the merge role runs it first (adds merge_runs_first), after the plan package's merge (BXF_TABLE decides the finish
tier). Sizes and synthetic pictures only."""
import json
import sys
import unittest
from pathlib import Path

from PIL import Image

from engine.bxf import g1
from tests.service.helpers import split_strip_height
from tests.service.test_banded_service import DEV, strip_input
from tests.service.test_integration import Base, all_done
from tests.test_service3_probe import STUB

Image.MAX_IMAGE_PIXELS = None


def unmatched_env():
    return dict(g1.committed_tables()[-1]['environment'], processor='Test processor (no G1 table)')


class G1uBase(Base):
    def stub(self, mode='write'):
        d = self.d / 'stub'
        d.mkdir(parents=True, exist_ok=True)
        (d / 'selfprobe_stub.py').write_text(STUB, encoding='utf8')
        (d / 'base.json').write_text(json.dumps(g1.committed_tables()[-1]), encoding='utf8')
        return {'CU_STUB_PROBE_MODE': mode, 'CU_STUB_PROBE_BASE': str(d / 'base.json'),
                'CU_STUB_PROBE_ENV': json.dumps(unmatched_env()), 'CU_STUB_PROBE_ARGS': str(d / 'args.json'),
                'CU_TEST_BXF_G1U': json.dumps({'environment': 'unmatched',
                                               'probe': [sys.executable, '-I', '-B', str(d / 'selfprobe_stub.py')]})}

    def run_job(self, svc, h=64, timeout=300, **extra):
        mid = self.add(svc, [strip_input(self.d / 'in', f'wide{h}.png', 4000, h)])['items'][0]['id']
        job = self.job(svc, [mid], {'scale': 8}, **extra)
        self.assertEqual(job['items'][0]['plan'].get('engine'), 'banded', job['items'][0]['plan'])
        return job, svc.wait_job(job['id'], all_done, timeout=timeout)


class TheCommittedTable(G1uBase):
    env = dict(DEV, CU_TEST_BXF_G1U=json.dumps({'environment': 'committed:1'}))

    def test_the_workstations_table_counts_the_banded_finish_and_no_probe_runs(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.1'})
        job, done = self.run_job(svc)
        it = done['items'][0]
        self.assertEqual(it['state'], 'done', it)
        self.assertEqual(job['items'][0]['plan']['banded']['finish_tier'], 'bxf')
        self.assertEqual(job['items'][0]['plan']['banded'].get('bxf_table'), 'committed')
        events = [e.get('event') for e in svc.log_lines()]
        self.assertIn('bxf_table', events)
        self.assertNotIn('bxf_probe_start', events)
        side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
        self.assertEqual(side['engine']['cpu_capability'], g1.committed_tables()[1]['environment']['cpu_capability'])
        self.assertEqual(side['engine']['bxf_table'], 'committed')
        self.assertEqual([x['finish_tier'] for x in side['engine']['bxf_stages']], ['bxf'] * 3)


class TheProbe(G1uBase):
    env = DEV

    def test_the_probe_runs_alone_then_the_image_takes_the_table(self):
        svc = self.service(env=dict(self.stub('write'), CU_FAKE_STAGE_SECONDS='0.1'))
        job, done = self.run_job(svc)
        it = done['items'][0]
        self.assertEqual(it['state'], 'done', it)
        self.assertEqual(job['items'][0]['plan']['banded']['finish_tier'], 'tier3')      # planned before the table
        events = [e.get('event') for e in svc.log_lines()]
        self.assertEqual(events.count('bxf_probe_start'), 1)
        self.assertIn('bxf_probe_done', events)
        self.assertIn('item_replanned', events)
        self.assertLess(events.index('bxf_probe_done'), events.index('item_dispatched'))      # never beside an image
        self.assertEqual(it['plan']['banded']['finish_tier'], 'bxf')
        self.assertTrue((self.d / 'state' / 'bxf' / 'local-table.json').is_file())
        args = json.loads((self.d / 'stub' / 'args.json').read_text(encoding='utf8'))
        self.assertIn('--cap-gib', args)
        side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
        self.assertEqual(side['engine']['bxf_table'], 'local')

    def test_a_probe_that_runs_out_of_time_leaves_tier_3(self):
        svc = self.service(env=dict(self.stub('exit2'), CU_FAKE_STAGE_SECONDS='0.1'))
        job, done = self.run_job(svc)
        it = done['items'][0]
        self.assertEqual(it['state'], 'done', it)
        self.assertEqual(it['plan']['banded']['finish_tier'], 'tier3')
        failed = [e for e in svc.log_lines() if e.get('event') == 'bxf_probe_failed']
        self.assertEqual(len(failed), 1)
        self.assertIn('did not finish in time', failed[0]['msg'])
        self.assertFalse((self.d / 'state' / 'bxf' / 'local-table.json').exists())


class KeepPlanes(Base):
    def test_a_release_build_refuses_it(self):
        svc = self.service()
        mid = self.add(svc, [strip_input(self.d / 'in', 'wide.png', 4000, 64)])['items'][0]['id']
        job = self.job(svc, [mid], {'scale': 2}, expect=400, dev_keep_planes=True)
        self.assertEqual(job['error']['code'], 'dev_setting')
        self.assertEqual(job['error']['message'], 'This developer setting is not available in this build.')

    def test_a_developer_build_keeps_every_pass(self):
        self.env = DEV
        H = split_strip_height()
        self.assertIsNotNone(H)
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.1'})
        mid = self.add(svc, [strip_input(self.d / 'in', 'wide.png', 4000, H)])['items'][0]['id']
        job = self.job(svc, [mid], {'scale': 8}, dev_keep_planes=True)
        done = svc.wait_job(job['id'], all_done, timeout=300)
        it = done['items'][0]
        self.assertEqual(it['state'], 'done', it)
        kept = self.d / 'state' / 'work' / job['id'] / 'i001' / 'kept'
        self.assertEqual(sorted(p.name for p in kept.iterdir()),
                         ['s0', 's1', 's2', 'stage0.u8', 'stage1.u8', 'stage2.u8'])
        # Compare resolved paths: a temp folder given in its 8.3 short form (as on GitHub's Windows runner) and the
        # service's long form name the same file.
        self.assertTrue({str(Path(p).resolve()) for p in it['timings']['kept']} >= {str((kept / 'stage2.u8').resolve())})


if __name__ == '__main__':
    unittest.main()
