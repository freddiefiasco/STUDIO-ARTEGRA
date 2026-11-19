# Release validation

## Artegra Enhancer (Beta) 5.0.1-beta.1: memory hotfix 5.0.1 (19 November 2026)

On a 64 GB PC with one RTX 5090, 5.0.0 Beta 1 refused Bolt and Redux 2× of a 3500 × 2188 render, Redux 2× of a
2800 × 3500 render and Redux 4× of a 1280 × 1600 image, which 5.0.1 makes. 5.0.0 Beta 1's memory estimate was well
above the measured peaks, its default limit was the computer's memory less 10 %, and it never tried a lighter
setting for memory. 5.0.1 changes the planner, the default limit, the check before an image starts and the messages
(see the [changelog](../CHANGELOG.md)). This section records what was checked before the release files were built;
their build and install check are recorded separately.

**Memory measurements.** On 19 November 2026 the published 5.0.0 Beta 1 (its own service and engine, one card, the
original memory settings, Look Default, seed 20261102) made eight images with its memory limit set to 200 GB, so that
none was refused, each in a fresh service. The peak is the most memory committed in a Windows Job around the service
and the engine together, and 5.0.1's estimate is fitted to these peaks. The app's own limit counts the engine's
processes only, about 1 GB less, so the peaks are slightly above what the limit counts. GB here are the app's GB,
2^30 bytes, as Windows counts memory. Supersample 2 is the full setting.

| Image | Computer | Passes: supersample, render MP → output MP | 5.0.0 estimate | Measured peak | 5.0.1 estimate |
|---|---|---|---:|---:|---:|
| Bolt 2× of a 3500 × 2188 render | a 64 GB PC with one RTX 5090 | 2, 122.5 → 30.6 | 61.5 | 51.1 | 52.7 |
| Redux 2× of a 3500 × 2188 render | a 64 GB PC with one RTX 5090 | 2, 122.5 → 30.6 | 61.5 | 46.0 | 52.7 |
| Redux 4× of a 1280 × 1600 image | a 64 GB PC with one RTX 5090 | 2, 32.8 → 8.2; 2, 131.1 → 32.8 | 63.8 | 50.0 | 54.8 |
| Bolt 2× of a 2800 × 3500 render (1) | a 64 GB PC with one RTX 5090 | 2, 156.8 → 39.2 | 70.4 | 59.2 | 61.0 |
| Redux 2× of a 2800 × 3500 render (1) | a 64 GB PC with one RTX 5090 | 2, 156.8 → 39.2 | 70.4 | 52.0 | 61.0 |
| Redux 6× of a 1280 × 1600 image | a 64 GB PC with one RTX 5090 | 2, 32.8 → 8.2; 2, 131.1 → 32.8; 1, 73.7 → 73.7 | 72.8 | 63.4 | 65.3 |
| Redux 8× of a 1280 × 1600 image (2) | a 64 GB PC with one RTX 5090 | 2, 32.8 → 8.2; 2, 131.1 → 32.8; 1, 131.1 → 131.1 | 106.0 | 87.2 | 89.8 |
| Redux 4× of a 3500 × 2188 render | a 128 GB workstation (one of its two RTX 5090 cards) | 2, 122.5 → 30.6; 1, 122.5 → 122.5 | 101.1 | 79.8 | 85.5 |

1. Measured with the render limit raised from 150 to 160 MP in a test copy, so that this image planned at
   supersample 2. 5.0.1 keeps the 150 MP limit: Redux makes this image at supersample 1.5 (5.0.0 Beta 1 planned
   the same pass, but refused it on a 64 GB PC for memory), and Bolt refuses it as over its size of about 9 MP.
2. Measured with the start check relaxed in a test copy (see below). It used 12.9 GB of the pagefile, free memory
   reached 0 at its peak, and it finished with the planned size.

- 5.0.1's estimate is above every measured peak, by 1.6 to 9.0 GB. Bolt peaked 5 to 7 GB above Redux for the same
  passes, and the estimate follows Bolt.
- Every result had the planned size and passed a sanity check of its pixels.
- The peak was always in the largest pass, never while saving. The engine's resident memory peaked at 55 to 77 % of
  the memory it committed, so on a 64 GB PC the binding limit is what Windows can commit (memory plus pagefile).
- The same pass committed the same memory, within 0.7 GB, on different PCs and in different runs.

**Why 5.0.0 Beta 1 held two of them.** On the 64 GB PC, 5.0.0 Beta 1 never started Redux 4× of the 3500 × 2188 render
or Redux 8× of the 1280 × 1600 image, even with its limit at 200 GB. Its start check wanted Windows' free commit to
exceed the estimate plus 2 GB, so both showed "Waiting for memory" until they were cancelled after 600 s. 5.0.1's
start check also counts the room a system-managed pagefile has to grow. The 4× was then measured on the workstation,
and the 8× on the same PC with the check relaxed (note 2).

**What 5.0.1 plans** at the default limits of a 64 GB PC with one RTX 5090 (59.0 GB of the 61.56 GB Windows reports)
and of a 128 GB workstation (122.2 GB of 127.37 GB). These are the release targets; `tests/test_planner_ram.py` holds
all but the last row, which is the planner's output limit.

| Image | 64 GB PC | 128 GB workstation |
|---|---|---|
| Redux and Bolt 2× of 3500 × 2188, either way round | runs at supersample 2 (52.7 GB) | runs at supersample 2 |
| Redux 4× of 1280 × 1600 | runs at supersample 2 in both passes (54.8 GB) | runs |
| Redux 2× of 2800 × 3500 | runs at supersample 1.5 (50.6 GB); 5.0.0 Beta 1 planned the same pass and refused it ("about 60 GB", over its 55.4 GB limit) | runs at supersample 1.5, as in 5.0.0 Beta 1 |
| Bolt 2× of 2800 × 3500 | refused as over Bolt's size, as in 5.0.0 Beta 1 | the same |
| Redux 6× and 8× of 1280 × 1600 | refused: "about 65 GB" and "about 90 GB" | runs |
| Redux 4× of 3500 × 2188 | refused: "about 86 GB" | runs |
| 6× and 8× of 3500 × 2188, 4× of 2800 × 3500 | refused: over the 150 MP output limit | the same |

