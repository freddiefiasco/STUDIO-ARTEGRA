# Release validation

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
