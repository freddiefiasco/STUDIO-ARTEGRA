"""Proof tooling for the engine's Prove phase (engine design ENGINE-DESIGN.md section 9.1, item B9). DEVELOPER ONLY.

Nothing here ships: tools/build_release.py copies host, ui, service, engine, node_pack and runtime, and of tools/ only
tools/verify_models.py (tests/proof/test_not_shipped.py checks this). A developer build (tools/make_dev_build.py) carries it.

Modules (each names the interpreter it needs; numpy and Pillow alone unless it says otherwise; one line per module, as
tests/proof/test_streamed_up.ModuleList reads it):
- colour: sRGB, linear light, CIE L*, Lab, CIEDE2000, Gaussian blur and block means (numpy).
- phases: the phase table of design 7.2, each role's compared form, and the phase counter (first differing phase).
- harness: both executors' stage graphs for the same (f, s), the 7.1 pairs and their machine classes, the dump spec, the
  worker command, the prompt runner.
- harness_io: the instrumentation's dump folders read back into compared entries, timelines and thread records.
- phase_run: one reference pair end to end (both executors, or one executor stored and compared later), the worker engine.
- comfy_nodes/cu_proof: the instrumentation (a ComfyUI custom-node folder; torch, inside a worker only).
- classic: 5.0.1's classic finish and protect gate run whole on a stage's planes (the oracle; torch and scipy, the worker
  runtime), and FINISH_KEYS checked against the classic pack.
- finish_rerun: the Large-image finish re-run on a stage's kept planes with the stage's own values and a second band
  height, process count or tier (the build's own pack, outside ComfyUI; torch and scipy, the worker runtime).
- registration: marks, the build record, sealing by sha256 before a result, the moved-mark check.
- packets: the registration record of one proof-matrix row (build, plan dict and variant constants, graph per pass, peaks,
  time band, deadline, window), whatever the row's kind.
- sampler: the 2 s sampler of Windows counters, Job objects and their peak commit (Windows; ctypes).
- records: the wsum lines of the worker log, the L3r split record per stage, phase times.
- r7: the commit-against-VRAM probe (torch.cuda allocations against PrivateUsage and Job commit; the work drive's space).
- seams: M4, the seam detector, at the plan's band, strip and tile positions.
- qmetrics: Q4 (block colour drift), Q5 (invented content; the pass-2 upscale streamed into a plane), Q11 (halo against the
  three-pass chain).
- tiers: design 7.3's tier rule.
- noise_floor: the noise-floor runner (the finish at three thread counts and the 333-row pow variant; torch, the worker
  runtime).
- halo_grid: the region-grid wrapper of the halo tools' halo_metric.measure (read by path; their interpreter).
- metrics: M1-M6 per case, the measured-alike check, noise floors and the pass rule.
- pairs: the blind pair maker, the X/Y order rule, the sealed key.
- tally: the blind verdict and BLIND-TALLY.json formats and their validators.
- cases: the blind comparison's case runner (job bodies for the release path and the developer force switch).
"""
