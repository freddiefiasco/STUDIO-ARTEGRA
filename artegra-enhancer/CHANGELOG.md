# Changelog

<!-- release-draft: engines. Kept, changed or removed by the release step from the proof record. -->

## Next release (draft)

- A second engine, the Large-image engine, makes sizes the Classic engine cannot make on your computer, up to 32,000 px on the longest side. The Classic engine keeps every upscale 5.0.1 makes. The plan and the result's caption name the engine, and so does the image's row where it has room.
- Unless your kind of processor was measured before this release, the first Large-image image on a computer waits while the app measures how the processor runs the Large-image engine's finish: about 22 to 25 minutes on our test PC's processor, longer on a slower one.
- A Large-image upscale can restart the image engine between passes to give back the memory the last pass held; the estimated time counts each restart.
- With Protect on, a large pass no longer spills into shared graphics memory: above about 33 MP the protected areas are found by a step that enlarges only the masks it keeps, using far less graphics memory.
- Finish times now count the work on large inputs and outputs. A Redux 6× of a 2350 × 1762 image with Protect on said 81 min and took 115 min; it now says 119 min.
- Graphics cards with 24 GB or less run every upscale 5.0.1 runs on them. With Protect on, the protected areas are found by the step that enlarges only the masks it keeps whenever the usual step would not fit the card; the masks are the same. An image that still needs more graphics memory than the card has runs as in 5.0.1, partly in shared memory, and its note says it can take longer than the time shown. How much longer has not been measured.

<!-- /release-draft -->

## 5.0.1-beta.1

On a 64 GB PC, Redux and Bolt now make 2× of 3500 × 2188 renders, and Redux 4× of 1280 × 1600 images, at full quality. Redux also makes 2× of 2800 × 3500 renders, at the lighter setting their size needs. 5.0.0-beta.1 refused them for memory.

- The memory estimate is now fitted to peaks measured on RTX 5090 PCs, plus a 3 % margin. The old one put 2× of a 3500 × 2188 render at 61.5 GB, so a 64 GB PC refused it in both modes; it peaks at 51 GB in Bolt and 46 GB in Redux.
- The app now keeps back 4 % of the computer's memory, and at least 2.5 GB, so it may use 59 GB on a 64 GB PC and 122 GB on a 128 GB PC. 5.0.0-beta.1 kept back 10 %, and at least 4 GB.
- When an image does not fit in memory at the full setting, the app tries a lighter setting at the same size before refusing it, and the image's caption says "Uses a lighter setting to fit this computer's memory."
- Redux 4× of a 3500 × 2188 render and Redux 6× or 8× of a 1280 × 1600 image need about 65 to 90 GB: a 64 GB PC refuses them with the amount they need, and a 128 GB PC runs them.
- Bolt now says when memory is the reason it cannot take an image, instead of naming its size limit.
- An image waiting for memory now says whether another image holds the memory or it needs more than the app may use. When Windows manages the pagefile, an image no longer waits for memory forever: the room the pagefile has to grow now counts.
- A memory limit 5.0.0-beta.1 set by default becomes the new default when you update; a limit you set yourself is kept.
- A stopped image queued again after updating from 5.0.0-beta.1 keeps its finished passes.
- The tests use a fixed memory figure instead of reading the computer's, so GitHub's 16 GB test machines plan images as any other computer does, and CI runs the privacy and secret scans before the tests.
- On a computer with two cards, an engine idle on one card is stopped when an image on the other card needs its memory; it starts again when it is next needed.
- Every image 5.0.0-beta.1 could make is planned with the same passes and made exactly as before.

## 5.0.0-beta.1

Artegra Enhancer is now a beta: **Artegra Enhancer (Beta)**.

