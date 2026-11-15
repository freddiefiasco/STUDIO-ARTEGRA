# Release validation

## Conservative memory update (alpha 3, 15 November 2026)

- Updated source: **403 tests plus 33 subtests passed** in 13.46 seconds on the remote Windows node. Twelve extended checks were deselected; the earlier baseline covered the extended fault/recovery suite.
- Auto selects the conservative profile for finite detected capacities up to 24 GiB. Explicit Original settings remains unchanged. Graph tests verify that memory saving changes only window batching, while launch checks verify the low-VRAM flag and 1 GiB reserve. Persistence, busy rejection and idle-worker restarts are covered.
- Standard on the 384-pixel crop passed visual review with whole-GPU peak 15,464 MiB, compared with 19,755 MiB in the earlier reference check. End-to-end elapsed time was 147.19 seconds. This is an observation, not a controlled performance benchmark.
- Standard at 768 by 768 input and 1536 by 1536 output passed a 14 GiB native PyTorch allocator budget: 254.29 seconds, peak allocated 10.52 GiB / reserved 12.27 GiB, no allocation retries or OOM errors. Whole-GPU peak was 13,584 MiB. It passed visual review.
- Fast at the same dimensions passed an 8 GiB allocator budget: 288.68 seconds, peak allocated 5.18 GiB / reserved 7.895 GiB, one internal allocator cache retry and no OOM error. Whole-GPU peak was 8,490 MiB. It passed visual review; an allocator retry is not an image resubmission.
- The four conservative outputs have mean absolute RGB-channel differences below 0.44 on the 0–255 scale against their matching reference outputs. They are not pixel-identical. No rainbow contours, embossed-fabric artifacts, blank tiles or obvious seams were observed.
- Standard also passed the 8 GiB limit: 518.46 seconds, peak allocated 5.16 GiB / reserved 7.895 GiB, one internal cache retry and no OOM. Whole-GPU peak was 8,488 MiB. Its PNG exactly matches the visually approved 14 GiB Standard output. GPU testing ended at seven submissions total.
- Alpha 3 build/startup and memory-control selection, persistence, reload and error display passed at 1024 by 600 logical pixels and 125%/150% scaling.
- Alpha 2 to alpha 3 Unicode installation, upgrade, startup and uninstall passed. The executable hash matched; user files and all 62,952 existing runtime files were preserved. SetupRuntime help and process/registry cleanup passed. Final documentation was refreshed afterwards with the executable unchanged.

The image checks used an isolated production-service source copy; final-source tests establish the same Balanced graph and flags. Numerical evidence is in [memory-20261115.json](qa/memory-20261115.json).

These checks used the original tile sizes, weights and numerical options. The QA-only allocator limit and adjusted engine headroom were applied before model allocations and read back exactly. No separate pressure helper was used. Only allocator memory was constrained; CUDA/driver allocations and other physical GPU architectures remain outside that simulation. All completed jobs preserved input and shut down their owned processes.

The existing 64 GB RAM recommendation remains: selected worker commitment reached 30.46 GiB although resident memory was lower. A larger pagefile does not override the conservative application budget on a 32 GB system. No system settings or model files were changed.

## Windows compatibility update (alpha 2, 15 November 2026)

Verification ran on a separate Windows 11 Pro build 26300 machine with an RTX
5090, driver 621.24 and 64 GB system RAM. No image processing ran on the owner's
workstation. Exactly three actual image jobs were submitted.

- Final safe source: **391 tests plus 33 subtests passed** in 10.52 seconds.
  Twelve extended checks were deselected for this final run; the earlier baseline
  included the extended fault/recovery checks and passed 332 tests plus 33 subtests.
- Packaged Standard and Fast both completed and passed visual review. A 384 by
  384 representative crop produced 768 by 768 output. End-to-end times were
  163.85 seconds for Standard and 32.09 seconds for Fast; Fast reused the warm
  worker, so these are observations rather than a controlled speed comparison.
- The third, experimental Minimum-memory job completed in 243.24 seconds but
  **failed visual review**, with coloured contours and distorted fabric detail.
  It and all other unqualified memory profiles were removed from the release.
  Auto retains the original reference tiles, model files and numerical settings.
- The GPU pressure exercise was not a hard 10 GB limit under Windows WDDM and
  does not qualify an RTX 3080. Quantization and the private conservative offload
  candidate remain unverified and are not included.
- Final frozen startup connected to the engine and exposed Fast mode. Settings,
  model consent, verification, diagnostic export and scrolling passed the
  packaged-interface probe at 1024 by 600 logical pixels and 125%/150% scaling.
- Installation, alpha 1 to alpha 2 upgrade, startup and uninstall passed in a
  Unicode folder. The installed executable matched the built executable hash;
  separate user-state, model and output sentinels were preserved. The existing
  62,952-file runtime was unchanged, the uninstall entry was removed, and all
  owned processes closed.
- Source privacy checks and the GitHub Windows checks passed. Installer and
  portable assets include SHA-256 checksums and an SBOM.

The actual image jobs used the candidate package before the failed profiles were
removed. Final-source graph/launch checks establish that the released reference
path is unchanged; the final safe package passed startup and upgrade checks.
No fourth image was submitted. Windows 10 and other GPU models were not
physically tested. Current ordinary-render admission requires more than the
default budget on a 32 GB system; 64 GB RAM is recommended. See
[COMPATIBILITY.md](COMPATIBILITY.md) and the numerical
[QA record](qa/compatibility-20261115.json) for the scope and limitations.

## Original reference validation (alpha 1)

- 331 tests plus 33 subtests passed on a separate Windows node; no failures or skips. Coverage includes model download/resume/cancellation, integrity, output preservation, crash recovery, authentication, queue behaviour and diagnostics.
- 203 targeted checks passed after removal of three unused external-node registrations. Image-processing functions and required graph nodes were unchanged.
- Selected Standard and Fast reference/pilot renders at 768×768 input and 1536×1536 output matched at zero differing pixels, cold and warm. Timing differences stayed within 5%.
- Original versus independently installed runtime comparisons also matched at zero differing pixels for selected Standard/Fast cold and warm renders.
- Completed GPU comparisons released owned processes and returned GPU memory to baseline within 15 seconds.
- Fresh runtime installation verified all 86 pinned dependency versions, source hashes, licence files and package consistency. The actual image-engine service started successfully.
- Frozen executable startup, model-consent gating, verification, diagnostic export, and source/binary privacy checks passed.

## Limits

GPU checks used RTX 5090 32 GB hardware and a representative render crop. They do not establish universal image/GPU compatibility. A 50-image simulated-engine batch was tested; no 50-image real-GPU or overnight endurance claim is made. The extended GPU batch was stopped at the owner's request to keep this release a lean refinement.

Numerical evidence is in `qa/source-parity.json` and `qa/runtime-parity.json`. Release assets carry SHA-256 checksums. No private test images, machine paths, credentials or original source history are distributed.
