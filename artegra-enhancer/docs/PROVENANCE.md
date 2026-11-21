# Source provenance

The user-selected source is the v5 early preview deployed on 13 November 2026 at 11:09 local time. It was imported from an immutable, allowlisted local snapshot. The original source and preview installation were not edited.

Reference snapshot tree SHA-256:

`cd2fd9c2f7eec3c7347d57afbd5260a1aaf61e4637a7952999fd1ee0763f6342`

The import includes only `engine/`, `service/`, `node_pack/`, the Creative Upscaler QML components, gallery components, and the service entry point. The preview's installed QML overrides for its wrapper, tab and API client were included in the reference. No original application binary, window-frame source or internal history was imported.

`SOURCE-MAP.json` records original and public hashes for each imported path and labels additions. Per-file hashes represent the exact snapshot rather than a moving branch.

Public adaptation removes private paths, comments and historical metadata. The service gets portable configuration, process-ID ownership, an authenticated endpoint and a separate notification identity. The QML API client uses the endpoint supplied by the new host. Preferences use the standalone application's namespace. The host's frame and Settings are new.

The tests compare 184 generated Standard/Fast graph cases to SHA-256 values calculated from the immutable source snapshot, covering all five Looks, four image sizes, chained 4× stages, speed-stack states, Standard pass ordering and Fast preview modes. This is prompt identity evidence, not rendered-pixel identity evidence.

## 5.0.0-beta.1: the final v5

"The final v5" here is version 5 of Studio Artegra's in-house app (its Creative Upscaler tab), the source this standalone is made from; it is not a release of Artegra Enhancer. The Beta takes the final v5's tab, service and finish-time logic (after its four QA and fix rounds, 16 November 2026) through a three-way merge: base = the early preview above, ours = the standalone, theirs = the final v5. A frozen copy of the final v5's in-scope files had the tree hash

`3ccc1ddcfbda32a0a1dcbbe2b0eb389d14a86777f5e9ed643858f862b2e07127`

(SHA-256 over the sorted lines `path NUL sha256 LF` of 136 files under engine/, service/, node_pack/, ui/qml/ and cu_service.py). Of these, 99 needed nothing (the final v5 had not changed them), 21 took the final v5's code with comments removed (the standalone had changed only comments), 2 more merged cleanly, 3 had one conflict each (the old port range and one helper line; the standalone's side was kept) and the window wrapper stayed the standalone's. The final v5's engine and node pack are byte-identical to the early preview, so the standalone's engine and node pack are unchanged. One exception came later (release QA, 18 November 2026): in `node_pack/claude_creative/live.py` the detailed-preview decoder's fallback, a fixed location, is now empty, so without a decoder in the models folder the preview uses the rough picture. `node_pack/MANIFEST.json`, which the engine checks at start, records the file's new hash. SOURCE-MAP marks both files with the beta layer. Saved images do not use that decoder.

The final v5's tab had two more fix rounds after that copy was taken (17 November 2026: the Mode follows a Look, factor or fine-tuning Bolt cannot make; an Undo puts back only each image's own factor; a change made while Bolt's files are checked stays on the waiting images). They changed only `ui/qml/creative/CreativeUpscalerTab.qml` and `ui/qml/creative/CuSettingsPanel.qml`, and came into the Beta by a forward three-way merge (base = the copy above, theirs = the final v5 after the rounds, both with comments removed and the Redux and Bolt names applied; ours = the Beta), which merged without conflicts. The final v5's tree after the rounds is

`5a960d40d4c196e8f4cd4bd7acbeb4ea34c0a7e9e6c4a05e8a05602f01ea7cfc`

(the same 136 files and method). No engine, node pack or service file changed in those rounds.

`SOURCE-MAP.json` records, per file, the final v5's SHA-256 and this release's. The Beta's own changes (the Redux and Bolt names and marks, the two-card Bolt rule, the update check, the uninstaller, the About page and the name) are listed in CHANGELOG.md, with the hardening round's small fixes from a UI/UX audit (modal Settings and About, honest start-up and engine-stopped states, the Save GPU memory retry, track contrast, preferences kept per state folder, the stale close prompt, the Shortcuts list, Windows reduced motion). `tests/test_service_prompt_identity.py` checks that the prompts the service sends for every Look, scale and mode equal the final v5's.

## 5.0.2 (in development): the Large-image engine and the SAM step that fits the card

