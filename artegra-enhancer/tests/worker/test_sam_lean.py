"""ClaudeSAM3DetectLean (node_pack/claude_creative/sam_lean.py) against ComfyUI's own SAM3_Detect, on synthetic images.

The stock code is read from a ComfyUI source tree named by CU_COMFY_SOURCE (the runtime's ComfyUI folder), and each file read is
first checked against runtime/source-manifest.json (its git blob hash), so the comparison is with the exact code the app ships:
- comfy_extras/nodes_sam3.py: SAM3_Detect.execute, _extract_text_prompts and _refine_mask, as written;
- comfy/ldm/sam3/detector.py: SAM3Detector.forward, as written (where orig_size scales the boxes and upsamples every query mask);
- comfy/utils.py: common_upscale, as written.
Only the network is a stand-in: a deterministic detector core (_get_backbone_features, the text resizer, _detect) and a
deterministic forward_segment, so the masks, boxes and scores depend on the image and the prompt as a real model's do.

What is checked, for float32, bfloat16 and float16, odd and even sizes, one and several kept objects, no kept object, and
individual masks on and off: the lean node's masks are the stock node's to the bit, its boxes and scores are the stock's, and it
never upsamples more than the kept masks to the full input.
Skipped where torch is not installed or CU_COMFY_SOURCE is not set:
    CU_COMFY_SOURCE=<ComfyUI folder> python -B -m unittest tests.worker.test_sam_lean   (from the artegra-enhancer folder)."""
import ast
import hashlib
import importlib.util
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

HAVE_TORCH = importlib.util.find_spec('torch') is not None
ROOT = Path(__file__).resolve().parents[2]
COMFY = os.environ.get('CU_COMFY_SOURCE')
MANIFEST = json.loads((ROOT / 'runtime' / 'source-manifest.json').read_text(encoding='utf8'))['files']


def blob_sha1(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def shipped_source(rel):
    """The text of a ComfyUI file, after checking it is the runtime's own (git blob hash in runtime/source-manifest.json)."""
    data = (Path(COMFY) / rel).read_bytes()
    if blob_sha1(data) != MANIFEST[rel]['blob']:
        raise AssertionError(f'{rel} in CU_COMFY_SOURCE is not the runtime\'s file')
    return data.decode('utf8')


def extract(src, path, names, glb):
    """Compile the named top-level functions, or Class.method functions, of a source text on their own, in `glb`."""
    tree = ast.parse(src)
    out = {}
    for name in names:
        if '.' in name:
            cls, meth = name.split('.')
            node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
            fn = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == meth)
        else:
            fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        fn = ast.FunctionDef(**{k: getattr(fn, k) for k in fn._fields if k != 'decorator_list'}, decorator_list=[])
        mod = ast.Module(body=[fn], type_ignores=[])
        ast.fix_missing_locations(mod)
        exec(compile(mod, path, 'exec'), glb)
        out[name] = glb[fn.name]
    return out


