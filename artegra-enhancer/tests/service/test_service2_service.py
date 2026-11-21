"""5.0.2 build wave 2, service package: the real service on the fake engine (written, not run in the package worktree; the
merge role runs it first, adds merge_runs_first). Sizes and synthetic images only.

- Start-up recovery: a Large-image result found already published at a restart gets its viewer copies again from its own
  planes, never a classic view.jpg and never a whole decode (merge report item 15).
- The banded-classes guard: on an engine whose Large-image classes did not load (the fake engine's 'missingbanded' fault
  drops two of them from /object_info; service/workers.py sets banded_missing from it, contract worker_banded), a
  Large-image image fails in plain words with the event banded_classes_missing and keeps its work files, while a classic
  image on the same engine runs.
- Physical memory (A5): with the fake engine's CU_FAKE_MEMORY, a Large-image image waits in plain words naming its size
  while the memory is short, and a size this computer can never hold is refused at queue time, naming it.
- Bolt's forced plan (contract bolt): a forced developer Bolt run plans through plan_forced(..., mode='fast'), runs the
  Large-image engine with the Fast recipe (the fake engine's stand-in, CU_FAST_TEST), and its sidecar carries the recipe's
  sidecar keys as the classic Bolt sidecar does. Needs the plan package's plan_forced(mode=) and banded Bolt (B16)."""
import json
import time
import unittest

from tests.service.test_banded_service import DEV, strip_input
from tests.service.test_integration import Base, all_done

WIDE = (4000, 64)                       # 8x: 32,000 x 512 px, three Large-image passes