**Plans 5.0.0 Beta 1 made are kept.** `tests/test_planner_ram.py` compares 5.0.1's planner with a frozen copy of
5.0.0 Beta 1's (`tests/fixtures/beta_planner_5_0_0b1.py`) over 112 image sizes at 2×, 4×, 6× and 8×. With no memory
limit every plan equals the Beta's. Every plan the Beta could run at its default limit on a 48, 64 or 128 GB computer
plans the same passes at 5.0.1's default, so it makes the same graph and pixels, and is never lightened or refused.
5.0.1's estimate is never above the Beta's. A plan stored by 5.0.0 Beta 1 still matches the same plan made now, so a
stopped image queued again keeps its finished passes. No image was made with 5.0.1 for this section: for every plan
5.0.0 Beta 1 could run, 5.0.1 sends the engine the same passes, and the measured images ran the Beta's engine.

**Checks of the code of the commit that adds this section** (below-normal priority).

- With the local word list: 892 tests passed, 8 skipped, 39 subtests passed (12 extended tests deselected; 12 min 22 s).
- GitHub's hosted runner has about 16 GB, and 98 tests failed there on 5.0.0 Beta 1 (see "published on GitHub"
  below). The tests now pin the computer's memory figure for themselves. In a fresh copy without the local word
  list, as in CI, with this computer's memory reading replaced by 15.9 GB: 888 passed, 11 skipped (the 8 above and
  the 3 word-list checks), 39 subtests passed, none failed (10 min 37 s). The test that pins `service/settings.py`
  to its reviewed hash was left out of that run, because the simulation changes that file.
- The public-content scan passed on the files and on the history (every blob and commit message reachable from any
  branch or tag), with the local word list and without it. `tools/check_secrets.py --history` (gitleaks 8.30.1,
  TruffleHog 3.99.9) passed all four of its scans. compileall and the host smoke check passed.
- CI now runs the privacy and secret scans before the tests, and the tests even when a scan fails, so a failing test
  no longer hides the scans' result. This has not run on GitHub yet.

**Review.** Before the commit, the change had an independent review (correctness, memory, Bolt and the interface, the
tests and CI, and completeness) and a second round that checked the fixes it led to. After that round the estimate's
constants were fitted again to all the measurements; the tests and scans in this section ran on the final code.

**Not measured.** Save GPU memory (cards with 24 GB or less), one image shared by two cards, and cards other than the
RTX 5090. See [KNOWN-ISSUES.md](../KNOWN-ISSUES.md).

## Artegra Enhancer (Beta) 5.0.0-beta.1: build checks (17 November 2026)

These are the build role's checks on a Windows 11 workstation, with the fake engine only: no GPU image was made for
this section. GPU parity is the next section; the release build and the install, upgrade, repair and uninstall
tests are in the section after it.

- **Merge.** The final v5 (frozen copy, tree `3ccc1ddcfbda32a0a1dcbbe2b0eb389d14a86777f5e9ed643858f862b2e07127`, 136
  files) merged onto the standalone. A file-by-file check of the code normal form (Python without comments and
  docstrings; QML/JS without comments) against the final v5, over 142 files: 115 equal it apart from the standalone
  layer, 21 carry only the reviewed Beta changes, 6 are files the final v5 does not have (4 of the standalone's, 2
  new in the Beta), and engine/ and node_pack/ carry no Beta change (one later exception, the preview decoder's
  fallback in node_pack/claude_creative/live.py: see "release QA fixes").
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
  (`tests/test_excluded_features.py`; since the rebuild below, the words are in the maintainer's local word list,
  and without it only the check of what the window loads runs); the public-content scan now refuses both words.
- **Unit and service tests: 842 passed, 7 skipped, 39 subtests passed** (12 extended tests deselected; 10 min 0 s,
  below-normal priority; after the hardening round and its fix below). The 7 skips are the final v5 cases for features the
  standalone does not have, each with its reason (internal two-card proof switch, internal history, finishing in
  the background) and the research notes the recipe test reads when present.
- **Public-content scan:** files passed; history: passed (every blob and commit message reachable from the branches).
  Since fix round 2 the scan also refuses another product's name in any case; since the hardening round, with
  nothing or up to three characters that are not letters or digits (or URL escapes) between its words, in file
  contents and in file names.
- **Secret scans (gitleaks, trufflehog): not run.** The scanners are not installed on this workstation and the
  build role was not cleared to download them. CI runs them on each push; see "release QA fixes" for what it covers.
  Both ran later, on the files and the whole history, and passed: see "secret scans before publishing".
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
- **Hardening round (from an interface audit).** Small, local fixes to defects a colleague could hit, each with a
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
  The full list, and what is planned for a later version, is in KNOWN-ISSUES.md.
- **Screens and privacy.** The release screens are retaken with a made-up, neutral demo output folder (Renders\Enhanced
  on drive D) in place of the temporary state folder, which holds the Windows user name. The earlier sets were withdrawn from the
  release folder. Every published image is checked with Windows OCR for user names and private paths (37 of the 64
  withdrawn images failed that check; every image of the new set passed). Retaken after the hardening fix, with Settings
  opened by a mouse click after a click on Mode: the keys pressed behind it changed nothing, and all 88 images passed
  the same check.
