import os
import time
import unittest
from unittest import mock

from service import comfy, config, workers
from service.logs import Logger
from service.settings import Settings
from tests.service.helpers import rmtree, tmpdir


class FeedBeforeReady(unittest.TestCase):
    def setUp(self):
        self.d = tmpdir()
        self.cfg = config.load(self.d / 'state', fake_engine=True)
        config.ensure_state_dirs(self.cfg)
        self.log = Logger(self.cfg.logs_dir, self.cfg.jobs_dir, echo=False)
        self.settings = Settings(self.d / 'settings.json', self.d / 'out', self.log)
        self.workers = []

    def tearDown(self):
        for w in self.workers:
            try:
                w.stop('test end')
            except Exception as e:
                print(f'worker stop failed: {e}')
        rmtree(self.d)

    def worker(self):
        w = workers.Worker(0, self.cfg, self.settings, self.log, 'fake')
        self.workers.append(w)
        return w

    @staticmethod
    def late_connect(seconds):
        real = comfy.WebSocket.connect

        def connect(*a, **kw):
            time.sleep(seconds)
            return real(*a, **kw)
        return mock.patch.object(comfy.WebSocket, 'connect', side_effect=connect)

    def events(self, name):
        return [r for r in self.log.recent(limit=500) if r.get('event') == name]

    def test_a_late_feed_is_waited_for(self):
        w = self.worker()
        with self.late_connect(0.8):
            t0 = time.monotonic()
            w.ensure_started()
            took = time.monotonic() - t0
        self.assertEqual(w.state, 'ready')
        self.assertIsNotNone(w.ws.last_message)
        self.assertTrue(w.ws.connected)
        self.assertGreaterEqual(took, 0.75)
        self.assertEqual(self.events('worker_feed_late'), [])

    def test_a_feed_that_stays_silent_holds_the_start_only_so_long(self):
        w = self.worker()
        with mock.patch.object(workers, 'FEED_WAIT_S', 0.4), self.late_connect(3.0):
            t0 = time.monotonic()
            w.ensure_started()
            took = time.monotonic() - t0
        self.assertEqual(w.state, 'ready')
        self.assertLess(took, 2.5)
        late = self.events('worker_feed_late')
        self.assertEqual(len(late), 1)
        self.assertEqual(late[0]['level'], 'warn')
        self.assertEqual(late[0]['msg'], 'The progress feed of the engine on GPU 1 did not answer within 0.4 s; progress is '
                                         'read by polling until it does')

    def test_a_refused_feed_does_not_hold_the_start(self):
        w = self.worker()
        with mock.patch.dict(os.environ, {'CU_FAKE_FAULT': 'nows'}):
            t0 = time.monotonic()
            w.ensure_started()
            took = time.monotonic() - t0
        self.assertEqual(w.state, 'ready')
        self.assertLess(took, workers.FEED_WAIT_S - 1.0)
        self.assertGreaterEqual(w.ws.disconnects, 1)
        self.assertEqual(self.events('worker_feed_late'), [])

    def test_a_start_stopped_while_it_waits_for_the_feed_is_stopped(self):
        w = self.worker()
        waited = []
        real = workers.Worker._wait_feed

        def wait_feed(self_, abort=None):
            waited.append(time.monotonic())
            return real(self_, abort)
        t0 = time.monotonic()
        with self.late_connect(3.0), mock.patch.object(workers.Worker, '_wait_feed', wait_feed):
            with self.assertRaises(workers.WorkerError) as cm:
                w.ensure_started(abort=lambda: bool(waited) and time.monotonic() - waited[0] > 0.3)
        self.assertEqual(str(cm.exception), 'The engine start was stopped.')
        self.assertEqual(w.state, 'stopped')
        self.assertEqual(len(waited), 1)
        self.assertLess(time.monotonic() - t0, 2.5)


if __name__ == '__main__':
    unittest.main()