@unittest.skipUnless(HAVE_TORCH and COMFY, 'needs torch and CU_COMFY_SOURCE (the runtime ComfyUI folder)')
class LeanSamAgainstComfyUIsSam3Detect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        import torch.nn.functional as F
        cls.torch, cls.F = torch, F
        cpu = torch.device('cpu')
        utils_g = {'torch': torch}
        common_upscale = extract(shipped_source('comfy/utils.py'), 'comfy/utils.py', ['common_upscale'], utils_g)['common_upscale']

        class ProgressBar:
            def __init__(self, total):
                self.total = total

            def update(self, n):
                pass

        mm = types.ModuleType('comfy.model_management')
        mm.load_model_gpu = lambda model: None
        mm.get_torch_device = lambda: cpu
        mm.intermediate_device = lambda: cpu
        cu = types.ModuleType('comfy.utils')
        cu.common_upscale = common_upscale
        cu.ProgressBar = ProgressBar
        comfy = types.ModuleType('comfy')
        comfy.model_management, comfy.utils = mm, cu
        io = types.SimpleNamespace(NodeOutput=lambda *a: a)
        g = {'torch': torch, 'F': F, 'comfy': comfy, 'json': json, 'io': io}
        src = shipped_source('comfy_extras/nodes_sam3.py')
        fns = extract(src, 'comfy_extras/nodes_sam3.py', ['_extract_text_prompts', '_refine_mask', 'SAM3_Detect.execute'], g)
        cls.stock_execute = staticmethod(lambda *a, **k: fns['SAM3_Detect.execute'](None, *a, **k))
        ns3 = types.ModuleType('comfy_extras.nodes_sam3')
        ns3._extract_text_prompts, ns3._refine_mask = fns['_extract_text_prompts'], fns['_refine_mask']
        extras = types.ModuleType('comfy_extras')
        extras.nodes_sam3 = ns3
        cls.modules = {'comfy': comfy, 'comfy.model_management': mm, 'comfy.utils': cu, 'comfy_extras': extras,
                       'comfy_extras.nodes_sam3': ns3}
        dg = {'torch': torch, 'F': F}
        cls.detector_forward = extract(shipped_source('comfy/ldm/sam3/detector.py'), 'comfy/ldm/sam3/detector.py',
                                       ['SAM3Detector.forward'], dg)['SAM3Detector.forward']
        spec = importlib.util.spec_from_file_location('cu_sam_lean_test', ROOT / 'node_pack' / 'claude_creative' / 'sam_lean.py')
        cls.lean_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.lean_mod)

    # ---- a deterministic stand-in for SAM 3.1 -------------------------------------------------------------------------
    def model(self, dtype, queries=200, res=72, seed=0, hot=3):
        torch, F = self.torch, self.F
        detector_forward = self.detector_forward
        gen = torch.Generator().manual_seed(seed)
        qe = torch.randn(queries, 8, generator=gen)
        filt = torch.randn(8, 3, 3, 3, generator=gen) * 0.6
        box_lo = torch.rand(queries, 2, generator=gen) * 0.6
        box_hi = box_lo + 0.05 + torch.rand(queries, 2, generator=gen) * 0.35
        boxes = torch.cat([box_lo, box_hi.clamp(max=1.0)], 1)                       # normalized xyxy
        bias = torch.full((queries,), -6.0)
        bias[torch.randperm(queries, generator=gen)[:hot]] = torch.linspace(1.0, 3.0, hot)   # a few queries over 0.6

        class Core:
            backbone = {'language_backbone': {'resizer': lambda t: t[..., :8] * 0.5}}

            def _get_backbone_features(self, images):
                x = F.interpolate(images.float(), size=(res, res), mode='area')
                feats = F.conv2d(x, filt, padding=1)                                  # [1, 8, res, res]
                return [feats.to(images.dtype)], [None], None, None

            def _detect(self, features, positions, text_embeddings=None, text_mask=None, points=None, boxes_in=None):
                f = features[0].float()
                t = text_embeddings.float().mean(1)                                   # [1, 8]
                masks = torch.einsum('qc,bchw->bqhw', qe, f) + (qe @ t[0])[None, :, None, None] * 0.2
                scores = bias + (qe @ t[0]) * 0.05
                return (boxes[None].to(features[0].dtype), scores[None].to(features[0].dtype),
                        masks.to(features[0].dtype), {})

        core = Core()

        class Sam3:
            def __call__(self, images, **kw):
                return detector_forward(core, images, **kw)

            def forward_segment(self, images, point_inputs=None, box_inputs=None, mask_inputs=None):
                m = F.interpolate(mask_inputs.float(), size=(1008, 1008), mode='bilinear', align_corners=False)
                return (m * 0.9 + (images.float().mean(1, keepdim=True) - 0.45) * 3.0).to(images.dtype)

        inner = types.SimpleNamespace(get_dtype=lambda: dtype, diffusion_model=Sam3())
        return types.SimpleNamespace(model=inner)

    def image(self, h, w, seed):
        torch = self.torch
        gen = torch.Generator().manual_seed(seed)
        y = torch.linspace(0, 1, h)[:, None]
        x = torch.linspace(0, 1, w)[None, :]
        base = torch.stack([(x * 7 + y * 3) % 1.0, ((x * 11).floor() + (y * 5).floor()) % 2 * 0.8 + 0.1,
                            torch.rand(h, w, generator=gen)], -1)
        return base[None].float()

    def cond(self, seed, multi=None):
        torch = self.torch
        gen = torch.Generator().manual_seed(100 + seed)
        emb = torch.randn(1, 6, 16, generator=gen)
        if multi:
            return [[emb, {'sam3_multi_cond': [{'cond': torch.randn(1, 6, 16, generator=gen), 'attention_mask': None,
                                                'max_detections': k} for k in multi]}]]
        return [[emb, {'attention_mask': torch.ones(1, 6, dtype=torch.int64)}]]

    def both(self, model, img, cond, individual=False, iterations=2):
        stock = self.stock_execute(model, img, conditioning=cond, threshold=0.6, refine_iterations=iterations,
                                   individual_masks=individual)
        calls = []
        real = self.F.interpolate

        def spy(x, size=None, **kw):
            out = real(x, size=size, **kw)
            calls.append(tuple(out.shape))
            return out
        with mock.patch.dict(sys.modules, self.modules), mock.patch.object(self.F, 'interpolate', spy):
            lean = self.lean_mod.ClaudeSAM3DetectLean().run(model, img, cond, 0.6, iterations, individual)
        return stock, lean, calls

    def assert_same(self, stock, lean, what):
        torch = self.torch
        self.assertEqual(stock[0].dtype, lean[0].dtype, what)
        self.assertEqual(tuple(stock[0].shape), tuple(lean[0].shape), what)
        self.assertTrue(torch.equal(stock[0], lean[0]), f'{what}: {int((stock[0] != lean[0]).sum())} differing mask values')
        self.assertEqual(stock[1], lean[1], what)

    # ---- the checks ---------------------------------------------------------------------------------------------------
    def test_the_masks_are_the_stock_nodes_to_the_bit(self):
        torch = self.torch
        n = 0
        for dtype in (torch.float32, torch.bfloat16, torch.float16):
            for (h, w) in ((64, 64), (101, 333), (777, 1001), (1000, 750)):
                for seed in (0, 1):
                    model = self.model(dtype, seed=seed)
                    img = self.image(h, w, seed)
                    stock, lean, calls = self.both(model, img, self.cond(seed))
                    self.assert_same(stock, lean, (dtype, h, w, seed))
                    self.assertGreater(float(lean[0].sum()), 0.0, 'a kept object')
                    big = [c for c in calls if c[-2:] == (h, w)]
                    self.assertTrue(big and all(c[-3] == 1 for c in big), calls)     # only one channel at the full size
                    n += 1
        self.assertEqual(n, 24)

    def test_several_kept_objects_and_individual_masks(self):
        torch = self.torch
        for individual in (False, True):
            model = self.model(torch.float32, seed=3, hot=6)
            img = self.image(300, 520, 3)
            stock, lean, calls = self.both(model, img, self.cond(3, multi=(1, 3, 5)), individual=individual)
            self.assert_same(stock, lean, individual)
            self.assertEqual(len(lean[1][0]), 1 + 3 + 5)

    def test_no_kept_object(self):
        torch = self.torch
        model = self.model(torch.float32, seed=4, hot=0)
        img = self.image(200, 120, 4)
        stock, lean, calls = self.both(model, img, self.cond(4))
        self.assert_same(stock, lean, 'none kept')
        self.assertEqual(float(lean[0].sum()), 0.0)
        self.assertEqual(lean[1], [[]])

    def test_without_refinement(self):
        torch = self.torch
        model = self.model(torch.float16, seed=5)
        img = self.image(257, 129, 5)
        stock, lean, calls = self.both(model, img, self.cond(5), iterations=0)
        self.assert_same(stock, lean, 'refine 0')

    def test_the_lean_node_declares_the_stock_inputs(self):
        it = self.lean_mod.ClaudeSAM3DetectLean.INPUT_TYPES()
        self.assertEqual(sorted(it['required']), sorted(['model', 'image', 'conditioning', 'threshold', 'refine_iterations',
                                                         'individual_masks']))
        self.assertEqual(self.lean_mod.ClaudeSAM3DetectLean.RETURN_TYPES, ('MASK', 'BOUNDING_BOX'))


if __name__ == '__main__':
    unittest.main()