- **Launchers** compile with the icon (C# compiler of the .NET Framework 4.8). The installer was not built in this
  round; it was built, and the install, upgrade, repair and uninstall tests were run, on 18 November (next sections).

## Artegra Enhancer (Beta) 5.0.0-beta.1: GPU parity with the final v5 (17 November 2026)

One GPU run on a separate Windows 11 Pro machine with one NVIDIA GeForce RTX 5090 (32 GB, driver 621.24) and 64 GB of
memory. The Beta's service (commit `15cff2c`) and the final v5's service ran one after the other on the same card, runtime
and models, each through its own HTTP API, one image per job, at seed 20261102, with the same settings and the renders in
the same order. Each service first made two untimed warm-up images, one in Redux and one in Bolt, so that no timed render
paid for a first read of the models. The judge was written, tested and hashed before the run. The numbers are in
[beta-gpu-parity-20261117.json](qa/beta-gpu-parity-20261117.json).

- **Result: passed, 9 of 9 marks.**
- **Pictures.** Each of the Beta's 11 renders equals the final v5's at 0 px (decoded RGB, a maximum difference of 0 over
  all 2,359,296 pixels): Redux Default and Light on two 768 px crops, Bolt Default and Light on the same crops, a 4×
  Redux chain on a 384 px crop (two passes) and both warm-ups. Five of them also equal, on both sides, the reference
  renders made during development at the same seed (Redux Default and Bolt Default on both crops, Bolt Light on one). The
  others have no earlier reference, so the final v5's render in the same run is their reference. Save GPU memory (Redux
  Default on the crop alpha 3 used) equals alpha 3's Save GPU memory output at 0 px. Redux against Bolt (largest difference
  194) and Default against Light (144) differ, so the comparison does see a change when there is one.
- **Prompts.** For the 11 renders made by both, every stage prompt the services sent to the engine (12 each) is the
  same once job ids are removed.
- **Times.** Each of the 9 timed renders took within 0.8 % of the final v5's (−0.57 % to +0.77 %): about 173 s for a
  Redux crop, 84 to 92 s for Bolt and 234 s for the 4× chain. The finish time shown before each image was the same in
  both (5.6 min for a Redux crop, 3.0 min for Bolt, 9.9 min for the 4× chain): longer than the measured time, never
  shorter. Save GPU memory took 257 s, with a whole-card peak of 16,548 MiB against about 23,300 MiB with the original
  settings.
- **Memory profile.** On this 32 GB card Auto chose the original settings, as designed.
- **Closing.** Each service closed when asked: the card was back within 512 MiB of its reading at start 0.13 s (final v5)
  and 0.43 s (Beta) after the request, the service exited with code 0 and every process it had started was gone. The
  Beta's service refused a request without its session token (401).
- **Runtime.** The pinned engine runtime was not installed for this run (downloading it was not cleared), so both
  services used the development runtime that the alpha 1 check found equal to the pinned runtime at 0 px (Python
  3.13.14, PyTorch 2.14.1+cu132, ComfyUI 0.42.4). The pinned lock, constraints, source list and patches are unchanged since
  alpha 1. The models were read where they are stored; nothing was copied to the test machine. The install tests of
  18 November then installed the pinned runtime from its publishers, and the installed app's Redux and Bolt renders
  equal this run's Beta renders at 0 px (next section).
- **Two cards: not run.** The test machines have one card each and the two-card machine was not available. The Beta's
  graph builder (with its two-card graph), run order, controls, planner, card policy and the shared image's remaining
  time are code-identical, comments aside, to the files the final v5's two-card Bolt proof ran; the final v5 itself
  equals those files except for the switch that proof turned on. The Beta differs from them only in documented ways: the
  Redux and Bolt names, the standalone's driver check, memory profiles and start-up, and the rule that lets a lone Bolt
  image share cards only on two identical desktop RTX 5090 cards with the original memory settings. That rule has unit
  tests only.
- **First attempt.** The first run stopped itself before starting anything: its free-card check counted desktop programs
  that Windows lists on the card as image engines. The check was corrected and tested, and the run was frozen and its
  judge registered again before it was queued.
- **After the run.** The final v5's last two tab fixes came in afterwards (two QML files, a host test and the docs). No
  engine, node pack, service or runtime file changed, so this run covers the Beta's image path as released.
- **Checks after the tab fixes: 843 passed, 7 skipped, 39 subtests passed** (12 extended tests deselected; 10 min 13 s,
  below-normal priority). The new host test fails on the earlier tab. The public-content scan of files and of history,
  compileall and the host smoke passed, and the file-by-file merge check against the final v5 after its last rounds passes
  for all 142 files. The secret scans were not run (the scanners are not installed here and downloading them was not
  cleared). They ran later and passed: see "secret scans before publishing".

## Artegra Enhancer (Beta) 5.0.0-beta.1: release build and install tests (18 November 2026)

The release files were built on the Windows 11 workstation and installed, used, upgraded, repaired and removed on a
separate Windows 11 Pro build 26300 test machine with one RTX 5090 32 GB (driver 621.24) and 64 GB of memory. Every
step ran unattended in that machine's own Windows account, through the app's real installer and uninstaller. The
numbers are in [qa/beta-install-20261118.json](qa/beta-install-20261118.json).

**Build.** Inno Setup 7.1.1 (the version used for alpha 4), the .NET Framework 4.8 C# compiler, the official CPython
3.13.14 embeddable package (its pinned SHA-256) and the locked dependencies of `uv.lock`.

- The first build stopped in the installer compiler: the uninstall options form called `CreateCustomForm` without
  arguments, which Inno Setup 7 refuses, so the Beta's uninstaller had never been compiled. It now passes the form's
  size, which Inno Setup 7 scales itself (a static test pins the call). The build also copies the SBOM beside the
  installer and the zip and lists all three in `SHA256SUMS.txt`, as alpha 4's release did.
