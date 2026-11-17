# Release validation

## Artegra Enhancer (Beta) 5.0.0-beta.1: build checks (17 November 2026)

These are the build role's checks on a Windows 11 workstation, with the fake engine only: no GPU image was made for
this section. GPU parity, the installer build and the install, upgrade and uninstall tests follow in later sections.

- **Merge.** The final v5 (frozen copy, tree `3ccc1ddcfbda32a0a1dcbbe2b0eb389d14a86777f5e9ed643858f862b2e07127`, 136
  files) merged onto the standalone. A file-by-file check of the code normal form (Python without comments and
  docstrings; QML/JS without comments) against the final v5, over 142 files: 115 equal it apart from the standalone
  layer, 21 carry only the reviewed Beta changes, 6 are files the final v5 does not have (4 of the standalone's, 2
  new in the Beta), and engine/ and node_pack/ carry no Beta change.
  `tests/test_final_v5_layer.py` pins this.
- **Prompt identity.** For 38 cases (every Look at 2×, 4×, 6× and 8×, Custom, a protect set, PNG 16-bit, TIFF 16-bit,
  JPEG, a seed, Bolt Light and Default, both preview settings, "Match earlier results", and one image shared by two
  cards in Redux and in Bolt), every stage prompt the Beta's service sends equals the final v5's, after normalising
  paths and ids. The two Save GPU memory cases have no final v5 counterpart; they differ from the original settings
  only by `batch_windows` 1 instead of 2 and are pinned to the Beta's reviewed run.
  `tests/test_service_prompt_identity.py`.
- **Two-card Bolt.** Not run on two GPUs (the test machines have one card each; the final v5's two-card Bolt proof ran
  on two RTX 5090 cards). The shared Bolt prompt equals the final v5's (above), dispatched to both cards with the 0.308
  finish factor on two fake cards named like the proven hardware; on any other pair, three cards, a laptop card, a
  24 GB card or Save GPU memory, Bolt runs one image per card with the 0.37 factor. `tests/service/test_bolt_two_cards.py`.
- **Excluded features.** No file name or content in the tracked tree carries the excluded rendering view or its patch
  (hex-encoded words in `tests/test_excluded_features.py`); the public-content scan now refuses both words.
- **Unit and service tests: 842 passed, 7 skipped, 39 subtests passed** (12 extended tests deselected; 10 min 0 s,
  below-normal priority; after the hardening round and its fix below). The 7 skips are the final v5 cases for features the
  standalone does not have, each with its reason (internal two-card proof switch, internal history, finishing in
  the background) and the research notes the recipe test reads when present.
- **Public-content scan:** files passed; history: passed (every blob and commit message reachable from the branches).
  Since fix round 2 the scan also refuses another product's name in any case; since the hardening round, with
  nothing or up to three characters that are not letters or digits (or URL escapes) between its words, in file
  contents and in file names.
- **Secret scans (gitleaks, trufflehog): not run.** The scanners are not installed on this workstation and the
  build role was not cleared to download them; the CI workflow runs them on push.
- **compileall** (host, service, engine, runtime) passed. **Host smoke** (`python -m host.app --smoke`) passed:
  tab loaded, engine connected, Bolt offered, no GPU used.
- **Screens.** Offscreen screenshots at 1280 × 800 and 1920 × 1080, each at 100 % and 125 % (physical pixels): empty,
  an image waiting in Redux, in Bolt, the two mode motions, running, a Bolt result, Settings with each update state
  and the uninstall entry, the uninstall confirmation and About. The marks land on whole device pixels at both
  scales. Retaken after the fix round, with one more: a real check that meets an HTTP protocol error ends on the
  plain failure, with the button ready again.