- Renamed the modes: Standard is now **Redux** and Fast is now **Bolt**, in every place you read them. Stored jobs and settings keep working.
- Added a small mark for each mode: Redux's stacked courses and Bolt's strike. They sit beside the names on the Mode control and on every queued image and result, so you can see which mode made what. Each moves once when you choose it; with reduced motion it only fades in.
- A Bolt result is saved as `name_cu2x_bolt.png`. Results named `_fast` from the alphas are still recognised.
- Brought the enhancement tab, its service and the finish-time logic up to date with all their latest fixes: Bolt is offered only after its files are checked, a single Bolt image can share two identical RTX 5090 cards, a shared image's finish time is shown correctly, and the live preview, activity and result views have their fixes. Saved images are made by the same engine and recipes as in the alphas; only the live preview's fallback changed.
- Bolt shares one image across two cards only on two identical desktop RTX 5090 cards with the original memory settings, the hardware that was proven. Everywhere else each Bolt image uses one card, and the finish time says so.
- Added **Check for updates** in Settings and a new **About** page. The check runs only when you click it and never downloads or installs anything.
- Added a Windows uninstaller: an Installed apps entry with the app's name, publisher, version and icon; a Start menu uninstall shortcut; and **Settings → Uninstall Artegra Enhancer…**. It closes only the app's own processes first, and offers to also remove the downloaded enhancement files and the settings and logs, both off by default. It never removes your images.
- Installing the Beta over an alpha upgrades it in place and keeps your models, settings, outputs and memory choice. An alpha's shortcuts are replaced.
- Added an app icon made from the Studio Artegra brandmark.
- Renamed the pilot notice to [BETA-TERMS.md](BETA-TERMS.md).
- Settings, About and the setup page now take the keyboard from the image workspace behind them, also after a click on Mode, Scale, Look or the image list: keys pressed there no longer start, remove or change images. Esc closes Settings and About. If the image engine stops while a question is open, the question closes.
- PRIVACY.md now describes the .json file saved beside each enhanced image, which holds full file paths.
- Opening the app shows "Opening your workspace" while the image engine starts, instead of the setup screen and a progress bar that never moved.
- If the image engine stops, the window says so and offers **Try again**; unfinished images carry on when it starts again.
- When an image runs out of graphics memory, **Try again with Save GPU memory** is offered (it asks first) instead of the same request.
- Slider rulers and progress tracks have more contrast.
- The enhancement tab's remembered choices (scale, Look, protected areas) are kept with the app's settings folder instead of being shared by every copy; an upgrade keeps them.
- The tab follows Windows' Animation effects setting. The close question goes away when the batch ends. The Shortcuts list no longer shows a key the window does not have. Check for updates stops on time when GitHub answers slowly.
- Two more tab fixes. With the form in Bolt, choosing a Look past Default, 4× or more, or fine-tuning now sets the Mode to Redux and says why, where before the Mode still showed Bolt while Start sent Redux. Undo of "Every waiting image set to 2×" now puts back only each image's own factor, and a Bolt image going back above 2× is put in Redux with a notice. During a long check of Bolt's files, a waiting Bolt image no longer falls back to its earlier settings.
- When the models folder has no detailed-preview decoder, the live preview shows the rough preview. It no longer looks for the decoder in a fixed location.
- The SBOM now lists what the package ships: the app, its Python packages, the bundled Python runtime and the bundled font. It no longer lists the build tools.
- The public-content scan refuses network paths. CI now scans every commit for secrets as well as the current files.
- The public-content scan reads its private words from an untracked local file, so the repository no longer holds them in any form. Without that file, as in CI, it runs only the generic checks. The installer's publisher line is exempt only in its exact form.
- New guides: [Tips](docs/TIPS.md), [Questions and answers](docs/FAQ.md) and [Troubleshooting](docs/TROUBLESHOOTING.md), which lists the messages the app can show with what to do. The README, the installation guide, the known issues and the privacy and security pages are rewritten, with screens of the app. `docs/assets/make_assets.py` makes the images offscreen, with the demo engine and synthetic pictures.
- Opening an issue on GitHub now offers forms for a problem and for an installation problem, and links to the guides.

## 0.1.0-alpha.4

- Rebuilt Windows installation as a guided app, engine and Standard/Fast setup with one terms review and clear progress.
- Added automatic storage and output locations, computer/space checks, verified downloads, retry/resume and a graphics readiness check.
- Added first-launch recovery and Repair installation; normal use no longer requires terminal commands, runtime folder selection or manually starting the engine.
- Preserved existing settings, enhancement files and output images during upgrades and removal.
- Fixed engine startup in folders containing non-ASCII characters.
- Kept the established image-processing recipes and conservative memory behaviour unchanged.

## 0.1.0-alpha.3

- Added Auto, Original settings and Save GPU memory controls with persistent preferences and safe idle-worker changes.
- Auto selects sequential tile processing and CPU model loading on cards with 24 GB or less. Original tile sizes, model weights and numerical options are retained.
- Qualified the conservative memory-saving path with actual service renders and constrained allocator checks on RTX 5090; other physical GPU models remain unverified.
- Kept the failed smaller-tile experiments and unverified quantized replacements out of the release.

## 0.1.0-alpha.2

- Added first-image RAM/commit checks and safer application memory budgets.
- Added Windows version/native x64 and NVIDIA driver checks, with a documented hardware qualification matrix.
- Improved settings on smaller and scaled displays, installation guidance and software interface rendering fallback.
- Smaller-memory profiles remain withheld after the Minimum candidate failed visual review.

## 0.1.0-alpha.1

- Extracted the Creative Upscaler v5 early preview into a standalone Qt Quick host.
- Preserved Standard and the preview's proven eight-step Fast recipe, including its size and Look restrictions.
- Added separate settings, authenticated local connections and owned-process shutdown.
- Removed private deployment paths and unrelated application integration.
- Added dependency locking, privacy checks, source provenance and packaging scripts.
- Published installer and portable builds with representative reference/runtime parity and installer checks.
