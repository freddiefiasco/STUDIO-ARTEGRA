"""tools/proof/halo_env.py (build wave 4, WP3P-5): the halo half runs in an interpreter with the halo tools' packages, or,
when CU_HALO_TOOLS asks for it and none is found, the rehearsal fails in plain words instead of passing on fidelity and
seams alone. In process, with the interpreter probe stubbed (no interpreter is started)."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.proof import halo_env


def runner(ok):
    """A stub subprocess.run: the probe of a command in `ok` (as a tuple) succeeds, any other fails."""
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        base = tuple(cmd[:-2])                          # the command without '-c <probe>'
        return subprocess.CompletedProcess(cmd, 0 if base in ok else 1)
    run.calls = calls
    return run


class HaloHalf(unittest.TestCase):
    def test_without_cu_halo_tools_the_halo_half_is_left_out_by_choice(self):
        run = runner(set())
        self.assertEqual(halo_env.halo_half({}, run=run, which=lambda n: None, platform='win32'), (None, None))
        self.assertEqual(run.calls, [])                 # nothing is probed when nothing asks for the halo half
        self.assertIn('left out', halo_env.LEFT_OUT)

    def test_the_launcher_s_python_3_12_with_the_packages_is_taken(self):
        run = runner({('py', '-3.12')})
        env = {'CU_HALO_TOOLS': 'halo-tools'}
        self.assertEqual(halo_env.halo_half(env, run=run, which=lambda n: 'py.exe', platform='win32'),
                         ('halo-tools', ['py', '-3.12']))
        self.assertEqual(run.calls[0][-1], 'import scipy, cv2, skimage')

    def test_cu_halo_py_names_the_interpreter(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'python.exe'
            exe.write_bytes(b'')
            run = runner({(str(exe),)})
            env = {'CU_HALO_TOOLS': 'halo-tools', 'CU_HALO_PY': str(exe)}
            self.assertEqual(halo_env.halo_half(env, run=run, which=lambda n: None)[1], [str(exe)])
        run = runner({('py', '-3.12')})
        self.assertEqual(halo_env.halo_half({'CU_HALO_TOOLS': 'h', 'CU_HALO_PY': 'py -3.12'}, run=run)[1], ['py', '-3.12'])

    def check_refusal(self, half):
        env = {'CU_HALO_TOOLS': 'halo-tools'}
        for kw in ({'run': runner(set()), 'which': lambda n: 'py.exe', 'platform': 'win32'},     # py -3.12 lacks them
                   {'run': runner(set()), 'which': lambda n: None, 'platform': 'win32'},         # no launcher
                   {'run': runner(set()), 'which': lambda n: None, 'platform': 'linux'}):
            with self.assertRaises(halo_env.HaloUnavailable) as c:
                half(env, **kw)
            self.assertIn('CU_HALO_TOOLS is set', str(c.exception))
            self.assertIn('Set CU_HALO_PY', str(c.exception))
        with self.assertRaises(halo_env.HaloUnavailable) as c:
            half(dict(env, CU_HALO_PY='nowhere/python.exe'), run=runner(set()))
        self.assertIn('CU_HALO_PY (nowhere/python.exe) does not import scipy, cv2, skimage', str(c.exception))

    def test_cu_halo_tools_without_an_interpreter_fails_in_plain_words(self):
        self.check_refusal(halo_env.halo_half)

    def test_a_mutant_that_falls_back_to_fidelity_and_seams_turns_it_red(self):
        def wave3(env, **kw):                          # wave 3: no interpreter, so the halo half was silently left out
            cmd, _ = halo_env.halo_python(env, **kw)
            return (env.get('CU_HALO_TOOLS'), cmd) if cmd else (None, None)
        with self.assertRaises(AssertionError):
            self.check_refusal(wave3)


if __name__ == '__main__':
    unittest.main()
