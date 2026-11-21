"""Proof tooling for the engine's Prove phase (engine design ENGINE-DESIGN.md section 9.1, item B9). DEVELOPER ONLY.

Nothing here ships: tools/build_release.py copies host, ui, service, engine, node_pack and runtime, and of tools/ only
tools/verify_models.py (tests/proof/test_not_shipped.py checks this). A developer build (tools/make_dev_build.py) carries it.

Modules (each names the interpreter it needs; numpy and Pillow alone unless it says otherwise):
- canon:        canonical JSON and file hashes (the identity record's own hashing).
- colour:       sRGB, linear light, CIE L*, Lab, CIEDE2000, Gaussian blur and block means (numpy).
- phases:       the phase table of design 7.2, each role's compared form, and the phase counter (first differing phase).
- harness:      both executors' stage graphs for the same (f, s), the 7.1 pairs, the dump spec, the worker command.
- comfy_nodes/cu_proof: the instrumentation (a ComfyUI custom-node folder; torch, inside a worker only).
- oracle_finish: 5.0.1's classic finish run whole on a stage's planes (torch and scipy, the worker runtime).
- registration: marks, sealing by sha256 before a result, the moved-mark check.
- sampler:      the 2 s sampler of Windows counters, Job objects and their peak commit (Windows; ctypes).
- records:      the wsum line of the worker log, the L3r split record, phase times.
- seams:        M4, the seam detector, at the plan's band, strip and tile positions.
- qmetrics:     Q4 (block colour drift), Q5 (invented content), Q11 (halo against the three-pass chain).
- tiers:        design 7.3's tier rule; noise_floor: the noise-floor runner (the finish at three thread counts and the
                333-row pow variant; torch, the worker runtime).
- halo_grid:    the region-grid wrapper of the halo tools' halo_metric.measure (read by path; their interpreter).
- metrics:      M1-M6 per case, noise floors and the pass rule.
- pairs:        the blind pair maker, the X/Y order rule, the sealed key.
- tally:        the blind verdict and BLIND-TALLY.json formats and their validators.
- cases:        the blind comparison's case runner (job bodies for the release path and the developer force switch).
"""