- Two builds from fresh copies of the same commit: 5,404 of the 5,407 package files are byte-identical. The two
  C# launchers differ by 17 and 18 bytes (their PE time stamp and module id; this compiler has no deterministic
  mode), and `PACKAGE-PROVENANCE.json` records their hashes. The SBOM is identical. The installer and the zip differ
  because they carry the launchers (and, in the zip, 532 file times). The tested files below are the first build,
  made from commit `23bd3fe`; they carry the documents as of that commit, before this section was written. They are
  the install-tested build, not the published files: those are a later rebuild (see "release files rebuilt from
  the final commit"), with their checksums in `SHA256SUMS.txt` beside them.

| File | Bytes | SHA-256 |
|---|---:|---|
| `ArtegraEnhancer-5.0.0b1-Setup.exe` | 98,482,367 | `6b3f228d4ef2f260340f3978431c295a739c5e89def078177f6abac08b4872c0` |
| `ArtegraEnhancer-5.0.0b1-windows-x64.zip` | 154,020,138 | `8043c18e882f3d27eae75dbaa3ab6fa8443f7a009704c41c2459171488ab3af4` |
| `SBOM.cdx.json` | 69,995 | `98435b0e60f12c85b9fc409eb7884fda9442722c09c4bd04abe6c42631cdaf1e` |

- At that commit: **845 tests passed, 7 skipped, 39 subtests passed** (12 extended tests deselected), the
  public-content scan passed on the files and the history, compileall passed and the host smoke check passed.
  The secret scanners (gitleaks, trufflehog) were not run here (see "release QA fixes").
- **Windows protection.** Microsoft Defender Antivirus (client 4.18.26100.4, engine 1.1.26100.4, signatures
  1.463.347.0), real-time protection on and no exclusions: custom scans of the installer, the unpacked portable zip
  and the installed app found no threats, and nothing was quarantined while the files were written.

**Test account.** The test machine's account syncs its Desktop, Pictures and Documents folders to a cloud drive. To
keep the test out of that sync, setup ran with the desktop shortcut unticked and with the save location set to a test folder
before setup, so the desktop shortcut and the default Pictures save location were not exercised. Nothing named
after the app appeared in those folders at any point. The AI-files folder was on a network drive.

**Fresh install** (silent). 900.7 s, exit code 0. Setup downloaded the pinned image engine from its publishers and
installed it (PyTorch 2.14.1+cu132; dependency check clean), checked five prepared model files by SHA-256 (copies of
the publishers' files, not downloaded again), downloaded the sixth (4xRealWebPhoto, 139.8 MB) from its publisher and
checked it, and passed its graphics check.

- Installed apps: **Artegra Enhancer (Beta)**, publisher Studio Artegra, version 5.0.0-beta.1, the app's icon, size
  about 397 MB (the app only; the AI files are not counted there). Start menu: **Artegra Enhancer (Beta)** and
  **Uninstall Artegra Enhancer (Beta)**.
- `ArtegraEnhancer.exe --smoke` passed. A normal start through the desktop launcher brought up the window and its
  engine service (handshake in 1 s). `ArtegraEnhancer.exe --quit-running`, the uninstaller's quit path, closed the
  launcher, the window and the service in 0.3 s (exit code 0); nothing of the app was left running.
- **One Redux and one Bolt image through the installed app's own window** (offscreen, through the tab's own
  functions; the first image after start, models read from the network drive): Redux Default 2× on the S4a crop in
  248 s (5.6 min shown), and Bolt Default 2× on the S1a crop in 92.5 s (3.0 min shown), saved as
  `S1a_cu2x_bolt.png`. **Both equal the GPU parity's Beta renders at 0 differing pixels** (1536 × 1536), with the
  same recorded settings, so the freshly installed engine gives the same pixels as the engine used for parity.
- **Check for updates** (a real request to GitHub): "Artegra Enhancer (Beta) 5.0.0 Beta 1 is up to date." The newest
  Artegra Enhancer release on GitHub was 0.1.0-alpha.4.
- **Uninstall from Windows, interactive** (its windows answered by window messages in a session no one was connected
  to): one confirmation ("Uninstall Artegra Enhancer (Beta)? …"), then the options form with both boxes unticked
  ("Also remove downloaded enhancement files (about 21 GiB)", "Also remove settings and logs"), then "Artegra
  Enhancer (Beta) was successfully removed from your computer." No second prompt. The options form appeared about
  117 s after the confirmation, while the uninstaller measured the AI files on the network drive; nothing else was on
  screen in that time. The app, its shortcuts and its Installed apps entry were removed; settings, AI files and
  every image were kept.
- Installing again over the kept files took 155 s; nothing was downloaded again.
- **Silent uninstall with `/REMOVESETTINGS=1`**: the app and its settings and logs were removed (no app folder was
  left under Local AppData); the AI files and every image were kept.

**Upgrade, repair and uninstall** (a second run on the same machine, starting where the first ended).

- **Upgrade from alpha 4.** The published alpha 4 installer (its SHA-256 matches the GitHub asset) installed over the
  kept AI files in 158.8 s. Installing the Beta over it took 153.8 s, exit code 0: one Installed apps entry, now
  **Artegra Enhancer (Beta)** 5.0.0-beta.1 (it was "Artegra Enhancer 0.1.0a4"), and the alpha's Start menu folder and
  its two shortcuts replaced by the Beta's. A file put in the settings folder under alpha 4, the saved locations, the
  AI files and every image were kept, and the Beta started. Setup showed no terms page because it ran silently; the
  wizard shows that page on every install, an upgrade included (INSTALL.md says so).
- **Repair.** Running the installer again over the Beta took 153.4 s (exit code 0). With the image engine's install
  record and the installation record deleted, the installer's setup worker, which runs the same installation code as
  **Settings → Repair installation**, restored both in 1,384 s (it reinstalled the image engine from its own download
  cache onto the network drive), and the app started afterwards.
- **Uninstall while an image is running.** A Redux image was running in the installed app (4,104 MiB in use on the
  card), and two unrelated processes named `ArtegraEnhancer.exe` and `python.exe` were running from another folder.
  The silent uninstaller closed the app, its service and its engine through the quit path and removed the app in
  2.3 s. The app exited with code 0, the card went back to its idle 1,315 MiB, and both same-named processes were
  left running. Settings, AI files and images were kept (`/VERYSILENT` keeps everything). The unfinished image
  carried on the next time the app opened.
- **Both options** (`/VERYSILENT /REMOVEFILES=1 /REMOVESETTINGS=1`): 648.8 s with the AI files on the network drive.
  The six model files and the image engine's own files were removed. A file the test had put in the models folder
  and one in the engine folder were kept (the engine folder kept its two marker files beside it), the settings and
  logs were removed apart from one file the test had put in the settings folder, which is kept by design, and every
  image was kept. This ran silently because the in-app attempt in the same run could not open: the image stopped
  by the previous step resumed when the app opened, and **Uninstall Artegra Enhancer…** is disabled while images are
  being made ("Finish or cancel the current image work first.").

**Settings → Uninstall in the app** (a third run: a fresh install again, 874.5 s, then the app opened with no image
running).

- **Uninstall Artegra Enhancer…** asked once: "Uninstall Artegra Enhancer (Beta)?" with **Uninstall** and **Keep
  it**. After **Uninstall** the app closed itself (exit code 0) and the registered uninstaller showed only its options
  form, no second confirmation, about two minutes later (measuring the AI files on the network drive). With only
  "Also remove downloaded enhancement files (about 21 GiB)" ticked, the six model files and the image engine's own
  files were removed (the files the test had put there were kept), the settings and every image were kept; it finished
  780 s after the app was opened.
- The app's empty registry key (Software\Studio Artegra under the current user) is part of its settings: the settings
  option removes it, and an uninstall that keeps settings leaves it, empty. The test removed it afterwards, and the
  account then matched its state before the first install, apart from the test's own network folders.

Of the 65 checks in the three runs, 61 passed. The other four were test design, not the app: the in-app uninstall
attempt in the second run (repeated and passed in the third), and three checks that expected folders to be empty
where the app keeps, by design, a file it did not make or the settings a files-only uninstall keeps. Each is
explained in the record.

Not exercised: the setup wizard's pages (every install ran silently; the uninstaller's own windows were driven), the
desktop shortcut and the default Pictures location (see "Test account"), the **Repair installation** button itself,
`/SILENT` without the options form, and two RTX 5090 cards (one card per test machine).