- **Fix round 1.** Two defects found by the independent check are fixed, each with tests that fail on the earlier
  code. *Uninstall clean-up:* "Also remove settings and logs" removed everything in a state folder except the
  current output folder, so an output folder used earlier inside the state folder (a job's, or the one kept in the
  service's settings) was deleted with its images. It now removes only the entries the app itself creates, by
  exact name, and keeps and logs anything else; every output folder named in the app's records is kept, and an app
  folder holding a file named like a result is kept whole. Each output folder is looked up once, and one on another
  drive is never resolved, so a long history or an offline share cannot stall the uninstaller (27 tests,
  `tests/test_uninstall_cleanup.py`, including a run through `--uninstall-cleanup`; the tests no longer touch the
  machine's own settings key). *Check for updates:*
  an HTTP protocol error (bad status line, cut-off answer, overlong header) escaped the check and left the button on
  "Checking for updates…". Every error now ends on the plain failure, and the button's bridge always reports back
  (`tests/test_updates.py`, `tests/test_updates_qt.py`).
- **Fix round 2.** *Uninstall clean-up:* "Also remove downloaded enhancement files" removed the image engine folder
  whole, so images saved inside it (its ComfyUI output folder, or any folder in the data folder chosen at setup)
  were deleted. The output folders are now read once, before either option runs, and both options keep them. In
  the engine folder only setup's own entries are removed, by exact name; in its ComfyUI folder only files that
  match the pinned source list byte for byte. Anything else stays and is logged, and the size the uninstall page
  shows is exactly what the option frees. Folders on the data folder's drive are looked up only when that option
  runs (28 more tests in `tests/test_uninstall_cleanup.py`, through `--uninstall-cleanup`; 26 of them and one
  changed test fail on the earlier code). *Public-content scan:* a ported test's name carried another product's
  name in snake case, which the scan did not catch. The test was renamed in every unpushed commit that held it, so
  no commit carries the name, and the scan now refuses it with any short joiner, in contents and in file names
  (`tests/test_public_scan.py`).
- **Hardening round (from the v6 UI/UX audit).** Small, local fixes to defects a colleague could hit, each with a
  test that drives the real window offscreen and fails on the code before it (`tests/test_host_states.py`, through
  `tests/qa/drive_host.py`; `tests/test_contrast_tokens.py`). *Settings and About* (and the setup page) hide the
  workspace and take the keyboard while they are up: behind them, Ctrl+Enter, Delete, B, M, 0, 1, F6, ? and Ctrl+. change nothing and Tab stays out, where before
  Ctrl+Enter started the waiting images and M and 0 changed the picture; Esc closes the page. The first version only
  hid the workspace, and its test opened the pages from script, so it missed the usual case, which the hardening check
  found: a mouse click on Mode, Scale, Look or a row of the image list gives that control the keyboard, a click on a
  header button does not move it, and Qt keeps it on a hidden item. Right, End, Down and Delete then changed the mode,
  scale and Look of every waiting image, moved the selection or asked to remove an image, out of sight. Now the page
  takes the keyboard as it appears, focus that lands in the hidden workspace later goes to the page, and a question
  the workspace had open closes when the engine stops. Two tests click with the mouse, press the keys (also with no
  pause after the click, and after focus is moved into the hidden workspace by code) and kill the engine for the setup
  page; both fail on the earlier code (`test_a_clicked_control_takes_no_keys_behind_settings_or_about`,
  `test_a_clicked_control_takes_no_keys_behind_the_engine_stopped_page`). The workspace is hidden, not disabled: a
  disabled white Upscale block is not drawn and faded back in over about 150 ms each time a page closed, which a
  test now rules out. *Start-up* shows
  "Opening your workspace" with the engine's status, with no setup steps and no progress bar (it showed a bar fixed
  at 28 % that pulsed forever). *An engine that stops* shows "The image engine is not running" with Try again, not
  the install step; after Try again the unfinished image carried on and finished. *Out of memory* offers Try again
  with Save GPU memory (asked first) when the card does not use it and no other image is working. *Slider rulers
  and progress tracks* reach 3.33:1 and 3.16:1 (were 2.0:1). *The tab's preferences* stay in the state folder
  (they went to the registry, shared by every copy) and move there once on upgrade. *The close prompt* goes away
  when the batch ends. *The Shortcuts sheet* no longer lists Tab for the panels. *Windows' Animation effects* off
  now gives the tab's reduced motion. *Check for updates* ends on time against an answer that drips in slowly.
  The full list and what was left for v6 is in KNOWN-ISSUES.md.
- **Screens and privacy.** The release screens are retaken with a made-up, neutral demo output folder (Renders\Enhanced
  on drive D) in place of the temporary state folder, which holds the Windows user name. The earlier sets were withdrawn from the
  release folder. Every published image is checked with Windows OCR for user names and private paths (37 of the 64
  withdrawn images failed that check; every image of the new set passed). Retaken after the hardening fix, with Settings
  opened by a mouse click after a click on Mode: the keys pressed behind it changed nothing, and all 88 images passed
  the same check.
- **Launchers** compile with the icon (C# compiler of the .NET Framework 4.8). **Installer: not built** (Inno Setup is
  not installed on this workstation). Its uninstall code, the options form and the single confirmation are
  therefore unverified, as are the install, upgrade-from-alpha-4, repair and uninstall tests.

## Guided installer update (alpha 4, 15 November 2026)

Qualification used a separate Windows 11 Pro build 26300 machine with an RTX
5090, driver 621.24 and 64 GB RAM. Image processing ran on that machine.
The numerical record is [installer-20261115.json](qa/installer-20261115.json).

- **467 tests plus 33 subtests passed** in 62.37 seconds, including the extended
  CPU fault suite. After an internal variable rename for the public-content
  policy, all 35 affected setup/dependency checks passed again.
- A genuinely empty application, settings and AI-data installation completed
  automatically in 440.01 seconds. Setup downloaded and hash-verified all six
  required models, prepared the pinned engine, passed its graphics check and
  successfully launched the installed app. No terminal, extraction-folder or
  manual runtime step was required.
- After the final Microsoft DLL compatibility fix, reinstalling the exact final
  package took 34.59 seconds and reused the verified AI files. All 2,229 installed
  code files matched the build. The following final image check used that package;
  the earlier empty-directory download and lifecycle checks preceded this fix.
- The native wizard's welcome, terms, location, ready, progress, completion and
  Finish actions passed. Native pixel capture was unavailable in the remote SSH
  session, so this establishes control flow and progress, not a visual inspection
  of those wizard pixels. The in-app setup and recovery screens were inspected.
- An installed Fast Default job enhanced a 384 by 384 crop to 768 by 768, saved
  its output and metadata to the default Pictures location, and preserved its
  input. The final output exactly matches the visually reviewed output. Automatic
  startup took 3.99 seconds; enhancement took 55.83 seconds with whole-GPU peak
  19,904 MiB. These observations are not controlled speed benchmarks.
- Normal window closing passed with exit code zero and no remaining owned
  processes. An earlier test sent Close before the UI received completion and
  correctly opened the active-work confirmation; the settled-window check
  required no additional image processing.
- Alpha 3 upgrade, repeated installation and uninstall passed. Settings,
  downloaded AI files and saved-image sentinels survived. Existing unrelated
  runtime files and persistent settings were unchanged; 76 newly generated
  Qt cache files were excluded from the persistent-settings comparison.
- Regression coverage includes interrupted downloads, corrupt or foreign files,
  cancellation, disconnected drives, Unicode folders, service failure/retry,
  UTF-8 worker startup and automatic storage/output defaults. Full-suite counts
  and the extended CPU fault checks are recorded in the numerical report.

The release uses official embedded CPython, ordinary unpacked application files
and thin Windows launchers. Earlier unpublished PyInstaller candidates triggered
Windows protection during worker startup and were rejected. Qualification of the
replacement keeps Windows protection enabled; current engine/signature versions
and scan results are recorded in the numerical report. This is not vendor
clearance or a guarantee about other antivirus products.

The engine uses the Microsoft runtime DLLs already included with the desktop
package, including on machines without developer tools. A fresh engine process
confirmed that it loaded the bundled MSVCP140 DLL before importing PyTorch.
No system DLLs, drivers, pagefile settings or antivirus exclusions were changed.

This is an unsigned alpha. Windows 10 and other physical GPU models have not
been qualified by these checks. The 64 GB RAM recommendation and image-size
admission limits remain. No overnight real-GPU endurance claim is made.

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
