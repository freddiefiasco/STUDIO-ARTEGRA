"""The node pack's detailed-preview decoder lookup names no network location (QA1-02).

The decoder is found where the app's workers register it (vae_approx in the models folder) or where
CLAUDE_LIVE_TAESD points. With neither, the fallback is empty: loading '' fails at once, the failure is recorded and
the preview carries on with the rough (latent2rgb) picture. The fallback must not be None, because ComfyUI's TAESD
builds a decoder with untrained weights when it is given no path. Saved images never use this decoder.
"""
import contextlib
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "node_pack" / "claude_creative" / "live.py"


def load_live():
    """node_pack/claude_creative/live.py on its own, with a stand-in torch (the test environment has no torch)."""
    torch = types.ModuleType("torch")
    torch.inference_mode = contextlib.nullcontext
    with mock.patch.dict(sys.modules, {"torch": torch}):
        spec = importlib.util.spec_from_file_location("node_pack_live_under_test", LIVE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def comfy_taesd():
    """A stand-in for comfy.taesd.taesd with ComfyUI's contract: weights load only when a path is given, and a
    missing file raises (torch.load / safetensors)."""
    taesd = types.ModuleType("comfy.taesd.taesd")

    class TAESD:
        def __init__(self, encoder_path=None, decoder_path=None, latent_channels=4):
            if decoder_path is not None and not Path(decoder_path).is_file():
                raise FileNotFoundError(decoder_path)
    taesd.TAESD = TAESD
    return {"comfy": types.ModuleType("comfy"), "comfy.taesd": types.ModuleType("comfy.taesd"), "comfy.taesd.taesd": taesd}


class PreviewDecoderFallback(unittest.TestCase):
    def setUp(self):
        self.live = load_live()
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("CLAUDE_LIVE_TAESD", None)

    def tearDown(self):
        self.env.stop()

    def test_the_fallback_is_empty_and_names_no_network_location(self):
        with mock.patch.dict(sys.modules, {"folder_paths": None}):
            found = self.live._find_taesd()
        self.assertEqual(found, "")
        self.assertIsNotNone(found)
        self.assertEqual(self.live.TAESD_FALLBACK, "")
        self.assertFalse(hasattr(self.live, "TAESD_NAS"))
        source = LIVE.read_bytes()
        self.assertNotIn(bytes([92]) * 2, source.split(b"TAESD_FALLBACK = ", 1)[1].split(b"\n", 1)[0])

    def test_the_registered_models_folder_still_wins(self):
        folder_paths = types.ModuleType("folder_paths")
        folder_paths.get_filename_list = lambda kind: ["other.pth", "taesdxl_decoder.safetensors"] if kind == "vae_approx" else []
        folder_paths.get_full_path = lambda kind, name: "models/" + kind + "/" + name
        with mock.patch.dict(sys.modules, {"folder_paths": folder_paths}):
            self.assertEqual(self.live._find_taesd(), "models/vae_approx/taesdxl_decoder.safetensors")
        os.environ["CLAUDE_LIVE_TAESD"] = "chosen.safetensors"
        self.assertEqual(self.live._find_taesd(), "chosen.safetensors")

    def test_an_empty_fallback_fails_at_once_and_the_preview_goes_rough(self):
        em = types.SimpleNamespace(taesd_path="")
        meta = {}
        self.live._TAESD.clear()
        self.live._TAESD_FAILED.clear()
        with mock.patch.dict(sys.modules, comfy_taesd()):
            self.assertIsNone(self.live._decode_taesd(em, None, types.SimpleNamespace(type="cpu"), meta))
        self.assertIn("FileNotFoundError", meta["taesd_error"])
        self.assertTrue(self.live._TAESD_FAILED.get(""))
        self.assertEqual(self.live._TAESD, {})


if __name__ == "__main__":
    unittest.main()
