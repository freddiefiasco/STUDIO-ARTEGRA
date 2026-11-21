"""5.0.2 (build wave 2, service package, item 2; contract worker_banded): before a Large-image prompt, the service refuses
it in plain words on an engine whose Large-image node classes did not load. service/workers.py (integ) sets
Worker.banded_missing after each start: None while unknown (go on as before), [] when every class loaded, else the sorted
list of the graph_banded.NODE_SPECS classes it lacks. A classic prompt never checks it.

banded_runner functions with a stub runner and stub workers; no engine, no service."""
import ast
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from service import banded_runner
from service.runner import ItemFailure

ROOT = Path(__file__).resolve().parents[1]


def worker(missing, **kw):
    return SimpleNamespace(gpu=0, banded_missing=missing, **kw)


class TheCheck(unittest.TestCase):
    def test_unknown_goes_on_as_before(self):
        self.assertIsNone(banded_runner.check_banded_classes(worker(None)))
        self.assertIsNone(banded_runner.check_banded_classes(SimpleNamespace(gpu=0)))     # a worker without the field

    def test_every_class_loaded_goes_on(self):
        self.assertIsNone(banded_runner.check_banded_classes(worker([])))

    def test_missing_classes_refuse_in_plain_words(self):
        with self.assertRaises(ItemFailure) as e:
            banded_runner.check_banded_classes(worker(['CUFinishBanded', 'CUCannyPlane']))
        f = e.exception
        self.assertEqual(f.event, 'banded_classes_missing')
        self.assertEqual(f.text, banded_runner.CLASSES_MISSING)
        self.assertEqual(f.data['missing'], ['CUCannyPlane', 'CUFinishBanded'])
        self.assertTrue(f.keep_work)                 # the image can run again once the engine is repaired
        self.assertFalse(f.kill_worker)              # the engine still runs classic images
        self.assertNotIn('CU', f.text)               # plain words: no class names in the person's text


class BeforeEveryPrompt(unittest.TestCase):
    def test_no_prompt_is_sent_to_an_engine_without_its_classes(self):
        client = mock.Mock()
        w = worker(['CUDecodePlane'], client=client, client_id='c', ws=None)
        r = SimpleNamespace(log=mock.Mock())
        with self.assertRaises(ItemFailure) as e:
            banded_runner._run_prompt(r, w, SimpleNamespace(jid='j', iid='i'), {'1': {'class_type': 'CUPlaneInput',
                                                                                    'inputs': {}}}, 'rid', 0, 1, {}, {},
                                      'cu_j_i_s0', None)
        self.assertEqual(e.exception.event, 'banded_classes_missing')
        client.prompt.assert_not_called()

    def test_an_unknown_or_complete_engine_gets_its_prompt(self):
        for missing in (None, []):
            client = mock.Mock()
            client.prompt.return_value = 'rid'
            w = worker(missing, client=client, client_id='c', ws=None)
            r = SimpleNamespace(log=mock.Mock(), _deadline_s=lambda ctx, st: 60.0,
                                _wait_prompt=mock.Mock(return_value={'ok': True}))
            hist, pid = banded_runner._run_prompt(r, w, SimpleNamespace(jid='j', iid='i', prompt_id=None), {}, 'rid', 0, 1,
                                                  {}, {'minutes': 1.0}, 'cu_j_i_s0', None)
            client.prompt.assert_called_once()
            self.assertEqual(pid, 'rid')

    def test_the_stage_refuses_before_it_touches_a_saved_checkpoint(self):
        with TemporaryDirectory() as td:
            work = Path(td) / 'work'
            plane_dir = work / 'j' / 'i' / 'planes' / 's0'
            plane_dir.mkdir(parents=True)
            (plane_dir / banded_runner.CHECKPOINT_FILE).write_text('{}', encoding='utf8')
            r = SimpleNamespace(banded_pack={'ok': True}, cfg=SimpleNamespace(work_dir=work),
                                _stage_disk_check=mock.Mock(side_effect=AssertionError('reached the stage')))
            st = {'factor': 2.0, 'supersample': 2.0, 'output_size': [2400, 2400], 'render_size': [4800, 4800],
                  'padded_size': [1200, 1200], 'input_size': [1200, 1200], 'minutes': 1.0}
            it = {'plan': {'engine': 'banded', 'stages': [st], 'banded': {}}}
            with self.assertRaises(ItemFailure) as e:
                banded_runner.run_stage(r, worker(['CUFinishBanded']), SimpleNamespace(jid='j', iid='i'), {}, {}, 0, 1, it)
            self.assertEqual(e.exception.event, 'banded_classes_missing')
            self.assertTrue((plane_dir / banded_runner.CHECKPOINT_FILE).is_file())


class ClassicPromptsNeverCheck(unittest.TestCase):
    def test_only_the_large_image_stage_reads_the_field(self):
        runner_src = (ROOT / 'service' / 'runner.py').read_text(encoding='utf-8')
        self.assertNotIn('banded_missing', runner_src)
        self.assertNotIn('check_banded_classes', runner_src)
        tree = ast.parse((ROOT / 'service' / 'banded_runner.py').read_text(encoding='utf-8'))
        callers = sorted({fn.name for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef)
                          for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == 'check_banded_classes'})
        self.assertEqual(callers, ['_run_prompt', 'run_stage'])


if __name__ == '__main__':
    unittest.main()
