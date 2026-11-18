# Changelog

## 5.0.0-beta.1

Artegra Enhancer is now a beta: **Artegra Enhancer (Beta)**.

- Renamed the modes: Standard is now **Redux** and Fast is now **Bolt**, in every place you read them. Stored jobs and settings keep working.
- Added a small mark for each mode: Redux's stacked courses and Bolt's strike. They sit beside the names on the Mode control and on every queued image and result, so you can see which mode made what. Each moves once when you choose it; with reduced motion it only fades in.
- A Bolt result is saved as `name_cu2x_bolt.png`. Results named `_fast` from the alphas are still recognised.
- Brought the enhancement tab, its service and the finish-time logic up to date with all their latest fixes: Bolt is offered only after its files are checked, a single Bolt image can share two identical RTX 5090 cards, a shared image's finish time is shown correctly, and the live preview, activity and result views have their fixes. The image engine is the one the alphas used.
- Bolt shares one image across two cards only on two identical desktop RTX 5090 cards with the original memory settings, the hardware that was proven. Everywhere else each Bolt image uses one card, and the finish time says so.
- Added **Check for updates** in Settings and a new **About** page. The check runs only when you click it and never downloads or installs anything.
- Added a Windows uninstaller: an Installed apps entry with the app's name, publisher, version and icon; a Start menu uninstall shortcut; and **Settings → Uninstall Artegra Enhancer…**. It closes only the app's own processes first, and offers to also remove the downloaded enhancement files and the settings and logs, both off by default. It never removes your images.
- Installing the Beta over an alpha upgrades it in place and keeps your models, settings, outputs and memory choice. The alpha's shortcuts are replaced.
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