## Artegra Enhancer (Beta) 5.0.0-beta.1: release QA fixes (18 November 2026)

An independent QA round of the release build found six defects to fix before publishing. Each is fixed at its root
with a test. No GPU or install run was repeated, for the reasons given under each item.

- **A private path in a test.** A ported test named a folder at a private network location. The Beta's commits had not
  been pushed, so the test was changed in the commit that added it: it reads that folder from `CU_FAST_FIX_PACKET`
  and is skipped when the variable is unset, like the other tests that need research files. The 31 later commits
  were replayed unchanged, so no commit to be published carries the path. Those commits have new numbers (the
  parity run's commit is now `15cff2c`, the tested build's `23bd3fe`); each one's files differ from before only in
  `tests/engine/test_fast_split.py`. With the variable set on the workstation, the test (the one-card and shared
  Bolt graphs against the proven packets) passed.
- **Public-content scan.** It now refuses Windows network paths, written plainly, in a raw string or escaped, and,
  where the maintainer's local word list is present, private server and folder names, in file contents and file
  names (`tests/test_public_scan.py`).
- **The preview decoder's fallback.** The node pack's live preview fell back to a fixed location for its
  decoder when the models folder had none. The fallback is now empty: loading it fails at once and the live preview uses the rough picture
  (`tests/test_node_pack_preview_fallback.py`). It is empty rather than no path because ComfyUI's preview decoder,
  given no path, starts with untrained weights. In the installed app the fallback is not reached: the service asks
  for the detailed preview only when the decoder file is in the models folder, and the workers register that folder,
  so the node pack finds the decoder there first. Saved images do not use this decoder, so the parity and install
  results above stand. `node_pack/MANIFEST.json`, which the engine checks at start, records the file's new hash:
  the first full test run after the change failed 17 tests because the engine refused the changed file until the
  manifest matched. This file and its manifest entry are the node pack's only changes.