class Recovery(Base):
    env = DEV

    def test_a_published_large_image_result_gets_its_viewer_copies_from_its_planes_after_a_restart(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2'})
        mid = self.add(svc, [strip_input(self.d / 'in', 'wide.png', *WIDE)])['items'][0]['id']
        job = svc.wait_job(self.job(svc, [mid], {'scale': 8})['id'], all_done, timeout=240)
        it = job['items'][0]
        self.assertEqual((it['state'], it['plan'].get('engine')), ('done', 'banded'), it)
        self.assertEqual(svc.shutdown(), 0)
        views = self.d / 'state' / 'media' / 'results' / f'{job["id"]}_{it["id"]}'
        self.assertTrue((views / 'result.plane').is_file())
        for name in ('proxy.jpg', 'thumb.jpg'):
            (views / name).unlink()                                      # the copies a crash left unmade
        rec_path = self.d / 'state' / 'jobs' / f'{job["id"]}.json'
        rec = json.loads(rec_path.read_text(encoding='utf8'))
        rec['items'][0]['state'] = 'finishing'                           # a result published just before the crash
        rec['items'][0]['history'].append({'ts': 'x', 'state': 'finishing'})
        rec['state'] = 'running'
        rec_path.write_text(json.dumps(rec), encoding='utf8')
        svc2 = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2'})
        j2 = svc2.wait_job(job['id'], all_done, timeout=60)
        self.assertEqual(j2['items'][0]['state'], 'done')
        t0 = time.monotonic()                     # the copies are made by a thread after the recovery: wait for its line
        while time.monotonic() - t0 < 60 and 'result_views_rebuilt' not in [l.get('event') for l in svc2.log_lines()]:
            time.sleep(0.2)
        events = [l.get('event') for l in svc2.log_lines()]
        self.assertIn('item_recovered_done', events)
        self.assertIn('result_views_rebuilt', events)
        self.assertNotIn('result_view_failed', events)
        self.assertTrue((views / 'proxy.jpg').is_file() and (views / 'thumb.jpg').is_file())
        self.assertFalse((views / 'view.jpg').exists())                 # never a classic view of a Large-image result
        q = f'kind=result&job={job["id"]}&item={it["id"]}'
        code, _, _ = svc2.get(f'/api/media/{mid}/proxy?{q}', raw=True)
        self.assertEqual(code, 200)
        self.assertEqual(svc2.shutdown(), 0)


class TheBandedClassesGuard(Base):
    env = DEV

    def test_a_large_image_image_on_an_engine_without_its_classes_fails_plainly(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_FAULT': 'missingbanded'})
        mid = self.add(svc, [strip_input(self.d / 'in', 'wide.png', *WIDE)])['items'][0]['id']
        job = svc.wait_job(self.job(svc, [mid], {'scale': 8})['id'], all_done, timeout=120)
        it = job['items'][0]
        self.assertEqual(it['state'], 'failed', it)
        self.assertEqual(it['message'], 'Parts of the Large-image engine did not load when the engine started, so this '
                                        'image was not upscaled. Choose Repair installation in Settings.')
        lines = [l for l in svc.log_lines() if l.get('event') == 'banded_classes_missing']
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['data']['missing'], ['CUCannyPlane', 'CUFinishBanded'])
        self.assertTrue((self.d / 'state' / 'work' / job['id']).exists())     # the work files are kept for a retry
        small = self.add(svc, [strip_input(self.d / 'in', 'small.png', 640, 480)])['items'][0]['id']
        j2 = svc.wait_job(self.job(svc, [small], {'scale': 2})['id'], all_done, timeout=120)
        self.assertEqual(j2['items'][0]['state'], 'done')                  # a classic image never checks it
        self.assertEqual(svc.shutdown(), 0)


class PhysicalMemory(Base):
    env = DEV

    def test_a_large_image_image_waits_in_plain_words_while_memory_is_short(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_MEMORY': '64,9'})
        mid = self.add(svc, [strip_input(self.d / 'in', 'wide.png', *WIDE)])['items'][0]['id']
        jid = self.job(svc, [mid], {'scale': 8})['id']
        j = svc.wait_job(jid, lambda j: j['items'][0]['message'].startswith('Waiting for memory'), timeout=30)
        msg = j['items'][0]['message']
        self.assertEqual(j['items'][0]['state'], 'queued')
        self.assertIn('32,000 × 512 px', msg)
        self.assertIn('system memory (RAM)', msg)
        held = [l for l in svc.log_lines() if l.get('event') == 'item_held_memory']
        self.assertTrue(held and held[-1]['data'].get('planes_gb') is not None)
        self.assertEqual(svc.shutdown(), 0)

    def test_a_size_this_computer_can_never_hold_is_refused_naming_it(self):
        svc = self.service(env={'CU_FAKE_MEMORY': '12,11'})
        mid = self.add(svc, [strip_input(self.d / 'in', 'wide.png', *WIDE)])['items'][0]['id']
        res = self.job(svc, [mid], {'scale': 8}, expect=400)
        self.assertEqual(res['error']['code'], 'plan_refused')
        self.assertIn('32,000 × 512 px', res['error']['message'])
        self.assertIn('more than this computer can free (12 GB in all)', res['error']['message'])
        self.assertEqual(svc.shutdown(), 0)

    def test_a_classic_image_is_admitted_as_5_0_1(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_MEMORY': '64,9'})
        mid = self.add(svc, [strip_input(self.d / 'in', 'small.png', 640, 480)])['items'][0]['id']
        j = svc.wait_job(self.job(svc, [mid], {'scale': 2})['id'], all_done, timeout=120)
        self.assertEqual(j['items'][0]['state'], 'done')
        self.assertEqual(svc.shutdown(), 0)


class BoltsForcedPlan(Base):
    env = dict(DEV, CU_FAST_TEST='1')

    def test_a_forced_bolt_run_carries_the_recipes_sidecar_keys(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2'})
        mid = self.add(svc, [strip_input(self.d / 'in', 'small.png', 1280, 960)])['items'][0]['id']
        job = self.job(svc, [mid], {'scale': 2, 'mode': 'fast'}, dev_force_engine='banded')
        plan = job['items'][0]['plan']
        self.assertEqual(plan.get('engine'), 'banded', plan)
        self.assertTrue(plan['banded']['forced'])
        self.assertEqual(plan['banded']['mode'], 'bolt')                    # plan_forced got the run mode
        job = svc.wait_job(job['id'], all_done, timeout=120)
        it = job['items'][0]
        self.assertEqual(it['state'], 'done', it)
        side = json.loads(open(it['sidecar'], encoding='utf8').read())
        self.assertEqual(side['engine']['executor'], 'large-image')
        fast = side['engine']['fast']
        self.assertEqual((fast['recipe'], fast['version']), ('test-fast', '0'))   # the recipe's own sidecar keys
        self.assertEqual(side['effective']['mode'], 'fast')
        self.assertEqual(svc.shutdown(), 0)


if __name__ == '__main__':
    unittest.main()
