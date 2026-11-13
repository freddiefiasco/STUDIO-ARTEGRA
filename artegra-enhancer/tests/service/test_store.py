"""Atomic job persistence, state transitions, idempotency and interrupted-work recovery."""
import datetime
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from service import config, store
from service.logs import Logger
from service.settings import Settings, SettingsError
from service.util import atomic_write_json, read_json
from tests.service.helpers import REPO, rmtree, tmpdir


def job_record(jid='j000000000001', rid='a' * 32, body_hash='h1', n_items=2, stages=2):
    plan = {'ok': True, 'factor': 4, 'minutes': 12.0, 'output_size': [400, 400],
            'stages': [{'index': k, 'minutes': 6.0} for k in range(stages)]}
    return {'id': jid, 'created': '2026-11-05T10:00:00.000+00:00', 'client_request_id': rid, 'body_hash': body_hash,
            'settings': {}, 'effective': {'scale': 4}, 'output_dir': str(Path(tempfile.gettempdir()) / 'synthetic-output'), 'output_format': 'png8',
            'items': [{'id': f'i{i + 1:03d}', 'name': f'p{i}.png', 'media_id': 'm' + '0' * 12, 'state': 'queued',
                       'stage_index': 0, 'progress': 0.0, 'plan': plan, 'timings': {'stages': []}} for i in range(n_items)]}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.d = tmpdir()
        self.log = Logger(self.d / 'logs', self.d / 'jobs', echo=False)
        self.s = store.JobStore(self.d / 'jobs', self.log)

    def tearDown(self):
        rmtree(self.d)

    def test_state_machine(self):
        ok = [('queued', 'preparing'), ('preparing', 'running'), ('running', 'running'), ('running', 'finishing'),
              ('finishing', 'done'), ('running', 'interrupted'), ('interrupted', 'queued'), ('queued', 'cancelled'),
              ('preparing', 'queued'), ('running', 'failed')]
        for a, b in ok:
            store.check_transition(a, b)
        # v4: Stop this image and Queue again (stopped / failed / cancelled -> queued); a finished image never runs again
        for a, b in [('running', 'stopped'), ('queued', 'stopped'), ('preparing', 'stopped'), ('interrupted', 'stopped'),
                     ('stopped', 'queued'), ('stopped', 'cancelled'), ('failed', 'queued'), ('cancelled', 'queued')]:
            store.check_transition(a, b)
        for a, b in [('done', 'queued'), ('failed', 'running'), ('cancelled', 'running'), ('queued', 'done'),
                     ('queued', 'running'), ('finishing', 'running'), ('running', 'nonsense'), ('finishing', 'stopped'),
                     ('stopped', 'running'), ('done', 'stopped')]:
            with self.assertRaises(store.StateError, msg=(a, b)):
                store.check_transition(a, b)
        jid = 'j000000000001'
        self.s.create(job_record(jid))
        with self.assertRaises(store.StateError):
            self.s.update_item(jid, 'i001', state='done')
        self.assertEqual(self.s.item(jid, 'i001')['state'], 'queued')    # refused change left nothing behind

    def test_job_state_derivation(self):
        d = lambda *st: store.derive_job_state([{'state': s} for s in st])
        self.assertEqual(d('queued', 'queued'), 'queued')
        self.assertEqual(d('running', 'queued'), 'running')
        self.assertEqual(d('done', 'queued'), 'running')
        self.assertEqual(d('done', 'done'), 'done')
        self.assertEqual(d('done', 'failed'), 'failed')
        self.assertEqual(d('done', 'cancelled'), 'cancelled')
        self.assertEqual(d('cancelled', 'cancelled'), 'cancelled')
        self.assertEqual(d('done', 'stopped'), 'stopped')            # v4: nothing runs, one image waits for Queue again
        self.assertEqual(d('stopped', 'queued'), 'running')
        self.assertEqual(d('stopped', 'running'), 'running')

    def test_atomic_persistence_and_reload(self):
        jid = 'j000000000002'
        self.s.create(job_record(jid))
        self.s.update_item(jid, 'i001', state='preparing')
        self.s.update_item(jid, 'i001', state='running', stage_index=0)
        on_disk = read_json(self.d / 'jobs' / f'{jid}.json')
        self.assertEqual(on_disk['items'][0]['state'], 'running')
        self.assertEqual(on_disk['state'], 'running')
        # a crash during an atomic write leaves only a stray .tmp beside the intact record
        (self.d / 'jobs' / f'{jid}.json.1234.abcdef.tmp').write_text('{"half": ', encoding='utf8')
        # progress-only updates are throttled but flushed
        self.s.update_item(jid, 'i001', progress=0.5)
        self.s.flush()
        self.assertEqual(read_json(self.d / 'jobs' / f'{jid}.json')['items'][0]['progress'], 0.5)
        s2 = store.JobStore(self.d / 'jobs', self.log)
        self.assertEqual(s2.load_all(), 1)
        self.assertEqual(s2.item(jid, 'i001')['state'], 'running')
        self.assertFalse(list((self.d / 'jobs').glob('*.tmp')))
        lines = (self.d / 'jobs' / f'{jid}.jsonl').read_text(encoding='utf8').splitlines()
        self.assertTrue(any(json.loads(l)['event'] == 'job_created' for l in lines))

    def test_corrupt_record_set_aside(self):
        (self.d / 'jobs').mkdir(exist_ok=True)
        (self.d / 'jobs' / 'j00000000000f.json').write_text('{broken', encoding='utf8')
        s2 = store.JobStore(self.d / 'jobs', self.log)
        self.assertEqual(s2.load_all(), 0)
        self.assertTrue(s2.load_problems)
        self.assertTrue(list((self.d / 'jobs').glob('j00000000000f.json.unreadable-*')))

    def test_idempotency(self):
        a, created = self.s.create(job_record('j000000000003', rid='b' * 32, body_hash='H'))
        self.assertTrue(created)
        b, created = self.s.create(job_record('j000000000004', rid='b' * 32, body_hash='H'))
        self.assertFalse(created)
        self.assertEqual(b['id'], 'j000000000003')
        with self.assertRaises(store.Conflict):
            self.s.create(job_record('j000000000005', rid='b' * 32, body_hash='OTHER'))
        self.assertEqual(len(self.s.list()), 1)
        s2 = store.JobStore(self.d / 'jobs', self.log)   # the index survives a restart
        s2.load_all()
        with self.assertRaises(store.Conflict):
            s2.find_request('b' * 32, 'OTHER')
        self.assertEqual(s2.find_request('b' * 32, 'H')['id'], 'j000000000003')

    def test_fifo_order(self):
        self.s.create(job_record('j00000000000a', rid='1' * 32, n_items=2))
        later = job_record('j00000000000b', rid='2' * 32, n_items=1)
        later['created'] = '2026-11-05T11:00:00.000+00:00'
        self.s.create(later)
        self.assertEqual(self.s.next_queued(), ('j00000000000a', 'i001'))
        self.assertEqual(self.s.next_queued(exclude={('j00000000000a', 'i001')}), ('j00000000000a', 'i002'))
        self.s.update_item('j00000000000a', 'i001', state='cancelled')
        self.s.update_item('j00000000000a', 'i002', state='cancelled')
        self.assertEqual(self.s.next_queued(), ('j00000000000b', 'i001'))

    def test_recovery_requeues_at_first_missing_stage(self):
        jid = 'j00000000000c'
        rec = job_record(jid, n_items=4, stages=3)
        self.s.create(rec)
        self.s.update_item(jid, 'i001', state='preparing')
        self.s.update_item(jid, 'i001', state='running', stage_index=1)       # crashed in stage 1, stage 0 file exists
        self.s.update_item(jid, 'i002', state='preparing')
        self.s.update_item(jid, 'i002', state='running', stage_index=2)
        self.s.update_item(jid, 'i002', state='finishing')                   # all stages exist
        self.s.update_item(jid, 'i003', state='preparing')
        self.s.update_item(jid, 'i003', state='running')
        self.s.update_item(jid, 'i003', state='finishing')
        self.s.update_item(jid, 'i003', state='done')
        files = {('i001', 0), ('i002', 0), ('i002', 1), ('i002', 2)}
        s2 = store.JobStore(self.d / 'jobs', self.log)
        s2.load_all()
        n = s2.recover(lambda j, i, k: (i, k) in files)
        self.assertEqual(n, 2)
        a, b, c, d = (s2.item(jid, f'i00{x}') for x in range(1, 5))
        self.assertEqual((a['state'], a['stage_index']), ('queued', 1))
        self.assertEqual((b['state'], b['stage_index']), ('queued', 3))
        self.assertEqual(c['state'], 'done')                                 # untouched
        self.assertEqual((d['state'], d['stage_index']), ('queued', 0))
        self.assertIn('interrupted', [h['state'] for h in a['history']])

    def test_failed_save_changes_nothing_in_memory(self):
        jid = 'j00000000000e'
        self.s.create(job_record(jid, n_items=1))
        real = store.atomic_write_json

        def broken(path, obj):
            raise OSError(28, 'No space left on device')
        store.atomic_write_json = broken
        try:
            with self.assertRaises(OSError):
                self.s.update_item(jid, 'i001', state='preparing', message='Preparing')
            self.assertIn('could not save its job list', self.s.save_problem)
        finally:
            store.atomic_write_json = real
        it = self.s.item(jid, 'i001')
        self.assertEqual((it['state'], it.get('message')), ('queued', None))   # memory still matches the disk
        self.assertEqual(self.s.next_queued(), (jid, 'i001'))
        self.s.update_item(jid, 'i001', state='preparing')
        self.assertIsNone(self.s.save_problem)                                # cleared by the next good save
        # conditional updates never touch an item that has left the given states
        self.s.update_item(jid, 'i001', state='cancelled', message='Cancelled')
        self.assertIsNone(self.s.update_item(jid, 'i001', message='Pass 1 of 1', if_state=store.ACTIVE))
        self.assertEqual(self.s.item(jid, 'i001')['message'], 'Cancelled')

    def test_recovery_ends_a_requested_cancel_as_cancelled(self):
        jid = 'j00000000000f'
        self.s.create(job_record(jid, n_items=2, stages=2))
        for iid in ('i001', 'i002'):
            self.s.update_item(jid, iid, state='preparing')
            self.s.update_item(jid, iid, state='running', stage_index=1)
        self.s.update_item(jid, 'i001', cancel_requested=True, message='Cancelling')   # then the service died
        s2 = store.JobStore(self.d / 'jobs', self.log)
        s2.load_all()
        s2.recover(lambda j, i, k: k == 0)
        a, b = s2.item(jid, 'i001'), s2.item(jid, 'i002')
        self.assertEqual(a['state'], 'cancelled')
        self.assertEqual((b['state'], b['stage_index'], b['stage'], b['stages'], b['stages_done']), ('queued', 1, 1, 2, 1))

    def test_recovery_completes_published_item(self):
        jid = 'j00000000000d'
        self.s.create(job_record(jid, n_items=1))
        for st in ('preparing', 'running', 'finishing'):
            self.s.update_item(jid, 'i001', state=st)
        s2 = store.JobStore(self.d / 'jobs', self.log)
        s2.load_all()
        s2.recover(lambda *a: True, published_check=lambda job, it: (str(self.d / 'out' / 'p0_cu4x.png'), str(self.d / 'out' / 'p0_cu4x.json')))
        it = s2.item(jid, 'i001')
        self.assertEqual((it['state'], it['output']), ('done', str(self.d / 'out' / 'p0_cu4x.png')))