- **Secret scans.** CI scanned only an export of the current files, so the history was never secret-scanned.
  `tools/check_secrets.py --history` now also scans every commit of every branch and tag (gitleaks `git` over all
  refs, trufflehog `git` offline), and CI runs it on each push and pull request that touches the app
  (`tests/test_check_secrets.py`). When these fixes were made, neither scanner had been run for this beta. Both have
  since run on the files and the whole history, with the same commands, and passed (see "secret scans before
  publishing"). The new CI step itself has not yet run on GitHub. CI's file scans passed on alpha 4's commit on GitHub. A pattern search of every blob and commit
  message reachable from any branch or tag, for GitHub, AWS, Slack, OpenAI, Anthropic, Hugging Face and Google keys,
  bearer tokens and private-key headers, found nothing; it does not replace the scanners.
- **A test fixture that read as a key.** `tests/fixtures/beta-normalised-hashes.json` put each pinned SHA-256 straight
  after its file name, and for `service/api.py` that line meets every condition of gitleaks' generic API key rule
  (checked against the rule's text in gitleaks 8.30.1's default settings, not by running gitleaks). The fixture now
  lists `{"path", "sha256"}` objects, as `docs/SOURCE-MAP.json` does, with the same pins, and
  `tests/test_final_v5_layer.py` reads that shape and fails on a file listed twice. Its earlier versions stay in the
  history to be pushed, so `.gitleaks.toml`, at the repository root for the history scan and in `artegra-enhancer/`
  for the file scan, keeps gitleaks' default rules and turns off only that rule, only for that file. Neither file
  ships. gitleaks 8.30.1 has since confirmed both the fix and these settings (see "secret scans before publishing").
- **SBOM.** It described the build environment (52 components, among them pytest, PyInstaller and Qt modules the
  package does not ship) and had no root component. It now describes the package: Artegra Enhancer (Beta)
  5.0.0-beta.1 as `metadata.component`, the node pack, the six Python distributions in the desktop runtime (the
  build stops if they differ from `PACKAGE-PROVENANCE.json`), the CPython 3.13.14 embeddable runtime with its pinned
  SHA-256 and the two Instrument Sans files, and every dependency reference resolves (`tests/test_sbom.py`).
- **Documents.** README, the release notes, the CHANGELOG, KNOWN-ISSUES, the release checklist and DECISIONS no
  longer use internal names; PROVENANCE says what "the final v5" is.
- **Checks at the code commit `1aa867d`: 860 tests passed, 8 skipped, 39 subtests passed** (12 extended tests
  deselected; 11 min 15 s, below-normal priority, in a fresh copy with every branch and tag). The eighth skip is the
  test above, without its variable. The public-content scan passed on the files and on the history,
  compileall passed and the host smoke check passed. The commit after it changes documents only.
- **Published files.** The tested build's files carry documents that are now out of date, so the published files are
  a rebuild of the release commit, made twice from fresh copies and compared file by file with the tested build.
  Only these may differ: the documents, the SBOM, `node_pack/claude_creative/live.py` and `node_pack/MANIFEST.json`,
  the two launchers (their time stamp and module id) and `PACKAGE-PROVENANCE.json`. Their checksums are in
  `SHA256SUMS.txt` beside them; a document inside the package cannot hold the package's own checksum. They were
  rebuilt again from the final commit (see "release files rebuilt from the final commit").

## Artegra Enhancer (Beta) 5.0.0-beta.1: secret scans before publishing (18 November 2026)

Before the Beta's first push, both secret scanners ran on the Windows 11 workstation, on the files and on every
commit of every branch and tag. Both passed. Nothing real was found, so no commit was rewritten.

**Scanners.** `tools/fetch_audit_tools.py` fetched the pinned releases from each project's GitHub release page and
checked each archive against the checksums file published with it. The archive SHA-256 values below are the
release's published digests; the executables' are of the files that were run.

| Scanner | Archive | Bytes | Archive SHA-256 | Executable SHA-256 |
|---|---|---:|---|---|
| gitleaks 8.30.1 | `gitleaks_8.30.1_windows_x64.zip` | 8,438,883 | `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e` | `17157e2ee8b76fc8b1d8bee607a250e34b8a8023c8bc81822d4b5ee4d78fcb7c` |
| TruffleHog 3.99.9 | `trufflehog_3.99.9_windows_amd64.tar.gz` | 77,546,391 | `da6754ea6f16be84fbda9860bdc49492edfa7a141eddc3ac900047fe88d16648` | `a0b790afde1e27db251d85cb398e62de365ac7fb8bb8f946a14c6016c87a2e72` |

No candidate was checked against any service: TruffleHog ran with `--no-update` and `--no-verification`, and
`tools/check_secrets.py` prints no candidate value.

**Results.** At `04417f1`, the tip of the 45 commits to be pushed, and again at the commit that adds this record
(documents only):

- `python tools/check_secrets.py --history` exited 0, with all four of its scans passed. The counts below are from
  the same scans run directly at `04417f1`:
  - gitleaks `dir` on an export of the 589 staged files: about 7.27 MB, no leaks.
  - TruffleHog `filesystem` on the same export: 1,119 chunks, 8,859,409 bytes, no results.
  - gitleaks `git --log-opts=--all`: 60 commits, which is every commit reachable from any branch or tag
    (`git rev-list --all`), about 7.68 MB, no leaks.
  - TruffleHog `git file://.`: 1,933 chunks, 7,631,195 bytes, no results. Its clone of the local repository worked
    on Windows, so `--trust-local-git-config` was not needed. The branches and tags it clones reach all 60 commits.
- `python tools/check_secrets.py` (the file scans alone) passed too.
- The public-content scan passed on the files and on the history.

**The fixture settings, checked with gitleaks itself.**

- The current `tests/fixtures/beta-normalised-hashes.json` passes with gitleaks' default rules alone. The new
  shape fixes it; the exception in `.gitleaks.toml` is needed only for the earlier versions in the history.
- Those four earlier versions, scanned with `gitleaks dir` and the default rules alone, give 4 findings, one per
  version, all from the generic rule at line 21. With the repository's settings they give none.
- The history scan with the default rules alone finds 1 leak: the commit that added that line (`a5afa5f`). gitleaks
  reads each commit's changes, so the later versions add none. With the repository's settings it finds none. So
  without the exception, CI's history step would have failed on the first push.
- The exception is narrow. With the repository's settings, a made-up GitHub token in that file is still found by
  the GitHub token rule, and the old fixture's content under another path is still found by the generic rule.
  These test files existed only in a temporary folder.

**Not yet run:** CI's own history step on GitHub. It runs on the first push.

## Artegra Enhancer (Beta) 5.0.0-beta.1: images of the GitHub page (18 November 2026)

The banner, the two mode marks and the nine app screens in `docs/assets` are made offscreen by
`docs/assets/make_assets.py`; no window opened. The marks are drawn from the app's own stroke lists in `CuIcon.qml`.
The screens come from the app in demo mode (no graphics card), with synthetic facade pictures the script draws, and
show a neutral output folder label instead of the real folder. The setup page is shown with a stand-in for the
installation that lists the real required models and uses the real progress wording.

- **Private text.** Every PNG was read with Windows OCR, and the words each screen showed were recorded while it was
  taken. Both were checked for the Windows user name, profile, AppData and Temp folders, drive and network paths,
  internal folder, machine and service names, the excluded product words and the old mode names: 10 images, no
  finding. Each image was also looked at in full.
- **Files.** The PNGs carry no metadata and are pinned in `asset-hashes.json`; together the images take 1.6 MB.
  Running the script again gives the same banner and marks byte for byte; the screens differ only where they show
  the time of day.
- **Not shown.** The installer's own pages cannot be drawn offscreen, so the installation guide describes them in
  words. No render is shown: a before and after picture needs a render cleared for publication.

## Artegra Enhancer (Beta) 5.0.0-beta.1: rebuilt on the rewritten public history (18 November 2026)

The alpha history on GitHub was rewritten on 18 November 2026 to remove private text: first a server path and
machine names in a few files, then the public-content scan's own list of private words, which it held hex-encoded.
The Beta's 51 commits had not been pushed, so they were rebuilt with git plumbing on the rewritten main (`fc867e0`,
alpha 4). Each keeps its author, committer, dates and message. Three messages were reworded so they no longer
describe the removed text, and the commit numbers cited in messages and in these records were renumbered (the
parity run's commit is now `15cff2c`, the install-tested build's `23bd3fe`, the code commit of the release QA
checks `1aa867d`).