5.0.2 is built on 5.0.1 as published. Its new code was written for Artegra Enhancer; nothing in it is imported from the final v5 or from another product. Where a new file follows third-party code step for step, the line below names it. The private merge verification described above covers the files as 5.0.0-beta.1 released them and does not cover 5.0.2's changes. Their checks are the 5.0.2 identity harness instead: `tests/test_engine_identity.py` (G0a-G0c: every plan 5.0.1 makes keeps its plan, its graph hashes and its classic engine and node-pack files), the registered hunk of `Runner._run_stage` (`tests/fixtures/run_stage_5_0_2.diff`), the registered fork of the classic spot node (`tests/fixtures/spot_banded_5_0_2.diff`), the registered lean-SAM exception (`tests/fixtures/sam_lean_5_0_2.*`), the two node-pack manifests, and the code pin (`tests/fixtures/beta-normalised-hashes.json`), which is regenerated when a build wave is merged. In `SOURCE-MAP.json`, the layers `5.0.1` and `5.0.2` mark the files changed after 5.0.0-beta.1 (`tests/test_source_map.py` checks that every file is listed and that a file without a later layer is still as 5.0.0-beta.1 released it). A file new after 5.0.0-beta.1 has no recorded hashes until the release that ships it records them.

The engine's base (written for 5.0.2):
- `engine/planner.py` keeps 5.0.1's planner verbatim as `plan_501` and adds a router. The Large-image engine is asked only for plans 5.0.1 refuses, and it admits none until the GPU proof sets `engine/banded_plan.BANDED_PROVEN_MP`.
- `engine/banded_plan.py` is the Large-image planner and its memory model.
- `engine/graph_banded.py` builds the Large-image prompts with the classic stage's input values.
- `engine/planes.py`, `engine/bands.py`, `engine/dat_bands.py` and `engine/lanczos_bands.py` are the plane store, the band arithmetic, the classic margin tiling in row bands (the same sums in the same order) and Pillow's two Lanczos passes in bands.
- `service/plane_io.py` holds the streamed writers, the viewer proxy and the regions. `service/banded_runner.py` runs the Large-image stages, and `service/build_channel.py` is the developer-build switch.
- `node_pack/claude_banded/` is the second node pack, with its own GPL-3.0 licence copy and its own manifest `node_pack/MANIFEST-banded.json`. The classic pack is untouched apart from the lean-SAM exception.
- Smaller changes are in `service/api.py`, `config.py`, `fake_comfy.py`, `media.py`, `runner.py` (the registered hunk) and `util.py`.

The SAM step that fits the card, and honest times:
- `node_pack/claude_creative/sam_lean.py` is a node with SAM3_Detect's inputs and outputs. It thresholds the masks first and upsamples only the kept ones, and it calls the runtime ComfyUI's own SAM3_Detect helpers.
- Its registration in `node_pack/claude_creative/__init__.py` and `node_pack/MANIFEST.json` is the registered exception.
- `engine/planner.py` and `engine/graph_v5t.py` carry the SAM ceiling and the fitted stage times. `service/engine_options.py`, `mask_graph.py`, `workers.py`, `comfy.py` and `runner.py` follow them.

Build wave 1:
- `node_pack/claude_banded/spot_banded.py` is a fork of `node_pack/claude_creative/spot.py` (unchanged) by the registered patch `tests/fixtures/spot_banded_5_0_2.diff`. The ControlNet hint reaches each window from its plane, a coverage mark is checked, the two-card split is static, the Brownian cache is an input, and torch is imported on first use.
- `node_pack/claude_banded/vae_planes.py`: CUEncodePlane runs the lines of ComfyUI's `VAE.encode_tiled_` (three tilings, ComfyUI's own `comfy.utils.tiled_scale`) on canvas windows read from the plane. CUDecodePlane follows `VAE.decode_tiled_` and `comfy.utils.tiled_scale_multidim` (tile positions, feather masks, add order) in row buffers, then ImageScale area and the finish's 8-bit step (ComfyUI at the runtime's commit, GPL-3.0).
- `node_pack/claude_banded/cn_plane.py` holds PlaneHint and CUControlNetApplyPlane, which calls ComfyUI's own `ControlNetApplyAdvanced.apply_controlnet` with the hint plane.
- `node_pack/claude_banded/canny_plane.py` runs ClaudeCannyTiled's tiles (kornia canny, hysteresis off) and its `scipy.ndimage.label` hysteresis, on planes.
- `node_pack/claude_banded/sam_plane.py` runs the classic pack's lean SAM node on a float32 view of the input plane.
- `node_pack/claude_banded/noise_banded.py` is the Brownian cache cap: a subclass of ComfyUI's BrownianTreeNoiseSampler in the classic noise prefetch's class-factory pattern (`claude_creative/noise.py`).
- `engine/bxf/` is new: the banded exact finish's numeric machinery.
  - Exact streamed selection on numpy's own percentile and median arithmetic (`selection.py`).
  - scipy's uniform_filter as whole-line strip and band passes (`uniform.py`).
  - The finish's 288-aligned pooled grids and whole-call zooms into mapped outputs (`pooling.py`).
  - Label, bincount, find_objects and keep tables on mapped planes (`components.py`).
  - The band executor (`local.py`), a CPU process pool for numpy and scipy band ops (`pool.py`, `_child.py`, `ops.py`) and mapped scratch planes (`work.py`).
  - The G1 classification table and its reader (`g1.py`, `g1_table.py`, written by `tools/gate_g1.py`). Each banded op carries the band geometry it was measured exact on, and the reader bands a pass only inside it.
  - It calls numpy and scipy only, and torch inside functions.
