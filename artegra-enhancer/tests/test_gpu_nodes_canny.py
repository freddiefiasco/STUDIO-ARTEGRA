"""CUCannyPlane's tile grid and hysteresis (node_pack/claude_banded/canny_plane.py) against ClaudeCannyTiled's own lines
(node_pack/claude_creative/__init__.py), on mapped planes, for synthetic low/strong masks with components that cross the
2048 px tile grid, at odd sizes: the same label array, the same kept set, the same edges (0 differing values). The kornia part
(the tiles themselves on a canvas): tests/worker/test_gpu_nodes_canny.py. Needs scipy (skipped where it is not installed;
run with the worker runtime's Python)."""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from engine import planes
from tests import test_gpu_nodes_helpers as H

HAVE_SCIPY = importlib.util.find_spec('scipy') is not None
CLASSIC = (H.ROOT / 'node_pack' / 'claude_creative' / '__init__.py').read_text(encoding='utf8')
# ClaudeCannyTiled.run's hysteresis, as written (checked against the source below)
CLASSIC_HYSTERESIS = ('lab, n = label(low, structure=np.ones((3, 3), bool))\n'
                      'keep = np.zeros(n + 1, bool); keep[np.unique(lab[high])] = True; keep[0] = False\n'
                      'out = keep[lab]\n')


def classic_tiles(H_, W_, tile):
    """The tile loop of ClaudeCannyTiled.run, compiled from its source: [(y0, y1, x0, x1, ya, xa, yb, xb)]."""
    tree = ast.parse(CLASSIC)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ClaudeCannyTiled')
    run = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    loop = next(n for n in ast.walk(run) if isinstance(n, ast.For) and ast.unparse(n.target) == 'y0')
    inner = loop.body[0]
    body = [s for s in inner.body if ast.unparse(s).startswith(('y1, x1 =', 'ya, xa, yb, xb ='))]
    inner.body = body + ast.parse('out.append((y0, y1, x0, x1, ya, xa, yb, xb))').body
    loop.body = [inner]
    g = {'H': H_, 'W': W_, 'tile': tile, 'M': 8, 'out': []}
    exec(compile(ast.Module(body=[loop], type_ignores=[]), 'ClaudeCannyTiled', 'exec'), g)
    return g['out']


def masks(h, w, seed):
    """Weak and strong masks like Canny's: thin 8-connected strokes (diagonals, staircases, long runs that cross the 2048 px
    grid), isolated weak pixels, and strong pixels on some strokes only."""
    rng = np.random.default_rng(seed)
    low = rng.random((h, w)) < 0.004
    y, x = np.mgrid[0:h, 0:w]
    for k in range(6):
        a, b = rng.integers(0, 97, 2)
        low |= ((x + a) % 211 == (y * (k + 1) + b) % 211) & (rng.random((h, w)) < 0.97)
    low[:, 2040:2056] |= (y[:, 2040:2056] % 37 == 0)
    low[2040:2056, :] |= (x[2040:2056, :] % 41 == 0)
    high = low & (rng.random((h, w)) < 0.01)
    high.flat[np.flatnonzero(low)[::97]] = True                      # strong pixels on some strokes, at any size
    return low, high


@unittest.skipUnless(HAVE_SCIPY, 'scipy is not installed here (run on the worker runtime)')
class HysteresisOnPlanesIsTheClassics(unittest.TestCase):
    def test_the_classic_lines_are_as_written(self):
        for line in CLASSIC_HYSTERESIS.splitlines()[:2]:
            self.assertIn(line, CLASSIC)
        self.assertIn('outs.append(torch.from_numpy(keep[lab]))', CLASSIC)
        self.assertIn('low[y0:y1, x0:x1] = (e > 0).cpu().numpy(); high[y0:y1, x0:x1] = (e == 1).cpu().numpy()', CLASSIC)

    def test_labels_kept_set_and_edges(self):
        from scipy.ndimage import label
        cp = H.module('canny_plane')
        for (h, w, band) in ((517, 1033, 2304), (2101, 4099, 2304), (2311, 2053, 7), (64, 3, 288)):
            low, high = masks(h, w, h * 7 + w)
            g = {'label': label, 'np': np, 'low': low, 'high': high}
            exec(CLASSIC_HYSTERESIS, g)
            with tempfile.TemporaryDirectory() as td:
                d = Path(td)
                lp = planes.from_array(d / 'low.plane', low.astype(np.uint8))
                hp = planes.from_array(d / 'high.plane', high.astype(np.uint8))
                lab = planes.Plane.create(d / 'lab.plane', (h, w, 1), 'i32')
                out = planes.Plane.create(d / 'edges.plane', (h, w, 1), 'u8')
                n = cp.hysteresis(planes.Plane.open(lp.path), planes.Plane.open(hp.path), lab, out, band=band)
                self.assertEqual(n, g['n'], (h, w))
                got_lab = lab.read_rows(0, h)[..., 0]
                self.assertEqual(int((got_lab != g['lab']).sum()), 0, (h, w))
                got = out.read_rows(0, h)[..., 0]
                self.assertEqual(got.dtype, np.uint8)
                self.assertEqual(int((got != g['out'].astype(np.uint8)).sum()), 0, (h, w))
                self.assertGreater(int(got.sum()), 0)
                self.assertLess(int(got.sum()), int(low.sum()))          # some weak components were dropped
                del got_lab, lab, out


class TheTileGridIsTheClassics(unittest.TestCase):
    def test_same_tiles_same_order(self):
        cp = H.module('canny_plane')
        for (h, w, tile) in ((2048, 2048, 2048), (2049, 4097, 2048), (517, 1033, 256), (8, 5000, 2048), (12001, 31999, 2048)):
            flat = [t for row in cp.tile_grid(h, w, tile) for t in row]
            self.assertEqual(flat, classic_tiles(h, w, tile), (h, w, tile))
            for row in cp.tile_grid(h, w, tile):
                self.assertEqual(len({(t[0], t[1], t[4], t[6]) for t in row}), 1)      # one band of rows per tile row


if __name__ == '__main__':
    unittest.main()