- **What changed in the rebuilt commits.** In every commit that has them: the public-content scan and its tests
  read the specific words from the untracked `.local/private-terms.txt` instead of holding them encoded, and two
  other tests read them the same way (`tests/test_excluded_features.py`, `tests/service/test_qa_engine.py`). The
  files the alpha rewrite changed take its versions, `node_pack/MANIFEST.json`, `SOURCE-MAP.json` and the layer
  fixture follow wherever they described those files, and the passages of these records that described the removed
  text were reworded. A commit-by-commit comparison found no other change: the same files and modes, the code
  normal form of `engine/`, `node_pack/` and `service/` unchanged apart from `node_pack/MANIFEST.json` and one
  string constant in some of the earlier commits, and every manifest, SOURCE-MAP and fixture entry exactly as
  consistent with its file as before.
- **Runs recorded above.** The GPU parity run, the release builds, the install tests and the checks in the
  sections above ran on the commits before this rebuild. Their renumbered commits differ from those only as listed
  here. The only difference in image code is that string constant in the parity commit, which saved images do not
  use, so the parity and install results stand.
- **Public-content scan.** The scan now holds no specific word in any encoding. With `.local/private-terms.txt`
  present it checks the same words as before, as well as the generic patterns. Without it, as in CI, it checks
  the generic patterns only and says so. The installer's publisher line is exempt only in its exact form, which
  the scan recognises by its SHA-256. A line of that form with any other listed word fails
  (`tests/test_public_scan.py`). With the file in place, the new scan and the one before it gave the same result
  on all 935 blobs and commit messages reachable from any branch or tag, and on 349 made-up inputs.
- **Checks on the code of `f9eed22`** (fresh local copies, below-normal priority). Without the local word list, as
  in CI: 860 tests passed, 11 skipped (the 8 earlier skips and the 3 word-list checks), 39 subtests passed, 12 extended
  tests deselected (9 min 57 s). With it: 863 passed, 8 skipped. compileall and the host smoke check passed. The
  public-content scan passed on the files and on the history (every blob and commit message reachable from any
  branch or tag, 67 commits), with the word list and without it. `tools/check_secrets.py --history` (gitleaks
  8.30.1, TruffleHog 3.99.9) passed all four of its scans. A decoded search of every blob, file name and commit
  message reachable from the branch, for the listed words written plainly or encoded (hex, base64, base32,
  base85, URL and backslash escapes, UTF-16, reversed, ROT13 and joined forms), found them only in the
  installer's publisher line; its other matches were random bytes in images and hashes.

## Artegra Enhancer (Beta) 5.0.0-beta.1: release files rebuilt from the final commit (19 November 2026)

The GitHub page changed documents that ship inside the installer and the portable zip, and the commits were rebuilt
on the rewritten history (see the section above), so the release files were built again from the branch's final
commit, `8a950ce`, with the same tools as before: Inno Setup 7.1.1, the .NET Framework 4.8 C# compiler, the CPython
3.13.14 embeddable package at its pinned SHA-256 and the dependencies locked in `uv.lock`. The build environment
sat in the same folder as for the earlier builds, because two dependency records in the package list hashes of
files that contain that folder's path.

- **What changed in the package.** Compared file by file with the previous release build: 5,381 files are
  byte-identical, 27 differ and 17 are new (in `docs/`: three guides, and the GitHub page's images and the script
  that makes them). Every file that differs or is new is one the commits changed (documents,
  `node_pack/MANIFEST.json`, and `service/workers.py` and `node_pack/claude_creative/__init__.py`, where only
  docstrings changed), or one of the two launchers and `PACKAGE-PROVENANCE.json`. The SBOM is identical. The 513
  package files that come from the repository equal the commit's files byte for byte, the documents included.
- **Nothing private ships.** A decoded search of every file in the package (the zip holds exactly these files),
  the SBOM and the checksums file, for the maintainer's private words and the build machine's account, folder and
  network names, written plainly or encoded, found none. The other matches were the app's own name with its
  punctuation removed, licence authors' e-mail addresses, the in-house product's earlier name in code names every
  alpha published, and random bytes in images, hashes and third-party libraries.
- **Checks at `8a950ce`** (a fresh local copy with every branch and tag, below-normal priority). With the local
  word list: **863 tests passed, 8 skipped, 39 subtests passed** (12 extended tests deselected; 9 min 59 s), the
  public-content scan passed on the files and on the history, `tools/check_secrets.py --history` passed all four
  of its scans, and compileall and the host smoke check passed. Without the word list, as in CI: the
  public-content scan passed on the files and on the history (generic checks only), and the document and scan tests
  gave 55 passed and 3 skipped (58 passed with the list).

**Install check** on the test machine of the earlier sections, in its own Windows account, unattended and offscreen,
with the same precautions (desktop shortcut unticked, the save location set to a test folder before setup). The six
AI files were the publishers' files, prepared beforehand in the AI-files folder on a network drive and read there.

- **Fresh install** (silent) of the build of `8a950ce`: 902.7 s, exit code 0. Setup downloaded and installed the
  pinned image engine from its publishers (PyTorch 2.14.1+cu132), checked the six AI files by SHA-256 and downloaded
  none, and passed its graphics check. Installed apps: **Artegra Enhancer (Beta)**, Studio Artegra, 5.0.0-beta.1,
  with its icon. Start menu: the app and **Uninstall Artegra Enhancer (Beta)**. Nothing named after the app appeared
  in the account's synced folders.