- `engine/bands.py` gains the registered finish band budgets (2, 3 and 6 GiB), their check, and the defaults (2 GiB, 1 process).
- `node_pack/claude_banded/bxf/` is CUFinishBanded with its fallback ladder, plus `finish.py`, the banded passes of 5.0.1's finish over planes.
  - Tier 0 is the banded exact finish where the G1 table applies. Tier 3 is 5.0.1's own v4_finish and shadow toe run whole, up to the size limit; its body is the earlier build's node, pinned in `tests/fixtures/finish_banded_5_0_2_base.txt`.
  - The passes call the classic `node_pack/claude_creative/v4finish.py` functions (read, never patched) and mirror v4_finish's own expressions line by line.
- `engine/vram_model.py` (the classic graphics-memory pre-check, the Large-image memory classes and the card class table) and `service/card_factor.py` (per-card time factors for deadlines, stall limits and the times said) are new. The card class table holds the makers' published figures (SM counts and memory bandwidths) as estimates, doubled for safety and replaced by the card's own measurement after its first image. The reference time per window (0.147 s) is the median of 339 sampling passes of the product stack on one RTX 5090.
- `node_pack/claude_banded/dev_vram.py` is the developer-only graphics-memory cap of the small-card emulation. A release build ignores it.
- Admission changes are in:
  - `service/runner.py`, outside the registered hunk, plus the hunk's deadline line, which now carries the card factor (5.0.1's value on cards over 24 GiB);
  - `service/banded_runner.py`: the split finish's memory check and record, the checkpoint and resume, and the live preview from a banded proxy;
  - `service/engine_options.py`: a Large-image plan's minutes are said as wall minutes;
  - `service/comfy.py`: progress weights and a prompt counter;
  - `service/workers.py`: spot's timing record on cards of 24 GiB or less;
  - `service/windows_job.py`: the Job's current committed memory and its process list;
  - `service/fake_comfy.py`: test-only fakes.
- Viewer changes:
  - `service/plane_views.py` is new: a Large-image result's viewer copies made from its plane, sized copies kept on disk, RGBA PNG proxies, and the guard that never decodes a Large-image result whole.
  - `service/media.py`, `service/api.py` and `service/naming.py` name the engine and serve the copies.
  - `host/installation.py` adds Setup's 48 GB memory floor behind a switch that is off.
  - `tools/build_release.py` checks the release channel and refuses draft release text.
  - The engine tag and line in the app are in `ui/qml/creative` (`format.js`, `CuTrayStatus.qml`, `CuQueueRow.qml`, `CuQueueModel.qml`, `CreativeUpscalerTab.qml`, `CuViewer.qml`).
- Developer tools that are never shipped (`tools/build_release.py` packages none of them):
  - `tools/gate_g1.py`, `gate_g1x.py`, `gate_g2.py` and `gate_g7.py`, the gates of the banded finish and of the Brownian cache cap;
  - `tools/proof/` and `tests/proof/`, the proof tooling: the phase-diff harness and its instrumentation, registration and sampling, seam and quality metrics, and the blind comparison kit. The instrumentation's custom-nodes folder `tools/proof/comfy_nodes/cu_proof` is loaded only by the harness's own worker.