- **Installed files.** 5,421 of the package's 5,425 files were installed, each identical to the package's copy
  (SHA-256), and the uninstaller's own two files are the only additions. The four left out are third-party files the
  app never opens: two test inputs of NumPy's f2py whose names start with a dot, and two Qt build objects in a
  `.qt` folder. The network drive the build ran on marks such names hidden, and the installer compiler leaves hidden
  files out. The portable zip has all four. This was the one check of 26 that did not pass.
- `ArtegraEnhancer.exe --smoke` passed. A normal start through the desktop launcher brought up the window and its
  engine service (handshake in 1 s). `ArtegraEnhancer.exe --quit-running` closed the launcher, the window and the
  service in 0.3 s (exit code 0); nothing of the app was left running.
- **One Redux and one Bolt image through the installed app's own window** (the first image after start): Redux
  Default 2× on the S4a crop in 249.1 s (5.6 min shown), and Bolt Default 2× on the S1a crop in 92.9 s (3.0 min
  shown), saved as `S1a_cu2x_bolt.png`. **Both equal the GPU parity's Beta renders at 0 differing pixels**
  (1536 × 1536), with the same recorded settings.
- **Check for updates** (a real request to GitHub): "Artegra Enhancer (Beta) 5.0.0 Beta 1 is up to date." The newest
  Artegra Enhancer release on GitHub was 0.1.0-alpha.4.
- **Windows protection.** Microsoft Defender Antivirus (client 4.18.26100.4, engine 1.1.26100.4, signatures
  1.463.355.0), real-time protection on: custom scans of the installer, the unpacked portable zip and the installed
  app found no threats.
- **Uninstall keeping the images** (`/VERYSILENT /REMOVESETTINGS=1`): 2.1 s. The app, its shortcuts, its Installed
  apps entry, its settings and logs and its registry key were removed. The two results with their recipe files and
  an earlier picture in the save folder were kept, and so were the AI files and the image engine. The account then
  matched its state before the install.

**Published files.** This section ships inside the package, so the published files are built again from the commit
that adds it, twice from fresh copies, and compared file by file with the install-checked build: only this file,
`docs/BUILD-RESULTS.json`, the two launchers and `PACKAGE-PROVENANCE.json` may differ. Their checksums are in
`SHA256SUMS.txt` beside them; a document inside the package cannot hold the package's own checksum.

## Artegra Enhancer (Beta) 5.0.0-beta.1: published on GitHub (19 November 2026)

The Beta was published from `26886e2`, the commit the release files in the section above were built from. This
section was added after publishing, so the copy of this file inside the published files and at the tag does not
have it.

- **Commits and tag.** `main` moved from `fc867e0` (alpha 4) to `26886e2` as a fast-forward of 54 commits; nothing
  was force-pushed. The tag `artegra-enhancer-v5.0.0-beta.1` is a lightweight tag on `26886e2`, like the alpha tags.
- **Release.** [Artegra Enhancer (Beta) 5.0.0](https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/tag/artegra-enhancer-v5.0.0-beta.1),
  published on 19 November 2026 (14:22 UTC on 18 November), marked Latest and not a pre-release. It is the
  repository's first Latest release; the four alphas stay pre-releases.
- **Release files.** GitHub's digest of each uploaded file equals its SHA-256 below, and each file downloaded again
  without signing in gave the same SHA-256 and size.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `ArtegraEnhancer-5.0.0b1-Setup.exe` | 99,612,632 | `b0be03de04cb84f69374f1e6ee6fc4051d15bd7f718e24a204360a9141df3fef` |
| `ArtegraEnhancer-5.0.0b1-windows-x64.zip` | 155,270,975 | `169b1d44bd18c57ba273f6a5f67e9b4bc53afdb8781ad4a3172b4761cd7c06a6` |
| `SBOM.cdx.json` | 16,574 | `885256fb133a9beca5756568506f5159d7a9197d326fc941e858f3ec4484784e` |
| `SHA256SUMS.txt` | 289 | `aed596cc022a139eaf3de8157df7f7816253ce5cf346bc649cb3721ec431d20e` |

**Checks from the public side**, without signing in, on 19 November 2026:

- The releases API, asked for the tag and for the latest release, gives this tag and title, not a draft and not a
  pre-release, the release text exactly as written, and the four files with the sizes and digests above. The
  repository's latest-release address opens this release, and its page shows the title and the Latest label.
- The 29 Markdown pages of the repository (all but the third-party licence texts) and the six issue forms were opened
  as github.com shows them on `main`. All 462 links, images and heading anchors on them and in the release text
  (360 different addresses, 23 of them pages outside GitHub) resolved, and every anchor names a heading on its page.
  The 12 images the pages show and the 2 the release text shows from the tag each downloaded with the SHA-256
  recorded for it. The repository's front page and the `artegra-enhancer` folder page both show the banner.
- **Check for updates**, the app's own code run against the live GitHub API: "Artegra Enhancer (Beta) 5.0.0 Beta 1
  is up to date." Given alpha 4's version instead, the same code reports 5.0.0 Beta 1 as available.

**The repository's checks on GitHub failed.** The push to `main` and the tag each started the checks on GitHub's
hosted Windows machine (runs
[44323347228](https://github.com/freddiefiasco/STUDIO-ARTEGRA/actions/runs/44323347228) and
[44323400115](https://github.com/freddiefiasco/STUDIO-ARTEGRA/actions/runs/44323400115)). Both stopped at the test
step: 98 tests failed, 764 passed and 11 were skipped, so the scans after it did not run there. The tests take the
service's memory limit from the machine they run on. That machine has about 16 GB, so the limit is 11.9 GB, and the
service refuses the upscales the tests ask for ("This upscale would need about 30 GB of memory, more than the
11.9 GB the app may use."). 91 of the 98 failures show that refusal. The other 7 look like the same cause: a 2x
scale marked not possible, a plan with no finish time, and five window checks that timed out waiting for an
upscale. The same tests passed in the local checks of the sections above, on machines with more memory. The
release files are not affected; the tests need a fixed memory limit of their own before the checks can pass on
GitHub's machines.

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
default budget on a 32 GB system; the app needs 64 GB of system memory. See
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
